# Safety Policy

`CRP-Safety-Policy` is a request/response header that turns AI safety from a
wish-list into a **declarative, enforceable contract**. It tells CRP exactly
what to do when the Decision Provenance Engine flags a response - and CRP does
it at the protocol layer, so application code cannot accidentally bypass it.

!!! info "Value proposition"
    Instead of writing bespoke safety logic in every service, you write one
    policy string. Every LLM call that flows through CRP is evaluated against it.

## Example policy

```http
CRP-Safety-Policy: halt-on CRITICAL;
                   redact-on HIGH PII;
                   warn-on MEDIUM;
                   require-grounding 0.75;
                   classify-eu-ai-act MANDATORY;
                   audit-mode CHAIN
```

Think of it as `Content-Security-Policy` for AI responses.

## Directives

| Directive | Values | Effect |
|-----------|--------|--------|
| `halt-on` | `CRITICAL`, `HIGH`, `MEDIUM` | Stop the call and return HTTP 451 / error response |
| `redact-on` | `HIGH PII`, `MEDIUM PII` | Strip detected personal data before delivery |
| `warn-on` | `MEDIUM`, `LOW` | Emit warning but deliver the response |
| `require-grounding` | `0.0`–`1.0` | Halt if grounding score is below threshold |
| `classify-eu-ai-act` | `MANDATORY`, `OPTIONAL` | Run Art. 6 risk classification |
| `audit-mode` | `CHAIN`, `SIMPLE`, `OFF` | Emit HMAC-chained or simple audit events |
| `checkpoint-on` | `HIGH`, `CRITICAL` | Route to human approval |

## SDK usage

```python
import crp

client = crp.SDKClient(safety_profile="strict")
# Equivalent to a policy that halts on CRITICAL, requires grounding, etc.

r = client.complete("Summarise the contract.")
print(r.crp.risk)
print(r.crp.compliant)
```

## Why it matters

| Without policy header | With `CRP-Safety-Policy` |
|-----------------------|--------------------------|
| Safety logic scattered across services | One policy string governs all calls |
| Developers can skip checks | Enforcement happens at the transport/Gateway layer |
| Incident response is reactive | Policy violations are logged and auditable by design |
| Compliance is manual | Policy itself becomes evidence |

[:octicons-arrow-right-24: Full reference](../safety/safety-policy.md)
[:octicons-arrow-right-24: SPEC-006](../spec/CRP-SPEC-006-safety-policy.md)
