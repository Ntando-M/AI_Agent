# API Gateway

The ASP.NET Core layer between the Angular browser client and the
Python analysis service.

## Why it exists

The Python API requires an `X-API-Key` on every route. If Angular called
FastAPI directly, that key would have to ship inside the browser bundle, where
every user could read it. This process holds the key server-side, attaches it
to every upstream request, and never returns it.

That is the entire responsibility. There is no analysis logic here. Every route
forwards to the same FastAPI endpoints the Python test suite exercises, so the
CLI, the API and the browser all reach one engine.

```
Angular (4200)  ->  ApiGateway (5000)  ->  FastAPI (8000)  ->  Orchestrator
                        holds the key      validates it        does the work
```

## Running

Both services must be running.

```bash
# 1. Python analysis service
venv/Scripts/python.exe -m api.app

# 2. This gateway
dotnet run --project api-dotnet
```

Then open http://localhost:5000/swagger to see the proxied surface.

## Configuration

`appsettings.json` holds non-secret defaults. The key comes from user secrets or
the environment, never from a committed file:

```bash
cd api-dotnet
dotnet user-secrets init
dotnet user-secrets set "PythonService:ApiKey" "<the same value as API_KEY in the Python .env>"
```

The gateway **refuses to start** without that key. Failing fast matters here: a
gateway running without one forwards unauthenticated requests that FastAPI then
rejects, which looks like a Python outage rather than a missing setting.

| Setting | Default | Purpose |
|---|---|---|
| `PythonService:BaseUrl` | `http://127.0.0.1:8000` | FastAPI address |
| `PythonService:ApiKey` | *(empty)* | Shared secret. Required. |
| `PythonService:ApiKeyHeader` | `X-API-Key` | Header name |
| `PythonService:TimeoutSeconds` | `300` | Per-request timeout |
| `Cors:AllowedOrigins` | `["http://localhost:4200"]` | Angular dev server |

## Endpoints

All under `/api`, mirroring FastAPI exactly:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Engine status |
| GET | `/api/sessions` | List conversations |
| POST | `/api/sessions` | Create a conversation |
| GET | `/api/sessions/{id}` | Read a conversation |
| DELETE | `/api/sessions/{id}` | Delete a conversation |
| POST | `/api/chat` | Ask inside a conversation |
| POST | `/api/analyse` | Ask statelessly |
| GET | `/api/datasets` | List datasets |
| POST | `/api/datasets` | Upload a dataset |
| GET | `/api/documents` | List documents |
| POST | `/api/documents` | Upload a document |
| GET | `/api/reports/{id}` | Fetch a report |

## Design notes

**Uploads stream through.** `POST /api/datasets` and `/api/documents` forward
the request body as a `StreamContent` with the original content type, so
multipart boundaries and file bytes survive the hop. Re-buffering an upload
would mean this process holds a whole dataset in memory for no reason.

**Responses pass through.** The upstream status code and JSON body are returned
as-is. A 404 from FastAPI stays a 404 with FastAPI's own `detail` message, so a
client sees what the analysis engine actually said rather than a generic gateway
error.

**Timeout is 300 seconds.** A legitimate analysis turn runs a planner call,
deterministic tools, and a synthesis call. The Python side owns its own budget;
the gateway must not cut a real analysis short.

**CORS is not a wildcard.** This service can read datasets and delete sessions,
so only Angular's dev server is allowed. A wildcard origin would let any site
open in the user's browser drive the engine.
