# CRP-SPEC-042: CRP Comply v2→v4 Upgrade & Ecosystem Integration

**Document:** CRP-SPEC-042  
**Title:** Context Relay Protocol (CRP) — CRP Comply Upgrade & Integration: Migrating from the v2 Audit-Only Proxy to the v4 Gateway, Full Safety Layer, and Native CRP Scan Connection  
**Version:** 1.0.0  
**Status:** Foundational — The Migration Architecture  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Supersedes operationally:** the Comply 0.1.0 bespoke proxy  
**Prerequisites:** CRP-SPEC-016, 005, 006, 033, 034, 036, 039, 040

---

## Abstract

The deployed CRP Comply (0.1.0, on CRP 3.1.1) has a structural problem: it reimplements pieces of CRP in parallel, weakly. Its proxy is a near-non-existent, untested OpenAI passthrough that logs HMAC-signed audit records but performs **no AI safety governance** — no DPE risk gating, no Safety Policy enforcement, no halt, no checkpoints. It is not connected to CRP Scan. And it uses an early version of the protocol as little more than an audit-header wrapper rather than the full governance-and-positioning protocol CRP has become. This specification defines the upgrade: **consolidation, not parallel reimplementation.** Comply's bespoke proxy is replaced by the CRP Gateway (SPEC-016) as its execution layer; the audit-only pipeline gains the full safety stack (DPE, Safety Policy, halt, the Safety Control Plane, and the Checkpoint inbox); the agent's regulatory-corpus retrieval is upgraded to CRP v4 (CDR/CDGR/CSO); and a new, convenient **Connect Repo** surface wires CRP Scan directly into Comply so that ungoverned-AI findings and their remediations flow natively into the compliance programme and the Inbox. The result: Comply stops being a weak parallel implementation and becomes the visual, self-service management plane over properly-deployed CRP infrastructure — with safety, scan, and compliance unified.

---

## 1. The Current-State Problem (Honest Diagnosis)

| Component | Current state (Comply 0.1.0) | Problem |
|-----------|------------------------------|---------|
| Proxy | Bespoke OpenAI passthrough + HMAC audit | Near-non-existent, untested; duplicates the Gateway badly |
| Safety | Audit logging only | **No governance** — does not risk-gate, halt, or check anything |
| Protocol use | Audit headers (X-CRP-Comply-*) | Uses CRP as a logging wrapper, not the full protocol |
| Scan | Not connected | The scan→comply loop the funnel depends on does not exist |
| Agent retrieval | Basic corpus query | Not using CRP v4 retrieval (CDR/CDGR) — suboptimal grounding |
| Version | CRP 3.1.1 (v2-era) | Behind the v4 architecture (CDR/CDGR/CSO/STL/safety) |

The throughline: **Comply built parallel, weaker versions of capabilities CRP already specifies properly.** The fix is not to improve the parallel implementations — it is to replace them with the real CRP infrastructure and make Comply the management surface over it.

---

## 2. The Consolidation Principle

```
BEFORE (parallel, weak):                AFTER (consolidated, correct):

Comply bespoke proxy ──┐                Comply UI ──── manages ────┐
   (audit only)        │                                          ▼
                       │                              ┌─ CRP GATEWAY (SPEC-016) ─┐
Comply audit log ──────┤                              │  full execution layer:   │
                       │                              │  DPE + Safety Policy +    │
Comply agent ──────────┤                              │  halt + checkpoints +     │
   (basic retrieval)   │                              │  CDR/CDGR + audit chain   │
                       │                              └───────────┬───────────────┘
(no scan connection)   │                                          │
                       ▼                              ┌───────────▼───────────────┐
   weak, partial CRP                                  │  CRP SCAN (013/036/039)   │
                                                      │  connected via Connect    │
                                                      │  Repo → Inbox remediations │
                                                      └────────────────────────────┘
```

Comply becomes the **visual, self-service management plane**. The execution is the Gateway. The detection is Scan. The intelligence is CRP v4. Comply orchestrates and presents — it no longer reimplements.

---

## 3. Upgrade 1 — Replace the Proxy With the Gateway

### 3.1 The Change

The Comply bespoke proxy is retired. Comply's Layer 3 evidence substrate becomes a **deployment/tenant of the CRP Gateway** (SPEC-016). The customer-facing endpoint (`comply.crprotocol.io/v1`) remains — preserving the existing drop-in integration snippets — but behind it runs the full Gateway request lifecycle (SPEC-016 / Gateway Blueprint), not a passthrough.

### 3.2 What This Gains Immediately

By routing through the Gateway, every inference that Comply governs now gets the full 22-step lifecycle (Gateway Blueprint §1): authentication, Safety Policy resolution, DPE 13-stage analysis, halt enforcement, CSO state, HMAC chain, and header emission — instead of just an audit log. The same endpoint the customer already uses suddenly does real governance.

### 3.3 Backward Compatibility

The existing integration (OpenAI base_url swap, the `X-CRP-Comply-*` headers) is preserved as the public contract. The headers are extended to the full CRP set (the `X-CRP-Comply-*` aliases map to the standard `CRP-*` headers, SPEC-002). Existing customers' code keeps working; it simply gains governance it did not have before. No breaking change to the wire contract.

### 3.4 The Two Deployment Modes Unify

Comply's "BYOK local / BYOK commercial / hosted" LLM model (SPEC-040 §7) maps directly onto the Gateway's provider routing + key vault (SPEC-016 §10). The Gateway already does exactly what Comply's LLM-provider settings describe — so this consolidates rather than conflicts. One key-management system, the Gateway's, surfaced through Comply's settings UI.

---

## 4. Upgrade 2 — Add the Full AI Safety Layer

### 4.1 From Audit-Only to Governed

The most serious current gap: Comply **audits but does not govern.** It records what happened; it does not prevent bad outcomes. The upgrade adds the complete safety stack to Comply's runtime (all already specified, now actually wired in):

| Capability | Spec | What Comply gains |
|-----------|------|-------------------|
| DPE risk scoring | 005 | every governed call risk-classified, not just logged |
| Safety Policy enforcement | 006 | halt-on-CRITICAL, require-grounding, block-fabrication |
| HTTP 451 halt | 002 | unsafe output stopped before it reaches the end user |
| Safety Control Plane | 033 | the visual safety settings surface (§6) |
| Checkpoints + Inbox | 033/034 | inline human-in-the-loop → the existing Inbox surface |
| Addable rules | 034 §11 | jailbreak, toxicity, secret-leakage, etc. |

### 4.2 The Safety Control Plane Lives in Settings

The live product already has a Settings surface with `CRP agent dispatch mode` and audit-trail controls. The Safety Control Plane (SPEC-033) extends this into the full visual registry: grounding slider, halt-level dropdown, PII handling, the addable-rule toggles, and checkpoint definitions — all self-service, no code (SPEC-040 §9). A compliance officer tightens governance from the dashboard.

### 4.3 Checkpoints Populate the Existing Inbox

The live product already has an **Inbox** surface that is currently empty. It becomes the Checkpoint inbox (SPEC-034): when a customer's governed system fires a checkpoint, it lands in the Comply Inbox for human resolution, producing the Art. 14 human-oversight evidence that slots directly into Layer 3. The surface exists; this fills it with its purpose.

### 4.4 Safety Evidence Feeds Compliance

The new safety signals are not just protective — they are **compliance evidence**. DPE risk scores feed Art. 9 risk management; halt events feed Art. 15 robustness; checkpoint resolutions feed Art. 14 human oversight; PII detections feed GDPR Art. 30/35. The safety layer Comply was missing is precisely the operational evidence its Layer 3 promised. Adding safety closes the gap between what Comply claims (compliance) and what it produced (audit logs).

---

## 5. Upgrade 3 — Native CRP Scan Connection (the "Connect Repo" surface)

### 5.1 The Convenient New Surface

A new, prominent **Connect Repo** page — the convenient, self-service scan integration the funnel needs. The flow:

```
┌─ CONNECT YOUR CODE ───────────────────────────────────────────┐
│  Find ungoverned AI in your codebase and fix it.              │
│                                                                │
│  ┌──────────────────────┐   ┌───────────────────────────────┐│
│  │  Connect GitHub      │   │  Paste scan results            ││
│  │  [ Authorise GitHub ]│   │  (from the crp-scan Action)    ││
│  │  → pick repos        │   │  [ paste SARIF / upload ]      ││
│  └──────────────────────┘   └───────────────────────────────┘│
│                                                                │
│  We scan with CRP's own semantic engine (SPEC-039), find      │
│  every ungoverned AI call, and turn each into a fix you can   │
│  apply — code PRs and config remediations, in your Inbox.     │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Two Connection Paths

- **Connect GitHub (deepest):** OAuth to GitHub, select repositories. Comply runs CRP Scan (SPEC-013/039) — semantic codebase ingestion via the code-CKF, multi-hop CDGR tracing — against the connected repos, on demand and on each push.
- **Paste/upload scan results (lightest):** a developer who already runs the `crp-scan` GitHub Action pastes or uploads its SARIF output. Comply ingests the findings without needing repo access.

### 5.3 What Connection Produces

Once connected, scan findings flow natively into Comply:

```
Scan findings → Comply, three destinations:

1. INBOX (remediations, SPEC-036):
   - code fixes → one-click "Open PR" (governed-client diffs)
   - config fixes → one-click "Apply in Control Plane"

2. PROGRAMME / EVIDENCE (Layer 2/3):
   - "ungoverned AI calls" becomes a tracked compliance finding
   - governing them produces the Art. 12 logging evidence
   - the scan result itself is dated evidence of due diligence

3. COMPLIANCE SCORE:
   - ungoverned calls lower the score; remediating raises it
   - makes the scan→fix→prove loop visible and motivating
```

### 5.4 The Loop the Funnel Always Needed

This closes the funnel SPEC-036 designed but Comply never implemented: **discover (Scan finds ungoverned AI) → connect (Connect Repo) → remediate (Inbox PRs/config) → prove (governed calls become Layer 3 evidence) → score rises.** It is the single most convenient on-ramp: a developer connects a repo and immediately sees what's ungoverned and how to fix it, with the fixes one click away.

---

## 6. Upgrade 4 — The Agent on CRP v4 Retrieval

### 6.1 The Regulatory Corpus Is the Perfect CKF Use Case

Comply's agent retrieves from a regulatory corpus (EU AI Act, GDPR, ISO 42001, NIS2, OECD). This is precisely what CRP v4's CKF + CDR/CDGR (SPEC-009/024/025) are built for. Upgrading the agent's retrieval to v4:

- **CDR (SPEC-024):** no repetition across a long deliverable; each section gets fresh, relevant regulatory material.
- **CDGR (SPEC-025):** multi-hop retrieval connects related articles — e.g. tracing how AI Act Art. 9 risk management connects to Art. 15 robustness and ISO 42001 Clause 6.1.2, surfacing the connective regulatory tissue a flat query misses.
- **CSO (SPEC-030):** the agent's interview state (what the customer has told it, what artefacts exist) carried as verified cognitive state, not a lossy summary — so a long compliance interview stays coherent.
- **STL (SPEC-031):** the agent positions the model on one focused compliance operation at a time (classify risk → retrieve articles → draft section → cite), rather than dumping the whole corpus into context.

### 6.2 Comply as a Live CRP Showcase

This makes Comply the flagship demonstration of CRP v4: the agent producing article-cited, provenance-tracked, non-repetitive, multi-hop-grounded compliance deliverables *is* CRP's context-management thesis proven on a hard, high-stakes domain. The product sells the protocol.

---

## 7. Upgrade 5 — Visual, Self-Service Governance

### 7.1 The Principle

Every capability surfaced visually, self-service, no code required for the common path. The compliance officer and developer manage everything from the dashboard:

| Capability | Visual surface |
|-----------|----------------|
| Safety settings | Control Plane in Settings (sliders, dropdowns, toggles) |
| Human oversight | Checkpoint Inbox (approve/reject/edit cards) |
| Scan & fix | Connect Repo + remediation Inbox (one-click PRs) |
| Compliance posture | Dashboard score (per-regulation %) |
| Evidence | Evidence dashboard (HMAC records) + one-click pack export |
| Deliverables | Recipe library + agent, promote-to-Vault |
| Artefacts | Artefact Room (draft/upload/refer) |

### 7.2 One-Click Flows

The self-service ethos: connect a repo (one OAuth), apply a remediation (one click → PR), generate a deliverable (pick recipe → answer → sign), export evidence (one button → article-mapped zip), tighten safety (one slider). No YAML, no code, for the management path — the unified config (SPEC-037) is written *by* the dashboard, not hand-edited by the compliance user.

---

## 8. The Migration Plan (v2 → v4)

A phased, non-breaking migration:

```
Phase 1 — Gateway swap (invisible to customers):
  Route comply.crprotocol.io/v1 through the CRP Gateway instead of the
  bespoke proxy. Preserve the X-CRP-Comply-* header contract. Existing
  customers gain real governance with zero code change.

Phase 2 — Safety layer activation:
  Turn on DPE risk scoring, Safety Policy (default balanced), halt. Surface
  the Safety Control Plane in Settings. Populate the Inbox with checkpoints.

Phase 3 — Scan connection:
  Ship the Connect Repo page (GitHub OAuth + SARIF paste). Wire findings to
  the Inbox (remediations), Programme (evidence), and score.

Phase 4 — Agent v4 retrieval:
  Migrate the agent's corpus retrieval to CDR/CDGR/CSO/STL. Re-index the
  regulatory corpus into a v4 CKF with consistent embeddings (SPEC-027 §2.5).

Phase 5 — Polish self-service:
  One-click flows, visual control plane, evidence-pack article mapping.
```

Phase 1 alone transforms the product from audit-only to governed without any customer-visible breakage — it should ship first.

---

## 9. Data Migration & Versioning

The existing Comply data (deliverables in Vaults, audit records) is preserved. The v2 audit records remain valid (HMAC chains verify regardless of protocol version). New records use the v4 chain. The regulatory corpus is re-embedded into a v4 CKF (a one-time re-index; embedding-model consistency enforced, SPEC-027 §2.5). Customer profiles and deliverable states carry forward unchanged. The migration is additive — nothing existing is lost.

---

## 10. Honest Status & Limits

This is a substantial migration of a live product — the largest single engineering effort in the ecosystem. It must be phased (§8) and non-breaking; Phase 1 (Gateway swap) delivers the biggest correctness gain (audit-only → governed) and should be prioritised.

Replacing the bespoke proxy with the Gateway assumes the Gateway is built to the standard of SPEC-016 / the Gateway Blueprint. If the Gateway is not yet production-ready, the interim step is to add the safety layer (DPE, Safety Policy, halt) to the existing proxy as a stopgap while the Gateway is completed — but the end state is the Gateway, not a permanently-improved bespoke proxy. Do not invest in making the parallel proxy good; invest in the Gateway and migrate.

The Scan connection depends on CRP Scan and semantic ingestion (SPEC-039) being built. The lightweight path (paste SARIF from the GitHub Action) can ship before the deep GitHub-OAuth integration, giving an early version of the loop.

The agent v4 retrieval upgrade requires re-indexing the corpus and validating (SPEC-026 SQB) that v4 retrieval genuinely improves deliverable quality over the current approach — measure, do not assume.

---

## 11. The End State

After this upgrade, CRP Comply is:
- **Governed, not just audited** — the full CRP safety stack on every call.
- **Built on the Gateway** — one proven execution layer, not a weak parallel proxy.
- **Connected to Scan** — a convenient Connect Repo surface turning ungoverned-AI findings into one-click fixes and compliance evidence.
- **Powered by CRP v4** — the agent's retrieval is the protocol's flagship showcase.
- **Visual and self-service** — every capability managed from the dashboard, no code for the common path.
- **Properly integrated** — Comply, Gateway, and Scan are one ecosystem sharing one protocol, not three disconnected tools.

Comply stops reimplementing CRP badly and becomes what it should be: the management and compliance plane over correctly-deployed CRP infrastructure.

---

## 12. References

- CRP-SPEC-016 — Gateway Service (replaces the bespoke proxy)
- CRP-SPEC-005/006 — DPE & Safety Policy (the missing governance)
- CRP-SPEC-033/034 — Safety Control Plane & Checkpoints (Settings + Inbox)
- CRP-SPEC-036/039 — Scan Remediation & Semantic Ingestion (Connect Repo)
- CRP-SPEC-024/025/030/031 — v4 retrieval & positioning (agent upgrade)
- CRP-SPEC-040 — CRP Comply (the product this upgrades)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
