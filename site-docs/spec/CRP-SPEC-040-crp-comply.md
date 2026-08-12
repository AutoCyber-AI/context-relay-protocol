# CRP-SPEC-040: CRP Comply - The Three-Layer AI Compliance & Governance Platform

**Document:** CRP-SPEC-040  
**Title:** Context Relay Protocol (CRP) - CRP Comply: Product Specification for the Three-Layer Compliance Platform (Programme · Artefacts · Evidence)  
**Version:** 2.0.0 - Aligned to live product (comply.crprotocol.io)  
**Status:** Foundational - Product Specification  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Consumes:** the governance/safety/audit output of the entire protocol  
**Prerequisites:** CRP-SPEC-010, 011, 033, 034, 036  
**Reflects:** the deployed product at comply.crprotocol.io (CRP 3.1.1 / Comply 0.1.0)

---

## Abstract

CRP Comply is the deployed compliance and AI-governance platform built on CRP. This specification is aligned to the live product rather than an idealised design. CRP Comply is organised around a **three-layer compliance model** - Layer 1 Programme (policy/governance text), Layer 2 Artefacts (the evidence you supply), Layer 3 Evidence (runtime audit substrate) - where each layer depends on the one before it, and the platform's central honesty principle is *provenance on every paragraph*: a deliverable that cites a model card which does not exist is fiction, so the platform tracks what evidence actually backs each claim. The product is delivered through two complementary generation surfaces - **Recipes** (deterministic, citation-grounded, form-driven deliverables) and the **Agent** (open-ended, interview-driven, corpus-retrieving) - backed by a **Vault** (append-only deliverable store), an **Evidence** substrate (HMAC-signed runtime audit), and an **Artefact Room** (the Layer 2 evidence tracker). It is BYO-LLM by design (commercial key, local endpoint, or hosted-by-us). Public plan descriptions are maintained on the [pricing page](../pricing.md). This document specifies the product as it exists and the roadmap surfaces that extend it.

---

## 1. The Three-Layer Compliance Model (the product's spine)

CRP Comply's defining structure. A compliance programme has three layers, each depending on the one before:

```
┌────────────────────────────────────────────────────────────────┐
│ LAYER 1 - PROGRAMME   (policy / governance text)               │
│   Interview-driven policy layer: AI Policy, Statement of        │
│   Applicability, QMS, Art. 17 manual, Art. 13 instructions.     │
│   Produced by the agent from your profile + regulatory corpus.  │
│   NO RUNTIME REQUIRED. This is the readiness programme.         │
├────────────────────────────────────────────────────────────────┤
│ LAYER 2 - ARTEFACTS   (the evidence you supply)                │
│   Model cards, dataset cards, architecture diagrams, DPAs,      │
│   pen-test reports, prior certifications. Without this layer,   │
│   Layer 1 is claims you cannot back up.                         │
├────────────────────────────────────────────────────────────────┤
│ LAYER 3 - EVIDENCE    (runtime audit substrate)                │
│   Proxy / SDK / webhook ingests your AI system's traffic and    │
│   produces the tamper-evident evidence AI Act Art. 12/15/72/73  │
│   and ISO 42001 Clause 9.1 require. HMAC-signed, chained.       │
└────────────────────────────────────────────────────────────────┘
```

### 1.1 The Critical Product Truth: Where the Runtime Fits

A defining honesty of the product - **the proxy is not optional for compliance, only for readiness:**

- You can buy CRP Comply for **Layer 1 alone** and use it as a **readiness programme** - useful for procurement, funding due-diligence, or pre-launch.
- But regulations with operational-evidence clauses (**AI Act Art. 12/15/72/73, ISO 42001 Clause 9.1 & Annex A.9, GDPR Art. 30/33, NIS2**) **require Layer 3**. Without runtime evidence, those clauses cannot be satisfied.

This distinction is the spine of the product: most customers start at Layer 1 (readiness), and move to Layer 3 (actual compliance) when they ship a production AI system.

### 1.2 The Provenance Principle

The platform's intellectual core: **provenance on every paragraph.** A DPIA or Annex IV technical file that references a "model card" which does not exist is fiction. The drafting loop looks identical from the outside, but the evidence underneath is missing. The Artefact Room (Layer 2, §4) tells the agent what evidence actually exists, so every paragraph of every deliverable carries a real provenance tag - drafted-by-agent, uploaded-by-you, or referred-to-third-party.

---

## 2. The Two Generation Surfaces - Recipe vs Agent

CRP Comply produces deliverables through two complementary surfaces. Understanding the distinction is essential to the product.

### 2.1 Recipes - Deterministic, Citation-Grounded

A **Recipe** is a deterministic, form-driven deliverable: answer a tailored set of inputs, get a signed draft in a known shape, citing specific articles. Recipes are the right surface for **Layer 1** policy/governance deliverables that have a known structure.

- Deterministic and reproducible - same inputs, same shaped output.
- Citation-grounded - cites specific regulatory articles.
- Form-driven - a tailored clarifying-questions flow, not open conversation.
- Examples: AI Literacy Programme (Art. 4), Prohibited Practices Self-Assessment (Art. 5), Transparency Notices (Art. 50), ISO 42001 AI Policy (Cl. 5.2), Statement of Applicability, Risk Treatment Plan, Management Review Record.

### 2.2 The Agent - Open-Ended, Interview-Driven

The **Agent** is conversational and open-ended - the right surface for **Layer 2 / 3** deliverables that need a branching interview, artefact upload, or runtime evidence. It retrieves from the regulatory corpus (EU AI Act, GDPR, ISO 42001, NIS2, OECD, etc.), asks clarifying questions, and produces answers with inline citations.

- Retrieves from the regulatory corpus (this is where CRP's CKF + retrieval power the agent).
- Asks clarifying questions as it goes (interview-driven).
- Produces inline-cited answers.
- Any agent answer can be **promoted to a saved Vault report in one click**.
- Example prompts: "Am I high-risk under Annex III?", "Draft the transparency statement for my recruiting assistant.", "What Annex III obligations apply to credit scoring?"

### 2.3 Agent Dispatch Modes

The agent runs in two dispatch modes (from the live Settings):
- **CRP mandatory (default)** - iterative domain-tool loop running all compliance domain tools (regulation query, AI Act risk classification, DPIA drafting, etc.). Recommended.
- **Agentic** - free-form Q&A where no structured compliance deliverable is needed.

The CRP audit trail is applied in **all** modes - the governance is never bypassed regardless of dispatch mode.

---

## 3. Layer 1 - The Programme (Obligations View)

### 3.1 The Programme Surface

The obligation-level view of the compliance programme. Each tile is **one deliverable one regulator will ask for**, tailored to the customer's profile, with its current evidence state:

```
Programme state:  [N ready] [N to draft] [N not applicable]

Grouped by regulation:
  EU AI Act      · Art. 4 literacy · Art. 5 prohibited · Art. 50 transparency ...
  ISO 42001      · AI Policy · Risk Assessment · Risk Treatment · SoA · Objectives ...
  NIST AI RMF    · RMF Profile
  Other          · conformity_evidence_pack (composed binder)
```

### 3.2 Profile-Driven Tailoring

Everything branches off the **onboarding questionnaire**, which captures: **actor role** (provider / deployer), **jurisdictions**, **risk tier**, and **whether the org trains GPAI models**. Every recommendation - which deliverables apply, the compliance score, the tailoring of each deliverable - derives from this profile. A deliverable marked "not applicable" was excluded by profile logic, not omitted.

### 3.3 Deliverable States

Each deliverable carries an evidence state: **Draft needed** (ready to generate), **Needs artefacts** (blocked on a Layer 2 upload - e.g. the AI System Impact Assessment needs model/dataset cards), or **Ready** (generated and in the Vault). This state model operationalises the provenance principle: a deliverable cannot be truly "ready" if the artefacts it cites are missing.

---

## 4. Layer 2 - The Artefact Room

### 4.1 The Three Artefact Dispositions

The Artefact Room tracks each class of evidence a regulator might ask for, and classifies how it is obtained:

| Disposition | Meaning | Examples |
|-------------|---------|----------|
| **Draftable by agent** | The platform can draft it from profile + corpus | AI policy & governance framework, Statement of Applicability |
| **You upload** | The customer owns it; the platform slots it in | Model card, dataset card & lineage, architecture diagram, prior certifications, vendor DPAs |
| **Referred out** | Must be done by a qualified third party | Penetration test & AI red-team report, legal sign-off |

### 4.2 The Honest Referral Model

A defining product integrity choice: some evidence the platform **will not** produce, because regulators expect independence. The pen-test / AI red-team report is **referred out** to an independent security-testing provider; the customer uploads the resulting report and Comply slots it into the Art. 15 accuracy/robustness/cyber evidence. Legal sign-off is similarly referred to the customer's own counsel.

This referral model is honest: Comply does not fake independent testing.

### 4.3 Why the Artefact Room Exists

It is the operationalisation of the provenance principle: it tells the agent what evidence the customer actually has, so every paragraph of every deliverable carries a real provenance tag. A deliverable referencing an artefact the customer has uploaded is backed; one referencing a missing artefact is flagged "Needs artefacts."

---

## 5. Layer 3 - The Evidence Substrate (Runtime)

### 5.1 What It Is

Immutable audit records of every AI inference that flowed through the customer's proxy. Each row is **HMAC-signed and independently verifiable** - this is the CRP audit chain (SPEC-011) applied to the customer's production traffic. It is what post-market monitoring, logging, and RoPA obligations actually cite.

### 5.2 The Evidence Dashboard

```
Total inferences · Compliance rate · PII detections · Injection attempts
Recent audit records (HMAC signed, last N of N)
```

### 5.3 How the Runtime Is Wired

Three ingestion paths (the customer opts in by routing their product through one):
- **Proxy** - point the AI system's LLM base URL at the Comply proxy.
- **SDK** - wrap calls with the Python SDK.
- **Webhook** - push inference data to Comply.

The drop-in proxy is OpenAI-compatible (from the live integration snippets):
```python
from openai import OpenAI
client = OpenAI(
    base_url="https://your-comply.example/v1",
    api_key="crp_YOUR_API_KEY",
)
# Compliance headers returned:
#   X-CRP-Comply: active
#   X-CRP-Comply-Record-ID: <audit-record-id>
#   X-CRP-Comply-Risk: MINIMAL | HIGH
#   X-CRP-Comply-Hallucination-Risk: LOW | MEDIUM | HIGH | CRITICAL
```

### 5.4 The Two Key Roles (Critical Distinction)

A subtle but important product point the live docs stress: there are **two distinct LLM key purposes** that must not be confused:
- The **BYOK platform key** (§7) powers the **compliance agent** (drafting deliverables, answering questions).
- The **Layer 3 runtime wiring** routes the customer's **own product traffic** through the evidence substrate.

These are separate. One runs the platform's intelligence; the other captures the customer's production evidence.

---

## 6. The Vault - Append-Only Deliverable Store

Every deliverable the compliance programme produces lands in the Vault: **append-only, hashable, exportable.** 

### 6.1 The Evidence Pack Export

The Vault's headline capability: when an auditor, insurer, or procurement team asks, export a **signed evidence pack** - risk management file, DPIA, processing records (GDPR Art. 30), conformity evidence, and the audit chain - as a single **zipped, article-mapped bundle**. This is the deliverable that closes enterprise deals and satisfies regulators: one signed, article-mapped export of the entire compliance position.

### 6.2 Storage Location Choice

Customers choose where deliverables live (from live Settings):
- **Your device (local)** - artefacts download to the browser; nothing retained on Comply infrastructure beyond the active session. Available on every plan. The customer controls the evidence trail end-to-end (and is responsible for its backup).
- **Hosted volume (cloud)** - tenant-isolated directory, replicated nightly to off-region disaster recovery (Cloudflare R2), searchable across full history from any device. Requires a paid tier.

This local-vs-hosted choice is the data-sovereignty control, consistent with the BYO-storage principle (SPEC-038).

---

## 7. The BYO-LLM Model

### 7.1 Three LLM Options

CRP Comply never bundles an LLM by default. The customer picks:
- **(a) BYOK commercial** - their OpenAI/Anthropic/Azure/Bedrock key, AES-256-GCM encrypted in the vault, subject to their vendor DPA. Best model quality.
- **(b) BYOK local** - point at LM Studio / Ollama / vLLM / llama.cpp; nothing leaves the network. Zero token cost. **This is the recommended Free-tier path.**
- **(c) Hosted by us** - Comply carries LLM capacity on Scale/Enterprise tiers; one invoice, no key to rotate.

Without an LLM configured, drafting and the agent return 502 - the LLM is the engine of the platform.

### 7.2 Audited-Call Quota

The public plan structure is summarised on the [pricing page](../pricing.md). At the protocol level:
- **Audited calls** are the metered unit. Every audited call (risk assessment, compliance report, DPIA, transparency, technical documentation, session audit, evidence pack) counts toward a monthly quota. Public free risk-classifier calls are rate-limited per IP and do not count.
- **Free tier:** 100 audited calls/month; local-LLM path; local storage only.
- **Paid tiers** (Starter / Scale / Enterprise) unlock: hosted storage, higher quotas, hosted LLM, longer retention.

This is a usage-aligned model: the free tier proves value, and tiers scale with real usage.

---

## 8. The Full Navigation / Surface Map (live product)

| Surface | Purpose |
|---------|---------|
| **Dashboard** | org overview, compliance scores by regulation (AI Act / ISO 42001 / GDPR), outstanding actions |
| **How it works** | the three-layer guide + setup steps |
| **Draft** | the Workspace - run a recipe or chat the agent |
| **Programme** | Layer 1 obligation tiles, tailored to profile |
| **Deliverables** | the recipe library (tailored + all, 30 deliverables) |
| **Artefacts** | Layer 2 artefact room (draftable / uploadable / referred) |
| **Evidence** | Layer 3 runtime audit records (HMAC-signed) |
| **Vault** | append-only deliverable store + evidence-pack export |
| **Inbox** | (checkpoint / review surface - see §9) |
| **Settings** | subscription, usage, LLM provider, storage, API keys, integration snippets |

### 8.1 The Compliance Score

The Dashboard shows an overall compliance percentage and per-regulation breakdown (e.g. AI Act 17%, ISO 42001 88%, GDPR 0%). This score is profile-derived (which obligations apply) and state-derived (how many are ready vs to-draft vs blocked-on-artefacts). It is the at-a-glance posture metric and a core engagement driver - customers work to raise the number.

---

## 9. Where the Safety Control Plane & Checkpoints Fit (roadmap alignment)

The live product has an **Inbox** surface. This is the natural home for the inline human-in-the-loop **Checkpoint inbox** (SPEC-033/034) and the **Scan remediation inbox** (SPEC-036) specified earlier. The alignment:

- The **Safety Control Plane** (SPEC-033) extends the live Settings/governance surface into the full safety registry (tune grounding, halt levels, custom rules) - building on the existing `CRP agent dispatch mode` and audit-trail controls already present.
- The **Checkpoint Inbox** (SPEC-034) populates the existing **Inbox** surface - checkpoints fired by customer systems land here for human resolution, producing the Art. 14 human-oversight evidence that slots into Layer 3.
- The **Scan Remediation Inbox** (SPEC-036) is a second Inbox stream - ungoverned-AI findings with one-click code-fix PRs and config remediations.

These are roadmap extensions of surfaces that already exist (Inbox, Settings, Evidence), not new products. They deepen Comply from a compliance-document platform into the full **AI Safety Control Centre** (SPEC-034 §14).

---

## 10. The Regulatory Corpus & Coverage

CRP Comply's agent retrieves from a regulatory corpus spanning **EU AI Act (Regulation (EU) 2024/1689), GDPR, ISO/IEC 42001:2023, NIST AI RMF, NIS2, OECD**, and more. The deliverable library covers 30 deliverables (12+ tailored to a typical profile) across these frameworks. Each deliverable maps to specific articles/clauses - e.g. EU AI Act Art. 4/5/50, ISO 42001 Clauses 5.2/6.1.2/6.1.3/6.1.4/6.2/9.3 and Annex A, GDPR Art. 30/33/35, NIST AI RMF Govern/Map/Measure/Manage.

This corpus + retrieval is itself a CRP showcase: the agent grounding its citations in the regulatory corpus is CRP's CKF + retrieval doing exactly what the protocol promises - grounded, cited, provenance-tracked generation.

---

## 11. The Relationship to the Protocol and Other Products

```
CRP PROTOCOL (open)  ──── governs every call, emits signals
        │
        ├─ CRP GATEWAY (SPEC-016)   ── hosted execution
        ├─ CRP SCAN (013/036/039)   ── finds ungoverned AI → Comply Inbox
        └─ CRP COMPLY (this spec)   ── the three-layer compliance platform
```

CRP Comply is the deployed product where the protocol's governance becomes compliance evidence and a managed programme. Independent security testing is referred out. CRP Scan feeds the Inbox. The Gateway is the scaled execution layer.

---

## 12. Honest Status & Roadmap

**Live today (Comply 0.1.0):** the three-layer model, recipes + agent, the programme/deliverables/artefacts/evidence/vault surfaces, BYO-LLM, the OpenAI-compatible proxy with compliance headers, local/hosted storage, the regulatory corpus, profile-driven tailoring, and the evidence-pack export.

**Roadmap (specified in this suite, building on live surfaces):**
- The full Safety Control Plane in Settings (SPEC-033).
- The Checkpoint Inbox populating the Inbox surface (SPEC-034).
- The Scan Remediation Inbox as a second Inbox stream (SPEC-036/039).
- The developer observability dashboard (quality trends, fabrications caught) extending the Evidence dashboard.
- Deeper evidence-pack article mapping and richer conformity binders.

**Honest limits:** the platform generates evidence-backed sections but regulatory artifacts still need human-authored context (intended purpose, deployment narrative) - the agent drafts and prompts for these. It generates evidence only for governed traffic (ungoverned calls produce nothing - which is why Scan exists). Independent testing (pen-test, legal) is deliberately referred out. The compliance score is a readiness indicator, not a legal guarantee of compliance.

---

## 13. References

- CRP-SPEC-010 - Regulatory Mapping (deliverable → article mapping)
- CRP-SPEC-011 - Audit Trail (the Layer 3 evidence substrate)
- CRP-SPEC-016 - Gateway (scaled execution)
- CRP-SPEC-033/034 - Safety Control Plane & Checkpoints (Settings + Inbox roadmap)
- CRP-SPEC-036/039 - Scan Remediation (Inbox roadmap)
- CRP-SPEC-038 - Storage Backends (local/hosted vault choice)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd. Aligned to the deployed product at comply.crprotocol.io (CRP 3.1.1 / Comply 0.1.0).*
