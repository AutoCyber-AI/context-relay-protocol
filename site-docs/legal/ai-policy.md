---
title: AI Policy
description: >-
  AutoCyber AI Pty Ltd AI policy - governing the development, deployment, and
  governance of AI systems per ISO/IEC 42001:2023 and the EU AI Act.
---

# AI Policy

**Company:** AutoCyber AI Pty Ltd (ABN 22 697 087 166)
**Policy owner:** Constantinos Vidiniotis, Founder & AI Governance Lead
**Effective date:** 27 May 2026
**Review cycle:** Annual
**Version:** 1.0
**Framework alignment:** ISO/IEC 42001:2023 Clause 5 · EU AI Act (Regulation 2024/1689) · NIST AI RMF 1.0 · OECD AI Principles

---

## 1. Purpose

AutoCyber AI Pty Ltd develops, deploys, and maintains AI systems - including the
**Context Relay Protocol™ (CRP)** and the **CRP product family** - for use in
cybersecurity, compliance, and AI governance.

This policy establishes the top-level commitments of AutoCyber AI regarding:

- How we **design and develop** AI systems
- How we **deploy** AI systems responsibly
- How we **govern** AI use within our own operations
- How we **support users** in meeting their own AI governance obligations

This policy satisfies:

- **ISO/IEC 42001:2023 Clause 5.2** (Leadership and commitment - AI policy)
- **ISO/IEC 42001:2023 Annex A.2** (Policies for AI systems)
- **EU AI Act Art. 17** (Quality Management System - policies)
- **NIST AI RMF GOVERN function** (Organisational governance)

---

## 2. Scope

This policy applies to:

1. All **AI systems developed by AutoCyber AI** - including CRP Comply, CRP Gateway, CRP Scribe,
   CRP Visualise, and the CRP library itself.
2. All **personnel, contractors, and third parties** who develop, operate, or contribute to those
   systems.
3. All **AI tools used internally** by AutoCyber AI (e.g., LLMs used in development assistance).

---

## 3. Our AI commitments

### 3.1 Human oversight

> "AI systems must support, not replace, human judgment in consequential decisions."

- Every AutoCyber AI product classifies its outputs with a **confidence score and hallucination
  risk rating** via the CRP Decision Provenance Engine (DPE).
- All AI-generated compliance reports are labelled as **advisory outputs**. Final decisions must
  be reviewed and accepted by a qualified human.
- Products provide **human override** mechanisms at every decision point.
- We design to EU AI Act Art. 14 standards: meaningful human oversight is a first-class design
  requirement, not an afterthought.

### 3.2 Transparency

- AI involvement is always **disclosed** to end users. No outputs are presented as if produced
  by a human.
- Every AI-generated output carries an **audit trail** (HMAC-signed, timestamped, attributable
  to specific model + version + prompt).
- Model names and versions used in evidence packs are recorded and disclosed to users.
- Our AI system architecture and data flows are documented in our [product documentation](../products/index.md).

### 3.3 Accuracy and reliability

- AutoCyber AI products use **tool-based classification** - regulatory articles, risk scores, and
  control numbers are produced by deterministic Python tools, not LLM free-text generation. The
  LLM cannot invent an article number or a fine amount.
- Outputs are cross-referenced against our authoritative regulatory corpus, which is versioned,
  hash-verified, and updated via a Live Regulation CI pipeline.
- Performance is benchmarked against known test cases. Benchmarks are published in
  [BENCHMARKS.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/BENCHMARKS.md).

### 3.4 Fairness and non-discrimination

- We do not design or market AI systems for purposes that would constitute unlawful discrimination.
- Our compliance analysis tools are neutral with respect to user organisation size, sector, or
  jurisdiction (within supported regulation packs).
- We conduct **bias audits** on any model fine-tune or classification layer before release.

### 3.5 Privacy and data protection

- Personal data processed by AI systems is minimised, anonymised where possible, and processed
  lawfully (see [Privacy Policy](privacy-policy.md)).
- **PII is redacted before LLM calls** using the `crp.security.PIIScanner`. PII never enters
  the LLM prompt.
- BYOK (Bring Your Own Key) modes allow enterprise users to route inference through their own
  LLM endpoint, ensuring personal data never leaves their perimeter.
- A **Data Protection Impact Assessment (DPIA)** is conducted for any AI system that processes
  personal data at scale (GDPR Art. 35).

### 3.6 Security

- AI systems are subject to the same controls as non-AI systems (see
  [Information Security Policy](information-security-policy.md)) plus AI-specific controls:
  - **Prompt injection defence** - system prompt architecture frames user input as untrusted;
    tools are the only classification emitter.
  - **Contradiction detection** - new user claims are checked against the Contextual Knowledge
    Fabric (CKF) to detect inconsistencies.
  - **Adversarial robustness** - products are tested against prompt-injection, jailbreak, and
    context-manipulation attacks before release.

### 3.7 Environmental responsibility

- We prefer smaller, efficient models over large models where task accuracy is equivalent.
- BYOK and local-model modes eliminate cloud inference cost and the associated carbon footprint.
- Model selection decisions document energy / carbon trade-offs where material.

---

## 4. EU AI Act risk classification

AutoCyber AI has assessed its AI systems under the EU AI Act (Regulation 2024/1689) risk
framework:

| System | Classification | Basis | Controls applied |
|---|---|---|---|
| **CRP Comply** (compliance analysis) | **Limited risk** - transparency obligations apply | Advisory tool; no binding decisions; human oversight mandatory | Art. 13 transparency; output labelling; Art. 14 human oversight design |
| **CRP Scribe** (document generation) | **Minimal risk** | Content-generation tool for business documents | Voluntary transparency best practices |
| **CRP Gateway** (inference proxy / monitoring) | **Minimal risk** | Infrastructure component; no autonomous decision-making | Runtime audit logging per Art. 12 principles |
| **CRP library** (open-source protocol) | **Minimal risk** - open-source exclusion may apply (Art. 2(12)) | Developer tooling; decisions rest with the integrating application | N/A (pass-through; obligations fall to the deployer) |

> **Note:** If a downstream user deploys CRP Comply in a **high-risk context** as defined by
> EU AI Act Annex III (e.g., employment decisions, creditworthiness, critical infrastructure),
> additional obligations apply to **the deployer** under Art. 26/27. CRP Comply provides the
> technical documentation, logs, and audit trail required to support such compliance - but the
> deployer bears primary responsibility for conformity assessment.

---

## 5. ISO/IEC 42001 alignment

This policy forms part of our **AI Management System (AIMS)** in accordance with ISO/IEC 42001:2023.

| Clause | Implementation |
|---|---|
| **5.1** Leadership and commitment | Policy owned by Founder; reviewed annually; communicated to all personnel |
| **5.2** AI Policy (this document) | ✅ This document |
| **6.1** Risk and opportunity assessment | AI impact assessments conducted for each product; risks logged in AIMS register |
| **6.2** AI objectives | Accuracy targets, hallucination-rate SLOs, and audit-completeness targets published per product |
| **7.4** Communication | AI policy published publicly at [crprotocol.io/legal/ai-policy/](https://crprotocol.io/legal/ai-policy/) |
| **8.4** AI system lifecycle | Lifecycle documented: design → development → testing → deployment → monitoring → retirement |
| **9.1** Monitoring and measurement | Runtime monitoring via CRP audit trail; quarterly internal review |
| **9.3** Management review | Annual AIMS review by Founder and Policy Owner |
| **10.2** Continual improvement | Incident-driven + annual review cycle |

### Statement of Applicability (SoA) - Annex A summary

| Control area | Status | Notes |
|---|---|---|
| A.2 Policies for AI | ✅ Implemented | This document |
| A.3 Internal organisation | ✅ Implemented | Policy Owner assigned; roles documented |
| A.4 Resources for AI systems | ✅ Implemented | Model selection criteria; LLM hosting options |
| A.5 Assessing impacts of AI systems | ✅ Implemented | Impact assessment per product (see AIMS register) |
| A.6 AI system lifecycle | ✅ Implemented | Documented in product engineering runbooks |
| A.7 Data for AI systems | ✅ Implemented | Corpus versioning, license management, content-hash integrity |
| A.8 Information for interested parties | ✅ Implemented | Public documentation; product user guides |
| A.9 Use of AI systems | 🔄 In progress | Runtime monitoring deployed; quarterly review cadence being formalised |
| A.10 Third-party and supply-chain | ✅ Implemented | Supplier DPAs; Dependabot; allow-list SSRF controls |

---

## 6. Prohibited uses

AutoCyber AI products and the CRP library **must not** be used for:

- Mass surveillance, social scoring, or real-time biometric identification in public spaces
  (EU AI Act Art. 5 prohibited practices)
- Generating disinformation, synthetic identity fraud, or deepfake content
- Automated profiling that results in unlawful discrimination under applicable law
- Any purpose that violates the CRP [Terms of Service](../terms-of-service.md) or applicable law

---

## 7. User obligations

When you use CRP Comply or other AutoCyber AI products to generate compliance evidence:

- You are responsible for reviewing AI outputs before using them in regulatory submissions.
- You are responsible for providing accurate inputs; the quality of AI outputs depends on input
  quality.
- You are responsible for maintaining the final compliance posture of your own AI systems. Our
  tools are **evidence-generation aids**, not substitutes for qualified legal or regulatory advice.

---

## 8. Accountability and governance

| Role | Responsibility |
|---|---|
| Founder / Policy Owner | Approve and review this policy; escalation point for AI ethics issues |
| Engineering Lead | Implement technical controls; manage the AIMS register |
| All personnel | Comply with this policy; report concerns or incidents |

Concerns about AI ethics, bias, or misuse may be raised confidentially to
[ai-governance@crprotocol.io](mailto:ai-governance@crprotocol.io).

---

## 9. Related documents

- [Privacy Policy](privacy-policy.md)
- [Information Security Policy](information-security-policy.md)
- [Terms of Service](../terms-of-service.md)
- [Compliance: ISO 42001](../compliance/iso-42001.md)
- [Compliance: EU AI Act](../compliance/eu-ai-act.md)
- [Compliance: GDPR](../compliance/gdpr.md)
- [Safety Case](../safety/index.md)
- [SECURITY.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/SECURITY.md)

---

## 10. Review history

| Version | Date | Change summary |
|---|---|---|
| 1.0 | 27 May 2026 | Initial publication |

---

*AutoCyber AI Pty Ltd · ABN 22 697 087 166 · Victoria, Australia*
*For AI governance enquiries: [ai-governance@crprotocol.io](mailto:ai-governance@crprotocol.io)*
