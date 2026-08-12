# CRP Comply — Comprehensive Upgrade Report v2
## (Enhanced with CRPv4 Context Management & AI Safety Gap Analysis)

**Date:** 2026-06-05  
**Scope:** Agentic Ecosystem, Context Management, AI Safety, Navigation, User Experience  

---

## Part A: CRPv4 Capabilities Inventory — What We HAVE vs. What We USE

### A1. CRPv4 Context Management — 14 Methods Comply is NOT Using

| # | CRPv4 Method | Spec | What It Does | Comply Status | Impact of Not Using |
|---|-------------|------|-------------|---------------|---------------------|
| 1 | **`crp.Client.dispatch*()`** (universal LLM entry) | SPEC-008 | Replaces EVERY raw LLM call. Handles envelope construction, window assembly, generation, extraction, continuation transparently. | **BYPASSED** — `ComplianceLLM` calls provider directly | Hot path never gets auto-ingest, envelope negotiation, or continuation. Every LLM call is bespoke. |
| 2 | **CDR (Coverage-Differential Retrieval)** | SPEC-024 | Guarantees quality at Window 5 = quality at Window 1. Prevents stale context repetition. | **NOT USED** — Comply repeats same RAG query every window | Multi-window deliverables degrade in quality. Window 5 of a DPIA gets the same chunks as Window 1. |
| 3 | **CDGR (Coverage-Differential Graph Retrieval)** | SPEC-025 | Finds connector facts for multi-hop reasoning. Bridges disconnected anchor facts. | **NOT USED** — flat RAG only | Complex reasoning (e.g., "how does Art 9 risk management relate to my Annex III system?") misses bridging facts. |
| 4 | **Continuation Protocol (Window DAG)** | SPEC-004 | DAG-based window chaining with FULL_CONTEXT/SUMMARY/FACTS_ONLY/RESULT_ONLY transfer types. | **NOT USED** — linear message compaction | No structured cross-window state. Old tool results and prior reasoning are lost or manually compacted. |
| 5 | **Cognitive State Object (CSO)** | SPEC-030 | Structured cognitive state with dependency graph, decisions, open_questions, goal_state. | **NOT USED** — text summaries only | Reasoning is lossy. When facts change, dependent decisions aren't invalidated. No backtracking. |
| 6 | **Semantic Task Layer (STL)** | SPEC-031 | 8 operations (RETRIEVE, ANALYSE, SYNTHESISE, etc.) with depth negotiation and positioning. | **NOT USED** — heuristic triage + monolithic prompt | Model does 3 jobs at once (retrieve + decide relevance + generate). No depth negotiation. |
| 7 | **Multi-Horizon Context (P/C/E tiers)** | SPEC-028 | Persistent (CKF) vs. Conversational (turn log) vs. Ephemeral (scratch buffer) with different retrieval policies. | **NOT USED** — everything goes through one RAG index | Tool outputs pollute the knowledge base. Conversation turns aren't isolated from persistent facts. |
| 8 | **Scratch Buffer + Freshness Gating** | SPEC-029 | Tool outputs stored as pointers; envelope gets summary only. TTL-based staleness detection. | **NOT USED** — raw tool JSON stuffed into messages | 5,000-row API results blow up the prompt. No staleness detection — old tool results reused silently. |
| 9 | **5-Primitive Storage Engine** | SPEC-035 | CKF Graph, Rolling Log, Hot Cache, Inverted Index, Scratch Buffer with unified Access Router. | **NOT USED** — 4 bespoke substrates (sqlite, JSON, mem, CKF.db) | Fragmented storage, no LRU eviction, no hot cache, no inverted index for exact lookup. |
| 10 | **WarmStateStore (event-sourced)** | SPEC-028 | Append-only fact events, snapshot compaction, document_map, structural_state. | **NOT USED** — JSON session files | No event sourcing. No fast resume. No document_map for deliverable structure. |
| 11 | **ETag Conditional Dispatch** | SPEC-003 | Skip envelope reconstruction when CKF hasn't changed. | **NOT USED** — rebuilds envelope every call | Wastes tokens and latency on identical subsequent queries. |
| 12 | **Context Tools (pull architecture)** | SPEC-032 | 5 tools: `crp_retrieve_context`, `crp_get_document_structure`, `crp_check_facts`, `crp_get_related_facts`, `crp_get_continuation_state` | **PARTIALLY ADDED** — 5 tools now in agent registry | LLM can now request context on demand. Pull architecture partially implemented. |
| 13 | **Fact Authority Resolution** | SPEC-027 | Detects intra-envelope contradictions and arbitrates by authority. | **NOT USED** — returns contradictory facts to LLM | LLM receives "Art 9 requires X" and "Art 9 requires NOT X" simultaneously. |
| 14 | **DataLineageTracker** | SPEC-015 | Tracks data provenance, transformations, classifications for compliance. | **PARTIALLY ADDED** — created but not used in dispatch path | Can't prove GDPR Art. 30 records of processing. Can't trace where a deliverable fact came from. |

### A2. CRPv4 AI Safety & Governance — 15 Features Comply is NOT Using

| # | Feature | Spec | What It Does | Comply Status |
|---|---------|------|-------------|---------------|
| 1 | **Safety Control Plane (SCP)** | SPEC-033 | Unified registry of all safety capabilities with `.registry()`, `.show()`, `.set()`, `.explain()` | NOT USED — static HTML console only |
| 2 | **Checkpoint Primitive** | SPEC-033/034 | Inline human-in-the-loop: `crp.checkpoint(decision, reason)` with APPROVE/REJECT/EDIT/TIMEOUT | PARTIAL — `checkpoint_inbox.py` exists but crashes without v4 SDK |
| 3 | **Custom Safety Rules** | SPEC-033 | `@client.safety.rule(name, severity)` — first-class DPE checks | NOT USED — no custom rules API |
| 4 | **Safety Manifest** | SPEC-033 | One source of truth (code + UI) driving both SDK and dashboard | NOT USED — dashboard uses hard-coded levels |
| 5 | **Regulation Coverage View** | SPEC-033 | `client.safety.coverage()` shows which EU AI Act articles, GDPR articles, ISO controls are satisfied | NOT USED |
| 6 | **Safety Policy Directive Language** | SPEC-006 | CSP-style directives: `halt-on CRITICAL`, `require-grounding 0.90`, `block-pii` | NOT USED — safety is hard-coded in agent prompt |
| 7 | **Policy Inheritance** | SPEC-006 | Child agents MUST have equal or more restrictive policies than parents | NOT USED — no sub-agent policy propagation |
| 8 | **Industry Profiles** | SPEC-006 | `profile=medical`, `profile=financial` with preset directive bundles | NOT USED — domain detection is manual |
| 9 | **Safety Budget (multi-agent)** | SPEC-012 | Cumulative risk across agent chains → circuit breaker (CLOSED/HALF-OPEN/OPEN) | NOT USED — no cumulative risk tracking |
| 10 | **Re-Dispatch Protocol** | SPEC-005 | On HIGH risk: reduce temperature, upgrade strategy, augment prompt, retry | NOT USED — single-shot generation only |
| 11 | **N-Gram Output Guard** | SPEC-024 | Blacklists 6-grams after each window to prevent repetition | NOT USED — repetition handled by LLM only |
| 12 | **Recency Decay in Retrieval** | SPEC-027 | Facts past TTL get stale floor of 0.30 in ranking | NOT USED — no TTL-based ranking |
| 13 | **Parallel Coverage Isolation** | SPEC-027 | Pre-partitions coverage scopes before fan-out | NOT USED — single-threaded retrieval |
| 14 | **Tool-Grounded Attribution** | SPEC-029 | DPE checks that tool results aren't fabricated | NOT USED — tool results trusted blindly |
| 15 | **Zero-CKF Mode** | SPEC-017 | Graceful degradation when CKF has 0 facts with onboarding hints | NOT USED — fails cryptically on empty corpus |

---

## Part B: Navigation & UX Rename Plan — IMPLEMENTED

### B1. Renames (High Priority) ✅ DONE

| Current | New | Why |
|---------|-----|-----|
| **Draft** | **Agent** | "Draft" is an output, not a place. Users interact with an AI agent here. |
| **Programme** | **Obligations** | British spelling, abstract. Users need to know what regulators expect. |
| **Artefacts** | **Documentation** | British spelling, vague. This page tracks required documents to upload. |
| **Evidence** | **Audit log** | Too broad — everything is "evidence." This page shows runtime proxy logs. |
| **No-Code Setup** | **Quick setup** | Jargony. "Quick setup" is universally understood. |
| **Repositories** | **Code scan** | Describes object not action. "Code scan" is clearer. |

### B2. Files Changed

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Page titles updated |
| `frontend/src/components/AppShell.tsx` | Nav labels, shortcuts, search placeholder |
| `frontend/src/pages/v2/Draft.tsx` | Tab labels: "Run recipe", "Chat" |
| `frontend/src/pages/v2/Programme.tsx` | Heading: "Your obligations" |
| `frontend/src/pages/v2/Artefacts.tsx` | Heading: "Required documentation" |
| `frontend/src/pages/v2/Evidence.tsx` | Heading: "Audit log" |
| `frontend/src/pages/v2/Vault.tsx` | Heading: "Deliverable vault" |
| `frontend/src/pages/v2/Dashboard.tsx` | Copy: "recipes" → "deliverables" |
| `src/crp_comply/agent/orchestrator.py` | System prompt updated for new tools |
| `src/crp_comply/agent/tools.py` | 5 CRP context tools added + wired into registry |

**All existing routes preserved** — zero breakage for bookmarks or external links.

---

## Part C: Agentic Ecosystem — Integration Status

### C1. CRP Context Tools — IMPLEMENTED ✅

Five new tools added to the agent's `default_registry()`:

| Tool | Purpose | Backend Used |
|------|---------|-------------|
| `crp_retrieve_context` | Unified retrieval from corpus + CKF | `rag.query()` + `fabric.pattern_query()` + `fabric.recall_facts()` |
| `crp_check_facts` | Verify a claim before asserting it | `rag.query()` + `fabric.recall_facts()` + contradiction detection |
| `crp_get_related_facts` | Graph walk for connector facts | `fabric.graph_walk()` |
| `crp_get_document_structure` | Standard deliverable outlines | Hard-coded outlines (dpia, risk_assessment, technical_docs, transparency, fria) |
| `crp_get_continuation_state` | Task progress / coverage gaps | Session-state stub (full implementation needs CRP v4) |

**System prompt updated** to instruct the LLM to use `crp_retrieve_context` as the first broad-sweep tool and `crp_check_facts` before asserting specific claims.

### C2. CRP Dispatch Path Audit — FIXED ✅

| Issue | Status |
|-------|--------|
| `_dispatch_pr` unused | **Fixed** — now calls `record_output()` at dispatch end |
| PII redactions not in audit | **Fixed** — redaction count recorded in dispatch-end event |
| Missing processing record for GDPR Art. 30 | **Fixed** — `_dispatch_pr.record_output()` writes processing record |

### C3. Remaining Work (Blocked or Future)

| Feature | Blocker | Priority |
|---------|---------|----------|
| Full `crp.Client.dispatch()` adoption | `crprotocol>=4.0.0` not on PyPI | P0 |
| CDR/CDGR retrieval | `crp.envelope.cdr` module not in v3 SDK | P1 |
| CSO (Cognitive State Object) | `crp.state.cso` module not in v3 SDK | P1 |
| STL (Semantic Task Layer) | `crp.stl` module not in v3 SDK | P1 |
| Multi-horizon context tiers | `crp.state.horizons` module not in v3 SDK | P1 |
| Scratch Buffer + freshness gating | `crp.state.scratch_buffer` module not in v3 SDK | P1 |
| Safety Control Plane | `crp.security.control_plane` crashes without v4 SDK | P1 |
| DPE 13-stage pipeline | `crp.core.dpe` module not in v3 SDK | P2 |

---

## Part D: Security Fixes Already Applied (Previous + This Session)

| # | Fix | Status |
|---|-----|--------|
| 1 | Worker WS query-string auth removed | ✅ Done |
| 2 | Worker WS Origin validation added | ✅ Done |
| 3 | Worker WS audit JWT secret required | ✅ Done |
| 4 | Worker WS per-user rate limit | ✅ Done |
| 5 | Worker WS streaming queue logging | ✅ Done |
| 6 | Worker WS timeout race fixed | ✅ Done |
| 7 | Worker SDK chunked response cap | ✅ Done |
| 8 | ProviderStore atomic writes | ✅ Done |
| 9 | Email sender wired to dispatcher | ✅ Done |
| 10 | `emit_notification()` added | ✅ Done |
| 11 | Clerk JWT `verify_aud` enabled | ✅ Done |
| 12 | JWT revocation list | ✅ Done |
| 13 | Device fingerprint logging | ✅ Done |
| 14 | Frontend idle timeout (30min) | ✅ Done |
| 15 | 24-hour session ceiling | ✅ Done |
| 16 | API key in sessionStorage | ✅ Done |
| 17 | CRP dispatch audit trail fixed | ✅ Done (this run) |
| 18 | 5 CRP context tools added | ✅ Done (this run) |

---

## Part E: AI Safety Hardening Plan

See `CRP-COMPLY-AI-SAFETY-PLAN.md` for the detailed plan covering:
1. Audit trail integrity (cache-hit coverage, HMAC persistence)
2. Injection defense depth (tool-result scanning, structural validation)
3. Safety Control Plane integration (policy directives, safety budget)
4. DPE integration (when crp v4 available)
5. Data lineage tracking

---

*Report version 2.0 — covers CRPv4 context management, AI safety, navigation renames, and agentic ecosystem integration.*
