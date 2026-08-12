# CRPv6 Hosting, Gateway, and Live Backend Guide

This guide explains where the **visual console**, **Gateway hosting layer**, and **live backend credentials** fit into a CRPv6 deployment. It is written for operators who want to move from a local `pip install crprotocol` to a hosted or SaaS-shaped deployment.

---

## 1. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER / BROWSER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐  │
│  │ CRP Console  │  │ Your App     │  │ AG-UI-compatible frontend        │  │
│  │ (optional)   │  │ (your code)  │  │ (CopilotKit, LangGraph, etc.)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────────┘  │
└─────────┼─────────────────┼─────────────────────────┼──────────────────────┘
          │                 │                         │
          │   HTTP / SSE    │   OpenAI-compatible     │   SSE / WebSocket
          │   /crp/console  │   /v1/chat/completions  │   /v1/chat/stream
          ▼                 ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CRP GATEWAY SERVICE                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Console      │  │ Capability   │  │ Provider     │  │ Key Vault    │   │
│  │ routes       │  │ Router       │  │ Router       │  │              │   │
│  │ (serves UI)  │  │ (tool loop)  │  │ (LLM calls)  │  │ (API keys)   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ HTTP / local function calls
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CRP AGENT RUNTIME                                    │
│  crp.Agent  →  Tool Capability Fabric  →  Capability Executor  →  TEL        │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ reads / writes
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OPTIONAL BACKENDS                                    │
│  SQLite   Redis   S3   File audit   HTTP audit   Telemetry (OTel)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

Three layers:

1. **Frontend / console layer** — renders the agent stream to a user.
2. **Gateway layer** — exposes an OpenAI-compatible API, hosts the console, and routes to LLM providers.
3. **Runtime + backend layer** — the CRP Agent SDK, storage, audit, and telemetry.

---

## 2. What is the CDN / Gateway hosting layer?

### 2.1 Embedded mode (today)

`crp/frontend/console.py` ships a self-contained HTML page. You mount it on any FastAPI app:

```python
from fastapi import FastAPI
from crp.frontend.console import mount_fastapi

app = FastAPI()
mount_fastapi(app, path="/crp/console")
```

The page talks to a stream endpoint (default `/v1/chat/stream`) and a chat endpoint (default `/v1/chat/completions`).

**Pros:** zero build step, works offline/air-gapped.  
**Cons:** not linted/minified, not CDN-cacheable, hard to theme.

### 2.2 CDN mode (recommended for SaaS)

Extract the HTML/JS/CSS into a buildable frontend package (`frontend/agent-console/`), bundle it with Vite, and upload the `dist/` folder to an object-store + CDN:

- **Object store:** AWS S3, Cloudflare R2, or any S3-compatible bucket.
- **CDN:** CloudFront, Cloudflare, or Fastly in front of the bucket.
- **Versioning:** upload each release to a versioned prefix, e.g. `s3://crp-cdn/crp-console/v6.0.0/`.

The Python backend then serves a tiny shim that loads the CDN bundle:

```python
@app.get("/crp/console")
def console():
    cdn = os.environ["CRP_CONSOLE_CDN_URL"]  # e.g. https://cdn.example.com/crp-console/v6.0.0
    return HTMLResponse(f"""
    <!doctype html>
    <html>
      <head><script>window.CRP_STREAM_URL="/v1/chat/stream";</script></head>
      <body><script src="{cdn}/index.js"></script></body>
    </html>
    """)
```

**Pros:** cacheable globally, versioned, small Docker image, CI-auditable dependencies.  
**Cons:** requires a build pipeline and a CDN account.

### 2.3 Gateway-hosted mode (multi-tenant)

In this mode the CRP Gateway is a standalone service that:

1. Accepts OpenAI-compatible `/v1/chat/completions` requests from tenants.
2. Runs the CRP positioned tool loop via `CapabilityRouter`.
3. Streams AG-UI + CRP governance events over SSE.
4. Serves `/crp/console` for any tenant, injecting that tenant's stream URL.

Each tenant supplies:

- An API key (stored in the Gateway key vault).
- A provider key or allowance (OpenAI, Anthropic, local LLM, etc.).
- Optional tool implementations registered with the Gateway.

The Gateway is the **hosting layer** because it is the first internet-facing service that combines the console, the API, and the provider routing in one place.

---

## 3. Where do live backend credentials come in?

CRPv6 itself is **stateless by default**. It keeps sessions in memory and writes audit events to memory. For production you wire in backends via the `infrastructure` section of `crp.config.yaml`.

### 3.1 Backend matrix

| Backend | What it stores | Why you might want it | Required credentials |
|---|---|---|---|
| **SQLite** | Session state, facts, CSO snapshots | Single-node persistence, zero network | None |
| **Redis** | Session state, SSE replay buffers, transient locks | Multi-replica / multi-user deployments, fast resumability | `redis://host:port` URL |
| **S3 / R2** | Session archives, audit logs, model cache | Long-term durable storage, cheap cold tier | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |
| **File audit sink** | Append-only JSONL audit trail | Local/air-gapped compliance logging | None |
| **HTTP audit sink** | Forward audit events to a SIEM / log aggregator | Centralised observability | Endpoint URL + optional API key |
| **Telemetry endpoint** | OpenTelemetry traces and metrics | Operator dashboards, cost tracking | OTLP endpoint + optional auth |

### 3.2 Where the credentials live

CRP never reads credentials from source code. They come from:

1. **Environment variables** (recommended for containers):

   ```bash
   export REDIS_URL=redis://localhost:6379/0
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_REGION=us-east-1
   export CRP_AUDIT_API_KEY=...
   export OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.example.com
   ```

2. **A secrets manager** (recommended for production):

   - AWS Secrets Manager, HashiCorp Vault, 1Password, Doppler, etc.
   - Inject them into the process at startup; CRP reads them as env vars or via `pydantic-settings`.

3. **Local `.env` file** (development only):

   ```text
   # .env
   REDIS_URL=redis://localhost:6379/0
   AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY_ID>
   AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_ACCESS_KEY>
   AWS_REGION=us-east-1
   ```

### 3.3 Can users specify the backends?

Yes. The `infrastructure` section of `crp.config.yaml` is user-facing:

```yaml
infrastructure:
  audit_sink: file           # none | memory | file | http
  audit_path: ./crp_audit.jsonl
  storage_backend: sqlite    # memory | sqlite | redis | s3
  storage_path: ./crp_state.db
  redis_url: ""
  s3_bucket: ""
  s3_prefix: crp/
  database_url: ""
  model_cache_dir: ./crp_models
  model_device: auto
  telemetry_endpoint: ""
```

Users can also override via code:

```python
from crp.config import CRPConfig
from crp.infrastructure import apply_config

cfg = CRPConfig.load("crp.config.yaml")
cfg.set("infrastructure.storage_backend", "redis")
cfg.set("infrastructure.redis_url", os.environ["REDIS_URL"])
infra = apply_config(cfg)
```

### 3.4 Per-backend details

#### SQLite

- **What:** local file-based SQL store for the `crp.state.backends.sqlite.SQLiteBackend`.
- **When:** single-container or desktop deployments; CI tests.
- **Credentials:** none.
- **Path config:** `infrastructure.storage_path`.

#### Redis

- **What:** in-memory cache/state store used for:
  - Session objects when `storage_backend=redis`.
  - SSE event replay buffers.
  - Distributed locks if multiple Gateway replicas run.
- **When:** multi-replica Gateway, resumable sessions, high-throughput deployments.
- **Credentials:** `redis_url` (can include auth: `redis://user:pass@host:port/0`).
- **Cloud options:** AWS ElastiCache, Redis Cloud, Upstash, self-hosted Redis.

#### S3 / R2

- **What:** durable object storage used for:
  - Long-term session archives.
  - Audit log cold storage.
  - CDN asset hosting for the console bundle.
- **When:** you need durable, replicated, cheap storage and can tolerate higher latency than Redis.
- **Credentials:** standard AWS env vars or IAM role. For R2, use S3-compatible keys and endpoint override (currently you must set the endpoint in the backend code or via `AWS_ENDPOINT_URL_S3`).
- **Config:** `s3_bucket`, `s3_prefix`.

#### HTTP audit sink

- **What:** fire-and-forget POST of each audit event to an external endpoint.
- **When:** shipping audit logs to a SIEM, compliance platform, or your own evidence collector.
- **Credentials:** usually an API key in an `Authorization` header. The current `_HttpAuditSink` does not inject a key; extend it to read `CRP_AUDIT_API_KEY` if needed.
- **Config:** `audit_endpoint`.

#### Telemetry endpoint

- **What:** OpenTelemetry OTLP endpoint for traces and metrics.
- **When:** you want operator dashboards (latency waterfalls, cost accounting, quality trends).
- **Credentials:** OTLP headers or API keys via standard OTel env vars.
- **Config:** `telemetry_endpoint`.

---

## 4. Recommended deployment topologies

### 4.1 Local / air-gapped

```yaml
infrastructure:
  audit_sink: file
  storage_backend: sqlite
  model_device: cpu
```

No credentials. Models cache to disk. Console served embedded.

### 4.2 Self-hosted server

```yaml
infrastructure:
  audit_sink: file
  storage_backend: redis
  redis_url: ${REDIS_URL}
  model_device: auto
```

Run Redis on the same host or a managed Redis. Serves the embedded console or a CDN shim.

### 4.3 SaaS / multi-tenant Gateway

```yaml
infrastructure:
  audit_sink: http
  audit_endpoint: ${CRP_AUDIT_ENDPOINT}
  storage_backend: redis
  redis_url: ${REDIS_URL}
  s3_bucket: ${CRP_SESSION_BUCKET}
  s3_prefix: sessions/
  telemetry_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
```

- Gateway replicated behind a load balancer.
- Redis for hot session state and SSE replay.
- S3 for long-term session archives.
- CDN for the console bundle.
- Clerk/Auth0 for user auth and stream isolation.

---

## 5. CI / local reproduction

To make live backends reproducible without real credentials, add a `docker-compose.ci.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3
      - DEFAULT_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY_ID>
      - AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_ACCESS_KEY>
```

Run tests with:

```bash
export CRP_GLINER_DISABLED=1
export REDIS_URL=redis://localhost:6379/0
export AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY_ID>
export AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_ACCESS_KEY>
export AWS_REGION=us-east-1
pytest tests/ -q --tb=short
```

Mark live-backend tests optional so the suite still passes when Redis/LocalStack are not running:

```python
import os
import pytest

@pytest.mark.skipif(os.environ.get("REDIS_URL") == "", reason="Redis not configured")
def test_redis_backend():
    ...
```

---

## 6. Security checklist for hosted deployments

- [ ] SSE endpoints require authenticated sessions (no anonymous stream access).
- [ ] Stream IDs are scoped to the owning user/tenant.
- [ ] Provider API keys live in the Gateway key vault, never in browser or agent config.
- [ ] Console bundle is served with CSP and does not `eval` agent-produced content.
- [ ] Tool output is escaped / rendered as declarative A2UI nodes, never raw HTML.
- [ ] Audit sinks use TLS.
- [ ] S3 buckets are private; pre-signed URLs are short-lived if used.
- [ ] Redis is password-protected and network-isolated in production.

---

## 7. What is built vs. what is still a wiring task

| Piece | Built in CRPv6 | Still to wire |
|---|---|---|
| Agent SDK runtime | ✅ | — |
| Gateway capability router | ✅ | — |
| AG-UI transparency stream | ✅ | — |
| Self-contained console HTML | ✅ | — |
| CDN build pipeline | ❌ | Vite package + CI publish step |
| Gateway console routes | ❌ | `crp/gateway/console_routes.py` |
| SQLite backend | ✅ | — |
| Redis backend | ✅ | credentials + CI service |
| S3 backend | ✅ | credentials + bucket |
| HTTP audit sink | ✅ | endpoint + API key injection |
| Telemetry wiring | partial | OTel exporter integration |
| Multi-tenant key vault | partial | provider-key isolation per tenant |

---

## 8. Summary

- **The CDN/Gateway hosting layer** is the internet-facing surface that serves the console and the OpenAI-compatible API. You can start with embedded mode and graduate to CDN + Gateway-hosted mode.
- **Live backend credentials** come from environment variables or a secrets manager; CRP reads them through the `infrastructure` section of `crp.config.yaml`.
- **Users can absolutely specify backends** — SQLite, Redis, S3, file/HTTP audit, and telemetry endpoint are all configurable without code changes.
- **For immediate distribution**, ship with SQLite + file audit + embedded console + optional Redis. That gives a working, air-gap-friendly, self-hosted CRPv6 package today.
