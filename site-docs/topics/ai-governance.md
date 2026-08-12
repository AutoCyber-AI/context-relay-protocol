---
seo_title: AI Governance Framework for LLMs — Policies, Oversight & Audit
description: CRP is an AI governance framework that enforces policies, human oversight, audit trails, and accountability for LLM systems through standard HTTP headers.
tags:
  - ai-governance
  - ai-safety
  - crp
---

# AI Governance Framework

<div class="hero-splash hero-splash--dark" markdown>

<div class="hero-kicker">🎯 Agentic Positioning · Governed by Design</div>

<h2 class="hero-headline" markdown>
Governance That Generates Audit-Ready Evidence.
</h2>

<p class="hero-sub">
Declarative policies, identity headers, human-in-the-loop checkpoints, and tamper-evident
audit — CRP Protocol's governance layer doesn't just control AI; it documents every decision
for regulators. HMAC-signed audit chains prove what happened, when, and who authorised it.
The evidence the EU AI Act, AIUC-1, ISO 42001, and NIST AI RMF all require.
</p>

<div class="aiuc-badge-list">
<span class="aiuc-badge">AIUC-1 Accountability — Activity Logging</span>
<span class="aiuc-badge">AIUC-1 Accountability — Quality Management</span>
<span class="aiuc-badge">EU AI Act Art. 17 — QMS</span>
</div>

<div class="hero-buttons">
<a href="/control-evidence/" class="md-button md-button--primary">See Control-Evidence Mapping</a>
<a href="/compliance/" class="md-button">Compliance Evidence</a>
</div>

</div>

**AI governance** is the system of policies, processes, controls, and accountability structures that ensure AI systems are developed, deployed, and operated responsibly, transparently, and in line with legal and ethical obligations.

For enterprises running LLMs, AI governance answers questions like:

- Who is accountable when an AI system makes a harmful decision?
- How do we enforce usage policies across models and providers?
- Where is the audit trail that proves compliance?
- How do we maintain human oversight without blocking every call?

Context Relay Protocol (CRP) turns these governance requirements into a **wire-level contract**: policies travel as HTTP headers, decisions are recorded in a tamper-evident audit chain, and oversight can be triggered automatically or on demand.

---

## Why LLMs need a governance framework

| Governance gap | Typical consequence | CRP control |
|---|---|---|
| No system inventory | Unknown shadow-AI usage | `CRP-System-Id` and session headers |
| No policy enforcement | Developers implement rules inconsistently | Declarative Safety Policy headers |
| No audit trail | Forensic investigation takes weeks | HMAC-chained window-level audit events |
| No human oversight | High-risk outputs ship automatically | Checkpoint headers with async approval |
| No accountability | Nobody owns a model decision | `CRP-Chain-Id`, `CRP-Agent-Id`, `CRP-Operator-Id` |

---

## CRP governance capabilities

### 1. Declarative policy enforcement

Governance rules are declared once and enforced at the Gateway:

```http
CRP-Safety-Policy: profile strict;
                   halt-on CRITICAL;
                   require-grounding 0.80;
                   redact-on HIGH PII;
                   checkpoint-on HIGH;
                   max-chain-budget 100
```

Applications do not need to reimplement these rules. The policy hash is pinned to the session token, so policy drift is cryptographically detectable. See [Safety Policy](../protocol/safety-policy.md).

### 2. Identity and chain-of-custody

Every CRP call carries identifiers for the session, chain, agent, operator, and AI system:

| Header | Purpose |
|---|---|
| `CRP-Session-Id` | Bind all windows in one user session |
| `CRP-Chain-Id` | Track multi-turn or multi-agent chains |
| `CRP-Agent-Id` | Identify the acting agent |
| `CRP-Operator-Id` | Link calls to a human owner |
| `CRP-System-Id` | Map calls to a registered AI system inventory |

### 3. Human-in-the-loop

When a call crosses a risk threshold, CRP emits a checkpoint event:

```http
CRP-Safety-Checkpoint: HIGH
CRP-Safety-Checkpoint-Uri: https://comply.crprotocol.io/checkpoints/abc123
```

A human reviewer can approve, reject, or edit the output. The decision is signed and added to the audit chain. See [Safety Control Plane](../protocol/safety-policy.md).

### 4. Tamper-evident audit

Every window extends an HMAC-SHA256 audit chain. Any tampering surfaces as `CRP-Provenance-Chain-Integrity: BROKEN`. The chain supports regulator-ready export in JSON or CSV.

---

## Standards alignment

| Standard | CRP governance contribution |
|---|---|
| **AIUC-1** | One of CRP's strongest proof points: Accountability (assignment, activity logging, AI disclosure, acceptable-use policy) and Society (quality management) — mapped and enforced through headers, checkpoints, and audit export. [Full mapping →](../aiuc-1.md) |
| **EU AI Act** | Risk management, data governance, technical documentation, record-keeping, transparency, human oversight, accuracy, and quality management. |
| **ISO/IEC 42001:2023** | AI management system context, leadership, planning, support, operations, and improvement evidence. |
| **NIST AI RMF** | GOVERN function (risk culture, accountability, legal review) and MAP function (context establishment, categorisation). |
| **GDPR** | Records of processing, DPIA support, data-minimization controls, and breach evidence. |

[:octicons-arrow-right-24: Compliance overview](../compliance/index.md)

---

## Frequently asked questions about AI governance

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is an AI governance framework?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "An AI governance framework is a structured set of policies, processes, controls, and accountability structures that ensure AI systems are secure, accurate, transparent, compliant, and aligned with organisational values."
      }
    },
    {
      "@type": "Question",
      "name": "How does CRP enforce AI governance?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP enforces governance through declarative Safety Policy headers, cryptographically pinned session tokens, identity headers, human-in-the-loop checkpoints, and a tamper-evident audit chain."
      }
    },
    {
      "@type": "Question",
      "name": "Can CRP work with our existing AI systems?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. CRP is provider-neutral and wraps any OpenAI-compatible endpoint. You can adopt it as a Gateway proxy, an SDK, or a sidecar without changing your application model."
      }
    }
  ]
}
</script>

### What is an AI governance framework?

An AI governance framework is a structured set of policies, processes, controls, and accountability structures that ensure AI systems are secure, accurate, transparent, compliant, and aligned with organisational values.

### How does CRP enforce AI governance?

CRP enforces governance through declarative Safety Policy headers, cryptographically pinned session tokens, identity headers, human-in-the-loop checkpoints, and a tamper-evident audit chain.

### Can CRP work with our existing AI systems?

Yes. CRP is provider-neutral and wraps any OpenAI-compatible endpoint. You can adopt it as a Gateway proxy, an SDK, or a sidecar without changing your application model.

---

## See also

- [Control-evidence mapping](../control-evidence.md)
- [AIUC-1 Aligned Safety & Security](../aiuc-1.md)
- [AI Safety](ai-safety.md)
- [AI Compliance](ai-compliance.md)
- [Context Management](context-management.md)
- [CRP Comply product](../products/comply.md)
- [Standards Track](../standards.md)
