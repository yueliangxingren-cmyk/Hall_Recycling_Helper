# Hall_Recycling_Helper
The app is for HKU residents checking a published rule for recycling an everyday item.

## Install and run

Requires Python 3.10+. From this folder:

```bash
py -m venv .venv              # Windows; on macOS/Linux use: python3 -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux use: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Then open http://127.0.0.1:8000 in a browser.

Rules live in `rules.json`. Restart the server after editing it.

## Configure model providers

No provider or model is assumed. Copy
`.env.example` to `.env` and fill in the supplied key, base URL, and model. The
server reads `.env` at startup; existing environment variables take precedence.
Chat uses `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`. Embeddings use separate
`EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, and `EMBEDDING_MODEL` settings. Use the
provider's OpenAI-compatible API root, without `/embeddings` or
`/chat/completions`. The adapter sends bearer authentication and standard
Chat Completions fields to `/chat/completions`; it does not send vendor-specific
parameters. The supplied provider must support JSON-object output mode.

Embeddings are optional and are configured only if the supplied service offers
an embedding model. You may put the same key/base URL in both sets of settings
if the service supports both, or use a separate embedding service. A chat key
alone does not imply access to embeddings. All three chat settings (key, base
URL, model) must be filled before chat calls are enabled; the same applies to
the three embedding settings.

Without credentials, exact names and synonyms still work and return the original
published text. Semantic lookup requires embedding credentials. Provider calls
have 15-second timeouts; model errors never produce new recycling advice.

If the server logs `LLM unavailable`, the message includes a safe diagnostic
code and HTTP status when available. Provider response bodies and credentials
are never logged.

| Diagnostic | What to check |
| --- | --- |
| `authentication_error` / HTTP 401 | The API key belongs to the configured endpoint/account |
| `access_denied` / HTTP 403 | The account has permission to use the model |
| `not_found` / HTTP 404 | Base URL and exact model ID |
| `invalid_request` / HTTP 400 | The model accepts the chat parameters, including JSON-object response mode |
| `rate_limit` / HTTP 429 | Account quota and rate limits |
| `dns_error`, `connection_error`, `tls_error` | Network access, DNS, or certificate configuration |
| `timeout` | The provider did not respond within the request timeout |
| `output_truncated` | The model exhausted its output token budget; reasoning models may consume it before producing final JSON |
| `invalid_json`, `invalid_response` | The provider returned malformed JSON or an incompatible Chat Completions response |

Run `python scripts/smoke_test.py --exact --in-process` to diagnose the chat
integration without requiring embeddings or a localhost listener. Restart the
server after changing `.env`.

## Retrieval and grounding

1. The hazard gate runs before retrieval or model calls.
2. Exact item/synonym matches ignore case and repeated whitespace.
3. For other queries, rule names/synonyms are embedded in batches of ten. Rule
   vectors are cached in memory until server restart. The best distinct item
   must have cosine similarity **strictly above 0.85** and beat the next item
   by at least 0.02. Otherwise the app returns `not_covered`.
4. Rules are selected within the requested context. For the same canonical item,
   authority priority is Hall > HKU > EPD. Existing HKU fields default to HKU
   authority and EPD fields to EPD authority. Optional `hku_source_level` and
   `epd_source_level` fields accept `hall`, `hku`, or `epd`. A hall override is a
   separate rule with the same `item`, its published bin and URL, and
   `hku_source_level: "hall"`. It need not repeat every synonym. Conflicting
   rules with equal authority cause abstention. `hku_hall_covered: false` or
   `epd_smart_covered: false` explicitly marks an unsupported context; existing
   `Not covered...` bin text is also recognized.
5. The LLM receives only the selected published rule, with a JSON-only prompt.
   It chooses an approved message and must copy bin/preparation fields exactly.
   This deliberately limits rewording: arbitrary paraphrases cannot be
   mechanically guaranteed to retain all location exceptions and conditions.
   Added advice, changed fields, unknown keys, malformed JSON, or provider
   failures cause fallback to the original rule. Citation, verification date,
   bin, and preparation text always come directly from the dataset.

The response retains the original fields and adds `matched_item`,
`retrieval_method` (`exact`, `embedding`, `none`), `similarity`, and `grounding`
(`llm`, `published_rule`, `not_applicable`) for API diagnostics. The form keeps
showing the published bin, preparation steps, source, and date.

## Tests

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The tests include one `/ask` integration case with mocked external provider
transport. It exercises actual adapters, embedding retrieval, JSON grounding,
and API serialization, but does **not** validate provider availability.

For a real provider test, start `uvicorn app:app` with both providers configured,
then run this single case against the running server:

```bash
python scripts/smoke_test.py
```

It asks about `plastic beverage bottle` in `hku_hall`, checks the published
plastic-bottle rule including its location exception and all prep steps, and
requires `retrieval_method: "embedding"`, cosine > 0.85 and `grounding: "llm"`.
Any abstention or fallback exits with failure, so missing credentials cannot
appear as a successful live test. To check just the running app and exact rule
without credentials, use `python scripts/smoke_test.py --offline`. Override the
target with `--base-url http://127.0.0.1:8001` if needed.

If only the chat key is supplied, run `python scripts/smoke_test.py --exact`.
This tests exact retrieval, the real LLM provider, grounding validation, and the
HTTP response for one plastic-bottle query. It fails if the LLM falls back to
published text. It does not validate semantic retrieval. The default smoke
command above remains the separate test for semantic retrieval and chat.

If your environment cannot open a localhost port, the same single-case check
can run through the real FastAPI route in process. Install the development
dependencies first, then choose the mode matching your configuration:

| Configuration | Command | What a pass establishes |
| --- | --- | --- |
| No key yet | `python scripts/smoke_test.py --offline --in-process` | Actual API route, exact retrieval, published fields, and response serialization; provider calls are disabled |
| Chat key, URL, and model supplied | `python scripts/smoke_test.py --exact --in-process` | Actual API route, exact retrieval, and validated output from the real chat provider |
| Chat and embeddings supplied | `python scripts/smoke_test.py --in-process` | Actual API route, semantic retrieval above the threshold, and validated output from the real chat provider |

In-process mode changes only how the test reaches `/ask`. Live modes still
make real external provider requests and fail on fallback. These checks do not
prove TCP listening, deployment, or browser behavior.

## Assessment documentation status

The implementation plan records what is implemented, what the tests establish,
and what still needs live evidence. Automated results and mocked integration
results must not be reported as a successful live provider test. The assessment
rubric and requirements PDFs are identified, but their contents could not be
read in this session. Rubric alignment is therefore **pending verification**;
no rubric scores, mandatory sections, word limits, or submission rules have
been inferred. Once readable copies are available, map each actual criterion
to a document section and evidence, and resolve any remaining gaps.

Implementation sequence and acceptance criteria are in `IMPLEMENTATION_PLAN.md`.


## Example core-path check

1. Select **EPD smart bin**.
2. Enter `pencil`.
3. Select **Ask**.
4. Confirm that the interface displays **Checking…** while processing.
5. Confirm that the expected unsupported-item result appears:

   ```text
   Not covered by published rules — please ask your hall office.
   ```

This example checks the live input → processing → output path and unsupported-item guidance.

## Demonstration

The submission recording, `demo.mp4`, shows the running web application and live item checks in 54.49 seconds.
