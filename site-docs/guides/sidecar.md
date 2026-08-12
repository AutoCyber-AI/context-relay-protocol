# HTTP Sidecar

CRP can run as a lightweight REST API server via `python -m crp serve`, enabling
cross-process context sharing without embedding the Python library. This is
useful for polyglot stacks - call CRP from Node.js, Go, Rust, or any language
with HTTP support.

!!! info "Status"
    The sidecar is available in the self-hosted SDK today. Managed SaaS sidecar
    endpoints are on the roadmap.

## Quick start

```bash
# Start the sidecar (loopback only by default)
python -m crp serve

# Or specify host/port
python -m crp serve --port 8900

# With authentication (required for non-loopback)
python -m crp serve --bind-all --auth-token "your-secret-token"
```

## Architecture

```
Your App (any language)
    ↓ HTTP
CRP Sidecar (127.0.0.1:9470)
    ↓ Python
CRP Library → LLM Provider
```

The sidecar uses Python's stdlib `http.server` - no extra dependencies beyond
the CRP package.

## Endpoints

### Session lifecycle

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions` | Create a new session |
| `GET` | `/sessions` | List active sessions (owned only) |
| `GET` | `/sessions/:id/status` | Get session status |
| `POST` | `/sessions/:id/close` | Close and flush session |

### Dispatch

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions/:id/dispatch` | Standard dispatch |
| `POST` | `/sessions/:id/dispatch/tools` | Tool-mediated dispatch |
| `POST` | `/sessions/:id/dispatch/reflexive` | Reflexive dispatch |
| `POST` | `/sessions/:id/dispatch/progressive` | Progressive dispatch |
| `POST` | `/sessions/:id/dispatch/stream-augmented` | Stream-augmented |
| `POST` | `/sessions/:id/dispatch/agentic` | Agentic dispatch |

### Knowledge

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions/:id/ingest` | Ingest external data |
| `GET` | `/sessions/:id/facts` | Query extracted facts |
| `POST` | `/sessions/:id/facts/share` | Share facts between sessions |
| `POST` | `/sessions/:id/facts/feedback` | Boost/penalize/reject facts |
| `GET` | `/sessions/:id/envelope` | Preview current envelope |

### Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/sessions/:id/providers` | Register fallback provider |
| `POST` | `/sessions/:id/estimate` | Estimate session cost |

## Example: Node.js client

```javascript
const response = await fetch('http://127.0.0.1:9470/sessions', { method: 'POST' });
const { session_id } = await response.json();

await fetch(`http://127.0.0.1:9470/sessions/${session_id}/ingest`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'CRP uses CKF for persistent knowledge.' }),
});

const answer = await fetch(`http://127.0.0.1:9470/sessions/${session_id}/dispatch`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    system_prompt: 'You are a helpful assistant.',
    task_input: 'What is CKF?',
  }),
});
console.log(await answer.json());
```

## Security

- Binds to `127.0.0.1` by default.
- `--bind-all` requires `--auth-token` unless you explicitly pass `--allow-unauthenticated`.
- Per-IP rate limiting (default 120 req/60s).
- No HTTPS - deploy behind a TLS reverse proxy for production.

[:octicons-arrow-right-24: CLI Reference](../getting-started/cli.md)
