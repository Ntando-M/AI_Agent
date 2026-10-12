# AI Data Analyst Chatbot

A conversational data analyst. You ask a question in plain language;
it answers using your documents, your datasets and your database —
and it shows its working.

The governing rule is that **an LLM never does arithmetic**. It decides
*which* operation to run. Pandas or SQL runs it. The model then
explains the result. Every number in every answer was computed by
deterministic code, which is why the same question always gets the
same answer.

Two front doors share one engine: a command-line REPL and a FastAPI
service. Adding a client did not add a second implementation.

---

## Quick start

```bash
# Python 3.13
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt                     # macOS/Linux

# Configure
cp .env.example .env      # then edit it — see Configuration below

# Create the analytical database (needed for SQL tools)
venv/Scripts/python.exe scripts/create_sales_database.py

# Run
venv/Scripts/python.exe main.py                                # CLI
venv/Scripts/python.exe -m api.app                             # API on :8000
```

Verify the install:

```bash
venv/Scripts/python.exe -m pytest -q        # 367 passed
```

---

## Configuration

Everything is environment-driven, loaded from `.env`, which is
git-ignored and must stay that way.

### LLM provider

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` or `ollama` |
| `GROQ_API_KEY` | — | Required when `LLM_PROVIDER=groq` |

Both providers sit behind `LLMGateway`, so the rest of the system
never knows which one is running. The CLI asks; the API reads
configuration at startup.

The model names are constants in `llm/groq_provider.py`
(`GROQ_MODEL`) and `llm/ollama_provider.py` (`OLLAMA_MODEL`), not
environment variables. Edit the module or extend the settings to
change them.

### API

The service **refuses to start without `API_KEY`**. That is
deliberate — every endpoint requires one, so defaulting to "no key
required" would ship an open service that can read every dataset
and delete every session.

| Variable | Default |
|---|---|
| `API_KEY` | none — **required** |
| `API_KEY_HEADER` | `X-API-Key` |
| `API_ALLOWED_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` |
| `API_DATASET_PATH` | `data/sample_sales.xlsx` |
| `API_ANALYTICS_DB_PATH` | `data/sales.db` |
| `API_CHAT_DB_URL` | `sqlite:///chat_history.db` |
| `API_DOCUMENTS_DIR` | `documents` |
| `API_DATASET_UPLOAD_DIR` | `data/uploads` |
| `API_REPORTS_DIR` | `reports` |

### Hardening

| Variable | Default | Purpose |
|---|---|---|
| `API_MAX_DATASET_UPLOAD_BYTES` | `10485760` | Upload size ceiling |
| `API_MAX_DOCUMENT_UPLOAD_BYTES` | `10485760` | Upload size ceiling |
| `API_ANALYSIS_TIMEOUT_SECONDS` | `120` | Wall-clock bound per analysis |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose tracing |

---

## Architecture

```
  CLI (main.py)          API (api/app.py)
       │                      │
       │   FastAPI key auth   │
       └──────────┬───────────┘
                  │
           Orchestrator  ── intent.classify_question() → SourcePlan
                  │
        ┌─────────┴─────────┐
        │                   │
  RAG retrieval      Deterministic analysis
  retriever.py       agent.py: plan → execute → synthesise
        │                   │
  Chroma ← Ollama      tool_registry (19 tools)
  embeddings          ├─ 15 dataframe tools (Pandas)
                      └─ 4 read-only SQL tools
                  │
        AnalysisResponse (Pydantic)
```

Two invariants shape this:

**The LLM plans, Python computes.** The planner emits a JSON step
list naming a tool and its arguments. Each tool has a Pydantic input
model. Results feed back for interpretation. There is no `eval`, no
`exec`, and no arithmetic in a prompt.

**The orchestrator owns no provider.** `LLMGateway` is injected. That
is what makes routing testable without an API key, and it is why the
CLI and the API cannot drift apart.

### Why these tools

19 registered tools, split by data source so dispatch is explicit:

- **Dataframe (15)** — `inspect_dataset`, `filter_dataset`,
  `get_unique_values`, `aggregate_dataset`, `calculate_statistics`,
  `group_by_column`, `sort_dataset`, `calculate_monthly_revenue`,
  `calculate_missing_percentage`, plus six chart tools
- **SQL (4)** — `inspect_database`, `list_tables`,
  `describe_table`, `execute_read_only_sql`

SQL tools are **hidden from the planner** when no database is
configured, so the model can never select a tool that would fail at
execution time.

---

## API

All routes except `/health` require `X-API-Key`. `/health` is
deliberately unauthenticated: a probe needs to know the service is
up, and it exposes only booleans.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness, provider, what is loaded |
| `GET` | `/sessions` | List conversations |
| `POST` | `/sessions` | Create a conversation |
| `GET` | `/sessions/{id}` | Full turn history |
| `DELETE` | `/sessions/{id}` | Delete a conversation |
| `POST` | `/chat` | Ask inside a conversation (persists) |
| `POST` | `/analyse` | Ask statelessly or in a session |
| `GET` | `/datasets` | Registered datasets |
| `POST` | `/datasets` | Upload `.csv` / `.xlsx` / `.xls` |
| `GET` | `/documents` | Indexed documents |
| `POST` | `/documents` | Upload `.txt` / `.pdf` / `.docx` |
| `GET` | `/reports/{id}` | Fetch a generated report |

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Which region earned the most?"}'
```

### Uploads are bounded

Both upload endpoints enforce a **size limit** and an **extension
limit** before a byte reaches disk:

- Filenames are reduced to a bare basename, so `../../.env` becomes
  `.env` and then fails the extension check
- The body is copied in 64 KB chunks with a running total, and the
  partial file is deleted the moment the limit is passed
- Oversized → `413`. Wrong type → `400`. Missing key → `401`

An extension is a client *claim*, not proof, so this bounds the
blast radius of a bad request; it does not make bad input good. The
loaders still have to survive a malformed file inside the limit.

### Timeouts

Analysis runs under a wall-clock bound (default 120s) and returns
`504` on expiry, so a caller can distinguish "too slow" from
"broken" (`500`).

Worth knowing: the bound stops the *caller* waiting, but a thread
that has already started cannot be cancelled — the abandoned thread
runs to completion. That is acceptable here because the work is
short and idempotent. It would not be acceptable for arbitrary code
execution.

---

## Logging

JSON lines on stderr, one event per line, so output is greppable and
machine-readable rather than prose.

```json
{"timestamp":"2026-10-05T14:59:26+0200","level":"INFO","logger":"ai_data_analyst.api.request","message":"request_completed","request_id":"logged-1","event":"request_completed","method":"GET","path":"/health","status_code":200,"duration_ms":1}
```

Every line for one request carries the same `request_id`. Send your
own `X-Request-ID` and it is honoured, so a trace started upstream
can be followed here — it is sanitised and length-bounded first,
because it is attacker-controlled and written verbatim to the log.

**The LLM answer is never logged.** The question and the tools that
ran are enough to debug; the answer may carry figures derived from
your data. `answer`, `api_key`, `authorization` and friends are
redacted at the formatter, not left to call sites.

Filterable events: `request_completed`, `request_failed`,
`analysis_completed`, `analysis_failed`, `analysis_timeout`,
`upload_accepted`, `upload_rejected`.

---

## Security posture

| Control | Where |
|---|---|
| API key, constant-time compare | `api/app.py` |
| Refuses to start without a key | `api/settings.py` |
| SQL read-only by validation | `data_analysis/sql_tools.py` |
| No `eval` / `exec` anywhere | project-wide rule |
| Pydantic validation on every tool input | `tool_models.py`, `sql_models.py` |
| Upload size + type limits | `api/uploads.py` |
| Filename traversal neutralised | `api/uploads.py` |
| Analysis timeout | `api/timeouts.py` |
| Secrets redacted from logs | `api/logging_config.py` |
| `.env`, databases, indexes ignored | `.gitignore` |

Not yet implemented: rate limiting, and a documented data-retention
policy.

---

## Project layout

```
main.py                  CLI loop, session selection
config.py                env-driven settings
api/
  app.py                 FastAPI app, routes, middleware
  registry.py            dataset / document / report stores
  schemas.py             17 Pydantic request+response models
  settings.py            resolved configuration
  uploads.py             size and type limits
  timeouts.py            wall-clock bound
  logging_config.py      JSON logging, correlation ids
orchestrator/
  orchestrator.py        routing, evidence merging, validation
  intent.py              question → SourcePlan
  llm_gateway.py         provider-agnostic LLM access
memory/
  sqlite_store.py        ConversationStore ABC + SQLite
data_analysis/
  agent.py               plan → execute → synthesise
  tool_registry.py       19 tools, split by data source
  analyzer.py            deterministic Pandas operations
  sql_tools.py           read-only SQL + validation
  charts.py              matplotlib
rag/
  document_loader.py     txt / pdf / docx
  text_splitter.py  embeddings.py  vector_store.py  retriever.py
llm/                     groq_provider.py, ollama_provider.py, router.py
models/response_models.py   AnalysisResponse — the response contract
scripts/                 database creation, document generation
tests/                   367 tests
docs/architecture.html   generated architecture diagram
```

### On the roadmap but unused

`llm/router.py`, `data_analysis/profiler.py` and
`data_analysis/reporting.py` are library code exercised by tests.
Nothing on the request path imports them. They are kept because the
profiler and the reporting layers are roadmap deliverables and are
genuinely useful, not because the orchestrator needs them.

---

## Regenerating the strategy document

`documents/word/FY2026_Sales_Strategy.docx` is generated from
`data/sales.db`, not written by hand:

```bash
venv/Scripts/python.exe scripts/generate_strategy_document.py
```

Every figure in it is computed from the sales table. A test asserts
the document still matches the data, so **if you change the
database, regenerate in the same commit** — otherwise the test fails
rather than letting the RAG corpus serve a stale strategy.

---

## Testing

```bash
venv/Scripts/python.exe -m pytest -q                     # all
venv/Scripts/python.exe -m pytest tests/test_v10_hardening.py -q
```

367 tests, no network required. The provider is injected as a stub,
which is why routing and the API can be tested without an API key.

If you are testing a provider for real, note that
`langchain-community` now emits a sunset deprecation warning. It
still works; plan a migration to standalone integration packages.

---

## Known limitations

- SQL is SQLite-only. The `SQLAlchemy` layer would take another
  engine, but nothing beyond SQLite has been tested.
- `resolve_analysis_type` prefers visualisation over database, so a
  request that produces a chart is always typed `visualisation`.
- The timeout cannot cancel in-flight work, only stop waiting for
  it (see above).
- No rate limiting, so the API is not safe to expose publicly as-is.
