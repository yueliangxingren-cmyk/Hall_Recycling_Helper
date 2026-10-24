"""Rule retrieval for Hall Recycling Helper.

Current behaviour: exact, case-insensitive match of the user's item against
each rule's "item" or any of its "synonyms" in rules.json.

Planned extensions (each slots into find_rule() as its own step):
  1. Embedding fallback: if no exact match, embed the query and pick the rule
     with the highest cosine similarity, but only if it is > 0.85.
  2. Source priority: when several rules match, prefer Hall > HKU > EPD.
  3. LLM rewording: rephrase the matched rule for the user. This must only
     reword the rule's fields, never add new advice.
"""

import json
from pathlib import Path

RULES_PATH = Path(__file__).parent / "rules.json"

# Which rules.json field holds the bin for each context the frontend can send.
CONTEXT_TO_BIN_FIELD = {
    "hku_hall": "hku_hall_bin",
    "epd_smart": "epd_smart_bin",
}

# Each context cites its own source, so the answer links to the page the bin rule came from.
CONTEXT_TO_SOURCE_FIELD = {
    "hku_hall": "hku_source_url",
    "epd_smart": "epd_source_url",
}


def load_rules(path: Path = RULES_PATH) -> list[dict]:
    """Read all rules from rules.json."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Loaded once at import time. Restart the server after editing rules.json.
RULES = load_rules()


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace so "  Plastic  Bottle " == "plastic bottle"."""
    return " ".join(text.lower().split())


def exact_match(query: str, rules: list[dict]) -> dict | None:
    """Return the first rule whose item or a synonym equals the normalized query."""
    for rule in rules:
        names = [rule["item"], *rule.get("synonyms", [])]
        if query in (normalize(name) for name in names):
            return rule
    return None


def to_answer(rule: dict, context: str) -> dict:
    """Turn a raw rule into the fields the API returns, picking the bin for this context."""
    return {
        "item": rule["item"],
        "bin": rule[CONTEXT_TO_BIN_FIELD[context]],
        "prep_step": rule["prep_step"],
        "source_url": rule[CONTEXT_TO_SOURCE_FIELD[context]],
        "date_checked": rule["date_checked"],
    }


def find_rule(item: str, context: str) -> dict | None:
    """Find the published rule for an item.

    Args:
        item: what the user typed, e.g. "Plastic Bottle".
        context: "hku_hall" or "epd_smart"; decides which bin is returned.

    Returns:
        A dict with item, bin, prep_step, source_url, date_checked,
        or None if no rule covers the item.
    """
    query = normalize(item)
    if not query:
        return None

    # Step 1: exact match on item name or synonym.
    rule = exact_match(query, RULES)

    # Step 2 (TODO): embedding fallback with cosine > 0.85 when rule is None.
    # Step 3 (TODO): if several rules match, apply source priority Hall > HKU > EPD.

    if rule is None:
        return None

    # Step 4 (TODO): optional LLM rewording of the answer fields.
    return to_answer(rule, context)
