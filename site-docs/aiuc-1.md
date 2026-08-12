---
seo_title: "AIUC-1 Aligned AI Safety & Security — CRP Protocol"
description: "CRP Protocol is AIUC-1 aligned: the open HTTP-header standard that delivers adversarial-tested AI safety, tamper-evident audit chains, and automated compliance evidence for AI agents."
tags:
  - aiuc-1
  - ai-safety
  - ai-security
  - ai-governance
  - ai-compliance
  - crp
---

# AIUC-1 Aligned AI Safety & Security

<div class="hero-splash hero-splash--dark" markdown>

![CRP protocol logo](assets/logo-full.png){ .hero-logo width="320" height="320" loading="eager" }

<div class="hero-kicker">🏅 AIUC-1 Proof Point · Agentic Positioning Layer</div>

<h1 class="hero-headline" markdown>
AIUC-1 Ready.<br/>Evidence-First.
</h1>

<p class="hero-sub">
<strong>AIUC-1</strong> (<a href="https://aiuc.com">AI Unified Certification</a>) is the world's first
independent standard to certify that AI agents are secure, safe, and reliable — created with 100+
Fortune 500 CISOs. It demands third-party adversarial testing, real-time input filtering, access
controls, audit trails, and compliance documentation across <strong>6 principles and 51
requirements</strong>. <strong>Context Relay Protocol™ produces 80%+ of the signed, tamper-evident
evidence</strong> AIUC-1 auditors verify.
</p>

<div class="hero-buttons">
<a href="/getting-started/quickstart/" class="md-button md-button--primary">Prove it free in 60 seconds</a>
<a href="/control-evidence/" class="md-button">See all control-evidence mappings</a>
</div>

<div class="hero-stats">
<div class="hero-stat"><span class="num">80%+</span><span class="label">AIUC-1 requirements covered</span></div>
<div class="hero-stat"><span class="num">13-stage</span><span class="label">DPE safety pipeline</span></div>
<div class="hero-stat"><span class="num">&lt;50ms</span><span class="label">Safety overhead per call</span></div>
<div class="hero-stat"><span class="num">HMAC</span><span class="label">Signed audit chain</span></div>
</div>

</div>

---

## What is AIUC-1?

**AIUC-1** is the world's first independent standard to certify that AI agents are secure, safe,
and reliable. It was developed by the **Artificial Intelligence Underwriting Company (AIUC)** with
a consortium of **100+ Fortune 500 CISOs and security leaders**. AIUC-1 defines **51 requirements
and 130 controls** across six risk principles:

- **Adversarial robustness** — can the system resist prompt injection, jailbreaks, and data exfiltration?
- **Real-time safety filtering** — are harmful inputs and outputs blocked before they reach users?
- **Access control & scope enforcement** — can the AI take unauthorised actions?
- **Human oversight** — is there a human-in-the-loop for high-risk decisions?
- **Audit & accountability** — can every decision be traced, attributed, and verified?
- **Compliance documentation** — can the system produce the evidence auditors expect?

AIUC-1's six principles are:

1. **Data & Privacy** — confidentiality, integrity, and privacy of data handled by AI agents.
2. **Security** — protection against vulnerabilities, adversarial attacks, and unauthorized access.
3. **Safety** — prevention of unintended and harmful actions, with robust controls and fail-safes.
4. **Reliability** — predictable, consistent agent behaviour, proper error handling and recovery.
5. **Accountability** — clear audit trails, logging, and human oversight for all agent actions.
6. **Society** — alignment with societal norms, ethics, and regulatory requirements.

Certification involves **thousands of adversarial scenarios derived from real-world incidents**,
conducted by accredited auditors. The certificate is valid for **12 months**, with agent behaviour
tested **at least quarterly** to keep pace with evolving AI risks. For enterprises deploying LLMs,
passing AIUC-1 is quickly becoming a procurement and insurance requirement.

!!! info "AIUC-1 is not a management-system certification"
    Unlike ISO 42001, which certifies the AI management system, AIUC-1 certifies the AI agent
itself through adversarial technical testing and control audits. The two certifications are
complementary.

---

## The CRP answer: protocol-layer safety

Most AI safety tools are bolted on **after** the model responds. CRP implements safety at the
**protocol layer** — every LLM call is scored, annotated, and enforced through standard HTTP
headers before the response reaches your application.

<div class="cr-compare" markdown>
<div class="bad" markdown>

### Traditional AI deployment

- Raw LLM output with no risk signal
- Safety checks scattered across application code
- Compliance evidence collected manually before audits
- No tamper-evident record of what happened
- Adversarial testing is a one-time pen-test

</div>
<div class="good" markdown>

### CRP-governed AI deployment

- Every call returns `LOW | MEDIUM | HIGH | CRITICAL` risk
- 13-stage DPE safety pipeline runs in &lt;50 ms
- EU AI Act, ISO 42001, NIST AI RMF evidence generated continuously
- HMAC-signed audit chain proves every event
- Adversarial defense is continuous, not point-in-time

</div>
</div>

---

## AIUC-1 principle coverage

AIUC-1 defines **51 requirements and 130 controls** across six principles. The table below maps
each principle to the CRP capabilities that produce the evidence AIUC-1 auditors verify.

| AIUC-1 principle | What it covers | CRP control evidence |
|------------------|---------------|----------------------|
| **Data & Privacy** | Confidentiality, integrity, privacy of data handled by AI agents | PII scanning, data-source manifests, context-source attestation, GDPR Art. 30 records, right-of-erasure support |
| **Security** | Adversarial attacks, jailbreaks, prompt injection, unauthorized access, endpoint abuse | 13-stage DPE pipeline, injection shield, rate limiting, session binding, HMAC-SHA256 key derivation, CRP Scan pre-production hardening |
| **Safety** | Harmful or unintended outputs, robust fail-safes | Output validation, safety budgets, policy-driven redaction, harmful-output blocking, checkpoint headers |
| **Reliability** | Predictable behaviour, error handling, recovery, hallucination prevention | Claim detection, grounding verification, fabrication/distortion scoring, contradiction detection, automatic continuation, re-grounding |
| **Accountability** | Audit trails, logging, human oversight, clear ownership | Identity headers, HMAC-SHA256 + BLAKE3 audit chain, checkpoint approval records, tamper-evident event export |
| **Society** | Societal norms, ethics, regulatory alignment, misuse prevention | Compliance evidence packs, acceptable-use policy enforcement, continuous adversarial testing, transparent boundary statements |

---

## Principle-by-principle mapping

### Data & Privacy

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Input data governance | Context-source manifests and `ContextManifest` attestation record what data enters the system and from where. |
| Personal data protection | PII scanner detects 7+ categories in inputs and outputs; supports GDPR data-minimization and breach prevention. |
| Data subject rights | Fact-level deletion in CKF supports right-of-erasure; retention policies are configurable and auditable. |

### Security

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Adversarial robustness | The 13-stage DPE pipeline is continuously red-teamed against prompt injection, jailbreaks, goal-hijacking, data exfiltration, and delimiter-forgery attacks. |
| Real-time input filtering | Input validation + injection shield run on every call in &lt;50 ms; attempts surface as `CRP-Safety-Injection-Detected`. |
| Unauthorized-action prevention | Safety Policy headers enforce `halt-on`, `redact-on`, `checkpoint-on`, and `max-chain-budget` rules; tool calls are grounded. |
| Endpoint protection | Gateway rate limiting, session binding, and scope headers (`CRP-System-Id`, `CRP-Operator-Id`) restrict access. |
| Deployment hardening | CRP Scan finds ungoverned LLM calls, hard-coded keys, missing input validation, and bad configurations in CI. |

### Safety

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Harmful-output prevention | Output validation, PII scanning, safety budgets, and policy-driven redaction halt or quarantine harmful outputs. |
| Human-in-the-loop | `CRP-Safety-Checkpoint` headers pause HIGH/CRITICAL responses for approve/reject/edit; decisions are signed and added to the audit chain. |
| Risk monitoring | Every response carries `CRP-Safety-Risk`, `CRP-Safety-Hallucination-Risk`, and quality tier; CRP Visualise aggregates posture live. |

### Reliability

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Hallucination prevention | DPE claim detection, attribution analysis, fabrication/distortion scoring, and provenance binding compare every claim to grounded facts. |
| Consistent behaviour | Automatic continuation, CSO relay, and re-grounding keep long tasks coherent across windows. |
| Error handling | Quality tiers (S/A/B/C/D) honestly report degradation; circuit breakers open when safety budgets are depleted. |

### Accountability

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Identity & ownership | Identity headers (`CRP-Agent-Id`, `CRP-Operator-Id`, `CRP-System-Id`) bind every call to an owner. |
| Tamper-evident logging | Every window extends an HMAC-SHA256 + BLAKE3 audit chain; tampering surfaces as `CRP-Provenance-Chain-Integrity: BROKEN`. |
| AI disclosure | Provenance export, source attribution, and `client.compliance.report()` generate disclosure artefacts from runtime data. |

### Society

| AIUC-1 control area | How CRP produces evidence |
|---------------------|---------------------------|
| Regulatory alignment | Pre-mapped EU AI Act, ISO 42001, NIST AI RMF, and GDPR evidence packs exported from runtime data. |
| Acceptable use | Declarative Safety Policy headers act like CSP for AI: portable, auditable, and enforced at the Gateway. |
| Continuous assurance | Adversarial testing is continuous, not point-in-time; the audit chain captures every control event. |

---

## Product-level AIUC-1 readiness

<div class="product-grid" markdown>
<div class="product-card" markdown>

### 🌐 CRP Gateway
**The AI Safety Firewall**

13-stage DPE safety, unbounded context, automatic continuation, and enforced provenance on every call — all in &lt;50 ms.

- Security — adversarial robustness
- Security — real-time input filtering
- Security — unauthorized-action prevention
- Safety — harmful-output blocking
- Safety — HITL checkpoints
- Reliability — hallucination prevention

[Explore Gateway](products/gateway.md){ .md-button .md-button--primary }

</div>
<div class="product-card" markdown>

### 📋 CRP Comply
**The Compliance Automation Engine**

Recipe-driven governance generates article-cited EU AI Act, ISO 42001, and GDPR evidence from HMAC-signed audit chains.

- Accountability — tamper-evident logging
- Accountability — quality-management evidence
- Society — regulatory compliance packs
- Data & Privacy — input-data governance
- Society — acceptable-use policy templates

[Explore Comply](products/comply.md){ .md-button .md-button--primary }

</div>
<div class="product-card" markdown>

### 🔍 CRP Scan
**The Pre-Production Security Scanner**

Finds ungoverned AI calls, hard-coded keys, missing safety policies, and injection risks in CI — before attackers do.

- Security — pre-deploy adversarial gap detection
- Security — endpoint-scraping prevention
- Security — deployment-environment hardening
- Accountability — logging assurance

[Explore Scan](products/scan.md){ .md-button .md-button--primary }

</div>
<div class="product-card" markdown>

### 📊 CRP Visualise
**The Safety Operations Dashboard**

Real-time risk posture, context flow, provenance chains, and compliance status for auditors and incident responders.

- Security — adversarial-input detection alerts
- Safety — risk-category monitoring
- Accountability — visual audit-trail exploration

[Explore Visualise](products/visualise.md){ .md-button }

</div>
<div class="product-card" markdown>

### 📝 CRP Scribe
**The Audit Documentation Tool**

Auto-documents every safety-policy decision, governance change, and compliance action with full provenance.

- Accountability — ownership documentation
- Society — AI disclosure reports
- Accountability — documented QMS

[Explore Scribe](products/scribe.md){ .md-button }

</div>
</div>

---

## Offensive security: the CRP differentiator

AIUC-1 requires **third-party adversarial testing**. CRP goes further: it treats
adversarial defense as a **continuous operational capability**, not a one-time certification
checkbox.

### CRP Gateway IS the continuous adversarial test

The 13-stage DPE pipeline is continuously tested against prompt injection, jailbreaks, data
exfiltration, and hallucination manipulation. Every update is red-teamed before deployment.
Certification is the floor; continuous defense is the standard.

### CRP Scan finds what attackers find first

Ungoverned LLM calls, hard-coded API keys, missing input validation, and exposed endpoints are
the exact entry points adversaries exploit. CRP Scan catches them in CI, before production,
before attackers do.

### HMAC-signed audit = immutable attack evidence

When attacks are attempted, the audit chain captures them immutably. You don't just know an
attack happened — you cryptographically prove it to regulators, insurers, and auditors.

### Local LLM = zero external attack surface

With Ollama / LM Studio, sensitive data never leaves your network. Even if the gateway is
compromised, there is no external data pipeline to exploit. Zero-CKF mode provides maximum
isolation for the most sensitive deployments.

---

## How CRP compares

| Capability | Generic API gateway | RAG-only tool | Standalone safety tool | CRP Protocol |
|------------|---------------------|---------------|------------------------|--------------|
| Routes traffic | ✅ | ❌ | ❌ | ✅ |
| Retrieves documents | ❌ | ✅ | ❌ | ✅ |
| Detects prompt injection | ⚠️ basic | ❌ | ✅ | ✅ 13-stage |
| Traces output provenance | ❌ | ❌ | ⚠️ limited | ✅ full DAG |
| Generates compliance evidence | ❌ | ❌ | ❌ | ✅ runtime packs |
| Tamper-evident audit chain | ❌ | ❌ | ❌ | ✅ HMAC-signed |
| Continuous adversarial defense | ❌ | ❌ | ❌ | ✅ built-in |
| AIUC-1 mapped controls | ❌ | ❌ | ⚠️ partial | ✅ 80%+ |

---

## Honest gap analysis

CRP Protocol is **AIUC-1 aligned**, not yet **AIUC-1 certified**. To maintain credibility, here
are the areas CRP does not fully cover today and how we handle them:

| Gap | Why it matters | How CRP addresses it |
|-----|---------------|----------------------|
| **Third-party adversarial validation** | AIUC-1 certification requires an accredited auditor (e.g. Schellman) to conduct technical testing. | CRP provides the signed, tamper-evident evidence auditors need. We partner with accredited AIUC-1 auditors; internal red-teaming is already continuous. |
| **Harmful-output attestation** | External validation of harmful-output controls is required for certification. | CRP emits the control-evidence trail; certification requires an accredited auditor's attestation. |
| **Cyber-misuse prevention** | Preventing AI from assisting with malware, exploits, etc. | Roadmap item: add a dedicated cyber-misuse detection stage to the DPE pipeline. |
| **Catastrophic-misuse prevention** | Preventing assistance with severe harms such as WMD development. | Roadmap item: evaluate dedicated classifiers with explicit weight-boundary controls. |
| **Insurance integration** | AIUC certification can unlock insurance coverage. | Explore partnership with AIUC to offer "CRP-protected, AIUC-insured" bundles. |

!!! info "Certification is the floor, not the ceiling"
    AIUC-1 certification validates a point-in-time state. CRP's architecture makes adversarial
defense, audit, and compliance evidence **continuous by design** — so your system stays aligned
long after the certificate is issued.

## See the broader control-evidence mapping

CRP produces signed, tamper-evident evidence for every major AI assurance framework, not just
AIUC-1. See the complete mapping across EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, and SOC 2.

[:octicons-arrow-right-24: Control-evidence mapping](control-evidence.md){ .md-button .md-button--primary }

---

## Get started with AIUC-1 aligned AI

<div class="cta-bar" markdown>
<div class="cta-bar__text">
<div class="cta-bar__title">Ready to ship AI agents that pass enterprise security audits?</div>
<div class="cta-bar__subtitle">Start free in 60 seconds, or talk to our AIUC-1 compliance team.</div>
</div>
<div class="cta-bar__actions">
<a href="/getting-started/quickstart/" class="md-button md-button--primary">Start Free</a>
<a href="mailto:ai-governance@crprotocol.io" class="md-button">Contact Team</a>
</div>
</div>

```python title="One line to AIUC-1 aligned AI"
import crp

client = crp.SDKClient(safety="strict")
answer = client.ask("Summarise the contract")

print(answer.crp.risk)               # LOW | MEDIUM | HIGH | CRITICAL
print(answer.crp.fabrications)       # unsupported claims
print(answer.crp.grounded)           # True | False
print(answer.crp.injection_detected) # True | False
print(answer.crp.chain_valid)        # True | False
```

---

## Frequently asked questions

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is AIUC-1?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "AIUC-1 (AI Unified Certification) is the world's first independent standard to certify that AI agents are secure, safe, and reliable. Developed by the Artificial Intelligence Underwriting Company (AIUC) with 100+ Fortune 500 CISOs, it defines 51 requirements and 130 controls across six principles: Data & Privacy, Security, Safety, Reliability, Accountability, and Society."
      }
    },
    {
      "@type": "Question",
      "name": "Is CRP Protocol AIUC-1 certified?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP Protocol is AIUC-1 aligned: it provides the technical infrastructure to meet more than 80% of AIUC-1 requirements out of the box. Full third-party certification requires accredited auditor attestation; CRP's roadmap adds additional misuse-prevention classifiers and deeper auditor tooling."
      }
    },
    {
      "@type": "Question",
      "name": "Which AIUC-1 requirements does CRP cover?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP produces control evidence across all six AIUC-1 principles: Data & Privacy (input data policy, PII protection), Security (adversarial robustness, real-time filtering, unauthorized-action prevention, endpoint protection, deployment hardening), Safety (harmful-output prevention, human-in-the-loop, risk monitoring), Reliability (hallucination prevention, consistent behaviour), Accountability (identity, tamper-evident logging, AI disclosure), and Society (regulatory alignment, acceptable use, continuous assurance)."
      }
    },
    {
      "@type": "Question",
      "name": "How does CRP prevent prompt injection?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP's 13-stage DPE pipeline includes a prompt-injection shield that detects direct, indirect, goal-hijacking, exfiltration, and delimiter-forgery attacks in under 50 milliseconds on every call."
      }
    },
    {
      "@type": "Question",
      "name": "What AIUC-1 gaps remain?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP does not yet provide accredited third-party certification, dedicated cyber-misuse prevention, or catastrophic-misuse classifiers. These are on the roadmap through partnerships and additional DPE stages."
      }
    }
  ]
}
</script>

### What is AIUC-1?

AIUC-1 (AI Unified Certification) is the world's first independent standard to certify that AI
agents are secure, safe, and reliable. Developed by the Artificial Intelligence Underwriting Company
(AIUC) with 100+ Fortune 500 CISOs, it defines 51 requirements and 130 controls across six
principles: Data & Privacy, Security, Safety, Reliability, Accountability, and Society.

### Is CRP Protocol AIUC-1 certified?

CRP Protocol is **AIUC-1 aligned**: it provides the technical infrastructure to meet more than
80% of AIUC-1 requirements out of the box. Full third-party certification requires accredited
auditor attestation; CRP's roadmap adds additional misuse-prevention classifiers and deeper auditor
tooling.

### Which AIUC-1 requirements does CRP cover?

CRP produces control evidence across all six AIUC-1 principles: Data & Privacy (input data
policy, PII protection), Security (adversarial robustness, real-time filtering, unauthorized-action
prevention, endpoint protection, deployment hardening), Safety (harmful-output prevention,
human-in-the-loop, risk monitoring), Reliability (hallucination prevention, consistent behaviour),
Accountability (identity, tamper-evident logging, AI disclosure), and Society (regulatory alignment,
acceptable use, continuous assurance).

### How does CRP prevent prompt injection?

CRP's 13-stage DPE pipeline includes a prompt-injection shield that detects direct, indirect,
goal-hijacking, exfiltration, and delimiter-forgery attacks in under 50 milliseconds on every call.

### What AIUC-1 gaps remain?

CRP does not yet provide accredited third-party certification, dedicated cyber-misuse prevention,
or catastrophic-misuse classifiers. These are on the roadmap through partnerships and additional
DPE stages.

---

## See also

- [AI Safety Protocol](topics/ai-safety.md)
- [AI Governance Framework](topics/ai-governance.md)
- [AI Compliance](topics/ai-compliance.md)
- [CRP Safety Case](safety/index.md)
- [DPE Pipeline](safety/dpe.md)
- [Products](products/index.md)
- [Control-evidence mapping](control-evidence.md)
- [CRPv5 Improvements](crpv5-roadmap.md)
