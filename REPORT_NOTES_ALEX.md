# Report notes (Alex): rules expansion

Working notes for report §1 Background and §5 Data sources. Branch:
`alex/rules-and-locations`. Dates are the dates the pages were read.

## Summary

- **Final rule count: 43** (was 23). I added 20 new rules and corrected 1
  existing rule (`styrofoam box`).
- **Hall-level rules: 0 delivered. Bin-location hints: not delivered.** No
  published HKU hall source states a recycling rule or a recycling-bin
  location (details below). The Hall > HKU > EPD priority logic still exists.
  It is tested only with clearly synthetic fixtures inside
  `tests/test_rules_dataset.py`, and a test asserts that no hall rule ships in
  `rules.json`.
- Test groups covered by the new rules:
  - covered everyday items (e.g. `envelope`, `toilet paper roll core`);
  - cross-system items where HKU and EPD differ (e.g. `plastic utensils`,
    `single-use battery`, and `plastic bag`, which is EPD-only);
  - items without a published EPD smart-bin rule (most new paper and plastic
    items);
  - HKU "don'ts" (e.g. `cookware`, `toothpaste tube`).
- Automated evidence (2026-11-18): `Ran 55 tests ... OK`. The offline
  in-process smoke test passed all 7 checks. No live LLM or embedding provider
  was used for this work.

## Correction to an existing rule

`styrofoam box`, EPD smart bin context. It previously said "Not covered by
EPD published rules". The LegCo written reply LCQ17 (28 Feb 2024) says some
EPD smart recycling bins collect "other plastics", with "polyfoam products"
given as an example. The EPD answer is now `Other plastics, only at EPD smart
recycling bins that collect "other plastics"`. Its `epd_source_url` is now
LCQ17 and its `date_checked` is 2026-11-18. The HKU side is unchanged.

## Sources

The "Cited by" counts below cover the whole dataset (existing and new
rules). Where an EPD answer says "Not covered by EPD published rules", the
cited EPD page is the published scope that does **not** list the item. This
convention comes from the original 23 rules.

| Source (official page) | What was taken | Cited by | Date checked |
| --- | --- | --- | --- |
| HKU re Campaign, Recycling 101: https://www.wastereduction.hku.hk/recycling-101 | The page's "The Correct Choice" and "Final Check Before Recycling" images were read visually because their text is not machine-readable. Paper DOs: envelopes, paper folders, toilet paper roll core, standard paper business cards. Paper DON'Ts: napkins/toilet paper, paper tableware, glued-sticker/adhesive paper, paper contaminated with food. Metals DON'Ts: potato chips cans, beer bottle caps, cookware. Plastics DOs: plastic utensils, CD. Plastics DON'Ts: medicine containers, correction fluid container, toothpaste tube, rubber and silicon products. Glass DON'Ts: tempered/laminated/strengthened glass. Battery DON'Ts: single-use batteries. Prep text: "remove all non-paper materials such as plastic coated pages and plastic tape before recycling"; general guideline "dry and clean" | 20 new rules (HKU side) | 2026-11-18 |
| HKU re Campaign, Photo Guide: https://www.wastereduction.hku.hk/photo-guide | Existing rules only. Re-read to confirm the coverage already used | 13 existing rules | 2026-10-24 (team); re-read 2026-11-18 |
| HKU re Campaign, re Facilities: https://www.wastereduction.hku.hk/re-facilities | Existing rules only. Re-read: smart-bin categories, and the plastic-bottle and glass-bottle location exceptions | 10 existing rules | 2026-10-24 (team); re-read 2026-11-18 |
| EPD Clean Recycling: https://www.wastereduction.gov.hk/en-hk/waste-reduction-programme/clean-recycling | Published EPD clean-recycling categories: paper; beverage and personal-care plastic bottles; metal cans; beverage cartons. No new item is named there, so new paper/plastic/metal items get "Not covered by EPD published rules" | 35 rules (EPD side) | 2026-11-18 |
| LegCo reply LCQ17, 28 Feb 2024: https://www.info.gov.hk/gia/general/202402/28/P2024022800418.htm | Some EPD smart recycling bins collect "other plastics (such as plastic bags, polyfoam products and plastic utensils)" | `plastic utensils`, `plastic bag`, `styrofoam box` (correction), plus 2 existing rules | 2026-11-18 |
| EPD Rechargeable Battery Recycling Programme: https://www.wastereduction.gov.hk/en-hk/waste-reduction-programme/rechargeable-battery-recycling-programme | The programme covers rechargeable batteries only. We did **not** claim that EPD refuses single-use batteries | `single-use battery`, plus 1 existing rule | 2026-11-18 |
| ISD TV API page: https://isd.gov.hk/eng/tvapi/14_ep144.html | Existing `glass bottle` rule only | 1 existing rule | 2026-10-24 (team); **not** re-checked in this work |

### Hall sources searched (none usable)

- Regulations Governing Halls and Flats
  (https://calendar.hku.hk/regulations-governing-halls-and-flats/): defers to
  each hall's own house rules. No recycling text.
- CEDARS housing policies
  (https://housing.cedars.hku.hk/university-accommodation/policies-regulations-and-guidelines):
  no waste or recycling text.
- CEDARS combined residence handbook (https://www.cedars.hku.hk/combine-handbook,
  downloaded 2026-11-18, 30-page PDF): the word "recycl" appears nowhere. Page 7
  mentions only *garbage* collection points. Student Flats residents take
  bagged trash to "the garbage collection point under R.C.Lee Hall". That is
  general waste, not recycling, so it was not used.
- Ching Lin Terrace page (https://wp2.cedars.hku.hk/nonhall/clt/): could not be
  loaded from our environment. A search-engine snippet suggests the page
  mentions recycling bins, but we did not verify it, so nothing was taken from
  it.

## Licence and permission basis

All sources are public educational or government information pages from HKU
(Sustainability Unit, Estates Office) and the HKSAR Government (EPD, LegCo
replies via info.gov.hk). The project is a non-commercial university course
project. It stores short factual statements (bin category and prep step) for
each item, attributes every answer to its source URL with the date checked,
and links users back to the original page. No images or substantial text were
copied from the sources.

## Privacy

The dataset and the new tests contain no personal data. Rules describe items
and bins only. The app stores nothing about users. The CEDARS handbook's
contact numbers and e-mail addresses were not copied into the repo.

## AI-use disclosure: what the AI did vs what Alex checked

**Done by the AI assistant (Claude Code):**
- Repo hygiene (line endings were already clean), branch creation, baseline
  test run (41 OK).
- Read the official pages listed above, including visually reading HKU's
  image-only Recycling 101 guide. Proposed 20 candidate rules with exact
  source wording.
- Searched for hall-level sources and downloaded and searched the CEDARS
  handbook. Reported that no usable hall source exists.
- Wrote the approved rules into `rules.json` and applied the styrofoam
  correction. Validated keys, URLs, duplicates, synonym clashes and hazard
  words.
- Updated two existing tests that hard-coded facts about the old 23-rule
  dataset. One assumed 3 embedding batches; the other assumed every rule is
  HKU-covered. Added `tests/test_rules_dataset.py` (14 tests).
- Drafted the README, the IMPLEMENTATION_PLAN evidence rows and these notes.

**Checked and decided by Alex:**
- Approved the 20-rule table with changes:
  - keep "re Kiosk"-only wording;
  - do not claim "general waste" for rejected items;
  - reword the single-use battery EPD answer so it does not claim EPD
    "does not recycle" them;
  - apply the styrofoam correction.
- Decided to skip hall rules and location hints when no published hall source
  was found, rather than use unpublished information.
- To do before submission: spot-check a sample of the new rules against the
  live pages, and review the final diff before merging.
