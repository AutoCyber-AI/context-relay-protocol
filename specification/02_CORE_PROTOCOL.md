<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 02 — Core Protocol Specification

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · [01 Research](01_RESEARCH_FOUNDATIONS.md) · **02 Core Protocol** · [03 Envelope](03_CONTEXT_ENVELOPE.md) · [04 Generation](04_TOKEN_GENERATION_PROTOCOL.md) · [05 Integration](05_SYSTEM_WIDE_INTEGRATION.md) · [06 Implementation](06_IMPLEMENTATION_PLAN.md)

> The Context Relay Protocol (CRP) — v2.0 FINAL

### Conformance Language (RFC 2119)

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) and [RFC 8174](https://datatracker.ietf.org/doc/html/rfc8174).

- **MUST / SHALL / REQUIRED**: Absolute requirement. Implementations that violate a MUST are non-conformant.
- **SHOULD / RECOMMENDED**: Valid reasons to deviate exist, but implications MUST be understood.
- **MAY / OPTIONAL**: Truly optional. Omitting a MAY feature MUST NOT break interoperability.

### Notation Conventions & Language Neutrality

CRP is a **language-neutral protocol**. Implementations MAY be written in any programming language.

**Normative definitions** use three formats, in order of precedence:
1. **JSON Schema (Draft 2020-12)** — The canonical, machine-readable type definitions for all protocol-facing types. Found in §6.10.2 and the **CRP Type Catalog** (Appendix A). Any conflict between JSON Schema and other representations MUST be resolved in favor of JSON Schema.
2. **RFC 2119 prose** — Behavioral contracts, preconditions, postconditions, and invariants expressed in English with RFC 2119 keywords.
3. **Pseudocode blocks** — Algorithmic descriptions using the `INTERFACE` / `FUNCTION` notation defined below.

**Reference implementation** code blocks (marked with `python`) appear throughout the specification to illustrate intent and provide a concrete example. These are **informative, not normative** — they show *one* way to implement a requirement, not *the* way. Where a Python code block and a JSON Schema disagree, the JSON Schema is authoritative.

**Pseudocode conventions**:
```
INTERFACE Name:
  operation(param: Type, param2: Type?) -> ReturnType
  # Type?  = nullable / optional
  # Type[] = ordered sequence (JSON array)
  # Set<Type> = unordered collection of unique values (JSON array with uniqueItems)
  # Map<K, V> = key-value mapping (JSON object)
  # bytes = opaque binary data (base64-encoded in JSON)
  # enum("A", "B", "C") = value restricted to listed strings

FUNCTION name(param: Type) -> ReturnType:
  # Algorithmic steps described in prose or structured pseudocode

RECORD TypeName:
  field: Type           # required field
  field?: Type          # optional field (may be null/absent)
  field: Type = default # field with default value
```

**Type mapping across languages**:

| CRP Type | JSON Schema | Python | TypeScript | Rust | Go | C# |
|----------|-------------|--------|------------|------|----|----|
| `string` | `"type": "string"` | `str` | `string` | `String` | `string` | `string` |
| `integer` | `"type": "integer"` | `int` | `number` | `i64` | `int64` | `long` |
| `number` | `"type": "number"` | `float` | `number` | `f64` | `float64` | `double` |
| `boolean` | `"type": "boolean"` | `bool` | `boolean` | `bool` | `bool` | `bool` |
| `bytes` | `"contentEncoding": "base64"` | `bytes` | `Uint8Array` | `Vec<u8>` | `[]byte` | `byte[]` |
| `Type?` | `["type", "null"]` | `Type \| None` | `Type \| null` | `Option<Type>` | `*Type` | `Type?` |
| `Type[]` | `"type": "array"` | `list[Type]` | `Type[]` | `Vec<Type>` | `[]Type` | `List<Type>` |
| `Set<Type>` | `"uniqueItems": true` | `frozenset[Type]` | `Set<Type>` | `HashSet<Type>` | `map[Type]bool` | `HashSet<Type>` |
| `Map<K,V>` | `"type": "object"` | `dict[K, V]` | `Record<K, V>` | `HashMap<K, V>` | `map[K]V` | `Dictionary<K, V>` |
| `uuid` | `"format": "uuid"` | `str` (UUID v4) | `string` | `Uuid` | `string` | `Guid` |

---

## 1. DESIGN AXIOMS

These axioms are non-negotiable. Every protocol decision derives from them.

**Axiom 1 — Task Isolation**: Every LLM operation executes in its own **dedicated context window**. No window serves two masters.

**Axiom 2 — Maximum Context Saturation**: The context envelope between windows carries the **maximum information that fits** — not a fixed-size summary, not a budget-limited slice, but every token that can physically fit after accounting for generation space. The envelope is the residual: $E = C - S - T - G$, where $G$ = the generation reserve (the model's `max_output_tokens` or a user-specified cap). The envelope fills everything that isn't system prompt, task input, or generation reserve.

**Axiom 3 — Zero Interpretation Overhead**: Envelope contents must be structured so the LLM can **act on them directly** without parsing, interpreting, or re-analyzing. Pre-digested facts, not raw data.

**Axiom 4 — Model Ignorance**: The LLM does not know CRP exists. No protocol metadata, no self-annotation requests, no CRP_META blocks. The model receives a system prompt + context + task and produces output. All protocol intelligence lives in the orchestrator.

**Axiom 5 — Unbounded Capacity**: Total system throughput is $N \times C$ where $N$ = number of windows and $C$ = capacity per window. No fixed upper bound. No artificial budget or ceiling. However: unbounded throughput is not unlimited context fidelity. Effective context degrades with scale (see Section 10 — Quality Tiers). CRP is honest about this degradation and provides hierarchical processing (Section 11) plus active validation (Section 13) to bound it to $O(\log N)$ levels.

**Axiom 6 — Portability**: The protocol is independent of any specific model, framework, API, or application. It specifies interfaces, not implementations.

**Axiom 7 — Window Provenance**: Every window is a node in a directed acyclic graph (DAG). Envelopes carry the lineage of facts — which window produced them, which windows consumed them. This enables debugging, rollback, and reproducibility.

**Axiom 8 — Hardware-Adaptive Resource Efficiency**: The protocol adapts its resource usage to the available hardware (VRAM, RAM, CPU). Model loading, extraction pipeline stages, and concurrency levels self-configure based on detected capabilities. No hardcoded hardware assumptions.

**Axiom 9 — Output Integrity**: `dispatch()` ALWAYS returns the complete, unmodified LLM output. Extraction is a read-only side effect — it observes the output and stores facts, but NEVER modifies, filters, or summarizes the returned string. What the LLM generated is exactly what the caller receives. For continuation windows, the return value is the assembled output from all windows with minimal boundary cleanup: echo removal (when the continuation window repeats the tail of the prior window) and clean-boundary trimming (removing partial trailing fragments before the stitch point). Per-window raw outputs are always preserved in warm state for audit.

**Axiom 10 — LLM Amplification & Active Collaboration**: CRP does not replace the LLM — it **amplifies** it. The LLM performs ALL intellectual work (reasoning, analysis, generation). CRP's role is to **amplify context, scaffold reasoning, and collaborate actively**: build better prompts (envelopes), observe output (extraction), manage state (warm state), ground the LLM in original source passages (source-grounded envelopes), carry the LLM's own synthesis forward (progressive understanding), and orchestrate micro-reasoning steps that enable capabilities beyond the model's native ability (meta-learning scaffolds). No CRP component modifies LLM output. The extraction pipeline uses pattern matching and statistical NLP — not inference. However, the LLM **actively participates** in context curation: it decides what's most important to carry forward, it reviews its own output for consistency, and its accumulated synthesis evolves across windows as a form of in-context learning.

---

## 2. CORE CONCEPTS

### 2.1 Task Window

A **Task Window** is a single, isolated LLM invocation with its own context.

```
┌──────────────────────────────────────────────────┐
│ TASK WINDOW                                      │
│                                                  │
│  ┌──────────────┐  System Prompt & Role          │
│  │ System Zone  │  (Fixed or adapted per intent) │
│  └──────────────┘                                │
│  ┌──────────────┐  State from previous windows   │
│  │ Envelope Zone│  (Maximally saturated)         │
│  └──────────────┘                                │
│  ┌──────────────┐  The specific task input        │
│  │ Task Zone    │  (What to do NOW)              │
│  └──────────────┘                                │
│                       LLM generates freely       │
│                       until natural completion   │
│                       or physical window limit   │
└──────────────────────────────────────────────────┘
```

**Maximum Context Saturation formula:**

$$C_{\text{window}} = S + E + T + G$$

Where:
- $S$ = System zone (role, instructions) — measured, not budgeted
- $T$ = Task zone (specific input for this operation) — measured, not budgeted
- $G$ = Generation reserve — the space reserved for the LLM to actually write output
- $E$ = Envelope zone (state from prior windows) — **fills ALL remaining space**

$$E = C_{\text{physical}} - S - T - G$$

**Generation reserve ($G$)** is determined by:
1. If the user provides `max_output_tokens` in TaskIntent → $G$ = that value
2. If the LLM provider reports a `max_output_tokens` capability → $G$ = that value
3. Otherwise → $G$ = `min(context_window // 4, 16384)` — a conservative default that ensures the model always has generation room

**Why a generation reserve is mandatory**: Transformer models have a fixed sequence length that covers BOTH input and output. If 128K tokens of input are loaded, the model has 0 tokens to generate. Even models that advertise separate input/output budgets (e.g., API providers) have a physical combined limit. The generation reserve ensures the model always has room to write.

**What about "filling everything"?** CRP still maximally saturates the envelope — it fills every token that isn't system prompt, task input, or generation reserve. The difference from a naive approach is that CRP's envelope carries semantically-scored, extraction-built facts — not raw prior output. A 40K-token envelope carries more useful information than 100K tokens of raw text.

If the model finishes generating before exhausting $G$, the unused reserve is simply not used — no waste. If it reaches the limit defined by $G$ and the task isn't fulfilled, continuation is triggered automatically.

### 2.2 Context Envelope

A **Context Envelope** is the maximally-dense structured state transfer between task windows.

The envelope is NOT:
- A fixed-size "baton" (2K, 4K, etc.)
- A naive summary of previous output
- A budget-limited slice
- Protocol metadata for the model to interpret

The envelope IS:
- **Priority-packed**: The most relevant facts for the NEXT task are first
- **Semantically scored**: Contents ranked by semantic similarity to the incoming task, recency, and novelty — not by hardcoded category tables
- **Atomic**: Each fact is self-contained and actionable
- **DAG-tracked**: Every fact carries its provenance — which window produced it
- **Dynamically sized**: Fills all available space after system + task zones

**Envelope Priority Stack:**

```
PRIORITY 1 — Critical State (always included)
  Goal:          What is the system ultimately trying to achieve
  Current Phase: Where we are in the overall plan
  Blockers:      Anything that's failed or is preventing progress
  Constraints:   Safety rules, scope limits, user directives

PRIORITY 2 — Semantically Relevant Intelligence (scored and packed)
  All facts from warm state, scored by:
    - Semantic similarity to the incoming task (embedding cosine)
    - Recency (exponential decay from window age)
    - Novelty (facts not yet seen by any window score higher)
  Packed greedily until the envelope budget is exhausted.

PRIORITY 3 — Cold Storage Retrievals (if space remains)
  CKF results pulled from persistent knowledge fabric
  via graph walk, pattern query, or semantic fallback
  when relevant to the current task.
```

### 2.3 TaskIntent (Replaces Task Taxonomy)

**There is no task type enum.** Tasks are described, not categorized. The orchestrator uses a declarative **TaskIntent** — all fields optional:

```python
@dataclass
class TaskIntent:
    """Declarative description of what the caller wants. All fields optional."""
    
    system_prompt: str = ""          # Role and instructions for the LLM
    task_input: str = ""             # The specific input to process
    
    # Optional declarations — all derived or defaulted if omitted
    output_schema: dict | None = None       # JSON schema for structured output
    output_grammar: str | None = None       # GBNF grammar for constrained generation
    stop_sequences: list[str] | None = None # Custom stop tokens
    temperature: float | None = None        # Override default; None = model default
    expected_output_length: str | None = None  # "short" | "long" | None (auto)
    max_output_tokens: int | None = None    # User-imposed cap (optional override)
    max_continuations: int | None = None    # User-imposed safety limit (optional)
    
    # The orchestrator derives everything else from these declarations
    # and from observing the model's actual behavior.
```

**Why no task types:** A TaskType enum creates a hardcoded relevance matrix (tool_selection gets X scores, report_section gets Y scores). This means every new task type requires updating the matrix, the extraction rules, the zone budgets, the stop sequences, and the temperature table. TaskIntent eliminates all of this — the protocol observes what the task needs and adapts.

### 2.4 Window DAG

A **Window DAG** is a directed acyclic graph connecting task windows by their envelopes. Unlike a linear "chain," a DAG captures:
- **Fan-out**: One window spawning multiple parallel windows
- **Fan-in**: Multiple windows merging their facts into one
- **Continuation**: Sequential windows extending a single output

```
           ┌──────────┐
           │  Plan    │
           │  Window  │
           └────┬─────┘
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │ Scan A │ │ Scan B │ │ Scan C │    ← Fan-out (parallel)
   └────┬───┘ └────┬───┘ └────┬───┘
        │       │       │
        └───────┼───────┘
                ▼
           ┌──────────┐
           │ Analyze  │                 ← Fan-in (merge)
           │ Window   │
           └────┬─────┘
                │
           ┌────┴─────┐
           │ Report   │───▶ Report    ← Continuation (extend)
           │ Part 1   │    Part 2
           └──────────┘
```

Each node stores:
- `window_id`: Unique identifier
- `parent_ids`: Which windows contributed to this window's envelope
- `child_ids`: Which windows received facts from this window
- `facts_produced`: Facts extracted from this window's output
- `facts_consumed`: Facts that were in this window's envelope

This provenance enables:
- **Debugging**: "Why did window 15 make that decision?" → trace back through the DAG
- **Rollback**: Invalidate a window's facts and rebuild downstream envelopes
- **Analysis**: Which windows contributed the most to the final output?

### 2.5 The Orchestrator

The **Orchestrator** is the non-LLM component that:
1. Receives a task dispatch request (TaskIntent)
2. Constructs the context envelope using semantic scoring
3. Assembles the task window (system + envelope + task)
4. Dispatches the window to the LLM — model generates freely
5. Runs the extraction pipeline on the output (graduated: regex → statistical → NER → UIE)
6. Measures information flow (new facts per token)
7. Determines if continuation is needed (only at physical wall + task unfulfilled)
8. Updates the window DAG
9. Returns the output

The Orchestrator NEVER calls the LLM for orchestration decisions. It uses deterministic logic and the extraction pipeline's measurements. All intelligence about "what to do next" is encoded in observable signals, not LLM judgment.

---

## 3. THE CRP STATE MODEL

### 3.1 Four-Tier Memory Hierarchy

CRP defines four tiers of state, each with different lifetime and accessibility:

```
Tier 0 — ACTIVE CONTEXT (the current task window)
  Lifetime:  One LLM call
  Location:  LLM's KV cache
  Size:      Model's context window (e.g. 128K tokens)
  Access:    Full attention — peak quality

Tier 1 — HOT STATE (the context envelope)
  Lifetime:  One window transition
  Location:  Application memory (structured, scored facts)
  Size:      Adaptive — fills all space after system + task zones
  Access:    Injected into next window's envelope zone

Tier 2 — WARM STATE (session working memory)
  Lifetime:  One session / engagement
  Location:  In-memory (primary hot path) + persistent backend (async)
  Size:      Megabytes — all accumulated facts, full tool outputs
  Access:    Selectively retrieved by the orchestrator for envelope construction
  Hot path:  ALL lookups and scoring hit the in-memory cache ONLY.
             The persistence backend is NEVER on the read path for envelope construction.
  Persistence: Async batch flush every 5 windows or on session close.
             RECOMMENDED backend: SQLite WAL (reads never block writes,
             checkpoint when journal exceeds 10MB).
             CONFORMANT alternatives: JSON file, in-memory-only (no persistence).
             Implementations MUST keep reads in-memory; persistence backend is pluggable.

Tier 3 — COLD STATE (persistent knowledge)
  Lifetime:  Cross-session (with garbage collection — see §6.8)
  Location:  SQLite + vector store (sentence-transformers/all-MiniLM-L6-v2)
  Size:      Bounded by storage budget (default: 500MB, configurable)
  Access:    CKF retrieval (graph walk + pattern query + semantic fallback),
             triggered by orchestrator when relevant
  Persistence: Facts AND graph structure (edges, topology) are persisted together.
               Cross-session retrieval reconstructs subgraphs, not just flat fact lists.
```

**Information flows UP the hierarchy:**

$\text{Tier 3} \xrightarrow{\text{CKF query}} \text{Tier 2} \xrightarrow{\text{Envelope construction}} \text{Tier 1} \xrightarrow{\text{Window injection}} \text{Tier 0}$

**After each window completes, output flows DOWN through extraction:**

$\text{Tier 0 output} \xrightarrow{\text{Graduated extraction}} \text{Tier 2} \xrightarrow{\text{Persistence}} \text{Tier 3}$

**Context Enhancement Principle**: CRP does not merely extend context length — it **actively improves context quality** for every window, regardless of input size. Even a short prompt that fits entirely in a single window benefits from CKF enrichment: the orchestrator queries the knowledge fabric for facts relevant to the current task, injecting cross-session knowledge, prior discoveries, and relationship context that the LLM would not otherwise have access to. The envelope transforms a "cold start" into an informed continuation. This is the dual promise of CRP: **arbitrarily large** context capacity AND **better context** at every scale.

### 3.2 Envelope Construction Algorithm

The envelope for window $W_{n+1}$ is constructed from Tier 2 warm state using a **three-phase scoring pipeline** — not a single embedding comparison:

**Phase 1: Multi-Aspect Task Decomposition** — A single embedding of the task captures topical similarity but misses indirect relevance. A task about "SQL injection analysis" is *topically* close to facts about SQL, but a fact about "firewall allows outbound on port 3306" is *logically critical* yet *topically distant*. Multi-aspect decomposition solves this:

```
FUNCTION decompose_task_aspects(task_intent):
  """Break the task into semantic aspects for multi-vector scoring."""
  text = task_intent.system_prompt + " " + task_intent.task_input
  
  # Extract noun phrases as explicit aspects
  aspects = extract_noun_phrases(text)  # ["SQL injection", "vulnerability analysis", "database"]
  
  # Add implicit aspects via dependency expansion:
  #   For each noun phrase, include related terms from the task context
  #   "SQL injection" → also expand to "database access", "web application", "input validation"
  expanded = []
  for aspect in aspects:
    expanded.append(aspect)
    # Use the embedding model to find warm state facts similar to each aspect
    # This ensures facts related to SUB-ASPECTS of the task are captured
  
  # Compute one embedding per aspect
  aspect_embeddings = [embed(a) for a in expanded]
  
  # Also compute the full-task embedding (used as tie-breaker)
  full_embedding = embed(text)
  
  return aspect_embeddings, full_embedding
```

**Phase 2: Bi-Encoder Fast Scoring + ANN Retrieval** — For sessions with < 1,000 facts, score all facts directly. For sessions with > 1,000 facts, use an Approximate Nearest Neighbor (ANN) index to retrieve the top-K candidates in $O(\log N)$ before scoring:

```
FUNCTION construct_envelope(task_intent, available_tokens, warm_state):
  
  # 1. Always include critical state (+ fact graph relationships for critical facts)
  envelope = []
  envelope.append(warm_state.goal)
  envelope.append(warm_state.current_phase)
  envelope.append(warm_state.blockers)
  envelope.append(warm_state.constraints)
  tokens_used = count_tokens(envelope)
  
  # 2. Multi-aspect scoring
  aspect_embeddings, full_embedding = decompose_task_aspects(task_intent)
  
  # For large warm states, use ANN index for O(log N) retrieval
  if warm_state.fact_count() > 1000:
    candidates = warm_state.ann_index.query_multi(
      aspect_embeddings + [full_embedding],
      top_k=500  # Retrieve top-500 candidates across all aspects
    )
  else:
    candidates = warm_state.active_facts()
  
  scored_items = []
  for fact in candidates:
    # Multi-aspect score: MAX similarity across all aspects
    # This ensures a fact relevant to ANY aspect of the task scores high
    aspect_scores = [
      cosine_similarity(fact.embedding, ae) for ae in aspect_embeddings
    ]
    max_aspect_sim = max(aspect_scores) if aspect_scores else 0
    full_sim = cosine_similarity(fact.embedding, full_embedding)
    
    # Combined similarity: weighted blend favoring aspect match
    sim = 0.7 * max_aspect_sim + 0.3 * full_sim
    
    # Recency: more recent facts score higher (exponential decay)
    recency = exp(-0.1 * fact.age_in_windows)
    
    # Novelty: facts not yet consumed by any window get a boost
    novelty = 1.5 if fact.seen_count == 0 else (1.0 if fact.seen_count < 3 else 0.5)
    
    # Dependency bonus: if this fact has graph edges to already-high-scoring facts,
    # boost it. A fact about "firewall config" that is a DEPENDENCY of "MySQL access"
    # inherits relevance from the dependency relationship.
    dep_bonus = compute_dependency_bonus(fact, scored_items, warm_state.fact_graph)
    
    score = sim * recency * novelty + dep_bonus
    scored_items.append((score, fact))
  
  scored_items.sort(reverse=True, key=lambda x: x[0])
```

**Phase 3: Cross-Encoder Reranking (Precision Pass)** — Bi-encoder scoring (Phase 2) is fast but approximate. For the top candidates, apply a cross-encoder that processes each (task, fact) pair with full attention — dramatically improving relevance precision for nuanced relationships:

```
  # 3. Cross-encoder reranking of top candidates
  #    Cross-encoders process (query, document) pairs with full attention,
  #    capturing nuanced relevance that bi-encoders miss.
  #    Model: cross-encoder/ms-marco-MiniLM-L6-v2 (~80MB, ~500 pairs/sec on CPU)
  TOP_K_RERANK = 200  # Rerank top-200 candidates (budget: ~400ms on CPU)
  
  if len(scored_items) > TOP_K_RERANK:
    top_candidates = scored_items[:TOP_K_RERANK]
    rest = scored_items[TOP_K_RERANK:]
    
    # Cross-encoder produces fine-grained relevance scores
    task_text = task_intent.system_prompt + " " + task_intent.task_input
    rerank_pairs = [(task_text, fact.text) for _, fact in top_candidates]
    rerank_scores = cross_encoder.predict(rerank_pairs)  # batch prediction
    
    # Blend cross-encoder score with bi-encoder score
    # Cross-encoder is more accurate but doesn't account for recency/novelty
    reranked = []
    for i, (bi_score, fact) in enumerate(top_candidates):
      blended = 0.6 * rerank_scores[i] + 0.4 * bi_score
      reranked.append((blended, fact))
    
    reranked.sort(reverse=True, key=lambda x: x[0])
    scored_items = reranked + rest
  
  # 4. Dependency-aware graph packing
  #    When packing facts, also include their graph neighbors (up to 2 hops)
  #    if those neighbors aren't already selected. This ensures logical chains
  #    are preserved — not just individual facts.
  packed_fact_ids = set()
  for score, fact in scored_items:
    fact_text = format_fact_with_relations(fact, warm_state.fact_graph)
    fact_tokens = count_tokens(fact_text)
    if tokens_used + fact_tokens <= available_tokens:
      envelope.append(fact_text)
      tokens_used += fact_tokens
      packed_fact_ids.add(fact.id)
      
      # Pull in graph-connected facts that aren't already packed
      for edge in warm_state.fact_graph.edges_from(fact.id):
        if edge.target_id not in packed_fact_ids:
          dep_fact = warm_state.fact_graph.nodes.get(edge.target_id)
          if dep_fact:
            dep_text = f"  → [{edge.relation_type}] {dep_fact.text}"
            dep_tokens = count_tokens(dep_text)
            if tokens_used + dep_tokens <= available_tokens:
              envelope.append(dep_text)
              tokens_used += dep_tokens
              packed_fact_ids.add(edge.target_id)
    elif available_tokens - tokens_used > 50:
      compressed = compress_to_fit(fact, available_tokens - tokens_used)
      if compressed:
        envelope.append(compressed)
        tokens_used += count_tokens(compressed)
      break
  
  # 5. Bookend strategy: duplicate top-3 most relevant facts at the end
  #    Counters the "lost in the middle" effect (Liu et al., 2023)
  #    Primacy (beginning) + recency (end) = maximum recall
  bookend_facts = scored_items[:3]
  for score, fact in bookend_facts:
    fact_text = format_fact(fact)
    fact_tokens = count_tokens(fact_text)
    if tokens_used + fact_tokens <= available_tokens:
      envelope.append(fact_text)  # Duplicated at end
      tokens_used += fact_tokens
  
  # 6. If space remains, pull from cold storage (Tier 3) via CKF multi-mode retrieval
  if available_tokens - tokens_used > 500:
    ckf_results = ckf_retrieve(
      query=warm_state.current_goal,
      budget_tokens=available_tokens - tokens_used,
      modes=[
        # Mode 1: Graph walk — traverse edges from high-scoring warm facts into cold subgraphs
        GraphWalkRetrieval(seed_facts=packed_fact_ids, max_hops=2),
        # Mode 2: Pattern query — content-addressable retrieval by structured pattern
        PatternQueryRetrieval(entity_type=task_intent.noun_phrases, relationship_type=task_intent.action_verbs),
        # Mode 3: Semantic fallback — traditional embedding similarity (ANN) for anything modes 1-2 missed
        SemanticFallbackRetrieval(query_embedding=task_embedding, top_k_adaptive=True),
      ]
    )
    for result in ckf_results:
      result_text = format_ckf_result(result)
      result_tokens = count_tokens(result_text)
      if tokens_used + result_tokens <= available_tokens:
        envelope.append(result_text)
        tokens_used += result_tokens
  
  return format_envelope(envelope)


FUNCTION compute_dependency_bonus(fact, already_scored, fact_graph):
  """Facts that are graph-connected to high-scoring facts get a relevance boost."""
  bonus = 0.0
  for edge in fact_graph.edges_involving(fact.id):
    neighbor_id = edge.target_id if edge.source_id == fact.id else edge.source_id
    for score, scored_fact in already_scored[-50:]:  # Check last 50 scored facts
      if scored_fact.id == neighbor_id:
        # Boost proportional to the neighbor's score and the edge confidence
        bonus += score * edge.confidence * 0.3
        break
  return min(bonus, 0.5)  # Cap the bonus to prevent runaway inflation
```

**Key differences from v1**:
- **Multi-aspect scoring**: The task is decomposed into semantic aspects. A fact only needs to be relevant to ONE aspect to score high — eliminating the problem of topically-distant but logically-critical facts scoring low.
- **Cross-encoder reranking**: Top-200 candidates are re-scored using full-attention pairwise comparison (cross-encoder/ms-marco-MiniLM-L6-v2), which captures nuanced relevance relationships that bi-encoder cosine similarity misses.
- **Dependency-aware graph packing**: When a fact is packed into the envelope, its graph neighbors (conditions, causes, dependencies) are pulled in automatically. The envelope carries logical chains, not isolated facts.
- **ANN indexing**: For sessions with >1,000 facts, retrieval is $O(\log N)$ via approximate nearest neighbor index instead of $O(N)$ full scan.

### 3.3 Graduated Fact Extraction Pipeline

After each window completes, its output is processed by a **graduated extraction pipeline** — not per-task-type extraction rules. The pipeline has four stages, each more powerful and more costly:

```
STAGE 1 — Regex (always runs, ~1ms)
  Extracts: IP addresses, ports, CVE IDs, URLs, email addresses,
            JSON blocks, error codes, version strings
  Cost: Negligible
  Output: list[Fact] with category="structured_entity"

STAGE 2 — Statistical NLP (always runs, ~5ms)
  Extracts: Key sentences (TextRank), noun phrases, section headers,
            list items, numerical values with units
  Cost: CPU-bound, no model loading
  Output: list[Fact] with category="statistical_extraction"

STAGE 3 — GLiNER NER (runs when Stage 2 yield is low, ~50ms)
  Extracts: Named entities with TASK-DERIVED labels
  Labels: Noun phrases from task_intent → GLiNER entity types
  Example: task says "analyze vulnerabilities" → labels = ["vulnerability", "service", "exploit"]
  Cost: Small model (~200MB), lazy-loaded
  Output: list[Fact] with category="ner_entity"

STAGE 4 — UIE (runs when Stage 3 yield is low, ~100ms)
  Extracts: Relations and events between entities
  Example: "Apache 2.4.52 is vulnerable to CVE-2024-XXXXX" → (Apache 2.4.52, vulnerable_to, CVE-2024-XXXXX)
  Cost: Larger model (~400MB), lazy-loaded
  Output: list[Fact] with category="relation"

STAGE 5 — Discourse Structure Extraction (runs on reasoning-dense content, ~150ms)
  Detects: Content complexity via heuristic (see below)
  Extracts: Rhetorical/logical relations between text spans using RST-inspired parsing
  Relations: condition, cause-effect, contrast, elaboration, concession, dependency, sequence
  Example: "If Party A fails to deliver AND Party B has not waived..."
    → (Party_A_delivery_failure, CONDITION_FOR, breach_claim)
    → (Party_B_waiver, NEGATES, breach_claim)
  Implementation: Lightweight discourse parser (RST-style) using dependency tree heuristics
    + discourse markers ("if", "however", "because", "unless", "therefore", "although")
    + syntactic patterns (conditional clauses, relative clauses, subordination)
  Cost: CPU-bound parse tree analysis (~150ms), no model loading
  Output: list[FactEdge] with relation_type and (source_fact_id, target_fact_id)

STAGE 6 — LLM-Assisted Relational Extraction (optional, runs on high-complexity content)
  Purpose: When Stages 1-5 yield low relational coverage on dense reasoning text,
           dispatch a SMALL LLM window to extract logical structure.
  Trigger: Content complexity score HIGH (see below) AND Stage 5 edge yield < 0.1 edges/sentence
  Extraction prompt: "Extract the logical relationships, conditions, dependencies,
    and reasoning chains from this text. Output as structured fact-relationship pairs."
  Window: Uses a DEDICATED extraction window — NOT the task window.
    System prompt: extraction-specific (short, ~200 tokens)
    Task input: the text chunk being processed
    Gen reserve: small (512-1024 tokens — structured output only)
  Cost: One LLM call per chunk (the main cost trade-off for reasoning-dense content)
  Output: list[FactEdge] with relation_type and (source_fact_id, target_fact_id)
  
  NOTE: Stage 6 is the ONLY extraction stage that uses the LLM. It is optional,
  off by default, and only activates for content flagged as reasoning-dense where
  Stages 1-5 genuinely cannot capture the logical structure. For entity-rich
  content (logs, scan results, API responses), Stages 1-4 are sufficient and
  Stage 6 never triggers.

**Extraction Model Lifecycle Management**: Stages 3 (GLiNER, ~200MB) and 4 (UIE, ~400MB) load models lazily on first trigger and cache them for reuse. However, these models must not remain resident indefinitely when unused — especially on memory-constrained systems running a primary LLM model.

```python
@dataclass
class ExtractionModelState:
    """Tracks loaded extraction models for lifecycle management."""
    model: Any | None = None         # The loaded model (None = unloaded)
    last_used_window: int = -1       # Last window where this stage triggered
    load_count: int = 0              # How many times loaded (for telemetry)
    cumulative_latency_ms: float = 0 # Total inference time across session

EXTRACTION_MODEL_UNLOAD_RULES:
  Idle threshold:      20 windows since last trigger (configurable)
  Check frequency:     Every window (during extraction stage routing)
  Unload action:       del model; gc.collect(); torch.cuda.empty_cache() (if GPU)
  Re-load cost:        ~500ms for GLiNER, ~800ms for UIE (acceptable vs. holding 600MB)
  
  FUNCTION manage_extraction_models(warm_state, window_index):
    """Unload extraction models idle for too long. Called per window."""
    for stage in [stage_3_gliner, stage_4_uie]:
      if stage.model is not None:
        idle_windows = window_index - stage.last_used_window
        if idle_windows > EXTRACTION_MODEL_IDLE_THRESHOLD:  # default: 20
          stage.unload()  # Free 200-400MB
          stage.model = None
          log(f"Unloaded {stage.name} after {idle_windows} idle windows")
  
  ADAPTIVE BEHAVIOR:
    - Under memory pressure (see §3.7.2): reduce idle threshold to 5 windows
    - Under low memory: unload ALL optional models immediately
    - Under no pressure: increase idle threshold to 50 windows
    - Cross-encoder model follows the same lifecycle (80MB, idle threshold 10)
```
```

**Singleton Model Registry — One Instance Per Model, Period:**

CRP uses multiple ML models across different subsystems — but each model type must exist as exactly **ONE instance** in memory. No subsystem may load its own copy. This is the **Singleton Model Registry** pattern:

```python
class ModelRegistry:
    """Process-wide singleton. Every model has exactly ONE instance.
    All subsystems (extraction, envelope builder, cross-encoder) 
    share the same loaded model through this registry."""
    
    _instance: "ModelRegistry | None" = None   # singleton
    _models: dict[str, Any]                    # name → loaded model
    _ref_counts: dict[str, int]                # name → active users
    _states: dict[str, ExtractionModelState]   # name → lifecycle state
    
    @classmethod
    def get(cls) -> "ModelRegistry":
        """Return the single global registry. Create on first call."""
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance
    
    REGISTERED_MODELS = {
        "all-MiniLM-L6-v2":  {"size_mb": 80,  "users": ["envelope_builder", "warm_state", "ckf"]},
        "GLiNER-base":       {"size_mb": 200, "users": ["extraction_stage_3"]},
        "UIE-base":          {"size_mb": 400, "users": ["extraction_stage_4"]},
        "cross-encoder":     {"size_mb": 80,  "users": ["envelope_reranker"]},
    }
    
    def acquire(self, model_name: str, caller: str) -> Any:
        """Get a model reference. Loads lazily on first acquire.
        Returns the SAME instance to every caller — zero duplication."""
        if model_name not in self._models:
            # Check ResourceAllocation model RAM ceiling BEFORE loading
            allocated = sum(m.memory_mb for m in self._states.values() if m.loaded)
            model_size = REGISTERED_MODELS[model_name]["size_mb"]
            if allocated + model_size > resource_allocation.max_model_ram_mb:
                # Evict least-recently-used model to make room
                self._evict_lru(needed_mb=model_size)
                # If still insufficient after eviction, return None (skip the model)
                allocated = sum(m.memory_mb for m in self._states.values() if m.loaded)
                if allocated + model_size > resource_allocation.max_model_ram_mb:
                    return None  # Caller must handle graceful degradation
            self._models[model_name] = load_model(model_name)
            self._states[model_name].loaded = True
            self._states[model_name].load_count += 1
        self._ref_counts[model_name] = self._ref_counts.get(model_name, 0) + 1
        return self._models[model_name]
    
    def release(self, model_name: str, caller: str):
        """Release a model reference. Model stays loaded for reuse.
        Lifecycle (unload after idle) is managed by the resource monitor."""
        self._ref_counts[model_name] = max(0, self._ref_counts.get(model_name, 0) - 1)
    
    def _evict_lru(self, needed_mb: int):
        """Unload models by least-recently-used until needed_mb is freed."""
        candidates = sorted(
            [(n, s) for n, s in self._states.items() if s.loaded and self._ref_counts.get(n, 0) == 0],
            key=lambda x: x[1].last_used_window
        )
        freed = 0
        for name, state in candidates:
            if freed >= needed_mb:
                break
            self._unload(name)
            freed += state.memory_mb

SINGLETON MODEL RULES:
  1. No subsystem may call load_model() directly. ALL model access goes through ModelRegistry.get().acquire()
  2. The embedding model (all-MiniLM-L6-v2) is shared by:
     - EnvelopeBuilder (for scoring facts by similarity)
     - WarmState (for computing fact embeddings)
     - CKF (for semantic fallback retrieval)
     All three get the SAME instance. Zero duplication. Total: 80MB, not 240MB.
  3. If max_model_ram_mb cannot fit the requested model, the caller SKIPS the model.
     - GLiNER returns None → extraction falls back to Stage 2 (statistical)
     - UIE returns None → extraction falls back to Stage 3 (NER only)
     - Cross-encoder returns None → envelope uses bi-encoder scores only
  4. Model unloading is CENTRALIZED. Only ModelRegistry._evict_lru() or the
     resource monitor may unload models. No subsystem may del a model reference.
  5. ModelRegistry is process-global. Even if multiple Client instances exist,
     they share models. Reference counting prevents premature unloads.
```

**Content Complexity Detection**: Before extraction, the pipeline classifies content into three categories to route extraction strategy:

```
FUNCTION detect_content_complexity(text):
  # Linguistic complexity indicators
  discourse_markers = count_occurrences(text, [
    "if", "unless", "provided that", "however", "therefore", "because",
    "although", "whereas", "notwithstanding", "pursuant to", "subject to",
    "in the event that", "on condition that", "except where"
  ])
  avg_sentence_length = mean([len(sent.split()) for sent in sentences(text)])
  subordinate_clause_ratio = count_subordinate_clauses(text) / count_sentences(text)
  entity_density = count_entities_stage1(text) / count_tokens(text)
  
  # Classification
  if entity_density > 0.05:
    return ENTITY_RICH     # Logs, scan results, API data → Stages 1-4 sufficient
  elif discourse_markers / count_sentences(text) > 0.3 or subordinate_clause_ratio > 0.4:
    return REASONING_DENSE  # Legal, scientific, argumentative → Stages 1-5 + optional 6
  else:
    return NARRATIVE         # Reports, creative, descriptive → Stages 1-4 + Stage 5
```

**Fact Graph (Replacing Flat Fact Lists)**: Facts are no longer stored as a flat list. They form a **directed fact graph** where nodes are atomic facts and edges are typed relationships:

```python
@dataclass
class Fact:
    """Atomic unit of extracted knowledge."""
    id: str
    text: str
    _embedding: ndarray | None = None   # DEFERRED: computed on first need, not on extraction
    category: str                   # extraction stage that produced it
    source_window_id: str
    confidence: float
    # ... existing fields ...
    
    @property
    def embedding(self) -> ndarray:
        """Lazy embedding — computed only when needed for scoring.
        Facts superseded before their first envelope appearance NEVER get embedded,
        saving ~5ms per fact × 30-40% supersession rate = 20-40% embedding cost reduction."""
        if self._embedding is None:
            self._embedding = embed(self.text)  # ~5ms, cached permanently after
        return self._embedding
    
    @property
    def is_embedded(self) -> bool:
        """Check if embedding has been computed (for telemetry)."""
        return self._embedding is not None

@dataclass
class FactEdge:
    """Typed relationship between two facts."""
    source_id: str                  # Fact ID
    target_id: str                  # Fact ID
    relation_type: str              # "condition", "cause_effect", "dependency", "elaboration", etc.
    confidence: float
    source_stage: str               # Which extraction stage produced this edge

class FactGraph:
    """Graph of facts with typed edges — replaces flat fact lists."""
    nodes: dict[str, Fact]
    edges: list[FactEdge]
    
    def subgraph_for(self, seed_facts: list[str], max_hops: int = 2) -> "FactGraph":
        """Extract a connected subgraph starting from seed facts.
        Used for dependency-aware envelope packing (Section 3.2)."""
        visited = set(seed_facts)
        frontier = set(seed_facts)
        for hop in range(max_hops):
            new_frontier = set()
            for edge in self.edges:
                if edge.source_id in frontier and edge.target_id not in visited:
                    visited.add(edge.target_id)
                    new_frontier.add(edge.target_id)
                if edge.target_id in frontier and edge.source_id not in visited:
                    visited.add(edge.source_id)
                    new_frontier.add(edge.source_id)
            frontier = new_frontier
        return FactGraph(
            nodes={k: v for k, v in self.nodes.items() if k in visited},
            edges=[e for e in self.edges if e.source_id in visited and e.target_id in visited]
        )
    
    def serialize_for_envelope(self, facts: list[Fact]) -> str:
        """Serialize facts WITH their relationships for the envelope.
        Relationships are expressed as natural language annotations."""
        lines = []
        for fact in facts:
            lines.append(f"- {fact.text}")
            # Include outgoing relationships as indented sub-lines
            for edge in self.edges_from(fact.id):
                target = self.nodes.get(edge.target_id)
                if target and target in facts:
                    lines.append(f"  → [{edge.relation_type}] {target.text}")
        return "\n".join(lines)
```

**Why a fact graph matters**: For entity-rich content (pentesting, logs), flat facts work fine because each fact is self-contained. For reasoning-dense content (legal contracts, scientific papers, policy analysis), the *relationships* between facts ARE the information. "Party A must deliver by March 1" is a fact. "This delivery obligation is a condition for the payment clause in Section 4.2" is the relationship that gives the fact meaning. Without edges, the extraction captures the bricks but loses the architecture.

**Event-Sourced Fact Model**: Every mutation to warm state is recorded as an immutable **FactEvent** in an append-only event log. Facts are never silently overwritten — they are superseded by new events:

```python
@dataclass
class FactEvent:
    """Immutable record of a fact lifecycle event."""
    event_id: str                   # Unique, monotonically increasing
    timestamp: float                # Wall-clock time
    window_id: str                  # Which window produced this event
    event_type: str                 # "created" | "superseded" | "compacted" | "archived" | "restored"
    fact_id: str                    # The fact this event concerns
    payload: dict                   # Event-type-specific data
    #   created:    {text, embedding, category, confidence, edges: [...]}
    #   superseded: {superseded_by: fact_id, reason: str}
    #   compacted:  {cluster_id: str, summary_fact_id: str}
    #   archived:   {tier: 3, storage_key: str}
    #   restored:   {from_tier: 3, session_id: str}

class FactEventLog:
    """Append-only event log. Enables temporal queries and state reconstruction."""
    events: list[FactEvent]         # Ordered by event_id
    
    def state_at_window(self, window_id: str) -> FactGraph:
        """Reconstruct the fact graph as it existed when window_id executed.
        Replays all events up to and including that window's extraction."""
        # Enables: "What did we know when we made that analysis?"
        
    def facts_between(self, window_start: str, window_end: str) -> list[Fact]:
        """Return all facts created between two windows.
        Enables: gap analysis, drift detection, knowledge growth audit."""
        
    def supersession_chain(self, fact_id: str) -> list[FactEvent]:
        """Trace the full lifecycle of a fact through supersessions.
        Enables: understanding how knowledge evolved across windows."""
```

**Why event sourcing matters for CRP**: (1) **Temporal queries** — "What did we know at Window $N$?" enables retroactive analysis when later windows reveal that earlier conclusions were wrong. (2) **Audit trail** — every fact can be traced to its extraction window, every supersession to its cause. (3) **State reconstruction** — after a crash or session resumption, replay the event log to rebuild warm state exactly. (4) **Retroactive correction** — when a fact is discovered to be wrong in Window $N+10$, the event log records the correction without destroying the history of what the system believed at each point. This is inspired by Martin Fowler's Event Sourcing pattern where the log of changes IS the source of truth, not the current state.

**Event Log Compaction & Snapshots**: The append-only event log grows linearly with session length. For long sessions (500+ windows, 50,000+ events), unbounded growth creates memory pressure and slows temporal queries. CRP uses a **snapshot-and-truncate** pattern:

```python
@dataclass
class EventLogSnapshot:
    """Periodic snapshot of warm state for fast recovery and log truncation."""
    snapshot_id: str
    window_id: str                  # Window at which snapshot was taken
    fact_graph_state: bytes         # Serialized FactGraph (facts + edges + communities)
    ann_index_state: bytes          # Serialized HNSW index
    embedding_cache: bytes          # All cached fact embeddings
    timestamp: float
    event_count_at_snapshot: int    # How many events preceded this snapshot

class FactEventLog:
    # ... existing methods ...
    
    def snapshot(self, warm_state) -> EventLogSnapshot:
        """Create a point-in-time snapshot of the full warm state.
        Called every snapshot_interval windows (default: 50)."""
        snap = EventLogSnapshot(
            snapshot_id=uuid4(),
            window_id=warm_state.current_window_id,
            fact_graph_state=serialize(warm_state.fact_graph),
            ann_index_state=serialize(warm_state.ann_index),
            embedding_cache=serialize(warm_state.embeddings),
            timestamp=time.time(),
            event_count_at_snapshot=len(self.events)
        )
        # Persist snapshot to cold storage
        cold_storage.save_snapshot(snap)
        return snap
    
    def truncate_before_snapshot(self, snapshot: EventLogSnapshot):
        """Remove in-memory events older than the snapshot.
        Events are already persisted in cold storage for audit.
        Only the most recent events (since snapshot) stay in memory."""
        cutoff = snapshot.event_count_at_snapshot
        archived = self.events[:cutoff]
        cold_storage.archive_events(archived)  # Batch write to Tier 3
        self.events = self.events[cutoff:]      # Keep only recent events in RAM
    
    def restore_from_snapshot(self, snapshot: EventLogSnapshot) -> WarmState:
        """Fast session resume: load snapshot + replay only recent events.
        Target: <1 second resume for any session size."""
        warm_state = deserialize_warm_state(snapshot)
        # Replay only events AFTER the snapshot
        recent_events = cold_storage.load_events_after(snapshot.event_count_at_snapshot)
        for event in recent_events:
            warm_state.apply_event(event)
        return warm_state

SNAPSHOT_RULES:
  Interval:        Every 50 windows (configurable)
  Snapshot size:    ~2-5MB typical (fact graph + ANN index + embeddings)
  Events retained:  Only events since last snapshot (in memory)
  Older events:     Persisted in cold storage (available for audit queries)
  Resume time:      <1 second (snapshot load + replay 0-50 events)
  
  WHY 50 windows:
    - At 50 facts/window, snapshot captures ~2,500 facts (manageable)
    - Event replay of ≤50 windows takes <100ms
    - Snapshot itself takes ~200ms (serialization)
    - Memory savings: 95%+ of events moved to cold storage
```

**Blackboard-Reactive Extraction Model**: The extraction pipeline operates as a **blackboard architecture** (Erman et al., 1980). Warm state is the blackboard — a shared data structure visible to all extraction stages. Each extraction stage is a **knowledge source** that watches the blackboard and fires when its preconditions are met:

```
BLACKBOARD MODEL:
  Blackboard:        Warm state (facts + fact graph + event log)
  Knowledge Sources:  Extraction Stages 1-6
  Control Component: Content complexity router + yield monitor

  Reactive Escalation Rules:
    Stage 1 (regex)      → ALWAYS fires
    Stage 2 (statistical) → ALWAYS fires
    Stage 3 (GLiNER)      → fires when Stage 1-2 entity yield < self-calibrated baseline
    Stage 4 (UIE)         → fires when Stage 3 relation yield is low
    Stage 5 (discourse)   → fires when content is REASONING_DENSE or NARRATIVE
    Stage 6 (LLM)         → fires when Stage 5 edge yield < 0.1 edges/sentence AND content is REASONING_DENSE

  The key insight: stages react to blackboard state, not to a fixed sequence.
  If a Stage 1 regex extracts a CVE ID, and the blackboard already contains
  a vulnerability fact referencing that CVE from a prior window, Stage 4 (UIE)
  may trigger to extract the relationship — even if Stage 2-3 yields were normal.
  
  This is reactive escalation: the blackboard's state determines which knowledge
  sources fire, enabling cross-window awareness during extraction.
```

**Why blackboard matters for CRP**: Traditional pipeline extraction processes each window's output in isolation. Blackboard-reactive extraction allows stages to consider what the system already knows (the blackboard/warm state) when deciding what to extract and how deeply. A fact that seems unremarkable in isolation becomes critical when it connects to an existing knowledge cluster. The blackboard model formalizes this: extraction is not just "process this output" but "process this output given everything we already know."

**Self-calibrating escalation**: The pipeline doesn't always run all 6 stages. It measures the **fact yield** of each stage and only escalates when the yield is low. If regex + statistical extraction produce enough facts to maintain healthy information flow, GLiNER, UIE, discourse parsing, and LLM extraction don't load. No hardcoded `min_desired_facts` threshold — "enough" is defined by whether information flow rate (Section 4.3) is above the self-calibrated baseline.

**Escalation with content complexity routing**: Content classified as ENTITY_RICH skips Stages 5-6 entirely. Content classified as REASONING_DENSE runs Stage 5 automatically and triggers Stage 6 when edge yield is low. Content classified as NARRATIVE runs Stage 5 but not Stage 6 (narrative relationships are captured well enough by discourse markers without LLM assistance).

**Task-derived entity labels**: Instead of hardcoded domain-specific labels (e.g., "vulnerability", "port", "CVE"), the pipeline extracts **noun phrases from the task input** and uses those as GLiNER entity types. This makes extraction task-aware without any domain configuration.

**Post-extraction quality gate**: After extraction, before facts enter warm state, a three-tier quality gate runs:

1. **Structural validation**: If `output_schema` was provided and parsing fails, mark the window as FAILED. Extracted facts are flagged `low_confidence` and excluded from envelope priority packing unless space is abundant.
2. **Confidence threshold**: GLiNER and UIE produce confidence scores. Facts below the self-calibrating confidence floor (10th percentile of observed session confidences) are flagged as `low_confidence`.
3. **Anomaly detection**: If a window produces >5x the typical fact count, the extraction result is flagged for review. This catches extraction running on error messages or stack traces.

**Post-extraction normalization**: Facts are normalized to a target range of 10-80 tokens:
- Facts >100 tokens: attempt split at conjunction/comma/semicolon boundaries
- Facts <5 tokens: attempt merge with adjacent facts from the same extraction stage
- Facts 10-80 tokens: keep as-is

This is best-effort — the scoring algorithm already handles varying sizes.

### 3.4 Contradiction Detection

After extraction, each new fact is compared against warm state for potential supersession:

```
FUNCTION detect_contradictions(new_facts, warm_state):
  for new_fact in new_facts:
    for existing in warm_state.active_facts():
      similarity = cosine_similarity(new_fact.embedding, existing.embedding)
      if similarity > 0.85:
        # High embedding similarity = same topic
        content_diff = edit_distance(new_fact.text, existing.text) / max(len(new_fact.text), len(existing.text))
        if content_diff > 0.3:
          # Same topic but different content = potential supersession
          existing.superseded_by = new_fact.id
          existing.supersession_confidence = similarity * content_diff
          # Deprioritize in envelope scoring (0.5x multiplier)
          # but do NOT delete — LLM can reason about contradictions
```

### 3.5 Bidirectional Extraction and Gap Analysis

The extraction pipeline runs in **two directions**:

1. **Task-side extraction**: Analyze the `task_intent.task_input` to extract what was ASKED for — required fields, expected sections, enumerated items, topic keywords. This produces a **task requirements** set.

2. **Output-side extraction**: Analyze the LLM's output to extract what was PRODUCED — facts, entities, sections written, items enumerated. This produces an **output fulfillment** set.

3. **Gap analysis**: Compare requirements vs. fulfillment. The gap is what's missing. This gap directly feeds:
   - **Completion detection**: Gap zero → task fulfilled → stop
   - **Continuation envelopes**: Gap non-zero → include the gap explicitly in the next window's envelope

**Task Requirement Parsing** — The task-side extraction uses a three-level approach to reliably identify what the task requests, because pattern matching alone cannot reliably decompose natural language task descriptions:

```
FUNCTION extract_task_requirements(task_intent):
  """Extract structured requirements from the task description."""
  text = task_intent.system_prompt + " " + task_intent.task_input
  requirements = TaskRequirements()
  
  # LEVEL 1: Structural parsing (deterministic, always runs)
  #   Numbered lists: "1. Network layer 2. Application layer 3. Physical layer"
  #   Bullet lists: "- item A\n- item B\n- item C"
  #   Explicit section headers: "## Section: Network Analysis"
  #   Keyword patterns: "covering X, Y, and Z" → ["X", "Y", "Z"]
  #   "include" / "address" / "analyze" + noun phrases → required topics
  requirements.explicit = parse_explicit_requirements(text)
  
  # LEVEL 2: Semantic decomposition (NLP-based, always runs)
  #   Extract noun phrases as required topics
  #   Identify action verbs + their objects: "analyze vulnerabilities" → topic
  #   Group related noun phrases into requirement clusters
  requirements.semantic = extract_semantic_requirements(text)
  
  # LEVEL 3: LLM-assisted requirement decomposition (optional, for complex tasks)
  #   When Level 1+2 yield < 3 requirements AND the task text is > 200 tokens
  #   (indicating a complex task that wasn't simply enumerated), dispatch a SMALL
  #   LLM window to decompose the task into explicit requirements.
  if len(requirements.all()) < 3 and count_tokens(text) > 200:
    requirements.llm_decomposed = llm_decompose_requirements(task_intent)
    #   Prompt: "List the specific topics, sections, or items this task requires.
    #            Output as a numbered list."
    #   Window: tiny (system ~100 tokens, task ~300 tokens, gen ~500 tokens)
    #   Cost: one small LLM call — justified because incorrect gap analysis causes
    #         either premature termination (missing content) or infinite continuation
  
  return requirements


FUNCTION gap_analysis(task_intent, output_facts, requirements=None):
  """Compare task requirements against output fulfillment."""
  if requirements is None:
    requirements = extract_task_requirements(task_intent)
  
  # For each requirement, check if the output contains matching content
  fulfilled = []
  missing = []
  
  for req in requirements.all():
    req_embedding = embed(req.text)
    
    # Check: is there a fact in the output that covers this requirement?
    best_match_score = 0.0
    for fact in output_facts:
      sim = cosine_similarity(req_embedding, fact.embedding)
      best_match_score = max(best_match_score, sim)
    
    if best_match_score > 0.65:
      fulfilled.append(req)
    else:
      missing.append(req)
  
  return GapResult(
    fulfilled=fulfilled,
    missing=missing,
    gap_is_zero=(len(missing) == 0),
    confidence=len(fulfilled) / max(len(requirements.all()), 1)
  )
```

**Why three levels?** A task like "Write a comprehensive security analysis covering network, application, and physical layers with recommendations" contains 4 implicit requirements (3 layers + recommendations). Level 1 (structural parsing) catches them if they're in a list format. Level 2 (semantic decomposition) catches them via noun phrase extraction. Level 3 (LLM-assisted) catches them when the task description is complex and neither structural nor semantic parsing identifies > 3 requirements. The cost of one small LLM call is justified because incorrect gap analysis cascades into either missing content (stopping too early) or infinite continuation (never detecting completion).

### 3.6 Warm State Compaction

As sessions grow (50+ windows, 10,000+ facts), warm state must be actively managed to prevent envelope construction from becoming a bottleneck and to maintain signal-to-noise ratio in the fact pool.

**Compaction triggers when:**
- Fact count exceeds the **compaction threshold** (default: 5,000 facts)
- OR envelope construction time exceeds 500ms
- OR successive envelopes show declining relevance scores (top-scored facts are only weakly relevant)

```
FUNCTION compact_warm_state(warm_state, task_intent):
  """Reduce warm state fact count while preserving information."""
  
  # 1. Archive superseded facts → Tier 3
  #    Facts with superseded_by set are moved to cold storage
  for fact in warm_state.superseded_facts():
    warm_state.archive_to_cold(fact)
  
  # 2. Cluster related facts using embedding proximity
  clusters = hierarchical_cluster(warm_state.active_facts(), threshold=0.80)
  #   threshold=0.80: facts with cosine similarity > 0.80 are grouped
  
  # 3. For each cluster with >5 members, create a cluster summary
  for cluster in clusters:
    if len(cluster.members) > 5:
      # Merge: Keep the highest-confidence member as representative
      # Archive others with pointer to representative
      representative = max(cluster.members, key=lambda f: f.confidence)
      
      # Create a summary fact that captures the cluster's information
      summary_text = summarize_fact_cluster(cluster.members)
      summary_fact = Fact(
        text=summary_text,
        embedding=embed(summary_text),
        category="cluster_summary",
        source_window_id=representative.source_window_id,
        confidence=mean([f.confidence for f in cluster.members]),
        member_count=len(cluster.members),
        member_ids=[f.id for f in cluster.members]  # Audit trail
      )
      
      # Replace cluster members with summary + representative
      for member in cluster.members:
        if member.id != representative.id:
          warm_state.archive_to_cold(member)
      warm_state.add_fact(summary_fact)
  
  # 4. Rebuild ANN index (if used) for the reduced fact set
  if warm_state.fact_count() > 1000:
    warm_state.rebuild_ann_index()
  
  # 5. Compact fact graph: merge edges for archived facts
  warm_state.fact_graph.compact(archived_ids=warm_state.recently_archived_ids())
  
  # 6. Persist graph structure to Tier 3 (cross-session graph persistence)
  #    Edges and topology are archived WITH their facts — not discarded.
  #    When facts move to cold storage, their graph neighborhood moves with them.
  warm_state.persist_graph_to_cold(
    archived_ids=warm_state.recently_archived_ids(),
    include_edges=True,          # All edges involving archived facts
    include_community_ids=True   # Cluster/community membership for reconstruction
  )


FUNCTION summarize_fact_cluster(facts):
  """Create a summary of multiple related facts. CPU-only, no LLM."""
  # Strategy: keep the most information-dense sentences
  # TextRank on the cluster members to find the most representative
  sentences = [f.text for f in facts]
  ranked = textrank(sentences, top_k=3)
  return " | ".join(ranked)
```

**ANN Index Maintenance**: When warm state exceeds 1,000 facts, an HNSW (Hierarchical Navigable Small World) index is maintained over fact embeddings. This provides $O(\log N)$ approximate nearest neighbor queries instead of $O(N)$ full scan:

- **Index construction**: ~50ms for 5,000 facts (one-time cost per rebuild)
- **Query time**: ~1ms for top-100 retrieval (vs. ~50ms for brute-force at 5,000 facts)
- **Update cost**: O(log N) per fact insertion
- **Rebuild trigger**: After compaction, or when >20% of indexed facts have been archived

The ANN index is used by the envelope construction algorithm (Section 3.2) for the initial candidate retrieval phase. Cross-encoder reranking then refines the top candidates.

**Cross-Session Graph Persistence**: When facts are archived from Tier 2 to Tier 3 (via compaction or session end), their **graph structure is preserved**. In traditional implementations, cold storage flattens facts into isolated vectors — the edges, topology, and community structure are lost. CRP persists the complete graph neighborhood:

```
ARCHIVE UNIT (what gets persisted to Tier 3):
  fact:           The atomic fact (text + embedding + metadata)
  edges:          All FactEdges involving this fact (inbound + outbound)
  community_id:   Cluster/community membership (from Leiden community detection)
  community_summary: The cluster summary text (if this fact was part of a compacted cluster)
```

When a CKF query retrieves facts from Tier 3, it reconstructs the **subgraph**, not just the flat fact list. This means cross-session retrieval returns structured knowledge: "Port 3306 is open" AND "Port 3306 → MySQL service → vulnerable to CVE-2024-XXXX" — the chain of relationships that gives facts meaning.

**Community Detection (Leiden Algorithm)**: During compaction, the fact graph is partitioned into communities using the Leiden algorithm (Traag et al., 2019). This identifies natural topic clusters in the knowledge (e.g., "network topology facts", "vulnerability findings", "credential discoveries"). Each community gets a summary, enabling holistic queries: instead of retrieving individual facts, the CKF can retrieve community summaries when the task requires broad awareness. This is inspired by GraphRAG's (Microsoft, 2024) community-based summarization approach.

**CQRS Principle (Command Query Responsibility Segregation)**: Warm state maintains **separate optimized structures** for extraction (writes) and envelope construction (reads):

```
WRITE PATH (extraction → warm state):
  Append FactEvent to event log
  Insert Fact into mutable working set
  Insert FactEdges into adjacency index
  Publish event: "fact_created" / "fact_superseded" / "edge_added"

READ PATH (envelope construction ← warm state):
  Query ANN index for embedding similarity candidates
  Query adjacency index for graph-connected facts
  Query pattern index for content-addressable matches
  Merge results → score → rank → pack
```

The write path is optimized for append throughput (event log + adjacency insert). The read path is optimized for query diversity (ANN + graph + pattern). Neither path blocks the other.

### 3.7 User Resource Allocation & Runtime Resource Monitor

#### 3.7.1 User Resource Allocation (Setup-Time)

Before any protocol operation begins, CRP allows the user to **declare hard resource limits**. The protocol NEVER exceeds these limits — it **slows down, sheds features, and degrades gracefully** rather than consuming more than allocated. This is CRP's fundamental contract with the host system: **the user's machine comes first**.

```python
@dataclass
class ResourceAllocation:
    """User-declared resource limits. Set at Client creation.
    The protocol will NEVER exceed these — it throttles to fit."""
    
    # Memory limits
    max_ram_mb: int = 512            # Max RAM CRP may use (warm state + models + caches)
    max_cold_storage_mb: int = 500   # Max disk for Tier 3 cold storage
    
    # CPU limits  
    max_threads: int = 2             # Max background threads for CRP work
    process_priority: str = "below_normal"  # "idle" | "below_normal" | "normal"
    
    # Model limits
    max_model_ram_mb: int = 300      # Max RAM for ALL loaded models combined
    
    # Timing limits
    max_envelope_latency_ms: int = 2000    # If envelope takes longer, shed features
    max_extraction_latency_ms: int = 1000  # If extraction takes longer, skip stages
    
    # Operational limits  
    max_windows_per_minute: int = 0  # 0 = unlimited (bounded only by LLM speed)

# Usage at Client creation — zero-config by default, explicit when needed:
client = crp.Client(
    llm_endpoint="http://localhost:8080",
    # Default: auto-detect system resources, allocate conservatively
)

client = crp.Client(
    llm_endpoint="http://localhost:8080",
    resource_allocation=ResourceAllocation(
        max_ram_mb=256,           # "I only have 8GB total, LLM needs most of it"
        max_model_ram_mb=100,     # "Only load tiny models or none at all"
        max_threads=1,            # "Single-threaded background work only"
        process_priority="idle",  # "I don't want to notice CRP at all"
    )
)
```

**Allocation Enforcement — The Throttle Contract:**

```
RULE 1 — RAM CEILING:
  CRP tracks its own memory footprint (warm state + loaded models + caches).
  If approaching max_ram_mb:
    1. Unload idle extraction models immediately (free 200-400MB)
    2. Shrink hot cache (reduce hot fact limit)
    3. Flush warm state to cold storage earlier
    4. Reduce ANN index size (cap top-k)
    5. NEVER allocate beyond the ceiling — drop features instead
    
RULE 2 — MODEL RAM CEILING:
  Total loaded model memory must stay under max_model_ram_mb.
  If a model load would exceed the ceiling:
    1. Unload least-recently-used model first
    2. If still insufficient, SKIP the model stage entirely
    3. Extraction degrades: skip GLiNER → skip UIE → regex-only
    4. Envelope degrades: skip cross-encoder → bi-encoder only
    
RULE 3 — THREAD CEILING:
  Background work (extraction, embedding, community detection) uses at most max_threads.
  All CRP work shares a single bounded ThreadPoolExecutor(max_workers=max_threads).
  If all threads are busy, new work queues — it does NOT spawn more threads.

RULE 4 — PROCESS PRIORITY:
  At Client creation, CRP sets its process/thread priority.
  "idle":         Windows: IDLE_PRIORITY_CLASS, Linux: nice 19
                  CRP gets CPU ONLY when nothing else wants it.
                  Impact: user-invisible, but operations may take 2-5x longer.
  "below_normal": Windows: BELOW_NORMAL_PRIORITY_CLASS, Linux: nice 10
                  CRP yields to all normal-priority processes.
                  Impact: <2% visible CPU during user activity.
  "normal":       OS default. CRP competes equally for CPU.
                  Impact: fastest CRP, but may be noticeable.

RULE 5 — LATENCY CEILINGS:
  If envelope construction exceeds max_envelope_latency_ms:
    → Immediately shed cross-encoder, source grounding, community boost
    → Next window starts with degraded but fast envelope
  If extraction exceeds max_extraction_latency_ms:
    → Skip remaining stages, keep what's extracted so far
    → Log which stages were skipped for telemetry

RULE 6 — GRACEFUL DEGRADATION GUARANTEE:
  At EVERY resource limit, CRP degrades QUALITY, never AVAILABILITY.
  dispatch() ALWAYS returns a result — even if the envelope contains
  zero context facts and extraction captured nothing.
  The MINIMUM viable CRP operation is:
    1. Pass system_prompt + task_input to LLM (zero envelope)
    2. Capture output (zero extraction)
    3. Return output unchanged
  This costs exactly 0 bytes of RAM beyond the allocati on, 0 threads,
  and is functionally transparent — the LLM call works as if CRP didn't exist.
```

**Default Allocation (Auto-Detect):**

When no `ResourceAllocation` is provided, CRP auto-detects the system and allocates conservatively:

```
FUNCTION auto_detect_allocation() -> ResourceAllocation:
  total_ram = os.sysinfo().total_ram_mb
  available_ram = os.sysinfo().available_ram_mb
  cpu_count = os.cpu_count()
  
  # Conservative: use at most 10% of available RAM, capped at 1GB
  max_ram = min(available_ram * 0.10, 1024)
  
  # Models: at most 60% of CRP's RAM budget
  max_model_ram = max_ram * 0.60
  
  # Threads: 2 on ≤4 cores, 4 on >4 cores, never more than half the cores
  max_threads = min(max(cpu_count // 2, 2), 4)
  
  # Priority: below_normal always (user's work takes precedence)
  priority = "below_normal"
  
  return ResourceAllocation(
    max_ram_mb=int(max_ram),
    max_model_ram_mb=int(max_model_ram),
    max_threads=max_threads,
    process_priority=priority
  )
```

#### 3.7.2 Runtime Resource Monitor

Axiom 8 ("Hardware-Adaptive Resource Efficiency") demands adaptation not just at session start but **during execution**. The resource monitor detects system pressure and triggers adaptive degradation of protocol overhead — analogous to TCP congestion control for CRP features. The monitor enforces the `ResourceAllocation` limits and additionally responds to OS-level pressure (other processes competing for resources).

```python
@dataclass
class ResourceSnapshot:
    """Point-in-time resource measurement. Taken per window."""
    ram_available_mb: int           # OS-reported available RAM
    ram_used_by_crp_mb: int         # Warm state + models + caches
    envelope_latency_ms: float      # Last envelope construction time
    extraction_latency_ms: float    # Last extraction pipeline time
    gpu_vram_free_mb: int | None    # None if no GPU
    cold_storage_mb: float          # Current Tier 3 size

class ResourcePressureLevel(Enum):
    NONE = "none"           # All features enabled
    MODERATE = "moderate"   # Shed expensive optional features
    HIGH = "high"           # Aggressive shedding
    CRITICAL = "critical"   # Minimum viable protocol only

FUNCTION assess_resource_pressure(snapshot: ResourceSnapshot) -> ResourcePressureLevel:
  """Classify current resource pressure."""
  
  # RAM pressure
  if snapshot.ram_available_mb < 512:
    return CRITICAL
  if snapshot.ram_available_mb < 1024:
    return HIGH
  if snapshot.ram_available_mb < 2048:
    return MODERATE
  
  # Latency pressure (envelope construction taking too long)
  if snapshot.envelope_latency_ms > 2000:
    return HIGH
  if snapshot.envelope_latency_ms > 1000:
    return MODERATE
  
  return NONE

ADAPTIVE DEGRADATION BY PRESSURE LEVEL:

| Feature | NONE | MODERATE | HIGH | CRITICAL |
|---------|------|----------|------|----------|
| Cross-encoder reranking | ON (400ms) | ON with caching | OFF (bi-encoder only) | OFF |
| Source grounding | Full budget | Half budget | Top-3 facts only | OFF |
| GLiNER/UIE models | Normal unload (20 win) | Aggressive unload (5 win) | Immediate unload | Never load |
| Community detection | Normal batching | Skip if <20% changed | OFF | OFF |
| Curation windows | Normal interval | Double interval | Quadruple interval | OFF |
| ORC reasoning chains | Normal | Max 3 steps | Max 2 steps | OFF (single window) |
| ANN top-k retrieval | Adaptive (20-200) | Cap at 50 | Cap at 20 | Cap at 10 |
| Event log snapshots | Every 50 windows | Every 25 windows | Every 10 windows | Every 5 windows |
| Review cycles (Tier 3) | Normal | Skip if overhead >10% | OFF | OFF |

IMPLEMENTATION:
  - ResourceMonitor runs at the START of each window (before envelope construction)
  - Takes <1ms (OS system calls for RAM, cached GPU query)
  - Updates session-level pressure state
  - All CRP subsystems check pressure level before executing expensive operations
  - Pressure transitions are logged for telemetry
  - Hysteresis: must see 3 consecutive windows at a level before downgrading features
                must see 5 consecutive windows recovered before upgrading features
```

### 3.8 Contextual Knowledge Fabric (CKF)

> **Architectural Note**: CRP defines a **Knowledge Backend Interface** — the abstract contract for knowledge storage operations. The **Contextual Knowledge Fabric (CKF)** described below is CRP's standard implementation and ships with every conformant SDK. CKF is a normative part of the protocol — it provides the intelligence that enables CRP's 9 permanent value propositions. Implementations MAY substitute alternative backends that conform to the interface, but the reference SDK MUST include full CKF.

**Knowledge Backend Interface** — the operations any conformant backend MUST support:

```
REQUIRED OPERATIONS:
  store(fact: Fact) -> void                    # Persist a fact
  retrieve(query: Query) -> list[Fact]         # Retrieve relevant facts
  query(pattern: Pattern) -> list[Fact]        # Structured pattern query
  persist(session_id: str) -> void             # Flush to persistent storage
  restore(session_id: str) -> WarmState        # Restore from persistent storage
  fact_count() -> int                          # Current fact count
  health() -> BackendHealth                    # Backend health status
  temporal_query(as_of: timestamp) -> State    # Point-in-time reconstruction
  graph_walk(seed: Fact, hops: int) -> Subgraph # Graph traversal
  community_summary(topic: str) -> Summary     # Cluster summarization
  subscribe(event_type: str, callback) -> void # Event subscription
```

The CKF is CRP's unified knowledge layer — the integrated system that manages all knowledge persistence, retrieval, and enrichment across Tiers 2 and 3. CKF replaces the loosely-defined "RAG layer" with a formally specified architecture that combines multiple retrieval paradigms:

**Architecture — Four Retrieval Modes:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXTUAL KNOWLEDGE FABRIC                  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Graph Walk   │  │ Pattern Query│  │  Semantic    │         │
│  │              │  │              │  │  Fallback    │         │
│  │ Traverse     │  │ Content-     │  │              │         │
│  │ edges from   │  │ addressable  │  │ Traditional  │         │
│  │ seed facts   │  │ structured   │  │ ANN cosine   │         │
│  │ (2-hop BFS)  │  │ matching     │  │ similarity   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                 │
│         └─────────┬────────┴──────────────────┘                │
│                   ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │           Community-Aware Merge & Rank           │          │
│  │  Deduplicate → Score → Community-boost → Rank    │          │
│  └──────────────────────────────────────────────────┘          │
│                   │                                             │
│         ┌─────────┴─────────┐                                  │
│         ▼                   ▼                                   │
│  ┌─────────────┐  ┌──────────────────┐                         │
│  │ Event Log   │  │ Pub-Sub Events   │                         │
│  │ (immutable  │  │ fact_created      │                         │
│  │  temporal   │  │ fact_superseded   │                         │
│  │  source of  │  │ edge_added        │                         │
│  │  truth)     │  │ community_updated │                         │
│  └─────────────┘  └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

**Mode 1 — Graph Walk Retrieval**: Starting from facts already in the envelope (seed facts), traverse graph edges into cold storage to pull in connected knowledge. A 2-hop BFS from a vulnerability fact retrieves the service it affects, the host it runs on, and related CVEs — reconstructing the subgraph around the task's focal point. This is the primary mode for continuation chains and domain-specific tasks where the knowledge structure matters.

**Mode 2 — Pattern Query Retrieval (Content-Addressable)**: Inspired by tuple spaces (Gelernter, 1985), facts can be retrieved by structured pattern matching — not just embedding similarity:

```python
def pattern_query(self, **pattern) -> list[Fact]:
    """Retrieve facts matching a structured pattern.
    Combines structured field matching with semantic filtering."""
    # Example patterns:
    #   pattern_query(entity_type="vulnerability", related_to="Apache 2.4.52")
    #   pattern_query(category="relation", relation_type="cause_effect")
    #   pattern_query(source_window_range=(5, 15), confidence_min=0.8)
    #   pattern_query(community_id="network_topology", recency_min=0.5)
    
    candidates = self.index.match(**pattern)       # Structured field match
    if pattern.get("semantic_filter"):
        candidates = self.semantic_rerank(candidates, pattern["semantic_filter"])
    return candidates
```

Pattern queries excel when the orchestrator knows *what kind* of fact it needs (structural query) rather than *what the fact says* (semantic query). For example, during envelope construction for a "write remediation plan" task, pattern_query(category="relation", relation_type="cause_effect") retrieves all causal chains — exactly what a remediation plan needs.

**Mode 3 — Semantic Fallback Retrieval**: Traditional embedding-based ANN retrieval. This is the safety net — anything that graph walk and pattern query miss is caught by semantic similarity. The top_k parameter is **adaptive**, inspired by TCP/IP congestion avoidance:

```
ADAPTIVE top_k:
  Start with top_k = 50 (conservative)
  If retrieval latency < 10ms → increase top_k by 10 (up to 200)
  If retrieval latency > 100ms → decrease top_k by 20 (floor 20)
  If retrieved facts' relevance scores are all < 0.3 → widen search (top_k × 2)
  If retrieved facts' relevance scores are all > 0.7 → narrow search (top_k ÷ 2)
  
  This is analogous to TCP's AIMD (Additive Increase, Multiplicative Decrease):
  slowly increase retrieval breadth when performance is good,
  rapidly decrease when overloaded.
```

**Mode 4 — Community Summary Retrieval**: For holistic or broad-scope tasks ("summarize everything we know about the target network"), retrieve **community summaries** instead of individual facts. Community summaries (generated during compaction via Leiden clustering) provide compressed overviews of topic clusters. This prevents the envelope from being dominated by hundreds of individual facts when a bird's-eye view is more appropriate.

**Pub-Sub Event Architecture**: The CKF publishes events when knowledge changes. Subsystems subscribe to react:

```
EVENTS PUBLISHED:
  fact_created       → Subscribers: ANN index (update), community detector (incremental)
  fact_superseded    → Subscribers: envelope builder (deprioritize), event log (record)
  edge_added         → Subscribers: graph index (update adjacency), community detector
  community_updated  → Subscribers: community summary cache (invalidate)
  anomaly_detected   → Subscribers: telemetry (alert), extraction pipeline (flag for review)

This decouples warm state mutation from downstream effects.
A new fact doesn't need to "know" about ANN indexing or community detection —
it just publishes an event, and interested subsystems react.
```

**Community Detection Batching**: The Leiden algorithm for community detection is expensive — O(N × iterations) on the fact graph. It must NOT run on every fact mutation. Batching rules:

```
COMMUNITY_DETECTION_POLICY:
  Trigger:          Once per window (at extraction completion), NOT per fact event
  Condition:        ≥10% of nodes changed since last partition
  Min interval:     3 windows between Leiden runs
  Incremental:      When <10% nodes changed, use incremental update (add new nodes
                    to nearest existing community via embedding proximity) — O(k) not O(N)
  Full re-partition: When ≥30% nodes changed, OR after compaction, OR every 50 windows
  
  Cost budget:
    Incremental:    <10ms (simple assignment)
    Full Leiden:    ~100-500ms @ 5000 nodes (acceptable if batched and infrequent)
  
  Subscriber behavior:
    fact_created    → community_detector.mark_dirty(fact_id)   # O(1) — just flag
    edge_added      → community_detector.mark_dirty(edge.src)  # O(1) — just flag
    window_complete → community_detector.maybe_run()           # Checks dirty count
```

**CKF vs. Vanilla RAG**: The CKF is NOT just "RAG with extra steps." The architectural difference:

| Aspect | Vanilla RAG | CKF |
|--------|------------|-----|
| Retrieval | Embedding similarity only | Graph walk + pattern query + semantic + community |
| Storage | Flat vector store | Graph structure with typed edges + community partitions |
| History | Overwrite on update | Event-sourced immutable log with temporal queries |
| Extraction | Extract-then-forget | Blackboard-reactive, cross-window-aware |
| Enrichment | At query time only | Continuous: every extraction updates the fabric |
| Session boundary | Knowledge dies or flattens | Graph structure and communities persist across sessions |

---

## 4. PROTOCOL OPERATIONS

### 4.1 Standard Task Dispatch

The basic CRP operation — **zero configuration required**:

```
1. Caller invokes: crp.dispatch(system_prompt, task_input)

2. Orchestrator measures:
     system_tokens = count_tokens(system_prompt)
     task_tokens   = count_tokens(task_input)
     gen_reserve   = resolve_generation_reserve(task_intent, llm_provider)
     available_input = context_window - gen_reserve

3. CHECK: Does the task input fit in the context window?
     if system_tokens + task_tokens > available_input:
       → Task input exceeds model's context window
       → Trigger AUTO-INGEST (Section 4.6)
       → This converts oversized input into warm state facts
       → Then re-dispatches with a synthesized task referencing those facts

4. Compute envelope budget:
     envelope_budget = available_input - system_tokens - task_tokens

5. Construct envelope:
     envelope = construct_envelope(task_intent, envelope_budget, warm_state)

6. Assemble window (message array, NOT single string):
     messages = [
       {"role": "system", "content": system_prompt},       # UNCHANGED from caller
       {"role": "user",   "content": envelope + "\n\n" + task_input}  # envelope ADDED, task UNCHANGED
     ]

7. Call LLM (through the user-provided provider):
     output = llm.generate_chat(messages, max_tokens=gen_reserve)

8. Run extraction pipeline (READ-ONLY — does NOT modify output):
     facts = graduated_extract(output, task_intent)
     task_fulfillment = gap_analysis(task_intent, facts)
     warm_state.store_raw_output(window_id, output)  # Full output also stored as blob

9. Update warm state and DAG:
     warm_state.add_facts(facts)
     dag.add_node(window_id, facts, parent_ids)

10. Detect physical wall:
      if llm_response.finish_reason == "length":
        → Model hit the generation reserve limit (physical wall)
        → If task_fulfillment.gap_is_zero: return output (wall was cosmetic)
        → Else: trigger continuation (Section 4.2)

11. Return UNMODIFIED output to caller (Axiom 9 — Output Integrity)
```

### 4.2 Continuation at the Physical Wall

Continuation triggers ONLY when the LLM's generation hits the **physical context window limit** AND the task is not yet fulfilled. Not at an arbitrary budget. Not at a configured ceiling.

```
FUNCTION handle_physical_wall(output_so_far, task_intent, warm_state):
  
  # 1. Run extraction on output so far
  facts = graduated_extract(output_so_far, task_intent)
  fulfillment = gap_analysis(task_intent, facts)
  
  # 2. Check if task is actually fulfilled despite hitting the wall
  if fulfillment.gap_is_zero:
    return output_so_far  # Done — the wall was cosmetic
  
  # 3. Check information flow — is the model still producing value?
  info_flow = measure_information_flow(facts, output_so_far)
  if info_flow.rate_near_zero:
    return output_so_far  # Information dried up — more windows won't help
  
  # 4. Check user-imposed limits (optional)
  if task_intent.max_continuations and continuation_count >= task_intent.max_continuations:
    return output_so_far  # User said stop
  
  # 5. Build continuation envelope from extraction (NOT raw text overlap)
  continuation_envelope = build_continuation_envelope(
    extracted_facts=facts,                    # What has been established
    structural_state=get_structural_state(output_so_far),  # Open brackets, list position
    task_gap=fulfillment.missing_items,       # What still needs to be addressed
    last_paragraph=get_last_natural_paragraph(output_so_far)  # Style anchor
  )
  
  # 6. Dispatch continuation window
  continuation_output = dispatch_window(
    system_prompt=task_intent.system_prompt,
    envelope=continuation_envelope,
    task_input="Continue from where the previous output ended. Address the remaining items."
  )
  
  # 7. Stitch and recurse
  stitched = stitch_outputs(output_so_far, continuation_output)
  continuation_count += 1
  return handle_if_wall_again(stitched, task_intent, warm_state, continuation_count)
```

**Key differences from v1 continuation:**
- No raw text overlap with magic numbers (100 min, 15% max, 300 base)
- No hardcoded generation budget (min 1000, max 8000)
- Continuation envelope built from EXTRACTED FACTS, not copied text
- Structural state (open brackets, list position) transferred semantically
- Task gap explicitly included — the continuation window knows what's missing
- Only triggers at the physical context window wall, nowhere else

### 4.3 Multi-Signal Completion Detection

Completion detection uses **multiple independent signals**, not fact flow alone. This is critical because different content types produce value in different ways — a conclusion section rephrases existing facts (zero new fact flow) while still generating essential content.

**Signal 1: Fact Flow (Primary for entity-rich content)**

$$\text{FactFlow}(t) = \frac{\Delta \text{facts}}{\Delta \text{tokens}}$$

Measured as a rolling window: how many NEW facts did the extraction pipeline find in the last N tokens? Highly informative for entity-rich output (scan results, tool outputs, data analysis). Less informative for discursive content (conclusions, recommendations, creative writing).

**Signal 2: Structural Flow (Primary for document-structured content)**

$$\text{StructFlow}(t) = \frac{\Delta \text{structural\_elements}}{\Delta \text{tokens}}$$

Counts new structural elements: headings, list items, paragraphs, table rows, code blocks, section transitions. A conclusion section that produces zero new facts still produces NEW PARAGRAPHS and may include a NEW HEADING. Structural flow remains positive even when fact flow is zero, as long as the model is actively creating document structure.

**Signal 3: Vocabulary Novelty (Primary for creative/discursive content)**

$$\text{VocabNovelty}(t) = \frac{|\text{unique 3-grams in } [t-k, t] \setminus \text{prior 3-grams}|}{|\text{3-grams in } [t-k, t]|}$$

Even a conclusion that rephrases existing facts uses DIFFERENT WORD COMBINATIONS than the body text. Vocabulary novelty remains positive for paraphrasing, summarizing, and rhetorical argument — all of which have fact flow near zero but genuine communicative value. Vocabulary novelty approaches zero ONLY when the model is truly repeating itself (degenerate loop) or producing filler.

**Signal 4: Structural Completion Patterns (Termination detector)**

```
FUNCTION detect_structural_completion(output_tail):
  """Detect genre-specific signals that indicate intentional conclusion."""
  indicators = 0
  
  # Conclusion markers (weighted by confidence)
  if contains_conclusion_heading(output_tail):    indicators += 3  # "## Conclusion", "## Summary"
  if contains_closing_phrases(output_tail):       indicators += 2  # "In summary,", "To conclude,"
  if contains_sign_off(output_tail):              indicators += 3  # Sign-off patterns
  if all_lists_closed(output_tail):               indicators += 1  # No open numbered lists
  if heading_depth_returning_to_root(output_tail): indicators += 2  # Back to top-level heading
  
  return indicators >= 3  # Multiple completion signals needed
```

**Composite Completion Decision:**

```
FUNCTION should_terminate_generation(signals, content_type):
  """Multi-signal completion decision. NOT just fact flow."""
  
  # Content type determines signal weighting
  if content_type == ENTITY_RICH:
    # Fact flow is the primary signal
    primary_dead = signals.fact_flow < 0.01
    secondary_dead = signals.vocab_novelty < 0.1
  
  elif content_type == DOCUMENT_STRUCTURED:
    # Structural flow + fact flow together
    primary_dead = signals.fact_flow < 0.01 AND signals.struct_flow < 0.01
    secondary_dead = signals.vocab_novelty < 0.15
  
  elif content_type == DISCURSIVE:
    # Vocabulary novelty is the primary signal (conclusions, creative, rhetorical)
    primary_dead = signals.vocab_novelty < 0.05
    secondary_dead = signals.struct_flow < 0.01

  # GRACE PERIOD: When primary signal dies but secondary is still alive,
  # allow K more tokens before terminating. This prevents cutting off
  # conclusions that are rephrasing existing facts with new vocabulary.
  if primary_dead and not secondary_dead:
    return False  # Allow grace period
  
  if primary_dead and secondary_dead:
    return True  # All signals dead — truly done
  
  if signals.structural_completion:
    return True  # Explicit structural closure detected
  
  return False  # Signals still alive — keep generating
```

**Streaming vs. post-completion**: During streaming, only Stage 1 (regex) and structural element detection provide real-time flow estimation — regex matches on structured patterns (IPs, CVEs, JSON keys) work on partial chunks. Stages 2-6 require sentence/paragraph boundaries and run only post-completion. The real-time signal uses Stage 1 matches + structural elements + vocabulary novelty for trend detection; the full pipeline runs after generation completes for accurate fact extraction.

**Content type detection**: The orchestrator classifies the *expected output type* from the TaskIntent (is it a tool selection? a report section? a creative piece?) to weight the signals appropriately. This is detected from the system prompt + task description, not hardcoded per task type.

**Self-calibrating baseline**: The protocol observes the first few windows of a session to establish what "normal" flow rates look like for each signal and for this specific model + hardware + quantization combination. Subsequent windows are compared against this empirical baseline, not hardcoded values.

### 4.4 Parallel Task Fan-Out

When multiple independent tasks can execute simultaneously:

```
1. Orchestrator identifies N independent tasks
2. For each task, construct an independent envelope from warm_state
3. Dispatch all N windows in parallel (or batched if resource-constrained)
4. Collect all N outputs
5. Run extraction on all N outputs
6. Merge facts from all N outputs into warm_state
7. Update DAG with fan-out edges
8. Continue with next dependent task
```

### 4.5 Hierarchical Decomposition

When a task is too large for one window:

```
1. Dispatch a planning window: "Break this task into sub-tasks"
2. Planning window outputs a task list
3. For each sub-task:
   a. Dispatch a dedicated window with sub-task-specific envelope
   b. Run extraction, update warm state
4. Dispatch a synthesis window: combine sub-task outputs
   (envelope carries all sub-task facts)
```

### 4.6 Auto-Ingest: Handling Input Larger Than the Context Window

When `task_input` exceeds the model's available input space ($S + T > C - G$), the orchestrator automatically converts the oversized input into warm state facts before dispatching:

```
FUNCTION auto_ingest(system_prompt, task_input, task_intent, warm_state):
  
  system_tokens = count_tokens(system_prompt)
  gen_reserve = resolve_generation_reserve(task_intent, llm_provider)
  available_for_task = context_window - system_tokens - gen_reserve
  
  # The task input doesn't fit. Chunk and ingest it.
  
  # 1. Detect structural elements that MUST NOT be split
  protected_spans = detect_protected_structures(task_input)
  #   Protected structures: tables (markdown/HTML), code blocks (``` or indented),
  #   JSON/XML blocks, numbered list items, blockquotes, image/figure references.
  #   Each protected span is marked with (start_offset, end_offset, type).
  #   The chunker will NEVER split within a protected span.
  
  # 2. Determine chunk size with structure-adaptive boundaries
  chunk_size = available_for_task - 500   # 500 tokens reserved for envelope overhead
  overlap = min(chunk_size // 10, 500)    # 10% overlap, capped at 500 tokens
  #   Overlap increased from 200 to 500 tokens to reduce boundary information loss.
  #   The reconciliation pass (step 4) deduplicates overlap-extracted facts.
  
  # 3. Split input into overlapping chunks at STRUCTURE-AWARE boundaries
  chunks = split_at_boundaries(task_input, chunk_size, overlap, protected_spans)
  #   split_at_boundaries now respects protected_spans:
  #     - NEVER splits within a protected structure (table, code block, etc.)
  #     - If a protected structure exceeds chunk_size, it becomes its own chunk
  #       (even if that makes it larger than the target — correctness over uniformity)
  #     - Splitting preference order:
  #       1. Section/heading breaks (# at start of line)
  #       2. Paragraph breaks (\n\n)
  #       3. Between protected structures (e.g., between two tables)
  #       4. Sentence boundaries (. followed by space/newline)
  #       5. Line breaks (\n)
  #       6. Word boundaries (space) — last resort
  
  # 4. Process each chunk through the extraction pipeline (NO LLM calls)
  per_chunk_facts = []
  for i, chunk in enumerate(chunks):
    facts = graduated_extract(chunk, task_intent)
    for fact in facts:
      fact.source = f"input_chunk_{i+1}_of_{len(chunks)}"
      fact.chunk_index = i
      fact.chunk_offset_start = chunk.offset_start  # Position in original input
      fact.chunk_offset_end = chunk.offset_end
    per_chunk_facts.append(facts)
  
  # 5. BOUNDARY RECONCILIATION PASS
  #    Facts extracted from overlapping regions may be duplicated or fragmented.
  #    Reconcile across adjacent chunk boundaries:
  reconciled_facts = reconcile_chunk_boundaries(per_chunk_facts, chunks)
  warm_state.add_facts(reconciled_facts)
  
  # 6. Also store the raw input in Tier 3 cold storage for later retrieval
  warm_state.store_raw_input(task_input, session_id)
  
  # 7. Now dispatch with an envelope built from the ingested facts
  #    The task_input for the LLM is a SYNTHESIZED reference, not the raw input
  synthesized_task = (
    f"Process the following material ({len(chunks)} sections ingested, "
    f"{warm_state.fact_count()} facts extracted). "
    f"Original request: {task_intent.task_input[:500]}"
  )
  
  envelope_budget = context_window - system_tokens - count_tokens(synthesized_task) - gen_reserve
  envelope = construct_envelope(task_intent, envelope_budget, warm_state)
  
  messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user",   "content": envelope + "\n\n" + synthesized_task}
  ]
  
  return dispatch_window(messages, gen_reserve)


FUNCTION detect_protected_structures(text):
  """Identify spans in the text that must not be split during chunking."""
  spans = []
  
  # Fenced code blocks: ``` ... ```
  for match in regex.finditer(r'```[\s\S]*?```', text):
    spans.append(ProtectedSpan(match.start(), match.end(), "code_block"))
  
  # Markdown tables: lines starting with |
  for match in regex.finditer(r'(\|[^\n]+\|\n)+', text):
    spans.append(ProtectedSpan(match.start(), match.end(), "table"))
  
  # JSON/XML blocks: { ... } or < ... > spanning multiple lines
  for match in regex.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
    if match.end() - match.start() > 50:  # Only protect substantial blocks
      spans.append(ProtectedSpan(match.start(), match.end(), "json_block"))
  
  # Numbered lists: sequential "1. ...\n2. ...\n3. ..."
  for match in regex.finditer(r'(\d+\.\s[^\n]+\n){2,}', text):
    spans.append(ProtectedSpan(match.start(), match.end(), "numbered_list"))
  
  return merge_overlapping_spans(spans)


FUNCTION reconcile_chunk_boundaries(per_chunk_facts, chunks):
  """Reconcile facts from overlapping regions between adjacent chunks."""
  all_facts = []
  
  for i in range(len(per_chunk_facts)):
    chunk_facts = per_chunk_facts[i]
    
    if i == 0:
      all_facts.extend(chunk_facts)
      continue
    
    # For each fact in this chunk, check if it duplicates a fact from the previous chunk
    # (which would happen in the overlap region)
    prev_facts = per_chunk_facts[i - 1]
    
    for fact in chunk_facts:
      is_duplicate = False
      is_complement = False
      complement_target = None
      
      for prev_fact in prev_facts:
        sim = cosine_similarity(fact.embedding, prev_fact.embedding)
        
        if sim > 0.95:
          # Near-identical fact — duplicate from overlap region. Skip it.
          is_duplicate = True
          break
        elif sim > 0.75:
          # High similarity but different content — may be complementary fragments.
          # Example: chunk N captured "Table columns: A, B, C" and chunk N+1
          # captured "Table columns: C, D, E" from the same table in the overlap.
          content_overlap = compute_token_overlap(fact.text, prev_fact.text)
          if content_overlap > 0.3:
            is_complement = True
            complement_target = prev_fact
            break
      
      if is_duplicate:
        continue  # Skip — already captured from previous chunk
      elif is_complement and complement_target:
        # Merge: combine the two fragments into a single fact
        merged_text = merge_fact_texts(complement_target.text, fact.text)
        complement_target.text = merged_text
        complement_target.embedding = embed(merged_text)  # Re-embed the merged fact
      else:
        all_facts.append(fact)  # New fact — not in overlap region
  
  return all_facts
```

**Key properties of auto-ingest:**
- **Zero LLM cost** (by default): Stages 1-5 use regex, statistical NLP, GLiNER, UIE, and discourse parsing — no LLM calls. Stage 6 (LLM-assisted relational extraction) is optional and only activates for reasoning-dense content.
- **Structure-aware chunking**: Tables, code blocks, JSON, and numbered lists are never split mid-structure. The chunker varies chunk size to keep structural units intact.
- **Boundary reconciliation**: After independent chunk extraction, a reconciliation pass deduplicates and merges facts from overlap regions — eliminating the fragmented-fact problem.
- **Transparent to the caller**: The user calls `crp.dispatch(prompt, million_token_input)` and CRP handles the rest
- **Lossy but prioritized with degradation awareness**: The extraction pipeline captures entities, key sentences, AND (for reasoning-dense content) logical relationships. The semantic scoring ensures the MOST RELEVANT facts for the specific task are in the envelope. The raw input is stored in Tier 3 for later retrieval if needed. See Section 7.6 for the honest degradation model.
- **Incremental**: If the user later dispatches another task on the same session, the facts from the first ingest are already in warm state — no re-ingestion needed

**When auto-ingest is NOT needed:**
- Task input fits in the context window → normal dispatch (Section 4.1)
- User calls `crp.ingest()` directly → manual ingest (Section 6.5)
- Task uses hierarchical decomposition → planning window breaks it down (Section 4.5)

### 4.7 Master Continuation Loop

The complete orchestration loop that ties dispatch, wall detection, continuation, and stitching together:

```
FUNCTION dispatch_with_continuation(system_prompt, task_input, task_intent, warm_state):
  
  accumulated_output = ""
  continuation_count = 0
  max_continuations = task_intent.max_continuations or CRP_MAX_CONTINUATIONS  # default 50
  all_window_outputs = []  # Raw per-window outputs preserved for audit
  all_window_facts = []    # Facts from each window (incremental, not re-extracted)
  task_requirements = extract_task_requirements(task_intent)  # Parse once, reuse
  
  # First window
  output, finish_reason = dispatch_single_window(system_prompt, task_input, task_intent, warm_state)
  accumulated_output = output
  all_window_outputs.append(output)
  
  # Extract facts from FIRST WINDOW ONLY (incremental)
  window_facts = graduated_extract(output, task_intent)
  all_window_facts.extend(window_facts)
  warm_state.add_facts(window_facts)
  
  # Continuation loop
  while finish_reason == "length" and continuation_count < max_continuations:
    
    # 1. Analyze using ALL accumulated facts (but only EXTRACT from latest window)
    fulfillment = gap_analysis(task_intent, all_window_facts, task_requirements)
    completion_signals = measure_completion_signals(all_window_facts, accumulated_output)
    
    # 2. Check termination conditions (multi-signal, Section 4.3)
    if fulfillment.gap_is_zero:
      break  # Task fulfilled — the wall was cosmetic
    
    content_type = detect_output_content_type(accumulated_output, task_intent)
    if should_terminate_generation(completion_signals, content_type):
      break  # All completion signals dead — more windows won't help
    
    # 3. Trigger re-grounding if chain is getting long (Section 4.9)
    if continuation_count > 0 and continuation_count % REGROUND_EVERY_N == 0:
      run_regrounding_pass(accumulated_output, warm_state, task_intent)
    
    # 4. Build continuation envelope
    continuation_envelope = build_continuation_envelope(
      facts_established=all_window_facts,
      structural_state=get_structural_state(accumulated_output),
      task_gap=fulfillment.missing_items,
      style_anchor=get_last_natural_paragraph(accumulated_output),
      voice_profile=warm_state.voice_profile,        # Long-chain coherence
      document_map=warm_state.document_map             # Progressive document structure
    )
    
    # 5. Format continuation prompt
    continuation_task = format_continuation_prompt(
      structural_state=get_structural_state(accumulated_output),
      missing_items=fulfillment.missing_items
    )
    
    # 6. Dispatch continuation window
    cont_output, finish_reason = dispatch_single_window(
      system_prompt=task_intent.system_prompt,
      task_input=continuation_task,
      task_intent=task_intent,
      warm_state=warm_state,
      override_envelope=continuation_envelope
    )
    
    all_window_outputs.append(cont_output)
    
    # 7. INCREMENTAL extraction: extract ONLY the new window's output
    #    NOT graduated_extract(accumulated_output) — that re-extracts everything
    new_facts = graduated_extract(cont_output, task_intent)
    all_window_facts.extend(new_facts)
    warm_state.add_facts(new_facts)
    
    # 8. Update document map with new structural elements
    warm_state.document_map.update(cont_output, continuation_count + 1)
    
    # 9. Stitch outputs
    accumulated_output = stitch_outputs(accumulated_output, cont_output)
    continuation_count += 1
    
    # 10. Compact warm state if it's getting large (Section 3.6)
    if warm_state.fact_count() > 5000:
      compact_warm_state(warm_state, task_intent)
  
  # Store all raw window outputs for audit
  for i, raw_output in enumerate(all_window_outputs):
    warm_state.store_raw_output(f"window_{i}", raw_output)
  
  return accumulated_output
```

**Key difference from v1 master loop**: Extraction is **incremental** — each window's output is extracted independently and the facts are appended. The v1 approach of `graduated_extract(accumulated_output)` re-extracted ALL accumulated output on every iteration, causing $O(N^2)$ extraction cost across N windows. Incremental extraction is $O(N)$ — each window's output is processed exactly once. Task requirements are parsed once and reused for all gap analysis calls.

**Physical wall detection** relies on the `finish_reason` field returned by the LLM provider:
- `"length"` → model hit the generation reserve limit → continuation candidate
- `"stop"` → model produced EOS naturally → check gap analysis
- `"stop"` AND `gap > 0` → model stopped early but task unfulfilled → redispatch with explicit gap in envelope (Section 7.1 Empty Continuation)

### 4.8 Stitch Algorithm

Complete specification of how multi-window outputs are assembled:

```
FUNCTION stitch_outputs(prior_output, continuation_output):
  
  # 1. Echo detection: find repeated text between tail of prior and head of continuation
  #    The LLM often re-generates the last sentence or paragraph from the envelope's style anchor
  tail = prior_output[-2000:]  # Last ~2000 chars for comparison
  head = continuation_output[:2000:]  # First ~2000 chars for comparison
  
  echo_length = longest_common_substring_at_boundary(tail, head)
  #   Searches for the longest string S such that:
  #     tail ends with S AND head starts with S
  #   Minimum length: 20 characters (avoid false matches on common words)
  
  # 2. Remove echo from continuation
  clean_continuation = continuation_output[echo_length:]
  
  # 3. Find clean stitch boundary in prior output
  #    Goal: avoid joining mid-sentence or mid-word
  stitch_point = find_clean_boundary(prior_output)
  #   find_clean_boundary searches backward from the end of prior_output for:
  #     1. Paragraph break (\n\n) — preferred
  #     2. Sentence end (. or ! or ? followed by space/newline) — good
  #     3. Line break (\n) — acceptable
  #     4. If none found within last 500 chars → use full prior_output (no trimming)
  #   The search window is at most 500 characters from the end.
  #   If the prior output ends cleanly (sentence boundary), stitch_point = len(prior_output).
  
  # 4. Preserve trimmed fragment
  trimmed_fragment = prior_output[stitch_point:]
  if trimmed_fragment:
    warm_state.store_trimmed_fragment(window_id, trimmed_fragment)
    # Trimmed fragment is stored for audit — never silently discarded
  
  # 5. Join
  return prior_output[:stitch_point] + clean_continuation


FUNCTION format_continuation_prompt(structural_state, missing_items):
  """Format the explicit continuation instruction sent to the LLM."""
  
  parts = ["Continue writing from where the previous section ended."]
  
  if structural_state.current_section:
    parts.append(f"You were writing: {structural_state.current_section}")
  
  if structural_state.list_position:
    parts.append(f"List position: item {structural_state.list_position.current} of {structural_state.list_position.total}")
  
  if structural_state.open_blocks:
    parts.append(f"Open blocks to close: {', '.join(structural_state.open_blocks)}")
  
  if missing_items:
    parts.append(f"Remaining items to address: {', '.join(missing_items)}")
  
  return "\n".join(parts)


FUNCTION get_structural_state(output):
  """Detect the structural position at the end of the output."""
  
  return StructuralState(
    current_section=detect_last_heading(output),          # Last ## or ### heading
    list_position=detect_list_position(output),            # "item 4 of 12" if in a list
    open_blocks=detect_unclosed_blocks(output),            # Unclosed ```, {, [, etc.
    markdown_depth=detect_heading_depth(output),           # Current heading nesting level
    last_heading_hierarchy=extract_heading_hierarchy(output) # ["Chapter 3", "Section 3.2", "3.2.1"]
  )


FUNCTION get_last_natural_paragraph(output):
  """Extract the last complete paragraph as a style anchor."""
  
  paragraphs = output.split("\n\n")
  # Walk backward to find a paragraph that is:
  #   - At least 50 characters (not a heading or blank)
  #   - Ends at a sentence boundary
  for para in reversed(paragraphs):
    para = para.strip()
    if len(para) >= 50 and para[-1] in ".!?:":
      return para
  # Fallback: last 500 characters
  return output[-500:]
```

---

## 5. WINDOW LIFECYCLE

Every task window follows this lifecycle:

```
CREATED ──▶ ASSEMBLED ──▶ DISPATCHED ──▶ GENERATING ──▶ COMPLETED ──▶ EXTRACTED
   │              │              │              │              │              │
   │ Envelope     │ Sent to      │ Tokens       │ Output       │ Facts into   │
   │ constructed  │ LLM API      │ streaming +  │ captured     │ warm state + │
   │              │              │ info flow    │              │ DAG updated  │
   │              │              │ monitored    │              │              │
```

### 5.1 Telemetry

Each window records:
- `window_id`: Unique identifier
- `dag_position`: Parent/child relationships
- `envelope_tokens`: How many tokens the envelope consumed
- `task_tokens`: How many tokens the task input consumed
- `output_tokens`: How many tokens were generated
- `saturation`: $\frac{S + E + T}{C}$ — how well the context window was filled
- `information_flow_profile`: Rolling fact yield over the generation
- `extraction_stages_used`: Which pipeline stages activated
- `facts_produced`: Count and categories of extracted facts
- `wall_time_ms`: Total time from dispatch to extraction
- `generation_speed`: Tokens/second during generation
- `continuation_triggered`: Whether the physical wall was reached

---

## 6. PROTOCOL INTERFACES

These interfaces define the contract between CRP and the host system.

### 6.1 LLM Interface

CRP requires an LLM provider — supplied by the caller, not discovered magically. The protocol supports both chat (message array) and completion (single string) APIs:

```
INTERFACE LLMProvider:
  # Chat-style API (preferred — matches OpenAI, Anthropic, Google, Ollama)
  generate_chat(messages: list[Message], **kwargs) -> str
  
  # Completion-style API (fallback — matches llama.cpp, vLLM raw)
  generate(prompt: str, **kwargs) -> str
  
  # Required utilities
  count_tokens(text: str) -> int
  context_window_size() -> int
```

CRP uses `generate_chat()` if available, falling back to `generate()`. The caller provides this interface at construction time:

```python
# Option A — Built-in adapter (recommended)
client = Client(llm=OpenAIAdapter(openai_client))
client = Client(llm=LlamaCppAdapter("http://localhost:8080"))

# Option B — Callable function
client = Client(
    generate_fn=lambda msgs, **kw: your_function(msgs, **kw),
    count_tokens=your_tokenizer,
    context_window=128000
)

# Option C — Env var auto-discovery (builds HTTP adapter)
client = Client()  # Uses CRP_LLM_ENDPOINT
```

When CRP dispatches a window, it constructs messages from the user's system prompt, envelope, and task input:

```python
messages = [
    {"role": "system", "content": task_intent.system_prompt},  # UNCHANGED
    {"role": "user",   "content": envelope_text + "\n\n" + task_intent.task_input}  # envelope ADDED, task UNCHANGED
]
```

The user's system prompt and task input are passed through **unmodified**. The envelope is **additional context** inserted before the task input — not a replacement for anything the user provided.

Any LLM that can be called from Python works with CRP. Grammar constraint support is optional (enables structured output guarantee for user schemas).

### 6.2 State Store Interface

```
INTERFACE WarmStateStore:
  add_facts(facts: list[Fact])
  get_facts(filter: FactFilter | None = None) -> list[Fact]
  get_critical_state() -> CriticalState
  update_phase(phase: str)
  get_all_facts_scored(task_embedding: ndarray) -> list[ScoredFact]
  get_structural_state() -> StructuralState
```

### 6.3 Envelope Builder Interface

```
INTERFACE EnvelopeBuilder:
  construct(task_intent: TaskIntent, budget_tokens: int,
            state: WarmStateStore) -> str
```

### 6.4 Extraction Pipeline Interface

```
INTERFACE ExtractionPipeline:
  extract(output: str, task_intent: TaskIntent) -> ExtractionResult
  measure_flow(output_chunk: str, window_facts: list[Fact]) -> float
  gap_analysis(task_intent: TaskIntent, facts: list[Fact]) -> GapResult
```

### 6.5 Orchestrator Interface

```
INTERFACE Orchestrator:
  dispatch(system_prompt: str, task_input: str, **kwargs) -> str
  dispatch_intent(intent: TaskIntent) -> str
  ingest(raw_text: str, source_label: str | None = None) -> ExtractionResult
```

**`ingest()`** provides direct extraction without an LLM window. It runs the graduated extraction pipeline on `raw_text`, adds extracted facts to warm state with `source_window="ingest:{source_label}"`, and returns the extraction result. No LLM call, no window creation, no envelope construction. This is how tool output, API responses, and file contents enter the system efficiently.

### 6.6 Session Lifecycle

- **Default**: One session per `Client()` instance. The constructor creates a new session ID automatically.
- **Explicit**: `Client(session_id="pentest-192.168.1.50")` — reuse session across calls to share warm state.
- **Concurrent**: Each `Client()` instance is fully isolated. Running two clients simultaneously is safe — no warm state cross-contamination.
- **Session end**: When the `Client` is garbage-collected or `client.close()` is called, warm state is flushed to cold storage (Tier 3) for cross-session retrieval. **Graph structure is persisted**: all facts, edges, community memberships, and community summaries are archived together. The event log is finalized and persisted. This ensures the next session can reconstruct the full knowledge fabric, not just retrieve isolated facts.
- **Session resumption**: If a `Client` is constructed with a `session_id` that already has persisted warm state (from Tier 3), that state is restored — including the fact graph structure, community partitions, and event log. This enables resumption after rate limits, crashes, or multi-day generation tasks with full knowledge continuity.

### 6.7 Cross-Session Garbage Collection

Cold storage (Tier 3) grows with every session. Without lifecycle management, it becomes unbounded — potentially reaching gigabytes after hundreds of sessions. CRP applies **cross-session garbage collection** to keep cold storage within a configurable budget:

```python
@dataclass
class ColdStoragePolicy:
    """Policy for cross-session garbage collection."""
    storage_budget_mb: int = 500       # Max cold storage size (default 500MB)
    stale_session_threshold: int = 50  # Sessions since last retrieval before GC-eligible
    stale_age_days: int = 90           # Days since creation before GC-eligible
    relevance_decay_factor: float = 0.95  # Per-session relevance decay
    min_facts_retained: int = 1000     # Never GC below this floor

FUNCTION cross_session_gc(cold_storage, policy):
  """Run garbage collection on Tier 3 cold storage. Called on session start."""
  
  if cold_storage.size_mb() < policy.storage_budget_mb * 0.8:
    return  # Under 80% of budget — no action needed
  
  # 1. Score all facts by cross-session relevance
  for fact in cold_storage.all_facts():
    sessions_since_retrieval = cold_storage.sessions_since_last_access(fact.id)
    days_since_creation = (now() - fact.created_at).days
    
    # Relevance decays with disuse and age
    fact.gc_score = (
      policy.relevance_decay_factor ** sessions_since_retrieval
      * (1.0 if days_since_creation < policy.stale_age_days else 0.5)
      * fact.confidence
      * (2.0 if cold_storage.has_active_edges(fact.id) else 1.0)  # Keep connected facts
    )
  
  # 2. Sort by gc_score ascending (lowest relevance first)
  candidates = sorted(cold_storage.all_facts(), key=lambda f: f.gc_score)
  
  # 3. Tombstone lowest-scoring facts until under budget
  tombstoned = 0
  while cold_storage.size_mb() > policy.storage_budget_mb * 0.7:  # Target 70%
    if cold_storage.fact_count() <= policy.min_facts_retained:
      break  # Never go below floor
    fact = candidates.pop(0)
    cold_storage.tombstone(fact.id)  # Mark for deletion, keep edges for 1 more cycle
    tombstoned += 1
  
  # 4. Purge previously tombstoned facts (from prior GC cycle)
  cold_storage.purge_tombstoned()
  
  # 5. Rebuild cold storage indexes
  cold_storage.rebuild_indexes()
  
  log(f"Cross-session GC: tombstoned {tombstoned} facts, "
      f"storage now {cold_storage.size_mb():.0f}MB / {policy.storage_budget_mb}MB")

GC_RULES:
  When:           On session start (before any new work)
  Trigger:        Cold storage exceeds 80% of budget
  Target:         Reduce to 70% of budget (hysteresis to avoid GC every session)
  Priority:       Facts with no edges > facts unused for 50+ sessions > old facts
  Never delete:   Facts with active cross-session edges (part of knowledge graph)
  Tombstone:      Two-phase: mark tombstoned in cycle N, purge in cycle N+1
                  (safety: if a session needs a tombstoned fact, it can be restored)
  Telemetry:      Log GC actions for audit
```

### 6.8 Cost Control Interface

CRP must prevent runaway spending. These are hard caps, not suggestions:

```
INTERFACE CostControls:
  # Constructor-level caps (set once at Client creation)
  max_windows_per_session: int | None       # Hard cap on window count
  max_total_input_tokens: int | None        # Hard cap on cumulative input
  max_total_output_tokens: int | None       # Hard cap on cumulative output
  rate_limit_tokens_per_min: int | None     # Auto-backoff to stay under rate limit
  rate_limit_requests_per_min: int | None   # Auto-backoff for request-based limits

  # Pre-flight estimation
  estimate_session(planned_dispatches, avg_envelope_tokens, avg_output_tokens,
                   provider_pricing) -> CostEstimate

  # Live tracking
  session_status() -> SessionStatus         # Running totals, remaining budget

  # Envelope preview (inspect WITHOUT dispatching)
  preview_envelope(system_prompt, task_input) -> EnvelopePreview
```

When ANY cap is exceeded, `dispatch()` raises `BudgetExhaustedError` instead of silently continuing. The error includes: cap type, amount used vs. limit, windows completed, and estimated remaining cost to complete.

Rate limit awareness is automatic: CRP tracks the observed rate limit headers from the LLM provider and delays subsequent dispatches to stay under the limit. No user-managed retry loops or backoff logic needed.

### 6.9 Global Overhead Budget

CRP has multiple supplementary features that each independently consume windows — curation, ORC, review cycles, re-grounding, validation. Each feature's documentation quotes its overhead individually (2-3% curation, 10-15% review, 2-5% ORC). **These are additive, not alternatives.** A session that activates all features could see 25-40% combined overhead — far exceeding any individual feature's stated cost.

The **Global Overhead Budget** caps total non-productive windows (windows that produce no user-visible output) as a percentage of productive windows:

```python
@dataclass
class OverheadBudget:
    """Caps total protocol overhead across all features."""
    max_overhead_pct: float = 15.0     # Default: 15% of productive windows
    current_overhead_windows: int = 0   # Running total
    current_productive_windows: int = 0 # Running total
    
    # Priority order for feature shedding (lowest priority shed first)
    FEATURE_PRIORITY = [
        ("review_tier3",    "weight": 3),  # Full review windows (most expensive)
        ("orc_steps",       "weight": 2),  # Extra ORC reasoning steps
        ("curation",        "weight": 1),  # Curation windows
        ("re_grounding",    "weight": 1),  # Re-grounding windows
        ("review_tier2",    "weight": 0),  # Binary probes (cheapest, shed last)
    ]

FUNCTION check_overhead_budget(budget, feature_name):
  """Called before dispatching any overhead window. Returns allow/deny."""
  current_ratio = budget.current_overhead_windows / max(budget.current_productive_windows, 1)
  
  if current_ratio < budget.max_overhead_pct / 100:
    budget.current_overhead_windows += 1
    return ALLOW
  
  # Over budget — check priority
  feature_priority = budget.FEATURE_PRIORITY[feature_name].weight
  if feature_priority >= 2:
    # High-priority features can exceed budget by 5%
    if current_ratio < (budget.max_overhead_pct + 5) / 100:
      budget.current_overhead_windows += 1
      return ALLOW
  
  log(f"Overhead budget exceeded ({current_ratio:.1%} > {budget.max_overhead_pct}%). "
      f"Shedding {feature_name}.")
  return DENY

OVERHEAD_BUDGET_RULES:
  Default cap:     15% (for every 100 productive windows, max 15 overhead windows)
  Feature shed:    Lowest priority first (review_tier3 → ORC → curation → re-grounding)
  Never shed:      Extraction (always runs) and Tier 1 validation (zero LLM cost)
  Reset:           On session start
  Override:        User can set max_overhead_pct in CostControls (0% = no overhead features)
  Telemetry:       Log overhead ratio per-window, cumulative by feature type
  
  COMBINED OVERHEAD BY TIER (with budget enforced):
    Tier A (2-10 windows):     ~5%  (curation only, review rare)
    Tier B (10-100 windows):   ~10% (curation + Tier 2 review + occasional re-grounding)
    Tier C (100-1K windows):   ~15% (capped — features shed to stay within budget)
    Tier D (1K+ windows):      ~15% (capped — aggressive shedding of review/ORC)
```

### 6.10 API Formalism

This section defines CRP's API contract using formal schemas, RFC 2119 conformance language, stability guarantees, and protocol-standard message types. CRP's API formalism is informed by — and compared against — industry protocol standards including JSON-RPC 2.0, LSP (Language Server Protocol), MCP (Model Context Protocol), and gRPC.

#### 6.10.1 Protocol Comparison — Design Rationale

CRP's API is a **local, synchronous, typed Python API** — not a network RPC protocol. This decision is deliberate:

| Protocol | Transport | Message Format | Lifecycle | CRP Relevance |
|----------|-----------|----------------|-----------|---------------|
| **JSON-RPC 2.0** | Transport-agnostic (HTTP, WebSocket, stdio) | JSON `{jsonrpc, method, params, id}` | Stateless | CRP borrows **error code ranges** and **request/response/notification taxonomy** |
| **LSP** | JSON-RPC over stdio/pipe/socket | JSON-RPC with typed params | Stateful (initialize → shutdown) | CRP borrows **lifecycle pattern** (init → operations → close) and **capability negotiation** |
| **MCP** | JSON-RPC over stdio/SSE | JSON-RPC with tool/resource schemas | Stateful (initialize → operations) | CRP borrows **nothing from MCP's transport**; CRP learns from MCP's **security failures** |
| **gRPC** | HTTP/2 | Protocol Buffers | Stateful (channel lifecycle) | CRP borrows **streaming patterns** (unary, server-streaming) and **status codes** |

**Why CRP is NOT a JSON-RPC service**: CRP runs in-process. Serializing every `dispatch()` call to JSON, parsing it, and serializing the response would add ~1-5ms per call for zero benefit. CRP's API is **direct function invocation** with typed dataclasses. An SDK MAY expose a JSON-RPC or gRPC transport layer for cross-process usage, but the protocol itself is defined as typed Python interfaces.

#### 6.10.2 Formal Type Definitions (JSON Schema)

All CRP API types are defined here in JSON Schema (Draft 2020-12) for language-neutral consumption. Implementations in Python use `@dataclass(slots=True)` with equivalent semantics.

##### TaskIntent

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TaskIntent",
  "description": "Declarative, all-optional description of what the caller wants. MUST be the input to dispatch() and dispatch_intent().",
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "maxLength": 10000,
      "description": "Free-text description of the task. SHOULD be concise."
    },
    "system_prompt": {
      "type": ["string", "null"],
      "description": "System prompt for the LLM window. MAY be omitted; CRP provides no default."
    },
    "task_input": {
      "type": ["string", "null"],
      "description": "The user-facing input to process. MUST pass structural validation (§22.3.1)."
    },
    "expected_output_type": {
      "type": ["string", "null"],
      "enum": [null, "text", "json", "markdown", "code"],
      "description": "Hint for extraction pipeline. MAY be omitted."
    },
    "max_windows": {
      "type": ["integer", "null"],
      "minimum": 1,
      "description": "Maximum windows for this task (including continuations). MAY be omitted for unbounded."
    },
    "max_output_tokens": {
      "type": ["integer", "null"],
      "minimum": 1,
      "description": "Per-window generation reserve. MUST NOT exceed the model's maximum output length."
    },
    "metadata": {
      "type": ["object", "null"],
      "maxProperties": 50,
      "description": "Arbitrary key-value metadata. MUST NOT exceed 50 keys."
    }
  },
  "additionalProperties": false
}
```

##### QualityReport

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "QualityReport",
  "description": "Returned by dispatch() alongside the LLM output. MUST always be provided.",
  "type": "object",
  "required": ["session_id", "window_id", "output", "facts_extracted", "security_flags"],
  "properties": {
    "session_id": {
      "type": "string",
      "format": "uuid",
      "description": "UUID v4 identifying the session. MUST be stable across all windows in a session."
    },
    "window_id": {
      "type": "string",
      "format": "uuid",
      "description": "UUID v4 identifying this specific window invocation."
    },
    "output": {
      "type": "string",
      "description": "The complete, unmodified LLM output (Axiom 9 — Output Integrity). MUST NOT be filtered, summarized, or truncated by CRP."
    },
    "facts_extracted": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of facts extracted from this window's output."
    },
    "continuation_windows": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of continuation windows triggered (0 if output fit in one window)."
    },
    "envelope_saturation": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Fraction of available envelope space used (0.0–1.0). SHOULD be > 0.9 for non-trivial tasks."
    },
    "quality_tier": {
      "type": "string",
      "enum": ["S", "A", "B", "C", "D"],
      "description": "CRP quality tier for this task based on window count (§10)."
    },
    "security_flags": {
      "$ref": "#/$defs/SecurityFlags",
      "description": "Security observations for this window. MUST always be present."
    },
    "telemetry": {
      "type": ["object", "null"],
      "description": "Performance telemetry. MAY be omitted if telemetry is disabled."
    }
  },
  "$defs": {
    "SecurityFlags": {
      "type": "object",
      "properties": {
        "injection_markers_detected": { "type": "integer", "minimum": 0 },
        "injection_marker_details": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "offset": { "type": "integer" },
              "pattern_name": { "type": "string" },
              "matched_text": { "type": "string" }
            }
          }
        },
        "unicode_normalized": { "type": "boolean" },
        "control_chars_stripped": { "type": "integer", "minimum": 0 },
        "input_truncated": { "type": "boolean" },
        "integrity_violations": { "type": "integer", "minimum": 0 }
      }
    }
  }
}
```

##### SessionStatus

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SessionStatus",
  "description": "Returned by session_status(). MUST always be available for OBSERVER role or above.",
  "type": "object",
  "required": ["session_id", "windows_completed", "total_input_tokens", "total_output_tokens", "facts_in_warm_state", "overhead_ratio"],
  "properties": {
    "session_id": { "type": "string", "format": "uuid" },
    "windows_completed": { "type": "integer", "minimum": 0 },
    "total_input_tokens": { "type": "integer", "minimum": 0 },
    "total_output_tokens": { "type": "integer", "minimum": 0 },
    "facts_in_warm_state": { "type": "integer", "minimum": 0 },
    "overhead_ratio": {
      "type": "number",
      "minimum": 0.0,
      "description": "Current overhead windows / productive windows ratio."
    },
    "remaining_budget": {
      "type": ["object", "null"],
      "description": "Remaining budget against cost caps. NULL if no caps set.",
      "properties": {
        "windows_remaining": { "type": ["integer", "null"] },
        "input_tokens_remaining": { "type": ["integer", "null"] },
        "output_tokens_remaining": { "type": ["integer", "null"] }
      }
    }
  }
}
```

##### CostEstimate

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CostEstimate",
  "description": "Returned by estimate_session(). Provides pre-flight cost estimation.",
  "type": "object",
  "required": ["estimated_windows", "estimated_input_tokens", "estimated_output_tokens"],
  "properties": {
    "estimated_windows": { "type": "integer", "minimum": 1 },
    "estimated_input_tokens": { "type": "integer", "minimum": 0 },
    "estimated_output_tokens": { "type": "integer", "minimum": 0 },
    "estimated_cost_usd": {
      "type": ["number", "null"],
      "description": "Estimated cost in USD. NULL if provider pricing not supplied."
    },
    "confidence": {
      "type": "string",
      "enum": ["high", "medium", "low"],
      "description": "Estimation confidence. 'high' = known task pattern, 'low' = novel task."
    }
  }
}
```

##### EnvelopePreview

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EnvelopePreview",
  "description": "Returned by preview_envelope(). Inspect without dispatching.",
  "type": "object",
  "required": ["total_tokens", "envelope_tokens", "facts_included", "saturation"],
  "properties": {
    "total_tokens": { "type": "integer", "minimum": 0 },
    "envelope_tokens": { "type": "integer", "minimum": 0 },
    "generation_reserve": { "type": "integer", "minimum": 0 },
    "facts_included": { "type": "integer", "minimum": 0 },
    "facts_available": { "type": "integer", "minimum": 0 },
    "saturation": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
  }
}
```

#### 6.10.3 Operation Contracts (RFC 2119)

Each CRP operation specifies preconditions, postconditions, and error behavior using RFC 2119 language.

##### `init(app_id, binding_secret?, config?) → SessionHandle`

| Aspect | Contract |
|--------|----------|
| **Precondition** | `app_id` MUST be a non-empty string. `binding_secret` MAY be omitted (auto-generation applies per §22.2.2). `config` MAY be a `SecurityConfig` or `CostControls` dataclass. |
| **Postcondition** | A new session MUST be created with a unique UUID v4 `session_id`. A `session_key` MUST be derived via HMAC-SHA256. Cold state from prior sessions with the same `session_id` (if provided) SHOULD be restored. Cross-session GC MUST run if cold storage exceeds 80% of budget. |
| **Error** | `SessionLimitExceeded` if `max_concurrent_sessions` reached. MUST include current session count and limit in error message. |
| **RBAC** | No role required — init establishes the session and assigns the role. |

##### `dispatch(system_prompt, task_input, **kwargs) → (str, QualityReport)`

| Aspect | Contract |
|--------|----------|
| **Precondition** | A valid session MUST exist (init called). Request signature MUST verify against session_key (§22.2.1). `task_input` MUST pass structural validation (§22.3.1). Session MUST NOT be expired. |
| **Postcondition** | Exactly one LLM invocation MUST occur (plus zero or more continuation windows). The returned string MUST be the complete, unmodified LLM output (Axiom 9). Extracted facts MUST be added to warm state with provenance signatures. `QualityReport` MUST be populated with all fields. |
| **Continuation** | If output is truncated, continuation windows MUST be created automatically until: (a) output completes, (b) `max_windows` reached, or (c) budget exhausted. |
| **Error** | `BudgetExhaustedError` if any cost cap exceeded. `RateLimitExceeded` if dispatch rate limit hit. `SessionExpired` if session timeout reached. All errors MUST include diagnostic details (cap type, current usage, limit). |
| **RBAC** | Requires OPERATOR or ADMIN role. |

##### `ingest(raw_text, source_label?) → ExtractionResult`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session. `raw_text` MUST pass structural validation. `raw_text` MUST NOT exceed `max_task_input_bytes`. |
| **Postcondition** | The extraction pipeline MUST run on `raw_text` without any LLM invocation. Extracted facts MUST be added to warm state with `source_window="ingest:{source_label}"` and `IngestProvenance` metadata. Facts MUST enter quarantine per §22.4.4. |
| **Error** | `RateLimitExceeded` if ingest rate limit hit. Structural validation failures MUST raise `ValidationError` before any processing occurs. |
| **RBAC** | Requires OPERATOR or ADMIN role. |

##### `session_status() → SessionStatus`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session. |
| **Postcondition** | MUST return current session state snapshot. MUST NOT modify any state. |
| **Error** | `SessionExpired` if session timeout reached. |
| **RBAC** | Requires OBSERVER, OPERATOR, or ADMIN role. |

##### `estimate_session(planned_dispatches, avg_envelope_tokens, avg_output_tokens, provider_pricing?) → CostEstimate`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session. |
| **Postcondition** | MUST return estimate without performing any LLM calls or state modifications. |
| **RBAC** | Requires OBSERVER, OPERATOR, or ADMIN role. |

##### `preview_envelope(system_prompt, task_input) → EnvelopePreview`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session. |
| **Postcondition** | MUST construct the envelope that `dispatch()` would use and return its metrics WITHOUT dispatching to the LLM. MUST NOT modify warm state. |
| **RBAC** | Requires OPERATOR or ADMIN role. |

##### `configure(config) → None`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session with ADMIN role. `config` MUST be a valid SecurityConfig or CostControls instance. |
| **Postcondition** | Configuration changes MUST take effect for all subsequent operations in this session. `SecurityConfig.structural_validation` MUST NOT be set to False — attempting to do so MUST raise `SecurityInvariantError`. |
| **RBAC** | Requires ADMIN role. |

##### `reset_session() → None`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session with ADMIN role. |
| **Postcondition** | All warm state MUST be flushed to cold storage. Warm state MUST be cleared. Window count, token counts, and overhead budget MUST be reset. A new session_key MUST be derived (new nonce). |
| **RBAC** | Requires ADMIN role. |

##### `export_state(format?) → bytes`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session with ADMIN role. |
| **Postcondition** | MUST return facts and relations as encrypted data (AES-256-GCM with a separate export key). Embedding vectors MUST NOT be included — they are recomputed on import. |
| **RBAC** | Requires ADMIN role. |

##### `close() → None`

| Aspect | Contract |
|--------|----------|
| **Precondition** | Valid session. |
| **Postcondition** | Warm state MUST be flushed to cold storage. Graph structure (facts, edges, communities) MUST be persisted. Event log MUST be finalized. Session key MUST be zeroed from memory. Subsequent operations on this session MUST raise `SessionClosed`. |
| **RBAC** | Any role. |

#### 6.10.4 Error Taxonomy (Standard Codes)

CRP defines error codes inspired by JSON-RPC 2.0's reserved range convention and gRPC status codes. Application-defined codes use the range 1000-9999.

| Code | Name | Description | Comparable To |
|------|------|-------------|---------------|
| 1001 | `BudgetExhaustedError` | Any cost cap (windows, tokens, rate) exceeded | gRPC `RESOURCE_EXHAUSTED` |
| 1002 | `RateLimitExceeded` | Per-session rate limit hit | gRPC `RESOURCE_EXHAUSTED`, HTTP 429 |
| 1003 | `SessionExpired` | Session timeout reached | gRPC `DEADLINE_EXCEEDED` |
| 1004 | `SessionLimitExceeded` | Max concurrent sessions reached | gRPC `RESOURCE_EXHAUSTED` |
| 1005 | `SessionClosed` | Operation on closed session | gRPC `FAILED_PRECONDITION` |
| 1010 | `ValidationError` | Structural validation failure (§22.3.1) | gRPC `INVALID_ARGUMENT` |
| 1011 | `SecurityInvariantError` | Attempted violation of security invariant | gRPC `PERMISSION_DENIED` |
| 1012 | `SignatureInvalid` | Request HMAC signature verification failed | gRPC `UNAUTHENTICATED` |
| 1013 | `RBACDenied` | Operation not permitted for current role | gRPC `PERMISSION_DENIED` |
| 1020 | `ProviderError` | LLM provider returned an error | gRPC `UNAVAILABLE` |
| 1021 | `ProviderTimeout` | LLM provider did not respond within timeout | gRPC `DEADLINE_EXCEEDED` |
| 1030 | `StateCorrupted` | Cold state integrity verification failed | gRPC `DATA_LOSS` |
| 1031 | `ChainVerificationFailed` | Fact chain signature verification failed | gRPC `DATA_LOSS` |

All errors MUST include:
- `code`: Integer error code from the table above
- `message`: Human-readable description
- `details`: Structured diagnostic data specific to the error type

```
RECORD CRPError:
  code: integer          # Error code from the table above (1001-1031)
  message: string        # Human-readable description
  details: Map<string, any>  # Error-specific structured data
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CRPError",
  "type": "object",
  "required": ["code", "message", "details"],
  "properties": {
    "code": { "type": "integer", "minimum": 1001, "maximum": 1031 },
    "message": { "type": "string" },
    "details": { "type": "object" }
  }
}
```

In languages with exception hierarchies (Python, Java, C#), `CRPError` SHOULD extend the language's base exception type. In languages without exceptions (Go, Rust), CRP errors SHOULD be returned as error values.

**Error response interoperability**: If CRP is exposed via a JSON-RPC transport (SDK), errors MUST be mapped to JSON-RPC error objects using code range -32000 to -32099 (implementation-defined server errors):

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Budget exhausted: max_windows_per_session=100 reached",
    "data": {
      "crp_code": 1001,
      "cap_type": "max_windows_per_session",
      "used": 100,
      "limit": 100,
      "windows_completed": 100,
      "estimated_remaining_cost": 0.45
    }
  },
  "id": 42
}
```

#### 6.10.5 Streaming API

CRP MUST support streaming for `dispatch()` to enable real-time output display. The streaming API follows the **server-streaming** pattern (comparable to gRPC server-streaming RPCs and LSP's `$/progress` notifications).

##### Synchronous Streaming

```
INTERFACE StreamingDispatch:
  dispatch_stream(system_prompt: string, task_input: string, options?: Map<string, any>) 
    -> Stream<StreamEvent>
```

`StreamEvent` is a discriminated union (tagged by `event_type`):

```
RECORD StreamEvent:
  event_type: enum("token", "extraction", "continuation", "window_complete", "done", "error")
  data: any    # Type depends on event_type — see table below
```

| `event_type` | `data` type | Description |
|---|---|---|
| `"token"` | `string` | A generated token (or token batch) |
| `"extraction"` | `ExtractionProgress` | Extraction pipeline progress (after window completes) |
| `"continuation"` | `ContinuationInfo` | A continuation window was triggered |
| `"window_complete"` | `WindowSummary` | A window finished (including continuation windows) |
| `"done"` | `QualityReport` | Final event — complete QualityReport |
| `"error"` | `CRPError` | Error during streaming |

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "StreamEvent",
  "type": "object",
  "required": ["event_type", "data"],
  "properties": {
    "event_type": {
      "type": "string",
      "enum": ["token", "extraction", "continuation", "window_complete", "done", "error"]
    },
    "data": {}
  },
  "discriminator": { "propertyName": "event_type" }
}
```

**Stream contract**:
- The stream MUST emit one or more `"token"` events as the LLM generates output.
- The stream MUST emit exactly one `"done"` event as the final event (or one `"error"` if the operation fails).
- `"token"` events MUST be emitted in generation order. Concatenating all `"token"` data values MUST produce the same string as the non-streaming `dispatch()` output.
- `"continuation"` events MUST be emitted between windows if continuation is triggered.
- Consumers that only care about the final result MAY ignore all events except `"done"`.

##### Asynchronous Streaming

```
INTERFACE AsyncStreamingDispatch:
  dispatch_stream_async(system_prompt: string, task_input: string, options?: Map<string, any>) 
    -> AsyncStream<StreamEvent>
```

The async variant follows identical semantics to the synchronous version. The only difference is that values are yielded asynchronously. Implementations SHOULD use the target language's async iteration pattern (Python: `async for`, JavaScript: `for await...of`, Rust: `Stream` trait, C#: `IAsyncEnumerable`, Go: channel receive).

#### 6.10.6 Async API Variant

All synchronous operations MUST have async equivalents. Each language binding SHOULD follow its native concurrency idiom:

```
INTERFACE AsyncOrchestrator:
  async dispatch(system_prompt: string, task_input: string, options?: Map<string, any>) 
    -> (string, QualityReport)
  async dispatch_intent(intent: TaskIntent) -> (string, QualityReport)
  async ingest(raw_text: string, source_label?: string) -> ExtractionResult
  async session_status() -> SessionStatus
  async estimate_session(...) -> CostEstimate
  async preview_envelope(...) -> EnvelopePreview
  async close() -> void
```

**Language-specific async mapping**:

| Language | Async Pattern | Example Return Type for `async dispatch()` |
|----------|---------------|---------------------------------------------|
| Python | `async def` / `await` / `asyncio` | `Coroutine[Any, Any, tuple[str, QualityReport]]` |
| TypeScript | `async` / `await` / `Promise` | `Promise<[string, QualityReport]>` |
| Rust | `async fn` / `.await` / `Future` | `impl Future<Output = Result<(String, QualityReport), CRPError>>` |
| Go | goroutines / channels | `func Dispatch(...) (string, *QualityReport, error)` |
| C# | `async` / `await` / `Task` | `Task<(string, QualityReport)>` |
| Java | `CompletableFuture` | `CompletableFuture<DispatchResult>` |

**Async contract**:
- Async operations MUST be non-blocking. They MUST NOT block the calling thread/event-loop during LLM generation — they MUST yield control to the runtime's scheduler.
- Concurrent `dispatch()` calls on the SAME session SHOULD be serialized (warm state is mutable). Concurrent calls on DIFFERENT sessions MAY execute in true parallel.
- See §23 (Concurrency Model) for full thread-safety and synchronization specifications.

#### 6.10.7 API Stability Tiers

CRP classifies every API surface into stability tiers, following LSP's versioning model and Rust's stability conventions:

| Tier | Label | Commitment | Breaking Change Policy |
|------|-------|------------|----------------------|
| **Stable** | No annotation | MUST NOT change signature or semantics within a major version (e.g., CRP 2.x). | Requires major version bump (CRP 3.0). |
| **Provisional** | `@provisional` | MAY change in minor versions (e.g., 2.1 → 2.2) with deprecation notice. | One minor version deprecation warning required. |
| **Experimental** | `@experimental` | MAY change or be removed without notice. MUST NOT be relied upon for production. | None required. |

**Current stability classifications**:

| API | Tier | Rationale |
|-----|------|-----------|
| `dispatch()` | **Stable** | Core operation. Used by every application. |
| `dispatch_intent()` | **Stable** | Convenience wrapper around dispatch. |
| `ingest()` | **Stable** | Core data ingestion path. |
| `session_status()` | **Stable** | Monitoring essential. |
| `close()` | **Stable** | Lifecycle essential. |
| `estimate_session()` | **Stable** | Cost control essential. |
| `preview_envelope()` | **Stable** | Debugging essential. |
| `configure()` | **Stable** | ADMIN operations essential. |
| `reset_session()` | **Stable** | ADMIN operations essential. |
| `export_state()` | **Provisional** | Export format may evolve. |
| `dispatch_stream()` | **Provisional** | StreamEvent types may expand. |
| `dispatch_stream_async()` | **Provisional** | Same as `dispatch_stream`. |
| Async variants (`async dispatch`, etc.) | **Provisional** | Concurrency semantics may refine. |

**Deprecation protocol**: When a Provisional API changes, the prior signature MUST continue to work for one minor version with a deprecation warning. The deprecation warning MUST include the replacement API and migration instructions.

#### 6.10.8 Protocol Versioning

CRP uses semantic versioning (Major.Minor.Patch):

- **Major** (e.g., 2.0 → 3.0): Breaking changes to Stable APIs. New major versions MAY remove deprecated features.
- **Minor** (e.g., 2.0 → 2.1): New features, Provisional API changes, new error codes. MUST NOT break Stable APIs.
- **Patch** (e.g., 2.0.0 → 2.0.1): Bug fixes only. MUST NOT change any API surface.

**Version negotiation**: `init()` MUST return the protocol version in the `SessionHandle`. Clients SHOULD verify the version and warn if a minor version mismatch exists. Clients MUST reject a major version mismatch.

```
RECORD SessionHandle:
  session_id: uuid               # UUID v4 — unique per session
  protocol_version: string       # SemVer "2.0.0"
  capabilities: Set<string>      # Granted RBAC permissions (e.g., "dispatch", "configure")
  session_key: bytes             # HMAC-derived session key (NEVER serialized to JSON/wire)
  created_at: number             # Monotonic timestamp (seconds since epoch)
  expires_at: number             # Session expiry timestamp
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SessionHandle",
  "description": "Returned by init(). session_key is NEVER included in JSON serialization.",
  "type": "object",
  "required": ["session_id", "protocol_version", "capabilities", "created_at", "expires_at"],
  "properties": {
    "session_id": { "type": "string", "format": "uuid" },
    "protocol_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "capabilities": { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
    "created_at": { "type": "number" },
    "expires_at": { "type": "number" }
  }
}
```

#### 6.10.10 State Schema Versioning

All persisted CRP data structures (cold state, event log, exported state) MUST carry a schema version to enable forward migration.

```
RECORD PersistedStateHeader:
  schema_version: string          # SemVer for the persisted format (e.g., "2.0.0")
  protocol_version: string        # CRP protocol version that wrote this state
  created_at: number              # Timestamp of state creation
  checksum: string                # BLAKE3 integrity hash of the payload
```

**Migration rules**:
- Implementations MUST be able to read state written by the same Major version (e.g., a CRP 2.3 reader MUST read CRP 2.0 state).
- Minor version differences SHOULD be handled by defaulting missing fields (new fields added in 2.1 default to their declared default values when read by 2.0).
- Major version differences MUST trigger an explicit migration step. Implementations MUST NOT silently reinterpret old-format data.
- If state verification fails (checksum mismatch, unknown schema version, structural corruption), implementations MUST raise `StateCorrupted` (code 1030) and MUST NOT silently discard or ignore the error.

**Migration strategy**:
1. **Forward-compatible writes**: When adding fields in a minor version, implementations MUST write them with defaults that older readers ignore safely.
2. **Explicit migration functions**: When a major version changes the schema, the implementation MUST provide a `migrate(old_state, from_version, to_version) → new_state` function.
3. **Rollback safety**: Before applying a migration, implementations SHOULD create a backup of the original state. If migration fails, the original state MUST be preserved.

#### 6.10.9 Interoperability with Standard Protocols

When CRP is exposed through an SDK transport layer, it MUST map to the target protocol's conventions:

##### JSON-RPC 2.0 Mapping

For cross-process or cross-language access, a CRP SDK MAY expose a JSON-RPC 2.0 transport:

| CRP Operation | JSON-RPC Method | Request Params | Result |
|---------------|----------------|----------------|--------|
| `init()` | `crp.init` | `{app_id, binding_secret?, config?}` | `SessionHandle` (without session_key) |
| `dispatch()` | `crp.dispatch` | `{system_prompt, task_input, ...kwargs}` | `{output, quality_report}` |
| `dispatch_stream()` | `crp.dispatch` + `$/progress` notifications | Same as dispatch | Stream of `StreamEvent` notifications → final result |
| `ingest()` | `crp.ingest` | `{raw_text, source_label?}` | `ExtractionResult` |
| `session_status()` | `crp.sessionStatus` | `{}` | `SessionStatus` |
| `estimate_session()` | `crp.estimateSession` | `{planned_dispatches, ...}` | `CostEstimate` |
| `preview_envelope()` | `crp.previewEnvelope` | `{system_prompt, task_input}` | `EnvelopePreview` |
| `configure()` | `crp.configure` | `{config}` | `null` |
| `close()` | `crp.close` | `{}` | `null` |

**JSON-RPC compliance requirements**:
- All requests MUST include `"jsonrpc": "2.0"`.
- Request IDs MUST be strings or integers (not null, per JSON-RPC best practice).
- Errors MUST use the error object format defined in JSON-RPC §5.1.
- CRP-specific errors MUST use codes in the -32000 to -32099 range (implementation-defined).
- Streaming MUST use JSON-RPC notifications (no `id` field) with method `$/crp/streamEvent`.

##### gRPC Mapping (Future SDK)

If exposing CRP via gRPC, the service definition SHOULD follow:

```protobuf
service CRP {
  rpc Init(InitRequest) returns (SessionHandle);
  rpc Dispatch(DispatchRequest) returns (DispatchResponse);
  rpc DispatchStream(DispatchRequest) returns (stream StreamEvent);
  rpc Ingest(IngestRequest) returns (ExtractionResult);
  rpc SessionStatus(Empty) returns (SessionStatus);
  rpc Close(Empty) returns (Empty);
}
```

gRPC status codes MUST map from CRP error codes per the table in §6.10.4.

---

## 7. FORMAL PROPERTIES

### 7.1 Information Preservation

For any window DAG $G = (W_1, W_2, \ldots, W_n)$, the total information available to the system is:

$$I_{\text{total}} = \sum_{i=1}^{n} I(W_i) \gg I(\text{single window})$$

Each window $W_i$ has access to:
- $I_{\text{fresh}}$: The full context window of fresh attention
- $I_{\text{envelope}}$: The maximally-saturated encoded history
- $I_{\text{tier2}}$: The warm state (accessible via orchestrator-mediated retrieval into the envelope)
- $I_{\text{tier3}}$: Cold state (accessible via CKF multi-mode retrieval into the envelope)

### 7.2 Attention Quality Guarantee

Because each window begins fresh, every token in the window receives **first-pass attention quality**. There is no degradation from accumulated context. The LLM never processes "stale" KV cache entries.

### 7.3 Composability

Window DAGs compose. If DAG $A$ produces facts $F_A$ and DAG $B$ needs $F_A$, the orchestrator includes $F_A$ in $B$'s envelope. No protocol changes needed.

### 7.4 Parallelizability

Any two windows with no data dependency can execute in parallel (on separate model instances, or batched). The protocol does not mandate sequential execution.

### 7.5 Zero-Configuration Guarantee

The default dispatch path (`crp.dispatch(system_prompt, task_input)`) requires **zero configuration**. No task types, no budgets, no weights, no thresholds. The protocol observes and adapts. Power users may provide a `TaskIntent` with optional overrides.

### 7.6 Honest Capacity and Degradation Model

CRP provides **arbitrarily large** context ingestion and token generation — there is no hardcoded ceiling. However, "arbitrarily large" is not "infinite without cost." The protocol is honest about how quality degrades as scale increases:

**Input Ingestion Degradation Curve:**

| Input Size | Extraction Fidelity | Content Type Impact | Mitigation |
|-----------|--------------------|--------------------|------------|
| < $C$ (fits in one window) | **Lossless** — full input in context | All types | N/A |
| $C$ to $10C$ (~1M tokens) | **High** — extraction captures >90% of entities, >80% of key sentences, >70% of relationships | Entity-rich: excellent. Reasoning-dense: good (with Stages 5-6). Narrative: good. | Structure-aware chunking + boundary reconciliation |
| $10C$ to $100C$ (~10M tokens) | **Moderate** — extraction captures >80% of entities, ~60% of key sentences, ~50% of relationships. Envelope carries only the most relevant ~100K tokens of extracted facts. | Entity-rich: good. Reasoning-dense: moderate (deep conditional chains may lose intermediate links). Narrative: moderate. | Warm state compaction + ANN indexing. Multi-dispatch with aspect-specific queries. |
| > $100C$ (>10M tokens) | **Prioritized lossy** — envelope is a highly curated sample. Raw input preserved in Tier 3 for on-demand retrieval. | All types: the envelope is a best-effort selection. Cross-domain relevance increasingly depends on multi-aspect scoring quality. | Tier 3 CKF backfill (graph walk + community retrieval). User should consider hierarchical decomposition (Section 4.5) to process in stages. |

**Output Generation Degradation Across Continuation Chains:**

| Chain Length | Quality Impact | Coherence | Mitigation |
|-------------|---------------|-----------|------------|
| 1-5 windows | **Peak** — fresh KV cache per window, extraction envelopes carry full state | High — style anchor + structural state maintain voice | N/A |
| 5-20 windows | **Good** — extraction-of-extraction starts to compress the representation | Good — voice profile + document map maintain coherence | Voice profile injection. Document map in envelope. |
| 20-50 windows | **Moderate** — semantic drift risk. Accumulated facts grow large (~5K-10K). Envelope construction time increases. | Moderate — re-grounding windows needed periodically | Degradation-triggered re-grounding (compound degradation model). Warm state compaction. |
| 50+ windows | **Adequate** — envelope carries curated top facts. Long-range document arc requires explicit management. | Requires active management — voice profiles, document maps, periodic re-grounding | All mitigations active. User should consider setting `max_continuations` and reviewing accumulated output. |

**Performance Scaling:**

| Operation | Cost at 100 facts | Cost at 1K facts | Cost at 10K facts | Cost at 50K facts |
|-----------|-------------------|-------------------|--------------------|--------------------|
| Envelope construction (bi-encoder) | ~10ms | ~50ms | ~100ms (with ANN: ~15ms) | ~500ms (with ANN: ~20ms) |
| Cross-encoder reranking (top-200) | ~400ms | ~400ms | ~400ms | ~400ms |
| Extraction per window | ~10ms | ~10ms | ~10ms | ~10ms |
| Warm state compaction | N/A | N/A | ~200ms | ~1s |
| Prefill (128K context) | ~3s | ~3s | ~3s | ~3s |

**The honest framing**: CRP enables arbitrarily large context ingestion with **semantically-prioritized, content-type-aware compression** and arbitrarily long token generation with **extraction-maintained, multi-signal-monitored coherence**. Both are real capabilities. Both degrade gracefully with scale. The degradation curve is content-type-dependent: entity-rich content degrades slowly; reasoning-dense content degrades faster; narrative content falls in between. The protocol's mitigations (fact graphs, discourse extraction, multi-aspect scoring, re-grounding windows, CKF enrichment) address the degradation — they don't eliminate it.

**Compound Degradation Model**: In long continuation chains, degradation compounds across windows. Each window's extraction is lossy — even at >90% fidelity, the accumulated loss over many windows becomes significant. CRP formalizes this with a **chain degradation estimate**:

$$d_{\text{chain}}(n) = 1 - \prod_{i=1}^{n} (1 - d_i)$$

Where $d_i$ is the per-window degradation (estimated from extraction yield, supersession rate, and information flow decline for window $i$). For a chain of $n$ windows each with degradation $d_i$:

```
FUNCTION compute_chain_degradation(window_metrics: list[WindowMetrics]) -> float:
    """Estimate cumulative degradation across a continuation chain.
    Returns a value between 0.0 (no degradation) and 1.0 (total loss)."""
    
    cumulative = 1.0
    for m in window_metrics:
        # Per-window degradation estimate from three signals:
        extraction_loss = 1.0 - m.extraction_yield      # How much extraction missed
        supersession_drift = m.supersession_rate * 0.5    # How much knowledge was overwritten
        flow_decline = max(0, m.baseline_flow - m.current_flow) / max(m.baseline_flow, 0.01)
        
        d_i = weighted_mean([extraction_loss, supersession_drift, flow_decline],
                           weights=[0.5, 0.3, 0.2])
        cumulative *= (1.0 - d_i)
    
    return 1.0 - cumulative

FUNCTION should_reground(chain_degradation: float, window_index: int) -> bool:
    """Dynamic re-grounding trigger — replaces fixed every-10-windows rule.
    Triggers re-grounding when compound degradation exceeds threshold."""
    
    REGROUND_THRESHOLD = 0.15   # Re-ground when 15% cumulative degradation estimated
    MIN_WINDOWS_BETWEEN = 3     # Minimum spacing to avoid re-grounding thrashing
    
    if chain_degradation >= REGROUND_THRESHOLD:
        return True
    return False
```

**Why compound degradation matters**: A fixed "re-ground every 10 windows" rule is both wasteful (re-grounds during low-degradation entity-rich chains) and insufficient (misses rapid degradation in reasoning-dense chains). The compound degradation model triggers re-grounding **when needed** based on actual measured quality loss, not on an arbitrary window count. This is analogous to TCP's congestion-triggered retransmission vs. fixed-interval polling.

---

## 8. COMPARISON WITH EXISTING APPROACHES

| Approach | Window Count | Context Quality | State Transfer | Knowledge Persistence | Configuration |
|----------|-------------|-----------------|----------------|----------------------|--------------|
| **Naive single window** | 1 | Degrades with length | N/A | None | None |
| **Sliding window** | N | Good but loses distant info | Implicit (overlap) | None (stateless) | Window size |
| **RAG-augmented** | 1 | Good for retrieved chunks | Retrieved chunks only | Flat vectors | Chunk size, top-k |
| **MemGPT (paging)** | 1 (virtual N) | Good but paging overhead | Function-call paging | Main/archival memory pages | Page sizes |
| **GraphRAG** | 1 | Good for holistic queries | Community summaries | Knowledge graph + communities | Entity types, community resolution |
| **Event Sourcing (generic)** | N/A | N/A (data pattern) | Event replay | Complete history (immutable log) | Event schema |
| **Blackboard Architecture** | N/A | N/A (control pattern) | Shared blackboard | Blackboard state | Knowledge source rules |
| **CRP** | N (dedicated) | **Peak per window** (Tier S–D quality grades) | **Extraction-driven envelope** + hierarchical map-reduce | **CKF: graph + events + communities** | **Zero (adaptive)** + self-calibrating review |

**Detailed Protocol Comparisons:**

**CRP vs. MemGPT**: MemGPT (Packer et al., 2023) virtualizes context via an OS-like paging metaphor — the LLM uses function calls to read/write main memory and archival storage. CRP's key difference: the LLM never manages its own memory. The orchestrator (not the LLM) decides what enters the envelope. This is by design (Axiom 4 — Model Ignorance, Axiom 10 — LLM Amplification). MemGPT's approach requires the LLM to spend tokens on memory management function calls; CRP spends those tokens on actual task output. The trade-off: MemGPT gives the LLM explicit memory control, CRP gives the orchestrator implicit memory optimization.

**CRP vs. GraphRAG**: GraphRAG (Microsoft, 2024) builds knowledge graphs from source documents and uses community detection (Leiden algorithm) to generate hierarchical summaries for holistic queries. CRP's CKF borrows this insight — community detection and summary retrieval (Section 3.7, Mode 4). The key difference: GraphRAG is a static, offline indexing pipeline applied to a fixed corpus. CRP's CKF is dynamic — the graph grows in real-time as extraction processes each window's output, communities are recomputed incrementally, and the graph structure is used for envelope construction (not just retrieval).

**CRP vs. Event Sourcing**: Event Sourcing (Fowler, 2005) stores state changes as an immutable sequence of events rather than mutable current state. CRP adopts this pattern for its fact lifecycle (Section 3.3, FactEvent model). The innovation: CRP combines event sourcing with the fact graph — each event records not just a fact mutation but also edge mutations. This enables temporal graph queries: "What was the relationship structure at Window N?" — a capability that neither traditional event sourcing nor traditional knowledge graphs provide alone.

**CRP vs. Blackboard Architecture**: The blackboard architecture (Erman et al., 1980; Hayes-Roth, 1985) uses a shared data structure (blackboard) with independent knowledge sources that react to blackboard state changes. CRP adopts this for extraction (Section 3.3, Blackboard-Reactive Extraction). The innovation: CRP's blackboard IS the warm state, meaning extraction stages can consider cross-window knowledge history, not just the current window's output. Traditional blackboard systems process a single problem; CRP's blackboard accumulates across an arbitrarily long sequence of problems.

**What CRP synthesizes**: CRP is not any one of these approaches — it synthesizes their strengths into a unified architecture:
- From **MemGPT**: The idea that context management needs explicit, structured memory tiers (but CRP puts the orchestrator in control, not the LLM)
- From **GraphRAG**: Community detection and graph-structured retrieval (but dynamic, not offline)
- From **Event Sourcing**: Immutable history and temporal queries (applied to the fact lifecycle)
- From **Blackboard Architecture**: Reactive, state-driven processing (applied to extraction escalation)
- From **TCP/IP**: Adaptive flow control and congestion avoidance (applied to retrieval breadth and re-grounding triggers)
- Unique to **CRP**: Extraction-driven envelopes, zero-configuration adaptive scoring, content-type-aware pipeline routing, hierarchical map-reduce-validate processing (Section 11), implicit context query signals (Section 12), three-tier cross-window validation (Section 13), model-capability-gated active review cycles (Section 14), scale-aware mode selection (Section 15), and the dual promise of larger AND better context — with honest quality tier reporting at every scale

---

## 9. IMPLEMENTATION GUIDELINES

For implementors adapting CRP to new systems:

1. **Start with `crp.dispatch()`**: Replace every `llm.generate()` call with `crp.dispatch(system_prompt, task_input)`. That's the minimum viable integration.
2. **Implement warm state store**: A structured store for facts with event log, keyed by recency and embedding. SQLite WAL is recommended. Include FactEvent logging from day one.
3. **Implement extraction pipeline**: Start with Stage 1 (regex) + Stage 2 (statistical). Add GLiNER/UIE later as needed. Wire as blackboard-reactive.
4. **Implement envelope builder**: Score facts by semantic similarity (all-MiniLM-L6-v2), pack greedily. Add CKF multi-mode retrieval (graph walk + pattern query) in phase 2.
5. **Add continuation**: Detect physical wall hits, build envelopes from extraction, not raw overlap. Use compound degradation model for re-grounding triggers.
6. **Measure saturation**: Track $\frac{S + E + T}{C}$ for each window. Target > 80%.
7. **Observe and iterate**: Use telemetry to identify underutilized windows, poor extraction yield, or unnecessary continuation chains.
8. **Validate with benchmarks**: Run the standard benchmark suite (see below) to verify extraction yield and degradation curves match the specification.
9. **Enable review cycles**: Review cycles self-calibrate (Section 13-14). Tier 1 (extraction-based validation) is always active. Configure `ReviewCycleConfig` only to override defaults.
10. **Add hierarchical processing**: For Tier C/D scale, implement the map-reduce-validate pipeline (Section 11). Start with a fixed fan-in of 50 and tune based on extraction yield per level.

**Do NOT**:
- Create a task type enum — use TaskIntent
- Hardcode zone budgets — measure and fill
- Hardcode relevance scores — use semantic similarity
- Set generation budgets — let the model generate freely
- Configure completion thresholds — measure information flow
- Flatten facts to vectors on session end — persist graph structure
- Use fixed re-grounding intervals — use compound degradation triggers

### 9.1 Benchmark Specification

Empirical validation requires standardized benchmarks. The following benchmark categories verify CRP's quality promises:

```
BENCHMARK SUITE:

1. EXTRACTION YIELD BENCHMARKS
   Input: Known documents with pre-annotated entities, relations, and discourse structure
   Expected: Extraction captures ≥90% of annotated entities, ≥70% of relations
   Content types: entity-rich (scan output), reasoning-dense (legal contract), narrative (report)
   Measures: per-stage yield, escalation trigger accuracy, false positive rate

2. ENVELOPE QUALITY BENCHMARKS
   Input: Session with 50+ accumulated facts + a new task
   Expected: Envelope contains the top-10 most relevant facts (as judged by human annotation)
   Measures: precision@10, recall@10, nDCG, multi-aspect coverage

3. DEGRADATION CURVE BENCHMARKS
   Input: Continuation chains of 5, 10, 25, 50 windows
   Expected: Measured chain_degradation_estimate matches predicted curve ±10%
   Measures: extraction yield per window, fact supersession rate, envelope relevance drift

4. CKF RETRIEVAL BENCHMARKS
   Input: Cold storage with 10K+ facts across 3+ sessions
   Expected: Graph walk retrieves connected subgraphs, pattern query returns typed matches
   Measures: retrieval latency, mode coverage (which mode found each result), cross-session graph integrity

5. CROSS-SESSION CONTINUITY BENCHMARKS
   Input: Session A generates facts → close → Session B resumes
   Expected: Session B's envelope contains Session A's relevant facts WITH graph structure
   Measures: fact recall, edge recall, community preservation

6. REVIEW CYCLE BENCHMARKS
   Input: 20-window continuation chain with injected inconsistencies
   Expected: Extraction-based review (Tier 1) catches ≥80% of contradictions,
             LLM-targeted review (Tier 2) catches ≥90%, full LLM review (Tier 3) catches ≥95%
   Measures: precision, recall, false positive rate per review tier, overhead per review cycle

7. HIERARCHICAL PROCESSING BENCHMARKS
   Input: 1M-token known document, processed both serially and hierarchically
   Expected: Hierarchical yields ≥40% higher effective context than serial at same scale
   Measures: effective context ratio, cross-level extraction yield, synthesis quality
```

---

## 10. QUALITY TIERS AND SCALE CLASSIFICATION

### 10.1 Honest Capacity Model

CRP provides **unbounded processing throughput** — no hardcoded ceiling on input ingestion or output generation. However, "unbounded throughput" is not "infinite context without cost." The LLM at any given moment has access to exactly **one window** worth of context ($C$ tokens). Everything else is mediated by the extraction pipeline and envelope construction.

This is analogous to how a **research assistant helps a researcher work through a library**. The researcher reads each section IN FULL (the LLM processes each window's actual content). The research assistant maintains a living index of everything read (warm state + fact graph), pulls the most RELEVANT prior pages to have open alongside the current section (source-grounded envelope), and carries the researcher's own running synthesis of themes across sessions (LLM-driven progressive understanding). The researcher can always see both: the original passages AND the synthesized understanding. The assistant also tracks what the researcher found confusing and proactively finds related material (CQS → CKF enrichment). CRP doesn't give the LLM "notes about a book" — it helps the LLM **read the book**, with the right pages open, the right passages highlighted, and the LLM's own accumulated understanding readily available.

CRP is honest about this. The protocol defines **quality tiers** that characterize the effective context quality at different scales:

### 10.2 Quality Tier Definitions

| Tier | Scale (tokens) | Windows ($C = 128K$) | Effective Context | Mechanism Required |
|------|---------------|----------------------|-------------------|-------------------|
| **S** | $\leq C$ (fits in 1 window) | 1 | **Lossless** — full input in context | Native window |
| **A** | $C$ to $10C$ (~1.3M) | 2–10 | **Near-lossless** ($<5\%$ measured degradation) | Linear chain + CKF enrichment |
| **B** | $10C$ to $100C$ (~13M) | 10–100 | **Good** ($5{-}20\%$ degradation) | Chain + compound degradation monitoring + re-grounding |
| **C** | $100C$ to $1{,}000C$ (~130M) | 100–1,000 | **Structured** ($20{-}40\%$ degradation) | **Hierarchical processing required** |
| **D** | $>1{,}000C$ (approaching 1B+) | 1,000+ | **Synthesis** ($>40\%$ base, offset by hierarchy) | Multi-level hierarchy + validation + review cycles |

### 10.3 Why Serial Chains Cannot Scale

The compound degradation formula (Section 7.6) mathematically prohibits serial chains at extreme scale. Even with 99% per-window extraction fidelity ($d_i = 0.01$):

$$d_{\text{chain}}(100) = 1 - 0.99^{100} = 0.634 \quad (63\% \text{ cumulative loss})$$
$$d_{\text{chain}}(1000) = 1 - 0.99^{1000} \approx 1.0 \quad (\text{total loss})$$

Re-grounding mitigates but doesn't eliminate this: re-extracting from 1B tokens of accumulated output still produces an envelope that represents only $\frac{C}{N \cdot C} = \frac{1}{N}$ of the original — at $N = 7{,}813$ windows (1B tokens / 128K window), the envelope samples $0.013\%$ of the input.

**Serial chains are valid for Tiers S, A, and B.** For Tiers C and D, hierarchical processing is mandatory (Section 11).

### 10.4 Effective Context Formula

For serial processing:
$$\text{EffCtx}_{\text{serial}}(N) = C \times \left(1 - d_{\text{chain}}(N)\right)$$

For hierarchical processing with fan-in $k$:
$$\text{EffCtx}_{\text{hier}}(N) = C \times \left(1 - d_{\text{chain}}\left(\lceil \log_k(N) \rceil\right)\right)$$

**Concrete examples** (with $C = 128K$, $d_i = 0.10$, $k = 100$):

| Input Size | Serial Windows | Serial Effective | Hier Levels | Hier Effective |
|-----------|---------------|-----------------|-------------|---------------|
| 1M (Tier A) | 8 | $128K \times 0.43 = 55K$ | 1 | $128K \times 0.90 = 115K$ |
| 10M (Tier B) | 78 | $\approx 0$ | 1 | $128K \times 0.90 = 115K$ |
| 100M (Tier C) | 781 | $\approx 0$ | 2 | $128K \times 0.81 = 104K$ |
| 1B (Tier D) | 7,813 | $\approx 0$ | 3 | $128K \times 0.73 = 93K$ |
| 100B (Tier D) | 781,250 | $\approx 0$ | 4 | $128K \times 0.66 = 84K$ |

**With hierarchical processing, 1 billion tokens yields 73% effective context** — 93K tokens of genuinely useful, extracted, synthesized context. This is the "1B Horizon" — a real, measurable, defensible claim.

### 10.5 Concrete Timing: Serial Fallback Cost Model

Hierarchical processing assumes parallelism ("when hardware allows"). When running on a single GPU with one model instance, all windows are serial. The concrete wall-clock costs:

| Scale | Windows (serial) | Windows (hierarchical) | Time @ 1 GPU (serial) | Time @ 1 GPU (hierarchical) | Time @ 4 GPUs (parallel) |
|-------|-----------------|----------------------|---------------------|---------------------------|-------------------------|
| 1M (Tier A) | 8 | 8 | ~40s | ~40s | ~10s |
| 10M (Tier B) | 78 | 78 | ~6.5 min | ~6.5 min | ~1.6 min |
| 100M (Tier C) | 781 | ~120 | ~65 min | ~10 min | ~2.5 min |
| 1B (Tier D) | 7,813 | ~220 | ~10.8 hrs | ~18 min | ~4.5 min |

**Assumptions**: 128K context window, 3s prefill + 2s generation per window, CRP overhead ~200ms/window.

**Key takeaway**: Hierarchical processing is not just a quality improvement — it is a **massive latency reduction** even on a single GPU. Processing 1B tokens drops from 10.8 hours (serial) to 18 minutes (hierarchical), because hierarchy reduces the window count from 7,813 to ~220.

**Cloud API timing**: With a cloud API at 100 requests/minute rate limit:

| Scale | Windows | Wall-clock @ 100 req/min |
|-------|---------|-------------------------|
| 10M (Tier B) | 78 | ~47 seconds |
| 100M (Tier C, hier.) | ~120 | ~72 seconds |
| 1B (Tier D, hier.) | ~220 | ~2.2 minutes |

### 10.6 Quality Tier Reporting

Every `crp.dispatch()` response includes quality metadata:

```python
@dataclass
class QualityReport:
    """Returned with every dispatch response."""
    tier: str                       # "S" | "A" | "B" | "C" | "D"
    total_tokens_processed: int     # Input + output across all windows
    window_count: int               # Total windows used
    chain_degradation: float        # Compound degradation estimate (0.0 – 1.0)
    effective_context_tokens: int   # Estimated useful context (C × (1 - degradation))
    processing_mode: str            # "serial" | "hierarchical" | "parallel"
    review_cycles_run: int          # Number of review cycles executed
    hierarchy_levels: int           # 0 for serial, 1+ for hierarchical
```

The protocol NEVER silently degrades. The caller always knows the quality tier, the estimated degradation, and the processing mode used.

---

## 11. HIERARCHICAL PROCESSING

### 11.1 The Map-Reduce-Validate Pattern

For Tier C and D processing, CRP uses a **hierarchical map-reduce-validate** pattern that bounds compound degradation to $O(\log N)$ extraction levels instead of $O(N)$ serial windows:

```
HIERARCHICAL PROCESSING PIPELINE:

Level 0 (Raw Input):
  Input:  N tokens (e.g., 1B)
  Action: Chunk into S segments of size ≤ k×C (e.g., 100 segments of 10M each)

Level 1 (Map Phase — Parallel):
  Input:  Each segment S_i (10M tokens)
  Action: Process via serial CRP chain (Tier B — ~78 windows each)
  Output: Per-segment synthesis S'_i (~10K tokens each, containing key facts, entities, relationships)
  Total:  S × 10K = 1M tokens of synthesized content
  Note:   Segments processed IN PARALLEL when hardware allows

Level 2 (Reduce Phase — Parallel):
  Input:  All S' syntheses grouped into R batches (~1M / R tokens each)
  Action: Synthesis windows merge per-segment outputs into aspect syntheses
  Output: R aspect summaries (~4K tokens each)
  Total:  R × 4K = 32K tokens of aspect-synthesized content

Level 3 (Validate + Final):
  Input:  All aspect summaries (32K tokens) — fits in ONE window
  Action: Final synthesis window with full aspect context
  Output: The requested generation, grounded in hierarchically synthesized 1B tokens

COMPOUND DEGRADATION: 3 levels × d_i = only d_chain(3), not d_chain(7813)
```

### 11.2 Hierarchical Dispatch

```python
FUNCTION hierarchical_dispatch(task_intent, large_input, config):
  """Process Tier C/D inputs via map-reduce-validate."""
  
  # 1. Determine hierarchy parameters
  segment_size = config.segment_size or (100 * task_intent.context_window)  # Default: 100× window
  fan_in = config.fan_in or 50                                              # Segments per reduce batch
  
  # 2. MAP: chunk and process segments in parallel
  segments = structure_aware_chunk(large_input, segment_size)
  segment_syntheses = []
  
  for segment in parallel_dispatch(segments):
    synthesis = crp.dispatch(
      system_prompt=f"Summarize and extract ALL key facts, entities, relationships, "
                    f"arguments, and data from this segment. Be comprehensive.",
      task_input=segment,
      expected_output_length="long"
    )
    segment_syntheses.append(synthesis)
  
  # 3. REDUCE: merge syntheses in batches
  while len(segment_syntheses) > fan_in:
    batches = chunk_list(segment_syntheses, fan_in)
    next_level = []
    for batch in batches:
      merged = crp.dispatch(
        system_prompt=f"Synthesize these {len(batch)} segment summaries into a unified "
                      f"analysis. Preserve all key facts, resolve contradictions, "
                      f"identify cross-segment patterns.",
        task_input="\n\n---\n\n".join(batch)
      )
      next_level.append(merged)
    segment_syntheses = next_level
  
  # 4. VALIDATE: cross-segment consistency check (see Section 13)
  validation = run_cross_window_validation(segment_syntheses, task_intent)
  
  # 5. FINAL: generate output with full synthesized context
  final_context = "\n\n---\n\n".join(segment_syntheses)
  if validation.issues:
    final_context += f"\n\n[VALIDATION NOTES]\n{format_issues(validation.issues)}"
  
  return crp.dispatch(
    system_prompt=task_intent.system_prompt,
    task_input=f"{final_context}\n\n---\n\n{task_intent.task_input}"
  )
```

### 11.3 When Hierarchical Processing Activates

Hierarchical processing is **automatic** — the orchestrator detects the quality tier and switches modes:

```python
FUNCTION select_processing_mode(task_intent, input_tokens, context_window):
  """Auto-select serial vs hierarchical based on scale."""
  
  windows_needed = ceil(input_tokens / context_window)
  
  if windows_needed <= 10:       # Tier S or A
    return ProcessingMode.SERIAL
  elif windows_needed <= 100:    # Tier B
    return ProcessingMode.SERIAL_WITH_REGROUNDING
  elif windows_needed <= 1000:   # Tier C
    return ProcessingMode.HIERARCHICAL
  else:                          # Tier D
    return ProcessingMode.HIERARCHICAL_MULTI_LEVEL
```

The user can override via `task_intent.processing_mode`, but the default is auto-detection.

---

## 12. CONTEXT QUERY SIGNALS (CQS) — Implicit LLM Feedback

### 12.1 The One-Way Problem

Current CRP architecture is unidirectional: Orchestrator → LLM. The LLM cannot request additional context because Axiom 4 (Model Ignorance) means it doesn't know CRP exists. However, LLMs **implicitly signal context hunger** through their output patterns.

### 12.2 Context Hunger Detection

The orchestrator monitors the generation stream for patterns that indicate the LLM needs more context than the envelope provided:

```python
FUNCTION detect_context_hunger(generation_stream, warm_state):
  """Detect implicit LLM signals that more context is needed.
  Returns a ContextHungerSignal or None."""
  
  signals = []
  
  # Signal 1: Hedging language — the LLM is uncertain
  hedging_patterns = [
    r"it is unclear whether", r"without (more|additional|further) information",
    r"cannot (determine|confirm|verify)", r"(may|might|could) (be|have)",
    r"insufficient (data|evidence|context)", r"further (analysis|investigation) (is )?needed",
    r"based on (limited|available) (information|data|context)"
  ]
  hedging_count = sum(len(re.findall(p, generation_stream, re.I)) for p in hedging_patterns)
  if hedging_count >= 3:  # Multiple hedging instances = strong signal
    signals.append(ContextHungerSignal(
      signal_type="hedging",
      strength=min(hedging_count / 5, 1.0),
      topic=extract_uncertain_topic(generation_stream)
    ))
  
  # Signal 2: Placeholder patterns — the LLM is referencing missing context
  placeholder_patterns = [
    r"\[(?:need|missing|TODO|TBD|citation needed)\]",
    r"as (?:discussed|mentioned|noted|shown|described) (?:earlier|previously|above|before)",
    r"(?:per|according to|referring to) the (?:previous|prior|earlier) (?:analysis|section|findings)",
    r"(?:see|refer to) (?:section|chapter|part) \d+"
  ]
  placeholder_count = sum(len(re.findall(p, generation_stream, re.I)) for p in placeholder_patterns)
  if placeholder_count >= 2:
    signals.append(ContextHungerSignal(
      signal_type="reference_miss",
      strength=min(placeholder_count / 3, 1.0),
      topic=extract_referenced_topic(generation_stream)
    ))
  
  # Signal 3: Repetition — the LLM is cycling on the same facts
  fact_mentions = extract_inline_facts(generation_stream)
  repeated = [f for f in fact_mentions if fact_mentions.count(f) >= 3]
  if repeated:
    signals.append(ContextHungerSignal(
      signal_type="repetition",
      strength=min(len(set(repeated)) / 3, 1.0),
      topic=repeated[0]  # Most repeated topic
    ))
  
  return signals if signals else None
```

### 12.3 Context Enrichment Response

When context hunger is detected, the orchestrator enriches the next window (or re-dispatches the current window) with targeted context:

```python
FUNCTION respond_to_context_hunger(signals, warm_state, ckf, current_envelope):
  """Build an enriched envelope targeting the LLM's apparent context needs."""
  
  for signal in signals:
    topic = signal.topic
    
    if signal.signal_type == "hedging":
      # The LLM is uncertain about a topic — pull more context from CKF
      additional_facts = ckf.retrieve(
        query=topic,
        modes=[GraphWalkRetrieval(seed_facts=topic_related_ids(topic)), 
               SemanticFallbackRetrieval(query_embedding=embed(topic), top_k=20)],
        budget_tokens=2000
      )
      current_envelope.inject_targeted(additional_facts, reason=f"Context enrichment: {topic}")
    
    elif signal.signal_type == "reference_miss":
      # The LLM is referencing something not in the envelope — find it
      referenced = ckf.retrieve(
        query=topic,
        modes=[PatternQueryRetrieval(keywords=extract_keywords(topic))],
        budget_tokens=3000
      )
      current_envelope.inject_targeted(referenced, reason=f"Referenced content: {topic}")
    
    elif signal.signal_type == "repetition":
      # The LLM is cycling — it needs DIFFERENT context on this topic
      current_facts = current_envelope.facts_matching(topic)
      alternative_facts = ckf.retrieve(
        query=topic,
        modes=[GraphWalkRetrieval(seed_facts=current_facts, min_hops=2)],  # 2+ hops = related but different
        budget_tokens=2000,
        exclude=current_facts  # Don't retrieve what's already in the envelope
      )
      current_envelope.inject_targeted(alternative_facts, reason=f"Alternative context: {topic}")
  
  return current_envelope
```

### 12.4 Re-Dispatch vs Next-Window Enrichment

Context hunger can trigger two responses:

1. **Mid-chain enrichment** (default): The enriched facts go into the NEXT continuation window's envelope. Low overhead — no wasted generation.
2. **Re-dispatch** (when `signal.strength ≥ 0.8`): The current window is abandoned, and a new window is dispatched with the enriched envelope. Higher overhead but prevents an entire window of low-quality output.

```python
if max(s.strength for s in signals) >= 0.8 and tokens_generated < 500:
  # Strong hunger signal early in generation → re-dispatch is worth it
  abandon_current_window()
  return dispatch_with_enriched_envelope(enriched_envelope)
else:
  # Moderate signal or late in generation → enrich next window
  warm_state.pending_enrichment = enriched_envelope
```

---

## 13. CROSS-WINDOW CONSISTENCY VALIDATION (CWCV)

### 13.1 The Consistency Problem

Each window generates independently. Without validation, Window 30's output can contradict Window 5's output, numbers can become inconsistent, and argument strands can drift. The existing contradiction detection (Section 3.4) catches individual fact supersession, but it doesn't catch **cross-window logical inconsistency** in generated output.

### 13.2 Three-Tier Validation System

CWCV operates as a three-tier system where Tier 1 ALWAYS runs (zero LLM cost), Tier 2 runs for medium-scale chains, and Tier 3 runs for large-scale chains with capable models:

**Tier 1 — Extraction-Based Validation (Always Active, Zero LLM Cost):**

```python
FUNCTION extraction_based_validation(warm_state, window_outputs):
  """Pure orchestrator-side validation — works with ANY model, including weak ones."""
  
  issues = []
  
  # Check 1: Numerical consistency
  #   Extract all numbers with context from all windows (Stage 1 regex)
  #   Flag when the same metric appears with different values
  numbers = extract_all_numbers_with_context(window_outputs)
  for metric, values in group_by_metric(numbers).items():
    if len(set(values)) > 1:
      issues.append(ConsistencyIssue(
        type="numerical_contradiction",
        description=f"'{metric}' appears as {values} across windows",
        severity="high",
        windows=values.source_windows
      ))
  
  # Check 2: Entity reference integrity
  #   All entities referenced in later windows should have been defined/extracted earlier
  entity_first_defined = {}
  entity_referenced = {}
  for i, output in enumerate(window_outputs):
    defined = extract_entities(output)
    referenced = extract_entity_references(output)
    for e in defined:
      entity_first_defined.setdefault(e, i)
    for e in referenced:
      if e not in entity_first_defined:
        issues.append(ConsistencyIssue(
          type="undefined_reference",
          description=f"Window {i} references '{e}' which was never defined",
          severity="medium"
        ))
  
  # Check 3: Embedding-based contradiction detection
  #   Compare fact embeddings across windows — high similarity + textual difference = contradiction
  for fact_a in warm_state.facts_from_windows(range(0, len(window_outputs))):
    for fact_b in warm_state.facts_from_windows(range(fact_a.window + 1, len(window_outputs))):
      sim = cosine_similarity(fact_a.embedding, fact_b.embedding)
      if sim > 0.85:
        text_diff = edit_distance_normalized(fact_a.text, fact_b.text)
        if text_diff > 0.3:
          issues.append(ConsistencyIssue(
            type="semantic_contradiction",
            description=f"Potential contradiction: '{fact_a.text[:80]}' vs '{fact_b.text[:80]}'",
            severity="high"
          ))
  
  # Check 4: Structural completeness (via document map)
  doc_map = warm_state.document_map
  if doc_map:
    missing_sections = [s for s in doc_map.planned_sections if not doc_map.has_content(s)]
    if missing_sections:
      issues.append(ConsistencyIssue(
        type="structural_gap",
        description=f"Planned sections missing content: {missing_sections}",
        severity="medium"
      ))
  
  return ValidationResult(tier=1, issues=issues)
```

**Tier 2 — LLM-Targeted Validation (Binary Questions, Works with 2B+ Models):**

```python
FUNCTION targeted_llm_validation(issues_from_tier1, warm_state, task_intent):
  """Dispatch focused binary questions to the LLM to confirm/deny contradictions.
  Designed for SMALL models — each question is short, binary, requires minimal reasoning."""
  
  confirmed_issues = []
  
  for issue in issues_from_tier1:
    if issue.type == "semantic_contradiction":
      # Short, binary question — even 2B models handle this well
      response = crp.dispatch(
        system_prompt="Answer YES or NO only. Do not explain.",
        task_input=f'Do these two statements contradict each other?\n'
                   f'Statement A: "{issue.facts[0].text}"\n'
                   f'Statement B: "{issue.facts[1].text}"\n'
                   f'Answer YES or NO:',
        max_output_tokens=10  # Minimize token waste
      )
      if "YES" in response.upper():
        issue.confirmed = True
        confirmed_issues.append(issue)
    
    elif issue.type == "numerical_contradiction":
      # Always confirmed — numerical mismatches are objective
      issue.confirmed = True
      confirmed_issues.append(issue)
  
  return ValidationResult(tier=2, issues=confirmed_issues)
```

**Tier 3 — Full LLM Review (Open-Ended Analysis, Requires 7B+ or Strong Reasoning Models):**

```python
FUNCTION full_llm_review(warm_state, accumulated_output, task_intent):
  """Dispatch a dedicated review window for comprehensive quality assessment.
  ONLY for models with demonstrated reasoning capability (see Section 13.3)."""
  
  # Build a review envelope with key claims from ALL windows
  key_claims = warm_state.get_highest_confidence_facts(top_k=50)
  document_map = warm_state.document_map
  
  review_result = crp.dispatch(
    system_prompt=(
      "You are a quality reviewer. Analyze the following document summary for:\n"
      "1. Contradictions between sections\n"
      "2. Unsupported claims\n"
      "3. Logical inconsistencies\n"
      "4. Missing connections between related findings\n"
      "5. Argument drift (conclusions that don't follow from premises)\n"
      "Output a numbered list of issues found. If no issues, output 'NO ISSUES FOUND.'"
    ),
    task_input=f"[DOCUMENT MAP]\n{serialize_document_map(document_map)}\n\n"
               f"[KEY CLAIMS]\n{serialize_facts(key_claims)}\n\n"
               f"[TASK]\n{task_intent.task_input[:500]}",
    expected_output_length="short"
  )
  
  # Parse the review output into structured issues
  issues = parse_review_output(review_result)
  return ValidationResult(tier=3, issues=issues)
```

### 13.3 Model Capability Assessment for Review Tiers

The review system self-calibrates to the model's capability. The orchestrator doesn't assume the model can review — it **tests** during the session's first review cycle:

```python
FUNCTION assess_review_capability(model_info, warm_state):
  """Determine the highest review tier this model can reliably execute.
  Called once per session. Result cached."""
  
  # Tier 1: ALWAYS available — no LLM involvement
  max_tier = 1
  
  # Tier 2 probe: Can the model answer binary questions reliably?
  probe_response = crp.dispatch(
    system_prompt="Answer YES or NO only.",
    task_input='Do these contradict?\nA: "The server runs on port 80."\nB: "The server runs on port 443."\nAnswer:',
    max_output_tokens=10
  )
  if "YES" in probe_response.upper():
    max_tier = 2
  
  # Tier 3 probe: Can the model produce structured analysis?
  if max_tier == 2:
    probe_response = crp.dispatch(
      system_prompt="List any logical issues in this pair of statements. Number each issue.",
      task_input='Statement 1: "All vulnerabilities were patched." Statement 2: "CVE-2024-1234 remains exploitable."',
      max_output_tokens=200
    )
    # Check if response contains numbered issues and identifies the contradiction
    if re.search(r'\d+[.)]', probe_response) and re.search(r'contradict|inconsisten|conflict', probe_response, re.I):
      max_tier = 3
  
  return max_tier
```

### 13.4 Review Cycle Configuration

```python
@dataclass
class ReviewCycleConfig:
    """Configuration for active review cycles. Mandatory — Tier 1 always runs."""
    
    enabled: bool = True                      # Master switch — Tier 1 always runs regardless
    tier_1_interval: int = 5                  # Run extraction-based validation every N windows
    tier_2_enabled: bool = True               # Enable LLM-targeted binary validation
    tier_2_interval: int = 10                 # Run Tier 2 every N windows (when enabled)
    tier_3_enabled: bool = True               # Enable full LLM review (auto-disabled for weak models)
    tier_3_interval: int = 20                 # Run Tier 3 every N windows (when enabled)
    tier_3_min_model_capability: int = 3      # Only run Tier 3 if assess_review_capability >= 3
    correction_mode: str = "flag"             # "flag" (report issues) | "correct" (auto-fix via redispatch)
    max_correction_windows: int = 3           # Max windows spent on corrections per review cycle
```

**Default behavior**: Tier 1 ALWAYS runs (zero cost). Tier 2 and 3 are enabled by default but auto-calibrate to the model's capability. If the model fails the Tier 2 probe, only Tier 1 runs. If the model passes Tier 2 but fails Tier 3, only Tiers 1-2 run. The user never needs to configure this — it self-adapts.

**Mandatory participation**: Even with the weakest model (0.5B parameter, fails all probes), the LLM still **actively participates** in context enrichment through the normal CRP loop — the orchestrator builds envelopes from the LLM's own extracted output, and Context Query Signals (Section 12) detect when the LLM needs more context. The review tiers add VALIDATION and CORRECTION on top, but the base CRP loop already makes the LLM an active participant in its own context management.

### 13.5 Correction Pipeline

When issues are found, the orchestrator can either flag them (default) or auto-correct:

```python
FUNCTION apply_corrections(issues, warm_state, task_intent, config):
  """Auto-correct confirmed issues by re-dispatching targeted correction windows."""
  
  if config.correction_mode == "flag":
    # Just include issues in the next envelope's critical state
    warm_state.blockers.extend([
      f"[CONSISTENCY ISSUE] {issue.description}" for issue in issues
    ])
    return
  
  # correction_mode == "correct" — dispatch correction windows
  corrections_applied = 0
  for issue in sorted(issues, key=lambda i: i.severity, reverse=True):
    if corrections_applied >= config.max_correction_windows:
      # Budget exceeded — flag remaining issues instead
      warm_state.blockers.append(f"[UNFIXED] {issue.description}")
      continue
    
    if issue.type == "numerical_contradiction":
      # Re-dispatch the window that introduced the wrong number
      # with the correct value from the earlier window included in the envelope
      correction = crp.dispatch(
        system_prompt=task_intent.system_prompt,
        task_input=f"CORRECTION NEEDED: {issue.description}. "
                   f"The correct value from earlier analysis is: {issue.canonical_value}. "
                   f"Rewrite the affected passage with the correct value.",
        max_output_tokens=500
      )
      warm_state.apply_correction(issue.window, correction)
      corrections_applied += 1
    
    elif issue.type == "semantic_contradiction":
      # Include both contradicting facts in the envelope and ask the LLM to resolve
      correction = crp.dispatch(
        system_prompt="Resolve this contradiction based on the available evidence.",
        task_input=f'Fact A (Window {issue.facts[0].window}): "{issue.facts[0].text}"\n'
                   f'Fact B (Window {issue.facts[1].window}): "{issue.facts[1].text}"\n'
                   f"Which is correct based on the evidence? Provide the corrected statement.",
        max_output_tokens=200
      )
      warm_state.apply_correction(issue.facts[1].window, correction)
      corrections_applied += 1
```

---

## 14. ACTIVE REVIEW CYCLES — LLM AS COLLABORATIVE PARTNER

### 14.1 Beyond Passive Generation

The standard CRP loop treats the LLM as a **passive text generator**: receive prompt → produce output → repeat. At scale (10+ windows), this underutilizes the LLM's reasoning capability. Active Review Cycles add three interaction patterns that make the LLM a **collaborative partner** in its own output — without violating Axiom 4 (Model Ignorance):

### 14.2 Pre-Generation Planning Windows

Before generating a long document (predicted chain length > 5 windows), dispatch a **planning window**:

```python
FUNCTION pre_generation_plan(task_intent, warm_state):
  """Ask the LLM to plan its own generation — the output structures subsequent windows."""
  
  plan = crp.dispatch(
    system_prompt="You are a document architect. Given this task, produce a detailed outline "
                  "with: (1) sections with estimated length, (2) key points per section, "
                  "(3) information dependencies between sections.",
    task_input=task_intent.task_input
  )
  
  # Extract structure from the plan
  planned_sections = extract_section_plan(plan)
  dependencies = extract_section_dependencies(plan)
  
  # Inject into warm state — all subsequent envelopes carry the plan
  warm_state.document_map = DocumentMap.from_plan(planned_sections, dependencies)
  warm_state.generation_plan = plan
  
  return planned_sections
```

The LLM doesn't know it's "planning for CRP" — it thinks it's performing a normal outlining task. But the orchestrator uses the plan to:
- Pre-stage CKF retrievals for each planned section
- Set expected window counts per section
- Detect when generation drifts from the plan
- Populate the document map from the start

### 14.3 Checkpoint Review Windows

Every N windows (configurable, default: every 10 for Tier 3 models), dispatch a **checkpoint review**:

```python
FUNCTION checkpoint_review(warm_state, window_index, task_intent, review_config):
  """Ask the LLM to review its own output-so-far for quality and consistency.
  
  IMPORTANT: This function gates on model capability. If the model cannot
  produce structured review output (Tier 3), this function is a no-op.
  Tier 1-2 validation (Section 13) still runs regardless."""
  
  if warm_state.model_review_capability < 3:
    return None  # Model not capable — rely on Tier 1-2 only
  
  if (window_index % review_config.tier_3_interval) != 0:
    return None  # Not at review interval
  
  # Build concise review input from document map + recent facts
  review_input = (
    f"[DOCUMENT PRODUCED SO FAR]\n{serialize_document_map(warm_state.document_map)}\n\n"
    f"[ORIGINAL TASK]\n{task_intent.task_input[:500]}\n\n"
    f"[KEY FACTS ({len(warm_state.active_facts())} total, showing top 30)]\n"
    f"{serialize_facts(warm_state.get_highest_confidence_facts(30))}\n\n"
    f"[REMAINING WORK]\n{serialize_gap(warm_state.gap_analysis)}"
  )
  
  review = crp.dispatch(
    system_prompt=(
      "Review this document-in-progress. Identify:\n"
      "1. Are we on track with the original task?\n"
      "2. Any contradictions or inconsistencies in the key facts?\n"
      "3. What should the next sections prioritize?\n"
      "4. Are there gaps not covered by the remaining work list?\n"
      "Be concise — bullet points only."
    ),
    task_input=review_input,
    expected_output_length="short"
  )
  
  # Extract review guidance and inject into subsequent envelopes
  guidance = extract_review_guidance(review)
  warm_state.review_guidance = guidance
  warm_state.blockers.extend(guidance.issues)
  
  return guidance
```

### 14.4 Post-Generation Self-Assessment

After the final window completes, dispatch a self-assessment:

```python
FUNCTION post_generation_assessment(accumulated_output, task_intent, warm_state):
  """Ask the LLM to assess its own completed output. Gate on model capability."""
  
  if warm_state.model_review_capability < 3:
    # Weak model — run Tier 1 + 2 validation only
    return extraction_based_validation(warm_state, accumulated_output)
  
  # Strong model — full self-assessment
  assessment = crp.dispatch(
    system_prompt=(
      "Review this completed document for quality. Score 1-10 and list specific issues:\n"
      "- Completeness: Does it cover everything asked?\n"
      "- Consistency: Any contradictions?\n"
      "- Accuracy: Any unsupported claims?\n"
      "- Structure: Is the organization logical?\n"
      "Output format: SCORE: X/10 followed by numbered issues."
    ),
    task_input=f"[TASK]\n{task_intent.task_input[:300]}\n\n"
               f"[DOCUMENT SUMMARY ({warm_state.window_count} windows)]\n"
               f"{serialize_document_map(warm_state.document_map)}\n\n"
               f"[KEY CLAIMS]\n{serialize_facts(warm_state.get_highest_confidence_facts(40))}",
    expected_output_length="short"
  )
  
  # Parse assessment
  score_match = re.search(r'SCORE:\s*(\d+)/10', assessment)
  score = int(score_match.group(1)) if score_match else None
  issues = parse_numbered_list(assessment)
  
  # If score is low and correction_mode is "correct", trigger targeted re-generation
  if score and score < 6 and warm_state.review_config.correction_mode == "correct":
    for issue in issues[:warm_state.review_config.max_correction_windows]:
      fix = crp.dispatch(
        system_prompt=task_intent.system_prompt,
        task_input=f"Fix this issue in the document: {issue}",
        max_output_tokens=1000
      )
      warm_state.apply_post_correction(fix, issue)
  
  return AssessmentResult(score=score, issues=issues)
```

### 14.5 The Tiered Participation Model

Here is how the LLM participates in context management at each capability level:

| Capability | Tier 1 (Any Model) | Tier 2 (2B+) | Tier 3 (7B+ / Strong Reasoning) |
|---|---|---|---|
| **Context enrichment** | CRP envelope loop — LLM output feeds extraction, facts feed next envelope | Same + CQS-detected enrichment | Same + pre-staged CKF per plan |
| **Consistency validation** | Extraction-based: numerical, entity reference, embedding contradiction | Same + binary YES/NO confirmation | Same + open-ended review |
| **Quality control** | Document map tracking, structural gap detection | Same + targeted binary probes | Same + full checkpoint reviews + self-assessment |
| **Correction** | Issue flagging in blocker section of envelope | Same + targeted corrections on confirmed issues | Same + post-generation re-writing of scored sections |
| **Planning** | Orchestrator-estimated section plan from task analysis | Same | LLM-generated outline → document map |
| **Overhead** | ~0% extra LLM calls | ~2-5% extra LLM calls (10-token binary questions) | ~10-15% extra LLM calls (review + plan + assessment) |

**Key insight**: Even the weakest model (0.5B, fails all probes) still participates in its own context enrichment through the BASE CRP loop. Every window's output is extracted → facts feed the next envelope → the LLM's own discoveries inform its future context. Context Query Signals (Section 12) detect when the LLM's output shows uncertainty and trigger targeted CKF retrieval. The review tiers add VALIDATION (catching errors) and CORRECTION (fixing errors) — they don't add PARTICIPATION (which is inherent in CRP's architecture).

### 14.6 Why This Doesn't Waste Tokens on Weak Models

The self-calibrating probe (Section 13.3) ensures:
- A 0.5B model: runs Tier 1 only — **zero** extra LLM calls
- A 2B model: runs Tiers 1-2 — **tiny** extra calls (binary questions, ~10 tokens each)
- A 7B+ model: runs Tiers 1-3 — **moderate** extra calls (review windows)
- A 70B+ model: runs all tiers + correction mode — **full** collaborative generation

No tokens are wasted on models that can't productively use them. The protocol degrades gracefully to pure extraction-based validation for weak models.

---

## 15. SCALE-AWARE MODE SELECTION

### 15.1 Unified Mode Table

The orchestrator automatically selects the processing strategy based on scale AND model capability:

| Scale | Windows | Serial Chain | Hierarchy | CQS | Validation | Review Cycles | Overhead |
|-------|---------|-------------|-----------|-----|------------|--------------|----------|
| **Tier S** ($\leq C$) | 1 | N/A | No | No | No | No | 0% |
| **Tier A** ($C$–$10C$) | 2–10 | Yes | No | Optional | Tier 1 | No | ~1% |
| **Tier B** ($10C$–$100C$) | 10–100 | Yes + re-grounding | No | Yes | Tier 1-2 | Optional (Tier 3 models) | ~3-5% |
| **Tier C** ($100C$–$1KC$) | 100–1K | **No** — hierarchy required | Yes | Yes | Tier 1-2-3 | Yes (model-gated) | ~10% |
| **Tier D** ($>1KC$) | 1K+ | **No** | Multi-level | Yes | Tier 1-2-3 | Yes (model-gated) | ~15% |

### 15.2 Mode Selection Algorithm

```python
FUNCTION configure_session(task_intent, estimated_tokens, model_info):
  """Configure all CRP subsystems based on scale and model capability."""
  
  tier = classify_quality_tier(estimated_tokens, model_info.context_window)
  model_capability = assess_review_capability(model_info, warm_state=None)
  
  config = SessionConfig(
    quality_tier=tier,
    processing_mode=select_processing_mode(task_intent, estimated_tokens, model_info.context_window),
    cqs_enabled=(tier.ordinal >= TIER_A.ordinal),
    validation_tiers=min(model_capability, 3 if tier.ordinal >= TIER_C.ordinal else 
                                           2 if tier.ordinal >= TIER_B.ordinal else 1),
    review_cycles_enabled=(tier.ordinal >= TIER_B.ordinal and model_capability >= 3),
    planning_window=(tier.ordinal >= TIER_B.ordinal),
    hierarchical=(tier.ordinal >= TIER_C.ordinal),
    re_grounding=(tier.ordinal >= TIER_B.ordinal),
  )
  
  return config
```

---

## 16. INVISIBLE EXECUTION — LIGHTWEIGHT PROTOCOL GUARANTEES

CRP's resource impact on the user's machine must be **below the threshold of human perception**. The user should not be able to tell CRP is running by looking at Task Manager, observing system lag, hearing disk activity, or feeling fan spin-up. This section specifies the concrete techniques that make CRP invisible.

**Design inspiration**: SQLite (deployed on billions of devices invisibly), Redis (memory-efficient compact encodings), Cap'n Proto (zero-copy data access), modern antivirus engines (scan at idle priority, cache results, never block the user).

### 16.1 Process & Thread Discipline

CRP runs as a **background tenant** on the user's machine. It has no right to visible system resources.

```
EXECUTION RULES:

1. PROCESS PRIORITY:
   Set at Client creation per ResourceAllocation.process_priority (§3.7.1).
   Default: BELOW_NORMAL — CRP yields to ALL user processes.
   
   Windows: SetPriorityClass(GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
   Linux:   os.nice(10)
   macOS:   os.nice(10) + PRIO_DARWIN_BG for I/O
   
   Effect: During user activity, CRP gets leftover CPU only.
   During idle, CRP uses available CPU freely.

2. BOUNDED THREAD POOL:
   All CRP background work shares a SINGLE ThreadPoolExecutor.
   max_workers = ResourceAllocation.max_threads (default: 2)
   
   Thread allocation:
     Thread 1: Extraction pipeline (regex → statistical → model stages)
     Thread 2: Async persistence (SQLite flush, cold storage writes)
   
   If both threads are busy, new work QUEUES. CRP never spawns additional threads.
   This is a hard ceiling, not a suggestion.

3. COALESCED TIMERS:
   CRP has multiple periodic operations (community detection, curation checks,
   resource monitoring, event log snapshots, model idle checks).
   Instead of N separate timers (N wake-ups per interval), ALL periodic
   operations share a SINGLE timer loop:
   
   CoalescedTimer runs once per second (1 wake-up/sec, not ~50).
   Each tick checks: "Which periodic tasks are due?"
   Only due tasks execute; others skip.
   Single timer = single wake-up = minimal power impact.

4. IDLE-CALLBACK SCHEDULING:
   Heavy operations (community detection, embedding computation, cold storage GC)
   are deferred to genuine system idle periods — not executed inline.
   
   IdleScheduler tracks the last LLM response timestamp.
   If the LLM is generating (user is waiting): CRP does NOTHING except
     capture output. No extraction, no embedding, no persistence.
   After generation completes and user has NOT dispatched within 50ms:
     CRP processes accumulated work in bounded time slices (16ms max).
   If user dispatches during processing: CRP immediately yields,
     queues remaining work, handles the new dispatch.
   
   Net effect: CRP's CPU-intensive work happens in the gaps between
   user interactions, never competing with active work.
```

### 16.2 Memory Efficiency — Data Structure Guarantees

CRP's data structures are chosen for minimal memory footprint, not ease of implementation. Every structure used in the hot path has a **memory budget justification**.

```
STRUCTURE 1 — FACT STORAGE (Hot Path):

  Facts use __slots__ to eliminate Python's per-instance __dict__ overhead:
    Python dict per fact:  ~560 bytes overhead (hash table, key objects, pointers)
    __slots__ per fact:    ~152 bytes overhead (fixed attribute pointers only)
    Savings:               73% overhead reduction per fact
  
  For 10,000 facts:
    dict-based:   ~10.6 MB (mostly overhead, not data)
    __slots__:    ~6.3 MB  
    This is the MINIMUM implementation requirement. All Fact-like objects MUST use __slots__.

STRUCTURE 2 — EMBEDDING STORAGE (Biggest Memory Consumer):

  Full-precision embeddings: 384 dimensions × 4 bytes = 1,536 bytes per fact.
  For 100,000 facts: 150 MB of embeddings alone.
  
  CRP uses SCALAR QUANTIZATION (SQ8) for warm state embeddings:
    float32 → uint8 per dimension, with per-column min/max calibration.
    Storage: 384 bytes per fact (not 1,536).
    Memory: 37.5 MB for 100K facts (not 150 MB).
    Recall: ~95-98% similarity search accuracy — negligible quality loss.
    
    The quantization is transparent to all CRP subsystems. EnvelopeBuilder,
    WarmState, and CKF call embedding.similarity() — the dequantization
    happens inside the comparison, not on load.
  
  Full-precision embeddings are retained ONLY for:
    - The current window's freshly extracted facts (before quantization)
    - Active cross-encoder reranking candidates (if cross-encoder is enabled)
    - Tier 3 cold storage exports (quantized on write)

STRUCTURE 3 — CKF GRAPH (Fact Relationships):

  CRP's fact graph stores typed edges between facts. Naive Python implementations
  use dict-of-sets or adjacency lists — creating millions of Python objects.
  
  CRP specifies Compressed Sparse Row (CSR) format for the CKF graph:
    Components: indptr (row pointers), indices (column IDs), weights (edge scores)
    All stored as contiguous numpy arrays (int32 + float32).
    
    Memory comparison for 100K facts, 500K edges:
      Python dict-of-sets:  ~120 MB (hash tables, set objects, pointer chains)
      Adjacency list:       ~45 MB  (list objects, index objects)
      CSR numpy arrays:     ~4 MB   (contiguous buffers, zero per-node overhead)
    
    CSR is the REQUIRED implementation for CKF graph storage.
    Adjacency wrappers (subgraph_for, edges_from) operate on CSR underneath.
    Graph mutations (new edges) are batched and trigger CSR rebuild at window boundaries.

STRUCTURE 4 — BLOOM FILTER FOR DEDUP:

  Before computing an expensive embedding to check "does this fact already exist?",
  CRP uses a Bloom filter for fast probabilistic existence testing:
  
    Size: ~117 KB for 100K items at 1% false-positive rate
    Lookup: O(1), ~microseconds
    
    Workflow:
      1. New fact extracted → hash fact text → Bloom filter check
      2. If Bloom says "definitely not present" → skip dedup, add directly
      3. If Bloom says "maybe present" → compute embedding, check exact similarity
    
    Expected benefit: ~99% of new facts pass through Bloom without needing
    an embedding computation. Dedup cost drops from ~5ms/fact to ~0.05ms/fact
    for non-duplicate facts (the majority).
```

### 16.3 I/O Discipline — Write-Behind & Memory-Mapped Cold Access

```
PRINCIPLE: CRP writes to disk in BATCHES, never per-operation.
           CRP reads cold data via mmap, never loading full files.

WRITE-BEHIND BATCHING:
  All warm state mutations accumulate in memory.
  Writes to SQLite happen ONLY:
    - Every 5 windows (batch flush) — see §3.1 Tier 2
    - On session close (final flush)
    - On snapshot (explicit persistence)
  
  Single batch write = single fsync() call.
  This reduces disk writes from ~100/sec (per-fact) to ~1 every 5 seconds.
  
  The user will NOT see disk activity indicators flickering.

MEMORY-MAPPED COLD DATA (Tier 3):
  Cold storage facts are stored in a binary file, accessed via mmap.
  The OS manages which pages are resident in RAM:
    - Frequently accessed facts: automatically cached by OS page cache
    - Rarely accessed facts: paged out, consuming zero RAM
    - Under system memory pressure: OS reclaims CRP cold pages FIRST
      (because CRP runs at BELOW_NORMAL priority)
  
  CRP's Tier 3 resident memory scales with ACCESS PATTERN, not DATA SIZE.
  A 500MB cold store may use only 2-10MB of actual RAM if most facts are
  rarely accessed. The OS transparently manages paging.

SEQUENTIAL I/O:
  All cold storage writes are APPEND-ONLY (sequential, not random).
  Sequential writes are 10-100x faster than random writes on all media.
  The event log, fact archive, and snapshot files are all append-structured.
  
  Read patterns use mmap (OS optimizes read-ahead for sequential access).
```

### 16.4 Resource Profile Targets

These are the **concrete resource targets** for a CRP implementation managing a typical workload:

```
RESOURCE PROFILE (100K accumulated facts, active session):

  RAM (Working Set):
    In-memory hot facts (1000 × 500B):                   ~500 KB
    SQ8 embeddings for hot facts (1000 × 384B):           ~375 KB
    CKF graph CSR (100K nodes, 500K edges):               ~4 MB
    Bloom filter (100K items):                            ~117 KB
    ANN index (loaded, SQ8-backed):                       ~5 MB
    Loaded models (depending on allocation):              80-760 MB
    Event log (recent events since last snapshot):        ~200 KB
    Miscellaneous (buffers, caches, Python overhead):     ~2 MB
    ─────────────────────────────────────────────────────────────
    TOTAL (excluding models):                             ~12 MB
    TOTAL (with embedding model only):                    ~92 MB
    TOTAL (all models loaded):                            ~772 MB
    TOTAL (models unloaded, minimum CRP):                 ~12 MB
  
  CPU (During User Activity):
    Process priority: BELOW_NORMAL → <2% visible CPU
    Idle scheduling: heavy work deferred to gaps between user interactions
    Per-window overhead: ~50-200ms (extraction + envelope) — runs while 
      LLM generates the NEXT response (pipelined, not serial)
  
  Disk I/O:
    Write frequency: 1 batch write every ~5 seconds (or 5 windows)
    Write size: ~10-50 KB per batch (50 facts × 500B + events)
    Write pattern: sequential append (optimal for all storage media)
    Cold reads: mmap, paged by OS (no explicit I/O in CRP code)
  
  Threads:
    Background: 2 (extraction + persistence)
    Async event loop: 1 (coalesced timer, idle scheduler)
    Total: 3 threads under CRP control
    
  Wake-ups:
    Timer: 1/sec (coalesced timer loop)
    No polling, no busy-waiting, no hot loops

COMPARISON — NAIVE IMPLEMENTATION vs CRP-OPTIMIZED:

  | Resource | Naive | CRP-Optimized | Reduction |
  |----------|-------|---------------|-----------|
  | RAM (100K facts, no models) | ~280 MB | ~12 MB | 96% |
  | Embedding storage | 150 MB | 37.5 MB | 75% |
  | Graph storage | 120 MB | 4 MB | 97% |
  | Disk writes per second | ~100 | ~0.2 | 99.8% |
  | Threads | unbounded | 3 | bounded |
  | Per-fact dedup cost | ~5ms | ~0.05ms | 99% |
  | Timer wake-ups/sec | ~50 | 1 | 98% |

MINIMUM VIABLE FOOTPRINT:
  If ResourceAllocation sets max_ram_mb=64 and max_model_ram_mb=0:
    CRP operates in "regex + statistical extraction only" mode.
    No ML models loaded. Bi-encoder scoring skipped. Envelope uses recency only.
    Total RAM: ~12 MB. CPU: negligible. This is CRP's floor — it cannot go lower
    while still providing any value. Even at this floor, dispatch() works,
    facts are extracted (Stages 1-2), warm state accumulates, and envelopes
    carry context forward based on recency scoring.
```

---

## 17. SOURCE-GROUNDED ENVELOPES

### 17.1 The Problem: Facts About Facts

Standard CRP envelopes carry **extracted facts** — compressed, atomic representations of what earlier windows produced. While efficient, this creates a "telephone game" at scale: by Window 50, the LLM reasons from facts that are 49 levels of extraction removed from the original content. The LLM never reads the actual text — it reads the orchestrator's interpretation of the text.

This is the difference between:
- **"Notes about a book"**: The LLM sees `PORT 443: Apache 2.4.52, CVE-2024-1234 (CVSS 9.8, RCE via headers)` — a compressed fact.
- **"Reading the book"**: The LLM sees the ACTUAL PASSAGE that produced that fact, alongside the compressed fact for rapid scanning.

### 17.2 Source Passage Storage

When the extraction pipeline processes a window's output, it now stores **source passages** alongside extracted facts:

```python
@dataclass
class SourcePassage:
    """Original text passage that produced one or more extracted facts."""
    passage_id: str
    text: str                       # The actual original text (verbatim)
    source_window: int              # Which window produced this text
    token_offset_start: int         # Start position in the window's output
    token_offset_end: int           # End position
    linked_fact_ids: list[str]      # Which facts were extracted from this passage
    token_count: int                # Cached token count of the passage
    relevance_score: float = 0.0    # Set during envelope construction
```

**Storage policy**: Source passages are stored for facts above a **confidence threshold** ($\geq 0.8$). Low-confidence facts don't warrant source storage because they're likely noise. This bounds storage: at 0.8 threshold, typically 30-60% of facts have source passages.

**Warm state extension**:
```python
# In warm_state.py
class WarmState:
    # ... existing fields ...
    source_passages: dict[str, SourcePassage]  # passage_id → SourcePassage
    fact_to_passages: dict[str, list[str]]     # fact_id → [passage_ids]
```

### 17.3 Source-Grounded Envelope Construction

When building the envelope, the orchestrator includes source passages for the **highest-relevance facts**:

```python
FUNCTION build_source_grounded_envelope(scored_facts, warm_state, budget_tokens):
  """Extend standard envelope with source passages for top-relevance facts."""
  
  # Standard scoring already complete — scored_facts is sorted by relevance
  
  # Phase 1: Pack facts as normal (atomic, compressed)
  fact_section, remaining = pack_facts(scored_facts, budget_tokens * 0.7)
  
  # Phase 2: Allocate remaining budget to source passages
  source_budget = remaining  # Up to 30% of envelope for source passages
  source_section = []
  
  for score, fact in scored_facts:
    if source_budget <= 0:
      break
    
    # Only ground facts above high-relevance threshold
    if score < HIGH_RELEVANCE_THRESHOLD:
      break
    
    # Look up source passages for this fact
    passage_ids = warm_state.fact_to_passages.get(fact.id, [])
    for pid in passage_ids:
      passage = warm_state.source_passages[pid]
      if passage.token_count <= source_budget:
        source_section.append(passage)
        source_budget -= passage.token_count
  
  return fact_section, source_section
```

### 17.4 Envelope Format with Source Grounding

```
[DISCOVERIES]
- CVE-2024-1234 affects Apache 2.4.52, CVSS 9.8, RCE via HTTP/2 headers — Window 3
  ↳ [SOURCE: Window 3, tokens 1200-1450]
    "The comprehensive scan revealed CVE-2024-1234 in Apache httpd 2.4.52 
     running on port 443. This is a critical Remote Code Execution vulnerability 
     with CVSS base score 9.8 that allows unauthenticated attackers to execute 
     arbitrary code via specially crafted HTTP/2 headers. The vulnerability was 
     disclosed in January 2024 and has active exploits in the wild..."

- MySQL 8.0.35 bound to localhost, authentication required — Window 2
  (no source passage — below high-relevance threshold for current task)

- WooCommerce 8.4.0 SQLi in order search, CVSS 8.1 — Window 4
  ↳ [SOURCE: Window 4, tokens 800-1100]
    "WooCommerce version 8.4.0 contains a SQL injection vulnerability in the 
     order search functionality. An authenticated attacker with shop manager 
     privileges can inject arbitrary SQL via the search parameter..."
```

The LLM reads the **actual text from earlier windows** — not just compressed facts. It "flips back to page 3" to read what was actually written.

### 17.5 Budget Allocation Strategy

| Quality Tier | Fact Budget | Source Passage Budget | Rationale |
|-------------|------------|----------------------|-----------|
| **S** | N/A | N/A | Everything fits in one window — no envelope needed |
| **A** | 90% | 10% | Few facts accumulated; low extraction drift risk; sources only for critical verification |
| **B** | 70% | 30% | Most facts competing for space; highest drift risk; source grounding most valuable here |
| **C** | 70% | 30% | Hierarchical synthesis introduces abstraction layers; sources anchor to original data |
| **D** | 75% | 25% | Multi-level synthesis; selective source grounding for highest-confidence-gap facts |

**Budget rationale**: Source grounding investment should scale with **extraction drift risk**, not inversely. Tier A has few windows and low drift — 10% is sufficient. Tier B/C have the highest risk of "telephone game" degradation — 30% budget maximizes the grounding benefit where it matters most. Tier D operates through multi-level synthesis where space is precious, so 25% balances grounding against fact coverage.

### 17.6 Why This Solves the Telephone Game

Without source grounding, compound degradation operates on TWO levels:
1. **Extraction fidelity**: Each window's output loses information during extraction ($d_i$ per window)
2. **Interpretation drift**: Each window's LLM adds its own interpretation layer, drifting from original data

Source-grounded envelopes **break the interpretation drift chain**: the LLM reads original passages, not interpretations of interpretations. The effective degradation formula becomes:

$$d_{\text{grounded}}(n) = d_{\text{extraction}}(n) \times (1 - p_{\text{source}})$$

Where $p_{\text{source}}$ is the fraction of critical facts that have source passages available. At $p_{\text{source}} = 0.5$ (50% of top facts have source passages), the effective degradation is halved for grounded content.

---

## 18. LLM-DRIVEN CONTEXT CURATION & PROGRESSIVE UNDERSTANDING

### 18.1 The Passive Recipient Problem

In standard CRP, the LLM has **zero say** in what gets carried forward. The orchestrator extracts facts mechanically (regex → NER → UIE → discourse → graph), scores them by embedding similarity, and packs the envelope. The LLM is a tenant in someone else's house — it generates, but someone else decides what matters.

This underutilizes the LLM's primary capability: **judgment**. The LLM knows what's important for its current reasoning in ways that no embedding similarity score can capture. A fact about "corporate governance policies" might score LOW by similarity to a penetration test task, but the LLM might know it's CRITICAL because it implies a specific compliance framework that affects exploitation boundaries.

### 18.2 LLM Context Curation Protocol

After key windows (configurable, default: every 5 windows, or at tier transitions), the orchestrator dispatches a **curation window**:

```python
FUNCTION llm_context_curation(warm_state, task_intent, window_index, config):
  """Ask the LLM to curate what's most important to carry forward.
  Does NOT violate Axiom 4 — the LLM thinks it's doing a standard summarization task."""
  
  if window_index % config.curation_interval != 0:
    return None
  
  # Provide the LLM with the current top facts and recent output
  top_facts = warm_state.get_highest_confidence_facts(top_k=40)
  recent_output = warm_state.get_recent_output_summary(last_n_windows=3)
  
  synthesis = crp.dispatch(
    system_prompt=(
      "You are analyzing an ongoing investigation. Based on the findings so far, provide:\n"
      "1. THE 5 MOST CRITICAL FINDINGS — the ones everything else depends on\n"
      "2. THE 3 KEY RELATIONSHIPS — connections between findings that matter most\n"
      "3. YOUR CURRENT ASSESSMENT — a 2-3 sentence synthesis of the overall picture\n"
      "4. WHAT'S MISSING — what information gaps remain\n"
      "Be specific and cite finding numbers."
    ),
    task_input=f"[FINDINGS SO FAR]\n{serialize_facts(top_facts)}\n\n"
               f"[RECENT ANALYSIS]\n{recent_output}",
    expected_output_length="medium"
  )
  
  # Store as first-class synthesis in warm state
  warm_state.llm_synthesis = LLMSynthesis(
    text=synthesis,
    window_index=window_index,
    supersedes=warm_state.llm_synthesis.synthesis_id if warm_state.llm_synthesis else None
  )
  
  return synthesis
```

The LLM doesn't know it's curating for CRP — it thinks it's performing a standard analytical task. But the orchestrator uses its synthesis as a **first-class envelope section** that carries the LLM's own judgment about what matters.

### 18.3 Progressive Understanding

Each curation cycle doesn't start fresh — it BUILDS on the previous synthesis:

```python
FUNCTION progressive_curation(warm_state, task_intent, window_index, config):
  """Evolve the LLM's understanding progressively across windows."""
  
  # Include the PREVIOUS synthesis in the input
  prior_synthesis = warm_state.llm_synthesis.text if warm_state.llm_synthesis else "No prior synthesis."
  new_facts_since_last = warm_state.get_facts_since(warm_state.llm_synthesis.window_index 
                                                     if warm_state.llm_synthesis else 0)
  
  evolved = crp.dispatch(
    system_prompt=(
      "You previously assessed an investigation and produced a synthesis. "
      "New findings have come in since then. Update your assessment:\n"
      "1. Revise your critical findings list (add, remove, or reprioritize)\n"
      "2. Update key relationships based on new evidence\n"
      "3. Provide your UPDATED assessment (how has the picture changed?)\n"
      "4. What new gaps have emerged?"
    ),
    task_input=f"[YOUR PREVIOUS SYNTHESIS]\n{prior_synthesis}\n\n"
               f"[NEW FINDINGS SINCE LAST SYNTHESIS]\n{serialize_facts(new_facts_since_last)}\n\n"
               f"[OVERALL TASK]\n{task_intent.task_input[:500]}",
    expected_output_length="medium"
  )
  
  # Replace previous synthesis with evolved version
  warm_state.llm_synthesis = LLMSynthesis(
    text=evolved,
    window_index=window_index,
    supersedes=warm_state.llm_synthesis.synthesis_id if warm_state.llm_synthesis else None,
    evolution_count=(warm_state.llm_synthesis.evolution_count + 1) if warm_state.llm_synthesis else 1
  )
  
  return evolved
```

**This is learning**: Not weight updates, but **accumulated understanding** that evolves. By Window 50, the LLM's synthesis reflects 50 windows of progressively refined comprehension — not just the orchestrator's last extraction pass.

### 18.4 Data Model

```python
@dataclass
class LLMSynthesis:
    """The LLM's own curated understanding, evolved progressively."""
    synthesis_id: str               # UUID
    text: str                       # The synthesis text
    window_index: int               # When this synthesis was produced
    supersedes: str | None          # ID of the prior synthesis this evolved from
    evolution_count: int = 1        # How many times the synthesis has evolved
    critical_findings: list[str] = None    # Parsed from synthesis (if structured)
    key_relationships: list[str] = None    # Parsed from synthesis
    confidence: float = 1.0         # Starts at 1.0, adjusted by validation
```

### 18.5 Envelope Integration

The LLM synthesis becomes a first-class envelope section, injected between CRITICAL STATE and DISCOVERIES:

```
SECTION 1:   CRITICAL STATE        (always present)
SECTION 1.5: LLM SYNTHESIS         (present when curation has run)
SECTION 2:   TASK BRIEF            (always present)
SECTION 3:   DISCOVERIES           (with source passages for high-relevance facts)
...remaining sections...
```

The synthesis section is formatted as:

```
[LLM_SYNTHESIS (Window 25, evolution 5)]
CRITICAL FINDINGS:
1. {finding} — {evidence}
2. {finding} — {evidence}
...
KEY RELATIONSHIPS:
- {relationship 1}
- {relationship 2}
CURRENT ASSESSMENT:
{2-3 sentence synthesis}
GAPS:
- {gap 1}
- {gap 2}
```

### 18.6 Token Overhead

| Tier | Curation Every N Windows | Synthesis Size | Overhead Per Window |
|------|-------------------------|---------------|-------------------|
| **A** | 5 | ~500 tokens | ~2% (dispatch + extract) |
| **B** | 5 | ~800 tokens | ~3% |
| **C** | 10 | ~1000 tokens | ~2% (amortized over hierarchy) |
| **D** | 20 | ~1500 tokens | ~1% (amortized) |

Progressive curation overhead is low because synthesis windows are SHORT (hundreds of tokens of output) and INFREQUENT (every 5-20 windows). The benefit — carrying the LLM's own judgment — far exceeds the cost.

---

## 19. CRP META-LEARNING ARCHITECTURE — TEACHING LLMS TO REASON

### 19.1 The Foundational Insight

A 2B-parameter model cannot perform multi-step chain-of-thought reasoning in a single window. Ask it to "analyze this vulnerability, consider the network topology, evaluate exploit difficulty, and recommend remediation" and it will produce a shallow answer that ignores interdependencies.

But that same 2B model CAN:
- Identify open ports from a scan (simple extraction)
- Determine if a CVE applies to a specific version (binary comparison)
- Rate a single vulnerability's severity given explicit criteria (structured classification)
- Write a remediation for a specific, well-described vulnerability (focused generation)

**CRP can orchestrate these micro-capabilities into a reasoning chain that exceeds the model's native ability.** This is not hypothetical — it's grounded in three research findings:

1. **In-Context Learning as Implicit Gradient Descent** (Dai et al., ACL 2023): Transformer attention has a dual form of gradient descent. LLMs produce "meta-gradients" from demonstration examples. CRP leverages this by structuring envelopes as implicit learning signals.

2. **STaR: Self-Taught Reasoner** (Zelikman et al., NeurIPS 2022): Models can bootstrap reasoning ability by iteratively learning from their own correct reasoning traces. CRP implements this at the session level — successful reasoning patterns are stored in CKF and retrieved for similar future tasks.

3. **Distilling Step-by-Step** (Hsieh et al., ACL 2023): A 770M model outperforms 540B PaLM when given step-by-step rationales as additional supervision. CRP provides these rationales through reasoning scaffolds in the envelope.

### 19.2 The Three Meta-Learning Mechanisms

#### Mechanism 1: Orchestrated Reasoning Chains (ORC)

CRP decomposes complex reasoning into steps within the model's capability, executing each step as a separate window:

```python
FUNCTION orchestrated_reasoning(task_intent, warm_state, model_capability):
  """Decompose complex reasoning into micro-steps for weak models."""
  
  # Step 1: Task decomposition (orchestrator, not LLM — works for ANY model)
  reasoning_steps = decompose_reasoning_task(task_intent)
  # Example for vulnerability analysis:
  #   Step 1: "List all identified services and their versions"
  #   Step 2: "For each service, identify known CVEs"
  #   Step 3: "For each CVE, assess exploitability given the network context"
  #   Step 4: "Rank vulnerabilities by combined risk"
  #   Step 5: "Recommend remediation for top-3 risks"
  
  accumulated_results = []
  
  for step in reasoning_steps:
    # Build a focused, simple prompt for this micro-step
    step_envelope = build_step_envelope(
      step=step,
      prior_results=accumulated_results,
      warm_state=warm_state,
      model_capability=model_capability
    )
    
    result = crp.dispatch(
      system_prompt=step.system_prompt,  # Tailored to step complexity
      task_input=step_envelope
    )
    
    # Extract structured output from this step
    step_facts = extract_step_results(result, step)
    accumulated_results.append(StepResult(step=step, output=result, facts=step_facts))
    
    # Validate: did the model actually accomplish this step?
    if not validate_step_output(result, step):
      # Model failed this step — simplify and retry with more scaffolding
      result = retry_with_scaffold(step, warm_state, model_capability)
  
  # Final synthesis: combine all step results
  return synthesize_reasoning_chain(accumulated_results, task_intent)
```

**Key insight**: Each window is within the model's capability ceiling. The CHAIN of windows produces reasoning that exceeds the model's native ability. A 2B model that can't analyze a vulnerability landscape in one shot CAN analyze it step by step, with CRP orchestrating the chain.

**ORC Cost-Benefit Gate**: ORC multiplies window count by 3-10× per task. This must only trigger when the single-window approach demonstrably fails:

```python
FUNCTION should_use_orc(task_intent, warm_state, model_capability, resource_pressure):
  """Gate ORC activation on cost-benefit analysis. Don't scaffold when unnecessary."""
  
  # Gate 1: Resource pressure override
  if resource_pressure >= HIGH:
    return False  # Cannot afford the window multiplication
  if resource_pressure >= MODERATE and model_capability >= 2:
    return False  # Moderate models can manage without ORC under pressure
  
  # Gate 2: Model capability vs. task complexity
  task_complexity = estimate_task_complexity(task_intent)  # 1-5 scale
  #   1: Simple extraction (list services)
  #   2: Single comparison (check CVE applicability)
  #   3: Multi-factor analysis (assess risk considering multiple variables)
  #   4: Chain reasoning (analyze → correlate → synthesize → recommend)
  #   5: Novel synthesis (creative problem-solving, adversarial thinking)
  
  if model_capability >= task_complexity:
    return False  # Model can handle this natively — no scaffolding needed
  
  # Gate 3: Try single-window first (probe)
  # Dispatch ONE window with the full task. If quality score >= 0.7, accept it.
  if not config.orc_skip_probe:
    probe_result = crp.dispatch(task_intent.system_prompt, task_intent.task_input)
    probe_quality = evaluate_generation_quality(probe_result)
    if probe_quality.overall_score >= 0.7:
      return False  # Single window succeeded — ORC unnecessary
    # Probe failed — ORC justified. Probe output still useful as warm state.
    warm_state.ingest(probe_result)
  
  return True

ORC_GATE_RULES:
  Default:     Probe first, ORC second (never assume failure)
  Skip probe:  When model_capability=1 AND task_complexity>=4 (known gap)
  Max steps:   Capped by resource pressure (NONE: 10, MODERATE: 5, HIGH: 3)
  Telemetry:   Log ORC gates (probe success/failure, steps taken)
```

#### Mechanism 2: In-Context Meta-Learning (ICML)

CRP structures the envelope to TEACH the model how to reason about the current task, leveraging the finding that in-context learning performs implicit gradient descent:

```python
FUNCTION build_metacognitive_envelope(task_intent, warm_state, ckf, model_capability):
  """Build an envelope that teaches the model HOW to reason, not just WHAT to reason about."""
  
  envelope_sections = []
  
  # 1. Standard CRP envelope sections (critical state, facts, etc.)
  envelope_sections.extend(build_standard_envelope(task_intent, warm_state))
  
  # 2. Reasoning scaffold — adapted to model capability
  if model_capability <= 2:  # Small model needs more scaffolding
    scaffold = build_reasoning_scaffold(task_intent, model_capability)
    envelope_sections.append(scaffold)
  
  # 3. Few-shot reasoning examples from CKF
  #    "Show me how someone solved a similar problem"
  similar_solved = ckf.retrieve_reasoning_traces(
    task_type=classify_task_type(task_intent),
    top_k=3,
    max_tokens=2000
  )
  if similar_solved:
    envelope_sections.append(format_reasoning_examples(similar_solved))
  
  return assemble_envelope(envelope_sections)


FUNCTION build_reasoning_scaffold(task_intent, model_capability):
  """Generate a step-by-step reasoning template for weak models."""
  
  # The scaffold tells the model HOW to think, not what to think
  if model_capability <= 1:  # 0.5B-1B models
    return (
      "[REASONING APPROACH]\n"
      "Follow these steps exactly:\n"
      f"Step 1: {generate_step_1(task_intent)}\n"
      f"Step 2: {generate_step_2(task_intent)}\n"
      f"Step 3: {generate_step_3(task_intent)}\n"
      "Output your answer after completing all steps."
    )
  elif model_capability <= 2:  # 2B-7B models
    return (
      "[APPROACH]\n"
      f"Consider: {generate_considerations(task_intent)}\n"
      f"Then conclude with your assessment."
    )
  else:
    return ""  # Strong models don't need scaffolding
```

#### Mechanism 3: Reasoning Template Library (RTL)

CRP accumulates successful reasoning patterns in the CKF across sessions:

```python
@dataclass
class ReasoningTrace:
    """A successful reasoning chain stored for future retrieval."""
    trace_id: str
    task_type: str                  # Classified task category
    task_summary: str               # What was being reasoned about
    steps: list[ReasoningStep]      # The micro-steps that worked
    model_class: str                # What model class succeeded (e.g., "2B", "7B", "70B+")
    quality_score: float            # How well the reasoning performed
    created_at: float
    usage_count: int = 0            # How often this trace has been reused

@dataclass
class ReasoningStep:
    """One step in a successful reasoning chain."""
    step_description: str           # What this step does
    system_prompt_template: str     # Template for this step's system prompt
    expected_output_format: str     # What good output looks like
    scaffold_level: int             # How much scaffolding this step needed (0-3)
```

The CKF stores reasoning traces alongside facts. When a new task matches a previously-solved pattern, the orchestrator retrieves the trace and uses it to scaffold the current reasoning:

```python
FUNCTION retrieve_reasoning_scaffold(task_intent, ckf, model_capability):
  """Pull matching reasoning traces from CKF for the current task."""
  
  # Find traces that match this task type AND this model capability
  matching_traces = ckf.query_reasoning_traces(
    task_embedding=embed(task_intent.task_input),
    model_class=classify_model(model_capability),
    min_quality=0.7,
    top_k=3
  )
  
  if matching_traces:
    best_trace = matching_traces[0]
    best_trace.usage_count += 1
    
    # Adapt the trace to the current task
    adapted_steps = [
      adapt_step(step, task_intent) for step in best_trace.steps
    ]
    return adapted_steps
  
  # No matching trace — use default decomposition
  return default_decomposition(task_intent, model_capability)
```

### 19.3 Why This Is Meta-Learning, Not Just Prompting

Traditional prompting: "Here's a task. Do it."

CRP Meta-Learning:
1. **The model learns from examples** — few-shot reasoning traces from CKF teach it HOW to reason about this type of problem (in-context meta-learning via implicit gradient descent)
2. **The system learns from the model** — successful reasoning chains are stored and reused; the RTL grows with each session (bootstrapping à la STaR)
3. **Scaffolding adapts to capability** — strong models get minimal scaffolding, weak models get step-by-step templates (progressive complexity à la Distilling Step-by-Step)
4. **Cross-session reasoning transfer** — a reasoning pattern that worked for vulnerability analysis on Host A is retrieved for vulnerability analysis on Host B

This creates a **virtuous cycle**: CRP teaches the model to reason → the model's reasoning succeeds → CRP stores the successful pattern → CRP uses the pattern to teach future models. Over time, even a 2B model with a large enough RTL can tackle problems that normally require 70B+ models, because it's reasoning from accumulated patterns rather than raw capability.

### 19.4 Capability Ceiling and Honest Limits

CRP Meta-Learning does NOT claim to make a 2B model equivalent to a 70B model. The limits are real:

| Capability | 2B + CRP Meta-Learning | 7B + CRP Meta-Learning | 70B+ Native |
|---|---|---|---|
| **Simple extraction** | ✅ Native ability | ✅ Native | ✅ Native |
| **Binary decisions** | ✅ With scaffolding | ✅ Minimal scaffolding | ✅ Native |
| **Multi-step reasoning** | ⚡ Via ORC (3-5 steps) | ⚡ Via ORC (5-10 steps) | ✅ Native |
| **Complex chain-of-thought** | ⚠️ Via ORC (limited depth, 10 steps max) | ✅ Via ORC | ✅ Native |
| **Novel reasoning** | ❌ No matching traces, limited capability | ⚡ Can attempt with heavier scaffolding | ✅ Native |
| **Creative synthesis** | ❌ Fundamentally limited | ⚡ With examples | ✅ Native |

The floor is raised, the ceiling is extended, but the fundamental capability gap remains. CRP is honest about this — the Quality Report includes a `meta_learning_scaffolding_level` field so users know how much scaffolding was required.

### 19.5 Configuration

```python
@dataclass
class MetaLearningConfig:
    """Configuration for CRP Meta-Learning. Auto-calibrates to model."""
    enabled: bool = True                    # Master switch
    orc_enabled: bool = True                # Orchestrated Reasoning Chains
    orc_max_steps: int = 10                 # Max micro-steps per reasoning chain
    orc_min_model_capability: int = 1       # ORC works for ANY model
    icml_enabled: bool = True               # In-Context Meta-Learning (few-shot examples)
    icml_max_examples: int = 3              # Max reasoning traces in envelope
    rtl_enabled: bool = True                # Reasoning Template Library
    rtl_min_quality_for_storage: float = 0.7  # Min quality to store a trace
    scaffold_level: str = "auto"            # "auto" | "none" | "light" | "heavy"
    curation_interval: int = 5              # LLM context curation every N windows
```

---

## 20. LEARNING ON CONTEXT — ROADMAP

### 20.1 The Vision

Current LLMs "forget" when the context window closes. Every window is a fresh start — the model re-reads its context, re-establishes its understanding, and generates from scratch. CRP's warm state preserves FACTS across windows, but not the model's internal UNDERSTANDING.

The learning-on-context roadmap describes three tiers of progressively deeper context learning:

### 20.2 Tier 1 — Implemented in CRP v2.0

These mechanisms are available NOW, within the current CRP architecture:

| Mechanism | How It Works | Research Basis |
|---|---|---|
| **LLM-Driven Context Curation** (§18) | LLM decides what's most important to carry forward | Judgment > embedding similarity for complex reasoning |
| **Progressive Understanding** (§18.3) | LLM's synthesis evolves across windows, building accumulated comprehension | In-context learning as implicit gradient descent (Dai et al., 2023) |
| **Source-Grounded Envelopes** (§17) | Original text passages included for high-relevance content | Eliminates interpretation drift ("telephone game") |
| **Reasoning Template Library** (§19.3) | Successful reasoning patterns stored in CKF, retrieved for similar tasks | STaR (Zelikman et al., 2022) — bootstrapping reasoning |
| **Orchestrated Reasoning Chains** (§19.2) | Complex reasoning decomposed into micro-steps | Distilling Step-by-Step (Hsieh et al., 2023) |

### 20.3 Tier 2 — Infrastructure-Dependent (Medium-Term)

These mechanisms require specific inference infrastructure but NO model modifications:

| Mechanism | How It Works | Requirements | Research Basis |
|---|---|---|---|
| **KV Cache Persistence** | Save the model's KV cache from critical windows; inject cached entries into subsequent windows so the model retains its internal representations | vLLM prefix sharing, SGLang RadixAttention, or equivalent KV cache management | Prefix caching in production inference engines |
| **KV Cache Compression** | Compress cached KV entries via INT4/INT8 quantization to reduce storage from ~16GB to ~2GB per snapshot | KV quantization support in inference engine | KV cache quantization research (2024) |
| **RAPTOR-Style Hierarchical Retrieval** | Recursively cluster and summarize facts into a tree; retrieve from the appropriate abstraction level for the current task | Tree-structured index over warm state + CKF | RAPTOR (Sarthi et al., ICLR 2024) — 20% absolute improvement on QuALITY benchmark |

**KV Cache Persistence in detail**: When the LLM processes Window 5, its KV cache encodes its "understanding" of the content — attention patterns, intermediate representations, resolved ambiguities. If we save this cached state and prepend it to Window 10's context, the model starts Window 10 with its Window 5 understanding already established. This is not text-to-text relay — it's representation-to-representation, preserving the model's internal state.

```python
# Conceptual interface — infrastructure-dependent implementation
@dataclass
class KVCacheSnapshot:
    """Snapshot of a model's KV cache from a specific window."""
    snapshot_id: str
    source_window: int
    kv_data: bytes                  # Serialized KV cache (compressed)
    compression_ratio: float        # Original size / compressed size
    model_id: str                   # Which model produced this cache
    context_tokens: int             # How many tokens of context this represents
    created_at: float

FUNCTION persist_kv_cache(inference_engine, window_id, warm_state):
  """Save the current KV cache for future injection. Infrastructure-dependent."""
  if inference_engine.supports_kv_export():
    kv_data = inference_engine.export_kv_cache(compress=True)
    snapshot = KVCacheSnapshot(
      snapshot_id=uuid4(),
      source_window=window_id,
      kv_data=kv_data,
      compression_ratio=inference_engine.kv_compression_ratio(),
      model_id=inference_engine.model_id,
      context_tokens=inference_engine.current_context_length()
    )
    warm_state.kv_snapshots[window_id] = snapshot
```

### 20.4 Tier 3 — Requires Model Modifications (Long-Term)

These mechanisms require training or fine-tuning. CRP can integrate them when available but does NOT depend on them:

| Mechanism | How It Works | Requirements | Research Basis |
|---|---|---|---|
| **Gist Tokens** | Train the model to compress its context into virtual "gist" tokens — 26× compression with minimal quality loss | Model fine-tuning (modifies attention masks) | Mu et al., NeurIPS 2023 — up to 26× compression, <5% quality loss |
| **Activation Beacons** | Condense long-range activations into beacon tokens that serve as compressed memory | Per-model adaptation | Zhang et al., 2024 — activation-level compression |
| **Reasoning Fine-Tuning** | Fine-tune the model on CRP-generated reasoning traces to internalize scaffolding | Training data from RTL + compute | STaR + CRP traces as training data |

**CRP's position**: Tiers 1-2 are fully model-agnostic (Axiom 6). Tier 3 offers superior performance where model modification is acceptable. CRP provides the FRAMEWORK that benefits from these advances without depending on them.

### 20.5 The Learning Progression

```
SESSION 1 (Cold Start)
  Model capability probed → Reasoning scaffolding calibrated
  LLM synthesis: None → First synthesis at Window 5
  RTL: Empty
  Source grounding: Active from Window 1

SESSION 1, WINDOW 20
  LLM synthesis: Evolved 4 times → rich accumulated understanding
  RTL: 3 successful reasoning traces stored from this session
  Source passages: 50+ stored, top-10 included in each envelope
  KV cache: Snapshots from key windows (if Tier 2 available)

SESSION 5 (Returning to similar task)
  RTL: 15 traces from 4 prior sessions → 3 best retrieved for scaffolding
  CKF: Cross-session knowledge enriches envelope from Window 1
  LLM synthesis: Starts from CKF-retrieved prior synthesis, not cold
  The model "knows how" to reason about this task type — learned across sessions
```

---

## 21. THE 9 PERMANENT VALUE PROPOSITIONS

### 21.1 Why CRP Is Irreplaceable at ANY Scale

CRP's value does not diminish as native context windows grow. Even a model with infinite native context needs CRP for 8 of these 9 propositions. Context extension (Proposition 5) is the LEAST important one.

### 21.2 The 9 Propositions

| # | Value Proposition | What CRP Provides | Why Native Context Cannot |
|---|---|---|---|
| **1** | **Context Quality** | Semantically scored, graph-structured, priority-packed envelope with source grounding | Native context is unstructured raw text — no ranking, no graph, no priority, no source highlighting |
| **2** | **Task Isolation** | One window, one master. No cross-task contamination. Fresh KV cache per task | A 10M native window processing 5 tasks = attention soup. Cross-task interference degrades ALL tasks |
| **3** | **Attention Optimization** | Critical facts in the attention sink (start of window). Source passages for highest-relevance items | At 500K tokens, middle content receives ~0.1× the attention of start/end (Liu et al., 2023). No native mechanism targets attention |
| **4** | **Cost Efficiency** | $O(N)$ total tokens. Each window processes only relevant facts, not growing history | $O(N^2)$ cumulative tokens: 100 turns × 128K = 12.8M tokens resent. CRP: ~1.3M total |
| **5** | **Cross-Session Knowledge** | CKF persists facts, graph, communities, reasoning traces across sessions | Native context dies when the session ends. Every new session is a cold start |
| **6** | **Structured Knowledge** | Typed fact graph with edges, communities, temporal history, reasoning traces | Raw text has no exploitable structure. The model must re-parse structure from text every time |
| **7** | **Multi-Agent Coordination** | Envelope = state protocol between agents. Each agent gets relevant context, not everything | Native context windows are private to each agent. No structured state transfer protocol exists |
| **8** | **Observability & Audit** | Full provenance: fact → source window → extraction stage → confidence → lifecycle events → envelope inclusion | Native context is a black box. No way to know what the model "noticed" or "ignored" |
| **9** | **Reasoning Amplification** | Meta-learning scaffolds, orchestrated reasoning chains, progressive understanding | Native context provides zero reasoning scaffolding. A weak model stays weak regardless of context size |

### 21.3 The Scientific Backing

The ICLR 2024 paper "Retrieval Augmentation for Long Context" (Xu et al., arXiv:2310.03025) demonstrates:

> "Retrieval can significantly improve the performance of LLMs **regardless of their extended context window sizes**."

Specifically: retrieval-augmented Llama2-70B with 32K context outperforms GPT-3.5-turbo-16K and Davinci-003. The paper shows that retrieval augmentation (CRP's approach) **complements** native long context — it doesn't become redundant.

CRP is this principle formalized into a complete protocol: not just retrieval, but scored retrieval + structured knowledge + source grounding + progressive understanding + reasoning amplification + cross-session learning.

### 21.4 Scale-Indexed Value

| Scale | CRP Primary Value | What Matters Most |
|-------|------------------|-------------------|
| **1K tokens** (fits in 1 window) | Cross-session enrichment, reasoning scaffolds | CKF injects knowledge the model wouldn't otherwise have |
| **100K tokens** (fits in 1 window) | Attention optimization, task isolation | Even within the window, CRP's scoring puts critical facts first |
| **1M tokens** (multiple windows) | All 9 propositions | CRP manages the window chain with quality, structure, and efficiency |
| **100M tokens** (hierarchical) | Hierarchy + validation + review + source grounding | Only hierarchical processing can maintain coherent understanding |
| **1B+ tokens** | Full CRP stack | No native context can match structured, validated, hierarchically-processed knowledge |

---

## 22. CRP SECURITY ARCHITECTURE

CRP is a **local protocol** — it runs in-process or as a local service alongside the application. It is NOT a network-facing service. This fundamentally shapes the threat model: attack surfaces are **poisoned input**, **corrupted state**, **cross-window contamination**, and **unauthorized protocol access** — not network interception.

**Design Inspiration**:

| Protocol | Security Principle Borrowed | CRP Application |
|----------|-----------------------------|-----------------|
| **TLS 1.3** | Session handshake, ephemeral keys, forward secrecy | Protocol binding handshake at `crp.init()` |
| **DNSSEC** | Hierarchical chain of trust — each zone signs delegation to next | Fact provenance chain — each window signs facts for the next |
| **MCP (lessons from failures)** | Tool poisoning, rug pulls, cross-server shadowing | Anti-poisoning quarantine, envelope sanitization, window isolation |
| **HTTPS Certificate Pinning** | Bind to a specific identity, reject imposters | Application binding via shared secret — reject unsigned calls |

### 22.1 Threat Model

CRP recognizes four trust zones:

| Zone | Description | Trust Level |
|------|-------------|-------------|
| **Application** | The caller that invokes CRP (AI assistant, chat app, agent) | TRUSTED — the registered consumer |
| **LLM** | The language model behind the LLM interface (§6.1) | SEMI-TRUSTED — follows instructions but can hallucinate or be manipulated |
| **External Data** | Content ingested via `crp.ingest()` or task_input from users | UNTRUSTED |
| **Stored State** | Warm state (Tier 2) and cold state (Tier 3) on disk | PROTECTED — integrity-critical |

**Attack Vector Matrix** (OWASP-aligned):

| Vector | OWASP Reference | CRP Risk | Defense Section |
|--------|----------------|----------|-----------------|
| Prompt injection via task_input | LLM01 | Attacker crafts input to manipulate LLM behavior through the envelope | §22.5 |
| Fact poisoning via ingest() | LLM04, ML02 | Malicious data enters knowledge graph, corrupts downstream windows | §22.4 |
| Cross-window contamination | LLM08 | Facts or injection fragments from one window leak into unrelated windows | §22.5 |
| Unauthorized protocol access | — | Non-registered application invokes CRP operations or reads state | §22.2 |
| State tampering | — | On-disk warm/cold state modified by external process | §22.7 |
| Embedding inversion | LLM08, ML03 | Attacker recovers source text from stored embedding vectors | §22.7 |
| Unbounded consumption (DoS) | LLM10 | Attacker triggers rapid dispatch or massive ingest to exhaust resources | §22.6 |
| Supply chain (model poisoning) | LLM03, ML06 | Compromised GGUF model loaded into ModelRegistry | §22.4 |

### 22.2 Trust Architecture — Protocol Binding

**Principle**: The application and the CRP protocol instance form a **bound pair**. External actors cannot invoke CRP operations even if they can observe the process.

**Inspired by**: TLS 1.3 handshake (mutual authentication + ephemeral session keys) and DNSSEC delegation (each zone cryptographically vouches for the next).

#### 22.2.1 Session Binding Handshake

When `crp.init()` is called, a binding handshake establishes trust:

```
APPLICATION                              CRP INSTANCE
    │                                         │
    │── init(app_id, binding_secret) ────────▶│
    │                                         │── generate session_nonce (32 bytes random)
    │                                         │── session_key = HMAC-SHA256(binding_secret, session_nonce)
    │◀── SessionHandle ──────────────────────│
    │    { session_id, session_key,           │
    │      capabilities, nonce }              │
    │                                         │
    │── dispatch(task, sig) ─────────────────▶│
    │   sig = HMAC-SHA256(session_key,        │── verify sig against session_key
    │         hash(request))                  │── reject if invalid
    │◀── QualityReport + output ─────────────│
```

**Protocol Binding Rules**:

1. **BINDING_SECRET**: A shared secret configured at deployment (environment variable `CRP_BINDING_SECRET` or key file). NEVER stored in warm/cold state. NEVER logged.
2. **SESSION_KEY**: Derived per session via `HMAC-SHA256(binding_secret, session_nonce)`. The nonce is random per session — ephemeral. Discarded on session end.
3. **REQUEST_SIGNING**: Every `dispatch()`, `ingest()`, and `session_status()` call includes `HMAC-SHA256(session_key, request_content_hash)`. Invalid signatures → immediate rejection with no partial processing.
4. **NO UNSIGNED PATH**: There is no API endpoint that accepts unsigned requests. Even `cost_estimate()` requires a valid session.
5. **FORWARD SECRECY**: Each session generates a new nonce and therefore a new session_key. Compromising one session's key does not compromise past or future sessions.
6. **SESSION EXPIRY**: Sessions expire after `session_timeout_seconds` (default: 24 hours). Expired sessions require re-initialization.

#### 22.2.2 Zero-Configuration Fallback

Per Axiom 10 (Zero-Configuration), CRP **MUST** work without explicit security setup.

When no `binding_secret` is provided:
- CRP generates a random 256-bit secret at first init
- Stores it in the OS process keyring (Windows DPAPI, macOS Keychain, Linux kernel keyring)
- Subsequent `init()` calls from the **same process** are automatically authenticated
- Cross-process access requires explicit secret sharing

This provides **process-level isolation by default** — no attacker from another process can invoke CRP without the binding secret.

```python
@dataclass(slots=True)
class SessionBinding:
    session_id: str           # UUID v4
    session_key: bytes        # HMAC-SHA256 derived, 32 bytes (NEVER serialized)
    app_id: str               # registered application identifier
    created_at: float         # monotonic timestamp
    expires_at: float         # created_at + session_timeout_seconds
    capabilities: frozenset   # granted RBAC permissions (§22.6)
    max_dispatch_rate: int    # requests per minute (DoS protection)
```

#### 22.2.3 Why Symmetric-Only (No PKI)

CRP deliberately uses **symmetric cryptography only** (HMAC, AES-GCM, BLAKE3). No RSA, no ECDSA, no certificates, no PKI.

**Rationale**:
1. CRP is local — there is no network intermediary to impersonate. The TLS problem of "who am I talking to across the Internet?" doesn't exist.
2. Symmetric-only is **quantum-resistant by default** — Shor's algorithm attacks asymmetric crypto, not symmetric.
3. Symmetric operations are ~1000× faster than asymmetric — zero latency impact.
4. No certificate management, no expiry headaches, no CA trust chains to maintain.

If future CRP versions add multi-device session sharing (where the application and CRP run on different machines), they **MUST** use NIST PQC standardized algorithms (ML-KEM for key encapsulation, ML-DSA for signatures).

### 22.3 Input Boundary — Validation & Sanitization

**Principle**: CRP validates input **structure and bounds** natively. Content-level filtering is the **caller's responsibility** — user ethics are their own duty. CRP provides advisory detection but does not censor.

**Inspired by**: OWASP LLM01 mitigations (constrain model behavior, validate output formats, implement input/output filtering).

#### 22.3.1 Structural Validation (ALWAYS — Zero Config — Cannot Be Disabled)

Every input to `dispatch()` and `ingest()` passes structural validation before reaching the extraction pipeline:

```python
@dataclass(slots=True)
class InputValidation:
    """Applied to every dispatch() and ingest() call. Non-negotiable."""
    
    # SIZE LIMITS (hard reject on failure)
    max_task_input_bytes: int = 50_000_000       # 50 MB absolute ceiling
    max_task_description_chars: int = 10_000      # TaskIntent.description limit
    max_metadata_keys: int = 50                   # prevent metadata-bombing
    
    # TYPE SAFETY
    allowed_input_types: frozenset = frozenset({
        'text/plain', 'text/markdown', 'text/html',
        'application/json', 'application/pdf'
    })
    
    # ENCODING SAFETY (prevent encoding-based injection)
    normalize_unicode: bool = True                # NFC normalization
    strip_null_bytes: bool = True                 # remove \x00
    strip_control_chars: bool = True              # remove non-printable (except \n\t\r)
    max_codepoint: int = 0x10FFFF                # reject chars beyond Unicode range
```

**Why this is native and lightweight**:
- Zero model invocations — pure structural checks, regex, byte counting
- Sub-millisecond execution (< 0.5ms for 50 MB input)
- Prevents: oversized payloads, encoding attacks, metadata bombing, null-byte injection, type confusion

**Structural Validation is the ONE security control that CANNOT be disabled.** No configuration, no ADMIN override. This is the protocol's immune system.

#### 22.3.2 Prompt Injection Detection (Advisory — Zero False-Positive Policy)

CRP detects **known** prompt injection patterns in task_input and tags them for caller awareness:

```python
INJECTION_MARKERS = [
    # Direct instruction override
    (r'(?i)<\s*(?:IMPORTANT|SYSTEM|INSTRUCTION)\s*>', 'tag_injection'),
    (r'(?i)ignore\s+(?:previous|all|above)\s+(?:instructions?|prompts?|guidelines?)', 'override_attempt'),
    (r'(?i)you\s+are\s+now\s+', 'role_reassignment'),
    (r'(?i)new\s+instructions?\s*:', 'instruction_injection'),
    (r'(?i)disregard\s+(?:everything|all)', 'override_attempt'),
    
    # Obfuscation techniques
    (r'(?i)base64\s*[:=]\s*[A-Za-z0-9+/=]{20,}', 'encoded_payload'),
    (r'[\x00-\x08\x0e-\x1f]', 'control_char_injection'),
    
    # MCP-inspired: hidden instructions in structured data
    (r'(?i)(?:tool|function|action)\s*:\s*(?:read|write|send|execute)', 'tool_invocation_attempt'),
]
```

**Advisory, NOT blocking**: CRP marks hits in `QualityReport.security_flags` but does **NOT** reject the input. The caller decides policy.

```python
@dataclass(slots=True)
class SecurityFlags:
    injection_markers_detected: int = 0          # total pattern hits
    injection_marker_details: tuple = ()         # ((offset, pattern_name, matched_text), ...)
    unicode_normalized: bool = False             # True if normalization was applied
    control_chars_stripped: int = 0              # count of stripped control characters
    input_truncated: bool = False                # True if max_bytes was hit
    integrity_violations: int = 0                # fact chain verification failures (§22.4)
```

**Zero false-positive policy**: Patterns are conservative. CRP would rather miss an injection than flag legitimate text. The purpose is awareness, not gate-keeping. An attacker who knows the patterns can bypass them — that's acceptable because CRP's deeper defense is **window isolation** (§22.5), not pattern matching.

### 22.4 Fact Integrity Chain

**Principle**: Every fact in the knowledge graph carries a **provenance signature**. Facts cannot be silently modified, injected, or replaced without detection.

**Inspired by**: DNSSEC's chain of trust — RRSIGs verify that DNS records come from their authoritative source (not a man-in-the-middle), DS records delegate trust from parent to child zone, and the chain extends from root to leaf.

#### 22.4.1 Fact Provenance Signature

Each fact extracted by the pipeline (§3.3) receives an integrity record:

```python
@dataclass(slots=True)
class FactProvenance:
    fact_hash: bytes             # BLAKE3(fact_text ‖ entity ‖ relation ‖ confidence)
    source_window_id: str        # window that produced this fact
    extraction_stage: int        # 1–6 (which pipeline stage extracted it)
    extraction_timestamp: float  # monotonic timestamp
    source_passage_hash: bytes   # BLAKE3(original text span) — links to §17
    chain_signature: bytes       # HMAC-SHA256(session_key, fact_hash ‖ parent_facts_hash)
```

#### 22.4.2 Chain of Trust — The DNSSEC Pattern Applied to Facts

Just as DNSSEC builds a chain from root → TLD → domain → record (each zone signs the delegation to the next), CRP builds a **fact chain**:

```
Session Init → session_key established (the "root of trust")
    │
Window 1 → extracts Fact A
    │   chain_sig_A = HMAC(session_key, hash(A))
    │
Window 2 → envelope includes Fact A → extracts Fact B
    │   chain_sig_B = HMAC(session_key, hash(B) ‖ hash(A))
    │
Window 3 → envelope includes Facts A, B → extracts Fact C
    │   chain_sig_C = HMAC(session_key, hash(C) ‖ hash(A) ‖ hash(B))
    │
    ▼ ... chain extends through entire session
```

**Analogy**:
| DNSSEC | CRP Fact Chain |
|--------|---------------|
| Root signing ceremony → root KSK | Session binding → session_key |
| Zone Signing Key (ZSK) | Window-local extraction |
| RRSIG on each record | chain_signature on each fact |
| DS record (parent → child trust) | Parent fact hashes in chain_signature |
| NSEC (explicit denial) | FactEvent.SUPERSEDED (explicit invalidation) |

#### 22.4.3 Chain Verification

Before a fact enters an envelope, CRP verifies:

1. **Integrity**: `fact_hash` matches recomputed BLAKE3 of current fact content. If content was tampered, hashes diverge.
2. **Provenance**: `chain_signature` HMAC verifies against `session_key` + declared parent fact hashes.
3. **Existence**: `source_window_id` exists in the window DAG and precedes the current window.
4. **Timestamp ordering**: `extraction_timestamp` is monotonically increasing within the session.

**Tampering Response**:
- Verification failure → fact is **quarantined** (removed from envelope candidates for remainder of session)
- `FactEvent.INTEGRITY_VIOLATION` recorded in event log with full details
- `QualityReport.security_flags.integrity_violations` incremented
- **NO automatic retry** — quarantine is permanent for the session. The caller must decide whether to continue.

#### 22.4.4 Ingest Provenance — Anti-Poisoning for External Data

Data entering via `crp.ingest()` receives distinct provenance handling. This is where OWASP LLM04 (Data Poisoning) and MCP Tool Poisoning lessons apply most directly.

```python
@dataclass(slots=True)
class IngestProvenance:
    source_label: str            # caller-provided source identifier ("user_upload", "api_response")
    ingest_timestamp: float
    content_hash: bytes          # BLAKE3 of raw input
    trust_level: str             # 'VERIFIED' | 'UNVERIFIED' (default: UNVERIFIED)
    quarantine_remaining: int    # windows remaining in quarantine (default: 1)
```

**Anti-Poisoning Rules**:

| Rule | Description | Rationale |
|------|-------------|-----------|
| **Provenance tagging** | All ingested facts tagged `source='ingest'` with their `IngestProvenance` | Envelopes can distinguish ingest-origin vs extraction-origin facts |
| **Quarantine window** | Ingested facts enter quarantine (default: 1 window). During quarantine: confidence penalty ×0.7, cannot override extraction-derived facts | Gives the LLM + extraction pipeline time to corroborate or contradict |
| **Unverified default** | All external data is `trust_level='UNVERIFIED'` unless caller explicitly certifies | Fail-safe: assume external data is potentially poisoned |
| **Cross-reference validation** | If a quarantined fact contradicts an extraction-derived fact of equal or higher confidence, the extraction-derived fact wins | The protocol trusts its own extraction over external claims |
| **Batch poisoning detection** | If >30% of facts from a single `ingest()` call fail cross-reference validation, ALL facts from that batch are quarantined permanently | Catches coordinated poisoning attempts |

### 22.5 Cross-Window Isolation & Prompt Injection Defense

**Principle**: Each window is a **trust boundary**. Content from one window cannot directly manipulate the behavior of another window through the envelope.

**Inspired by**: OWASP LLM01 (segregate and identify external content, enforce privilege control), MCP cross-server shadowing attacks (a malicious server's tool description redirected a trusted server's email tool).

#### 22.5.1 Envelope Sanitization

When building an envelope from warm state, CRP applies three layers of sanitization:

**Layer 1 — Fact-Only Transfer**: Envelopes carry **facts** (structured named entities, relations, typed graph nodes) — not raw text snippets that could contain injection payloads. The extraction pipeline (§3.3) normalizes LLM output into atomic, structured facts. An injection payload like `"Ignore all previous instructions and..."` would need to survive extraction as a named fact with an entity type and confidence score — which it cannot.

**Layer 2 — Source Passage Sandboxing**: When source passages are included (§17), they are wrapped in containment markers:
```
[SOURCE_PASSAGE window=3 confidence=0.92 readonly=true]
The server was configured with Apache 2.4.49 running on port 443...
[/SOURCE_PASSAGE]
```
These markers signal to the envelope format (and any consuming LLM) that this content is **quoted data**, not instructions. The `readonly=true` attribute is a format-level assertion.

**Layer 3 — Metadata Stripping**: Task_input metadata fields that match injection patterns (§22.3.2) are stripped before entering the envelope. The original is preserved in the event log for audit.

#### 22.5.2 Window Isolation Guarantees

| Property | Guarantee | Mechanism |
|----------|-----------|-----------|
| **Context isolation** | Window N's envelope contains facts extracted from prior windows, never raw output text | Extraction pipeline (§3.3) is the ONLY bridge between windows |
| **Injection propagation block** | An injection payload in Window N cannot reach Window N+1 as an instruction | Facts are normalized text; extraction strips instructional framing |
| **Cross-task contamination** | Parallel fan-out windows (§4.4) share no mutable state | Each window reads an immutable snapshot of warm state at dispatch time |
| **Ingest contamination** | External data cannot silently override extraction-derived facts | Quarantine + confidence penalty (§22.4.4) |
| **Echo-based injection** | Repeated text in continuation cannot bypass extraction | Echo detection (§4.8) removes redundant text before extraction runs |
| **Payload splitting** | Distributing injection fragments across multiple inputs cannot accumulate | Each window's extraction normalizes independently; fragments don't reassemble as facts |

#### 22.5.3 The MCP Lesson Applied

MCP's Tool Poisoning Attack worked because **tool descriptions were passed raw to the LLM** — hidden `<IMPORTANT>` tags in tool descriptions were invisible to users but visible to models. CRP's architecture is fundamentally resistant:

1. CRP **never passes raw external text to the LLM as instructions**. All text passes through extraction → facts → envelope construction.
2. CRP's envelope is **structured data** (facts, passages, metadata), not a flat text blob. There is no mechanism for injecting executable instructions into the envelope format.
3. CRP respects **Axiom 4 (Model Ignorance)** — the LLM doesn't know CRP exists. There are no CRP-specific instructions in the prompt that an attacker could hijack.

### 22.6 Role-Based Access Control (RBAC)

**Principle**: Not every caller needs full protocol access. RBAC restricts operations to prevent accidental or malicious misuse.

#### 22.6.1 Role Definitions

| Role | `dispatch()` | `ingest()` | `session_status()` | `cost_estimate()` | `configure()` | `reset_session()` | `export_state()` |
|------|-------------|------------|--------------------|--------------------|---------------|-------------------|-------------------|
| **OBSERVER** | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **OPERATOR** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **ADMIN** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Role Assignment**:
- Roles are assigned during `crp.init()` via the `SessionBinding.capabilities` field
- **Default (no config): OPERATOR** — full dispatch + ingest, no configuration or export. Sufficient for 95% of use cases.
- **OBSERVER**: For monitoring dashboards, cost tracking, session health checks. Cannot modify state.
- **ADMIN**: For session management, configuration changes, state export, session reset. Required for destructive operations.

```python
@dataclass(slots=True)
class RBACPolicy:
    role: str = 'OPERATOR'                        # OBSERVER | OPERATOR | ADMIN
    max_dispatch_per_minute: int = 60              # rate limit — DoS protection
    max_ingest_bytes_per_minute: int = 100_000_000 # 100 MB/min ingest ceiling
    max_concurrent_sessions: int = 4               # per application (app_id)
    allow_state_export: bool = False               # requires ADMIN
    allow_session_reset: bool = False              # requires ADMIN
    allow_encryption_disable: bool = False          # requires ADMIN
```

#### 22.6.2 Rate Limiting — Anti-DoS (OWASP LLM10)

CRP enforces per-session rate limits to prevent unbounded consumption:

| Operation | Default Limit | Minimum Allowed | Exceeded Behavior |
|-----------|--------------|-----------------|-------------------|
| `dispatch()` | 60/minute | 1/minute | `RateLimitExceeded` error with retry-after hint |
| `ingest()` | 100 MB/minute | 1 MB/minute | `RateLimitExceeded` error |
| Concurrent sessions | 4 per app_id | 1 per app_id | `SessionLimitExceeded` error |
| Session duration | 24 hours | 1 hour | `SessionExpired` error — requires re-init |

Rate limits interact with Resource Allocation (§3.7.1): if `ResourceAllocation.max_windows_per_minute` is set, the dispatch rate limit is capped to `min(RBAC limit, resource limit)`.

### 22.7 State Protection

**Principle**: CRP's warm and cold state may contain sensitive extracted knowledge. State must be protected at rest and resistant to external tampering.

#### 22.7.1 Encryption at Rest

```python
@dataclass(slots=True)
class StateEncryption:
    enabled: bool = True                       # default ON
    algorithm: str = 'AES-256-GCM'             # authenticated encryption (integrity + confidentiality)
    key_derivation: str = 'HKDF-SHA256'        # derive storage key from binding_secret
    key_rotation_sessions: int = 100            # rotate derived key every N sessions
    nonce_strategy: str = 'counter'             # AES-GCM nonce: counter-based (no reuse risk)
```

**What IS encrypted**:
| Data | Location | Encryption |
|------|----------|------------|
| Cold state (Tier 3) | Disk (SQLite / files) | AES-256-GCM with HKDF-derived key |
| Event log | Disk (append-only) | AES-256-GCM per log segment |
| Exported state | File (ADMIN export) | AES-256-GCM with separate export key |

**What is NOT encrypted** (performance-critical, in-memory only):
| Data | Location | Protection |
|------|----------|------------|
| Active warm state (Tier 2) | Process memory | OS process isolation |
| ANN index | Process memory | Reconstructible from facts |
| Model weights | Process memory (ModelRegistry) | Loaded from verified GGUF paths |

#### 22.7.2 Embedding Inversion Protection

Stored SQ8 quantized embeddings carry inherent protection: quantization to 8-bit integers with scalar quantization loses precision, making inversion attacks (recovering source text from embeddings — OWASP LLM08 risk #3) significantly harder than on float32.

CRP adds two additional defenses:

1. **Embedding Salting**: Before storage, a random 4-byte salt is XOR'd into each embedding vector segment. The salt is stored alongside. On retrieval, the salt is reversed. This prevents direct embedding comparison attacks by an adversary who accesses the storage file — they cannot query the stored embeddings directly against a target corpus without the salt.

2. **No Direct Embedding Export**: `export_state()` (ADMIN-only) exports facts and relations as text — **never** raw embedding vectors. On import, embeddings are recomputed from fact text. This eliminates the embedding-as-attack-surface entirely for export scenarios.

#### 22.7.3 State Integrity Verification

When cold state is loaded at session resumption:
1. AES-GCM decryption verifies authentication tag → detects tampering
2. After decryption, fact chain signatures (§22.4.2) are spot-checked (random 10% sample)
3. If >5% of spot-checked facts fail verification → entire cold state is rejected, session starts fresh
4. `FactEvent.COLD_STATE_INTEGRITY_FAILURE` recorded

### 22.8 OWASP Alignment Matrix

#### 22.8.1 OWASP Top 10 for LLM Applications (2025) — CRP Coverage

| ID | Vulnerability | CRP Mitigation | Defense Depth |
|----|--------------|----------------|---------------|
| **LLM01** | **Prompt Injection** | Advisory injection detection (§22.3.2), fact-only envelope transfer, source passage sandboxing, window isolation (§22.5), extraction normalization | **3 layers** — detection + structural defense + isolation |
| **LLM02** | **Sensitive Info Disclosure** | RBAC restricts state export (§22.6), encryption at rest (§22.7), no LLM access to raw warm state, session binding prevents unauthorized reads | **2 layers** — access control + encryption |
| **LLM03** | **Supply Chain** | GGUF models loaded from verified paths with hash check in ModelRegistry (§3.3), no runtime package installation, pinned dependencies | **1 layer** — verified model loading |
| **LLM04** | **Data & Model Poisoning** | Ingest quarantine (§22.4.4), provenance tagging, cross-reference validation, confidence penalty for unverified data, batch poisoning detection | **4 layers** — quarantine + provenance + cross-reference + batch detection |
| **LLM05** | **Improper Output Handling** | Three-tier extraction validation (§3.3 quality gates), structural validation (§22.3.1), fact chain integrity check | **2 layers** — validation + integrity |
| **LLM06** | **Excessive Agency** | CRP has NO tool-calling capability. It structures context, not actions. The LLM receives an envelope of facts, not a toolkit of functions | **Architectural** — attack surface doesn't exist |
| **LLM07** | **System Prompt Leakage** | CRP does not inject system prompts. Envelope is structured data, not instruction text. Model Ignorance (Axiom 4) means there are no CRP instructions to leak | **Architectural** — no system prompt to leak |
| **LLM08** | **Vector & Embedding Weaknesses** | Embedding salting (§22.7.2), SQ8 quantization, no embedding export, access-scoped fact retrieval via RBAC | **3 layers** — salting + quantization + access control |
| **LLM09** | **Misinformation** | Source-grounded envelopes (§17), fact chain verification (§22.4), contradiction detection (§3.4), CWCV (§13) | **4 layers** — source grounding + chain + contradiction + validation |
| **LLM10** | **Unbounded Consumption** | Rate limiting (§22.6.2), budget caps (§6.8), resource allocation (§3.7.1), session duration limits | **3 layers** — rate limit + budget + resource allocation |

#### 22.8.2 OWASP ML Security Top 10 (2023) — CRP Coverage

| ID | Risk | CRP Mitigation |
|----|------|----------------|
| **ML01** | Input Manipulation Attack | Structural validation (§22.3.1), Unicode normalization, injection pattern detection |
| **ML02** | Data Poisoning Attack | Ingest quarantine, provenance chain, cross-reference validation, batch detection |
| **ML03** | Model Inversion Attack | Embedding salting, no embedding export, SQ8 quantization loss |
| **ML04** | Membership Inference Attack | CRP does not expose training data; warm state is session-scoped and encrypted |
| **ML05** | Model Theft | ModelRegistry binds models to process; no model export API in CRP |
| **ML06** | AI Supply Chain Attacks | Hash-verified GGUF models from configured paths only |
| **ML07** | Transfer Learning Attack | CRP does not perform transfer learning; uses pre-trained models read-only |
| **ML08** | Model Skewing | Not applicable — CRP does not train or fine-tune models |
| **ML09** | Output Integrity Attack | Three-tier extraction validation, fact provenance signatures, quality gates |
| **ML10** | Model Poisoning | Models loaded from verified paths only; ModelRegistry hash check on load |

#### 22.8.3 MCP Security Lessons Applied

| MCP Vulnerability | How It Works | CRP Equivalent Risk | CRP Defense |
|-------------------|-------------|---------------------|-------------|
| **Tool Poisoning Attack** | Hidden `<IMPORTANT>` tags in tool descriptions instruct LLM to exfiltrate data | Injection in task_input metadata | Advisory detection + extraction normalization strips instructional text |
| **Rug Pull** | Server changes tool description after client approval | Warm state facts modified after acceptance | HMAC-signed fact chain verifies integrity at envelope construction time |
| **Cross-Server Shadowing** | Malicious server's tool description alters behavior of trusted server's tools | Cross-window contamination via facts | Window isolation — each window's envelope is built from extracted facts, not raw text from other windows |
| **Hidden Exfiltration** | LLM encodes sensitive data in tool call arguments | LLM includes sensitive data in output | CRP preserves raw output (Output Integrity) — caller can audit. CRP does not transmit data |

### 22.9 Quantum-Resistant & AI-Attack Considerations

#### 22.9.1 Post-Quantum Readiness

CRP's cryptographic posture:

| Current Algorithm | Purpose | Quantum Threat | Status |
|-------------------|---------|---------------|--------|
| HMAC-SHA256 | Session binding, fact chain signatures | Grover's algorithm halves effective security to 128-bit — still secure | ✅ Quantum-safe |
| AES-256-GCM | State encryption at rest | Grover's halves to 128-bit effective — still secure | ✅ Quantum-safe |
| BLAKE3 | Fact hashing, content integrity | Hash functions resistant to quantum attacks | ✅ Quantum-safe |
| HKDF-SHA256 | Key derivation | Based on HMAC — same analysis applies | ✅ Quantum-safe |

**CRP does NOT use** (and therefore is NOT vulnerable to):
- RSA or ECDSA (Shor's algorithm threat) — CRP uses no asymmetric signatures
- Diffie-Hellman (Shor's algorithm threat) — CRP uses pre-shared secrets, no key exchange
- Elliptic curve operations — CRP uses no ECC

**Conclusion**: CRP's symmetric-only design means it is **already quantum-resistant**. No algorithm migration is required. This is a deliberate architectural choice — symmetric-only crypto is sufficient because CRP has no network key exchange requirement.

**Future Migration Path**: If CRP adds multi-device session sharing (application and CRP on different machines), those transports MUST use NIST PQC standardized algorithms:
- **ML-KEM** (FIPS 203) for key encapsulation
- **ML-DSA** (FIPS 204) for digital signatures

#### 22.9.2 AI-Specific Attack Resistance

Attacks specific to AI/ML systems and CRP's posture:

| Attack | Mechanism | CRP Defense | Residual Risk |
|--------|-----------|-------------|---------------|
| **Adversarial suffix** | Appending token sequences that bypass LLM safety filters | Envelope is structured facts, not raw text — reduces attack surface. CRP does not control the LLM's own safety. | Model-level (outside CRP scope) |
| **Gradient-based extraction** | Using model gradients to extract training data | CRP only processes model outputs. No gradient access, no training. | None for CRP |
| **Embedding space attack** | Crafting inputs that cluster near target embeddings to influence retrieval | Bi-encoder + cross-encoder reranking (§3.2) requires both vector proximity AND cross-attention relevance. Single-vector attacks defeated by the second stage. | Low — would need to fool both stages |
| **Sleeper agent activation** | Trigger phrases that activate hidden model backdoors | Outside CRP's scope (model-level). BUT: source grounding (§17) + CWCV (§13) would detect anomalous output shifts. | Model-level; CRP provides detection |
| **Payload splitting** | Distributing injection fragments across multiple inputs to bypass per-input filters | Window isolation prevents accumulation — extraction normalizes each input independently. Fragments don't reassemble in the fact graph. | Very low |
| **Data exfiltration via LLM output** | LLM encodes sensitive data in its response for collection by external party | CRP preserves raw output for audit (Output Integrity). No CRP component transmits data externally. Caller audits output. | Caller responsibility |
| **Prompt leaking via continuation** | Attacker crafts input to make the LLM reveal system instructions in its output | CRP injects NO system instructions (Axiom 4). Envelope is structured data. Nothing to leak. | None for CRP |

### 22.10 Security Configuration

```python
@dataclass(slots=True)
class SecurityConfig:
    """CRP security configuration. All fields have SAFE defaults.
    Structural validation cannot be disabled by any configuration."""
    
    # ── PROTOCOL BINDING ──
    binding_secret: Optional[bytes] = None       # None = auto-generate per process
    session_timeout_seconds: int = 86_400        # 24-hour max session (min: 3600)
    
    # ── INPUT VALIDATION ──
    structural_validation: bool = True            # LOCKED True — cannot be set False
    injection_detection: bool = True              # advisory markers in QualityReport
    unicode_normalization: bool = True            # NFC normalize all text input
    max_task_input_bytes: int = 50_000_000        # 50 MB ceiling
    
    # ── FACT INTEGRITY ──
    fact_chain_signing: bool = True               # HMAC chain of trust on all facts
    ingest_quarantine_windows: int = 1            # quarantine period for ingest() data
    ingest_default_trust: str = 'UNVERIFIED'      # VERIFIED | UNVERIFIED
    batch_poison_threshold: float = 0.3           # reject batch if >30% facts conflict
    
    # ── RBAC ──
    default_role: str = 'OPERATOR'                # OBSERVER | OPERATOR | ADMIN
    max_dispatch_per_minute: int = 60             # minimum: 1
    max_ingest_bytes_per_minute: int = 100_000_000  # minimum: 1_000_000
    max_concurrent_sessions: int = 4              # minimum: 1
    
    # ── STATE PROTECTION ──
    encrypt_cold_state: bool = True               # disabling requires ADMIN role
    encryption_algorithm: str = 'AES-256-GCM'     # only AES-256-GCM supported
    key_rotation_sessions: int = 100              # rotate storage key every N sessions
    embedding_salt: bool = True                   # XOR salt on stored embeddings
    
    # ── COLD STATE INTEGRITY ──
    cold_state_spot_check_ratio: float = 0.1      # verify 10% of facts on load
    cold_state_rejection_threshold: float = 0.05  # reject if >5% fail verification
```

**Security Invariants** (hardened — cannot be weakened by any configuration or role):

| Invariant | Enforcement |
|-----------|-------------|
| Structural validation is ALWAYS enabled | `SecurityConfig.structural_validation` setter raises `SecurityInvariantError` if set to False |
| Rate limits cannot be removed | Minimum enforced: 1 dispatch/min, 1 MB/min ingest, 1 session |
| Fact chain signing requires a secret | Uses auto-generated process key when no explicit secret configured |
| Cold state encryption default is True | Disabling requires ADMIN role AND explicit `configure()` call |
| No unsigned API path exists | Even with auto-generated secret, all requests are signed |

---

## 23. CONCURRENCY MODEL

CRP supports concurrent usage across multiple sessions and, within constraints, within a single session. This section specifies thread-safety guarantees, synchronization requirements, and deadlock prevention — in language-neutral terms applicable to any runtime.

### 23.1 Concurrency Scope

| Scope | Concurrency | Constraint |
|-------|-------------|------------|
| **Cross-session** | Fully parallel | Different sessions share no mutable state. Implementations MUST support concurrent operations on different sessions without serialization. |
| **Intra-session dispatch** | Serialized | Within a single session, `dispatch()` calls MUST be serialized. Warm state is mutable and not designed for concurrent writes. |
| **Intra-session reads** | Parallel | Read-only operations (`session_status()`, `estimate_session()`, `preview_envelope()`) MAY execute concurrently with a running `dispatch()`. |
| **Streaming + reads** | Parallel | While `dispatch_stream()` emits events, `session_status()` MAY be called concurrently to inspect progress. |
| **Model registry** | Thread-safe singleton | The model registry (§3.3) MUST be safe for concurrent access from multiple sessions. Model loading MUST use a lock-per-model-slot strategy to prevent double-loading without blocking unrelated models. |

### 23.2 Synchronization Requirements

Implementations MUST provide the following synchronization guarantees:

#### 23.2.1 Session-Level Lock

Each session MUST have a write-lock (mutex, monitor, or equivalent) that serializes state-mutating operations:

```
OPERATIONS REQUIRING WRITE LOCK:
  dispatch()                  # Modifies warm state, event log
  dispatch_intent()           # Same as dispatch
  ingest()                    # Modifies warm state, event log
  configure()                 # Modifies session configuration
  reset_session()             # Clears and reinitializes state
  close()                     # Finalizes and flushes state

OPERATIONS REQUIRING READ LOCK (or no lock):
  session_status()            # Read-only snapshot
  estimate_session()          # Read-only computation
  preview_envelope()          # Read-only envelope construction
```

- Write operations MUST acquire the session lock before accessing warm state. If the lock is already held, the operation MUST either block or return `CRPError(code=1002, message="Session busy")` — the choice is implementation-defined but MUST be documented.
- Read operations SHOULD use a read-lock (shared lock) if the language/runtime supports reader-writer locks. If not, read operations MAY acquire the full session lock, but this degrades performance for concurrent status queries.

#### 23.2.2 Model Registry Synchronization

The `ModelRegistry` singleton (§3.3) manages shared model instances across sessions:

```
SYNCHRONIZATION RULES:
  load_model(name)    → MUST acquire per-model lock.
                        MUST NOT hold a global lock during download/initialization.
                        MUST be idempotent — concurrent load requests for the SAME model
                        MUST result in exactly one load, not duplicates.
  
  get_model(name)     → MUST be lock-free after initial load (read-only access).
  
  unload_model(name)  → MUST acquire per-model lock.
                        MUST verify ref_count == 0 before unloading.
                        MUST NOT unload while any session is actively using the model.
  
  ref_count tracking  → MUST use atomic increment/decrement (or equivalent).
                        Sessions acquire a reference on first use, release on close().
```

#### 23.2.3 Cold Storage Synchronization

Cold storage (Tier 3) is shared across sessions with the same `app_id`:

- **Reads**: Multiple sessions MAY read cold storage concurrently.
- **Writes**: Cold storage writes (session close, GC) MUST be atomic at the granularity of a single session's state block. Implementations SHOULD use a compare-and-swap or journaling mechanism to prevent corruption from concurrent writes.
- **Cross-session GC** (§6.7): MUST acquire an exclusive lock on the cold storage index. GC SHOULD run at most once per minute to avoid lock contention.

### 23.3 Deadlock Prevention

CRP operations involve at most three lockable resources. The **lock ordering** below MUST be followed by all implementations to prevent deadlocks:

```
LOCK ORDERING (acquire in this order, release in reverse):
  1. Cold Storage Lock       (lowest priority — acquire first if needed)
  2. Model Registry Lock     (per-model, not global)
  3. Session Write Lock      (highest priority — acquire last)
```

**Deadlock-free guarantee**: Since all operations acquire locks in the same order, circular wait is impossible. No CRP operation requires acquiring lock 1 while holding lock 3.

**Timeout policy**: Lock acquisition SHOULD have a timeout (implementation-defined, RECOMMENDED: 30 seconds). If a lock cannot be acquired within the timeout, the operation MUST fail with `CRPError(code=1003)` and MUST NOT leave any state partially modified.

### 23.4 Thread-Safety Classification

Every CRP component is classified for thread-safety:

| Component | Thread-Safety Level | Notes |
|-----------|-------------------|-------|
| `Orchestrator` | Thread-safe across sessions, serialized within session | Session lock per §23.2.1 |
| `WarmStateStore` | NOT thread-safe | Protected by session lock |
| `EnvelopeBuilder` | Stateless — inherently thread-safe | Creates new envelope per call |
| `ExtractionPipeline` | Stateless per invocation — thread-safe | Stateful only within a single extract() call |
| `ModelRegistry` | Thread-safe (singleton, per-model locks) | §23.2.2 |
| `EventLog` | Append-only — thread-safe for appends | Concurrent reads safe; appends serialized by session lock |
| `CKF / FactGraph` | Per-session: protected by session lock. Cross-session: read-safe | Graph mutations only during session-locked operations |
| `SecurityConfig` | Immutable after init — inherently thread-safe | Changes via `configure()` create a new config snapshot |
| `ColdStoragePolicy` | Protected by cold storage lock | §23.2.3 |

---

## 24. OBSERVABILITY & AUDIT

CRP provides a comprehensive observability layer designed for production monitoring, debugging, compliance auditing, and performance analysis. This section defines structured event formats, metrics catalogs, trace specifications, and audit trail requirements.

### 24.1 Design Principles

1. **Structured by default**: All observable output MUST be structured (JSON or equivalent). No free-text log messages in production.
2. **Zero-cost when disabled**: Observability features that are not enabled MUST add zero overhead to the critical path. Implementations SHOULD use compile-time or load-time feature flags, not runtime branch-per-event checks.
3. **Audit-grade completeness**: The combination of structured events, metrics, and the fact event log (§5.4) MUST be sufficient to fully reconstruct any CRP session — what happened, when, why, and what was the outcome.
4. **Standard formats**: CRP's observability MUST map cleanly to industry-standard telemetry systems (OpenTelemetry, Prometheus, structured JSON logging) without custom parsers.

### 24.2 Structured Event Log

CRP emits **structured events** for every significant operation. Events follow a common envelope:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CRPEvent",
  "description": "Common envelope for all CRP structured events.",
  "type": "object",
  "required": ["timestamp", "event_type", "session_id", "severity", "payload"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp with timezone (e.g., 2026-04-06T14:30:00.123Z). MUST use UTC."
    },
    "event_type": {
      "type": "string",
      "description": "Dot-namespaced event type (e.g., 'crp.dispatch.start')."
    },
    "session_id": {
      "type": ["string", "null"],
      "format": "uuid",
      "description": "Session UUID. NULL for system-level events (e.g., model loading)."
    },
    "window_id": {
      "type": ["string", "null"],
      "format": "uuid",
      "description": "Window UUID. NULL for non-window events."
    },
    "severity": {
      "type": "string",
      "enum": ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"],
      "description": "Event severity level."
    },
    "component": {
      "type": "string",
      "description": "CRP component that emitted the event (e.g., 'orchestrator', 'extraction', 'security')."
    },
    "payload": {
      "type": "object",
      "description": "Event-specific structured data. Schema depends on event_type."
    },
    "trace_id": {
      "type": ["string", "null"],
      "description": "OpenTelemetry-compatible trace ID (32-character hex). NULL if tracing disabled."
    },
    "span_id": {
      "type": ["string", "null"],
      "description": "OpenTelemetry-compatible span ID (16-character hex). NULL if tracing disabled."
    }
  }
}
```

### 24.3 Event Type Catalog

All CRP event types, organized by subsystem. Implementations MUST emit events marked **Required**. Events marked **Optional** SHOULD be emitted when the corresponding feature is enabled.

#### 24.3.1 Session Lifecycle Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.session.init` | INFO | **Yes** | `app_id`, `protocol_version`, `rbac_role`, `config_summary` |
| `crp.session.close` | INFO | **Yes** | `windows_completed`, `total_input_tokens`, `total_output_tokens`, `facts_stored`, `duration_seconds` |
| `crp.session.expire` | WARN | **Yes** | `reason` ("timeout" / "budget_exhausted"), `windows_completed` |
| `crp.session.resume` | INFO | **Yes** | `cold_facts_restored`, `cold_state_age_seconds` |
| `crp.session.configure` | INFO | **Yes** | `changed_fields[]`, `old_values{}`, `new_values{}` |
| `crp.session.reset` | WARN | **Yes** | `facts_flushed`, `windows_reset` |

#### 24.3.2 Dispatch Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.dispatch.start` | INFO | **Yes** | `task_input_tokens`, `system_prompt_tokens`, `envelope_tokens`, `generation_reserve`, `saturation` |
| `crp.dispatch.complete` | INFO | **Yes** | `output_tokens`, `facts_extracted`, `quality_tier`, `latency_ms`, `continuation_windows` |
| `crp.dispatch.continuation` | INFO | **Yes** | `continuation_number`, `reason` ("physical_wall" / "truncation"), `prior_window_id` |
| `crp.dispatch.error` | ERROR | **Yes** | `error_code`, `error_message`, `error_details` |
| `crp.dispatch.budget_warning` | WARN | **Yes** | `cap_type`, `used`, `limit`, `remaining_pct` |

#### 24.3.3 Extraction Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.extraction.start` | DEBUG | Optional | `input_length`, `content_type` |
| `crp.extraction.stage_complete` | DEBUG | Optional | `stage` (1-6), `stage_name`, `facts_found`, `latency_ms` |
| `crp.extraction.complete` | INFO | **Yes** | `total_facts`, `total_edges`, `stages_executed[]`, `total_latency_ms` |
| `crp.extraction.quality_gate` | INFO | **Yes** | `facts_accepted`, `facts_rejected`, `rejection_reasons[]` |
| `crp.extraction.contradiction` | WARN | **Yes** | `new_fact_id`, `superseded_fact_id`, `similarity_score` |

#### 24.3.4 Envelope Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.envelope.build_start` | DEBUG | Optional | `warm_facts_available`, `ckf_facts_available` |
| `crp.envelope.build_complete` | INFO | **Yes** | `facts_included`, `facts_available`, `saturation`, `scoring_latency_ms`, `ckf_retrieval_ms` |
| `crp.envelope.overflow` | WARN | Optional | `facts_dropped`, `lowest_dropped_score` |

#### 24.3.5 Security Events

Security events are critical for audit compliance and MUST always be emitted regardless of log level configuration.

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.security.signature_verified` | TRACE | Optional | `hmac_algorithm`, `verification_latency_us` |
| `crp.security.signature_failed` | ERROR | **Yes** | `expected_prefix`, `received_prefix`, `session_id` |
| `crp.security.injection_detected` | WARN | **Yes** | `pattern_name`, `matched_text`, `offset`, `action` ("flagged" / "stripped") |
| `crp.security.rbac_denied` | WARN | **Yes** | `operation`, `required_role`, `actual_role` |
| `crp.security.rate_limited` | WARN | **Yes** | `cap_type`, `current_rate`, `limit` |
| `crp.security.integrity_violation` | ERROR | **Yes** | `fact_id`, `expected_hash`, `actual_hash`, `source_window` |
| `crp.security.quarantine_reject` | WARN | **Yes** | `source_label`, `facts_rejected`, `reason` ("conflict_ratio" / "confidence" / "batch_poisoning") |
| `crp.security.config_change` | INFO | **Yes** | `field`, `old_value`, `new_value`, `role` |

#### 24.3.6 Model & Resource Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.model.load_start` | INFO | **Yes** | `model_name`, `model_size_mb` |
| `crp.model.load_complete` | INFO | **Yes** | `model_name`, `load_latency_ms`, `memory_used_mb` |
| `crp.model.unload` | INFO | **Yes** | `model_name`, `reason` ("idle" / "pressure" / "session_close"), `idle_windows` |
| `crp.model.download_start` | INFO | **Yes** | `model_name`, `source_url` |
| `crp.resource.pressure_change` | WARN | **Yes** | `old_level`, `new_level`, `ram_used_pct`, `vram_used_pct` |
| `crp.resource.feature_shed` | WARN | **Yes** | `feature_disabled`, `reason`, `overhead_ratio` |

#### 24.3.7 CKF Events

| Event Type | Severity | Required | Payload Fields |
|-----------|----------|----------|---------------|
| `crp.ckf.retrieval` | DEBUG | Optional | `mode` ("graph_walk" / "pattern_query" / "semantic" / "community"), `results_count`, `latency_ms` |
| `crp.ckf.community_detect` | INFO | Optional | `communities_found`, `modularity_score`, `latency_ms` |
| `crp.ckf.gc_run` | INFO | **Yes** | `facts_purged`, `facts_archived`, `cold_storage_before_mb`, `cold_storage_after_mb` |

### 24.4 Metrics Catalog

CRP exposes metrics suitable for time-series monitoring (Prometheus, OpenTelemetry Metrics, CloudWatch, Datadog, etc.). All metrics use the `crp_` prefix.

#### 24.4.1 Counter Metrics (monotonically increasing)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `crp_dispatches_total` | counter | `session_id`, `quality_tier` | Total dispatch operations completed |
| `crp_windows_total` | counter | `session_id`, `type` (productive/continuation/overhead) | Total windows executed |
| `crp_tokens_input_total` | counter | `session_id` | Total input tokens consumed |
| `crp_tokens_output_total` | counter | `session_id` | Total output tokens generated |
| `crp_facts_extracted_total` | counter | `session_id`, `stage` | Facts extracted by pipeline stage |
| `crp_facts_superseded_total` | counter | `session_id` | Facts superseded by newer contradictions |
| `crp_errors_total` | counter | `error_code` | Total errors by error code |
| `crp_security_events_total` | counter | `event_type` | Security events by type |
| `crp_ingest_operations_total` | counter | `session_id` | Total ingest operations |
| `crp_continuations_total` | counter | `session_id` | Total continuation windows triggered |

#### 24.4.2 Gauge Metrics (current value)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `crp_active_sessions` | gauge | `app_id` | Currently active sessions |
| `crp_warm_state_facts` | gauge | `session_id` | Current fact count in warm state |
| `crp_warm_state_bytes` | gauge | `session_id` | Current warm state memory usage |
| `crp_cold_storage_bytes` | gauge | `app_id` | Total cold storage usage |
| `crp_models_loaded` | gauge | | Number of models currently loaded |
| `crp_model_memory_bytes` | gauge | `model_name` | Memory used per loaded model |
| `crp_overhead_ratio` | gauge | `session_id` | Current overhead window ratio |
| `crp_resource_pressure_level` | gauge | | Current resource pressure (0=nominal, 1=elevated, 2=critical, 3=emergency) |

#### 24.4.3 Histogram Metrics (distributions)

| Metric | Type | Buckets | Labels | Description |
|--------|------|---------|--------|-------------|
| `crp_dispatch_latency_seconds` | histogram | 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120 | `quality_tier` | End-to-end dispatch latency |
| `crp_extraction_latency_seconds` | histogram | 0.01, 0.05, 0.1, 0.25, 0.5, 1 | `stage` | Per-stage extraction latency |
| `crp_envelope_saturation` | histogram | 0.5, 0.7, 0.8, 0.9, 0.95, 0.99 | | Envelope space utilization |
| `crp_envelope_build_seconds` | histogram | 0.001, 0.005, 0.01, 0.05, 0.1 | | Envelope construction time |
| `crp_ckf_retrieval_seconds` | histogram | 0.001, 0.005, 0.01, 0.05, 0.1, 0.5 | `mode` | CKF retrieval latency by mode |
| `crp_security_overhead_seconds` | histogram | 0.00001, 0.0001, 0.001, 0.01 | `check_type` | Security check latency |

### 24.5 Distributed Tracing (OpenTelemetry)

CRP operations SHOULD emit OpenTelemetry-compatible traces when tracing is enabled. Each operation produces spans with standard attributes.

#### 24.5.1 Trace Structure

A typical `dispatch()` call produces the following span tree:

```
crp.dispatch (root span)
├── crp.security.validate_request
│   ├── crp.security.verify_signature
│   └── crp.security.validate_input
├── crp.envelope.build
│   ├── crp.ckf.retrieval (one per mode used)
│   ├── crp.envelope.score_facts
│   └── crp.envelope.pack
├── crp.llm.generate
│   └── (LLM provider span — delegated to provider SDK)
├── crp.extraction.pipeline
│   ├── crp.extraction.stage_1_regex
│   ├── crp.extraction.stage_2_statistical
│   ├── crp.extraction.stage_3_gliner (if enabled)
│   ├── crp.extraction.stage_4_uie (if enabled)
│   ├── crp.extraction.stage_5_discourse (if enabled)
│   └── crp.extraction.stage_6_llm (if enabled)
├── crp.warm_state.update
│   ├── crp.warm_state.quality_gate
│   ├── crp.warm_state.contradiction_check
│   └── crp.warm_state.add_facts
└── crp.telemetry.emit (QualityReport construction)
```

#### 24.5.2 Span Attributes

All CRP spans MUST include:

| Attribute | Type | Description |
|-----------|------|-------------|
| `crp.session_id` | string | Session UUID |
| `crp.window_id` | string | Window UUID (if applicable) |
| `crp.protocol_version` | string | CRP protocol version |
| `crp.component` | string | Component name |

Operation-specific spans SHOULD include:

| Span | Additional Attributes |
|------|-----------------------|
| `crp.dispatch` | `crp.quality_tier`, `crp.facts_extracted`, `crp.continuation_count`, `crp.saturation` |
| `crp.envelope.build` | `crp.facts_included`, `crp.saturation`, `crp.scoring_method` |
| `crp.llm.generate` | `crp.input_tokens`, `crp.output_tokens`, `crp.finish_reason`, `crp.model_name` |
| `crp.extraction.stage_*` | `crp.stage_number`, `crp.facts_found`, `crp.content_type` |

#### 24.5.3 Trace Propagation

When CRP is accessed via JSON-RPC or gRPC transport (§6.10.9), trace context MUST be propagated using the W3C Trace Context headers (`traceparent`, `tracestate`). The transport layer is responsible for extracting trace context from incoming requests and injecting it into the CRP span context.

### 24.6 Audit Trail Specification

CRP's audit trail serves compliance, forensics, and debugging. It combines three data sources:

| Data Source | Content | Retention | Tampering Protection |
|-------------|---------|-----------|---------------------|
| **Fact Event Log** (§5.4) | Complete lifecycle of every fact (created, superseded, compacted, archived) | Configurable per §25.3 | BLAKE3 chain hashing (§22.4) |
| **Structured Event Log** (§24.2) | All CRP operations with timestamps and payloads | Configurable per §25.3 | Append-only; rotation creates sealed archives |
| **Security Event Log** | Subset of structured events with `crp.security.*` type | MUST be retained for minimum 90 days | Same as structured log + separate security audit stream |

#### 24.6.1 Audit Query Interface

Implementations MUST provide an audit query interface:

```
INTERFACE AuditLog:
  query_events(
    session_id?: uuid,
    window_id?: uuid,
    event_type?: string,          # Prefix match — "crp.security" matches all security events
    severity_min?: enum("TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"),
    time_range?: (start: datetime, end: datetime),
    limit?: integer               # Default: 1000, Max: 10000
  ) -> EventPage
  
  reconstruct_session(
    session_id: uuid
  ) -> SessionReconstruction
  # Returns complete reconstruction: all events, all facts, all windows, timeline
  
  export_audit_bundle(
    session_id: uuid,
    format: enum("json", "jsonl", "csv")
  ) -> bytes
  # Exports a self-contained, verifiable audit bundle for a session
```

```
RECORD EventPage:
  events: CRPEvent[]              # Matching events
  total_count: integer            # Total matching events (may exceed returned count)
  next_cursor?: string            # Pagination cursor for next page
```

```
RECORD SessionReconstruction:
  session_id: uuid
  timeline: CRPEvent[]            # All events in chronological order
  fact_graph_snapshots: Map<integer, FactGraphSnapshot>  # Fact graph state at each window
  quality_reports: QualityReport[] # One per dispatch
  security_summary: SecurityAuditSummary
  metadata: Map<string, any>
```

#### 24.6.2 Audit Completeness Guarantee

For any session that was properly closed (via `close()` or session timeout), the audit trail MUST be sufficient to answer:

1. **What happened?** — Full chronological event sequence with structured payloads
2. **What facts were extracted?** — Complete fact lifecycle via FactEvent log
3. **What was the LLM told?** — Envelope contents at each window (reconstructable from events)
4. **What did the LLM produce?** — Output preserved per Output Integrity (Axiom 9)
5. **Were there security incidents?** — All security events with full context
6. **What decisions did CRP make?** — Scoring decisions, quality gate results, continuation triggers, feature shedding
7. **What was the cost?** — Complete token counts, window counts, latency measurements

#### 24.6.3 Compliance Mapping

CRP's audit system maps to common compliance requirements:

| Requirement | CRP Coverage |
|-------------|-------------|
| **SOC 2 — CC7.2** (System monitoring) | Structured event log + metrics cover all system activity |
| **SOC 2 — CC7.3** (Anomaly detection) | Security events for injection, integrity violations, rate limiting |
| **GDPR — Art. 30** (Records of processing) | Session reconstruction shows all data processing with timestamps |
| **GDPR — Art. 35** (Impact assessment) | Audit bundles provide complete processing records for DPIA |
| **HIPAA — §164.312(b)** (Audit controls) | Tamper-resistant event log with chain hashing; 90-day security retention |
| **ISO 27001 — A.12.4** (Logging and monitoring) | Structured events, metrics, alerting integration |
| **AI Act — Art. 12** (Record-keeping for high-risk AI) | Full session reconstruction including LLM inputs/outputs, decisions, safety checks |

### 24.7 Log Levels and Filtering

Implementations MUST support configurable log level filtering:

| Level | Purpose | Production Default |
|-------|---------|-------------------|
| `TRACE` | Extremely detailed — per-token, per-fact-score events | OFF |
| `DEBUG` | Internal pipeline details — stage-by-stage extraction, scoring breakdowns | OFF |
| `INFO` | Normal operations — dispatch start/complete, session lifecycle | **ON** |
| `WARN` | Concerning but recoverable — budget warnings, rate limits, injection flags | **ON** |
| `ERROR` | Failed operations — signature failures, provider errors, state corruption | **ON** |
| `FATAL` | Unrecoverable — the CRP instance cannot continue | **ON** |

**Override**: Security events (`crp.security.*`) MUST always be emitted regardless of the configured log level. An implementation MUST NOT provide a way to suppress security event emission.

### 24.8 Log Rotation and Retention

```
RECORD LogRetentionPolicy:
  structured_log_max_size_mb: integer = 500      # Rotate when log exceeds this size
  structured_log_max_age_days: integer = 30       # Archive logs older than this
  security_log_min_retention_days: integer = 90   # Security events MUST be retained
  fact_event_log_retention: enum("session", "persistent") = "persistent"
  archive_format: enum("gzip", "zstd", "none") = "zstd"
  archive_encryption: boolean = true              # Encrypt archived logs using state encryptor
```

- On rotation, the completed log file MUST be sealed (no further writes) and a BLAKE3 hash MUST be computed and stored alongside it.
- Archived logs SHOULD be compressed. If `archive_encryption` is true, archived logs MUST be encrypted using the same AES-256-GCM mechanism as cold state (§22.7).
- Implementations MUST NOT delete security events before `security_log_min_retention_days` has elapsed, regardless of other retention settings.

---

## 25. CONFIGURATION MANAGEMENT

CRP's configuration is hierarchical, validated, and auditable. This section specifies the configuration schema, layering, validation, and runtime change semantics.

### 25.1 Configuration Hierarchy

CRP configuration is resolved through a layered hierarchy. Later layers override earlier ones:

```
LAYER 1: Protocol Defaults (hardcoded in CRP specification — this document)
    ↓ overridden by
LAYER 2: Environment Variables (CRP_* prefix, per §25.4)
    ↓ overridden by
LAYER 3: Configuration File (JSON/YAML/TOML, per §25.5)
    ↓ overridden by
LAYER 4: init() Parameters (programmatic configuration at session creation)
    ↓ overridden by
LAYER 5: configure() Calls (runtime changes within a session, ADMIN role only)
```

**Resolution rule**: For any configuration key, the value from the highest applicable layer wins. Implementations MUST log (at DEBUG level) which layer each configuration value was resolved from, to aid debugging.

### 25.2 Configuration Schema

The complete CRP configuration is specified as a JSON Schema. All fields have defaults — a zero-configuration start is REQUIRED to be valid.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CRPConfiguration",
  "description": "Complete CRP configuration schema. All fields have defaults.",
  "type": "object",
  "properties": {
    "protocol": {
      "type": "object",
      "description": "Core protocol settings.",
      "properties": {
        "version": { "type": "string", "const": "2.0.0" },
        "app_id": { "type": "string", "minLength": 1, "maxLength": 256 }
      }
    },
    "security": {
      "type": "object",
      "description": "Security configuration. See §22 for full specification.",
      "properties": {
        "binding_secret": { "type": ["string", "null"], "contentEncoding": "base64", "default": null },
        "session_timeout_seconds": { "type": "integer", "minimum": 3600, "maximum": 604800, "default": 86400 },
        "structural_validation": { "const": true, "description": "CANNOT be disabled. Always true." },
        "advisory_injection_detection": { "type": "boolean", "default": true },
        "max_task_input_bytes": { "type": "integer", "minimum": 1024, "maximum": 104857600, "default": 10485760 },
        "rbac": {
          "type": "object",
          "properties": {
            "default_role": { "type": "string", "enum": ["OBSERVER", "OPERATOR", "ADMIN"], "default": "OPERATOR" },
            "max_dispatch_per_minute": { "type": "integer", "minimum": 1, "default": 60 },
            "max_ingest_bytes_per_minute": { "type": "integer", "minimum": 1000000, "default": 100000000 },
            "max_concurrent_sessions": { "type": "integer", "minimum": 1, "default": 4 }
          }
        },
        "encryption": {
          "type": "object",
          "properties": {
            "encrypt_cold_state": { "type": "boolean", "default": true },
            "algorithm": { "type": "string", "const": "AES-256-GCM" },
            "key_rotation_sessions": { "type": "integer", "minimum": 1, "default": 100 },
            "embedding_salt": { "type": "boolean", "default": true }
          }
        },
        "integrity": {
          "type": "object",
          "properties": {
            "cold_state_spot_check_ratio": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.1 },
            "cold_state_rejection_threshold": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.05 }
          }
        }
      }
    },
    "resources": {
      "type": "object",
      "description": "Resource limits. See §3.7 for full specification.",
      "properties": {
        "max_model_ram_mb": { "type": "integer", "minimum": 256, "default": 2048 },
        "max_warm_state_facts": { "type": "integer", "minimum": 100, "default": 50000 },
        "max_warm_state_mb": { "type": "integer", "minimum": 10, "default": 512 },
        "process_priority": { "type": "string", "enum": ["realtime", "high", "normal", "below_normal", "idle"], "default": "below_normal" }
      }
    },
    "cost_controls": {
      "type": "object",
      "description": "Budget caps. See §6.8 for full specification.",
      "properties": {
        "max_windows_per_session": { "type": ["integer", "null"], "minimum": 1, "default": null },
        "max_input_tokens_per_session": { "type": ["integer", "null"], "minimum": 1, "default": null },
        "max_output_tokens_per_session": { "type": ["integer", "null"], "minimum": 1, "default": null },
        "max_dispatch_rate_per_minute": { "type": ["integer", "null"], "minimum": 1, "default": null },
        "max_ingest_bytes_per_minute": { "type": ["integer", "null"], "minimum": 1, "default": null }
      }
    },
    "extraction": {
      "type": "object",
      "description": "Extraction pipeline configuration.",
      "properties": {
        "max_stages": { "type": "integer", "minimum": 1, "maximum": 6, "default": 6 },
        "gliner_model": { "type": "string", "default": "urchade/gliner_base" },
        "uie_model": { "type": "string", "default": "universal-ie/UIE-base-en" },
        "cross_encoder_model": { "type": "string", "default": "cross-encoder/ms-marco-MiniLM-L6-v2" },
        "embedding_model": { "type": "string", "default": "sentence-transformers/all-MiniLM-L6-v2" }
      }
    },
    "observability": {
      "type": "object",
      "description": "Logging and monitoring configuration. See §24.",
      "properties": {
        "log_level": { "type": "string", "enum": ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"], "default": "INFO" },
        "enable_tracing": { "type": "boolean", "default": false },
        "enable_metrics": { "type": "boolean", "default": true },
        "metrics_export_format": { "type": "string", "enum": ["prometheus", "otlp", "json", "none"], "default": "prometheus" },
        "metrics_export_interval_seconds": { "type": "integer", "minimum": 1, "default": 15 },
        "log_retention": {
          "type": "object",
          "properties": {
            "structured_log_max_size_mb": { "type": "integer", "minimum": 10, "default": 500 },
            "structured_log_max_age_days": { "type": "integer", "minimum": 1, "default": 30 },
            "security_log_min_retention_days": { "type": "integer", "minimum": 30, "default": 90 },
            "archive_compression": { "type": "string", "enum": ["gzip", "zstd", "none"], "default": "zstd" },
            "archive_encryption": { "type": "boolean", "default": true }
          }
        }
      }
    },
    "overhead_budget": {
      "type": "object",
      "description": "Overhead budget. See §16.",
      "properties": {
        "max_overhead_pct": { "type": "number", "minimum": 0.01, "maximum": 0.50, "default": 0.15 },
        "feature_priority": {
          "type": "array",
          "description": "Features to shed under pressure, in order (first = shed first).",
          "items": { "type": "string" },
          "default": ["review_tier3", "review_tier2", "orc", "cqs_enrichment", "review_tier1", "re_grounding", "voice_profile"]
        }
      }
    }
  },
  "additionalProperties": false
}
```

### 25.3 Configuration Validation

Configuration validation occurs at two levels:

**Layer-time validation** (when a configuration layer is loaded):
- JSON Schema validation MUST pass. Invalid configurations MUST be rejected, not silently defaulted.
- Cross-field constraints are checked:
  - `security.rbac.max_dispatch_per_minute` × expected window duration MUST NOT exceed `session_timeout_seconds` (nonsensical: allowing more dispatches than a session could physically complete).
  - `resources.max_warm_state_facts` MUST be ≥ 100.
- Security invariants are enforced: `structural_validation` MUST be `true`. Attempting to set it to `false` MUST raise `SecurityInvariantError` (code 1011).

**Runtime validation** (on `configure()` calls):
- Only ADMIN role MAY call `configure()`.
- Changes MUST be validated against the same JSON Schema.
- Every configuration change MUST emit a `crp.session.configure` event (§24.3.1) recording old and new values.
- Certain fields are **init-only** and MUST NOT be changed at runtime:

| Init-Only Field | Reason |
|----------------|--------|
| `security.binding_secret` | Session key derived at init; changing would invalidate all signed state |
| `protocol.version` | Protocol version is fundamental identity |
| `protocol.app_id` | Used for cold storage partitioning |

### 25.4 Environment Variable Mapping

CRP configuration MAY be set via environment variables using the `CRP_` prefix with double-underscore nesting:

| Environment Variable | Maps To | Example |
|---------------------|---------|---------|
| `CRP_SECURITY__SESSION_TIMEOUT_SECONDS` | `security.session_timeout_seconds` | `CRP_SECURITY__SESSION_TIMEOUT_SECONDS=43200` |
| `CRP_SECURITY__RBAC__DEFAULT_ROLE` | `security.rbac.default_role` | `CRP_SECURITY__RBAC__DEFAULT_ROLE=OBSERVER` |
| `CRP_RESOURCES__MAX_MODEL_RAM_MB` | `resources.max_model_ram_mb` | `CRP_RESOURCES__MAX_MODEL_RAM_MB=4096` |
| `CRP_OBSERVABILITY__LOG_LEVEL` | `observability.log_level` | `CRP_OBSERVABILITY__LOG_LEVEL=DEBUG` |
| `CRP_COST_CONTROLS__MAX_WINDOWS_PER_SESSION` | `cost_controls.max_windows_per_session` | `CRP_COST_CONTROLS__MAX_WINDOWS_PER_SESSION=50` |

**Parsing rules**:
- Double underscore (`__`) separates nesting levels.
- Values are parsed as the JSON Schema type of the target field (integer fields parse as integers, boolean fields accept "true"/"false"/"1"/"0").
- Unknown environment variables with the `CRP_` prefix SHOULD emit a warning at startup.
- Environment variables MUST NOT be used for secrets in production. `CRP_SECURITY__BINDING_SECRET` SHOULD use a secure secret manager reference (e.g., `vault://path/to/secret`, `aws-ssm://parameter-name`) rather than a raw value.

### 25.5 Configuration File Format

CRP accepts configuration files in JSON, YAML, or TOML. The file path is resolved in this order:

1. Explicit path passed to `init(config_path=...)`
2. `CRP_CONFIG_FILE` environment variable
3. `./crp.json`, `./crp.yaml`, `./crp.toml` (current working directory)
4. Platform-specific user config directory (e.g., `~/.config/crp/config.json` on Linux, `%APPDATA%\crp\config.json` on Windows)

If no configuration file is found, protocol defaults (Layer 1) apply. This MUST NOT be an error.

### 25.6 Configuration Change Semantics

| Change Timing | Mechanism | Scope | Auditability |
|---------------|-----------|-------|-------------|
| Before `init()` | Environment variables + config file | Entire process | Logged at session start in `crp.session.init` event |
| At `init()` | `config` parameter | This session | Merged with higher-priority layers; logged in `crp.session.init` |
| During session | `configure(config)` | This session, all subsequent operations | `crp.session.configure` event with old/new values |

**Atomicity**: Configuration changes via `configure()` MUST be atomic — all fields in the provided config object are applied together, or none are. If validation fails for any field, the entire change MUST be rejected.

---

## 26. MULTI-PROVIDER LLM INTERFACE

CRP is LLM-agnostic. This section specifies how implementations connect to any LLM provider — cloud API, local inference server, or custom endpoint — with minimal configuration, automatic diagnostics, and zero lock-in.

**Design Principles:**

1. **Three fields to start**: `endpoint`, `api_key`, `model` — that is the minimum viable LLM configuration. For local models, even `api_key` and `model` are optional
2. **OpenAI Chat Completions as lingua franca**: The `POST /v1/chat/completions` interface (with `Authorization: Bearer <key>`, JSON body `{model, messages, ...}`) is the de facto industry standard. Most providers implement it. CRP treats it as the default wire format
3. **Auto-detection is the default path, not a fallback**: CRP MUST infer the provider, capabilities, required authentication, and correct request format from the endpoint URL alone whenever possible. Manual configuration exists as an override, not a requirement
4. **Many models need no API key**: Local inference servers (Ollama, LM Studio, LlamaFile, vLLM, llama.cpp server) and some cloud providers (Hugging Face free tier, Cloudflare Workers AI free tier) do not require authentication. CRP MUST NOT reject a configuration simply because `api_key` is absent — it MUST attempt the connection regardless and only report an auth error if the provider actually returns HTTP 401/403
5. **Honest diagnostics**: When something fails, tell the user exactly what is wrong and why — do not swallow errors behind generic "connection failed" messages
6. **Escape hatch**: Every auto-detected value MUST be overridable. Users who know what they are doing can specify everything manually

### 26.1 Provider Configuration Schema

The complete provider configuration. Only `endpoint` is REQUIRED; everything else has sensible defaults or is auto-detected.

```json
{
  "$id": "https://crp-protocol.org/schema/v2/llm-provider.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CRPLLMProvider",
  "description": "Configuration for connecting CRP to an LLM provider.",
  "type": "object",
  "required": ["endpoint"],
  "properties": {
    "endpoint": {
      "type": "string",
      "format": "uri",
      "description": "Base URL of the LLM API. Examples: 'https://api.openai.com/v1', 'http://localhost:11434/v1', 'https://api.anthropic.com/v1'. CRP appends the appropriate path (e.g., /chat/completions) automatically.",
      "examples": [
        "https://api.openai.com/v1",
        "http://localhost:11434/v1",
        "https://api.anthropic.com/v1",
        "https://generativelanguage.googleapis.com/v1beta",
        "http://localhost:8080/v1"
      ]
    },
    "api_key": {
      "type": ["string", "null"],
      "description": "API key or bearer token. Read from environment variable CRP_LLM_API_KEY if not set. For local models and providers that do not require authentication (Ollama, LM Studio, LlamaFile, vLLM, llama.cpp server, self-hosted endpoints), omit entirely or set to null. CRP MUST NOT require this field — it MUST attempt to connect without a key and only fail if the provider rejects the request with HTTP 401/403.",
      "default": null
    },
    "model": {
      "type": "string",
      "description": "Model identifier as the provider expects it. Examples: 'gpt-4o', 'claude-sonnet-4-20250514', 'llama3.1:70b', 'mistral-large-latest'. If omitted, CRP queries the provider's model list and selects the most capable available model.",
      "examples": ["gpt-4o", "claude-sonnet-4-20250514", "llama3.1:70b", "qwen2.5:32b"]
    },
    "provider": {
      "type": "string",
      "enum": ["openai", "anthropic", "azure", "google", "bedrock", "ollama", "vllm", "lmstudio", "llamafile", "groq", "together", "deepseek", "mistral", "openrouter", "custom"],
      "description": "Explicit provider hint. Auto-detected from endpoint URL when omitted. Use 'custom' for unlisted providers that implement the OpenAI-compatible API."
    },
    "api_version": {
      "type": "string",
      "description": "API version string. Required for Azure ('2024-06-01') and Google ('v1beta'). Auto-detected for other providers."
    },
    "headers": {
      "type": "object",
      "additionalProperties": { "type": "string" },
      "description": "Additional HTTP headers to include in every request. Merged with auto-generated headers (Authorization, Content-Type). User-specified headers take precedence.",
      "examples": [{ "X-Custom-Header": "value", "Anthropic-Version": "2024-01-01" }]
    },
    "request_format": {
      "type": "string",
      "enum": ["openai_chat", "anthropic_messages", "google_generate", "auto"],
      "default": "auto",
      "description": "Wire format for requests. 'auto' detects from provider. Most providers use 'openai_chat'. Only Anthropic and Google use their own formats natively."
    },
    "capabilities": {
      "type": "object",
      "description": "Override auto-detected model capabilities. CRP probes these on first use; manual override skips probing.",
      "properties": {
        "max_context_tokens": {
          "type": "integer",
          "minimum": 1,
          "description": "Maximum input context window in tokens."
        },
        "max_output_tokens": {
          "type": "integer",
          "minimum": 1,
          "description": "Maximum output tokens per request."
        },
        "supports_streaming": { "type": "boolean", "default": true },
        "supports_tool_calling": { "type": "boolean", "default": false },
        "supports_json_mode": { "type": "boolean", "default": false },
        "supports_system_message": { "type": "boolean", "default": true },
        "supports_vision": { "type": "boolean", "default": false },
        "tokenizer": {
          "type": "string",
          "description": "Tokenizer identifier for accurate token budgeting. Examples: 'cl100k_base' (GPT-4), 'o200k_base' (GPT-4o). Auto-detected from model name.",
          "examples": ["cl100k_base", "o200k_base"]
        }
      }
    },
    "retry": {
      "type": "object",
      "description": "Retry policy for transient failures.",
      "properties": {
        "max_retries": { "type": "integer", "minimum": 0, "default": 3 },
        "backoff_base_ms": { "type": "integer", "minimum": 100, "default": 1000 },
        "backoff_max_ms": { "type": "integer", "minimum": 1000, "default": 60000 },
        "retryable_status_codes": {
          "type": "array",
          "items": { "type": "integer" },
          "default": [429, 500, 502, 503, 504],
          "description": "HTTP status codes that trigger a retry."
        }
      }
    },
    "timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "default": 120000,
      "description": "Per-request timeout in milliseconds. Streaming requests use this as the timeout for the first chunk; subsequent chunks use timeout_ms / 10."
    },
    "tls": {
      "type": "object",
      "description": "TLS configuration for custom certificate authorities or mutual TLS.",
      "properties": {
        "ca_cert_path": { "type": "string", "description": "Path to CA certificate bundle." },
        "client_cert_path": { "type": "string" },
        "client_key_path": { "type": "string" },
        "verify": { "type": "boolean", "default": true }
      }
    }
  }
}
```

**Minimal usage examples** (these three snippets are all valid CRP provider configurations):

```json
{ "endpoint": "https://api.openai.com/v1", "api_key": "sk-...", "model": "gpt-4o" }
```

```json
{ "endpoint": "http://localhost:11434/v1" }
```

```json
{ "endpoint": "https://api.anthropic.com/v1", "api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514" }
```

```json
{ "endpoint": "http://localhost:8080/v1", "model": "my-local-model" }
```

Note: The second and fourth examples have **no `api_key`** — this is valid and expected for local inference servers.

### 26.2 Provider Auto-Detection

When `provider` is omitted, CRP MUST infer it from the `endpoint` URL using the following deterministic rules, evaluated in order. Auto-detection is the **primary** path — not a convenience feature. The goal is that a user should be able to point CRP at any well-known endpoint and have everything work without specifying `provider`, `request_format`, or authentication requirements.

**Authentication auto-detection**: When a provider is auto-detected, CRP also infers whether authentication is required:

| Detected Provider | API Key Required? | Auth Header Format |
|---|---|---|
| `openai` | Yes | `Authorization: Bearer {api_key}` |
| `anthropic` | Yes | `x-api-key: {api_key}` |
| `azure` | Yes | `api-key: {api_key}` (header) or `?api-key=` (query) |
| `google` | Yes | `Authorization: Bearer {api_key}` (or ADC) |
| `bedrock` | Yes (AWS Sig v4) | AWS credential chain |
| `ollama` | **No** | No auth header sent |
| `lmstudio` | **No** | No auth header sent |
| `llamafile` | **No** | No auth header sent |
| `vllm` | **No** (unless configured) | No auth header sent by default |
| `groq` | Yes | `Authorization: Bearer {api_key}` |
| `together` | Yes | `Authorization: Bearer {api_key}` |
| `deepseek` | Yes | `Authorization: Bearer {api_key}` |
| `mistral` | Yes | `Authorization: Bearer {api_key}` |
| `openrouter` | Yes | `Authorization: Bearer {api_key}` |
| `custom` | **Try without, then with** | If `api_key` is provided, send it; if not, attempt unauthenticated |

**Endpoint pattern matching** (evaluated in order):

| Endpoint Pattern | Detected Provider | Default `request_format` |
|---|---|---|
| `*.openai.com*` | `openai` | `openai_chat` |
| `*.anthropic.com*` | `anthropic` | `anthropic_messages` |
| `*.openai.azure.com*` or `*.cognitiveservices.azure.com*` | `azure` | `openai_chat` |
| `*.googleapis.com*` or `*.aiplatform.googleapis.com*` | `google` | `google_generate` |
| `*.amazonaws.com*/model/*` | `bedrock` | `openai_chat` |
| Host is `localhost` or `127.0.0.1` or `0.0.0.0`, port `11434` | `ollama` | `openai_chat` |
| Host is `localhost` or `127.0.0.1` or `0.0.0.0`, port `1234` | `lmstudio` | `openai_chat` |
| Host is `localhost` or `127.0.0.1` or `0.0.0.0`, port `8080` | `llamafile` | `openai_chat` |
| Host is `localhost` or `127.0.0.1` or `0.0.0.0`, port `8000` | `vllm` | `openai_chat` |
| `*.groq.com*` | `groq` | `openai_chat` |
| `*.together.xyz*` or `*.together.ai*` | `together` | `openai_chat` |
| `*.deepseek.com*` | `deepseek` | `openai_chat` |
| `*.mistral.ai*` | `mistral` | `openai_chat` |
| `*.openrouter.ai*` | `openrouter` | `openai_chat` |
| None of the above | `custom` | `openai_chat` |

**Rationale for `openai_chat` default**: The OpenAI Chat Completions wire format (`POST /chat/completions` with `{model, messages}`) has been adopted by the overwhelming majority of inference providers (Ollama, vLLM, LM Studio, LlamaFile, Together AI, Groq, Deepseek, Mistral, and hundreds of others). Defaulting to it means most custom endpoints work with zero additional configuration.

### 26.3 Connection Diagnostics

When CRP cannot reach or successfully query the LLM, it MUST produce a `ProviderDiagnostic` — not a generic error, but a specific, actionable diagnosis.

**Diagnostic sequence** (executed in order, short-circuits on first confirmed cause):

```
FUNCTION diagnose_provider(config: LLMProvider) -> ProviderDiagnostic:
  // Step 1: Network reachability
  IF NOT tcp_connect(config.endpoint, timeout=5s) THEN
    RETURN ProviderDiagnostic {
      code: "UNREACHABLE",
      message: "Cannot establish TCP connection to {endpoint}",
      suggestion: "Check that the server is running and the URL is correct. For local models, ensure the inference server is started.",
      details: { endpoint: config.endpoint, timeout_ms: 5000 }
    }

  // Step 2: TLS handshake (if HTTPS)
  IF config.endpoint starts with "https" THEN
    result = tls_handshake(config.endpoint, config.tls)
    IF result.failed THEN
      RETURN ProviderDiagnostic {
        code: "TLS_FAILURE",
        message: "TLS handshake failed: {result.reason}",
        suggestion: "Check certificate validity. For self-signed certs, set tls.ca_cert_path or tls.verify=false (development only).",
        details: { tls_error: result.reason, cert_subject: result.cert_subject }
      }

  // Step 3: HTTP health check (adapt auth based on provider)
  // Note: For providers that don't require auth (ollama, lmstudio, llamafile, vllm),
  // CRP MUST NOT send an Authorization header unless the user explicitly provided an api_key.
  headers = build_auth_headers(config)  // empty for keyless providers
  response = http_get(config.endpoint + "/models", headers=headers, timeout=10s)
  IF response.status == 401 OR response.status == 403 THEN
    IF config.api_key IS NULL AND provider_requires_auth(config.provider) THEN
      RETURN ProviderDiagnostic {
        code: "AUTH_FAILED",
        message: "Provider '{config.provider}' requires an API key but none was provided",
        suggestion: "Set api_key in provider config or CRP_LLM_API_KEY environment variable. For {config.provider}: key format is '{key_format_hint(config.provider)}'.",
        details: { status: response.status, provider: config.provider, key_required: true }
      }
    ELSE
      RETURN ProviderDiagnostic {
        code: "AUTH_FAILED",
        message: "Authentication rejected (HTTP {response.status})",
        suggestion: "Verify api_key is correct. For OpenAI: starts with 'sk-'. For Anthropic: starts with 'sk-ant-'. Check CRP_LLM_API_KEY environment variable.",
        details: { status: response.status, provider: config.provider }
      }
  IF response.status == 404 THEN
    RETURN ProviderDiagnostic {
      code: "ENDPOINT_NOT_FOUND",
      message: "The endpoint does not have a /models route",
      suggestion: "The URL may need a version prefix (e.g., /v1). Try: {endpoint}/v1",
      details: { attempted_url: config.endpoint + "/models" }
    }

  // Step 4: Model availability
  IF config.model IS NOT NULL THEN
    models = parse_model_list(response.body)
    IF config.model NOT IN models THEN
      RETURN ProviderDiagnostic {
        code: "MODEL_NOT_FOUND",
        message: "Model '{config.model}' is not available on this provider",
        suggestion: "Available models: {first_10(models)}. Check spelling and access permissions.",
        details: { requested_model: config.model, available_models: models }
      }

  // Step 5: Completions endpoint test
  test_response = http_post(config.endpoint + "/chat/completions", {
    model: config.model OR first(models),
    messages: [{ role: "user", content: "Say 'ok'" }],
    max_tokens: 5
  }, timeout=30s)
  IF test_response.status != 200 THEN
    RETURN ProviderDiagnostic {
      code: "COMPLETION_FAILED",
      message: "Test completion returned HTTP {test_response.status}",
      suggestion: "The model may be loading (try again in 30s), or the request format may be incompatible. Try setting request_format explicitly.",
      details: { status: test_response.status, body: truncate(test_response.body, 500) }
    }

  // Step 6: Success — extract capabilities
  RETURN ProviderDiagnostic {
    code: "OK",
    message: "Provider connection verified",
    detected_provider: auto_detect(config.endpoint),
    detected_model: config.model OR first(models),
    detected_capabilities: probe_capabilities(config)
  }
```

The `ProviderDiagnostic` schema:

```json
{
  "$id": "https://crp-protocol.org/schema/v2/provider-diagnostic.json",
  "title": "ProviderDiagnostic",
  "type": "object",
  "required": ["code", "message"],
  "properties": {
    "code": {
      "type": "string",
      "enum": ["OK", "UNREACHABLE", "TLS_FAILURE", "AUTH_FAILED", "ENDPOINT_NOT_FOUND", "MODEL_NOT_FOUND", "COMPLETION_FAILED", "RATE_LIMITED", "INCOMPATIBLE_FORMAT", "TIMEOUT"]
    },
    "message": { "type": "string" },
    "suggestion": { "type": "string", "description": "Human-readable fix suggestion." },
    "details": { "type": "object", "description": "Structured diagnostic data." },
    "detected_provider": { "type": "string" },
    "detected_model": { "type": "string" },
    "detected_capabilities": { "$ref": "#/properties/capabilities" }
  }
}
```

Implementations MUST run the diagnostic sequence at `init()` time when a provider is configured. Implementations SHOULD expose a standalone `diagnose()` function that users can call to troubleshoot without starting a full session.

### 26.4 Capability Probing

CRP MUST determine the model's capabilities to correctly budget tokens, choose extraction strategies, and set review tiers (Section 14). Capabilities are resolved in priority order:

1. **User-specified** (`capabilities` in provider config) — highest priority, no probing
2. **Known model registry** — built-in table of well-known models and their capabilities
3. **Provider API** — querying the provider's model info endpoint (e.g., `GET /models/{model}`)
4. **Runtime probes** — sending test completions to empirically determine capabilities

**Known Model Registry** (reference subset — implementations SHOULD maintain a comprehensive, updatable registry):

| Model Pattern | Context | Max Output | Streaming | Tool Calling | JSON Mode | Tokenizer |
|---|---|---|---|---|---|---|
| `gpt-4o*` | 128,000 | 16,384 | ✓ | ✓ | ✓ | `o200k_base` |
| `gpt-4-turbo*` | 128,000 | 4,096 | ✓ | ✓ | ✓ | `cl100k_base` |
| `gpt-3.5-turbo*` | 16,385 | 4,096 | ✓ | ✓ | ✓ | `cl100k_base` |
| `claude-sonnet-4*`, `claude-opus-4*` | 200,000 | 16,384 | ✓ | ✓ | ✓ | — |
| `claude-3-haiku*` | 200,000 | 4,096 | ✓ | ✓ | ✓ | — |
| `llama3.1:*b` | 128,000 | 4,096 | ✓ | ✗ | ✗ | — |
| `llama3.1:70b*` | 128,000 | 4,096 | ✓ | ✓ | ✗ | — |
| `qwen2.5:*` | 128,000 | 8,192 | ✓ | ✓ | ✓ | — |
| `mistral-large*` | 128,000 | 8,192 | ✓ | ✓ | ✓ | — |
| `gemini-*-pro*` | 1,000,000 | 8,192 | ✓ | ✓ | ✓ | — |
| `deepseek-chat*` | 64,000 | 8,192 | ✓ | ✓ | ✓ | — |

**Runtime probe sequence** (when registry lookup fails):

```
FUNCTION probe_capabilities(config: LLMProvider) -> Capabilities:
  caps = default_capabilities()

  // Probe 1: streaming support
  TRY stream_request(config, "Say 'hello'", max_tokens=5, stream=true)
    caps.supports_streaming = true
  CATCH
    caps.supports_streaming = false

  // Probe 2: system message support
  TRY completion(config, system="Reply with 'yes'", user="Confirm", max_tokens=5)
    caps.supports_system_message = true
  CATCH
    caps.supports_system_message = false

  // Probe 3: JSON mode
  TRY completion(config, user="Return {\"ok\":true}", response_format={"type":"json_object"}, max_tokens=20)
    caps.supports_json_mode = true
  CATCH
    caps.supports_json_mode = false

  // Probe 4: context window (binary search via tokenizer)
  caps.max_context_tokens = binary_search_context_limit(config, lower=4096, upper=2000000)

  RETURN caps
```

Probe results MUST be cached for the session lifetime. Implementations SHOULD persist probe results in cold storage keyed by `(provider, model)` to avoid re-probing across sessions.

### 26.5 Request Format Adapters

CRP normalises all LLM interactions to a single internal representation and translates to the provider's wire format at the boundary. Implementations MUST support these three wire formats:

**Format 1: `openai_chat`** — The default. Used by OpenAI, Azure, Ollama, vLLM, LM Studio, Groq, Together AI, Deepseek, Mistral, OpenRouter, and most OpenAI-compatible servers.

```
POST {endpoint}/chat/completions
Authorization: Bearer {api_key}    // OMITTED for keyless providers (Ollama, LM Studio, etc.)
Content-Type: application/json

{
  "model": "{model}",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "..." }
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "stream": true
}
```

**Format 2: `anthropic_messages`** — Native Anthropic API.

```
POST {endpoint}/messages
x-api-key: {api_key}
anthropic-version: 2024-01-01
Content-Type: application/json

{
  "model": "{model}",
  "system": "...",
  "messages": [
    { "role": "user", "content": "..." }
  ],
  "max_tokens": 4096,
  "stream": true
}
```

**Format 3: `google_generate`** — Google Gemini / Vertex AI.

```
POST {endpoint}/models/{model}:streamGenerateContent?alt=sse
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "system_instruction": { "parts": [{ "text": "..." }] },
  "contents": [
    { "role": "user", "parts": [{ "text": "..." }] }
  ],
  "generationConfig": {
    "maxOutputTokens": 4096,
    "temperature": 0.7
  }
}
```

**Internal ↔ Wire translation** is performed by a `RequestAdapter` interface:

```
INTERFACE RequestAdapter:
  FUNCTION format_request(internal: CRPCompletionRequest) -> HTTPRequest
  FUNCTION parse_response(http_response: HTTPResponse) -> CRPCompletionResponse
  FUNCTION parse_stream_chunk(chunk: bytes) -> StreamDelta | null
```

Implementations wanting to add support for new wire formats (e.g., AWS Bedrock's native format, Cohere, etc.) implement this interface. The `custom` provider uses `openai_chat` by default but accepts a user-supplied adapter.

### 26.6 Fallback Chains

CRP SHOULD support provider fallback — if the primary provider fails, automatically route to a secondary. This is critical for production reliability.

```json
{
  "$id": "https://crp-protocol.org/schema/v2/llm-provider-chain.json",
  "title": "CRPProviderChain",
  "type": "object",
  "required": ["providers"],
  "properties": {
    "providers": {
      "type": "array",
      "items": { "$ref": "llm-provider.json" },
      "minItems": 1,
      "description": "Ordered list of providers. CRP tries the first, falls back to the next on failure."
    },
    "fallback_on": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["UNREACHABLE", "AUTH_FAILED", "RATE_LIMITED", "TIMEOUT", "COMPLETION_FAILED", "MODEL_NOT_FOUND"]
      },
      "default": ["UNREACHABLE", "RATE_LIMITED", "TIMEOUT"],
      "description": "Diagnostic codes that trigger fallback to the next provider."
    },
    "max_fallback_attempts": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "Maximum number of providers to try before giving up."
    }
  }
}
```

**Usage example** — a production chain with cloud primary, local fallback:

```json
{
  "providers": [
    { "endpoint": "https://api.openai.com/v1", "api_key": "sk-...", "model": "gpt-4o" },
    { "endpoint": "http://localhost:11434/v1", "model": "llama3.1:70b" }
  ],
  "fallback_on": ["UNREACHABLE", "RATE_LIMITED", "TIMEOUT"]
}
```

When fallback occurs, CRP MUST emit a `crp.provider.fallback` event (Section 24) with the diagnostic code and the identity of both the failed and the replacement provider.

### 26.7 Tokenizer Reconciliation

Accurate token budgeting (Section 6, Section 15) requires knowing the model's tokenizer. CRP handles this as follows:

1. **If `capabilities.tokenizer` is set** — use the specified tokenizer directly
2. **If the model is in the Known Model Registry** — use the registered tokenizer
3. **If the provider exposes a token-counting endpoint** (e.g., Anthropic's `/messages/count_tokens`) — use it
4. **Otherwise** — fall back to a conservative character-based estimator: `token_count ≈ character_count / 3.5`

The character-based fallback intentionally over-estimates (most tokenizers average ~4 characters/token) to prevent context overflow. Implementations SHOULD log a warning when falling back to the character estimator, advising the user to set `capabilities.tokenizer` for optimal performance.

**Tokenizer caching**: Tokenizer instances MUST be cached per model. Loading a tokenizer (e.g., `tiktoken` for OpenAI models) can take 100-500ms; this cost MUST NOT be paid per-request.

### 26.8 Environment Variable Mapping

Provider configuration integrates with the Configuration Hierarchy (Section 25). Environment variables for provider configuration use the `CRP_LLM_` prefix:

| Environment Variable | Maps To | Example |
|---|---|---|
| `CRP_LLM_ENDPOINT` | `endpoint` | `https://api.openai.com/v1` |
| `CRP_LLM_API_KEY` | `api_key` | `sk-...` |
| `CRP_LLM_MODEL` | `model` | `gpt-4o` |
| `CRP_LLM_PROVIDER` | `provider` | `openai` |
| `CRP_LLM_TIMEOUT_MS` | `timeout_ms` | `120000` |
| `CRP_LLM_MAX_RETRIES` | `retry.max_retries` | `3` |
| `CRP_LLM_MAX_CONTEXT` | `capabilities.max_context_tokens` | `128000` |
| `CRP_LLM_MAX_OUTPUT` | `capabilities.max_output_tokens` | `16384` |

**Priority**: `init()` parameters > environment variables > config file > protocol defaults (consistent with Section 25.1).

**Zero-config local models**: For Ollama and LM Studio running on default ports, CRP SHOULD work with zero configuration — auto-detect the local server, query available models, and pick the largest. The user just calls `crp.init()` and gets a working session.

---

## 27. DEPLOYMENT & OPERATIONS

> **Full deployment specification**: `09_DEPLOYMENT.md` — includes architectural rationale, resource requirements, startup/shutdown sequences, retry policies, health monitoring, container guidance, and MCP/gRPC/LSP comparison.

CRP is deployed as an **embedded library** — imported directly into the application process. This is the architecturally correct choice because CRP manages context **within** a single application's LLM workflow. There are no two separate systems to connect; adding a transport layer (stdio, HTTP, gRPC) would add complexity, latency, and failure modes for zero benefit.

### 27.1 Deployment Models

CRP supports three deployment models:

- **Model 1: Embedded Library** (RECOMMENDED) — `import crp; session = crp.init(...)`. Zero network overhead. Session state in-process. The primary and designed deployment mode.
- **Model 2: CLI Wrapper** — Stateful command-line tool for shell scripts and non-native environments. Session state persisted to disk. UNIX-composable.
- **Model 3: HTTP Sidecar** — Localhost REST API (`127.0.0.1:9470`) for polyglot environments. Single-process, NOT multi-tenant. An accommodation, not the designed model.

### 27.2 Resource Summary

| Configuration | RAM | Disk | Startup |
|---|---|---|---|
| Minimal (Stages 1-2) | ~50 MB | ~10 MB | < 100ms |
| Standard (Stages 1-4) | ~200 MB | ~150 MB | ~2s |
| Full (all stages) | ~500 MB | ~400 MB | ~5s |

Extraction stages 3-6 MUST be loaded lazily. `init()` completes in < 500ms with cloud LLM, < 3s with local model.

### 27.3 Retry & Timeout

LLM API retries use exponential backoff (`delay = min(base × 2^attempt, max) + jitter`). HTTP 429 retries up to 5× with `Retry-After`. Server errors retry 3×. Auth and request errors fail immediately. All timeouts configurable. All retries emit `crp.provider.retry` events. See `09_DEPLOYMENT.md` §7 for full tables.

### 27.4 Health Monitoring

Embedded library: `health(session)` returns status, provider diagnostic, fact count, uptime, loaded stages.
HTTP sidecar: `/health` (liveness), `/ready` (readiness), `/metrics` (Prometheus). See `09_DEPLOYMENT.md` §8.

---

## 28. PROTOCOL PUBLICATION & ADOPTION

This section specifies how CRP is published, how it gains visibility and credibility, and the path to industry recognition.

> **Monetization strategy** is documented separately in `08_MONETIZATION.md`. The protocol specification is free and open (CC BY-SA 4.0). Implementation code is licensed under Elastic License 2.0 (non-production use free; production use requires a commercial license). Monetization targets production deployment licensing, managed infrastructure, enterprise operations, courses, and domain specialization — never the specification itself.

### 28.1 GitHub Repository Structure

CRP MUST be published as a standalone, dedicated GitHub repository — separate from any specific implementation. The repository structure:

```
context-relay-protocol/
├── README.md                     # Protocol overview, quick start, badge wall
├── LICENSE.md                    # CC BY-SA 4.0 (spec) + Elastic License 2.0 (code)
├── CONTRIBUTING.md               # Contribution guidelines, CLA, review process
├── CODE_OF_CONDUCT.md            # Contributor Covenant
├── CHANGELOG.md                  # Per-version changes, RFC 2119 change impact
├── GOVERNANCE.md                 # Decision-making process, maintainer roles
│
├── specification/                # The normative specification
│   ├── 01_INTRODUCTION.md        # Axioms, design philosophy, scope
│   ├── 02_CORE_PROTOCOL.md       # Full protocol spec (this document)
│   ├── 03_CONTEXT_MANAGEMENT.md  # Context envelope, windowing, extraction
│   ├── 04_TOKEN_BUDGET.md        # Token economics, budget allocation
│   ├── 05_SYSTEM_INTEGRATION.md  # Cross-component integration table
│   ├── 06_IMPLEMENTATION_PLAN.md # Reference implementation structure
│   └── 07_SECURITY.md           # Security architecture deep-dive
│
├── schemas/                      # Machine-readable JSON Schema files
│   ├── task-intent.json
│   ├── quality-report.json
│   ├── session-status.json
│   ├── llm-provider.json
│   ├── provider-diagnostic.json
│   ├── provider-chain.json
│   ├── crp-event.json
│   ├── crp-config.json
│   └── persisted-state-header.json
│
├── examples/                     # Language-neutral usage examples
│   ├── quickstart.md             # 5-minute getting started
│   ├── local-model.md            # Zero-config Ollama/LM Studio
│   ├── multi-provider.md         # Fallback chains
│   ├── extraction-pipeline.md    # Custom extraction stages
│   └── session-resumption.md     # Cross-session knowledge
│
├── rfcs/                         # Protocol change proposals
│   ├── 0000-template.md          # RFC template
│   └── 0001-initial-release.md   # v2.0 rationale
│
├── media/                        # Diagrams, logos, presentation materials
│   ├── logo.png
│   ├── architecture-overview.svg
│   └── envelope-flow.svg
│
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug-report.yml
    │   ├── spec-clarification.yml
    │   └── feature-request.yml
    ├── PULL_REQUEST_TEMPLATE.md
    └── workflows/
        ├── validate-schemas.yml  # CI: validate JSON Schema files
        └── link-check.yml        # CI: check internal cross-references
```

**Key repository principles**:

- **Specification-only**: The spec repo contains ONLY the protocol specification, JSON schemas, and examples. SDK implementations live in separate repos (`crp-python`, `crp-typescript`, `crp-rust`)
- **Machine-readable schemas**: Every JSON Schema referenced in the spec is also available as a standalone `.json` file in `/schemas/` for direct consumption by implementations
- **RFC process**: All non-trivial changes to the specification go through the `/rfcs/` process. This creates an auditable history of design decisions
- **CI validation**: GitHub Actions validate that JSON Schema files parse correctly and that internal cross-references resolve

### 28.2 README Design

The README is the protocol's front door. It MUST contain:

1. **One-sentence description**: "CRP is an open protocol for structured context management across LLM invocations"
2. **Problem statement**: 3-4 sentences on why context management matters and what breaks without it
3. **Key differentiators** (bulleted, scannable):
   - Embedded library, not a server — zero deployment overhead
   - Works with any LLM provider — auto-detected, 3 fields to configure
   - Structured knowledge extraction — not just text chunking
   - Cross-session knowledge persistence — sessions build on each other
   - Honest quality guarantees — degradation model, not magic claims
4. **Quick start**: The absolute minimal code to get CRP working (3-5 lines)
5. **Comparison table**: CRP vs "no context management" vs LangChain vs MCP (different problems, not competitors)
6. **Badge wall**: License, CI, spec version, SDK versions, Discord member count
7. **Links**: Specification, SDKs, examples, community

### 28.3 Visibility & Accreditation Strategy

Getting a protocol adopted requires more than publishing code. CRP needs a multi-channel visibility strategy:

#### 28.3.1 Standards Track

| Action | Target | Purpose |
|---|---|---|
| **IETF Internet-Draft** | Submit as Informational RFC | Formal recognition in the internet standards ecosystem. CRP's JSON-RPC interop mapping (§6.10.9) and structured event format (§24.2) are candidates for standalone I-Ds |
| **W3C Community Group** | Create "Context Management for AI" CG | Broader standards discussion. W3C CGs are lightweight (no formal process) but carry credibility |
| **ISO/IEC JTC 1/SC 42** | Participate in AI standardization | SC 42 covers AI standards (ISO/IEC 42001 AI Management). CRP's observability and audit trail align with AI Act compliance — propose CRP as a reference architecture |
| **Linux Foundation / LF AI & Data** | Apply for project hosting | Technical neutrality and governance credibility. MCP went through LF — CRP should too |

#### 28.3.2 Academic Credibility

| Action | Purpose |
|---|---|
| **Publish a technical paper** (arXiv + peer-reviewed venue) | Document the formal properties (§8), degradation model (§7.6), extraction pipeline (§3.3), and CKF architecture (§3.7). Target venues: ACL, EMNLP, NeurIPS (Systems track), or USENIX |
| **Reproducible benchmarks** | Publish benchmark results (when SDK exists) as a companion dataset. Include extraction yield, degradation curves, quality tier boundaries |
| **Cite foundational work** | CRP builds on established research (Transformer attention ↔ gradient descent dual (Dai et al., 2023), RST discourse parsing, Leiden community detection). Properly citing this positions CRP as rigorous, not ad-hoc |
| **University partnerships** | Offer CRP as a research platform for context management, knowledge extraction, and LLM orchestration research |

#### 28.3.3 Developer Community

| Channel | Strategy |
|---|---|
| **Hacker News** | Launch post: "Show HN: CRP — An open protocol for structured LLM context management." Focus on the problem (context is broken), the differentiation (embedded library, structured extraction, honest degradation model), and the 5-line quickstart |
| **Reddit** (r/MachineLearning, r/LocalLLaMA, r/programming) | Technical deep-dives. r/LocalLLaMA audience is perfect for the zero-config local model story |
| **Twitter/X** | Thread format: "Why context management for LLMs is broken and how we're fixing it." Share architecture diagrams, benchmark results, comparison tables |
| **YouTube / Technical Talks** | 20-minute talk: "Beyond RAG: Structured Context Management with CRP." Submit to AI Engineer, PyCon, Strange Loop |
| **Discord / Slack Community** | Dedicated CRP Discord. Channels: #general, #spec-discussion, #sdk-python, #sdk-typescript, #sdk-rust, #showcase, #help |
| **Blog Series** | Progressive disclosure: (1) Why CRP exists, (2) CRP vs RAG, (3) The extraction pipeline, (4) CKF deep-dive, (5) Building with CRP |

#### 28.3.4 Industry Recognition

| Action | Purpose |
|---|---|
| **Integration with major LLM frameworks** | LangChain adapter, LlamaIndex adapter, Semantic Kernel adapter. Being listed in their docs is worth more than any marketing |
| **Editor/IDE plugins** | VS Code extension, JetBrains plugin that uses CRP under the hood. Developers experience CRP without knowing it |
| **Cloud provider marketplace listings** | AWS Marketplace, Azure Marketplace, GCP Marketplace for CKF-as-a-Service and enterprise integrations |
| **Case studies** | Document real-world usage: "How Company X processes 10M tokens/day with CRP." Concrete results > abstract claims |
| **Comparison with MCP** | Position clearly: "MCP connects LLMs to tools. CRP manages context across LLM invocations. They solve different problems and can be used together." Avoid adversarial positioning |

#### 28.3.5 Governance & Trust

| Element | Implementation |
|---|---|
| **Open governance model** | GOVERNANCE.md in the repo. Clear roles: Maintainers (merge authority), Committers (review authority), Contributors. Modeled after Apache Software Foundation governance |
| **Specification versioning** | Dated versions (like MCP: `2025-06-18`) with clear changelog. Breaking changes require RFC + 6-month deprecation notice |
| **Conformance test suite** | Published test suite that any implementation can run to verify conformance. "CRP Conformant" badge for passing implementations |
| **Interoperability events** | Annual "CRP Interop" event where SDK implementers test their implementations against each other using the conformance suite |
| **Security disclosure process** | SECURITY.md with responsible disclosure policy. Security@ email. CVE assignment for vulnerabilities in reference implementations |

### 28.4 Publication Timeline

| Phase | Timeframe | Deliverables |
|---|---|---|
| **Pre-announcement** | Now | Clean up spec, extract JSON schemas, prepare repo structure |
| **Soft launch** | Week 1-2 | Push to GitHub, publish README, invite 20-30 selected reviewers from AI/systems community |
| **Technical paper** | Week 3-6 | Submit arXiv preprint documenting formal properties and architecture |
| **Public announcement** | Week 6-8 | Hacker News, Reddit, Twitter. SDK alpha (Python) available |
| **Community building** | Month 2-4 | Discord, blog series, first external contributors, LF AI application |
| **Standards track** | Month 4-6 | IETF Internet-Draft, W3C CG formation |
| **SDK 1.0** | Month 6-9 | Python SDK stable, TypeScript SDK beta, conformance test suite |
| **Ecosystem growth** | Month 9-12+ | LangChain adapter, VS Code extension, first case studies |

### 28.5 Positioning Statement

**For developers building LLM-powered applications** who need reliable context management across multiple LLM invocations, **CRP (Context Relay Protocol)** is an open protocol that provides structured knowledge extraction, cross-session persistence, and honest quality guarantees. **Unlike** ad-hoc prompt chaining, proprietary context APIs, or vector-only RAG, CRP offers a **formally specified, LLM-agnostic, embedded-library protocol** with a graduated extraction pipeline, graph-structured knowledge fabric, and transparent degradation model — all deployable with zero infrastructure overhead.

---

## 29. GLOSSARY

| Term | Definition |
|------|-----------|
| **Task Window** | A single, isolated LLM invocation with dedicated context |
| **Context Envelope** | Maximally-saturated structured state transfer between windows |
| **Maximum Context Saturation** | The principle that envelopes fill ALL available space, not a budgeted slice |
| **TaskIntent** | Declarative, all-optional description of what the caller wants |
| **Warm State** | Session-scoped accumulated facts and decisions (Tier 2) |
| **Cold State** | Persistent cross-session knowledge (Tier 3) |
| **Window DAG** | Directed acyclic graph of windows linked by envelopes and fact provenance |
| **Orchestrator** | The non-LLM component that dispatches tasks, builds envelopes, and runs extraction |
| **Fact** | An atomic, self-contained piece of information extracted from window output |
| **Extraction Pipeline** | Graduated 6-stage pipeline (regex → statistical → GLiNER → UIE → discourse structure → LLM-assisted relational) that extracts facts and relationships from output |
| **Information Flow** | The rate of new facts per token — one of the signals in the multi-signal completion detection system (see Section 4.3) |
| **Saturation** | The ratio of used-to-available tokens in a window |
| **Continuation** | A follow-up window triggered at the physical output limit with an extraction-built envelope |
| **Fan-Out** | Parallel dispatch of independent task windows |
| **Gap Analysis** | Bidirectional comparison of task requirements vs. output fulfillment |
| **Model Ignorance** | The principle that the LLM does not know CRP exists |
| **Quality Gate** | Three-tier validation (structural, confidence, anomaly) between extraction and warm state |
| **Contradiction Detection** | Embedding similarity comparison to identify superseded facts |
| **Ingestion** | `crp.ingest()` — direct extraction of non-LLM data into warm state without a window |
| **Auto-Ingest** | Automatic chunking and extraction of oversized input when task_input exceeds context window |
| **Output Integrity** | The guarantee that `dispatch()` returns the complete, unmodified LLM output (per-window raw outputs preserved for audit) |
| **LLM Amplification** | The principle that CRP enhances the LLM's context, not replaces its reasoning |
| **Generation Reserve** | $G$ — the token space reserved for the LLM to write output within a window |
| **Physical Wall** | When `finish_reason == "length"` — the LLM hit the output token limit |
| **Echo Detection** | Identifying and removing repeated text between the tail of one window and the head of the next |
| **Structural State** | Detected document structure at the end of a window's output (current section, list position, open blocks) |
| **Style Anchor** | The last natural paragraph of output, included in continuation envelopes for voice/tone consistency |
| **Budget Cap** | Hard user-controlled limits on windows, input tokens, or output tokens per session |
| **Session Resumption** | Restoring warm state from Tier 3 to continue a session after interruption |
| **Cost Estimate** | Pre-flight projection of token usage, cost, and time for a planned session |
| **Fact Graph** | Directed graph of extracted facts connected by typed edges (condition, cause_effect, dependency, elaboration, sequence). Replaces flat fact lists for reasoning-dense content, enabling dependency-aware envelope packing |
| **FactEdge** | A typed, directed relationship between two facts in the fact graph (e.g., `fact_A --cause_effect--> fact_B`). Extracted by Stage 5 (discourse parsing) or Stage 6 (LLM-assisted) |
| **Content Complexity Detection** | Automatic classification of input/output text as ENTITY_RICH, REASONING_DENSE, or NARRATIVE to route through appropriate extraction and scoring strategies |
| **Discourse Structure Extraction** | Stage 5 of the extraction pipeline — identifies rhetorical relations (condition, cause-effect, contrast, elaboration) between text spans using RST-inspired parsing. CPU-only, ~150ms |
| **LLM-Assisted Relational Extraction** | Stage 6 of the extraction pipeline — optional, uses a small LLM to extract implicit logical relationships that pattern-based stages miss. Triggered only for high-complexity content with low Stage 5 edge yield |
| **Multi-Aspect Task Decomposition** | Phase 1 of envelope scoring — decomposes the task into semantic aspects (noun phrases, action verbs, implicit requirements) so facts need only match ONE aspect to score high |
| **Cross-Encoder Reranking** | Phase 3 of envelope scoring — re-scores top-200 bi-encoder candidates using a cross-encoder (ms-marco-MiniLM-L6-v2) that processes (task, fact) pairs with full attention for nuanced relevance |
| **ANN Index** | Approximate Nearest Neighbor index (HNSW) over fact embeddings for O(log N) retrieval. Constructed at ~50ms for 5K facts, queried at ~1ms |
| **Warm State Compaction** | Periodic maintenance of warm state when fact count exceeds threshold — archives superseded facts, clusters related facts hierarchically, summarizes clusters, rebuilds ANN index |
| **Voice Profile** | Stylistic fingerprint extracted from early generation output (sentence length distribution, vocabulary level, tone markers, formatting patterns). Injected into continuation envelopes to prevent style drift |
| **Progressive Document Map** | Running table-of-contents built incrementally from each window's structural elements (headings, sections, list structures). Injected into continuation envelopes so the LLM knows document position |
| **Re-Grounding Window** | Periodic re-extraction from accumulated output (not warm state) to realign the warm state with what was actually written. Corrects drift between intended and actual content |
| **Boundary Reconciliation** | Post-chunking pass that detects and resolves duplicate or complementary facts extracted independently from overlapping chunk regions |
| **Protected Span** | A contiguous region of text (code block, table, JSON object, numbered list) that the structure-aware chunker must never split |
| **Structural Flow** | Completion signal that counts new structural elements (headings, paragraphs, list items, table rows) per token — remains positive during conclusions and summaries even when fact flow is zero |
| **Vocabulary Novelty** | Completion signal measuring the ratio of new unique n-grams per token — distinguishes genuine paraphrasing/summarizing from degenerate repetition loops |
| **Incremental Extraction** | O(N) extraction strategy where each window's output is processed exactly once and appended to warm state, replacing the O(N²) approach of re-extracting all accumulated output |
| **Multi-Signal Completion Detection** | Replacement for single-signal information flow — combines Fact Flow, Structural Flow, Vocabulary Novelty, and Structural Completion Patterns with content-type adaptive weighting |
| **Degradation Model** | Honest characterization of quality loss at scale — input fidelity decreases with volume, output coherence decreases with chain length. See Section 7.6 |
| **Contextual Knowledge Fabric (CKF)** | CRP's standard knowledge layer. Combines graph-structured storage, multi-mode retrieval (graph walk, pattern query, semantic fallback, community summary), event-sourced fact history, and pub-sub event architecture. Ships with every conformant SDK. CKF IS the protocol's intelligence. See Section 3.8 |
| **FactEvent** | Immutable record of a fact lifecycle event (created, superseded, compacted, archived, restored). Recorded in the append-only event log. Enables temporal queries and state reconstruction |
| **Event Log** | Append-only log of all FactEvents. The authoritative record of how knowledge evolved across windows. Enables temporal queries ("what did we know at Window N?"), audit trails, and crash recovery via replay |
| **Temporal Query** | Querying the event log to reconstruct the fact graph as it existed at a specific point in time. Enables retroactive analysis when later windows reveal earlier conclusions were wrong |
| **Blackboard Architecture** | Control pattern where extraction stages (knowledge sources) react to warm state (blackboard) changes rather than executing in a fixed sequence. Enables cross-window-aware extraction. See Section 3.3 |
| **Content-Addressable Retrieval** | Retrieving facts by structured pattern matching on fact attributes (entity_type, relation_type, source_window, confidence) rather than embedding similarity alone. Inspired by tuple spaces (Gelernter, 1985). CKF Mode 2 |
| **Graph Walk Retrieval** | Traversing fact graph edges from seed facts to retrieve connected knowledge from cold storage, reconstructing subgraphs rather than isolated facts. CKF Mode 1 |
| **Pattern Query** | A structured query specifying fact attributes to match, optionally combined with a semantic filter. Used for content-addressable retrieval when the orchestrator knows what KIND of fact it needs |
| **Community Detection** | Partitioning the fact graph into topic clusters using the Leiden algorithm (Traag et al., 2019). Each community represents a coherent knowledge topic (e.g., "network topology", "vulnerability findings"). Generates community summaries for holistic retrieval |
| **Community Summary Retrieval** | CKF Mode 4 — retrieving compressed community summaries instead of individual facts for broad-scope tasks. Prevents envelope saturation with hundreds of individual facts when a bird's-eye view is more appropriate |
| **CQRS (Command Query Responsibility Segregation)** | Maintaining separate optimized data structures for the write path (extraction → warm state: event log + adjacency insert) and the read path (envelope construction ← warm state: ANN + graph + pattern query). Neither path blocks the other |
| **Pub-Sub Events** | Decoupled event architecture where warm state mutations publish events (fact_created, fact_superseded, edge_added, community_updated, anomaly_detected) and interested subsystems subscribe and react independently |
| **Context Enhancement** | The principle that CRP improves context quality for EVERY window, not just extends context length. Even short prompts benefit from CKF enrichment — cross-session knowledge, prior discoveries, and relationship context are injected into the envelope. CRP's dual promise: arbitrarily large capacity AND better context at every scale |
| **Chain Degradation Estimate** | $d_{\text{chain}}(n) = 1 - \prod_{i=1}^{n}(1 - d_i)$ — compound degradation formula tracking cumulative quality loss across continuation chains. Used to trigger dynamic re-grounding when $d_{\text{chain}}$ exceeds threshold (replacing fixed every-N-windows re-grounding) |
| **Adaptive top_k** | TCP/IP-inspired AIMD (Additive Increase, Multiplicative Decrease) strategy for dynamically adjusting the number of facts retrieved by semantic fallback. Increases top_k when retrieval is fast and relevant, decreases when overloaded or low-relevance |
| **Cross-Session Graph Persistence** | The guarantee that when facts are archived to Tier 3, their graph structure (edges, community memberships, community summaries) is preserved alongside the fact embeddings. Enables graph reconstruction on session resumption |
| **Benchmark Specification** | Standard test inputs with known content types, expected extraction yields, expected degradation curves, and community structure validation — used to empirically validate CRP's quality promises. See Section 9 |
| **Quality Tier** | Classification (S/A/B/C/D) of effective context quality at a given processing scale. Tier S = lossless (fits in one window), Tier D = synthesis mode (>1000 windows, hierarchical required). See Section 10 |
| **Effective Context** | The estimated number of genuinely useful context tokens available to the LLM after accounting for compound degradation. Formula: $C \times (1 - d_{\text{chain}}(n))$ for serial, $C \times (1 - d_{\text{chain}}(\lceil \log_k n \rceil))$ for hierarchical |
| **Hierarchical Processing** | Map-reduce-validate pattern for Tier C/D inputs. Chunks input into segments, processes segments in parallel, synthesizes results hierarchically — bounding degradation to $O(\log N)$ levels. See Section 11 |
| **Context Query Signals (CQS)** | Implicit patterns in LLM output (hedging language, placeholder references, repetitive facts) that the orchestrator detects to infer context hunger and trigger targeted CKF enrichment. See Section 12 |
| **Context Hunger** | The state where LLM output patterns indicate the model needs more context than the envelope provided — detected via CQS without violating Axiom 4 |
| **Cross-Window Consistency Validation (CWCV)** | Three-tier validation system (extraction-based, LLM-targeted binary, full LLM review) that detects and optionally corrects contradictions and inconsistencies across windows. Tier 1 always runs (zero LLM cost). See Section 13 |
| **Active Review Cycles** | Interaction patterns (planning windows, checkpoint reviews, self-assessment) that elevate the LLM from passive generator to collaborative partner. Model-capability-gated. See Section 14 |
| **Review Tier** | Classification of review capability: Tier 1 (extraction-only, any model), Tier 2 (binary LLM questions, 2B+), Tier 3 (full reasoning review, 7B+). Self-calibrating via probe |
| **Model Capability Assessment** | Orchestrator probes that test the model's ability to perform structured review tasks, determining the maximum review tier it can reliably execute. Cached per session |
| **Pre-Generation Planning Window** | A dedicated window dispatched before long chains where the LLM outlines the document structure, which the orchestrator uses to pre-stage CKF retrievals and track generation progress |
| **Checkpoint Review Window** | A periodic review window (every N windows) where the LLM reviews its own output-so-far for consistency and completeness. Only dispatched for Tier 3-capable models |
| **Mid-Generation Context Injection (MGCI)** | Enriching the current or next window's envelope with targeted CKF content in response to detected context hunger signals |
| **Scale-Aware Mode Selection** | Automatic configuration of all CRP subsystems (processing mode, CQS, validation tiers, review cycles, hierarchy) based on input scale and model capability. See Section 15 |
| **1B Horizon** | The demonstrated capability boundary: 1 billion tokens processed via 3-level hierarchy yields ~73% effective context (93K useful tokens at 128K window). A measurable, defensible claim |
| **Unbounded Capacity** | CRP's processing throughput has no fixed ceiling ($N \times C$), but effective context quality degrades with scale. CRP is honest about this degradation and provides mechanisms (hierarchy, validation, review) to bound it. Replaces the informal term "unlimited" |
| **Source Passage** | Original verbatim text chunk stored alongside extracted facts. Included in envelopes for high-relevance facts so the LLM reads actual text, not just compressed facts. Solves the "telephone game" (interpretation drift at scale). See Section 17 |
| **Source-Grounded Envelope** | An envelope that includes original source passages alongside extracted facts for the highest-relevance items. The LLM "flips back to page 3" instead of reading a note about page 3 |
| **LLM Synthesis** | The LLM's own curated understanding, evolved progressively across curation cycles. A first-class envelope section carrying the LLM's judgment about what matters most. See Section 18 |
| **LLM-Driven Context Curation** | Periodic dispatch of a curation window where the LLM decides what's most important to carry forward — its judgment augments the orchestrator's embedding-based scoring |
| **Progressive Understanding** | The pattern where each LLM synthesis cycle builds on the previous one, creating an evolving comprehension that accumulates across windows. A form of in-context learning without weight updates |
| **Orchestrated Reasoning Chain (ORC)** | Decomposition of complex reasoning into micro-steps, each executed in a separate window within the model's capability ceiling. The chain of windows produces reasoning that exceeds the model's native ability. See Section 19 |
| **In-Context Meta-Learning (ICML)** | Leveraging the dual form between Transformer attention and gradient descent (Dai et al., 2023) to structure envelopes as implicit learning signals — demonstration examples in the envelope teach the model HOW to reason |
| **Reasoning Template Library (RTL)** | CKF-resident collection of successful reasoning traces stored across sessions. Retrieved and adapted for similar future tasks, enabling progressive bootstrapping of reasoning capability |
| **Reasoning Scaffold** | Step-by-step reasoning template injected into the envelope for models below a capability threshold. Tells the model HOW to think about the task, adapted to its capability level |
| **Meta-Learning Config** | Session-level configuration for CRP Meta-Learning: ORC, ICML, RTL, scaffold level. Auto-calibrates to model capability |
| **KV Cache Persistence** | Tier 2 learning mechanism: saving the model's KV cache from critical windows and injecting it into subsequent windows to carry forward internal representations, not just text. Infrastructure-dependent |
| **Reasoning Trace** | A stored record of a successful reasoning chain — task type, micro-steps, system prompts, quality score — persisted in CKF for cross-session retrieval |
| **9 Permanent Value Propositions** | The nine reasons CRP is irreplaceable at any scale: context quality, task isolation, attention optimization, cost efficiency, cross-session knowledge, structured knowledge, multi-agent coordination, observability, and reasoning amplification. See Section 21 |
| **Reasoning Amplification** | The principle that CRP doesn't just extend context — it amplifies the model's reasoning capability through meta-learning scaffolds, orchestrated reasoning chains, and progressive understanding |
| **Interpretation Drift** | The gradual divergence between original content and the LLM's representation of it, caused by each window adding its own interpretive layer. Source-grounded envelopes mitigate this |
| **Session Binding** | Protocol-level authentication between the application and CRP instance. Uses HMAC-SHA256 with a shared secret to derive ephemeral session keys. Ensures only registered applications can invoke CRP operations. See Section 22.2 |
| **Binding Secret** | Shared secret between application and CRP, configured at deployment. Used to derive session keys. Auto-generated from OS keyring when not explicitly provided. Never stored in warm/cold state |
| **Protocol Binding Handshake** | The initialization sequence at `crp.init()` where application identity is verified and a session key is derived. Inspired by TLS 1.3 handshake. See Section 22.2.1 |
| **Fact Provenance** | Integrity record attached to every extracted fact: BLAKE3 content hash, source window, extraction stage, and HMAC chain signature. Enables tamper detection. See Section 22.4.1 |
| **Fact Integrity Chain** | DNSSEC-inspired chain where each fact's signature includes the hashes of parent facts it depends on. Verifiable back to the session root of trust (session_key). See Section 22.4.2 |
| **Ingest Quarantine** | Probationary period (default: 1 window) for facts entering via `crp.ingest()`. Quarantined facts receive a confidence penalty (×0.7) and cannot override extraction-derived facts. Anti-poisoning defense. See Section 22.4.4 |
| **Security Flags** | Per-dispatch report of security observations: injection pattern matches, Unicode normalizations, integrity violations. Included in QualityReport. Advisory, not blocking. See Section 22.3.2 |
| **Window Isolation** | The guarantee that no raw text from one window can reach another window as instructions. Extraction normalizes output into facts; facts are structured data, not executable text. See Section 22.5 |
| **RBAC (Role-Based Access Control)** | Three-role access model: OBSERVER (read-only), OPERATOR (dispatch + ingest), ADMIN (full control including export and reset). Assigned at session init. See Section 22.6 |
| **Rate Limiting** | Per-session throttle on dispatch frequency and ingest volume to prevent unbounded consumption (OWASP LLM10). Enforced even in zero-config mode. See Section 22.6.2 |
| **Embedding Salting** | XOR of a random 4-byte salt into stored embedding vectors before persistence. Prevents direct embedding comparison attacks by adversaries with storage access. Reversed on retrieval. See Section 22.7.2 |
| **State Encryption** | AES-256-GCM encryption of cold state, event log, and exported state at rest. Key derived from binding secret via HKDF-SHA256. Enabled by default. See Section 22.7.1 |
| **API Formalism** | The formal specification of CRP's API surface: JSON Schema type definitions, RFC 2119 operation contracts, error taxonomy, streaming protocol, async variant, stability tiers, versioning, and interoperability mappings. See Section 6.10 |
| **CRPError** | Base error type for all CRP operations. 13 error codes (1001-1031) mapped to gRPC/JSON-RPC equivalents. All errors carry structured `details` for diagnostics. See Section 6.10.4 |
| **StreamEvent** | Discriminated union for streaming dispatch events. 6 event types (token, extraction, continuation, window_complete, done, error). See Section 6.10.5 |
| **SessionHandle** | Return type from `init()` containing session metadata: session_id, protocol version, RBAC capabilities, session key, expiry. See Section 6.10.8 |
| **API Stability Tier** | Classification (Stable/Provisional/Experimental) of API surfaces with versioning guarantees. Stable APIs MUST NOT break within a major version. Provisional APIs require one-minor-version deprecation notice. See Section 6.10.7 |
| **State Schema Versioning** | SemVer-based versioning on all persisted CRP data structures. Ensures forward migration (same-major reads always succeed) and explicit migration steps for major version changes. See Section 6.10.10 |
| **Concurrency Model** | CRP's thread-safety guarantees: cross-session parallelism, intra-session serialization, lock ordering for deadlock prevention, per-component thread-safety classification. See Section 23 |
| **Session Lock** | Per-session write-lock (mutex) that serializes state-mutating operations (dispatch, ingest, configure) within a session. Read-only operations may run concurrently. See Section 23.2.1 |
| **Lock Ordering** | Fixed acquisition order (Cold Storage → Model Registry → Session) that prevents deadlocks across all CRP operations. See Section 23.3 |
| **Structured Event** | JSON-formatted event with common envelope (timestamp, event_type, session_id, severity, payload, trace/span IDs). The atomic unit of CRP observability. See Section 24.2 |
| **Audit Trail** | Three-source audit system combining fact event log, structured event log, and security event log. Sufficient to fully reconstruct any CRP session. See Section 24.6 |
| **Session Reconstruction** | Complete rebuild of a session from its audit trail: all events, all facts, all windows, timeline. Enables forensic analysis and compliance reporting. See Section 24.6.1 |
| **Audit Bundle** | Self-contained, verifiable export of a session's complete audit trail. Exportable as JSON, JSONL, or CSV. See Section 24.6.1 |
| **Configuration Hierarchy** | Five-layer configuration resolution: Protocol Defaults → Environment Variables → Config File → init() Parameters → configure() Calls. Higher layers override lower. See Section 25.1 |
| **Init-Only Configuration** | Configuration fields that MUST NOT be changed after `init()` (e.g., binding_secret, app_id, protocol version). Attempting runtime change MUST raise an error. See Section 25.3 |
| **Language Neutrality** | The principle that CRP is a language-neutral protocol. JSON Schema is the normative type definition format. Python code blocks are informative reference implementations. See Notation Conventions |
| **LLM Provider** | The external service or local server that CRP calls to perform LLM inference. Configured via endpoint URL, API key, and model name. See Section 26 |
| **Provider Auto-Detection** | Deterministic inference of the LLM provider type from the endpoint URL pattern. Eliminates manual configuration for known providers. See Section 26.2 |
| **Provider Diagnostic** | Structured diagnosis of LLM provider connectivity issues. 10 diagnostic codes (UNREACHABLE through TIMEOUT) with human-readable suggestions. See Section 26.3 |
| **Capability Probing** | Runtime discovery of an LLM model's capabilities (context window, streaming, tool calling, JSON mode) through test completions. Cached per session. See Section 26.4 |
| **Request Format Adapter** | Interface that translates CRP's internal completion representation to a provider's wire format (OpenAI Chat, Anthropic Messages, Google Generate). See Section 26.5 |
| **Fallback Chain** | Ordered list of LLM providers tried in sequence when the primary provider fails. Triggered by configurable diagnostic codes. See Section 26.6 |
| **Tokenizer Reconciliation** | Resolution of the correct tokenizer for accurate token budgeting: user-specified → known registry → provider API → character-based fallback. See Section 26.7 |
| **Embedded Library** | CRP's primary deployment model — imported as a library into the application process. No separate server, no network overhead for CRP operations. See 09_DEPLOYMENT.md §3.1 |
| **CLI Wrapper** | Alternative CRP deployment as a stateful command-line tool. Session state persisted to disk between invocations. See 09_DEPLOYMENT.md §3.2 |
| **HTTP Sidecar** | Alternative CRP deployment as a localhost HTTP service for polyglot environments. Binds to 127.0.0.1 only by default. See 09_DEPLOYMENT.md §3.3 |
| **Knowledge Backend Interface** | Abstract contract for CRP knowledge storage operations: store, retrieve, query, persist, restore, fact_count, health, temporal_query, graph_walk, community_summary, subscribe. CKF is the standard implementation shipping with every SDK. Alternative backends MAY be substituted. See Section 3.8 |
| **Managed CKF Infrastructure** | CKF running at organizational scale — federated across sessions, horizontally scaled, with high availability. The CKF code is free; managing it at enterprise scale is the service. See 08_MONETIZATION.md |
| **Extraction Plugin Marketplace** | Third-party marketplace for custom extraction stages, domain adapters, and knowledge connectors built on CRP's extensible pipeline. See 08_MONETIZATION.md |
| **Protocol Publication** | CRP's strategy for open publication, standards-track submission, academic credibility, and developer community building. See Section 28 |
