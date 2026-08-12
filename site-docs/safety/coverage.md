# Coverage and Limits

A blunt, line-by-line summary of what CRP™ covers - and what it does not.
Use this page as the canonical answer when a sceptic, regulator, or board
member asks "what does this protocol actually guarantee?"

## What CRP Covers (verifiable, today)

| Concern | Mechanism | Spec |
|---------|-----------|------|
| Unbounded output length | Window DAG continuation | [SPEC-004](../spec/CRP-SPEC-004-continuation.md) |
| Truncation mid-task | Wall detection + re-extraction + repack | SPEC-004, [SPEC-005](../spec/CRP-SPEC-005-dpe.md) |
| Cross-window repetition | n-gram + semantic overlap (DPE Stage 7) | SPEC-005 |
| Cross-window contradiction | DPE Stage 6 | SPEC-005 |
| Hallucination risk on every call | DPE Stages 3–5, 10 | SPEC-005 |
| Distorted numbers / dates / names | DPE Stage 4 | SPEC-005 |
| Coherent prose across windows | DPE Stage 9 + stitching | SPEC-005 |
| Transport-layer policy enforcement | `CRP-Safety-Policy` | [SPEC-006](../spec/CRP-SPEC-006-safety-policy.md) |
| Per-call, per-session HMAC chain | Audit Trail | [SPEC-011](../spec/CRP-SPEC-011-audit-trail.md) |
| Regulator-grade evidence (EU AI Act, ISO 42001, GDPR, NIST AI RMF) | Header-emitted, machine-verifiable | [SPEC-010](../spec/CRP-SPEC-010-regulatory-mapping.md) |
| Multi-agent risk-budget accumulation | Chain budget + circuit breaker | [SPEC-012](../spec/CRP-SPEC-012-multi-agent-safety.md) |
| Conformance and interop testing | Standard test suite | [SPEC-014](../spec/CRP-SPEC-014-conformance.md) |
| Operating without a CKF | Zero-CKF safety-only mode | [SPEC-017](../spec/CRP-SPEC-017-zero-ckf-mode.md) |

## What CRP Does NOT Cover

| Concern | Why CRP can't address it | Where it is addressed |
|---------|--------------------------|-----------------------|
| Model alignment / values | Cannot inspect model weights | Alignment research (Anthropic, DeepMind, etc.) |
| Training data bias | The training corpus is out of band | Dataset audits, red-teaming |
| Constitutional / RLHF behaviour | Internal to the model | Model providers |
| Emergent capability risks | Cannot predict novel behaviours | AI Safety institutes (US AISI, UK AISI) |
| Adversarial prompt robustness | Beyond protocol scope | Red-team programmes, model-side defences |
| Insider threat at the model vendor | Trust boundary is the API | Vendor risk management |
| Whether the LLM is sentient | Not an engineering question | Philosophy and cognitive science |

## A Note on "Defense in Depth"

CRP is one layer in a defence-in-depth architecture:

```
[ Application policy ]
        │
[ CRP gateway: Safety Policy + DPE + audit ]  ← CRP lives here
        │
[ Model provider safety filters ]
        │
[ Model weights and alignment ]
```

Removing any layer weakens the system. CRP is the layer that has been
under-served by the industry until now.
