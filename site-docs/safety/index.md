---
hide:
  - toc
seo_title: "AI Safety & Governance — The CRP Safety Case"
description: "The CRP safety case: how the Decision Provenance Engine, Safety Policy, and audit chain make LLM outputs safer and accountable."
---

# AI Safety & Governance

<div class="cr-hero" markdown>

## The only thing worse than an unsafe AI call is not knowing it happened

CRP turns every LLM interaction into an **observable, risk-scored, auditable event**.
You do not need to trust the model. You need to trust the signals CRP produces
about the model's output - and those signals are cryptographically signed,
reproducible, and regulator-ready.

</div>

<div class="cr-stats" markdown>
<div class="cr-stat"><span class="num">13</span><span class="label">DPE checks per response</span></div>
<div class="cr-stat"><span class="num">&lt;50ms</span><span class="label">Safety overhead</span></div>
<div class="cr-stat"><span class="num">HMAC</span><span class="label">Signed audit chain</span></div>
<div class="cr-stat"><span class="num">EU AI Act</span><span class="label">Evidence auto-generated</span></div>
</div>

---

## What CRP actually delivers for AI safety

Most AI safety tools give you a score and a prayer. CRP couples every score to a
deterministic action:

| Risk signal | What CRP detects | What CRP does |
|-------------|------------------|---------------|
| **Hallucination / fabrication** | Claims with no source support | Raises risk tier, flags `fabrications`, can halt or redispatch |
| **Grounding failure** | Output not tied to provided context | Sets `grounded=False`, routes to human review if policy says so |
| **Contradiction** | New output conflicts with prior facts | Logs conflict, downgrades quality, surfaces in audit |
| **PII leakage** | Personal data in input or output | Sets `pii_detected=True`, can redact or halt |
| **Prompt injection** | Override, goal-hijack, exfiltration patterns | Sets `injection_detected=True`, halts on strict profiles |
| **Quality collapse** | Output below S/A/B/C/D threshold | Surfaces `quality` tier, triggers redispatch or checkpoint |
| **Regulatory risk** | EU AI Act high-risk patterns without controls | Classifies call, emits compliance evidence automatically |

Every signal is **measurable**, **stored**, and **actionable** - not a dashboard vanity metric.

---

## Before & after: what changes in production

<div class="cr-compare" markdown>
<div class="bad" markdown>

### ❌ Without CRP

- Every LLM call returns raw text.
- No risk score. No provenance. No audit trail.
- Safety code is optional, scattered, and easy to bypass.
- Compliance evidence is written by consultants months later.
- When something goes wrong, you cannot reconstruct what the model was told or why it answered.

</div>
<div class="good" markdown>

### ✅ With CRP

- Every call returns `risk`, `grounded`, `fabrications`, `pii_detected`, `injection_detected`, `compliant`.
- HMAC-signed audit event is emitted in milliseconds.
- Safety policy is enforced at the protocol layer - non-bypassable.
- EU AI Act / ISO 42001 / GDPR evidence is generated from real runtime data.
- Full provenance DAG lets you reconstruct any answer, any time.

</div>
</div>

---

## How it works in 5 lines

```python
import crp

client = crp.SDKClient()
client.configure(safety_profile="strict")

response = client.complete("Summarise the quarterly report.")
print(response.crp.risk)           # LOW | MEDIUM | HIGH | CRITICAL
print(response.crp.grounded)       # True | False
print(response.crp.compliant)      # True | False
print(response.crp.injection_detected)
print(response.crp.pii_detected)

valid, _ = client.audit.verify()   # cryptographic chain integrity
assert valid
```

That is the full safety pipeline: input validation, injection scanning, PII
detection, DPE scoring, safety-policy evaluation, audit emission, and chain
verification - all in one call.

---

## The Decision Provenance Engine (DPE)

DPE is CRP's runtime safety core. It does not ask the model to be honest; it
checks whether the model's output can be traced back to verifiable facts.

1. **Claim detection** - break output into atomic claims.
2. **Attribution analysis** - link each claim to source facts.
3. **Fabrication detection** - flag claims with no source.
4. **Distortion detection** - catch misrepresented sources.
5. **Entailment scoring** - measure source-to-claim support.
6. **Cross-window contradiction** - detect conflicts across continuation windows.
7. **Repetition detection** - prevent loops and echo.
8. **Completeness verification** - check whether the task was fully covered.
9. **Flow analysis** - evaluate logical progression.
10. **Hallucination risk scoring** - combine signals into a single risk tier.
11. **Quality tiering** - assign S/A/B/C/D.
12. **Safety policy evaluation** - apply `halt-on`, `redact-on`, `require-grounding` rules.
13. **Provenance binding** - lock the verdict into the audit chain.

Each stage is deterministic and testable. The full report is available through
`client.audit.events()`.

---

## Safety Policy as code

CRP's safety policy language works like Content-Security-Policy: declarative,
transport-layer enforceable rules.

```text
CRP-Safety-Policy: default-src context; halt-on CRITICAL; require-grounding 0.70;
                   redact-on HIGH PII; checkpoint-on HIGH human-oversight
```

- `halt-on CRITICAL` - returns HTTP 451 and stops the call.
- `redact-on HIGH PII` - strips detected personal data before delivery.
- `require-grounding 0.70` - fails outputs whose grounding score is below 70%.
- `checkpoint-on HIGH` - routes to human approval.

Policies are enforced by the Gateway and by the SDK, so they cannot be skipped
by a misconfigured client.

---

## What CRP does NOT claim to solve

CRP is an infrastructure protocol, not an alignment lab. It does not:

- Inspect model weights or training data.
- Guarantee the model has "good values."
- Predict novel emergent behaviours.

What it *does* solve is the operational safety layer that is achievable today:
**observable outputs, verifiable evidence, enforceable policies**.

---

## The business value

| Cost / risk area | Without CRP | With CRP |
|------------------|-------------|----------|
| Incident investigation | Days of log archaeology | Seconds via session reconstruction |
| Compliance evidence | $50K–$500K consultant engagement | Auto-generated from runtime data |
| PII breach exposure | Unknown until audit | Detected and halted per call |
| Hallucination liability | No systematic detection | Fabrication count on every response |
| Audit readiness | Reactive document scramble | Always-current evidence pack |

---

## Deeper reading

<div class="grid cards" markdown>

-   **[DPE Pipeline](dpe.md)**

    What each of the 13 stages checks and why.

-   **[Safety Policy Language](safety-policy.md)**

    How `CRP-Safety-Policy` directives work.

-   **[Coverage & Limits](coverage.md)**

    Exactly what is and is not in scope.

-   **[Black-Box Question](black-box.md)**

    Why governing an opaque model is not only possible but correct.

-   **[SDK AI Safety Reference](../sdk/ai-safety.md)**

    Map every safety capability to SDK calls.

</div>
