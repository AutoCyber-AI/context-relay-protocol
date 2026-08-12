# SDK Error Reference

CRP errors are designed to be actionable: they state **what** happened, **why**, and **the one fix**.

---

## Exception hierarchy

```
CRPError
├── ValidationError
├── BudgetExhaustedError
├── ChainVerificationFailedError
├── ProviderError
│   ├── ProviderTimeoutError
│   └── RateLimitExceededError
├── SecurityInvariantError
├── SessionClosedError
├── SessionExpiredError
├── SignatureInvalidError
└── StateCorruptedError
```

!!! note "No SafetyHalt"
    `crp.SafetyHalt` does **not** exist. Use `crp.SecurityInvariantError` for safety-triggered halts.

---

## Common exceptions

### `SecurityInvariantError`

Raised when a safety policy triggers a hard stop.

```python
try:
    r = client.complete("Generate a medical diagnosis")
except crp.SecurityInvariantError as e:
    print(e.code)         # 1011
    print(e.message)      # human-readable cause
    print(e.details)      # evidence dict
```

### `BudgetExhaustedError`

The session safety budget has been depleted.

```python
except crp.BudgetExhaustedError as e:
    print(e.code)          # 1001
    print(e.details)
    # Reset the session or route to human review
```

### `ChainVerificationFailedError`

The HMAC provenance chain is broken, indicating tampering or state corruption.

```python
except crp.ChainVerificationFailedError as e:
    print(e.code)         # 1031
    print(e.details)
    # Do not trust outputs from this session
```

### `ProviderError`

Upstream provider failure (OpenAI, Anthropic, Ollama, etc.).

```python
except crp.ProviderError as e:
    print(e.code)         # 1020
    print(e.details)      # may include provider name / status code
```

### `ValidationError`

Configuration or input validation failed.

```python
except crp.ValidationError as e:
    print(e.code)         # 1010
    print(e.details)
```

---

## Error codes

Many exceptions expose a stable `code` string suitable for programmatic handling.

| Code | Exception | Meaning |
|------|-----------|---------|
| `1011` | `SecurityInvariantError` | Policy halted the response |
| `1001` | `BudgetExhaustedError` | Safety budget depleted |
| `1031` | `ChainVerificationFailedError` | HMAC chain invalid |
| `1021` | `ProviderTimeoutError` | Upstream timeout |
| `1002` | `RateLimitExceededError` | Provider or CRP rate limit |
| `1010` | `ValidationError` | Config or input invalid |
| `1005` | `SessionClosedError` | Session was explicitly closed |
| `1003` | `SessionExpiredError` | Session TTL expired |
| `1012` | `SignatureInvalidError` | Token or webhook signature bad |
| `1030` | `StateCorruptedError` | Storage integrity failure |

---

## Graceful degradation

By default, CRP tries to return a governed response even when something fails:

```python
r = client.complete("...")

if r.finish_reason == "error":
    print("Dispatch failed")
elif r.finish_reason == "halted":
    print(f"Halted: {r.crp.risk}")
else:
    print(r.text)
```

Always inspect `r.crp.risk` even when `finish_reason == "stop"`.
