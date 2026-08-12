# CRP Gateway Backend — v4 Spec Integration Guide

This document bridges the portable backend modules added to `crp_shared` with the
Gateway and Comply FastAPI applications. The modules themselves are tested and
ready; the steps below show how to wire them into the live services.

## What was added to `crp_shared`

| Module | Purpose | Key spec |
|--------|---------|----------|
| `crp_shared.audit` | Postgres-backed, append-only audit trail with per-session HMAC chains, window HMACs, export (NDJSON/OCSF), and signed Comply streaming. | SPEC-011 |
| `crp_shared.session_token` | HMAC-SHA256 signed session tokens with the full v4 payload (`v`, `sid`, `win`, `qh`, `sb`, `ct`, `cid`, `dag`, `str`, `pol`, `ckf`, `scope`, `iat`, `exp`, `nonce`). | SPEC-007 |
| `crp_shared.crp_headers` | Builder for the standard 40+ CRP response headers across Context, Safety, Provenance, Compliance, Agent, and Memory namespaces. | SPEC-002 |
| `crp_shared.schema` | Idempotent Postgres schema for Gateway audit tables and state tables (`gateway_sessions`, `gateway_windows`, `gateway_documents`, `gateway_pipelines`). | — |

## Wiring into `crp-gateway/main.py`

### 1. Environment variables

Add these to the Gateway `.env` / Railway variables:

```bash
# Stable 32+ byte secret. Generate once and store in Railway.
GATEWAY_MASTER_KEY=<base64-or-hex-secret>

# Comply real-time audit streaming (optional but required for continuous compliance)
COMPLY_WEBHOOK_URL=https://comply.crprotocol.io/api/v1/webhooks/audit-stream
COMPLY_WEBHOOK_API_KEY=<random-secret-shared-with-comply>
```

### 2. Lifespan changes

```python
import os
import httpx
from contextlib import asynccontextmanager

from crp_shared import (
    ensure_gateway_schema,
    init_db,
    close_db,
    get_db,
)
from crp_shared.audit import AuditTrail
from crp_shared.session_token import SessionTokenManager

_audit_trail: AuditTrail | None = None
_session_token_manager: SessionTokenManager | None = None


def get_audit_trail() -> AuditTrail:
    if _audit_trail is None:
        raise RuntimeError("AuditTrail not initialised")
    return _audit_trail


def get_session_token_manager() -> SessionTokenManager:
    if _session_token_manager is None:
        raise RuntimeError("SessionTokenManager not initialised")
    return _session_token_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    pool = get_db()  # or keep a direct reference from init_db()
    await ensure_gateway_schema(pool)

    master_key = os.environ.get("GATEWAY_MASTER_KEY", "").encode()
    if not master_key:
        # Fallback for local dev only. In production require a real secret.
        master_key = b"local-dev-key-do-not-use-in-production-32"

    http_client = httpx.AsyncClient(timeout=30.0)

    global _audit_trail, _session_token_manager
    _session_token_manager = SessionTokenManager(
        gateway_master_key=master_key,
        default_ttl_seconds=3600,
    )
    _audit_trail = AuditTrail(
        pool=pool,
        gateway_master_key=master_key,
        comply_webhook_url=os.environ.get("COMPLY_WEBHOOK_URL"),
        comply_api_key=os.environ.get("COMPLY_WEBHOOK_API_KEY"),
        http_post=http_client.post,
    )

    yield

    await http_client.aclose()
    await close_db()


app = FastAPI(lifespan=lifespan)
```

### 3. Audit endpoints

Add to the existing router:

```python
from fastapi import Depends, HTTPException
from crp_shared import AuditTrail, get_audit_trail, ChainIntegrity


@app.get("/crp/v4/audit/{session_id}")
async def list_audit_events(
    session_id: str,
    limit: int = 1000,
    offset: int = 0,
    trail: AuditTrail = Depends(get_audit_trail),
):
    return {
        "session_id": session_id,
        "events": [
            {
                "event_type": e.event_type.value,
                "severity": e.severity.value,
                "window_id": e.window_id,
                "index": e.event_index,
                "timestamp": e.timestamp,
                "data": e.data,
                "hmac": e.event_hmac,
            }
            for e in await trail.get_events(session_id, limit, offset)
        ],
    }


@app.post("/crp/v4/verify-chain")
async def verify_chain(
    body: dict,
    trail: AuditTrail = Depends(get_audit_trail),
):
    session_id = body.get("session_id")
    from_index = body.get("from_index", 0)
    integrity, broken_at = await trail.verify_chain(session_id, from_index)
    return {
        "session_id": session_id,
        "integrity": integrity.value,
        "broken_at": broken_at,
    }


@app.get("/crp/v4/audit/{session_id}/export.ndjson")
async def export_audit_ndjson(
    session_id: str,
    include_debug: bool = False,
    trail: AuditTrail = Depends(get_audit_trail),
):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        await trail.export_ndjson(session_id, include_debug),
        media_type="application/x-ndjson",
    )
```

### 4. Emitting audit events from inference routes

Inside `chat/completions` or the `GatewayRequestLifecycle` wrapper, after a
window is produced:

```python
trail = get_audit_trail()
await trail.record_event(
    AuditEvent(
        event_type=EventType.DISPATCH_COMPLETED,
        severity=EventSeverity.INFO,
        session_id=session_id,
        window_id=window_id,
        data={
            "model": model,
            "provider": provider,
            "latency_ms": latency_ms,
            "tokens_used": tokens_used,
        },
    ),
    tenant_id=tenant_id,
)
```

For safety-critical outcomes use `EventType.SAFETY_HALT` or `EventType.FABRICATION_DETECTED`.

### 5. Signed session tokens

Replace the current base64 session token with:

```python
manager = get_session_token_manager()
token = manager.issue(
    session_id=session_id,
    window_id=window_id,
    quality_hash=SessionTokenManager.hash_context(prompt + context),
    soft_budget=soft_budget_used,
    continuation_count=continuation_count,
    conversation_id=conversation_id,
    dag_node_id=dag_node_id,
    strategy=strategy,
    policy_id=policy_id,
    ckf_etag=ckf_etag,
    scope=encode_scope("chat"),
)
```

Verify on continuation:

```python
decoded = manager.verify(token)
```

### 6. Response headers

Build the CRP header set and merge into the response:

```python
from crp_shared import HeaderContext, build_crp_headers

headers = build_crp_headers(
    HeaderContext(
        session_id=session_id,
        window_id=window_id,
        chain_tip_hmac=chain_tip,
        window_hmac=window_hmac,
        risk_score=dpe_report.risk_score,
        risk_level=dpe_report.risk_level,
        fabrication_score=dpe_report.fabrication_score,
        ...,
    )
)
return JSONResponse(response_body, headers=headers)
```

## Wiring into `crp-comply`

### 1. Webhook receiver

Add a new route in Comply:

```python
import hmac
import hashlib

@app.post("/api/v1/webhooks/audit-stream")
async def receive_audit_stream(request: Request):
    body = await request.body()
    signature = request.headers.get("X-CRP-Signature", "")
    # Validate signature against COMPLY_WEBHOOK_API_KEY
    # Persist events to Comply evidence tables
    return {"received": True}
```

### 2. Chain-tip verification

When displaying a session’s audit trail, Comply should call:

```python
requests.post(
    "https://gateway.crprotocol.io/crp/v4/verify-chain",
    json={"session_id": session_id},
)
```

and store the integrity result with the evidence bundle.

## Migration notes

- The new tables are created idempotently by `ensure_gateway_schema()`. Run it
  once at startup; it is safe on every deploy.
- Existing in-memory stores (`_sessions`, `_documents`, `_pipelines`,
  `_audit_chains`) can be migrated incrementally. Start by routing audit events
  through `AuditTrail`; state persistence can follow.
- Set `GATEWAY_MASTER_KEY` in production before the first deploy. Rotating the
  key invalidates previously issued session tokens and audit HMACs; plan a
  migration window if you need historical verification across rotations.
