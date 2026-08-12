# The Black-Box Question

> **"If LLMs are black boxes, how can CRP make any guarantees about what they produce?"**

This is the most important sceptical question, and it deserves a direct
answer. Black-box governance is not only possible - it is the *only* honest
form of governance for any system whose internals are opaque.

---

## The Short Answer

CRP makes no claims about what happens inside the model. It governs what
goes in and what is done with what comes out.

```
[What CRP controls]                    [The black box]

 ┌─────────────────┐                   ┌──────────────┐
 │ Context Envelope│ ── structured ──► │              │
 │ (what goes in)  │     input         │   LLM Model  │
 └─────────────────┘                   │  (CRP cannot │
                                       │   see inside)│
 ┌─────────────────┐                   │              │
 │ DPE Analysis    │ ◄── raw text ──── │              │
 │ (what comes out)│     output        └──────────────┘
 └─────────────────┘
```

The LLM is given a precisely constructed Context Envelope (the input layer).
What it produces is then subjected to 13 stages of analysis - claim
detection, attribution, fabrication, distortion, entailment, contradiction,
repetition, completeness, flow, hallucination risk, quality tiering, policy
evaluation, provenance binding. Based on those analyses, CRP decides whether
to deliver, flag, halt, or re-dispatch the response.

---

## Analogies That Dissolve the Objection

This is not fundamentally different from how every other form of governance works:

| Governance system | Inside the black box | What is governed |
|-------------------|----------------------|------------------|
| Financial audit | What was in the accountant's mind | Whether the numbers are consistent and traceable |
| Breathalyser | Liver chemistry | What is present in the output |
| HTTP security headers | What is in the database | What gets delivered |
| TLS | The content being encrypted | Confidentiality, integrity, authenticity of transit |
| Drug test | Body chemistry | Whether specific substances are detectable |
| CRP | Model weights and internal representations | The observable outputs of every inference |

In each case, the inability to see inside is acknowledged, and governance
proceeds on the observable surface. The result is real, measurable, and
verifiable - not theatre.

---

## The Two Claims, Untangled

The sceptical "LLM atheist" position usually conflates two different statements:

1. **"You cannot fully understand what an LLM will do in all situations."** - TRUE.
2. **"You cannot verify, govern, and record what it actually did in specific calls."** - FALSE. CRP disproves this.

The first is an alignment research problem. The second is a protocol
engineering problem, and it has a solution.

---

## What CRP Therefore Provides

- **Verifiable** - every assertion the protocol makes about a response is
  expressed in headers that are cryptographically chained to the audit trail.
- **Measurable** - the DPE produces numerical scores (hallucination risk,
  flow score, completeness ratio), not vibes.
- **Enforceable** - Safety Policy directives stop bad responses *before*
  they reach the application.
- **Regulatable** - the evidence emitted satisfies EU AI Act Article 12 / 13
  logging requirements, ISO 42001 control evidence, GDPR Article 22 traceability.

The black box is real. Its observable surface is also real. CRP is the
governance layer for that surface.

---

## Further Reading

- [The CRP safety case](index.md)
- [The DPE pipeline](dpe.md)
- [Coverage and limits](coverage.md)
- [SPEC-005 - DPE normative specification](../spec/CRP-SPEC-005-dpe.md)
