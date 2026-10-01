# AGENTS.md — AI Data Analyst Chatbot

## Project
Python CLI data analyst. An LLM (Groq or Ollama) decides *what* to do; deterministic
Python/Pandas/SQL do the actual work. Built against
`documents/pdf/AI_Data_Analyst_Chatbot_Roadmap.pdf` — that document is the
authority on scope. Read it before planning anything non-trivial.

## Layout
```
main.py                    CLI loop, session selection, orchestration entry
config.py                  env-driven settings (LLM_PROVIDER etc.)
llm/                       router.py, groq_provider.py, ollama_provider.py
models/response_models.py  AnalysisResponse — the single structured output contract
rag/                       loader → splitter → embeddings → vector_store → retriever
data_analysis/             loader, profiler, tools, tool_models, tool_registry,
                           analyzer, agent, charts, reporting, sql_*
tests/                     pytest, one file per version milestone
documents/                 RAG source material (pdf/, word/, text/)
data/                      sample datasets + sales.db
outputs/charts/            generated PNGs
```

## Commands
Run everything through the project venv — it is Python 3.13 and has the deps:
```bash
venv/Scripts/python.exe -m pytest -q          # 140 tests
venv/Scripts/python.exe main.py               # run the CLI
```

## Rules that must hold
1. **Architectural changes need authorisation.** Before changing module boundaries,
   the provider interface, the tool dispatch model, or the response contract,
   explain the change and its architectural impact and ask first. This is the
   user's explicit standing instruction.
2. **Never let the LLM do arithmetic.** It formulates an operation; Pandas or SQL
   executes it. Tool results feed back for interpretation.
3. **Tools stay narrow.** Each tool has one purpose, a Pydantic input model in
   `data_analysis/tool_models.py` (or `sql_models.py`), and a predictable return
   shape. No unrestricted `eval`/`exec`.
4. **SQL stays read-only.** No INSERT/UPDATE/DELETE/DROP/ALTER.
5. **Secrets never enter Git.** `.env`, `chat_history.db`, `chroma_db/`, `venv/`,
   `__pycache__/` are ignored — keep them that way.
6. **One commit per working milestone**, named for the version it closes
   (e.g. `V7: close gate - <what landed>`).
7. **Green tests before committing.** Never commit a broken suite.
8. **Wrap-sensitive assertions are a trap.** Prompts are built with
   `textwrap.dedent`, so tests asserting a literal sentence break when wrapping
   shifts. Assert on normalised text or a distinctive fragment.

## Current state
At V7 complete (`0648c69`). V8 — integration behind one orchestrator — not started.
`orchestrator/` and `agents/` were deleted in `85c7ebc` as dead code; routing
currently lives in `main.py`. There is no `README.md`.

## Gotchas
- `orchestrator/` and `agents/` still exist as empty directories with stale
  `__pycache__`. Nothing imports them.
- Chart output lives in `outputs/charts/`, not `outputs/`.
- `main.py` is 553 lines and still holds provider selection, session management
  and dispatch. That is the main thing V8 should untangle.
