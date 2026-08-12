# CRP-SPEC-043: The Gateway as Runtime Product & The Visual Console

**Document:** CRP-SPEC-043  
**Title:** Context Relay Protocol (CRP) — CRP Gateway as the Full Runtime Product: Subscription Service, Complete Capability Access, and the Low-Code/No-Code Console  
**Version:** 1.0.0  
**Status:** Foundational — Product Definition  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Extends:** CRP-SPEC-016 (Gateway service contract)  
**Prerequisites:** CRP-SPEC-016, 031, 032, 037, 040

---

## Abstract

SPEC-016 specifies the Gateway as a service contract; the Gateway Blueprint specifies its internals. Neither defines it as a *product* with a clear purpose, customer, and the full-capability surface it must expose. This document does. The CRP Gateway is **the runtime product**: a managed, hosted subscription service where a customer points their application at the Gateway and receives, on every LLM call, full CRP governance (safety, provenance, compliance signals) plus the complete context-management capability suite (CDR, CDGR, CSO, STL, knowledge, sessions, tools) — accessed both through the API and, critically, through a **low-code/no-code visual console** that lets non-developers and developers alike configure and operate governed AI pipelines without writing code. The Gateway answers one question: *how do I run governed, context-managed AI in production, without building any of it myself?* This specification defines its purpose, its boundary against CRP Comply and CRP Scan, its full capability surface, the visual console that is currently missing, and its subscription model.

---

## 1. What the Gateway Is — Purpose and Boundary

### 1.1 The One-Sentence Purpose

> The Gateway is the managed runtime: point your application at it and every AI call is governed and context-managed, configurable by API or visual console, on a rolling subscription — so you never build context management, safety, or compliance instrumentation yourself.

### 1.2 The Clean Boundary (Gateway vs Comply vs Scan)

The three products form one pipeline with no overlap:

```
┌────────────────────────────────────────────────────────────────┐
│  CRP SCAN — "FIND"                                              │
│  Discovers ungoverned AI calls in your codebase.               │
│  Routes findings + remediations onward.                        │
├────────────────────────────────────────────────────────────────┤
│  CRP GATEWAY — "RUN"   ◀── THIS DOCUMENT                       │
│  The runtime. Governs every call. Provides the full context    │
│  capability suite. API + visual console. Rolling subscription.  │
│  Produces the tamper-evident runtime evidence.                 │
├────────────────────────────────────────────────────────────────┤
│  CRP COMPLY — "PROVE"                                          │
│  Consumes the Gateway's runtime evidence. Adds artefacts +      │
│  the expert agent. Produces audit-ready deliverables & packs.   │
│  NOT a runtime — it proves what the runtime did.               │
└────────────────────────────────────────────────────────────────┘

The remediation CRP Scan recommends and CRP Comply tracks IS:
"route this call through the Gateway." The Gateway is the fix.
The Gateway's output is the evidence Comply packages.
```

This boundary resolves the blur: **the Gateway is the only runtime.** Comply does not run a parallel proxy (SPEC-042 retires it); Comply consumes the Gateway. Scan finds what isn't yet on the Gateway. One runtime, one compliance layer, one scanner.

### 1.3 Who Buys It

| Customer | Why |
|----------|-----|
| Developers shipping AI features | governance + quality without building it |
| Companies running AI in production | managed, compliant, no infra |
| Teams with weak/local models | the context capability that lifts output quality |
| Non-technical AI builders | the visual console — governed AI without code |

---

## 2. The Full Capability Surface

The Gateway must expose CRP's *entire* capability suite, not just governance. This is what "all their LLM calls governed but also have at their disposal the various context strategies" means.

### 2.1 Governance (always on)

Every call, automatically: DPE risk scoring (SPEC-005), Safety Policy enforcement + halt (SPEC-006), HMAC provenance chain (SPEC-011), compliance classification (SPEC-010), all emitted as headers (SPEC-002). This is the baseline — the reason to route through the Gateway at all.

### 2.2 Context Capability (at the customer's disposal)

The full context-management suite, available on demand:

| Capability | Spec | What the customer gets |
|-----------|------|----------------------|
| Knowledge (CKF) | 009 | ingest documents → grounded answers |
| Coverage-Differential Retrieval | 024 | quality that holds at any output length |
| Graph retrieval (CDGR) | 025 | multi-hop, connector-aware grounding |
| Cognitive State relay (CSO) | 030 | coherent long/multi-step work |
| Semantic Task Layer (STL) | 031 | positioning — focused, token-efficient |
| Multi-horizon context | 028 | conversation + document + tool context |
| Tool/agentic support | 029 | governed tool use, tool provenance |
| Storage backends | 038 | bring-your-own-store, locatable, sovereign |

### 2.3 Safety Control (self-service)

The Safety Control Plane (SPEC-033): tune grounding, halt levels, PII handling, add custom rules, define checkpoints — visually, no code. Shared with Comply (same control plane, same config, SPEC-037).

### 2.4 Amplification (opt-in)

For weak/local models on async tasks: AIR/CQR/CLD/ROS via PEF (SPEC-018–022), governed by the opt-in boundary (SPEC-023). Off by default; available when wanted.

---

## 3. The Visual Console — Low-Code/No-Code (the missing surface)

### 3.1 Why This Is the Key Missing Piece

The Gateway today is API-only. The customer's stated need: *"the various context strategies via an API or even better something graphical / low-code-no-code."* A visual console turns the Gateway from a developer tool into a product anyone can operate — and it is the single biggest expansion of the Gateway's addressable market.

### 3.2 What the Console Provides

```
┌─ CRP GATEWAY CONSOLE ─────────────────────────────────────────┐
│  Pipelines   Knowledge   Safety   Playground   Analytics      │
│                                                                │
│  ┌─ BUILD A GOVERNED AI PIPELINE (no code) ─────────────────┐ │
│  │                                                           │ │
│  │  [Input] → [Knowledge: my-docs ▾] → [Depth: thorough ▾]  │ │
│  │          → [Safety: strict ▾] → [Checkpoint: >$1M ▾]      │ │
│  │          → [Model: gpt-4o ▾] → [Output]                   │ │
│  │                                                           │ │
│  │  Drag blocks to compose. Each block is a CRP capability. │ │
│  │  [ Test ]  [ Deploy as endpoint ]  [ Export as code ]    │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 3.3 Console Surfaces

| Surface | What it does (no code) |
|---------|----------------------|
| **Pipelines** | visually compose governed AI flows — drag capability blocks (knowledge, depth, safety, checkpoints, tools, model), connect them, deploy as a live endpoint |
| **Knowledge** | upload/manage documents, see the CKF, browse what the AI knows, set storage location (SPEC-038) |
| **Safety** | the visual Safety Control Plane (SPEC-033) — sliders, toggles, checkpoint builder |
| **Playground** | test prompts against the configured pipeline, see governance signals live (risk, grounding, sources) |
| **Analytics** | the observability dashboard — calls, quality trends, fabrications caught, token savings, cost |

### 3.4 The Three Operating Modes

The console serves all skill levels:
- **No-code:** compose pipelines visually, deploy endpoints, never see code.
- **Low-code:** visual composition + small custom expressions (a checkpoint condition, a custom rule).
- **Code:** "Export as code" generates the SDK/config (SPEC-032/037) for developers who want to take the visual pipeline into their codebase. The console and code are the same underlying config (SPEC-037) — visual edits and code edits are interchangeable.

### 3.5 Deploy-as-Endpoint

A pipeline built in the console deploys as a live, governed API endpoint the customer's app calls — the visual flow becomes production infrastructure. This is the no-code payoff: build a governed AI pipeline by dragging blocks, click deploy, get a production endpoint, no code written.

---

## 4. The Subscription Model

Rolling subscription, usage-based, distinct from Comply's compliance tiers:

| Tier | For | Includes |
|------|-----|----------|
| **Free** | trial, hobby | governance on N calls/mo, basic console, community |
| **Developer** | individual devs | higher quota, full context suite, API + console, code export |
| **Team** | scale-ups | shared pipelines, more knowledge, analytics, SSO |
| **Business/Enterprise** | production at scale | high volume, data residency, dedicated capacity, SLAs, on-prem option |

The Gateway monetises *runtime* (calls governed, capability used). Comply monetises *compliance* (deliverables, evidence, audit-readiness). A customer may subscribe to one or both: the Gateway to run governed AI, Comply to prove it. They compose but are sold separately.

---

## 5. The Relationship to Comply and Scan (operational)

### 5.1 Gateway → Comply (evidence flow)

A Gateway customer who also needs compliance connects their Gateway to Comply. The Gateway's runtime evidence (the HMAC audit chain, risk scores, checkpoint resolutions) streams into Comply's Layer 3 (SPEC-040 §5, SPEC-042). The customer runs on the Gateway; Comply turns that runtime into audit-ready evidence. No duplicate instrumentation.

### 5.2 Scan → Gateway (the remediation target)

When CRP Scan finds an ungoverned call, the remediation (SPEC-036) is "route it through the Gateway" — the diff swaps the base_url to the Gateway endpoint. The Gateway is literally the fix Scan recommends. Scan finds; the Gateway governs; Comply proves.

### 5.3 One Config Across All Three

The unified config (SPEC-037) is shared: the safety settings a customer sets in the Gateway console are the same settings Comply reads for evidence and Scan checks against. One source of truth across the ecosystem.

---

## 6. Honest Status & Limits

The Gateway's runtime (SPEC-016 + Blueprint) is the foundation; this document adds the product framing and the visual console. The console is substantial frontend engineering — a visual pipeline builder, knowledge manager, safety UI, playground, and analytics. It should be built after the runtime is solid, starting with the playground (test a configured pipeline) and the safety UI (the highest-value no-code surfaces), then the full pipeline builder.

The no-code pipeline builder must compile to the same config/SDK as code (SPEC-037) — if the visual and code paths diverge, the "export as code" promise breaks. This is an engineering discipline requirement: one config model, two editing surfaces.

"Deploy as endpoint" means the Gateway hosts customer-defined pipelines — a multi-tenant execution concern (isolation, quota, abuse prevention) that the Gateway architecture (Blueprint §2) must enforce per deployed pipeline.

The boundary with Comply must be held: the Gateway is the runtime, Comply consumes it. If Comply is allowed to keep its own parallel runtime, the blur returns. SPEC-042's retirement of the bespoke proxy is a prerequisite for this clean separation.

---

## 7. References

- CRP-SPEC-016 — Gateway Service (the contract this productises)
- CRP-SPEC-031 — STL (a console capability block)
- CRP-SPEC-032 — Developer Experience (code export target)
- CRP-SPEC-033 — Safety Control Plane (the console Safety surface)
- CRP-SPEC-037 — Unified Config (the shared source of truth)
- CRP-SPEC-040/042 — Comply (the compliance consumer of Gateway evidence)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
