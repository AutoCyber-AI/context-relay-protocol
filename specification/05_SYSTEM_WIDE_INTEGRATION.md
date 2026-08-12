<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 05 — System-Wide Integration

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · [01 Research](01_RESEARCH_FOUNDATIONS.md) · [02 Core Protocol](02_CORE_PROTOCOL.md) · [03 Envelope](03_CONTEXT_ENVELOPE.md) · [04 Generation](04_TOKEN_GENERATION_PROTOCOL.md) · **05 Integration** · [06 Implementation](06_IMPLEMENTATION_PLAN.md)

> How CRP applies to ALL LLM operations in any agentic system — and how to map yours.

---

## 1. PRINCIPLES OF SYSTEM-WIDE ADOPTION

CRP is not a feature you bolt onto one subsystem. It replaces the **entire paradigm** of how your system interacts with the LLM. Every single `llm.generate()` call becomes a `crp.dispatch()`.

### 1.1 The Audit-First Approach

Before implementing CRP, you must:
1. **Map every LLM call site** — find every place your code invokes the LLM
2. **Identify chains** — which calls naturally form sequences where state must transfer
3. **Mark continuation candidates** — which calls produce output that might exceed one window
4. **Flag shared state** — which calls read/write the same facts

Note: you do NOT need to "classify each call into a task type." TaskIntent is declarative and all-optional — the protocol derives everything it needs from the system prompt and task input.

### 1.2 The Wrapper Pattern

Implementation follows ONE pattern for EVERY call site:

```python
# BEFORE (direct LLM call):
response = llm.generate(prompt, max_tokens=4096)

# AFTER (CRP dispatch — zero configuration):
response = crp.dispatch(
    system_prompt=SYSTEM_PROMPT,
    task_input=task_data
)

# AFTER (CRP dispatch — with optional user overrides):
response = crp.dispatch(
    system_prompt=SYSTEM_PROMPT,
    task_input=task_data,
    output_schema={"type": "object", "properties": {"tool": {"type": "string"}}},
    max_continuations=10
)
```

The CRP dispatcher handles envelope construction, window assembly, generation, extraction, information flow measurement, and continuation — all transparently.

---

## 2. WASA AI CALL SITE MAP

### 2.1 Complete Inventory (87+ Sites)

Every LLM invocation in WASA AI, organized by subsystem:

#### Subsystem 1: Memory Management (6 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `memory_compiler.py` | 266 | Compile conversation memory | Yes |
| `context_compaction.py` | 427 | Compact context | Yes |
| `context_compaction.py` | 713 | Context summary | Yes |
| `context_compaction.py` | 735 | Context summary | No |
| `conversation_summarizer.py` | 264 | Summarize conversation | Yes |
| `cycle.py` | 542 | Cycle memory reflection | No |

**CRP Impact**: Memory windows get the full conversation in their task zone. The envelope carries session metadata and prior memory entries. Extraction pipeline captures key decisions and facts from conversation summaries.

#### Subsystem 2: Planning & Execution (8 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `generator.py` | 328 | Generate pentest plan | Yes |
| `generator.py` | 392 | Generate sub-plan | No |
| `replanner.py` | 477 | Re-plan based on findings | Yes |
| `replanner.py` | 524 | Adjust plan | No |
| `replanner.py` | 861 | Re-evaluate plan | No |
| `hierarchical.py` | 560 | Hierarchical plan step | No |
| `llm_integration.py` | 190 | Plan generation | Yes |
| `llm_integration.py` | 454 | Plan adjustment | No |

**CRP Impact**: Planning windows receive the full discovery state via semantically-scored envelope. The plan output is extracted as structured facts that subsequent windows reference. Replanning windows get both the original plan AND accumulated findings — scored by relevance to the replanning task.

#### Subsystem 3: Tool Selection & Orchestration (8 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `phase_engine.py` | 1416 | Select next tool | No |
| `phase_engine.py` | 1696 | Tool parameter generation | No |
| `phase_engine.py` | 2084 | Evaluate tool result | No |
| `evaluator_optimizer.py` | 805 | Evaluate chain step | No |
| `evaluator_optimizer.py` | 842 | Optimize chain | No |
| `enhanced_routing.py` | 1272 | Route to tool set | No |
| `enhanced_routing.py` | 1317 | Confirm routing | No |
| `llm_mcp_bridge.py` | 546 | MCP tool orchestration | No |

**CRP Impact**: These produce SHORT output (100-500 tokens). The envelope dominates — filled with discoveries, available tools, and phase state via semantic scoring. These windows benefit most from CRP because fresh context + full discovery state = better tool selection.

#### Subsystem 4: Report Generation (8 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `report_generator.py` | 581 | Generate report section | Yes |
| `report_generator.py` | 5554 | Compile final report | Yes |
| `report_generator.py` | 5575 | Report conclusion | No |
| `sectioned_generator.py` | 335 | Generate section | Yes |
| `sectioned_generator.py` | 680 | Generate finding detail | No |
| `event_emitter.py` | 594 | Emit progress event | No |
| `event_emitter.py` | 640 | Emit update | No |
| `cvss_calculator.py` | 955 | Calculate CVSS with LLM | No |

**CRP Impact**: Report windows are the highest-value CRP targets. Each section gets its own window with section-specific findings in the envelope (scored by semantic similarity to the section topic). Continuation produces unbounded section length with extraction-built envelopes. Gap analysis ensures nothing is missed.

#### Subsystem 5: Reasoning & Agents (6 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `react_agent.py` | 299 | ReAct reasoning step | No |
| `streaming_reasoner.py` | 381 | Stream reasoning | Yes |
| `plan_execute_agent.py` | 240 | Plan step | No |
| `plan_execute_agent.py` | 339 | Execute step reasoning | No |
| `plan_execute_agent.py` | 418 | Evaluate result | No |
| `plan_execute_agent.py` | 614 | Final answer | Yes |

**CRP Impact**: The ReAct loop is already close to CRP's model (separate LLM call per step). CRP formalizes the state transfer with extraction-built envelopes instead of ad-hoc prompt concatenation.

#### Subsystem 6: Knowledge/CKF (10 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `unified_query_service.py` | 1193 | CKF-enhanced query | Yes |
| `unified_query_service.py` | 3260 | Chat response | Yes |
| `unified_query_service.py` | 3361 | Follow-up response | Yes |
| `rag/service.py` | 504 | CKF query | No |
| `rag_engine_integration.py` | 2429 | CKF integration | No |
| `wasa_llm_bridge.py` | 117 | LLM bridge query | No |
| `rag_agent.py` | 197 | Agent CKF step | No |
| `rag_agent.py` | 496 | Agent synthesis | Yes |
| `rag_agent.py` | 700 | Agent final answer | Yes |

**CRP Impact**: Knowledge windows receive CKF-retrieved documents in their task zone. The envelope carries query context and prior conversation, semantically scored. The Contextual Knowledge Fabric (Tier 3) is queried via multi-mode retrieval (graph walk + pattern query + semantic fallback) BEFORE envelope construction. Cross-session knowledge, graph structure, and community summaries are available to every window.

#### Subsystem 7: Continuation (18 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `continuation_manager.py` | 499 | Continuation pass 1 | Yes |
| `continuation_manager.py` | 593 | Continuation pass N | Yes |
| `continuation_manager.py` | 705 | Final continuation | Yes |
| `adaptive_continuation.py` | 194 | Adaptive continue | Yes |
| `input_pool.py` | 380 | Input pool continue | Yes |
| `service.py` | ~3580+ | Service auto-continue | Yes |
| `websocket.py` | ~1287+ | WS auto-continue | Yes |
| *(+11 more across various files)* | — | Various continuation | Yes |

**CRP Impact**: These ARE already continuation windows. CRP replaces ALL 18 ad-hoc continuation implementations with ONE unified protocol: extraction-built envelopes, information flow measurement, physical-wall-only triggers, gap-driven continuation content.

#### Subsystem 8: API Controllers (7 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `llm_narrator.py` | 321 | Narrate operation | No |
| `routers/llm.py` | 231 | Direct LLM query | Yes |
| `status.py` | 374 | Status summary | No |
| `websocket.py` | 1287 | WebSocket chat | Yes |
| `websocket.py` | 1399 | WebSocket pentest | Yes |
| `websocket.py` | 2328 | WebSocket stream | Yes |
| `metasploit.py` | 457 | Metasploit guidance | No |

**CRP Impact**: These are user-facing endpoints. Each message becomes a dedicated window with conversation history semantically scored in the envelope.

#### Subsystem 9: Intent & Routing (4 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `integration_bridge.py` | 1120 | Classify intent | No |
| `query_orchestrator.py` | 548 | Route query | No |
| `multi_turn_coordinator.py` | 776 | Coordinate turn | No |
| `resource_manager.py` | 61 | Resource classification | No |

**CRP Impact**: Cheapest windows — tiny output, minimal task input. The envelope is massive but semantic scoring naturally deprioritizes most content for classification tasks (the embeddings of a classification task don't match most discovery facts).

#### Subsystem 10: MCP/Subagents (6 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `integration_bridge.py` | 3761 | Bridge orchestration | No |
| `integration_bridge.py` | 4060 | Tool execution plan | No |
| `integration_bridge.py` | 5240 | Result evaluation | No |
| `executor.py` | 4693 | Per-tool analysis | No |
| `subagents/base.py` | 373 | Subagent LLM call | No |
| `orchestrator.py` | 976/1042 | Agent orchestration | No |

**CRP Impact**: Subagent windows are naturally isolated. CRP adds inter-agent state transfer via envelopes.

#### Subsystem 11: Core Service (5 sites)

| File | Line | Current Purpose | Continuation? |
|------|------|----------------|---------------|
| `service.py` | 1523 | Main generation | Yes |
| `service.py` | 3478 | Streaming generation | Yes |
| `service.py` | 3580 | Auto-continuation | Yes |
| `service.py` | 3757 | Context-managed gen | Yes |
| `service.py` | 3917 | Direct generation | No |

**CRP Impact**: `service.py` is the central LLM gateway. All CRP dispatches route through here. The service needs a CRP-aware dispatch layer wrapping these 5 entry points.

---

## 3. CRP INTEGRATION ARCHITECTURE

### 3.1 Layer Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                                │
│  (API controllers, WebSocket handlers, CLI)                        │
│                          │                                         │
│                          ▼                                         │
│  ┌─────────────────────────────────────────────────────┐          │
│  │             CRP ORCHESTRATOR                         │          │
│  │                                                      │          │
│  │  ┌───────────────┐  ┌────────────────────────────┐  │          │
│  │  │ Envelope      │  │ Graduated Extraction       │  │          │
│  │  │ Builder       │  │ Pipeline (Blackboard)      │  │          │
│  │  │ (semantic +   │  │ (regex→stats→GLiNER→UIE   │  │          │
│  │  │  CKF multi-   │  │  →discourse→LLM-relational)│  │          │
│  │  │  mode query)  │  │                            │  │          │
│  │  └───────┬───────┘  └─────────────┬──────────────┘  │          │
│  │          │                        │                  │          │
│  │  ┌───────▼───────┐  ┌────────────▼──────────────┐  │          │
│  │  │ Window        │  │ Information Flow            │  │          │
│  │  │ DAG Manager   │  │ Monitor + Degradation       │  │          │
│  │  └───────┬───────┘  └────────────┬──────────────┘  │          │
│  │          │                        │                  │          │
│  │  ┌───────▼───────┐  ┌────────────▼──────────────┐  │          │
│  │  │ Warm State    │  │ Continuation               │  │          │
│  │  │ Store (SQLite)│  │ Manager                    │  │          │
│  │  └───────┬───────┘  └────────────┬──────────────┘  │          │
│  │          │                        │                  │          │
│  │  ┌───────▼────────────────────────▼──────────────┐  │          │
│  │  │  CQS Detector │ CWCV Validator │ Review Mgr   │  │          │
│  │  │  (§12)        │ (§13 3-tier)   │ (§14 gated)  │  │          │
│  │  └───────┬────────────────────────┬──────────────┘  │          │
│  │          │                        │                  │          │
│  │  ┌───────▼───────┐  ┌────────────▼──────────────┐  │          │
│  │  │ Hierarchical  │  │ Scale Mode Selector        │  │          │
│  │  │ Processor     │  │ + Quality Reporter         │  │          │
│  │  └───────────────┘  └────────────────────────────┘  │          │
│  └─────────────────────────┬───────────────────────────┘          │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────┐          │
│  │            LLM SERVICE LAYER                         │          │
│  │  (service.py → llama_server.py → llama.cpp)          │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                    │
│  ┌─────────────────────────────────────────────────────┐          │
│  │            STORAGE LAYER                             │          │
│  │  Tier 2: WarmStateStore (SQLite WAL + memory cache)  │          │
│  │          + Event Log (append-only FactEvents)        │          │
│  │          + Pub-Sub Event Bus                         │          │
│  │  Tier 3: CKF (SQLite + all-MiniLM-L6-v2             │          │
│  │          + graph structure + community partitions)    │          │
│  └─────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 New Components

| Component | Purpose | Key Design |
|-----------|---------|-----------|
| `EnvelopeBuilder` | Pack facts into window context with CKF retrieval | Embedding-based relevance + graph walk + pattern query |
| `WarmStateStore` | Fact store with embeddings, lifecycle tracking, and event log | In-memory hot path (all reads); async SQLite WAL persistence (batch flush every 5 windows) + FactEvent log with snapshot compaction |
| `ExtractionPipeline` | Graduated 6-stage blackboard-reactive extraction | Self-calibrating escalation, cross-window awareness |
| `InformationFlowMonitor` | Measures fact yield per token, compound degradation | Multi-signal completion + degradation-triggered re-grounding |
| `ContinuationManager` | Physical-wall-only continuation with extraction envelopes | Replaces ALL 18 ad-hoc implementations |
| `WindowDAG` | Tracks window provenance — parents, children, facts | Enables debugging and rollback |
| `ContextualKnowledgeFabric` | Unified knowledge layer (Tier 3) — graph, patterns, semantics | Multi-mode retrieval, event-sourced, community-aware |
| `FactEventLog` | Append-only immutable event log for all fact lifecycle events | Temporal queries, state reconstruction, audit trail |
| `PubSubEventBus` | Decoupled event publication for warm state mutations | Subscribers: ANN index, community detector, telemetry |
| `HierarchicalProcessor` | Map-reduce-validate for Tier C/D scale inputs | Parallel segment processing, multi-level synthesis (02_CORE §11) |
| `CQSDetector` | Detects implicit context hunger from LLM output patterns | Hedging/placeholder/repetition detection, triggers envelope enrichment (02_CORE §12) |
| `CrossWindowValidator` | Three-tier consistency validation (CWCV) | Tier 1: extraction-only (always). Tier 2: binary LLM probes. Tier 3: full review (02_CORE §13) |
| `ReviewCycleManager` | Active LLM review cycles — planning, checkpoint, assessment | Model-capability-gated (auto-calibrating). Tier 1 always runs (02_CORE §14) |
| `ScaleModeSelector` | Auto-configure all CRP subsystems by quality tier | Selects serial/hierarchical, CQS, validation tiers, review frequency (02_CORE §15) |
| `QualityReporter` | Quality tier classification and degradation reporting | Every dispatch returns tier (S-D), degradation %, effective context estimate (02_CORE §10) |
| `SourceGroundingEngine` | Stores and retrieves original source passages alongside extracted facts | Dual-layer envelope: compressed facts + verbatim source text for high-relevance items (02_CORE §17) |
| `LLMContextCurator` | Periodic LLM-driven curation of what matters most | Dispatches curation windows; produces [LLM_SYNTHESIS] envelope section with progressive understanding (02_CORE §18) |
| `MetaLearningEngine` | Orchestrated Reasoning Chains + In-Context Meta-Learning + Reasoning Template Library | Decomposes complex tasks into micro-steps; scaffolds reasoning for weak models; stores successful patterns in CKF (02_CORE §19) |
| `ReasoningTemplateLibrary` | CKF-resident collection of successful reasoning traces | Stores, retrieves, and adapts reasoning patterns across sessions. Enables cross-session reasoning transfer (02_CORE §19.3) |
| `ResourceMonitor` | Runtime hardware/memory pressure detection | Measures RAM, VRAM, latency per window; classifies pressure level; triggers adaptive feature degradation (02_CORE §3.7.2) |
| `ResourceAllocator` | User-declared resource limits enforced at setup | Caps RAM, model memory, threads, process priority. Protocol throttles to fit — never exceeds allocation (02_CORE §3.7.1) |
| `ModelRegistry` | Singleton model registry — ONE instance per model type | Process-global. all-MiniLM, GLiNER, UIE, cross-encoder shared across all subsystems. LRU eviction under RAM ceiling (02_CORE §3.3) |
| `CrossEncoderCache` | Caches cross-encoder reranking results across windows | Avoids redundant 400ms reranking for unchanged (task, fact) pairs; 50-80% hit rate in continuation chains (03_ENVELOPE §3.3) |
| `OverheadBudgetManager` | Caps total protocol overhead windows as % of productive windows | Priority-based feature shedding when overhead exceeds budget; prevents additive overhead explosion (02_CORE §6.9) |
| `ColdStorageGC` | Cross-session garbage collection for Tier 3 | Relevance-decay scoring, two-phase tombstone/purge, storage budget enforcement with LRU eviction (02_CORE §6.7) |
| `EventLogSnapshotManager` | Periodic warm state snapshots for fast resume and log compaction | Snapshot every 50 windows; enables <1s session resume; truncates in-memory event log (02_CORE §3.3) |
| `ExtractionModelLifecycle` | Manages loading/unloading of extraction models (GLiNER, UIE, cross-encoder) | Lazy load on first need, unload after N idle windows, adaptive thresholds under memory pressure (02_CORE §3.3) |
| `IdleScheduler` | Defers heavy work to genuine system idle periods | Tracks user activity; CRP does zero CPU work while LLM is generating; processes work in 16ms slices during idle (02_CORE §16.1) |
| `CoalescedTimer` | Single timer loop for all periodic CRP operations | 1 wake-up/sec instead of ~50; checks which periodic tasks are due each tick (02_CORE §16.1) |
| `SessionBindingManager` | Protocol binding handshake and session key lifecycle | Derives ephemeral session keys via HMAC-SHA256; verifies request signatures; manages session expiry (02_CORE §22.2) |
| `InputValidator` | Structural validation + advisory injection detection | Unicode normalization, size limits, type safety, prompt injection pattern detection. Non-disableable structural checks (02_CORE §22.3) |
| `FactIntegrityChain` | DNSSEC-inspired provenance signing for extracted facts | BLAKE3 content hashing + HMAC chain signatures; tamper detection at envelope construction; quarantine on failure (02_CORE §22.4) |
| `IngestQuarantine` | Anti-poisoning defense for external data via `crp.ingest()` | Confidence penalty (×0.7), cross-reference validation, batch poisoning detection (>30% conflict → reject batch) (02_CORE §22.4.4) |
| `RBACEnforcer` | Role-based access control + rate limiting | OBSERVER/OPERATOR/ADMIN roles; per-session dispatch rate limits; ingest volume limits; DoS prevention (02_CORE §22.6) |
| `StateEncryptor` | AES-256-GCM encryption for cold state and event log at rest | HKDF-derived storage key from binding secret; key rotation; embedding salting for inversion protection (02_CORE §22.7) |
| `CRPError` | Base exception hierarchy for all CRP operations | 13 error codes (1001-1031) mapped to gRPC status equivalents; structured `details` dict; JSON-RPC error mapping for SDK transport (02_CORE §6.10.4) |
| `StreamEvent` | Discriminated union for streaming dispatch events | 6 event types (token, extraction, continuation, window_complete, done, error); sync Iterator + async AsyncIterator; token concatenation invariant (02_CORE §6.10.5) |
| `SessionHandle` | Return type from init() containing session metadata | session_id, protocol_version (SemVer), RBAC capabilities, session_key, expiry; version negotiation (02_CORE §6.10.8) |
| `PersistedStateHeader` | Schema version header for all persisted CRP data | schema_version (SemVer), protocol_version, creation timestamp, BLAKE3 checksum; enables forward migration (02_CORE §6.10.10) |
| `SessionLock` | Per-session write-lock for state-mutating operations | Serializes dispatch/ingest/configure within session; read operations concurrent; 30s acquisition timeout (02_CORE §23.2.1) |
| `CRPEventEmitter` | Structured event emission for observability | 30+ event types across 7 subsystems; JSON envelope with OpenTelemetry trace/span IDs; security events always emitted (02_CORE §24.2-24.3) |
| `MetricsExporter` | Time-series metrics for monitoring | Prometheus/OTLP/JSON export; 10 counters, 8 gauges, 6 histograms; `crp_` metric prefix (02_CORE §24.4) |
| `AuditLog` | Audit query and session reconstruction interface | Three-source audit (facts + events + security); session reconstruction; exportable audit bundles; SOC 2/GDPR/HIPAA/AI Act compliant (02_CORE §24.6) |
| `ConfigurationResolver` | Hierarchical configuration resolution | 5-layer hierarchy: defaults → env vars → config file → init() → configure(); JSON Schema validation; atomic runtime changes (02_CORE §25) |
| `LLMProviderManager` | Multi-provider LLM connection management | Provider auto-detection from endpoint URL; 3-format request adapters (OpenAI/Anthropic/Google); capability probing; fallback chains; tokenizer reconciliation (02_CORE §26) |
| `ProviderDiagnostic` | Connection diagnostics and troubleshooting | 6-step diagnostic sequence; 10 diagnostic codes; actionable human-readable suggestions; runs at init() and on-demand via diagnose() (02_CORE §26.3) |
| `RequestAdapter` | Wire format translation for LLM providers | Translates CRP internal completion requests to provider-specific HTTP requests; parses responses and streaming chunks; extensible for custom providers (02_CORE §26.5) |
| `HealthMonitor` | Session and provider health reporting | Liveness/readiness probes for sidecar mode; health() function for embedded; provider status, warm state size, uptime, extraction stage inventory (09_DEPLOYMENT §8) |

---

## 4. MIGRATION STRATEGY

### 4.1 Phase 0: Foundation (No LLM Changes)

Build CRP core. Wire passive telemetry to existing calls. **Zero behavior change.**

### 4.2 Phase 1: Agentic Loop (8 sites)

Migrate `phase_engine.py` tool selection — highest-value target. Each tool selection gets fresh context with full discovery state.

### 4.3 Phase 2: Report Generation (8 sites)

Each report section gets a dedicated window with section-specific findings. Continuation chains produce unbounded section length.

### 4.4 Phase 3: Planning & Reasoning (14 sites)

Planning and reasoning windows get semantically-scored envelopes.

### 4.5 Phase 4: Everything Else (57+ sites)

18 continuation sites → unified CRP continuation. 10 Knowledge/CKF sites → CRP with Contextual Knowledge Fabric integration. All remaining sites → `crp.dispatch()`.

---

## 5. FOR OTHER SYSTEMS

### 5.1 Mapping Your System

To apply CRP to ANY system that uses an LLM:

**Step 1: Find all LLM calls**
```bash
grep -rn "generate\|complete\|chat\|invoke" --include="*.py" | grep -i "llm\|model\|gpt"
```

**Step 2: Replace each with `crp.dispatch()`**
```python
# Every call site becomes:
response = crp.dispatch(system_prompt=SYSTEM_PROMPT, task_input=data)
```

**Step 3: Optionally add TaskIntent for structured output**
```python
# Only when you need grammar-constrained output:
response = crp.dispatch(
    system_prompt=SYSTEM_PROMPT,
    task_input=data,
    output_schema={"type": "object", ...}
)
```

**Step 4: Measure and observe**
```python
# Check saturation, information flow, extraction yield
telemetry = crp.get_session_telemetry()
```

### 5.2 Minimum Viable CRP

```python
class MinimalCRP:
    def __init__(self, llm, context_window_size, max_output_tokens=4096):
        self.llm = llm
        self.ctx_size = context_window_size
        self.max_output = max_output_tokens
        self.facts = []  # Warm state
    
    def dispatch(self, system_prompt, task_input):
        sys_tokens = self.llm.count_tokens(system_prompt)
        task_tokens = self.llm.count_tokens(task_input)
        available_input = self.ctx_size - self.max_output
        
        # Auto-ingest: if task input exceeds available space, chunk and extract
        if sys_tokens + task_tokens > available_input:
            self._auto_ingest(task_input)
            task_input = f"Process the ingested material. Original: {task_input[:300]}"
            task_tokens = self.llm.count_tokens(task_input)
        
        envelope_budget = available_input - sys_tokens - task_tokens
        
        # Build envelope — pack facts by recency until full
        envelope = ""
        for fact in reversed(self.facts):
            if self.llm.count_tokens(envelope + fact) <= envelope_budget:
                envelope += fact + "\n"
            else:
                break
        
        prompt = system_prompt + "\n\n" + envelope + "\n\n" + task_input
        output, finish_reason = self.llm.generate(prompt, max_tokens=self.max_output)
        
        # Extract facts (minimal: store output summary)
        self.facts.append(f"[Window {len(self.facts)}]: {output[:500]}")
        
        # Continuation: if the model hit the output limit and we need more
        while finish_reason == "length":
            cont_prompt = system_prompt + "\n\n" + envelope + "\n\nContinue from where you left off."
            cont_output, finish_reason = self.llm.generate(cont_prompt, max_tokens=self.max_output)
            output += cont_output  # Minimal stitching
            self.facts.append(f"[Continuation]: {cont_output[:500]}")
        
        return output
    
    def _auto_ingest(self, large_input):
        """Chunk large input and extract facts without LLM calls."""
        chunk_size = self.ctx_size // 2
        for i in range(0, len(large_input), chunk_size):
            chunk = large_input[i:i + chunk_size]
            self.facts.append(f"[Ingested chunk {i // chunk_size}]: {chunk[:500]}")
```

This ~40-line implementation captures CRP's core:
- Fresh window per call
- Envelope fills available space (with generation reserve)
- Auto-ingest for oversized input
- Continuation loop for unbounded output
- Facts accumulate
- No hardcoded budgets

---

## 6. SUMMARY: 87+ SITES → 1 PROTOCOL → ZERO CONFIGURATION

| Subsystem | Site Count | Continuation? | What Changes |
|-----------|-----------|---------------|------|
| Memory Management | 6 | Yes | Ad-hoc summaries → extraction-built envelopes |
| Planning & Execution | 8 | Mixed | Prompt concatenation → semantically-scored envelopes |
| Tool Selection | 8 | No | Fixed prompt → fresh window with full discovery state |
| Report Generation | 8 | Yes | Single-window generation → per-section windows with continuation |
| Reasoning & Agents | 6 | Mixed | Ad-hoc state → formal envelope transfer |
| Knowledge/CKF | 10 | Mixed | RAG-only → CKF multi-mode retrieval (graph walk + pattern query + semantic fallback) + extraction + envelope + cross-session graph persistence |
| Continuation | 18 | Yes | 18 ad-hoc implementations → 1 unified protocol |
| API Controllers | 7 | Yes | Direct LLM → CRP dispatch |
| Intent & Routing | 4 | No | Minimal change — already cheap windows |
| MCP/Subagents | 6 | No | Add inter-agent envelope transfer |
| Core Service | 5 | Yes | CRP-aware dispatch layer |

**Total: 86 sites, 1 protocol, zero task types, zero budgets, zero configuration.**
