# The Safety Policy Directive Language

`CRP-Safety-Policy` is an HTTP header that lets the caller (or a gateway, or
a WAF) declare what the protocol should do when the DPE flags a response.

It is to AI safety what `Content-Security-Policy` is to web XSS: a wire-level,
declarative, transport-layer enforcement mechanism. Full normative grammar is
in [SPEC-006](../spec/CRP-SPEC-006-safety-policy.md).

## Examples

```
CRP-Safety-Policy: halt-on CRITICAL; redact-on HIGH PII; warn-on MEDIUM
```

```
CRP-Safety-Policy: classify-eu-ai-act MANDATORY;
                   audit-mode CHAIN;
                   max-hallucination-risk 0.30
```

```
CRP-Safety-Policy: default-src self;
                   allow-claim-source envelope, ckf;
                   block-claim-source model-knowledge
```

## Why Declarative Beats Code

Every line of application code that *forgets* to call a safety routine becomes
a hole. A policy header is enforced by the protocol layer for every call,
regardless of whether the application code remembered. The pattern is exactly
the one CSP solved for browsers a decade ago.

## Directive Categories

| Category | Directives | Purpose |
|----------|------------|---------|
| Action | `halt-on`, `redact-on`, `warn-on`, `dispatch-on` | What to do when a severity threshold trips |
| Source | `allow-claim-source`, `block-claim-source` | Which knowledge sources are admissible |
| Classification | `classify-eu-ai-act`, `classify-nist-rmf` | Mandatory regulatory tagging |
| Audit | `audit-mode`, `audit-export-to` | How the verdict is recorded and where |
| Limits | `max-hallucination-risk`, `min-quality-tier`, `max-windows` | Numeric guard-rails |

## Enforcement Verdicts

When the DPE evaluation completes, the gateway returns one of:

- `200 OK` - policy passed, response delivered.
- `200 OK` with `CRP-Safety-Verdict: WARN` - delivered with a warning header.
- `200 OK` with redacted body and `CRP-Safety-Verdict: REDACTED` - sensitive content stripped.
- `451 Unavailable For Legal Reasons` with `CRP-Safety-Verdict: HALT` - response withheld; reason in `CRP-Safety-Reason`.
- `409 Conflict` with `CRP-Safety-Verdict: REDISPATCH` - the caller is asked to re-dispatch with adjusted envelope.

`451` was chosen deliberately to make policy halts unambiguous and machine-readable
across CDNs, WAFs, and observability tools.

## See also

- [SPEC-006](../spec/CRP-SPEC-006-safety-policy.md) - full normative grammar (ABNF).
- [SPEC-005](../spec/CRP-SPEC-005-dpe.md) - how verdicts are produced.
- [SPEC-014](../spec/CRP-SPEC-014-conformance.md) - interoperability tests for policy enforcement.
