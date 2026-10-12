# Web client

The Angular front end. One screen: ask a question, read the answer, see which
tools produced it.

```
Browser (4200)  ──proxy──>  ApiGateway (5000)  ──key──>  FastAPI (8000)
   no API key                   holds the key           computes the answer
```

The browser never holds the API key. That is the entire reason the gateway
exists, and it is why every call in `api.service.ts` targets a **relative**
`/api` path. An absolute `http://127.0.0.1:8000` would bypass the gateway,
break CORS, and put the secret in the JS bundle. Three tests in
`api.service.spec.ts` exist purely to fail if that ever changes.

## Running

The stack needs all three processes. One command starts the back end:

```bash
# from the repository root
venv/Scripts/python.exe scripts/run_services.py
```

Add the client in a second terminal:

```bash
cd web
npm install
npm start
```

Then open http://localhost:4200.

Individually, if you prefer:

```bash
npx ng serve --port 4200                            # this client
dotnet run --project api-dotnet                     # gateway, :5000
venv/Scripts/python.exe -m uvicorn "api.app:get_app" --factory --port 8000
```

## Design

Minimal on purpose. Three places carry the application:

| File | Role |
|---|---|
| `api.service.ts` | The only place that knows the gateway exists |
| `app.ts` | State, as signals |
| `app.html` / `app.css` | One screen, no component library |

No UI framework, no state library, no router. The interface is a single page
with a fixed layout, so a design system would cost more in configuration than
it saves.

**Signals, not observables.** Each piece of state is readable at its point of
use with no subscription to track.

**Nothing is computed here.** Every number rendered was produced by the Python
tools and is only being displayed. This layer formats and nothing else, which
is what keeps the figures identical whichever client asks.

## What it shows

- Engine status: provider, version, and whether the dataset, database and
  document index loaded
- Conversation list, with switch and delete
- Registered datasets with row and column counts
- Per answer: the analysis type, a confidence percentage, the **tools that
  ran**, and collapsible calculations, findings and sources

Showing the tool names is the point. An LLM can produce a confident wrong
number; listing `execute_read_only_sql` next to the SQL that ran is what makes
the claim checkable.

## Uploads

Sent as `FormData` with the filename intact, because the filename is what the
analysis service checks against its allow-list. The 10 MB cap and the
`.csv .xlsx .xls` / `.txt .pdf .docx` restrictions are enforced server-side in
`api/uploads.py` — the browser's `accept` attribute is a convenience, not a
control. A rejection is surfaced verbatim, so the message names the rule that
was broken.

## Error handling

Three failures are distinguished because each needs different words:

| Condition | Shown as |
|---|---|
| Gateway unreachable | "Cannot reach the gateway on port 5000. Is the stack running?" |
| Analysis timed out | "The analysis took too long and was stopped." |
| Engine rejected it | The engine's own `detail`, verbatim |

The gateway deliberately passes upstream error bodies through unchanged, so
the explanation that reaches the user is the one the analysis engine wrote.

## Configuration

| What | Where |
|---|---|
| Gateway address | `proxy.conf.json`, `/api` → `http://127.0.0.1:5000` |
| Allowed origins | `appsettings.json` in `api-dotnet`, `Cors:AllowedOrigins` |

In production, serve `dist/web` behind the gateway and the relative `/api`
paths keep working with no rebuild — the proxy only exists for development.

## Tests

```bash
npm test          # 13 tests
npm run build     # production bundle
```

The security tests are the ones worth keeping green: they assert no
`X-API-Key` header is ever sent, that the key never appears in a query string,
and that every URL is relative.
