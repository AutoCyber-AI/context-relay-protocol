# CRP — Master Index (v4/v6 Complete)

**For:** Engineering team building CRP v4 and CRPv6
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Status:** 59 numbered specs (001–059) + supporting docs + LIVE Stripe objects
**Currency of this index:** supersedes all prior indexes (last full index was ~SPEC-017 era)

---

## HOW TO USE THIS REPO

1. **CRP-V4-UPGRADE-PROMPT.md** — START HERE. The v3→v4 upgrade plan: what to
   keep, change, add, and skip. The build bible.
2. **CRP-MASTER-INDEX.md** (this file) — the catalogue: what every doc is.
3. **CRP-SDK-REFERENCE.md** — the developer interface you implement.
4. **CRP-GATEWAY-BLUEPRINT.md** — how to build the hosted Gateway.
5. **CRP-ECOSYSTEM-BOUNDARIES.md** — who-does-what across Scan/Gateway/Comply.
6. Then the specs, in the order the upgrade prompt dictates.

---

## THE 48 SPECS — WHAT EACH PROVIDES

### CORE PROTOCOL (the always-on, millisecond, any-model engine)
| # | Spec | What it provides |
|---|------|------------------|
| 001 | Core Specification | the protocol axioms, the request/relay model |
| 002 | HTTP Header Vocabulary | all CRP-* headers (the wire contract) |
| 003 | Context Envelope | 3-phase packing, primacy-recency assembly |
| 004 | Continuation & DAG | window continuation — now relays the CSO (030) |
| 005 | Decision Provenance Engine | the 13-stage risk/grounding/attribution analysis |
| 006 | Safety Policy Language | the CSP-style policy + halt directives |
| 007 | Session Token | HKDF stateless state relay |
| 008 | Dispatch Strategy | the 9 dispatch strategies |
| 009 | Contextual Knowledge Fabric | the CKF: HNSW + graph + communities |
| 011 | Audit Trail & HMAC Chain | tamper-evident provenance log |
| 015 | Security & Privacy | injection shield, PII, threat model |
| 017 | Zero-CKF / Onboarding Mode | governance works before any setup |

### CONTEXT QUALITY (the v4 retrieval/relay core)
| # | Spec | What it provides |
|---|------|------------------|
| 024 | **CDR** | Coverage-Differential Retrieval — quality at any length. THE core fix |
| 025 | **CDGR** | graph retrieval — multi-hop, connector facts |
| 027 | Retrieval Integrity | parallel coverage isolation, fact authority, recency |
| 030 | **CSO** | Cognitive State Object — what CRP actually relays (state, not text) |

### POSITIONING LAYER (the keystone — context OUT of the LLM)
| # | Spec | What it provides |
|---|------|------------------|
| 028 | Multi-Horizon Context | persistent / conversational / ephemeral tiers + intent |
| 029 | Ephemeral & Tool Context | scratch buffer, tool-output provenance, freshness |
| 031 | **STL** | Semantic Task Layer — positioning not injection, role separation |
| 035 | Context Lifecycle & Access | the 5-primitive storage engine + access router |
| 038 | Pluggable Storage Backends | bring-your-own-store, locations, visibility |

### SAFETY & GOVERNANCE
| # | Spec | What it provides |
|---|------|------------------|
| 010 | Regulatory Mapping | EU AI Act / GDPR / ISO 42001 / NIST control mapping |
| 012 | Multi-Agent Safety | safety budget, circuit breaker across agents |
| 033 | Safety Control Plane | visible/tunable/extensible safety + the Checkpoint primitive |
| 034 | Safety Coverage + Checkpoint Lifecycle | the coverage map + approve/reject/edit/timeout |

### DEVELOPER EXPERIENCE & CONFIG
| # | Spec | What it provides |
|---|------|------------------|
| 032 | Developer Experience | the progressive-disclosure SDK (Level 0–3) |
| 037 | Unified Config | one optional crp.config.yaml governs everything |

### VALIDATION
| # | Spec | What it provides |
|---|------|------------------|
| 014 | Conformance | levels, test vectors, certification |
| 026 | **Semantic Quality Benchmark** | the binding proof: Factual F1 + judge score |

### OPT-IN AMPLIFICATION (OFF by default — for weak local models, async)
| # | Spec | What it provides |
|---|------|------------------|
| 023 | **Amplification Boundary** | READ FIRST — defines what must never be default |
| 018 | AIR | closed-loop feedback / error quarantine |
| 019 | CQR | the 6 cognitive failure modes (detection stays in Core) |
| 020 | CLD | cognitive load distribution (working memory = the CSO) |
| 021 | ROS | reasoning orchestration / self-consistency |
| 022 | PEF | parallel execution fabric (makes 020/021 fast) |

### PRODUCTS — CRP SCAN (FIND)
| # | Spec | What it provides |
|---|------|------------------|
| 013 | crp-scan GitHub Action | detection patterns, SARIF, the funnel |
| 036 | Scan Remediation Engine | code-fix PRs, config fixes, guided fixes |
| 039 | Semantic Code Ingestion | Scan uses CRP's own CKF to understand large repos |

### PRODUCTS — CRP GATEWAY (RUN)
| # | Spec | What it provides |
|---|------|------------------|
| 016 | Gateway as a Service | the service contract, tiers, onboarding |
| 043 | Gateway Runtime Product | the product framing + low-code/no-code visual console |

### PRODUCTS — CRP COMPLY (PROVE)
| # | Spec | What it provides |
|---|------|------------------|
| 040 | CRP Comply | the 3-layer compliance platform (Programme/Artefacts/Evidence) — aligned to LIVE product |
| 042 | Comply Upgrade & Integration | v2→v4 migration: Gateway swap, safety layer, Scan connect, agent v4 |
| 048 | No-Code Governance + GitHub + Signup | Scan-driven no-code governance, secure GitHub, result-preserving signup |

### NEW PRODUCT PATTERNS & FRONTIERS
| # | Spec | What it provides |
|---|------|------------------|
| 044 | Authoritative Domain Agent | provably-grounded expert agents bound to an official corpus |
| 045 | Knowledge Learning | external learned knowledge that feels innate (honest weight boundary) |
| 046 | User-Defined Cognition | compile plain-language thinking processes into reasoning patterns |

### GO-TO-MARKET
| # | Spec | What it provides |
|---|------|------------------|
| 041 | Adoption & Ecosystem | framework adapters, onboarding, templates, conversion |
| 047 | Monetisation & Payments | LIVE Stripe objects + Clerk linkage + entitlement code |

### CRPv6 AGENTIC LAYER
| # | Spec | Status | What it provides |
|---|------|--------|------------------|
| 049 | Verification Relay | Implemented (symbolic + PRM advisory) | step-level reasoning verification and LLM-Modulo repair |
| 050 | Quality-Tier-Supervised Router | Implemented (fallback); learned model roadmap | capability-aware dispatch with escalation ladder |
| 051 | Predictive Positioning | Roadmap (Wave 3) | world-model induction and simulation-before-action |
| 052 | Intent & Speech-Act Positioning | Implemented | pragmatic interpretation and cross-session coreference |
| 053 | Clarification Protocol | Implemented (basic); deep disambiguation roadmap | ambiguity as a first-class protocol primitive |
| 054 | Structured Decoding | Implemented | token-level grammar constraints for valid tool calls |
| 055 | Epistemic Profiles | Roadmap (entropy only) | per-model, per-task calibration and uncertainty |
| 056 | Transparency Emission Layer | Implemented (D1–D3); D4–D6 roadmap | streaming governance evidence as AG-UI events |
| 057 | Bi-Temporal CKF | Implemented | event-time vs ingestion-time fact validity |
| 058 | Governed Delegation | Roadmap (preview) | policy envelope, audit chain, and verification across agent boundaries |
| 059 | Agent Capability Layer | Implemented | typed tool manifest, intent-compiler, result envelope, `crp.Agent` SDK |

---

## SUPPORTING DOCUMENTS (top level)

| Doc | What it provides |
|-----|------------------|
| **CRP-V4-UPGRADE-PROMPT.md** | the v3→v4 build plan — keep/change/add/skip (START HERE) |
| CRP-MASTER-INDEX.md | this catalogue |
| CRP-SDK-REFERENCE.md | the complete developer interface (the "steering wheel") |
| CRP-GATEWAY-BLUEPRINT.md | how to build the Gateway (22-step lifecycle, components) |
| CRP-ECOSYSTEM-BOUNDARIES.md | Scan=FIND, Gateway=RUN, Comply=PROVE, ADA=TRUST |
| CRP-MARKET-STRATEGY.md | low-code market, Gateway repositioning, completeness assurance |
| CRP-STRIPE-SETUP-GUIDE.md | all 12 live payment links + IDs + dashboard config |
| CRP-GITHUB-APP-GUIDE.md | implement the secure GitHub App connection |
| CRP-BUILD-PROMPT.md | earlier tiered build plan (superseded by V4-UPGRADE-PROMPT for the upgrade) |
| CRP-CODER-BRIEF.md | earlier CDR-centric brief |
| autocyberai-github-profile-README.md | the company GitHub org profile |

---

## THE 12 NON-NEGOTIABLE INVARIANTS (never violate)

1. Core path < 50ms overhead. No extra inference in Core.
2. Model-agnostic — identical governance on any model.
3. Axiom 4 — strip all CRP-* headers before the provider.
4. Positioning not injection (STL) — build frames up, don't trim down.
5. Embedding consistency across CKF / Coverage / Turn-Log.
6. CSO preservation verified — no silent state loss.
7. HMAC chain unbroken.
8. Amplification opt-in, off by default, async only.
9. Right storage primitive per access (router), not everything through vectors.
10. Checkpoints never leave the end user with a raw error.
11. Remediations are always proposals (PRs), never auto-commits.
12. Config optional and provenanced (CRP-Config-Hash).

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
