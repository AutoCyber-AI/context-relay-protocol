<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 06 — Implementation Plan

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · [01 Research](01_RESEARCH_FOUNDATIONS.md) · [02 Core Protocol](02_CORE_PROTOCOL.md) · [03 Envelope](03_CONTEXT_ENVELOPE.md) · [04 Generation](04_TOKEN_GENERATION_PROTOCOL.md) · [05 Integration](05_SYSTEM_WIDE_INTEGRATION.md) · **06 Implementation**

> Concrete plan for implementing CRP in WASA AI — and a template for any system.
>
> v2.0 FINAL — All hardcoded values, task‑type enums, and zone budgets eliminated.

---

## 1. IMPLEMENTATION OVERVIEW

### 1.1 What We're Building

| Deliverable | Description | New/Modified |
|-------------|-------------|--------------|
| `wasa_ai/crp/` | New CRP package | **NEW** — 8 modules |
| `wasa_ai/crp/orchestrator.py` | Central CRP dispatch + window lifecycle + DAG management | NEW (~600 lines) |
| `wasa_ai/crp/envelope.py` | Envelope builder with semantic scoring and priority packing | NEW (~450 lines) |
| `wasa_ai/crp/warm_state.py` | In-memory fact store with embedding-based scoring | NEW (~350 lines) |
| `wasa_ai/crp/extraction_pipeline.py` | Graduated extraction: regex → statistical → GLiNER → UIE | NEW (~500 lines) |
| `wasa_ai/crp/continuation.py` | Envelope-based continuation with gap analysis | NEW (~350 lines) |
| `wasa_ai/crp/information_flow.py` | Marginal information flow measurement + completion detection | NEW (~250 lines) |
| `wasa_ai/crp/telemetry.py` | Window utilization, extraction quality, flow metrics | NEW (~200 lines) |
| `wasa_ai/crp/__init__.py` | Package init, public API: `dispatch()`, `get_telemetry()` | NEW (~40 lines) |
| `wasa_ai/crp/source_grounding.py` | Source passage storage, retrieval, and envelope integration | NEW (~300 lines) |
| `wasa_ai/crp/llm_curation.py` | LLM-driven context curation + progressive understanding | NEW (~250 lines) |
| `wasa_ai/crp/meta_learning.py` | ORC engine + ICML envelope builder + reasoning scaffold generator | NEW (~400 lines) |
| `wasa_ai/crp/reasoning_template_library.py` | RTL storage, retrieval, and adaptation using CKF | NEW (~200 lines) |
| `wasa_ai/crp/resource_manager.py` | ResourceAllocator, ResourceMonitor, ModelRegistry (singleton), OverheadBudgetManager, ExtractionModelLifecycle, CrossEncoderCache, ColdStorageGC, EventLogSnapshotManager, IdleScheduler, CoalescedTimer | NEW (~700 lines) |
| `wasa_ai/crp/security.py` | SessionBindingManager, InputValidator, FactIntegrityChain, IngestQuarantine, RBACEnforcer, StateEncryptor, SecurityConfig, SecurityFlags | NEW (~550 lines) |

**Total new code: ~5,140 lines in 15 files.**

Notable omissions from prior versions:
- **No `task_types.py`** — there is no TaskType enum. TaskIntent is a lightweight, all-optional dataclass defined in `orchestrator.py`.
- **No zone budget tables** — Maximum Context Saturation ($E = C - S - T$) replaces all fixed allocations.

### 1.2 Feature Flag

CRP is gated by a single boolean flag. There are no "phases" or per-task-type toggles — CRP is either active or not.

```python
# .env
CRP_ENABLED=false          # Master kill switch — false = all dispatch() falls through
CRP_LOG_ENVELOPES=true     # Log envelope contents for debugging
CRP_MAX_CONTINUATIONS=50   # Safety limit on continuation chains (the ONLY numeric config)

# Optional resource allocation overrides (all have safe auto-detected defaults)
# CRP_MAX_RAM_MB=512       # Max RAM CRP may use (default: 10% of available, cap 1GB)
# CRP_MAX_MODEL_RAM_MB=300 # Max RAM for loaded models (default: 60% of CRP RAM)
# CRP_MAX_THREADS=2        # Max background threads (default: min(cpu_count//2, 4))
# CRP_PROCESS_PRIORITY=below_normal  # "idle" | "below_normal" | "normal"

# Optional security overrides (all have safe defaults — zero-config works)
# CRP_BINDING_SECRET=<hex>  # Shared secret for protocol binding (default: auto-generated)
# CRP_SESSION_TIMEOUT=86400 # Max session duration in seconds (default: 24h)
# CRP_DEFAULT_ROLE=OPERATOR # OBSERVER | OPERATOR | ADMIN (default: OPERATOR)
# CRP_ENCRYPT_COLD_STATE=true  # AES-256-GCM encryption at rest (default: true)
# CRP_MAX_DISPATCH_RATE=60  # Max dispatch() calls per minute (default: 60)
# CRP_INGEST_QUARANTINE=1   # Quarantine windows for ingest() data (default: 1)
```

When `CRP_ENABLED=false`, all `crp.dispatch()` calls fall through to the existing direct LLM calls. Zero behavior change.

Resource allocation can also be set programmatically via `ResourceAllocation` at `Client()` creation (see 02_CORE §3.7.1). Environment variables are defaults; programmatic values override them.

The `CRP_MAX_CONTINUATIONS` value (default 50) is NOT a budget or tuning parameter — it is a runaway-prevention safety valve, analogous to a stack depth limit. It should never trigger under normal operation. If it does, it indicates a bug in the completion detection logic, and the system logs a warning.

---

## 2. PHASE 0: FOUNDATION (No LLM Changes)

**Objective**: Build the CRP core and wire passive telemetry. No production behavior changes.

### 2.1 Step 0.1 — TaskIntent (in orchestrator.py)

TaskIntent is NOT an enum. It is a declarative, all-optional structure that accompanies a dispatch call. The protocol derives everything it needs from the system prompt and task input — TaskIntent merely provides optional hints.

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TaskIntent:
    \"""All-optional declarative hints. Every field defaults to None/empty.\"""
    output_schema: dict[str, Any] | None = None   # JSON Schema for grammar-constrained output
    max_continuations: int | None = None           # Override safety limit for this call
    session_id: str | None = None                  # Group windows into a session
    metadata: dict[str, Any] = field(default_factory=dict)  # Arbitrary caller metadata
```

**What's NOT here:**
- No task type label (the protocol doesn't classify tasks)
- No zone budgets (Maximum Context Saturation computes these dynamically)
- No output reserve (the model generates freely until done or at the wall)
- No relevance weights (semantic scoring computes these from embeddings)
- No continuation policy (all windows can continue; completion detection decides)

### 2.2 Step 0.2 — Warm State Store

Create `wasa_ai/crp/warm_state.py`:

Core data model:
```python
@dataclass
class Fact:
    id: str                          # Unique identifier (UUID)
    content: str                     # The atomic fact text
    embedding: list[float] | None    # Embedding vector (computed lazily)
    source_window: str               # Which window produced this fact
    created_at: float                # Timestamp
    superseded_by: str | None = None # ID of fact that replaces this one
    seen_count: int = 0              # How many windows have seen this fact
    token_count: int = 0             # Cached token count
    confidence: float = 1.0          # Extraction confidence (from pipeline)
    extraction_stage: str = ""       # Which pipeline stage produced this fact
```

Core operations:
- `add_facts(facts)` — Append new facts, de-duplicate by embedding similarity
- `get_ranked_facts(task_embedding, budget_tokens)` — Score by semantic similarity + recency + novelty, return facts that fit budget
- `mark_seen(fact_ids, window_id)` — Track which windows consumed which facts
- `supersede(old_id, new_fact)` — Replace outdated fact with newer version
- `compute_embeddings(model)` — Batch-embed any facts missing vectors

**Scoring** (all self-calibrating, no hardcoded weights):

$$\text{score}(f) = \alpha \cdot \text{sim}(f, q) + \beta \cdot \text{recency}(f) + \gamma \cdot \text{novelty}(f)$$

Where $\alpha, \beta, \gamma$ are derived from the observed distribution of each signal within the current session — not from a config file. At session start, uniform weights ($\frac{1}{3}$ each). As extraction produces facts, the system observes which signal dimensions have wider variance (more discriminative power) and increases their weight proportionally.

### 2.3 Step 0.3 — Envelope Builder

Create `wasa_ai/crp/envelope.py`:

Implements the greedy priority packing algorithm from [03_CONTEXT_ENVELOPE.md](03_CONTEXT_ENVELOPE.md):

1. Measure $S$ (system prompt tokens) and $T$ (task input tokens)
2. Resolve generation reserve $G$: user-specified `max_output_tokens` → LLM provider's max → default `min(C // 4, 16384)`
3. Compute available input space: $A = C_{\text{physical}} - G$
4. **If $S + T > A$**: trigger auto-ingest (chunk input, extract facts into warm state, synthesize a smaller task reference)
5. Compute envelope budget: $E = A - S - T$
6. Embed the task input to get query vector $q$
7. Score ALL active facts against $q$ using warm state scoring
8. Greedy-pack facts in descending score order until $E$ is exhausted
9. Optionally pull from cold storage (vector DB) if budget remains
10. Format packed facts as structured text (no protocol metadata)

**Generation reserve ($G$)** ensures the model always has room to produce output. The envelope fills ALL remaining space after system, task, and generation reserve.

### 2.4 Step 0.4 — Graduated Extraction Pipeline

Create `wasa_ai/crp/extraction_pipeline.py`:

This is the protocol's **sole sensory system**. All information entering the warm state passes through this pipeline. There are NO per-task-type extraction rules — one pipeline handles all output formats.

```
Stage 1: Regex patterns
├── JSON key-value extraction
├── Structured list/table detection
├── URL/IP/hash/error code capture
└── Named patterns (email, CVE, port)

Stage 2: Statistical NLP (no model required)
├── TextRank for key sentence selection
├── TF-IDF for term importance scoring
├── BERTSum-style extractive summarization
└── Noun phrase extraction for entity candidates

Stage 3: GLiNER (lightweight NER, ~200MB)
├── Entity labels derived from task input noun phrases
├── Zero-shot entity recognition
└── Confidence-scored entity spans

Stage 4: UIE (Universal Information Extraction, ~400MB)
├── Full relation extraction
├── Event detection
├── Triggered only when Stage 3 confidence < threshold
└── Heaviest stage — skipped if earlier stages suffice
```

**Self-gating**: Each stage runs only if previous stages did not extract enough information. "Enough" is measured by marginal yield — if Stage 2 extracted 50 facts from a window output, Stage 3 may be skipped. The threshold self-calibrates from observed extraction patterns across the session.

**Bidirectional extraction**: The pipeline runs on BOTH the task input (to understand what the task needs) AND the window output (to capture what was produced). The delta between task-side entities and output-side entities feeds into gap analysis.

### 2.5 Step 0.5 — Information Flow Monitor

Create `wasa_ai/crp/information_flow.py`:

The protocol's completion detection system. Replaces all hardcoded weighted signals and threshold-based completion checks.

```python
@dataclass
class FlowMetrics:
    window_id: str
    new_facts_extracted: int         # Novel facts from this window
    repeated_facts: int              # Facts that duplicate existing warm state
    marginal_gain: float             # new / (new + repeated)
    gap_coverage: float              # % of task-input entities found in output
    cumulative_facts: int            # Total facts across all windows in chain
    flow_trend: list[float]          # marginal_gain history across recent windows
```

**Completion signal**: When `marginal_gain` drops below a self-calibrated floor (derived from observed session behavior, NOT a fixed threshold), the task is considered complete. The system also checks `gap_coverage` — if the task input mentioned entities that never appeared in any output, it flags potential incompleteness.

**No fixed thresholds**: The floor is the 10th percentile of observed `marginal_gain` values across all completed windows in the current session. At session start (no history), the system uses the physical window wall as the only stopping signal. After ~5 windows of observation, the self-calibrated floor activates.

### 2.6 Step 0.6 — Telemetry

Create `wasa_ai/crp/telemetry.py`:

Records per-window:
```python
@dataclass
class WindowMetrics:
    window_id: str
    chain_position: int              # Position in DAG
    parent_window: str | None        # DAG parent
    envelope_tokens: int
    envelope_budget: int             # E = C - S - T
    task_tokens: int
    system_tokens: int
    utilization: float               # (S + E + T) / C_physical
    generation_tokens: int           # Actual output tokens
    generation_speed: float          # tokens/second
    wall_time_ms: int
    continuation_triggered: bool
    extraction_stage_used: str       # Highest extraction stage invoked
    facts_extracted: int
    marginal_gain: float             # From information flow monitor
    gap_coverage: float              # From gap analysis
```

Stored in a rotating log file: `data/crp_telemetry.jsonl`.

### 2.7 Step 0.7 — Passive Wiring

Add telemetry hooks to existing LLM calls WITHOUT changing behavior:

```python
# In service.py generate method:
if crp_telemetry_enabled:
    telemetry.record_passive(
        caller=inspect.stack()[1],
        prompt_tokens=count_tokens(prompt),
        output_tokens=count_tokens(response),
        wall_time_ms=elapsed_ms
    )
```

This builds a dataset of current call patterns BEFORE any CRP migration.

**Phase 0 deliverables**: 9 new files, passive telemetry, zero behavior change.

---

## 3. PHASE 1: AGENTIC LOOP

**Objective**: Migrate `phase_engine.py` tool selection to CRP. Highest-impact target.

### 3.1 What Changes

The phase engine's `_execute_phase_agentic()` method currently:
1. Assembles a prompt with tool definitions + accumulated turn_results
2. Calls `llm.generate()` directly
3. Parses the tool selection from output
4. Executes the tool
5. Appends results to turn_results
6. Repeats

With CRP:
1. Orchestrator dispatches a window for tool selection
2. Envelope builder constructs envelope from warm state (accumulated discoveries ranked by semantic similarity to available tools)
3. Task zone contains available tool definitions
4. Window dispatched → LLM selects tool
5. Extraction pipeline captures: tool name, reasoning, parameters
6. Tool executes → results extracted as new facts → warm state updated
7. Next iteration: fresh window with envelope containing ALL discoveries, semantically ranked for the next decision

### 3.2 Key Code Changes

In `phase_engine.py`:
```python
# BEFORE:
prompt = self._build_tool_selection_prompt(phase, turn_results, available_tools)
response = await self.llm_service.generate(prompt, max_tokens=500)

# AFTER (zero configuration):
response = await crp.dispatch(
    system_prompt=self._get_tool_selection_system_prompt(phase),
    task_input=self._format_available_tools(available_tools)
)
```

The `turn_results` accumulator is replaced by the warm state store. Each tool execution's results are extracted as facts automatically. The protocol routes discoveries forward via semantically-scored envelopes — no manual result threading.

### 3.3 Validation

Run 5 pentest targets with CRP disabled vs enabled:
- Compare: number of unique tools selected
- Compare: relevance of tool choices to accumulated findings
- Compare: total agentic loop time
- Compare: tool selection accuracy (did it pick tools that found real vulnerabilities?)

Gate: CRP must match or exceed baseline on all metrics.

---

## 4. PHASE 2: REPORT GENERATION

**Objective**: Migrate report generation to CRP with dedicated windows per section.

### 4.1 What Changes

Currently, report generation:
- Stuffs ALL findings into one prompt
- Generates the entire report in one (possibly continued) LLM call
- Continuation is ad-hoc, with fixed overlap

With CRP:
- Each report section gets a dedicated window with a fresh context
- The envelope carries findings ranked by semantic relevance to each section's topic
- Continuation chains (if a section exceeds one window) use extraction-built envelopes — not raw text overlap
- The report structure is tracked in warm state as facts
- Information flow measurement detects when a section is complete

### 4.2 Report Generation Flow

```
1. PLANNING window: "Given these findings, outline report sections"
   → Output: section list with assigned findings per section
   → Extraction pipeline: captures section names, finding assignments

2. For each section:
   a. SECTION window: "Write section X"
      → Envelope: findings semantically matched to section topic
      → If section hits physical window wall → continuation
      → Continuation envelope: extraction-built summary of prior output + remaining findings
   b. Extraction: section content stored in warm state

3. SUMMARY window: "Write executive summary"
   → Envelope: all section summaries (extracted facts) + key findings
   → This window has the densest envelope — full report context
   → Information flow will be high (many entities to cover)

4. RECOMMENDATIONS window: "Write recommendations"
   → Envelope: all vulnerabilities + MITRE mappings
   → Gap analysis flags any vulnerabilities not addressed
```

### 4.3 Validation

Compare report quality:
- Same findings → compare output with evaluation criteria
- Check: section completeness, evidence inclusion, recommendation quality
- Check: continuation stitching quality (no duplicates, no gaps — verified by gap analysis)

---

## 5. PHASE 3: REMAINING SUBSYSTEMS

**Objective**: Migrate all remaining LLM call sites to CRP.

### 5.1 Planning Windows

Each planning call gets:
- Envelope: full target state, user constraints, prior plan (if replanning) — all semantically ranked
- Task: "Generate a pentest plan for target X" or "Adapt plan based on new findings"
- Output: structured plan (steps, tools, phases) — extraction captures each step as a fact

### 5.2 Reasoning Windows

Each reasoning call gets:
- Envelope: the relevant context ranked by semantic similarity to the analysis question
- Task: "Analyze this tool output" or "Evaluate this vulnerability"
- Output: structured analysis — extraction captures conclusions, severity assessments, evidence

### 5.3 Memory & Reflection Windows

Memory compilation and context compaction route through CRP:
- These are large-input windows (full conversation in task zone)
- The envelope carries: session metadata, prior memory entries, key decisions
- Output: compressed memory artifacts for cold storage (vector DB)
- Extraction is critical here — the extracted facts ARE the long-term memory

### 5.4 CKF Integration

Knowledge/CKF call sites route through CRP:
- Contextual Knowledge Fabric (Tier 3) queried via multi-mode retrieval BEFORE envelope construction
- Retrieval modes: graph walk (from seed facts), pattern query (structured matching), semantic fallback (ANN), community summary (holistic)
- Retrieved documents go in the task zone (not the envelope)
- The envelope carries: query context, prior conversation, intent — semantically scored
- Cross-session knowledge, graph structure, and community summaries are available to every window
- Event log records all CKF queries for audit and temporal analysis

### 5.5 Continuation Unification

Replace BOTH existing continuation systems (`continuation_manager.py` and `adaptive_continuation.py`) with `wasa_ai/crp/continuation.py`:
- Single continuation implementation using extraction-built envelopes
- No raw text overlap — each continuation window receives a semantically-scored envelope of extracted facts from prior windows in the chain
- Completion detection via marginal information flow (self-calibrated, no fixed thresholds)
- Maximum continuation safety limit (CRP_MAX_CONTINUATIONS, default 50)

---

## 6. FILE PLAN

### 6.1 New Files

```
wasa_ai/crp/
├── __init__.py              # Public API: dispatch(), get_telemetry()
├── orchestrator.py          # CRPOrchestrator, dispatch, DAG lifecycle, TaskIntent
├── warm_state.py            # WarmStateStore, Fact, embedding-based scoring
├── envelope.py              # EnvelopeBuilder, semantic scoring, priority packing, CKF integration
├── extraction_pipeline.py   # Graduated 6-stage blackboard-reactive extraction
├── information_flow.py      # Marginal information flow, gap analysis, completion detection
├── continuation.py          # Envelope-based continuation, degradation-triggered re-grounding
├── telemetry.py             # WindowMetrics, FlowMetrics, rotating log, chain degradation
├── context_scoring.py       # Embedding model management, similarity computation, self-calibrating weights
├── ckf/                     # Contextual Knowledge Fabric (unified knowledge layer)
│   ├── __init__.py          # CKF public API: ckf_retrieve(), pattern_query(), graph_walk()
│   ├── fabric.py            # ContextualKnowledgeFabric — orchestrates multi-mode retrieval
│   ├── graph_store.py       # Graph structure persistence (facts + edges + communities in Tier 3)
│   ├── pattern_index.py     # Content-addressable pattern matching index (tuple space)
│   ├── community_detector.py # Leiden algorithm community detection + summary generation
│   ├── event_log.py         # FactEventLog — append-only immutable event log, temporal queries
│   └── pubsub.py            # PubSubEventBus — decoupled event publication/subscription
├── models/                  # Data models
│   ├── fact.py              # Fact, FactEdge, FactGraph dataclasses
│   ├── events.py            # FactEvent, EventType enums
│   └── metrics.py           # WindowMetrics, FlowMetrics, ChainDegradation
├── benchmarks/              # Benchmark specification and runners
│   ├── extraction_yield.py  # Standard extraction yield benchmarks
│   ├── envelope_quality.py  # Envelope precision/recall benchmarks
│   ├── degradation_curve.py # Chain degradation curve validation
│   └── ckf_retrieval.py     # CKF multi-mode retrieval benchmarks
├── hierarchy/               # Hierarchical processing for Tier C/D (02_CORE §11)
│   ├── __init__.py          # Public API: hierarchical_dispatch()
│   ├── processor.py         # HierarchicalProcessor — map-reduce-validate orchestration
│   ├── chunker.py           # Structure-aware chunking for hierarchical segments
│   └── synthesizer.py       # Cross-segment synthesis and merge logic
├── review/                  # Active review cycles (02_CORE §13-14)
│   ├── __init__.py          # Public API: run_review_cycle(), assess_model_capability()
│   ├── tier1_extraction.py  # Tier 1: extraction-based validation (zero LLM cost, always active)
│   ├── tier2_binary.py      # Tier 2: LLM-targeted binary validation (works with 2B+ models)
│   ├── tier3_full.py        # Tier 3: full LLM review (requires 7B+ / strong reasoning)
│   ├── capability_probe.py  # Model capability assessment — self-calibrating tier selection
│   └── correction.py        # Correction pipeline — flag or auto-fix detected issues
├── cqs/                     # Context Query Signals (02_CORE §12)
│   ├── __init__.py          # Public API: detect_context_hunger()
│   ├── detector.py          # CQS pattern detection (hedging, placeholders, repetition)
│   ├── enrichment.py        # CQS response — targeted CKF retrieval and envelope injection
│   └── mgci.py              # Mid-Generation Context Injection
├── scale/                   # Scale-aware mode selection (02_CORE §15)
│   ├── __init__.py          # Public API: configure_session()
│   ├── classifier.py        # Quality tier classification (S/A/B/C/D)
│   ├── mode_selector.py     # Processing mode selection based on scale + model capability
│   └── reporter.py          # QualityReport generation — included in every dispatch response
├── security.py              # SecurityConfig, RBACEnforcer, InputValidator, FactIntegrityChain, StateEncryptor (02_CORE §22)
├── errors.py                # CRPError base + 13 typed error codes (02_CORE §6.10.4)
├── streaming.py             # StreamEvent, dispatch_stream(), dispatch_stream_async() (02_CORE §6.10.5)
├── types.py                 # SessionHandle, CostEstimate, EnvelopePreview, PersistedStateHeader (02_CORE §6.10.2, §6.10.10)
├── concurrency.py           # SessionLock, ModelRegistryLock, ColdStorageLock, lock ordering enforcement (02_CORE §23)
├── observability/           # Observability & audit subsystem (02_CORE §24)
│   ├── __init__.py          # Public API: emit_event(), get_metrics(), query_audit()
│   ├── events.py            # CRPEvent envelope, CRPEventEmitter, 30+ event type definitions
│   ├── metrics.py           # MetricsExporter: Prometheus/OTLP/JSON counters, gauges, histograms
│   ├── tracing.py           # OpenTelemetry span generation, W3C Trace Context propagation
│   ├── audit.py             # AuditLog: query interface, session reconstruction, audit bundles
│   └── retention.py         # LogRetentionPolicy: rotation, archival, encryption, security log retention
├── config.py                # ConfigurationResolver: 5-layer hierarchy, JSON Schema validation, env var mapping (02_CORE §25)
├── providers/               # Multi-provider LLM interface (02_CORE §26)
│   ├── __init__.py          # Public API: connect(), diagnose(), provider_chain()
│   ├── manager.py           # LLMProviderManager: auto-detection, capability probing, fallback chains
│   ├── diagnostics.py       # ProviderDiagnostic: 6-step diagnostic sequence, 10 diagnostic codes
│   ├── adapters.py          # RequestAdapter implementations: OpenAIChatAdapter, AnthropicAdapter, GoogleAdapter
│   ├── registry.py          # Known model registry: capabilities, tokenizers, context windows
│   └── tokenizers.py        # Tokenizer reconciliation: registry → provider API → character fallback
├── health.py                # HealthMonitor: liveness/readiness probes, provider status, session health (02_CORE §27.6)
```

### 6.2 Modified Files (by phase)

**Phase 0:**
- `service.py` — Add passive telemetry hook (5 lines)
- `.env` — Add CRP feature flags (3 lines)
- `config.py` — Add CRP config entries (6 lines)

**Phase 1:**
- `phase_engine.py` — Refactor 3 call sites to use `crp.dispatch()` (~50 lines changed)

**Phase 2:**
- `report_generator.py` — Refactor 3 call sites (~40 lines changed)
- `sectioned_generator.py` — Refactor 2 call sites (~30 lines changed)

**Phase 3:**
- `generator.py` — Refactor 2 call sites (~25 lines changed)
- `replanner.py` — Refactor 3 call sites (~35 lines changed)
- `llm_integration.py` — Refactor 2 call sites (~25 lines changed)
- `continuation_manager.py` — Deprecate (replaced by `crp/continuation.py`)
- `adaptive_continuation.py` — Deprecate (replaced by `crp/continuation.py`)
- Remaining ~57 sites — Add `crp.dispatch()` wrapper (~200 lines changed total)

### 6.3 Files NOT Modified

These files are untouched by CRP:
- `llama_server.py` — The raw LLM interface stays as-is; CRP calls through `service.py`
- `context_ingestion.py` — Already handles token counting; CRP uses it
- `input_pool.py` — The input pool feeds INTO CRP, doesn't need to change
- All non-LLM code (tools, schemas, VM management, SSH, etc.)

---

## 7. TESTING STRATEGY

### 7.1 Unit Tests

```
tests/crp/
├── test_warm_state.py          # Fact CRUD, scoring, superseding, embedding similarity
├── test_envelope.py            # Priority packing, budget adherence, saturation verification
├── test_extraction_pipeline.py # Per-stage extraction accuracy, self-gating, entity label derivation
├── test_information_flow.py    # Marginal gain calculation, gap analysis, self-calibration
├── test_continuation.py        # Envelope-based continuation, completion detection
├── test_context_scoring.py     # Embedding computation, weight self-calibration
├── test_orchestrator.py        # Dispatch flow, DAG construction, fallback behavior
├── test_review_cycles.py       # Tier 1-3 validation, model capability probing, correction pipeline
├── test_hierarchical.py        # Map-reduce-validate pipeline, cross-level synthesis
├── test_cqs_detector.py        # Context hunger detection patterns, enrichment response
├── test_scale_modes.py         # Quality tier classification, mode selection, session config
└── test_quality_reporter.py    # Quality report generation, tier accuracy
```

### 7.2 Integration Tests

- **Envelope saturation test**: Verify envelope uses 100% of available budget ($E = C - S - T$, no leftover) — property test
- **Continuation quality test**: Multi-window output maintains coherence without raw overlap — extraction-built envelopes carry forward all essential context
- **Fallback test**: When `CRP_ENABLED=false`, behavior matches pre-CRP exactly — zero regression
- **Extraction pipeline test**: Each stage produces valid facts; self-gating correctly skips unnecessary stages
- **Information flow test**: Completion detection fires at the right time — not too early (incomplete output), not too late (wasted windows)
- **Telemetry test**: All metrics recorded correctly for each window — including DAG relationships

### 7.3 End-to-End Tests

- **Pentest comparison**: Same target, CRP off vs on → compare tool selection, findings, report quality
- **Report quality**: Same findings → compare section completeness and prose quality
- **Performance**: CRP on vs off → measure total latency overhead (target: <5% increase from envelope construction + extraction)

---

## 8. ROLLOUT PLAN

| Week | Phase | Action | Risk |
|------|-------|--------|------|
| 1 | 0 | Build CRP core (9 files), add passive telemetry | None — no behavior change |
| 2 | 0 | Analyze telemetry, verify envelope saturation, validate extraction pipeline stages | None |
| 3 | 1 | Migrate phase_engine (3 sites), A/B test | Low — behind feature flag |
| 4 | 1 | Validate Phase 1, tune self-calibration bootstrap | Low |
| 5 | 2 | Migrate report generation (5 sites), test continuation quality | Medium — output quality matters |
| 6 | 3 | Migrate planning + reasoning + memory (20+ sites) | Medium |
| 7 | 3 | Migrate continuation systems, deprecate old managers | Medium — continuation is critical |
| 8 | 3 | Migrate remaining 40+ sites | Low per site, cumulative medium |

**Rollback**: Set `CRP_ENABLED=false` at any point to revert all behavior instantly. No data migration needed.

---

## 9. FOR OTHER SYSTEMS — IMPLEMENTATION TEMPLATE

### 9.1 Minimum Viable Implementation (Any Language)

```
1. Create a WarmStateStore (even a simple list of strings works for v0)
2. Create an EnvelopeBuilder:
   a. Measure system prompt + task input tokens
   b. Fill ALL remaining space with facts, ranked by relevance
   c. No output reserve — let the model generate freely
3. Create a dispatch function:
   a. Build envelope (step 2)
   b. Assemble prompt = system + envelope + task
   c. Call LLM
   d. Extract facts from output (even basic regex is sufficient to start)
   e. Update warm state
4. Replace every LLM call with dispatch()
5. Add continuation: if generation hits the physical window wall,
   run extraction on output so far, build a NEW envelope from extracted
   facts, and dispatch a continuation window
6. Add information flow measurement:
   a. Count novel vs repeated facts per window
   b. When marginal gain drops below observed floor, task is complete
7. Add telemetry to measure improvement
```

**Note**: You do NOT need to define task types, configure zone budgets, or write per-task extraction rules. The protocol derives everything from the content.

### 9.2 Zero-Config Quick Start

The simplest possible CRP integration:

```python
import crp

# Initialize once — auto-detects hardware, loads embedding model
client = crp.Client(llm_endpoint="http://localhost:8080/v1/completions")

# Every LLM call becomes this:
response = client.dispatch(
    system_prompt="You are a security analyst.",
    task_input="Analyze these nmap results: ..."
)

# That's it. CRP handles:
# - Envelope construction (semantic scoring, priority packing)
# - Extraction (graduated pipeline)
# - Continuation (if output hits the wall)
# - Completion detection (marginal information flow)
# - Fact management (warm state, deduplication, superseding)
# - Window DAG tracking (provenance, debugging)
```

### 9.3 Expected Benefits

Based on research ([01_RESEARCH_FOUNDATIONS.md](01_RESEARCH_FOUNDATIONS.md)):

| Metric | Expected Improvement | Mechanism |
|--------|---------------------|-----------|
| Tool selection accuracy | +20-40% | Fresh window, full discovery context in envelope |
| Report quality | +30-50% | Dedicated windows, section-specific envelopes |
| Output length capability | Unbounded | Chained generation with extraction-built envelopes |
| Context utilization | ~100% | Maximum Context Saturation fills every available token |
| Configuration effort | Zero | No task types, no budgets, no weights to tune |

### 9.4 Known Considerations

- **Prefill overhead**: Each window re-computes KV cache for the system prompt. Prompt caching mitigates this (supported by most inference engines).
- **Extraction pipeline size**: Full pipeline (GLiNER + UIE) requires ~600MB additional model memory. The pipeline self-gates — it only loads heavier stages when lighter stages are insufficient.
- **Cold start**: First window in a session has an empty envelope. This is by design — the system bootstraps from the task input. After one window, the extraction pipeline has populated the warm state and subsequent envelopes are rich.
- **Self-calibration bootstrap**: Self-calibrating weights and thresholds need ~5 windows of observation before they stabilize. During bootstrap, the system uses uniform weights and the physical window wall as the only stopping signal. This is safe — it simply means the first few windows may run slightly longer than optimal.

---

## 10. DEPENDENCY SUMMARY

### 10.1 Python Packages

| Package | Version | Purpose | Required? |
|---------|---------|---------|-----------|
| `sentence-transformers` | ≥2.0 | Embedding computation (all-MiniLM-L6-v2) | Yes |
## 11. CKF DATA MODELS

Core data models for the Contextual Knowledge Fabric implementation:

```python
# ===== Event Sourcing Models =====

class EventType(str, Enum):
    FACT_CREATED = "created"
    FACT_SUPERSEDED = "superseded"
    FACT_COMPACTED = "compacted"
    FACT_ARCHIVED = "archived"
    FACT_RESTORED = "restored"
    EDGE_ADDED = "edge_added"
    EDGE_REMOVED = "edge_removed"
    COMMUNITY_UPDATED = "community_updated"

@dataclass
class FactEvent:
    event_id: str                   # Monotonically increasing, globally unique
    timestamp: float                # Wall-clock time
    window_id: str                  # Producing window
    event_type: EventType
    fact_id: str                    # Target fact
    payload: dict                   # Event-type-specific data

# ===== Knowledge Fabric Models =====

@dataclass
class KnowledgeFabric:
    """Unified knowledge layer — the CKF instance."""
    graph: FactGraph                # Facts + typed edges
    event_log: FactEventLog         # Immutable event history
    pattern_index: PatternIndex     # Content-addressable fact index
    community_map: CommunityMap     # Leiden communities + summaries
    ann_index: ANNIndex             # HNSW embedding index
    pubsub: PubSubEventBus          # Event publication bus

@dataclass
class CommunityMap:
    """Community detection results from Leiden algorithm."""
    communities: dict[str, Community]     # community_id → Community
    fact_to_community: dict[str, str]     # fact_id → community_id

@dataclass
class Community:
    """A topic cluster in the fact graph."""
    community_id: str
    member_fact_ids: list[str]
    summary_text: str               # TextRank-generated summary of members
    summary_embedding: ndarray      # For semantic matching against tasks

@dataclass
class PatternIndex:
    """Content-addressable index for structured pattern queries."""
    by_category: dict[str, set[str]]        # category → fact_ids
    by_entity_type: dict[str, set[str]]     # entity_type → fact_ids
    by_relation_type: dict[str, set[str]]   # relation_type → fact_ids
    by_window_range: SortedList             # For temporal range queries
    by_community: dict[str, set[str]]       # community_id → fact_ids

@dataclass
class ChainDegradation:
    """Compound degradation tracking for continuation chains."""
    per_window: list[float]         # d_i values per window
    cumulative: float               # 1 - ∏(1 - d_i)
    last_reground_window: int       # Window index of last re-grounding
    threshold: float = 0.15         # Re-grounding trigger threshold

# ===== Quality Tier Models (02_CORE §10) =====

class QualityTier(str, Enum):
    S = "S"  # ≤ C tokens, lossless
    A = "A"  # C to 10C, < 5% degradation
    B = "B"  # 10C to 100C, 5-20% degradation
    C = "C"  # 100C to 1000C, 20-40% degradation, hierarchy required
    D = "D"  # > 1000C, > 40% base, offset by hierarchy

@dataclass
class QualityReport:
    """Returned with every dispatch response."""
    tier: QualityTier
    total_tokens_processed: int
    window_count: int
    chain_degradation: float        # 0.0 – 1.0
    effective_context_tokens: int    # C × (1 - degradation)
    processing_mode: str            # "serial" | "hierarchical" | "parallel"
    review_cycles_run: int
    hierarchy_levels: int           # 0 for serial, 1+ for hierarchical
    cqs_signals_detected: int       # Number of context hunger signals
    corrections_applied: int        # Number of auto-corrections

# ===== Review Cycle Models (02_CORE §13-14) =====

@dataclass
class ReviewCycleConfig:
    """Configuration for active review cycles."""
    enabled: bool = True
    tier_1_interval: int = 5        # Extraction-based validation every N windows
    tier_2_enabled: bool = True     # LLM-targeted binary validation
    tier_2_interval: int = 10
    tier_3_enabled: bool = True     # Full LLM review (auto-disabled for weak models)
    tier_3_interval: int = 20
    tier_3_min_model_capability: int = 3
    correction_mode: str = "flag"   # "flag" | "correct"
    max_correction_windows: int = 3

@dataclass
class ConsistencyIssue:
    """An issue found by cross-window validation."""
    type: str                       # numerical_contradiction, semantic_contradiction, etc.
    description: str
    severity: str                   # "low", "medium", "high"
    windows: list[int] = None
    confirmed: bool = False
    facts: list = None

@dataclass
class ValidationResult:
    """Result of a CWCV validation cycle."""
    tier: int                       # 1, 2, or 3
    issues: list[ConsistencyIssue]
    timestamp: float
    window_range: tuple[int, int]   # Windows validated

# ===== CQS Models (02_CORE §12) =====

@dataclass
class ContextHungerSignal:
    """Detected implicit LLM signal that more context is needed."""
    signal_type: str                # "hedging", "reference_miss", "repetition"
    strength: float                 # 0.0 to 1.0
    topic: str                      # Extracted topic of the hunger
    window_id: str
    token_offset: int               # Where in the generation the signal was detected

@dataclass
class EnrichmentRequest:
    """Request to enrich the next envelope with targeted context."""
    topic: str
    signal_type: str
    source_signal: ContextHungerSignal
    budget_tokens: int = 2000

# ===== Hierarchical Processing Models (02_CORE §11) =====

@dataclass
class HierarchicalPlan:
    """Plan for map-reduce-validate hierarchical processing."""
    total_tokens: int
    segment_count: int
    segment_size: int
    fan_in: int
    hierarchy_levels: int
    estimated_degradation: float    # d_chain(hierarchy_levels)
    processing_mode: str            # "hierarchical" | "hierarchical_multi_level"

# ===== Scale Mode Models (02_CORE §15) =====

@dataclass
class SessionConfig:
    """Auto-configured session parameters based on scale + model capability."""
    quality_tier: QualityTier
    processing_mode: str
    cqs_enabled: bool
    validation_tiers: int           # Max validation tier (1, 2, or 3)
    review_cycles_enabled: bool
    planning_window: bool
    hierarchical: bool
    re_grounding: bool
    model_review_capability: int    # Assessed via probe (1, 2, or 3)

# ===== Source Grounding Models (02_CORE §17) =====

@dataclass
class SourcePassage:
    """Original text passage that produced one or more extracted facts."""
    passage_id: str
    text: str                       # Verbatim original text
    source_window: int
    token_offset_start: int
    token_offset_end: int
    linked_fact_ids: list[str]
    token_count: int
    relevance_score: float = 0.0    # Set during envelope construction

# ===== LLM Curation Models (02_CORE §18) =====

@dataclass
class LLMSynthesis:
    """The LLM's own curated understanding, evolved progressively."""
    synthesis_id: str               # UUID
    text: str                       # The synthesis text
    window_index: int               # When produced
    supersedes: str | None          # Prior synthesis ID
    evolution_count: int = 1
    critical_findings: list[str] = None
    key_relationships: list[str] = None
    confidence: float = 1.0

@dataclass
class CurationConfig:
    """Configuration for LLM-driven context curation."""
    enabled: bool = True
    curation_interval: int = 5     # Every N windows
    max_synthesis_tokens: int = 1500
    progressive: bool = True       # Build on prior synthesis

# ===== Meta-Learning Models (02_CORE §19) =====

@dataclass
class ReasoningTrace:
    """A successful reasoning chain stored for future retrieval."""
    trace_id: str
    task_type: str
    task_summary: str
    steps: list                     # list[ReasoningStep]
    model_class: str                # "0.5B-1B", "2B-7B", "7B+"
    quality_score: float
    created_at: float
    usage_count: int = 0

@dataclass
class ReasoningStep:
    """One step in a successful reasoning chain."""
    step_description: str
    system_prompt_template: str
    expected_output_format: str
    scaffold_level: int             # 0 (none) to 3 (heavy)

@dataclass
class MetaLearningConfig:
    """Configuration for CRP Meta-Learning."""
    enabled: bool = True
    orc_enabled: bool = True
    orc_max_steps: int = 10
    orc_min_model_capability: int = 1
    icml_enabled: bool = True
    icml_max_examples: int = 3
    rtl_enabled: bool = True
    rtl_min_quality_for_storage: float = 0.7
    scaffold_level: str = "auto"    # "auto" | "none" | "light" | "heavy"
    curation_interval: int = 5

# ===== KV Cache Persistence Models (02_CORE §20 Tier 2) =====

@dataclass
class KVCacheSnapshot:
    """Snapshot of a model's KV cache from a specific window."""
    snapshot_id: str
    source_window: int
    kv_data: bytes                  # Serialized, compressed KV cache
    compression_ratio: float
    model_id: str
    context_tokens: int
    created_at: float

# ===== Resource Management Models (02_CORE §3.7, §6.7, §6.9, §16) =====

@dataclass
class ResourceAllocation:
    """User-declared resource limits. Set at Client creation.
    The protocol will NEVER exceed these — it throttles to fit."""
    max_ram_mb: int = 512
    max_cold_storage_mb: int = 500
    max_threads: int = 2
    process_priority: str = "below_normal"  # "idle" | "below_normal" | "normal"
    max_model_ram_mb: int = 300
    max_envelope_latency_ms: int = 2000
    max_extraction_latency_ms: int = 1000
    max_windows_per_minute: int = 0        # 0 = unlimited

@dataclass
class ResourceSnapshot:
    """Point-in-time resource measurement. Taken per window."""
    ram_available_mb: int
    ram_used_by_crp_mb: int
    envelope_latency_ms: float
    extraction_latency_ms: float
    gpu_vram_free_mb: int | None
    cold_storage_mb: float
    pressure_level: str             # "none" | "moderate" | "high" | "critical"

@dataclass
class EventLogSnapshot:
    """Periodic snapshot of warm state for fast recovery and log truncation."""
    snapshot_id: str
    window_id: str
    fact_graph_state: bytes
    ann_index_state: bytes
    embedding_cache: bytes
    timestamp: float
    event_count_at_snapshot: int

@dataclass
class ColdStoragePolicy:
    """Policy for cross-session garbage collection."""
    storage_budget_mb: int = 500
    stale_session_threshold: int = 50
    stale_age_days: int = 90
    relevance_decay_factor: float = 0.95
    min_facts_retained: int = 1000

@dataclass
class OverheadBudget:
    """Caps total protocol overhead across all features."""
    max_overhead_pct: float = 15.0
    current_overhead_windows: int = 0
    current_productive_windows: int = 0

@dataclass
class CrossEncoderCacheEntry:
    """Cached cross-encoder score for a (task, fact) pair."""
    task_hash: str
    fact_id: str
    score: float
    window_created: int

@dataclass
class ExtractionModelState:
    """Tracks loaded extraction models for lifecycle management."""
    model_name: str                 # "gliner", "uie", "cross_encoder"
    loaded: bool = False
    last_used_window: int = -1
    load_count: int = 0
    cumulative_latency_ms: float = 0
    memory_mb: float = 0           # Approximate resident memory

@dataclass
class ModelRegistryEntry:
    """Singleton model registry entry — one instance per model type."""
    model_name: str
    size_mb: float
    users: list[str]               # subsystems that use this model
    ref_count: int = 0
    instance: Any = None           # The actual loaded model (singleton)

# ===== Security Models (02_CORE §22) =====

@dataclass
class SessionBinding:
    """Protocol binding between application and CRP instance."""
    session_id: str                # UUID v4
    session_key: bytes             # HMAC-SHA256 derived, 32 bytes (NEVER serialized)
    app_id: str                    # registered application identifier
    created_at: float              # monotonic timestamp
    expires_at: float              # created_at + session_timeout_seconds
    capabilities: frozenset        # granted RBAC permissions
    max_dispatch_rate: int = 60    # requests per minute

@dataclass
class FactProvenance:
    """Integrity record for every extracted fact."""
    fact_hash: bytes               # BLAKE3(fact_text ‖ entity ‖ relation ‖ confidence)
    source_window_id: str          # window that produced this fact
    extraction_stage: int          # 1–6 (pipeline stage)
    extraction_timestamp: float
    source_passage_hash: bytes     # BLAKE3(original text span)
    chain_signature: bytes         # HMAC-SHA256(session_key, fact_hash ‖ parent_hashes)

@dataclass
class IngestProvenance:
    """Provenance for externally-ingested data (anti-poisoning)."""
    source_label: str              # caller-provided source identifier
    ingest_timestamp: float
    content_hash: bytes            # BLAKE3 of raw input
    trust_level: str = "UNVERIFIED"  # VERIFIED | UNVERIFIED
    quarantine_remaining: int = 1  # windows remaining in quarantine

@dataclass
class SecurityFlags:
    """Per-dispatch security observations. Included in QualityReport."""
    injection_markers_detected: int = 0
    injection_marker_details: tuple = ()  # ((offset, pattern_name, matched_text), ...)
    unicode_normalized: bool = False
    control_chars_stripped: int = 0
    input_truncated: bool = False
    integrity_violations: int = 0

@dataclass
class SecurityConfig:
    """Security configuration with safe defaults."""
    binding_secret: bytes | None = None     # None = auto-generate
    session_timeout_seconds: int = 86_400   # 24 hours
    structural_validation: bool = True       # LOCKED True — cannot disable
    injection_detection: bool = True         # advisory markers
    fact_chain_signing: bool = True
    ingest_quarantine_windows: int = 1
    ingest_default_trust: str = "UNVERIFIED"
    batch_poison_threshold: float = 0.3
    default_role: str = "OPERATOR"           # OBSERVER | OPERATOR | ADMIN
    max_dispatch_per_minute: int = 60
    max_ingest_bytes_per_minute: int = 100_000_000
    max_concurrent_sessions: int = 4
    encrypt_cold_state: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    key_rotation_sessions: int = 100
    embedding_salt: bool = True

@dataclass
class RBACPolicy:
    """Role-based access control."""
    role: str = "OPERATOR"                     # OBSERVER | OPERATOR | ADMIN
    max_dispatch_per_minute: int = 60
    max_ingest_bytes_per_minute: int = 100_000_000
    max_concurrent_sessions: int = 4
    allow_state_export: bool = False
    allow_session_reset: bool = False

# ── API Formalism Types (02_CORE §6.10) ──────────────────────

@dataclass(slots=True)
class CRPError(Exception):
    """Base error for all CRP operations (§6.10.4)."""
    code: int              # 1001-1031 per error code table
    message: str           # Human-readable description
    details: dict          # Error-specific structured data

@dataclass(slots=True)
class StreamEvent:
    """Events emitted during streaming dispatch (§6.10.5)."""
    event_type: str        # token | extraction | continuation | window_complete | done | error
    data: Any              # Type depends on event_type

@dataclass(slots=True)
class SessionHandle:
    """Returned by init() (§6.10.8)."""
    session_id: str                # UUID v4
    protocol_version: str          # SemVer "2.0.0"
    capabilities: frozenset        # granted RBAC permissions
    session_key: bytes             # HMAC-derived (NEVER serialized)
    created_at: float              # monotonic timestamp
    expires_at: float              # session timeout

@dataclass(slots=True)
class CostEstimate:
    """Pre-flight cost estimation (§6.10.2)."""
    estimated_windows: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float | None = None
    confidence: str = "medium"     # high | medium | low

@dataclass(slots=True)
class EnvelopePreview:
    """Dry-run envelope metrics (§6.10.2)."""
    total_tokens: int
    envelope_tokens: int
    generation_reserve: int
    facts_included: int
    facts_available: int
    saturation: float              # 0.0–1.0
```

---

| `pydantic` | ≥2.0 | Data validation for Fact, TaskIntent, metrics | Yes |
| `gliner` | ≥0.2 | Stage 3 NER extraction | Optional (degrades to Stage 2 if absent) |
| `uie-pytorch` | ≥0.1 | Stage 4 Universal IE | Optional (degrades to Stage 3 if absent) |
| `outlines` | ≥0.1 | Grammar-constrained generation (for user schemas) | Optional |

### 10.2 Models

| Model | Size | Purpose | Auto-download? |
|-------|------|---------|----------------|
| `all-MiniLM-L6-v2` | ~80MB | Embedding for semantic scoring | Yes |
| `GLiNER-base` | ~200MB | NER extraction | Yes (on first Stage 3 invocation) |
| `UIE-base` | ~400MB | Universal IE | Yes (on first Stage 4 invocation) |
 **Models are managed by the Singleton ModelRegistry** (02_CORE §3.3) — ONE instance per model type, shared across all subsystems. Models are unloaded after N idle windows (default: 20 for GLiNER/UIE, 10 for cross-encoder) to free resident memory. Under resource pressure, unload thresholds are reduced aggressively (see 02_CORE §3.7.2). Total loaded model memory is capped by `ResourceAllocation.max_model_ram_mb` (§3.7.1).
All models are loaded lazily — they are downloaded and loaded into memory only when their pipeline stage is first needed. If the model RAM ceiling would be exceeded, LRU eviction frees space; if still insufficient, the requesting stage degrades gracefully (e.g., GLiNER skipped → fall back to statistical extraction).

---

*Document version: 2.0 FINAL — Zero hardcoded values, zero task types, zero budgets.*
*Part of: Context Relay Protocol (CRP) specification.*
