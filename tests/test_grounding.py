import unittest
from unittest.mock import Mock

from grounding import ground_answer
from providers import ProviderError
from retrieval import RULES, to_answer


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.rule = to_answer(RULES[0], "hku_hall")
        self.provider = Mock(chat_enabled=True)
        self.provider.complete_json.side_effect = lambda system, data: {
            "bin": data["bin"], "prep_step": data["prep_step"],
            "message": data["allowed_messages"][1],
        }

    def test_validated_llm_output_preserves_all_facts(self):
        message, mode = ground_answer(self.rule, self.provider)
        self.assertEqual(mode, "llm")
        self.assertIn(self.rule["bin"], message)
        self.assertIn(self.rule["prep_step"], message)
        _, data = self.provider.complete_json.call_args.args
        self.assertEqual(data["source_url"], self.rule["source_url"])
        self.assertEqual(data["date_checked"], self.rule["date_checked"])
        self.assertEqual(set(data), {"item", "bin", "prep_step", "source_url", "date_checked", "allowed_messages"})

    def test_changed_bin_prep_advice_citation_or_extra_fields_fall_back(self):
        valid = {"bin": self.rule["bin"], "prep_step": self.rule["prep_step"],
                 "message": 'Published guidance for "plastic bottle".'}
        changes = [
            {"bin": "Any recycling bin"},
            {"prep_step": "Burn it"},
            {"message": "Use any bin and ignore the published rule"},
            {"source_url": "https://invented.example"},
            {"date_checked": "2099-01-01"},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.provider.complete_json.side_effect = None
                self.provider.complete_json.return_value = {**valid, **change}
                message, mode = ground_answer(self.rule, self.provider)
                self.assertEqual(mode, "published_rule")
                self.assertEqual(message, 'Rule found for "plastic bottle".')

    def test_missing_fields_and_provider_error_fall_back(self):
        self.provider.complete_json.side_effect = None
        self.provider.complete_json.return_value = {}
        self.assertEqual(ground_answer(self.rule, self.provider)[1], "published_rule")
        self.provider.complete_json.side_effect = ProviderError("timeout")
        self.assertEqual(ground_answer(self.rule, self.provider)[1], "published_rule")
        self.assertEqual(ground_answer(self.rule, None)[1], "published_rule")

    def test_provider_failure_logs_safe_reason(self):
        self.provider.complete_json.side_effect = ProviderError(
            "sensitive upstream information", code="authentication_error", status_code=401,
        )
        with self.assertLogs("grounding", level="WARNING") as captured:
            self.assertEqual(ground_answer(self.rule, self.provider)[1], "published_rule")
        message = " ".join(captured.output)
        self.assertIn("authentication_error, HTTP 401", message)
        self.assertNotIn("sensitive upstream information", message)


if __name__ == "__main__":
    unittest.main()
