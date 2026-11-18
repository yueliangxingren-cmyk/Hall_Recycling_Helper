import math
import unittest
from unittest.mock import Mock

from providers import ProviderError
from retrieval import RULES, RuleRetriever, cosine_similarity, to_answer


def provider_for(vectors, query):
    provider = Mock(embeddings_enabled=True)
    provider.embed.side_effect = [vectors, [query]]
    return provider


class RetrievalTests(unittest.TestCase):
    def test_exact_normalizes_whitespace_and_case_without_embedding(self):
        provider = Mock(embeddings_enabled=True)
        result = RuleRetriever(RULES, provider).find_rule("  WATER   Bottle ", "hku_hall")
        self.assertEqual(result["item"], "plastic bottle")
        self.assertEqual(result["retrieval_method"], "exact")
        provider.embed.assert_not_called()

    def test_existing_names_and_synonyms_match_both_contexts(self):
        retriever = RuleRetriever(RULES)
        for rule in RULES:
            for name in [rule["item"], *rule["synonyms"]]:
                for context in ("hku_hall", "epd_smart"):
                    with self.subTest(name=name, context=context):
                        result = retriever.find_rule(name, context)
                        if rule[f"{context}_bin"].startswith("Not covered"):
                            self.assertIsNone(result)
                        else:
                            expected = to_answer(rule, context)
                            self.assertEqual({key: result[key] for key in expected}, expected)

    def test_no_cross_context_answer_for_unsupported_epd_item(self):
        self.assertIsNone(RuleRetriever(RULES).find_rule("coffee cup", "epd_smart"))
        self.assertIsNotNone(RuleRetriever(RULES).find_rule("coffee cup", "hku_hall"))

    def test_unknown_blank_and_disabled_embeddings_abstain(self):
        retriever = RuleRetriever(RULES)
        for item in ("", " \n ", "dinosaur fossil"):
            self.assertIsNone(retriever.find_rule(item, "hku_hall"))

    def test_embedding_match_is_strictly_above_threshold(self):
        for score in (0.84, 0.85, 0.86):
            with self.subTest(score=score):
                provider = provider_for([[1, 0]], [score, math.sqrt(1 - score ** 2)])
                result = RuleRetriever(RULES[:1], provider).find_rule("beverage container", "hku_hall")
                if score <= 0.85:
                    self.assertIsNone(result)
                else:
                    self.assertEqual(result["retrieval_method"], "embedding")
                    self.assertAlmostEqual(result["similarity"], score)

    def test_semantic_ambiguity_abstains(self):
        provider = provider_for([[1, 0], [0.999, 0.001]], [1, 0])
        self.assertIsNone(RuleRetriever(RULES[:2], provider).find_rule("container", "hku_hall"))

    def test_rule_vectors_cached_queries_not_cached(self):
        provider = provider_for([[1, 0]], [1, 0])
        provider.embed.side_effect = [[[1, 0]], [[1, 0]], [[1, 0]]]
        retriever = RuleRetriever(RULES[:1], provider)
        for _ in range(2):
            self.assertIsNotNone(retriever.find_rule("beverage container", "hku_hall"))
        self.assertEqual(provider.embed.call_count, 3)

    def test_failed_index_is_retried_and_never_partially_cached(self):
        provider = Mock(embeddings_enabled=True)
        provider.embed.side_effect = [ProviderError("unavailable"), [[1, 0]], [[1, 0]]]
        retriever = RuleRetriever(RULES[:1], provider)
        self.assertIsNone(retriever.find_rule("beverage container", "hku_hall"))
        self.assertIsNotNone(retriever.find_rule("beverage container", "hku_hall"))

    def test_hall_priority_over_hku_and_epd_for_same_item(self):
        rules = [{**RULES[0], "hku_source_level": level, "hku_hall_bin": level}
                 for level in ("epd", "hku", "hall")]
        for ordered in (rules, list(reversed(rules))):
            self.assertEqual(RuleRetriever(ordered).find_rule("plastic bottle", "hku_hall")["bin"], "hall")

    def test_hall_override_applies_even_if_only_hku_has_the_synonym(self):
        hall = {**RULES[0], "hku_source_level": "hall", "synonyms": [], "hku_hall_bin": "Hall bin"}
        result = RuleRetriever([RULES[0], hall]).find_rule("water bottle", "hku_hall")
        self.assertEqual(result["bin"], "Hall bin")

    def test_semantic_match_obeys_authority_priority(self):
        hall = {**RULES[0], "hku_source_level": "hall", "hku_hall_bin": "Hall bin"}
        provider = provider_for([[1, 0], [0.9, 0.1]], [1, 0])
        result = RuleRetriever([RULES[0], hall], provider).find_rule("beverage container", "hku_hall")
        self.assertEqual(result["bin"], "Hall bin")

    def test_conflicting_same_authority_abstains_without_embedding(self):
        conflicting = {**RULES[0], "hku_hall_bin": "Different bin"}
        provider = Mock(embeddings_enabled=True)
        self.assertIsNone(RuleRetriever([RULES[0], conflicting], provider).find_rule("plastic bottle", "hku_hall"))
        provider.embed.assert_not_called()

    def test_conflicting_coverage_at_same_authority_abstains(self):
        conflicting = {**RULES[0], "hku_hall_covered": False}
        for ordered in ([RULES[0], conflicting], [conflicting, RULES[0]]):
            self.assertIsNone(RuleRetriever(ordered).find_rule("plastic bottle", "hku_hall"))

    def test_ambiguous_synonym_never_falls_through_to_embeddings(self):
        rules = [{**rule, "synonyms": ["bottle"]} for rule in RULES[:2]]
        provider = Mock(embeddings_enabled=True)
        self.assertIsNone(RuleRetriever(rules, provider).find_rule("bottle", "hku_hall"))
        provider.embed.assert_not_called()

    def test_invalid_vectors_abstain(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 0]), 0)
        self.assertEqual(cosine_similarity([1], [1, 0]), 0)
        self.assertEqual(cosine_similarity([float("nan"), 1], [1, 0]), 0)

    def test_explicit_unsupported_override_does_not_borrow_lower_authority(self):
        hall = {**RULES[0], "hku_source_level": "hall", "hku_hall_covered": False}
        self.assertIsNone(RuleRetriever([RULES[0], hall]).find_rule("water bottle", "hku_hall"))


if __name__ == "__main__":
    unittest.main()
