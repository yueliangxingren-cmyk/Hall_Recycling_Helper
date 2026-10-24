"""Exact-first, context-scoped retrieval over published recycling rules."""

import json
import logging
import math
from pathlib import Path
from threading import Lock

from providers import ModelProvider, ProviderError

LOGGER = logging.getLogger(__name__)
RULES_PATH = Path(__file__).parent / "rules.json"
SIMILARITY_THRESHOLD = 0.85
AMBIGUITY_MARGIN = 0.02
CONTEXT_TO_BIN_FIELD = {"hku_hall": "hku_hall_bin", "epd_smart": "epd_smart_bin"}
CONTEXT_TO_SOURCE_FIELD = {"hku_hall": "hku_source_url", "epd_smart": "epd_source_url"}
CONTEXT_TO_LEVEL_FIELD = {"hku_hall": "hku_source_level", "epd_smart": "epd_source_level"}
SOURCE_PRIORITY = {"hall": 0, "hku": 1, "epd": 2}


def load_rules(path: Path = RULES_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


RULES = load_rules()


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def source_level(rule: dict, context: str) -> str:
    default = "hku" if context == "hku_hall" else "epd"
    return normalize(rule.get(CONTEXT_TO_LEVEL_FIELD[context], default))


def to_answer(rule: dict, context: str) -> dict:
    return {
        "item": rule["item"],
        "bin": rule[CONTEXT_TO_BIN_FIELD[context]],
        "prep_step": rule["prep_step"],
        "source_url": rule[CONTEXT_TO_SOURCE_FIELD[context]],
        "date_checked": rule["date_checked"],
    }


def choose_rule(matches: list[dict], context: str) -> dict | None:
    """Resolve authorities for one item; refuse conflicting or ambiguous matches."""
    if not matches or len({normalize(rule["item"]) for rule in matches}) != 1:
        return None
    priority = min(SOURCE_PRIORITY.get(source_level(rule, context), 3) for rule in matches)
    preferred = [rule for rule in matches
                 if SOURCE_PRIORITY.get(source_level(rule, context), 3) == priority]
    answers = {json.dumps({**to_answer(rule, context), "covered": is_covered(rule, context)},
                          sort_keys=True) for rule in preferred}
    return preferred[0] if len(answers) == 1 else None


def exact_match(query: str, rules: list[dict], context: str = "hku_hall") -> dict | None:
    names = {normalize(rule["item"]) for rule in rules if query in
             {normalize(name) for name in [rule["item"], *rule.get("synonyms", [])]}}
    return choose_rule([rule for rule in rules if normalize(rule["item"]) in names], context)


def is_covered(rule: dict, context: str) -> bool:
    # New records can use explicit booleans; retain compatibility with existing data.
    return rule.get(f"{context}_covered", True) is not False and not normalize(
        rule[CONTEXT_TO_BIN_FIELD[context]]
    ).startswith("not covered")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.hypot(*left) * math.hypot(*right)
    if not denominator or not math.isfinite(denominator):
        return 0.0
    score = sum(a * b for a, b in zip(left, right)) / denominator
    return max(-1.0, min(1.0, score)) if math.isfinite(score) else 0.0


class RuleRetriever:
    def __init__(self, rules: list[dict], provider: ModelProvider | None = None):
        self.rules = rules
        self.provider = provider
        self._vectors = None
        self._lock = Lock()

    def _documents(self):
        # Names rather than disposal advice: shared bin names must not drive matches.
        return ["; ".join([rule["item"], *rule.get("synonyms", [])]) for rule in self.rules]

    def _rule_vectors(self):
        with self._lock:
            if self._vectors is None:
                self._vectors = self.provider.embed(self._documents())
            return self._vectors

    def find_rule(self, item: str, context: str) -> dict | None:
        if context not in CONTEXT_TO_BIN_FIELD:
            raise ValueError("Unknown recycling context")
        query = normalize(item)
        if not query:
            return None
        eligible = [rule for rule in self.rules if rule.get(CONTEXT_TO_BIN_FIELD[context])
                    and rule.get(CONTEXT_TO_SOURCE_FIELD[context])]
        if not eligible:
            return None
        exact = [rule for rule in eligible if query in
                 {normalize(name) for name in [rule["item"], *rule.get("synonyms", [])]}]
        method, similarity = "exact", None
        if exact:
            # Embeddings must not override ambiguous exact matches.
            rule = exact_match(query, eligible, context)
        else:
            if not self.provider or not self.provider.embeddings_enabled:
                return None
            try:
                vectors = self._rule_vectors()
                query_vector = self.provider.embed([query])[0]
                scores = {}
                for candidate, vector in zip(self.rules, vectors):
                    if not candidate.get(CONTEXT_TO_BIN_FIELD[context]) or not candidate.get(
                        CONTEXT_TO_SOURCE_FIELD[context]
                    ):
                        continue
                    name = normalize(candidate["item"])
                    score = cosine_similarity(query_vector, vector)
                    scores[name] = max(scores.get(name, -1.0), score)
                ranked = sorted(scores.items(), key=lambda row: row[1], reverse=True)
                if not ranked or ranked[0][1] <= SIMILARITY_THRESHOLD:
                    return None
                name, similarity = ranked[0]
                if len(ranked) > 1 and similarity - ranked[1][1] < AMBIGUITY_MARGIN:
                    return None
                rule = choose_rule([r for r in eligible if normalize(r["item"]) == name], context)
                method = "embedding"
            except ProviderError as exc:
                LOGGER.warning("Embedding retrieval unavailable (%s); returning no match", exc.diagnostic)
                return None
        if rule is None or not is_covered(rule, context):
            return None
        return {**to_answer(rule, context), "retrieval_method": method, "similarity": similarity}


# Keep a deterministic helper for callers that don't need semantic retrieval.
def find_rule(item: str, context: str) -> dict | None:
    return RuleRetriever(RULES).find_rule(item, context)
