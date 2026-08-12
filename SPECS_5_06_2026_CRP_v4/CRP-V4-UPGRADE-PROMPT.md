# CRP v3 → v4 — The Final Upgrade Prompt for Engineering

**For:** Lead Developer / Engineering Team
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Scope:** Upgrade the verified CRP v3 implementation to the full v4 architecture,
and upgrade the three products (Scan, Gateway, Comply) to match.

---

## 0. WHERE WE ARE (v3, verified)

CRP v3 is real and tested against a live local LLM:
- Governance works: HTTP 451 halt, HMAC audit chain, DPE, Safety Policy.
- CKF recall works. 1537 tests, 25 conformance vectors.
- Published on PyPI (`pip install crprotocol`, import `crp`).
- CRP Comply 0.1.0 is live on CRP 3.1.1 — but it's audit-only on a weak
  bespoke proxy, no real safety governance, not connected to Scan.

**v4 keeps everything that works and adds: the context-quality core (CDR/
CDGR/CSO), the positioning layer (STL), the storage engine, the full safety
control surface, and the product upgrades.**

---

## 1. THE ONE PRINCIPLE

> CRP Core is millisecond, any-model, governance-only, and imposes nothing.
> Everything expensive (amplification) is opt-in, off by default, async.

If a change would slow the Core path or require a specific model, it belongs
in opt-in Amplification (Tier 4), not Core. Never conflate them.

---

## 2. WHAT TO KEEP (v3 — don't rebuild)

These are verified; carry them forward unchanged except where a v4 spec amends them:
- SPEC-001 core model, SPEC-002 headers, SPEC-005 DPE, SPEC-006 Safety Policy,
  SPEC-007 session token, SPEC-009 CKF, SPEC-011 audit chain, SPEC-015 security,
  SPEC-017 zero-CKF.
- The HTTP 451 halt, the HMAC chain, the conformance vectors.
- The PyPI package shape (`crp`).

---

## 3. WHAT TO ADD (v4 — the new core, build in this order)

### TIER 1 — Context Quality + Storage + Safety Surface (build first, benchmark before moving on)

| Order | Spec | Build |
|-------|------|-------|
| 1 | SPEC-035 | the 5-primitive storage engine + access router (CKF graph, rolling log, hot cache, inverted index, pointer store). Build this FIRST — everything retrieves through it. |
| 2 | SPEC-038 | pluggable backends for each primitive + visibility API (client.storage.overview, knowledge.location). |
| 3 | SPEC-009 (amend) | add graph edges + communities to the CKF (needed for CDGR). |
| 4 | SPEC-024 | **CDR** — the novelty-weighted retrieval formula, exactly as in §7. The core quality fix. |
| 5 | SPEC-027 | retrieval integrity: recency, contradiction resolution, parallel coverage isolation. |
| 6 | SPEC-025 | **CDGR** — graph retrieval; seed with CDR, walk the graph, bridge-value scoring. |
| 7 | SPEC-030 | **CSO** — the Cognitive State Object; replaces text-summary continuation. Decisions-with-rationale, dependency graph, preservation verification. |
| 8 | SPEC-004 (amend) | continuation now relays the CSO (not text); revision protocol. |
| 9 | SPEC-033 | the Safety Control Plane + the **Checkpoint** primitive (call / decorator / checkpoint_when). |
| 10 | SPEC-034 | the checkpoint resolution lifecycle (approve/reject/edit/timeout) + the addable safety rules (jailbreak, toxicity, secrets, copyright, agency, drift). |
| 11 | SPEC-037 | the unified config — one optional crp.config.yaml; layered override; CRP-Config-Hash. |

**Gate:** run SPEC-026 (Semantic Quality Benchmark) here. A feature ships only
if it improves BOTH Factual F1 AND judge score. Do not proceed to Tier 2 until
CDR/CDGR/CSO demonstrably beat the v3 baseline.

### TIER 2 — The Positioning Layer (what makes v4 revolutionary)

| Order | Spec | Build |
|-------|------|-------|
| 12 | SPEC-028 | multi-horizon context: 3 tiers, intent classification, reference resolution. |
| 13 | SPEC-029 | ephemeral/tool context: scratch buffer, tool provenance, freshness. |
| 14 | SPEC-031 | **STL** — the Semantic Task Layer. Task taxonomy (8 ops), negotiated depth (D1–D5), Operation Frames, anchored goal-compass. This drives all of Tier 1. |

### CROSS-CUTTING — Developer Experience (build alongside, not after)

| Spec | Build |
|------|-------|
| SPEC-032 | the progressive-disclosure SDK: Level 0 (base_url governance), Level 1 (ingest/ask), Level 2 (depth/tools/safety), Level 3 (raw). 70% of devs never leave 0–1. Hide all 58 headers behind response.crp. |

---

## 4. WHAT IS OPTIONAL / SKIP (the overhead traps)

These were explored and deliberately fenced as OPT-IN, OFF by default, because
they add 40x latency. **Do NOT build them into Core. Build only when a real
customer needs them, and only behind the SPEC-023 boundary.**

| Spec | Status | Why |
|------|--------|-----|
| SPEC-023 | READ FIRST if touching amplification | the boundary governor — defines what must never be default |
| SPEC-020 CLD | OPTIONAL — skip for now | capability amplification for weak models; async only |
| SPEC-021 ROS | OPTIONAL — skip for now | consensus/debate reliability; async only |
| SPEC-022 PEF | OPTIONAL — skip for now | only exists to make 020/021 fast; build last or never |
| SPEC-018 AIR | PARTIAL — keep error-quarantine only | n-gram feedback superseded by CDR |
| SPEC-019 CQR | detection only, in Core | the failure-mode taxonomy; remediation is opt-in |

**The decision:** ship Core (Tier 1+2) + products WITHOUT 020/021/022. They are
genuinely valuable only for weak local models on async tasks. Most users on a
capable model never need them. Adding them to Core was the original
over-engineering mistake — do not repeat it.

Also deprioritise: backward-looking continuation summaries (replaced by the CSO).

---

## 5. PRODUCT UPGRADES — which specs are for which product

### CRP SCAN (FIND) — these specs
- SPEC-013 — the GitHub Action + scanner (exists; keep).
- SPEC-036 — **add** the Remediation Engine: code-fix PRs (template library),
  config fixes (to Comply), guided fixes. Free=previews, paid=auto-PRs.
- SPEC-039 — **add** semantic code ingestion: Scan uses CRP's own CKF + CDGR
  to understand large repos and trace calls through wrappers. Needs tree-sitter/
  LSP parsers + the CKF. This is the accuracy upgrade.

### CRP GATEWAY (RUN) — these specs
- SPEC-016 — the service contract (exists; keep) + CRP-GATEWAY-BLUEPRINT.md.
- SPEC-043 — **add** the runtime-product framing + the **low-code/no-code visual
  console** (pipeline builder, playground, analytics, deploy-as-endpoint, export-
  as-code). This is the market-expanding surface.
- The Gateway is the ONLY runtime. It runs Tier 1+2. Comply consumes its evidence.

### CRP COMPLY (PROVE) — these specs
- SPEC-040 — the product (aligned to the LIVE 3-layer product: Programme/
  Artefacts/Evidence; recipes vs agent; Vault; BYO-LLM + credits).
- SPEC-042 — **THE migration** (v2→v4): (1) replace the bespoke proxy WITH the
  Gateway, (2) add the full safety layer, (3) the Connect Repo surface, (4)
  upgrade the agent to v4 retrieval, (5) visual self-service. **Phase 1 (Gateway
  swap) ships first** — turns audit-only into governed with no customer breakage.
- SPEC-048 — **add** the truly-no-code governance loop (Scan finds → Comply
  offers → user expresses → CRP translates to config+code via an ADA over the
  CRP specs), the secure GitHub App connection, and the result-preserving
  post-detection signup.
- SPEC-044 — the compliance agent IS an Authoritative Domain Agent (the corpus
  is the regulatory text). The SPEC-048 Translator is also an ADA (corpus = the
  CRP specs).

### CROSS-PRODUCT — these specs
- SPEC-047 — monetisation: the LIVE Stripe objects + Clerk org linkage +
  entitlement webhook (TS) + runtime entitlement/metering (Python). See also
  CRP-STRIPE-SETUP-GUIDE.md and CRP-GITHUB-APP-GUIDE.md.
- SPEC-037 — the one config shared across all three products.
- SPEC-041 — adoption: framework adapters, onboarding, templates.

---

## 6. THE CORE ALGORITHMS (implement exactly — see specs for full code)

- **CDR** (SPEC-024 §7): score = importance × max(relevance, residual) × novelty
  [floor 0.20] × recency × ngram-guard; MIN_RELEVANCE 0.55; weighted-mean coverage.
- **STL** (SPEC-031 §7): classify → propose depth → decompose → for each op:
  build minimal frame + goal-compass → position model → verify → integrate CSO →
  maybe renegotiate depth.
- **CSO** (SPEC-030): extract decisions WITH rationale + dependency graph;
  verify preservation ≥ 1.0 or repair; HMAC-chain to prior CSO.

---

## 7. VALIDATION (the binding gate)

Build SPEC-026 (SQB) and use it as the ship gate throughout:
1. **CDR test:** Window 5 repetition < 1% AND Factual F1 ≥ Window 1.
2. **CDGR test:** multi_hop_recall jumps vs CDR-only.
3. **STL test:** positioned execution beats injected on Factual F1 + coherence,
   AND CRP-STL-Frame-Vs-Inject < 0.30.
4. **The decisive experiment:** 7B + full CRP vs 70B naive — quality parity at
   lower cost. This is what converts "spec-complete" into "proven."

A feature ships ONLY if it improves Factual F1 AND judge score. Longer/less-
repetitive is NOT sufficient.

---

## 8. REPO STRUCTURE

```
context-relay-protocol/
├── crp/
│   ├── core/
│   │   ├── ckf/              # 009 (graph-enabled)
│   │   ├── envelope/         # 003
│   │   ├── retrieval/        # 024 CDR, 025 CDGR, 027 integrity
│   │   ├── dpe/              # 005
│   │   ├── state/            # 030 CSO, 007 session
│   │   ├── continuation/     # 004 (CSO-based)
│   │   ├── policy/           # 006
│   │   ├── safety/           # 033 control plane, 034 checkpoints + rules
│   │   ├── audit/            # 011
│   │   └── headers/          # 002
│   ├── storage/              # 035 engine + router, 038 backends
│   ├── context/
│   │   ├── multihorizon/     # 028
│   │   └── ephemeral/        # 029
│   ├── stl/                  # 031 positioning ← Tier 2
│   ├── config/               # 037 unified config
│   ├── amplify/              # 018-022 ← OPTIONAL, opt-in, governed by 023
│   ├── gateway/              # 016 + 043 console
│   ├── scan/                 # 013 + 036 remediation + 039 semantic ingestion
│   ├── comply/               # 040 + 042 migration + 048 no-code/github
│   ├── ada/                  # 044 authoritative domain agent
│   ├── billing/              # 047 entitlement + metering
│   └── conformance/          # 014 + 026 SQB
└── tests/{conformance,sqb}/
```

---

## 9. THE SEQUENCE IN ONE PARAGRAPH

Build the storage engine + router (035/038) first; layer CDR/CDGR/CSO (024/025/
030/027) on top and benchmark with SQB (026) before going further; add the
safety control plane + checkpoints (033/034) and the unified config (037);
then the positioning layer (028/029/031) which is what makes v4 special;
expose it all through the progressive-disclosure SDK (032). Then upgrade the
products: Gateway gets its console (043), Scan gets remediation + semantic
ingestion (036/039), Comply gets the v2→v4 migration (042) + no-code governance
+ GitHub (048). Wire monetisation (047) with the live Stripe objects and Clerk.
Skip amplification (020/021/022) until a real customer needs it. Prove
everything with SQB. Hold the 12 invariants.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
