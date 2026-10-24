# Retrieval and LLM grounding plan

## Confirmed scope and assessment status

- The API uses the OpenAI-style interface. Configure its base URL and model
  alongside the key in `.env`. No vendor
  or model is assumed, and requests contain no vendor-specific parameters.
- Embedding support is a separate capability to confirm with the supplied
  provider. A chat key alone is sufficient for exact retrieval plus LLM
  grounding, but not proof of semantic retrieval.
- Assessment sources identified: `AILT9019_Midterm_Rubric.pdf` and
  `AILT9019_Midterm_Check_Requirements.pdf`. Their contents could not be read:
  text/page reads returned no content and file downloads failed. **Alignment
  with the actual rubric and requirements is not yet verified.** This document
  is an engineering plan and evidence record, not a completed assessment
  submission or a claim of rubric compliance.

## Implementation sequence

1. Preserve the hazard gate and existing `/ask` response fields. Reject blank or
   oversized requests. Return `not_covered` when the selected context explicitly
   has no published rule.
2. Normalize item names and synonyms, resolve exact matches first, then use
   cosine similarity strictly greater than 0.85 for embedding fallback. Cache
   rule vectors in memory, batch provider requests, and abstain on ambiguity or
   provider failure. Prefer Hall > HKU > EPD for rules for the same item within
   the requested context; never borrow a bin from another context.
3. Load provider settings from environment or `.env`. Configure chat and
   embeddings independently because a chat endpoint may not offer
   embeddings. Bound network requests with timeouts and hide provider errors
   and credentials from API responses and logs.
4. Pass only the selected published rule to the LLM, never user instructions.
   Request structured, extractive output: the model may assemble a message
   using complete published fields, but cannot invent or omit qualifications
   inside them. Validate every returned field and construct source/date/bin/
   preparation fields on the server. Fall back to the original rule on errors.
5. Add regression checks for retrieval threshold, priority, context isolation,
   hazard bypass, malformed/provider failures, and grounding validation. Start
   the real HTTP server and run one request through the whole application.
   A separate live smoke command must require actual embedding retrieval and
   validated LLM output, and fail if either silently falls back.
6. Support the same single-case smoke test through the actual FastAPI app in
   process, avoiding the environment's TCP listening restriction. Offline mode
   explicitly disables model calls; live modes still require real provider
   output. Verify the offline route now and retain the live checks for the key.

## Acceptance

- Existing exact/synonym queries still work without credentials.
- Unknown, ambiguous, hazardous, or unsupported inputs cannot receive invented
  advice or citations.
- Tests can run without API credentials; live-provider evidence must be
  reported separately from mocked-provider or deterministic checks.
- With only chat configured, `python scripts/smoke_test.py --exact` must pass
  exact retrieval and validated live LLM output for `plastic bottle`. This does
  not establish that embeddings work.
- Live test input: `plastic beverage bottle` in `hku_hall`; expected published
  rule: `plastic bottle`, including its location exception and prep steps.

## Environment discovered before implementation

The checkout has no `.env`, no chat/embedding credentials in the process
environment, and no installed app dependencies. Live provider validation is
blocked until credentials are configured. Do not substitute mocks and describe
them as a successful live LLM test.

## Validation result

- Implemented exact-first semantic retrieval, authority priority, explicit
  context abstention, independent provider configuration, and constrained JSON
  grounding with published-rule fallback.
- Installed application and test dependencies from existing cached wheels after
  PyPI DNS resolution failed.
- All 41 automated regression and API tests pass. The single semantic `/ask`
  integration case covers rule embedding batches, query embedding, rule
  selection, LLM JSON validation, and API serialization. External HTTP transport
  is mocked; this is not a live provider check.
- Uvicorn completes application startup, but binding `127.0.0.1:8765` fails with
  `Operation not permitted` in this execution environment. No listening server
  remains running.
- The single offline end-to-end case passes through the actual FastAPI route:
  `python scripts/smoke_test.py --offline --in-process`. All seven assertions
  pass: matched published item, status, full bin instruction including location
  exception, every preparation step, HKU citation, date, and exact retrieval.
  Provider calls are disabled; the result correctly reports
  `grounding: "published_rule"`. This is application evidence without a TCP
  listener, not evidence of a live LLM or a deployed browser experience.
- Provider credentials, URL, and model are now configured. The live exact-case
  smoke test reaches the provider adapter but fails with `dns_error` because
  this execution environment cannot resolve the configured host. Published-rule
  fallback works, and the smoke test correctly fails its live-LLM assertion.
  This does not establish the cause of an error in a separately running server.
  From a terminal with working provider network access, run
  `python scripts/smoke_test.py --exact --in-process` for chat-only validation,
  or `python scripts/smoke_test.py --in-process` for embeddings plus chat.
  Both require real provider results and fail on fallback. To also verify TCP
  serving, start `uvicorn app:app` and omit `--in-process` from the smoke command.

## Evidence and outstanding work

| Check | Current evidence | Remaining action |
| --- | --- | --- |
| Exact and synonym retrieval | Automated tests against both supported contexts | None for local logic |
| Embedding threshold and source priority | Controlled-vector tests and mocked transport integration | Validate the actual provider/model; retain the threshold unless separately justified |
| LLM grounding | Tests reject altered bin/prep text, added advice, and invented provenance; failures log safe diagnostic codes | Run one live chat-backed case with provider network access |
| Published source and date | API fields are copied from `rules.json` | Dataset provenance is retained; independent source re-verification is outside these tests |
| API route and serialization | Single offline end-to-end case passes through the actual FastAPI app in process | Live model calls need provider network access; TCP serving needs a terminal that permits listening |
| Rubric coverage | Source PDF identities resolved, contents unavailable | Obtain readable text/pages, enumerate actual criteria, and add criterion-to-section mapping |
| Required submission format and sections | Not yet known | Confirm against the requirements PDF before calling this submission-ready |

After readable assessment sources are available, verify their precise criteria,
format/length limits, required demonstrations and evidence, and any source or
AI-use disclosure requirements. Record only requirements actually stated in
those sources. Keep unperformed live checks explicitly pending.
