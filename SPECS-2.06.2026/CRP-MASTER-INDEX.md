# CRP — Complete Specification Suite — Master Index

**For:** Engineering team building CRP
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Version:** v4 complete — 41 specs + supporting docs

## START HERE
1. Read **CRP-BUILD-PROMPT.md** — the tiered build plan, invariants, core
   algorithms, validation criteria. This is your build bible (includes the
   v2 update for specs 033–037; specs 038–041 noted below).
2. Read **CRP-SDK-REFERENCE.md** — the developer interface you're implementing.
3. Read **CRP-GATEWAY-BLUEPRINT.md** — how to build the hosted service.
4. Then the specs, in the order the build prompt dictates.

## THE 41 SPECS (in /crp-specs/)

### Tier 1 — Core Protocol (build first)
- SPEC-001 core-protocol · SPEC-002 headers · SPEC-003 envelope
- SPEC-009 ckf · SPEC-024 CDR · SPEC-025 CDGR · SPEC-027 retrieval-integrity
- SPEC-005 dpe · SPEC-030 cognitive-state-object · SPEC-004 continuation
- SPEC-006 safety-policy · SPEC-007 session-token · SPEC-011 audit
- SPEC-017 zero-ckf · SPEC-015 security
- SPEC-035 storage-engine · SPEC-038 storage-backends (BYO store)
- SPEC-033 safety-control-plane · SPEC-034 safety-coverage+checkpoint-lifecycle

### Tier 2 — Positioning Layer
- SPEC-028 multi-horizon-context · SPEC-029 ephemeral-tool-context
- SPEC-031 semantic-task-layer (STL)

### Tier 3 — Products
- SPEC-016 gateway · SPEC-013 github-action-scan
- SPEC-036 scan-remediation · SPEC-039 semantic-code-ingestion
- SPEC-040 crp-comply (the revenue product) · SPEC-014 conformance · SPEC-026 SQB

### Tier 4 — Opt-in Amplification (build last, governed by SPEC-023)
- SPEC-023 amplification-boundary (READ FIRST) · SPEC-018 AIR · SPEC-019 CQR
- SPEC-020 CLD · SPEC-021 ROS · SPEC-022 PEF

### Cross-cutting
- SPEC-032 developer-experience · SPEC-037 unified-config
- SPEC-010 regulatory-mapping · SPEC-012 multi-agent-safety
- SPEC-041 adoption-ecosystem (go-to-market, not protocol)

### Other specs present
- SPEC-008 dispatch

## SUPPORTING DOCS
- CRP-FEASIBILITY.md · CRP-SUBMISSION-GUIDE.md · CRP-SITE-STRATEGY.md
- CRP-PUBLIC-CHECKLIST.md · CRP-IETF-EMAIL-TEMPLATES.md · CRP-IANA-RESPONSE-STRATEGY.md

## SPECS 038–041 — BUILD NOTES (not yet in build-prompt v2)
- **SPEC-038** (storage backends): fold into Tier 1 storage work. Every
  primitive gets a pluggable backend + the config surface + visibility API
  (client.storage.overview, client.knowledge.location).
- **SPEC-039** (semantic code ingestion): Tier 3 Scan work. Scan ingests the
  repo into a code-CKF and uses CDGR multi-hop to trace calls through
  wrappers. Requires tree-sitter/LSP parsers + CRP's CKF.
- **SPEC-040** (CRP Comply): the revenue product. Build incrementally —
  control plane + observability + audit first, then checkpoint inbox, then
  evidence engine, then Scan remediation inbox.
- **SPEC-041** (adoption): framework adapters (LangChain/LlamaIndex/Vercel),
  `crp init`, quickstart repo, template gallery. Go-to-market engineering.

## THE NON-NEGOTIABLE INVARIANTS (from build prompt, never violate)
1. Core path < 50ms overhead. No extra inference in Core.
2. Model-agnostic. Identical governance on any model.
3. Axiom 4: strip all CRP-* headers before the provider.
4. Positioning not injection (STL): build frames up, don't trim down.
5. Embedding consistency across CKF/Coverage/Turn-Log.
6. CSO preservation verified — no silent state loss.
7. HMAC chain unbroken.
8. Amplification opt-in, off by default, async only.
9. Right storage primitive per access (router), not everything through vectors.
10. Checkpoints never leave the end user with a raw error.
11. Remediations are always proposals (PRs), never auto-commits.
12. Config optional and provenanced (CRP-Config-Hash).

## BUILD SEQUENCE (high level)
Phase 1: storage engine + router → CKF + CDR/CDGR → DPE → safety policy +
         control plane + checkpoints → headers → audit → gateway MVP (Level 0)
Phase 2: CSO + continuation → multi-horizon + tools → STL positioning (Level 1)
Phase 3: Comply (control plane + observability + checkpoint inbox + evidence)
Phase 4: Scan + semantic ingestion + remediation → conformance/SQB
Phase 5: amplification (opt-in) → adoption ecosystem (adapters, templates)

Validate everything with the Semantic Quality Benchmark (SPEC-026):
a feature ships only if it improves Factual F1 AND judge score.

---
*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
