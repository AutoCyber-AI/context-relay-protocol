# CRP 2.0 — Complete Capabilities Catalog & Verification Plan

> **Purpose**: Enumerate EVERY capability of the Context Relay Protocol, and define
> how each will be verified through live testing.
>
> **Status**: 13/13 spec conformance. 185 focused tests passing (6 smoke + 34 tool relay + 61 relay strategies + 84 agentic). §20–§22 implemented.

---

## THE PROBLEM CRP SOLVES

Every LLM has a finite context window. When a task exceeds that window — a 200-page
document, a 50-step debugging session, a multi-phase penetration test — information
is lost. Developers face two bad options:

1. **Truncate**: Drop older context. The model forgets critical facts mid-task.
2. **RAG-only**: Retrieve chunks. The model gets fragments without structure or continuity.

CRP solves this by making context window size irrelevant. It continuously extracts,
ranks, and re-injects the most relevant facts from ALL prior windows into each new
window — maintaining structured memory across unlimited context with O(log N) quality
degradation instead of the cliff-edge collapse of naive approaches.

**One API call**: Replace `llm.generate()` with `crp.dispatch()`. Everything else is automatic.

---

## TABLE OF CONTENTS

1. [Core Dispatch Pipeline](#1-core-dispatch-pipeline)
2. [Session Management](#2-session-management)
3. [Extraction Pipeline (6 Stages)](#3-extraction-pipeline-6-stages)
4. [Envelope Builder (6 Phases)](#4-envelope-builder-6-phases)
5. [State Management (3-Tier Memory)](#5-state-management-3-tier-memory)
6. [CKF — Contextual Knowledge Fabric (4-Mode Retrieval)](#6-ckf--contextual-knowledge-fabric-4-mode-retrieval)
7. [Continuation System (Multi-Window)](#7-continuation-system-multi-window)
8. [Security (8 Layers)](#8-security-8-layers)
9. [Advanced Features](#9-advanced-features)
10. [LLM Provider Support](#10-llm-provider-support)
11. [Configuration & Adaptivity](#11-configuration--adaptivity)
12. [Protocol Axioms](#12-protocol-axioms)
13. [Verification Test Plan](#13-verification-test-plan)

---

## 1. CORE DISPATCH PIPELINE

The core loop: receive task → build envelope → call LLM → extract facts → store.

| # | Capability | Method | Description |
|---|-----------|--------|-------------|
| 1.1 | **Single dispatch** | `dispatch(system, task)` | Full pipeline: envelope → LLM → extraction → QualityReport |
| 1.2 | **Intent dispatch** | `dispatch_intent(intent)` | Dispatch from a structured TaskIntent object |
| 1.3 | **Batch dispatch** | `dispatch_batch(items)` | Sequential dispatch of multiple (system, task) pairs |
| 1.4 | **Streaming dispatch** | `dispatch_stream(system, task)` | Yields StreamEvent tokens in real-time, extracts on completion |
| 1.5 | **Hierarchical dispatch** | `dispatch_hierarchical(system, task)` | Map-reduce for inputs that exceed context window (§14) |
| 1.6 | **Zero-LLM ingestion** | `ingest(text, source)` | Extract facts from external text without calling the LLM |
| 1.7 | **Batch ingestion** | `ingest_batch(items)` | Ingest multiple texts in sequence |
| 1.8 | **State export** | `export_state()` | Serialize all session state to bytes (encrypted) |
| 1.9 | **Async variants** | `async_dispatch()`, `async_ingest()`, `async_dispatch_stream()`, `async_close()` | Asyncio-compatible versions of all core operations |
| 1.10 | **Tool-mediated dispatch (§20)** | `dispatch_with_tools(system, task, tools)` | LLM requests context via tool calls; multi-round negotiation |
| 1.11 | **Reflexive dispatch (§21)** | `dispatch_reflexive(system, task)` | Generate blind → fact-check → refine. Accuracy-critical tasks |
| 1.12 | **Progressive dispatch (§21)** | `dispatch_progressive(system, task)` | Compact index first → expand on demand. Breadth-first knowledge |
| 1.13 | **Stream-augmented dispatch (§21)** | `dispatch_stream_augmented(system, task)` | Inject context mid-generation. Long-form coherent output |
| 1.14 | **Agentic dispatch (§22)** | `dispatch_agentic(system, task)` | Full cognitive loop: analyze → plan → synthesize → route → generate → evaluate → revise → curate |

**Key invariant (Axiom 9)**: `dispatch()` returns the LLM's output UNMODIFIED. CRP never alters, filters, or post-processes the model's response.

---

## 1b. AGENTIC ARCHITECTURE (§22) — LLM-IN-THE-LOOP

The paradigm shift: instead of CRP being a pipeline that sends prompts to an LLM, the LLM is **inside** CRP as its cognitive engine. CRP orchestrates all reasoning, and the LLM provides intelligence at every decision point.

```
Traditional:   User → LLM → Text
RAG:           User → Context + LLM → Text
Agentic:       LLM (controller) → Tools → LLM → Output

CRP §22:       CRP (orchestrator) → LLM (cognitive engine)
               → CRP (acts on reasoning) → LLM (generates)
               → CRP (evaluates via LLM) → CRP (curates)
```

| # | Cognitive Module | What It Does | Replaces |
|---|-----------------|--------------|----------|
| 1b.1 | **Task Analysis** | LLM semantically understands task complexity, domain, knowledge needs | Regex-based heuristics |
| 1b.2 | **Strategy Routing** | LLM chooses optimal dispatch strategy (push/reflexive/progressive/stream) | Hardcoded "always push" |
| 1b.3 | **Fact Synthesis** | LLM merges, deduplicates, organizes raw KB facts into coherent knowledge | Raw fact dump into envelope |
| 1b.4 | **Output Evaluation** | LLM assesses output quality, identifies missing elements, triggers revision | Heuristic quality score |
| 1b.5 | **Memory Curation** | LLM manages CRP's knowledge base: promote, demote, merge, discard | Fixed-interval time decay |
| 1b.6 | **Execution Planning** | LLM decomposes complex tasks into multi-step plans with per-step strategies | Single flat dispatch |

**Key architecture decisions:**
- The LLM **never touches CRP state directly** — it returns structured JSON, CRP acts on it
- All cognitive calls go through a single `_cognitive_call()` bottleneck for budgeting/logging
- Multi-step plans are **actually executed**: each step dispatches with its own strategy, feeding outputs forward
- Revision carries **structured evaluation feedback** (scores, missing elements, synthesis hints)
- Strategy **adjusts dynamically** if first attempt scores < 40% completion
- Post-revision curation runs **iteratively** to refine KB after each revision round
- Inner dispatch continuation state **feeds into evaluation** for truncation awareness

---

## 2. SESSION MANAGEMENT

Every CRP interaction happens within a session — a bounded unit with its own state, budget, and lifecycle.

| # | Capability | Method | Description |
|---|-----------|--------|-------------|
| 2.1 | **Session status** | `session_status()` | Returns windows completed, tokens consumed, cost, overhead ratio |
| 2.2 | **Cost estimation** | `estimate_session(system, task)` | Pre-flight cost estimate without calling the LLM |
| 2.3 | **Envelope preview** | `preview_envelope(system, task)` | Inspect what would go into the envelope without dispatching |
| 2.4 | **Runtime configuration** | `configure(**kwargs)` | Change mutable settings (e.g., max_ram_mb) at runtime |
| 2.5 | **Session reset** | `reset_session()` | Clear all counters, DAG, and warm state (ADMIN only) |
| 2.6 | **Session close** | `close()` | Flush state, zero keys, prevent further dispatch |
| 2.7 | **Budget caps** | Config: `max_windows_per_session`, `max_total_input_tokens` | Hard limits that raise BudgetExhaustedError |
| 2.8 | **Session timeout** | Config: `session_timeout` | Auto-expire after inactivity |
| 2.9 | **Remaining budget** | `session_status().remaining_budget` | Windows/tokens remaining before cap |

---

## 3. EXTRACTION PIPELINE (6 STAGES)

After every LLM response, CRP extracts structured facts through a graduated pipeline. Each stage adds capabilities; stages self-gate based on availability.

| Stage | Name | Module | What It Extracts |
|-------|------|--------|-----------------|
| **1** | Regex | `extraction/regex_extractor.py` | URLs, emails, IPs, dates, versions, CVEs, file paths, JSON blocks, code fences, key-value pairs (21 built-in patterns + custom) |
| **2** | Statistical | `extraction/statistical.py` | TextRank top sentences, noun phrases, section headers, list items, numeric quantities |
| **3** | GLiNER | `extraction/gliner.py` | Named entities with dynamic label derivation from task context |
| **4** | UIE | `extraction/uie.py` | Entity relations, event structures, universal IE |
| **5** | Discourse | `extraction/discourse.py` | Discourse markers, rhetorical relations, argument structure |
| **6** | LLM | `extraction/llm_extractor.py` | LLM-generated fact extraction (optional, disabled by default) |

**Quality Gate**: After extraction, a 3-tier validation runs:
- Tier 1: Structural checks (field completeness, type correctness)
- Tier 2: Confidence threshold filtering
- Tier 3: Anomaly detection (deviation from extraction history)

**Key metric**: Extraction yield = facts extracted per 1000 output tokens.

---

## 4. ENVELOPE BUILDER (6 PHASES)

The envelope is the optimally-packed context that goes into each LLM window. It maximizes information density within the token budget.

| Phase | Name | What It Does |
|-------|------|-------------|
| **1** | Task Decomposition | Analyzes the task to identify aspects needing fact support |
| **2** | Bi-Encoder Scoring | Scores every candidate fact by: semantic similarity, recency, information flow, graph centrality, confidence |
| **3** | Cross-Encoder Reranking | Reranks top candidates with cross-encoder (cached) for precision |
| **4** | Graph-Aware Packing | Greedy packing that preserves graph connectivity (related facts stay together) |
| **5** | Bookend Compression | Compresses low-priority facts to ~30% token size, recovering space |
| **6** | CKF Retrieval Gate | If remaining budget > 500 tokens, retrieves additional facts from CKF |

**Context budget formula (Axiom 2)**:
$$E = C - S - T - G$$
Where: C = context window, S = system tokens, T = task tokens, G = generation reserve.

The envelope fills ALL of E — no wasted tokens.

---

## 5. STATE MANAGEMENT (3-TIER MEMORY)

CRP maintains three tiers of memory, inspired by CPU cache hierarchies.

| Tier | Name | Lifetime | Location | Purpose |
|------|------|----------|----------|---------|
| **0** | Model Context | One window | LLM context window | Active generation |
| **1** | Hot State | One transition | Application memory | Facts selected for next envelope |
| **2** | Warm State | One session | In-memory + async persist | All accumulated facts, full tool outputs |
| **3** | Cold State | Cross-session | Disk (encrypted) | Persistent knowledge with GC |

### Warm State Store (Tier 2) Features

| # | Capability | Description |
|---|-----------|-------------|
| 5.1 | **Fact storage** | `add_facts()`, `get_facts()`, `get_ranked_facts()` |
| 5.2 | **Fact lifecycle** | `mark_seen()`, `supersede()`, age tracking, consumption tracking |
| 5.3 | **Critical state** | Goal, phase, blockers, constraints — always in envelope |
| 5.4 | **Structural state** | Current section, list position, open blocks, markdown depth |
| 5.5 | **Event sourcing** | Append-only FactEventLog with monotonic IDs |
| 5.6 | **Snapshots** | EventLogSnapshot for fast session resume |
| 5.7 | **Compaction** | Clustering + summarization of old facts |
| 5.8 | **Fact graph** | Edges between facts with relation types and confidence |

---

## 6. CKF — CONTEXTUAL KNOWLEDGE FABRIC (4-MODE RETRIEVAL)

The CKF provides intelligent retrieval from the full fact corpus. Four modes cover different information needs.

| Mode | Name | Module | Strategy |
|------|------|--------|----------|
| **1** | Graph Walk | `ckf/graph_walk.py` | BFS traversal from seed facts, following typed edges |
| **2** | Pattern Query | `ckf/pattern_query.py` | Structural pattern matching (e.g., `PERSON HAS_ROLE ORGANIZATION`) |
| **3** | Semantic | `ckf/semantic.py` | ANN search via HNSW index (lazy-built at 1000+ facts, cosine fallback before) |
| **4** | Community | `ckf/community.py` | Leiden algorithm community detection + topic summarization |

**Retrieval orchestration**: The envelope builder calls CKF as a gate in Phase 6 — only when there's budget remaining and facts are relevant.

---

## 7. CONTINUATION SYSTEM (MULTI-WINDOW)

When a task can't be completed in one window, CRP automatically continues across windows.

| # | Capability | Description |
|---|-----------|-------------|
| 7.1 | **Gap analysis** | Detects incomplete output via signal analysis |
| 7.2 | **Continuation envelope** | Builds next window's envelope from extraction, not raw overlap |
| 7.3 | **Flow monitoring** | Tracks information flow across windows (marginal gain, saturation) |
| 7.4 | **Output stitching** | Joins multi-window outputs coherently |
| 7.5 | **Re-grounding triggers** | Compound degradation model triggers fact refresh |

### Three-Way Termination

| Code | Condition | Meaning |
|------|-----------|---------|
| **A** | `gap_is_zero` | All requirements met — task complete |
| **B** | `all_signals_dead` | Semantic + rhetorical signals flatline — nothing more to say |
| **C** | `count >= max` | Safety bound (default: 50 windows) |

---

## 8. SECURITY (8 LAYERS)

CRP security is defense-in-depth. Layer 1 is MANDATORY and cannot be disabled.

| Layer | Name | Module | Purpose | Disableable? |
|-------|------|--------|---------|-------------|
| **1** | Input Validation | `security/validation.py` | Unicode NFC normalization, control char stripping, length limits | **NO** (§7.4) |
| **2** | Injection Detection | `security/injection.py` | 21 regex patterns + optional ML classifier (DeBERTa/TF-IDF) | Advisory |
| **3** | RBAC | `security/rbac.py` | 3 roles (OBSERVER/OPERATOR/ADMIN), 13 permissions, sliding-window rate limiting | No |
| **4** | Session Binding | `security/binding.py` | HMAC-SHA256 key derivation per session, prevents cross-session replay | No |
| **5** | Fact Integrity | `security/integrity.py` | BLAKE3/SHA-256 hash chain, HMAC verification (spot-check + full audit) | No |
| **6** | State Encryption | `security/encryption.py` | AES-256-GCM with HKDF-derived keys for cold storage | No |
| **7** | Ingest Quarantine | `security/quarantine.py` | 1-window anti-poisoning: ingested facts get 0.7× confidence penalty, verified after one window | No |
| **8** | Embedding Defense | `security/embedding_defense.py` | SQ8 quantization + XOR salting, auto-stripped on export | No |

### RBAC Roles & Permissions

| Role | Level | Permissions |
|------|-------|-------------|
| OBSERVER | 0 | READ_FACTS, READ_STATE, READ_ENVELOPE, READ_EVENTS |
| OPERATOR | 1 | All Observer + DISPATCH, INGEST, STORE_FACTS, EXPORT_STATE, CONFIGURE |
| ADMIN | 2 | All Operator + DELETE_FACTS, MANAGE_SESSIONS |

### Injection Detection Patterns (21)

Prompt injection, role override, system prompt extraction, delimiter abuse, encoding attacks, multi-language injection, tool-use hijacking, data exfiltration, context window stuffing, and more.

---

## 9. ADVANCED FEATURES

| # | Capability | Module | Spec | Description |
|---|-----------|--------|------|-------------|
| 9.1 | **Source Grounding** | `advanced/source_grounding.py` | §17 | Verbatim passage storage alongside facts for citation |
| 9.2 | **Meta-Learning (ORC)** | `advanced/meta_learning.py` | §19 | Orchestrated Reasoning Chains — structured multi-step reasoning scaffolds |
| 9.3 | **Meta-Learning (ICML)** | `advanced/meta_learning.py` | §19 | In-Context Meta-Learning — few-shot exemplar injection for small models |
| 9.4 | **Meta-Learning (RTL)** | `advanced/meta_learning.py` | §19 | Reasoning Template Library — task-type-specific templates |
| 9.5 | **LLM Curation** | `advanced/curator.py` | §18 | Progressive understanding synthesis (every 5-10 windows) |
| 9.6 | **Hierarchical Dispatch** | Orchestrator | §14 | Map-reduce segmentation for inputs exceeding context window |
| 9.7 | **Auto-Ingest** | Orchestrator | §4.6 | Auto-trigger ingestion when input > available envelope budget |

---

## 10. LLM PROVIDER SUPPORT

CRP is model-agnostic (Axiom 4: Model Ignorance). It works with any provider that can generate text.

| Provider | Module | Transport | Status |
|----------|--------|-----------|--------|
| **OpenAI** | `providers/openai.py` | httpx async, openai SDK | Implemented |
| **Anthropic** | `providers/anthropic.py` | anthropic SDK | Implemented |
| **Ollama** | `providers/ollama.py` | HTTP REST | Implemented |
| **LlamaCpp** | `providers/llamacpp.py` | llama-cpp-python bindings | Implemented |
| **Custom** | `providers/custom.py` | User-provided `generate_fn` + `count_tokens_fn` | Implemented |

**Auto-detection**: If no provider is specified, CRP auto-detects from environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.).

---

## 11. CONFIGURATION & ADAPTIVITY

| # | Capability | Description |
|---|-----------|-------------|
| 11.1 | **Zero-config start** | `CRPOrchestrator(provider=...)` — everything self-configures |
| 11.2 | **Hardware-adaptive** | Auto-detects RAM, CPU, GPU and adjusts thread pools, batch sizes |
| 11.3 | **Immutable + mutable config** | Some settings (max_windows) lock after session start; others (max_ram_mb) are runtime-mutable |
| 11.4 | **Environment variable override** | `CRP_MAX_RAM_MB`, `CRP_MAX_DISPATCH_RATE`, etc. |
| 11.5 | **Config resolver** | Cascading: defaults → env vars → explicit kwargs |
| 11.6 | **Self-calibrating weights** | Extraction, scoring, and re-grounding weights self-adjust after ~5 windows |

---

## 12. PROTOCOL AXIOMS

These are the 10 non-negotiable design principles. Every CRP implementation MUST honor these.

| # | Axiom | Guarantee |
|---|-------|-----------|
| 1 | **Task Isolation** | Each window gets a dedicated, clean context |
| 2 | **Maximum Context Saturation** | E = C - S - T - G. No wasted tokens. |
| 3 | **Zero Interpretation Overhead** | Facts are pre-digested: the model reads, not parses |
| 4 | **Model Ignorance** | The model never knows CRP exists |
| 5 | **Unbounded Capacity** | No artificial ceiling. O(log N) degradation. |
| 6 | **Portability** | Language, framework, and model independent |
| 7 | **Window Provenance** | Full DAG lineage: every fact traces to its source window |
| 8 | **Hardware-Adaptive Resource Efficiency** | Self-configures per hardware. Never starves the host. |
| 9 | **Output Integrity** | LLM output is returned UNMODIFIED. Always. |
| 10 | **LLM Amplification** | CRP amplifies the model's capability, never replaces it |

---

## 13. VERIFICATION TEST PLAN

Each capability will be verified through live testing. Tests are grouped by complexity.

### Tier 1: Core Pipeline (Can verify with ANY LLM, even 4K context)

| Test | Capability | Method | Expected Result |
|------|-----------|--------|-----------------|
| V1.1 | Single dispatch | `dispatch("You are a calculator.", "What is 6*7?")` | Returns "42" (or equivalent), QualityReport with metrics |
| V1.2 | Extraction on output | Check `report.facts_extracted > 0` | At least 1 fact extracted from LLM response |
| V1.3 | Session status | `session_status()` after dispatch | `windows_completed == 1`, `total_input_tokens > 0` |
| V1.4 | Envelope preview | `preview_envelope("sys", "task")` | Returns EnvelopePreview with `total_tokens > 0` |
| V1.5 | Cost estimation | `estimate_session("sys", "task")` | Returns CostEstimate with `estimated_windows == 1` |
| V1.6 | Output integrity | Compare dispatch output to raw LLM output | Byte-identical (Axiom 9) |
| V1.7 | Zero-LLM ingestion | `ingest("The capital of France is Paris.", "test")` | Facts stored, no LLM call made |
| V1.8 | Budget enforcement | Set `max_windows_per_session=1`, dispatch twice | Second dispatch raises BudgetExhaustedError |
| V1.9 | Session close | `close()` then `dispatch()` | Raises SessionClosedError |
| V1.10 | Configure | `configure(max_ram_mb=128)` | Config updated, immutable fields raise ValueError |

### Tier 2: Multi-Window & State (Needs 2+ dispatches)

| Test | Capability | Method | Expected Result |
|------|-----------|--------|-----------------|
| V2.1 | Fact accumulation | Dispatch 3 times with related tasks | Facts from window 1 appear in window 3's envelope |
| V2.2 | Envelope growth | Preview envelope before and after dispatches | Envelope contains more facts after more windows |
| V2.3 | DAG tracking | Check `orch.dag.window_count()` after dispatches | DAG grows with each dispatch, records parent-child |
| V2.4 | Session reset | Reset after dispatches | All counters zero, DAG cleared |
| V2.5 | Critical state | Set phase via warm store | Critical state persists across windows |
| V2.6 | Fact supersession | Extract conflicting facts | Newer fact supersedes older via `supersede()` |

### Tier 3: Security (No LLM needed — unit-testable)

| Test | Capability | Method | Expected Result |
|------|-----------|--------|-----------------|
| V3.1 | Input validation | Dispatch with control chars | Chars stripped, dispatch succeeds |
| V3.2 | Injection detection | Dispatch with "ignore previous instructions" | SecurityFlags shows `injection_markers_detected > 0` |
| V3.3 | RBAC enforcement | Create OBSERVER, try dispatch | RateLimitExceededError with permission denial |
| V3.4 | RBAC role hierarchy | ADMIN can reset, OPERATOR cannot | Permission checks correct |
| V3.5 | Rate limiting | Dispatch faster than rate limit | RateLimitExceededError after threshold |
| V3.6 | Fact integrity | Tamper with a fact's hash | Integrity check detects tampering |
| V3.7 | State encryption | Export state | Output is AES-256-GCM encrypted bytes |
| V3.8 | Ingest quarantine | Ingest external text | Facts get 0.7× confidence penalty |

### Tier 4: Extraction & CKF (Rich content testing)

| Test | Capability | Method | Expected Result |
|------|-----------|--------|-----------------|
| V4.1 | Regex extraction | Dispatch with URLs/emails/IPs in output | Stage 1 extracts structured entities |
| V4.2 | Statistical extraction | Dispatch with paragraphs | Stage 2 extracts key sentences via TextRank |
| V4.3 | Discourse extraction | Output with "however", "therefore" | Stage 5 extracts discourse relations |
| V4.4 | Quality gate | Check report.quality_tier | Returns "excellent", "good", "acceptable", or "degraded" |
| V4.5 | CKF graph walk | Add facts with edges, query via graph walk | Related facts retrieved via BFS |
| V4.6 | CKF pattern query | Add typed facts, query by pattern | Matching facts returned |
| V4.7 | CKF semantic | Add 1000+ facts, query semantically | HNSW index built, similar facts returned |

### Tier 5: Advanced & Integration (Full system test)

| Test | Capability | Method | Expected Result |
|------|-----------|--------|-----------------|
| V5.1 | Streaming dispatch | `dispatch_stream("sys", "task")` | StreamEvents yielded, final output matches non-streaming |
| V5.2 | Batch dispatch | `dispatch_batch([(s1,t1), (s2,t2)])` | Both dispatches succeed, facts accumulate |
| V5.3 | Hierarchical dispatch | Dispatch with input > context window | Auto-segments, map-reduce produces combined result |
| V5.4 | Continuation | Task requiring multi-window response | Auto-continues, stitched output coherent |
| V5.5 | Source grounding | Enable source grounding, dispatch | Report includes verbatim passages |
| V5.6 | Meta-learning scaffolds | Enable ORC/ICML/RTL with small model | Scaffolds injected into envelope |
| V5.7 | Provider swap | Same task with OpenAI, Ollama | Same CRP behavior, different outputs |
| V5.8 | WASA integration | Full pentest phase through CRP | CRP manages context across WASA phases |

### Verification Strategy

**Phase A — Unit Verification (NOW)**
Run the existing 709 tests. Confirm 13/13 spec conformance. ✅ DONE

**Phase B — Live Single-Window (NEXT)**
Use a small local LLM (Ollama with a 4K model like `phi3:mini` or `qwen2:0.5b`).
Run Tier 1 tests (V1.1-V1.10). Proves the core pipeline works end-to-end.

**Phase C — Live Multi-Window**
Use the same LLM. Run Tier 2 tests (V2.1-V2.6).
Proves fact accumulation, envelope growth, and DAG tracking work with real LLM output.

**Phase D — Security Audit**
Run Tier 3 tests (V3.1-V3.8). Most don't need an LLM — they test protocol internals.

**Phase E — WASA Integration Test**
Run a real WASA AI penetration test phase through CRP.
Proves CRP works in production with real tool outputs and multi-step reasoning.

---

## SUMMARY

| Category | Capabilities | Verified By |
|----------|-------------|-------------|
| Core Dispatch | 14 methods (incl. tool, reflexive, progressive, stream-aug, agentic) | 185 unit tests + Tier 1 live |
| Agentic Architecture (§22) | 6 cognitive modules, multi-step plans, revision loop | 84 agentic tests |
| Session Management | 9 features | 185 unit tests + Tier 1 live |
| Extraction Pipeline | 6 stages + quality gate | 185 unit tests + Tier 4 live |
| Envelope Builder | 6 phases | 185 unit tests + Tier 2 live |
| State Management | 8 features across 4 tiers | 185 unit tests + Tier 2 live |
| CKF Retrieval | 4 modes | 185 unit tests + Tier 4 live |
| Continuation | 5 subsystems, 3-way termination | 185 unit tests + Tier 5 live |
| Security | 8 layers, 13 permissions, 21 injection patterns | 185 unit tests + Tier 3 live |
| Advanced | 7 features | 185 unit tests + Tier 5 live |
| Provider Support | 5 providers | Tier 5 live |
| Configuration | 6 adaptivity features | 185 unit tests |
| Protocol Axioms | 10 guarantees | Design + test coverage |

**Total unique capabilities cataloged: 100+**
**Total test assertions backing them: 185 unit tests**
**Live verification tests defined: 35 scenarios across 5 tiers**
