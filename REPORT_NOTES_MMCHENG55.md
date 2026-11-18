# Report notes: mmcheng55

Prepared 18 November 2026 (Hong Kong). These sections are ready for team editing;
they do not claim that the presentation has been recorded. The implementation
and evaluation preparation were AI-assisted. User review is still required
before claiming personal verification or presenting the results.

## §2 Pipeline

The Hall Recycling Helper serves a web form and a FastAPI `/ask` endpoint.
Requests contain an item (1–500 characters) and one of two contexts:
`hku_hall` or `epd_smart`. Whitespace is normalized and blank inputs are rejected.
A substring-based hazard gate runs before retrieval or model calls. It returns
`refused` for configured hazards such as power banks, paint and syringes. This
conservative mechanism can also reject harmless words containing a hazard term;
it is not a comprehensive hazard classifier.

Retrieval first matches normalized item names and synonyms in the selected
context. For competing rules for the same item, source priority is Hall, then
HKU, then EPD; conflicting equal-priority answers cause abstention. The shipped
43-rule dataset currently contains no Hall-level rules. An optional embedding
fallback compares item-name/synonym vectors using cosine similarity. It requires
a score strictly above 0.85 and a gap of at least 0.02 over the next item. Rule
vectors are cached in memory. Missing embeddings, provider errors, ambiguity,
and explicit lack of coverage produce the `not_covered` response. Embeddings
were not configured for the live evaluation reported here.

For a selected rule, the chat model receives only published rule fields and two
server-approved messages. It must return a JSON object containing exactly
`bin`, `prep_step`, and `message`, copy the bin and preparation text verbatim,
and select one allowed message. The server validates all three fields. It
constructs the authoritative response fields, source URL and checked date from
the dataset. Failed validation or a provider error produces a deterministic
published-rule message. The `grounding` field distinguishes validated `llm`
output from `published_rule` fallback. This design bounds the model's role to
formatting; it does not independently establish the truth of the source data.

## §3 Evaluation method

`scripts/evaluate.py` submits the 30 fixed `tests.csv` requests through the real
FastAPI route using TestClient. Live mode makes external requests to the
configured chat provider using the existing private key. No provider response
is mocked in the live runs. The configured model is `qwen3.8-flash`. Keys and
provider response error bodies are excluded from recorded evidence.

The suite contains ten item pairs across both contexts (20 cases), five hazard
refusals, four unknown/unsupported queries, and one published rejection. Pairs
include plastic bottles, personal-care bottles, aluminium cans, drink cartons,
glass, styrofoam, plastic utensils, rechargeable batteries, office paper and
newspapers. Inputs also exercise aliases, uppercase and excess whitespace.
For each case, checks cover HTTP status, response status, selected item, full
bin and preparation instructions, citation, checked date, retrieval method,
approved message and grounding mode. Expected fields are frozen in the CSV
before the live runs, rather than generated from responses at evaluation time.
They were derived from the project dataset, so this is a regression evaluation
of faithful delivery, not independent verification of recycling advice.

Live success additionally requires `grounding == llm` for all 21 expected `ok`
responses. The nine refused/not-covered cases require no model answer. Offline
success explicitly allows published-rule output. Every run records individual
responses, timings, checks, model, Python/dependency versions, commit identity,
and SHA-256 hashes of inputs and application files. The commit identifies the
base checkout; hashes capture the evaluated uncommitted files.

### Pilot and limitations

The first offline pilot scored 29/30. Its T30 expectation incorrectly assumed
that a single-use battery in EPD context would return `not_covered`. Inspection
of the published-rule contract showed that the app returns `ok` with a factual
rejection message. The fixture was corrected before live testing; application
code and source rules were unchanged. `results/pilot-tests.csv` and
`results/pilot-offline.json` retain that evidence. Final offline results are in
`results/offline.json` (30/30).

The suite is small and deliberately fixed; it is not an estimate of accuracy
on arbitrary user queries. No live semantic retrieval was tested, because no
embedding credentials/model were configured. Unknown inputs therefore exercise
abstention without embeddings. Mocked/vector regression tests separately cover
semantic thresholds and failure handling. TestClient tests route execution and
serialization, not TCP serving, browser rendering or deployment. Latencies
include network and provider work in this environment and are not load-test
measurements. Two repeated runs cannot establish general model reliability.

## §6 Contribution entry (draft for review)

For mmcheng55: Prepared the fixed 30-case CSV and repeatable evaluation runner,
pinned the direct runtime and test dependencies to installed versions, and
executed offline checks and real chat-provider evaluation. Prepared report
sections on the pipeline and evaluation, preserved per-case evidence, and
drafted the presentation segment. Codex assisted with code, evaluation
execution, and writing. The member must review the artifacts and deliver their
own speaking segment; no attendance or recording is claimed here.

## Presentation segment (approximately 35–40 seconds)

“Our helper checks hazardous items first, then looks up the published rule for
the selected recycling system. The language model can only choose approved
wording; bin instructions, preparation steps and citations stay tied to the
rule. I prepared thirty test cases covering both systems, aliases, hazards and
unsupported items, and tested the real chat provider twice. Our evaluation
separates correct fallback answers from successful model responses. These tests
cover the API pipeline; they do not establish live semantic retrieval, because
embeddings were not configured.”

Record this segment yourself in the team's three-minute video with your full
name visible. Replace the result wording with the measured results below if
time permits. The screenshot provides only the account handle, not the full
name; none has been invented.

## Recorded results (18 November 2026)

| Measure | Live run 1 | Live run 2 |
| --- | --- | --- |
| Correct response cases | 30/30 | 30/30 |
| Strict live case passes | 29/30 | 29/30 |
| Validated LLM answers | 20/21 eligible | 20/21 eligible |
| Total measured request time | 157.15 s | 162.69 s |
| Median request latency (all 30) | 6.53 s | 5.64 s |

Both runs returned correct expected content for all 30 cases (100%). Each
scored 29/30 (96.7%) on the strict live criterion: run 1 timed out on T30
(single-use battery, EPD); run 2 timed out on T12 (foam box, EPD). The adapter
reported `timeout` in each case under its 15-second configured timeout, and the
route returned the correct `published_rule` fallback. Each run therefore had
20 validated LLM answers out of 21 eligible cases (95.2%). Both commands
correctly exited with status 1, preserving the distinction between response
correctness and provider success. No retries were used to replace these results.

The two runs used separate app instances and overlapped in wall-clock time;
these latency figures are descriptive and must not be treated as isolated
performance benchmarks. Both used identical suite, rule, application and
dependency hashes. The single-case real chat smoke test also passed.

Evidence: `results/live-run-1.json`, `results/live-run-2.json`,
`results/offline.json`, and `results/unit-tests.txt` (58 regression tests pass).
`pip check` reported no broken requirements. Runtime pins cover the four direct
application dependencies, and the test dependency is also pinned; this is not
a full transitive dependency lock or a fresh-install verification.

Optional sentence for the presentation: “Both runs delivered all thirty
expected answers; each had one model timeout that safely fell back to the
published rule.”
