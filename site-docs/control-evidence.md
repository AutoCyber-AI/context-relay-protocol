---
seo_title: "AI Security & Safety Control Evidence — EU AI Act, AIUC-1, ISO 42001, NIST"
description: "CRP produces signed, tamper-evident control evidence for every major AI assurance framework: EU AI Act, AIUC-1, ISO/IEC 42001, NIST AI RMF, and SOC 2-for-AI."
tags:
  - control-evidence
  - ai-safety
  - ai-security
  - ai-governance
  - ai-compliance
  - eu-ai-act
  - aiuc-1
  - iso-42001
  - nist-ai-rmf
  - crp
---

# AI Security & Safety Control Evidence

<div class="hero-splash hero-splash--dark" markdown>

![CRP protocol logo](assets/logo-full.png){ .hero-logo width="320" height="320" loading="eager" }

<div class="hero-kicker">🏅 Control Evidence · Agentic Positioning Layer</div>

<h1 class="hero-headline" markdown>
Controls are easy to claim.<br/>CRP proves they operate.
</h1>

<p class="hero-sub">
Every major AI assurance framework — <strong>EU AI Act, AIUC-1, ISO/IEC 42001, NIST AI RMF,
SOC 2-for-AI</strong> — demands the same thing underneath its own vocabulary:
<strong>provable, operating controls — continuous, verifiable evidence</strong>.
CRP emits exactly that on every governed AI call.
</p>

<div class="hero-buttons">
<a href="/getting-started/quickstart/" class="md-button md-button--primary">Prove it free in 60 seconds</a>
<a href="/aiuc-1/" class="md-button">AIUC-1 proof point</a>
</div>

<div class="hero-stats">
<div class="hero-stat"><span class="num">13-stage</span><span class="label">Safety on every call</span></div>
<div class="hero-stat"><span class="num">&lt;50ms</span><span class="label">Overhead</span></div>
<div class="hero-stat"><span class="num">HMAC</span><span class="label">Signed audit chain</span></div>
<div class="hero-stat"><span class="num">5+</span><span class="label">Frameworks supported</span></div>
</div>

</div>

---

## The common demand across every AI standard

| Framework | What it is | What it demands (the common thread) |
|-----------|-----------|-------------------------------------|
| **EU AI Act** | Law (Reg. 2024/1689) | Risk management, logging (Art.12), human oversight (Art.14), QMS (Art.17), technical documentation (Annex IV) — i.e. **evidence the controls operate**. |
| **AIUC-1** | AI agent security/safety/reliability standard | Adversarial testing, real-time input filtering, access control, **audit trails**, continuous monitoring — i.e. **evidence the agent behaves under pressure**. |
| **ISO/IEC 42001:2023** | AI management system standard | Documented controls + operational evidence + continual improvement. |
| **NIST AI RMF** | US risk framework | GOVERN / MAP / MEASURE / MANAGE — measurement & documentation of AI risk controls. |
| **SOC 2 (AI)** | Trust services | Evidence controls operate over a period, not at a point in time. |

**The common requirement: provable, operating controls — continuous, verifiable evidence.** CRP is built to emit exactly that. Different standards, one agentic positioning engine.

---

## The control-evidence mapping

What CRP actually emits, and which standard-demands it satisfies.

| CRP capability (operates on every call) | Evidence it emits | Satisfies (examples) |
|----------------------------------------|-------------------|----------------------|
| **DPE 13-stage safety** ([SPEC-005](spec/CRP-SPEC-005-dpe.md)) | Risk, grounding, fabrication, distortion, contradiction scores — signed | AIUC-1 Security/Safety/Reliability · EU AI Act Art.15 · ISO 42001 performance evaluation |
| **Safety Policy + HTTP 451 halt** ([SPEC-006](spec/CRP-SPEC-006-safety-policy.md), [SPEC-002](spec/CRP-SPEC-002-headers.md)) | Policy-enforced + halt events — signed | AIUC-1 Security/Safety · EU AI Act Art.14 · NIST AI RMF MANAGE |
| **Human-in-the-loop checkpoints** ([SPEC-033](spec/CRP-SPEC-033-safety-control-plane.md), [SPEC-034](spec/CRP-SPEC-034-safety-coverage.md)) | Approval records with who/when — signed | AIUC-1 Safety/Accountability · EU AI Act Art.14 · ISO 42001 operation |
| **HMAC audit chain** ([SPEC-011](spec/CRP-SPEC-011-audit-trail.md)) | Tamper-evident event log | AIUC-1 Accountability · EU AI Act Art.12 · SOC 2 · ISO 42001 records |
| **Identity & provenance headers** ([SPEC-002](spec/CRP-SPEC-002-headers.md)) | AuthZ + provenance per call | AIUC-1 Accountability · EU AI Act Art.13 · GDPR Art.30 |
| **CRP Scan findings** ([SPEC-013](spec/CRP-SPEC-013-github-action.md), [SPEC-036](spec/CRP-SPEC-036-scan-remediation.md)) | Pre-production vulnerability + remediation evidence | AIUC-1 Security · EU AI Act Art.15 cybersecurity |
| **Comply evidence packs** ([SPEC-040](spec/CRP-SPEC-040-crp-comply.md)) | Annex IV, DPIA/FRIA, QMS docs — signed | EU AI Act Annex IV/Art.17 · ISO 42001 · AIUC-1 Accountability/Society |
| **Local-LLM / zero-exfiltration mode** ([SPEC-017](spec/CRP-SPEC-017-zero-ckf-mode.md)) | 0-byte-egress attestation | AIUC-1 Data & Privacy/Security · data-residency requirements · GDPR data minimisation |

**The point:** CRP doesn't just *have* controls — it produces the *evidence each control operated*, mapped to what the standards demand.

---

## Proof points by framework

### EU AI Act

CRP addresses **33 of 35 technical controls** across Articles 6–17 and generates the evidence
regulators expect:

- **Article 9** — Risk management system: DPE scores + quality tiers + continuous monitoring
- **Article 10** — Data governance: context-source manifests, PII detection, embedding consistency
- **Article 12** — Record-keeping: HMAC-chained window events
- **Article 13** — Transparency: provenance export + source attribution
- **Article 14** — Human oversight: checkpoint headers with signed approval records
- **Article 15** — Accuracy/robustness/cybersecurity: fabrication detection, contradiction checks, injection shield
- **Article 16/17** — QMS: recipe-driven evidence packs

[:octicons-arrow-right-24: EU AI Act details](compliance/eu-ai-act.md)

### AIUC-1

CRP produces **80%+ of the control evidence** AIUC-1 auditors verify across all six principles:

- **Data & Privacy** — input-data governance, PII scanning, data-source manifests, zero-exfiltration mode
- **Security** — adversarial robustness, real-time input filtering, unauthorized-action prevention, adversarial-input detection, endpoint protection, deployment hardening
- **Safety** — harmful-output prevention, human-in-the-loop, risk-category monitoring
- **Reliability** — hallucination prevention, consistent behaviour, error handling
- **Accountability** — activity logging, quality management, AI disclosure, acceptable-use policy, accountability assignment
- **Society** — regulatory alignment, continuous assurance, transparent boundary statements

[:octicons-arrow-right-24: Full AIUC-1 mapping](aiuc-1.md)

### ISO/IEC 42001:2023

CRP features map to AI management system clauses 4–10, providing evidence for context,
leadership, planning, support, operations, performance evaluation, and improvement.

[:octicons-arrow-right-24: ISO 42001 alignment](compliance/iso-42001.md)

### NIST AI RMF

CRP supports all four NIST AI RMF functions:

| Function | CRP evidence |
|---|---|
| **GOVERN** | Policy headers, accountability identifiers, human oversight checkpoints |
| **MAP** | System registry, context-source manifests, risk classification |
| **MEASURE** | DPE scores, quality tiers, grounding percentages, contradiction counts |
| **MANAGE** | Safety budgets, circuit breakers, redaction, response actions |

[:octicons-arrow-right-24: NIST AI RMF alignment](compliance/nist-ai-rmf.md)

### SOC 2-for-AI / GDPR

- **SOC 2:** Continuous, HMAC-signed evidence that controls operate over time, not just at a point in time.
- **GDPR:** PII scanning, data-source manifests for Article 30, DPIA-ready risk scores, right-of-erasure support.

---

## Honest boundaries

To maintain credibility:

- CRP produces the **technical control evidence**; it is **not itself an accredited certifier**.
  AIUC-1 certificates are issued by AIUC via accredited auditors; EU AI Act conformity is
  assessed by notified bodies or self-assessment per risk class. CRP makes you
  **audit-ready and certification-ready**.
- AIUC-1 **updates quarterly**. CRP's continuous evidence model is designed to keep pace,
  but the mapping must be versioned against each release.
- Some requirements (e.g. third-party attestation, catastrophic-misuse modules) are provided
  **via accredited partners** rather than by CRP alone.

---

## Get started

<div class="cta-bar" markdown>
<div class="cta-bar__text">
<div class="cta-bar__title">Ready to prove your AI controls operate?</div>
<div class="cta-bar__subtitle">Start free in 60 seconds, or talk to our governance team.</div>
</div>
<div class="cta-bar__actions">
<a href="/getting-started/quickstart/" class="md-button md-button--primary">Start Free</a>
<a href="mailto:ai-governance@crprotocol.io" class="md-button">Contact Team</a>
</div>
</div>

```python title="One line to evidence-backed AI"
import crp

client = crp.SDKClient(safety="strict")
answer = client.ask("Summarise the contract")

print(answer.crp.risk)               # LOW | MEDIUM | HIGH | CRITICAL
print(answer.crp.grounded)           # True | False
print(answer.crp.fabrications)       # unsupported claims
print(answer.crp.chain_valid)        # HMAC chain integrity
print(client.audit.export())         # regulator-ready evidence bundle
```

---

## See also

- [AIUC-1 Aligned Safety & Security](aiuc-1.md)
- [AI Safety Protocol](topics/ai-safety.md)
- [AI Governance Framework](topics/ai-governance.md)
- [AI Compliance](topics/ai-compliance.md)
- [CRP Safety Case](safety/index.md)
- [DPE Pipeline](safety/dpe.md)
- [Products](products/index.md)
- [CRPv5 Improvements](crpv5-roadmap.md)
