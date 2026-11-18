"""Checks on rules.json itself, plus one example per proposal test group."""

import unittest
from collections import Counter, defaultdict
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from app import create_app, is_hazardous
from providers import ModelProvider, Settings
from retrieval import RULES, RuleRetriever, normalize

REQUIRED_KEYS = ["item", "synonyms", "hku_hall_bin", "epd_smart_bin", "prep_step",
                 "hku_source_url", "epd_source_url", "date_checked"]
OFFICIAL_HOST_SUFFIXES = (".hku.hk", ".gov.hk")


def by_item(name):
    return next(rule for rule in RULES if rule["item"] == name)


class DatasetTests(unittest.TestCase):
    def test_every_rule_has_required_keys_in_order_and_official_urls(self):
        for rule in RULES:
            with self.subTest(item=rule["item"]):
                self.assertEqual([key for key in rule if key in REQUIRED_KEYS], REQUIRED_KEYS)
                self.assertTrue(all(rule[key] for key in REQUIRED_KEYS if key != "synonyms"))
                for key in ("hku_source_url", "epd_source_url"):
                    url = urlparse(rule[key])
                    self.assertEqual(url.scheme, "https")
                    self.assertTrue(url.hostname.endswith(OFFICIAL_HOST_SUFFIXES), rule[key])

    def test_rule_count_is_at_least_forty(self):
        self.assertGreaterEqual(len(RULES), 40)

    def test_synonyms_are_lowercase_and_names_are_unambiguous(self):
        owners = defaultdict(set)
        for rule in RULES:
            for name in [rule["item"], *rule["synonyms"]]:
                self.assertEqual(name, name.lower(), rule["item"])
                owners[normalize(name)].add(normalize(rule["item"]))
        self.assertEqual({name: items for name, items in owners.items() if len(items) > 1}, {})

    def test_no_duplicate_item_within_one_authority_level(self):
        levels = Counter((normalize(rule["item"]), rule.get("hku_source_level", "hku"),
                          rule.get("epd_source_level", "epd")) for rule in RULES)
        self.assertEqual([key for key, count in levels.items() if count > 1], [])

    def test_no_rule_name_is_caught_by_the_hazard_gate(self):
        names = [name for rule in RULES for name in [rule["item"], *rule["synonyms"]]]
        self.assertEqual([name for name in names if is_hazardous(name)], [])


class TestGroupExamples(unittest.TestCase):
    """One exact-match example per proposal test group, through the real /ask route."""

    def setUp(self):
        self.client = TestClient(create_app(ModelProvider(Settings())))

    def ask(self, item, context):
        return self.client.post("/ask", json={"item": item, "context": context}).json()

    def test_covered_everyday_item(self):
        data = self.ask("Envelopes", "hku_hall")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["matched_item"], "envelope")
        self.assertEqual(data["bin"], by_item("envelope")["hku_hall_bin"])
        self.assertEqual(data["retrieval_method"], "exact")

    def test_cross_system_item_answers_differ_by_context(self):
        hku = self.ask("plastic fork", "hku_hall")
        epd = self.ask("plastic fork", "epd_smart")
        self.assertEqual((hku["status"], epd["status"]), ("ok", "ok"))
        self.assertNotEqual(hku["bin"], epd["bin"])
        self.assertNotEqual(hku["source_url"], epd["source_url"])

    def test_item_not_taken_by_epd_smart_bins(self):
        self.assertEqual(self.ask("toilet roll tube", "hku_hall")["status"], "ok")
        self.assertEqual(self.ask("toilet roll tube", "epd_smart")["status"], "not_covered")

    def test_epd_only_item_is_not_covered_in_hku_context(self):
        self.assertEqual(self.ask("plastic bag", "hku_hall")["status"], "not_covered")
        self.assertEqual(self.ask("plastic bag", "epd_smart")["status"], "ok")

    def test_hku_rejected_item_returns_published_rejection(self):
        data = self.ask("frying pan", "hku_hall")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["bin"], "Not accepted for recycling at re Kiosk")

    def test_styrofoam_epd_correction(self):
        data = self.ask("styrofoam", "epd_smart")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["source_url"],
                         "https://www.info.gov.hk/gia/general/202402/28/P2024022800418.htm")

    def test_hazard_and_not_covered_behaviour_unchanged(self):
        for context in ("hku_hall", "epd_smart"):
            # Hazard words still win even when the rest of the text names a dataset item.
            self.assertEqual(self.ask("lithium aa battery", context)["status"], "refused")
            self.assertEqual(self.ask("paint thinner", context)["status"], "refused")
            data = self.ask("pencil", context)
            self.assertEqual(data["status"], "not_covered")
            self.assertEqual(data["message"],
                             "Not covered by published rules — please ask your hall office.")


class HallPriorityWithNewRulesTests(unittest.TestCase):
    """No published hall source was found, so the hall rule here is synthetic test data only."""

    def test_synthetic_hall_override_beats_hku_for_a_new_rule(self):
        hku = by_item("envelope")
        hall = {**hku, "synonyms": [], "hku_source_level": "hall",
                "hku_hall_bin": "SYNTHETIC TEST HALL BIN",
                "hku_source_url": "https://example.hku.hk/synthetic-test-fixture"}
        for rules in ([hku, hall], [hall, hku]):
            result = RuleRetriever(rules).find_rule("letter envelope", "hku_hall")
            self.assertEqual(result["bin"], "SYNTHETIC TEST HALL BIN")
        # The hall override never leaks into the EPD context.
        epd = RuleRetriever([hku, hall]).find_rule("envelope", "epd_smart")
        self.assertIsNone(epd)

    def test_shipped_dataset_contains_no_synthetic_hall_rules(self):
        self.assertFalse(any(rule.get("hku_source_level") == "hall" for rule in RULES))


if __name__ == "__main__":
    unittest.main()
