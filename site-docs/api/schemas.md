# JSON Schemas

CRP defines 10 JSON Schema files for protocol data structures. These schemas
are used for validation, documentation, and OpenAPI specification. They describe
payloads used by the current high-level SDK methods and the HTTP sidecar.

## Schema Inventory

| Schema | File | Purpose |
|--------|------|---------|
| [Task Intent](#task-intent) | `task-intent.json` | Task description shape |
| [Quality Report](#quality-report) | `quality-report.json` | Quality assessment shape |
| [Session Handle](#session-handle) | `session-handle.json` | Session creation metadata |
| [Session Status](#session-status) | `session-status.json` | Session runtime metadata |
| [Envelope Preview](#envelope-preview) | `envelope-preview.json` | Envelope planning metadata |
| [Stream Event](#stream-event) | `stream-event.json` | Streaming event shape |
| [Cost Estimate](#cost-estimate) | `cost-estimate.json` | Cost estimation shape |
| [CRP Error](#crp-error) | `crp-error.json` | Error responses |
| [Persisted State Header](#persisted-state-header) | `persisted-state-header.json` | Cold storage metadata |
| [OpenAPI](#openapi) | `openapi.json` | Full sidecar API spec |

All schemas are in the `schemas/` directory at the repository root.

---

## Task Intent

Task description shape used by the orchestrator and sidecar. All fields are
optional:

```json
{
  "description": "Compare React and Vue",
  "system_prompt": "You are a senior frontend architect.",
  "task_input": "Focus on performance, DX, and ecosystem.",
  "expected_output_type": "markdown",
  "max_windows": 5,
  "max_output_tokens": 4096,
  "metadata": {
    "project": "framework-eval",
    "priority": "high"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable task description |
| `system_prompt` | string | System prompt for the LLM |
| `task_input` | string | The actual task/question |
| `expected_output_type` | enum | `text`, `json`, `markdown`, `code` |
| `max_windows` | integer | Maximum continuation windows |
| `max_output_tokens` | integer | Max tokens per window |
| `metadata` | object | Arbitrary key-value pairs (max 50 keys) |

---

## Quality Report

Quality assessment shape exposed on `response.crp` and through
`client.compliance.report()`.

```json
{
  "session_id": "abc-123",
  "window_id": "win-1",
  "output": "The complete generated text...",
  "quality_tier": "A",
  "facts_extracted": 42,
  "security_flags": {
    "injection_markers": [],
    "unicode_normalization": true,
    "control_chars_stripped": false,
    "truncation_detected": false,
    "integrity_violations": []
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | Session identifier |
| `window_id` | string | Window identifier |
| `output` | string | Unmodified LLM output (Axiom 9) |
| `quality_tier` | enum | `S`, `A`, `B`, `C`, `D` |
| `facts_extracted` | integer | Number of facts extracted |
| `security_flags` | object | Security check results |

### Quality Tiers

| Tier | Meaning |
|------|---------|
| S | Exceptional - fully grounded, no hallucinations |
| A | Strong - minor gaps |
| B | Acceptable - some parametric claims |
| C | Marginal - significant gaps |
| D | Poor - mostly ungrounded |

---

## Session Handle

Session creation metadata returned by low-level session initialization.

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "protocol_version": "2.0.0",
  "capabilities": ["dispatch", "ingest", "stream", "tools"],
  "created_at": "2026-04-10T12:00:00Z",
  "expires_at": "2026-04-10T14:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | Unique session identifier |
| `protocol_version` | SemVer | CRP version |
| `capabilities` | array | RBAC-granted capabilities |
| `created_at` | ISO 8601 | Creation timestamp |
| `expires_at` | ISO 8601 | Expiration timestamp |

---

## Session Status

Session runtime metadata, accessible via `s.status()` on a session object.

```json
{
  "session_id": "abc-123",
  "windows_completed": 9,
  "total_input_tokens": 34521,
  "total_output_tokens": 9836,
  "facts_in_warm_state": 372,
  "overhead_ratio": 0.061,
  "remaining_budget": null
}
```

---

## Envelope Preview

Envelope planning metadata used internally when building context windows.

```json
{
  "total_tokens": 3842,
  "envelope_tokens": 2100,
  "facts_included": 15,
  "saturation": 0.994
}
```

---

## Stream Event

Streaming event shape used by internal streaming paths.

```json
{
  "event_type": "token",
  "data": "The "
}
```

| Event Type | Data | When |
|-----------|------|------|
| `token` | String | Each token arrives |
| `extraction` | Progress object | Background extraction |
| `continuation` | Window metadata | New window starts |
| `window_complete` | Window stats | Window finishes |
| `done` | QualityReport | All generation complete |
| `error` | Error details | Something went wrong |

---

## Cost Estimate

Cost estimation shape used by budget and planning components.

```json
{
  "estimated_windows": 5,
  "estimated_input_tokens": 15000,
  "estimated_output_tokens": 10000,
  "estimated_cost_usd": 0.025,
  "confidence": "medium"
}
```

---

## CRP Error

Error response format:

```json
{
  "code": 1001,
  "message": "Token budget exhausted",
  "details": "Session abc-123 exceeded maximum token budget"
}
```

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| 1001 | BudgetExhausted | Token budget exceeded |
| 1002 | RateLimit | Rate limit hit |
| 1003 | SessionExpired | Session timed out |
| 1004 | SessionLimit | Max sessions reached |
| 1005 | SessionClosed | Session already closed |
| 1010 | ValidationError | Invalid input |
| 1011 | SecurityInvariant | Security check failed |
| 1012 | SignatureInvalid | HMAC signature mismatch |
| 1013 | RBACDenied | Permission denied |
| 1020 | ProviderError | LLM provider error |
| 1021 | ProviderTimeout | LLM provider timeout |
| 1030 | StateCorrupted | Internal state corruption |
| 1031 | ChainVerificationFailed | Audit chain integrity failure |

---

## Persisted State Header

Cold storage / export metadata:

```json
{
  "schema_version": "1.0",
  "protocol_version": "2.0.0",
  "created_at": "2026-04-10T12:00:00Z",
  "checksum": "blake3:abc123..."
}
```

Uses BLAKE3 for integrity verification.

---

## OpenAPI

The full OpenAPI 3.1.0 specification for the [HTTP Sidecar](../guides/sidecar.md)
is available at `schemas/openapi.json`. Import it into:

- **Postman** - Import → File → `openapi.json`
- **Swagger UI** - Point to the JSON file
- **Any OpenAPI client generator** - Generate clients for any language
