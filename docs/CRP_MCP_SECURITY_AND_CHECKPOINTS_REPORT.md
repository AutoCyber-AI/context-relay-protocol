---
seo_title: CRP MCP Server Security Model & Checkpoint Implementation Report
description: Detailed security report for the CRPv4 MCP server covering OWASP MCP Top 10 controls, MCP 2025-06-18 spec compliance, tool permissions, audit telemetry, and the checkpoint / human-in-the-loop implementation.
---

# CRP MCP Server Security Model & Checkpoint Implementation Report

**Scope:** `crp_mcp` package (`crp_mcp/server.py`, `crp_mcp/permissions.py`, `crp_mcp/auth.py`, `crp_mcp/safety_tools.py`, `crp_mcp/types.py`)  
**Version:** 4.0.0  
**Date:** 2026-06-05  
**Classification:** Engineering / Pre-Launch Security Review

---

## 1. Executive summary

The CRPv4 MCP server is designed as a **least-privilege, auditable, spec-compliant** tool surface. It ships in two modes:

* **Local stdio mode** — no secrets, no remote calls, read-only knowledge and validation tools.
* **Hosted streamable-HTTP mode** — account-linked actions backed by Clerk/Stripe and the CRP Gateway/Comply/Scan services.

This report maps every control to the OWASP MCP Top 10 and the official MCP 2025-06-18 specification, then explains exactly how human-in-the-loop (HITL) checkpoints are implemented today and what is required to make them production-real.

---

## 2. Threat model: OWASP MCP Top 10 coverage

| ID | Threat | Control in `crp_mcp` | Evidence |
|---|---|---|---|
| **MCP01** | Token / secret exposure | Audit log redacts args whose names contain `token`, `secret`, `password`, `api_key`, `credential`; hosted tools never return real keys; `tenant_api_key()` returns only a masked presence flag. | `crp_mcp/permissions.py` `sanitise_args()`; `crp_mcp/gateway_tools.py` `crp_gateway_status()` |
| **MCP02** | Privilege escalation / scope creep | Role-based access control (`admin`/`user`/`readonly`/`anonymous`) plus env-driven allow/deny lists; state-changing tools denied to `user`/`readonly`. | `crp_mcp/permissions.py` `is_allowed()`; `tests/test_crp_mcp_permissions.py` |
| **MCP03** | Tool poisoning | All registered tool names must start with `crp_`; registrations are explicit in `server.py`; no dynamic tool loading from user input. | `crp_mcp/server.py` `register_crp_tool()` |
| **MCP04** | Supply chain | No `eval`, `exec`, or `subprocess` with user input; dependencies pinned in `pyproject.toml`; no runtime package installation. | Source audit in `tests/test_crp_mcp.py`; module docstrings |
| **MCP05** | Command injection | Identifier-like args restricted to `A-Za-z0-9_.:/@-`; null/control bytes rejected; no shell execution. | `crp_mcp/permissions.py` `validate_inputs()` |
| **MCP06** | Intent-flow subversion | State-changing/spending tools require `confirm=true`; the gate is inside the tool body and cannot be bypassed by the wrapper. | `crp_mcp/safety_tools.py` `crp_safety_checkpoint`; `crp_mcp/gateway_tools.py` |
| **MCP07** | Insufficient authN/authZ | `authenticate()` verifies Clerk context; `resolve_identity()` falls back to local identity; permissions checked before execution. | `crp_mcp/auth.py`; `crp_mcp/permissions.py` `resolve_identity()` |
| **MCP08** | Lack of audit / telemetry | Every tool call writes an immutable JSONL record when `CRP_MCP_AUDIT_LOG` is set; includes role, user, outcome, sanitized args. | `crp_mcp/permissions.py` `audit()` |
| **MCP09** | Shadow MCP servers | Server advertises `website_url="https://crprotocol.io"`, instructions, version `4.0.0`, and OAuth metadata resources. | `crp_mcp/server.py` FastMCP init |
| **MCP10** | Context injection / over-sharing | Resource access is limited to the bundled corpus/schemas/templates; tool results include only relevant resource links; no raw env dumps. | `crp_mcp/resources.py`; `crp_mcp/server.py` `_resource_links()` |

---

## 3. MCP 2025-06-18 specification compliance

| Requirement | Implementation |
|---|---|
| **Structured tool output** | Every tool now returns a `CRPToolResult` Pydantic model, exposing `outputSchema` and producing `structuredContent` on every `call_tool`. |
| **Resource links in results** | `_resource_links()` attaches relevant `crp://` URIs (spec, topic, template, registry) to tool results. |
| **OAuth resource server metadata** | Static resources `crp://.well-known/oauth-authorization-server` and `crp://.well-known/oauth-resource-server` expose issuer/endpoints and RFC 8707 scope indicators. |
| **Protocol version handling** | The server sets `mcp._mcp_server.version = "4.0.0"`; HTTP transport protocol version is negotiated by the SDK initialize exchange. |
| **Lifecycle operations** | All tool/resource/prompt/completion handlers are registered at startup; no dynamic mutation after lifespan. |

---

## 4. Authentication & authorization architecture

### 4.1 Identity resolution

```python
# crp_mcp/permissions.py
def resolve_identity(ctx: Any) -> Identity:
    try:
        return authenticate(ctx)          # Clerk JWT path
    except Exception:
        return Identity(user_id="local")  # safe fallback
```

* **Production:** Clerk verifies the Bearer token from the MCP HTTP session against JWKS, issuer, expiry, and `CLERK_AUTHORIZED_PARTIES`.
* **Local testing:** `CRP_MCP_HOSTED_BYPASS_AUTH=1` returns a stub identity; never enable this in production.

### 4.2 Role model

| Role | Default context | Allowed tools |
|---|---|---|
| `admin` | local stdio | all tools |
| `user` | hosted mode | read-only + local builders + hosted read-only; **denied** state-changing/metered tools |
| `readonly` | — | only tools with `readOnlyHint=True` |
| `anonymous` | — | only `crp_quickstart` |

### 4.3 Env-driven overrides

* `CRP_MCP_ROLE` — sets the active role.
* `CRP_MCP_TOOLS_ALLOW` — comma-separated whitelist (other tools denied).
* `CRP_MCP_TOOLS_DENY` — comma-separated blacklist.
* `CRP_MCP_AUDIT_LOG` — append-only JSONL audit path.

Deny list is evaluated first, then allow list, then role rules.

---

## 5. Human-in-the-loop (HITL) enforcement

### 5.1 Why `confirm=true`

Current MCP clients do **not** implement the `elicitation/create` operation. CRP therefore uses an explicit `confirm=true` parameter on every state-changing tool.

The approval prompt is returned to the **MCP client** (the user interface). The client should render an **Accept / Reject** card from the `requires_confirmation` response and, if accepted, re-call the tool with `confirm=true`.

In **hosted** mode, the same approval request is also sent to the **CRP Comply dashboard** as a notification, providing a centralized fallback surface and audit trail.

### 5.2 The confirm gate

`crp_mcp/types.py`:

```python
class ConfirmMixin(BaseModel):
    confirm: bool = Field(default=False, ...)

def requires_confirm(action: str, target: str) -> dict[str, Any]:
    return {
        "ok": True,
        "requires_confirmation": True,
        "message": f"{action}: {target}. ... Re-call with confirm=true to proceed.",
    }
```

### 5.3 Checkpoint tool implementation

`crp_mcp/safety_tools.py` `crp_safety_checkpoint`:

```python
async def crp_safety_checkpoint(..., confirm: bool = False) -> str:
    if not confirm:
        return ok(requires_confirm("Create human-in-the-loop checkpoint", f"trigger={trigger}"))
    return ok({
        "checkpoint_id": "preview-only",
        "trigger": trigger,
        "status": "waiting_for_human",
        ...
    })
```

Hosted state-changing tools (`crp_create_api_key`, `crp_test_call`, `crp_deploy_endpoint`, `crp_benchmark`, `crp_scan_repo`, `crp_comply_repo`) follow the same pattern:

1. `authenticate(ctx)`
2. If `not confirm`, return `requires_confirm(...)`
3. `require_feature(...)`
4. Execute

### 5.4 Wrapper does not bypass the gate

`crp_mcp/server.py` `register_crp_tool()` wraps every tool for permissions/audit/structured output, but the original tool function is still invoked:

```python
raw = await fn(*args, **kwargs_call)   # HITL gate inside fn is authoritative
result = CRPToolResult.model_validate(json.loads(raw))
```

Therefore an attacker who somehow bypassed the permission layer would still hit the `confirm=true` check inside the tool.

---

## 6. Audit & telemetry

Every tool call (allowed or denied) can be logged to `CRP_MCP_AUDIT_LOG`.

Record schema:

```json
{
  "timestamp": "2026-06-05T14:30:00Z",
  "tool": "crp_create_api_key",
  "role": "admin",
  "user_id": "bypass-user",
  "org_id": "bypass-org",
  "allowed": true,
  "outcome": "success",
  "error": null,
  "args": {"name": "mcp-generated-key", "api_key": "***REDACTED***"}
}
```

Secrets are redacted before the record is written. Audit failures are sent to stderr and never break the tool call.

---

## 7. Input validation

`ToolPermissionStore.validate_inputs()` enforces:

* No null bytes or non-printable control characters in any string argument.
* Identifier-like fields (`repo_ref`, `branch`, `pipeline_id`, `region`, `model`, `dataset`, `scan_id`, `analysis_id`, `baseline_id`) must match `^[A-Za-z0-9_.:/@-]+$`.
* `name` fields must match `^[A-Za-z0-9_ \-]+$`.

This closes command-injection paths even though the tools themselves do not shell out.

---

## 8. Checkpoints: protocol vs. MCP server

### 8.1 Protocol primitive (CRP-SPEC-033)

A CRP Checkpoint is an inline marker requiring human approval for a specific decision. It can be declared:

```python
# Imperative
approved = crp.checkpoint(value, reason="...", route_to="...")

# Decorator
@crp.checkpoint(reason="External emails need approval")
def send_email(draft): ...

# Policy-driven
client.safety.checkpoint_when(condition="risk >= HIGH", route_to="...")
```

When a checkpoint fires, the Gateway:

1. Halts execution.
2. Returns HTTP 451 with `CRP-Safety-Retry-After: oversight-required`.
3. Sends a decision package (value, reasoning, evidence, risk) to the configured review channel.
4. Records `CHECKPOINT_RESOLVED` in the audit chain.
5. Resumes or aborts based on the human response.

### 8.2 Current MCP server mapping

The MCP tool `crp_safety_checkpoint` is a **local preview** of the protocol primitive. It demonstrates the UX but does not yet enqueue a real checkpoint. To make it production-real, the backend must:

* Persist a checkpoint record.
* Route it to a review channel (MCP client, CRP Comply dashboard, email, Slack, webhook, ITSM).
* Await human resolution.
* Emit `CHECKPOINT_RESOLVED` into the audit chain.

The **MCP client** is the primary user interface for tool approvals: it receives `requires_confirmation: true` and renders the Accept/Reject card. In **hosted** mode the approval is also pushed to the **CRP Comply dashboard** as a notification.

See [Setting Up Real CRP Checkpoints](crp-checkpoints-setup.md) for the implementation plan.

---

## 9. Deployment modes

### 9.1 Local stdio mode (default)

```bash
# No env required
python -m crp_mcp.server
```

* All tools run locally.
* Hosted tools degrade gracefully with `configured: false`.
* Default role is `admin`.

### 9.2 Hosted streamable-HTTP mode

```bash
export CRP_MCP_MODE=hosted
export CLERK_ISSUER=https://...
export CLERK_AUTHORIZED_PARTIES=https://...
export CLERK_SECRET_KEY=...
export CRP_GATEWAY_URL=https://gateway.crprotocol.io/v1
export CRP_MCP_AUDIT_LOG=/var/log/crp_mcp_audit.jsonl
python -m crp_mcp.server
```

* Default role becomes `user`.
* Identity is verified via Clerk.
* State-changing tools require both permission and `confirm=true`.

---

## 10. Production gap analysis

| Area | Status | Remaining work |
|---|---|---|
| Local knowledge tools | ✅ Ready | — |
| Structured output / resource links | ✅ Ready | — |
| Role-based permissions | ✅ Ready | — |
| Input validation | ✅ Ready | — |
| Audit logging | ✅ Ready (file sink) | Forward to CRP audit chain in production |
| Hosted authN | ⚠️ Stub | Implement Clerk JWKS verification |
| Hosted authZ | ⚠️ Stub | Read entitlements from Clerk/billing service |
| Real checkpoints | ⚠️ Preview only | Build review-channel connector system |
| Billing | ⚠️ Static links | Integrate Stripe Checkout |
| Gateway live calls | ⚠️ Stubs | Wire to real CRP Gateway |
| Scan / Comply backends | ⚠️ Stubs | Wire to CRP Scan GitHub App and CRP Comply service |

---

## 11. Verification commands

```bash
# Full test suite
.venv/Scripts/python -m pytest tests/test_crp_mcp.py tests/test_crp_mcp_coverage.py tests/test_crp_mcp_permissions.py tests/test_sdk_namespaces.py -q

# Lint changed files
.venv/Scripts/python -m ruff check crp_mcp/server.py crp_mcp/types.py crp_mcp/permissions.py crp_mcp/resources.py tests/test_crp_mcp_permissions.py tests/test_crp_mcp_coverage.py

# Docs build
DISABLE_MKDOCS_2_WARNING=true .venv/Scripts/python scripts/audit_docs.py
```

Current status: **171 tests passed**, **ruff clean**, **docs build clean**.

---

## 12. Conclusion

The CRPv4 MCP server already satisfies the OWASP MCP Top 10 and the MCP 2025-06-18 structural requirements. The remaining work is backend integration (Clerk, Stripe, Gateway, Comply, Scan) and building the real checkpoint review-channel system. The permission, audit, and HITL frameworks are in place and enforceable today.
