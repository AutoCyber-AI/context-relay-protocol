# CRP-SPEC-044: The Authoritative Domain Agent

**Document:** CRP-SPEC-044  
**Title:** Context Relay Protocol (CRP) — The Authoritative Domain Agent: Provably-Grounded Expert Agents Bound to an Official Corpus  
**Version:** 1.0.0  
**Status:** Foundational — New Product Pattern  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Generalises:** the CRP Comply compliance agent into a reusable pattern  
**Prerequisites:** CRP-SPEC-005, 009, 024, 025, 030, 031

---

## Abstract

CRP Comply's compliance agent — an expert on the EU AI Act, ISO 42001, GDPR and other standards, grounded in an official regulatory corpus and citing specific articles — is the first instance of a pattern far bigger than Comply. It fills a genuine, unsolved gap in agentic AI: **trustworthy domain-expert agents whose authority is provable.** Today, asking any LLM an expert domain question ("what does Article 9 require?", "what is the contraindication for this drug?", "what does our internal policy say about X?") returns a plausible answer that may be hallucinated — catastrophic in high-stakes domains. This document specifies the **Authoritative Domain Agent (ADA)**: a CRP-governed agent bound to an authoritative, official corpus, *guaranteed by the protocol to speak only from that corpus*, with provenance on every claim and a refusal to answer beyond what the corpus supports. The ADA is the inverse of a general chatbot: where a chatbot answers everything plausibly, an ADA answers only what it can ground in its authoritative source, and proves it. This is a reusable product pattern — compliance is the first vertical; law, medicine, standards, internal policy, and any domain with an official body of truth are the rest.

---

## 1. The Gap in Agentic AI

### 1.1 The Problem With Expert LLM Answers

A general LLM asked an expert question produces fluent, confident, authoritative-*sounding* output. In low-stakes domains this is fine. In high-stakes domains — regulation, law, medicine, safety standards, financial rules — it is dangerous: the answer *might* be a hallucinated regulation, a misremembered statute, a plausible-but-wrong dosage. The user cannot tell the difference between a grounded answer and a confident fabrication. There is no proof of authority.

### 1.2 Why RAG Alone Does Not Solve It

Retrieval-augmented generation retrieves relevant documents and lets the model answer "using" them. But standard RAG does not *guarantee* the answer stays within the retrieved authority — the model freely blends retrieved text with its parametric knowledge, and nothing verifies that each claim is actually grounded in the official source versus invented. RAG improves grounding; it does not prove it or enforce it.

### 1.3 What's Actually Needed

An agent that:
1. Is **bound** to an authoritative, official corpus (the real EU AI Act text, the actual ISO standard, the genuine clinical guideline).
2. **Only speaks from it** — every claim verified-grounded in the corpus, enforced, not hoped.
3. **Cites** the specific source for every claim (article, clause, page).
4. **Refuses** to answer beyond what the corpus supports, rather than fabricating.
5. **Proves** its authority — the grounding is auditable, not asserted.

This is the Authoritative Domain Agent. CRP makes it possible because CRP already verifies grounding (DPE), enforces it (Safety Policy), and proves it (provenance chain).

---

## 2. The ADA Pattern

### 2.1 The Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  AUTHORITATIVE CORPUS (official, versioned, immutable)       │
│    the real regulation / standard / guideline / policy text  │
│    ingested into a dedicated CKF (SPEC-009)                  │
├─────────────────────────────────────────────────────────────┤
│  ADA GROUNDING ENFORCEMENT (CRP)                             │
│    - CDR/CDGR retrieve the relevant authoritative passages   │
│    - STL positions the model: "answer ONLY from this"        │
│    - DPE verifies EVERY claim is corpus-grounded             │
│    - Safety Policy: block-ungrounded (no parametric answers) │
│    - claims that can't be grounded → REFUSE, don't fabricate │
├─────────────────────────────────────────────────────────────┤
│  PROVABLE OUTPUT                                             │
│    every claim cited to its corpus source + grounding score  │
│    + provenance hash → auditable proof of authority          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 The Defining Rule: Grounded or Refuse

The ADA's hard rule, enforced by Safety Policy (SPEC-006) with `block-ungrounded`:

> Every claim the ADA makes MUST be grounded in the authoritative corpus. A claim that cannot be grounded is NOT made — the ADA states what the corpus does and does not cover, rather than filling the gap with parametric knowledge.

This is the inverse of normal LLM behaviour. A general LLM fills gaps with plausible content. An ADA leaves gaps explicit: "The corpus does not address X" is a valid, valuable ADA answer — and the trustworthy one.

### 2.3 How CRP Enforces It (not just prompts it)

The distinction from "just prompt the model to stay grounded": CRP *verifies and enforces*:
- DPE Stage 2 (attribution) classifies every claim as CORPUS_GROUNDED or not.
- Claims not grounded in the corpus are flagged PARAMETRIC/UNVERIFIABLE.
- Safety Policy `block-ungrounded` halts or strips ungrounded claims before the answer is delivered.
- The delivered answer therefore contains *only* corpus-grounded claims, each cited — enforced by the protocol, not trusted to the model.

This is why the ADA needs CRP specifically: the grounding guarantee is a protocol-enforced property, not a prompt-engineering hope.

---

## 3. The Authority Guarantee — Provable, Not Asserted

### 3.1 Every Answer Is Auditable

Each ADA answer carries:
- The specific corpus citations for every claim (article/clause/section/page).
- A grounding score per claim (how strongly the corpus supports it).
- A provenance hash linking to the exact corpus version (SPEC-011).

An auditor, a regulator, or the user can verify: this answer came from this official source, version X, at these specific locations. The authority is *proven*, not claimed. A compliance officer can defend an ADA answer to a regulator because it is traceable to the official text.

### 3.2 Corpus Versioning

The authoritative corpus is versioned and immutable. When the EU AI Act is amended, a new corpus version is ingested; answers cite the version they were grounded in. An ADA answer is reproducible: "grounded in EU AI Act consolidated version 2026-01-15, Art. 9(2)(a)." This matters in domains where the authority changes over time and historical answers must remain verifiable against the text as it was.

---

## 4. ADA as a Reusable Product Pattern

### 4.1 Compliance Is the First Vertical, Not the Only One

CRP Comply's agent is the first ADA — bound to the regulatory corpus. The pattern generalises to any domain with an authoritative body of truth:

| Vertical | Authoritative corpus | The ADA answers |
|----------|---------------------|-----------------|
| **Compliance** (Comply, live) | EU AI Act, ISO 42001, GDPR, NIS2 | "what does Art. 9 require?" — cited |
| **Legal** | statutes, case law, contracts | "what does this clause mean?" — sourced |
| **Medical** | clinical guidelines, drug formularies | "what's the contraindication?" — referenced |
| **Standards** | technical standards (IEEE, ISO, IETF) | "what does the spec mandate?" — cited |
| **Internal policy** | company policies, runbooks | "what's our policy on X?" — grounded |
| **Financial** | regulations, internal controls | "is this permitted under MiFID?" — sourced |
| **Scientific** | peer-reviewed literature | "what does the evidence say?" — cited |

Each is the same pattern: an official corpus + CRP grounding enforcement + provable citations. Only the corpus changes.

### 4.2 The Product Offering

ADA can be offered as:
- **A capability of the Gateway** — "bind an agent to your corpus, get grounding enforcement" as a console pipeline (SPEC-043 §3).
- **A standalone product per vertical** — e.g. a legal-research ADA, a clinical-guideline ADA, sold to that vertical.
- **An enterprise feature** — "turn your internal knowledge into an authoritative agent that never invents policy."

The internal-policy vertical is especially broad: every enterprise has policies, runbooks, and documentation that employees ask about — and every enterprise fears an AI assistant inventing policy. An ADA bound to the company's actual documents, refusing to invent, is immediately valuable and broadly applicable.

### 4.3 Why This Is a Distinct Product, Not Just a Feature

The ADA is a distinct pattern because its *value proposition is inverted* from a general assistant. A general assistant is valued for answering broadly and helpfully. An ADA is valued for answering *narrowly and provably* — for refusing to go beyond its authority. This is a different product with a different promise ("trustworthy, not helpful-at-all-costs") for a different buyer (high-stakes domains where a wrong confident answer is a liability). It deserves its own positioning.

---

## 5. The Honest Boundary — What ADA Does and Doesn't Do

### 5.1 What It Guarantees

- Every delivered claim is grounded in the authoritative corpus (enforced).
- Every claim is cited to its source (provable).
- Ungrounded questions get "the corpus doesn't cover this," not fabrication.
- The authority is auditable against a specific corpus version.

### 5.2 What It Does Not Do

- **It does not interpret beyond the text.** An ADA grounds answers in the corpus; it does not provide legal/medical *judgment* that goes beyond what the source says. "What does Art. 9 require?" — yes. "Will I win my case?" — no; that is judgment beyond the corpus, and the ADA says so. This boundary is a feature: the ADA stays within provable authority and refers judgment to a qualified human (consistent with Comply's referral model, SPEC-040 §4.2).
- **It does not guarantee the corpus is correct or complete** — only that the answer faithfully reflects the corpus. If the official source is wrong, the ADA faithfully reflects a wrong source (and cites it, so the error is traceable).
- **It does not replace the professional.** The ADA is a provably-grounded research and drafting tool; the lawyer, doctor, or compliance officer remains the decision-maker. Checkpoints (SPEC-033) insert their judgment where it matters.

### 5.3 The Honest Novelty

The components (RAG, grounding checks, citation) exist. The ADA's contribution is the *enforced, provable, refuse-rather-than-fabricate* combination as a protocol-guaranteed pattern: grounding is not improved-on-average (RAG) but *enforced-per-claim* (CRP Safety Policy), and authority is not asserted but *proven* (CRP provenance). That enforcement-and-proof, applied to authoritative-corpus agents, is the genuine contribution — and it is only possible because CRP already provides per-claim grounding verification and provenance as protocol properties.

---

## 6. Headers

| Header | Meaning |
|--------|---------|
| `CRP-ADA-Corpus` | The authoritative corpus + version the answer is grounded in |
| `CRP-ADA-Grounding` | Fraction of the answer grounded in the corpus (must be 1.0 for delivery) |
| `CRP-ADA-Refused-Claims` | Count of claims the ADA refused to make (ungroundable) |
| `CRP-ADA-Citations` | Count of corpus citations in the answer |

`CRP-ADA-Grounding: 1.00` is the guarantee made visible: the entire answer is corpus-grounded. Anything less is not delivered as an authoritative answer.

---

## 7. Relationship to the Ecosystem

```
CRP PROTOCOL — provides per-claim grounding verification + provenance
        │
        ├─ enables the ADA pattern (this spec)
        │
        ├─ CRP COMPLY — the first ADA (regulatory corpus) + compliance platform
        ├─ CRP GATEWAY — can host ADAs as console pipelines (bind-your-corpus)
        └─ future vertical ADAs — legal, medical, standards, internal policy
```

The ADA is the pattern; Comply's agent is its first instance; the Gateway can offer it as a capability; and each vertical is a potential standalone product. It is the same dogfooding logic as CRP Scan: CRP's own properties (grounding, provenance) make a new product class possible.

---

## 8. References

- CRP-SPEC-005 — DPE (per-claim grounding verification)
- CRP-SPEC-006 — Safety Policy (block-ungrounded enforcement)
- CRP-SPEC-009 — CKF (the authoritative corpus store)
- CRP-SPEC-024/025 — CDR/CDGR (authoritative passage retrieval)
- CRP-SPEC-030/031 — CSO/STL (grounded interview state + positioning)
- CRP-SPEC-040 — CRP Comply (the first ADA instance)
- CRP-SPEC-043 — Gateway (can host ADAs as pipelines)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
