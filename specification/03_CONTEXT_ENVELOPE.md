<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 03 — The Context Envelope

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · [01 Research](01_RESEARCH_FOUNDATIONS.md) · [02 Core Protocol](02_CORE_PROTOCOL.md) · **03 Envelope** · [04 Generation](04_TOKEN_GENERATION_PROTOCOL.md) · [05 Integration](05_SYSTEM_WIDE_INTEGRATION.md) · [06 Implementation](06_IMPLEMENTATION_PLAN.md)

> Maximally-saturated, semantically-scored, adaptive state transfer between windows.

---

## 1. WHY THE ENVELOPE IS EVERYTHING

The context envelope is where CRP lives or dies. A bad envelope means the next window is blind. A good envelope means the next window is **omniscient** about everything relevant.

**The Old Way (Fixed Baton)**:
```
{
  "current_phase": "exploitation",
  "target": "192.168.1.100",
  "findings_summary": "Found 3 open ports",
  "last_tool": "nmap"
}
```
~100 tokens. 99.9% of the 128K window is wasted on the system prompt re-explaining context the system already knows.

**The CRP Way (Maximally-Saturated Envelope)**:
```
[GOAL] Penetration test of 192.168.1.100 — web application focus
[PHASE] Exploitation (3/8) — reconnaissance and enumeration complete
[BLOCKER] None
[CONSTRAINT] In-scope: 192.168.1.0/24. No DoS. No social engineering.

[DISCOVERIES]
- PORT 22/tcp: OpenSSH 8.9p1 Ubuntu — auth required, no known CVEs
- PORT 80/tcp: Apache 2.4.52 — serves WordPress 6.4.2
- PORT 443/tcp: Apache 2.4.52 — same WordPress, valid TLS
- PORT 3306/tcp: MySQL 8.0.35 — bound to localhost only
- WordPress plugins: Contact Form 7 (5.8.4), Yoast SEO (21.6), WooCommerce (8.4.0)
- WooCommerce 8.4.0 has CVE-2024-XXXXX (SQLi in order search, CVSS 8.1)
- WordPress xmlrpc.php enabled — brute-force vector
- /wp-admin/ login page accessible — no rate limiting detected
- robots.txt reveals /wp-content/uploads/ and /wp-json/ endpoints
- /wp-json/wp/v2/users/ exposes usernames: admin, editor, shopmanager

[DECISIONS]
- Exploit WooCommerce SQLi first (highest CVSS, direct database access)
- WordPress user enumeration provides targets for credential attacks if SQLi fails
- Skip SSH exploitation (no known vulns, auth required)

[ERROR_LOG]
- nikto scan timed out on port 443 (30s limit) — output partial, re-run may be needed

[TOOL_HISTORY]
- nmap -sV -sC 192.168.1.100 → 4 ports (22,80,443,3306)
- whatweb 192.168.1.100 → WordPress 6.4.2, Apache 2.4.52
- wpscan --url http://192.168.1.100 → 3 plugins, xmlrpc enabled, user enum
- nikto -h https://192.168.1.100 → PARTIAL (timeout)
- gobuster dir -u http://192.168.1.100 -w common.txt → 23 paths found
```

~600 tokens. Already 6× the naive baton. But the window is 128K — we have **100K+ tokens of envelope budget remaining**. This gets filled with the full tool outputs, CVE details, ATT&CK mappings — everything that fits. The next window doesn't need to re-discover ANYTHING.

---

## 2. ENVELOPE STRUCTURE

### 2.1 Sections

Every envelope contains these sections, in priority order:

```
SECTION 1:   CRITICAL STATE         (always present, 100-500 tokens)
SECTION 1.5: LLM SYNTHESIS          (present when curation has run — see 02_CORE §18)
SECTION 2:   TASK BRIEF             (always present, varies)
SECTION 3:   DISCOVERIES            (adaptive, semantically scored content)
SECTION 3.5: SOURCE PASSAGES        (adaptive, original text for high-relevance facts — see 02_CORE §17)
SECTION 3.6: CONTEXT SOURCES        (adaptive, provenance manifest for retrieved content — see §14)
SECTION 4:   DECISIONS & PLAN       (adaptive, reasoning trail)
SECTION 5:   ERROR LOG              (adaptive, what failed and why)
SECTION 6:   TOOL HISTORY           (adaptive, command summaries)
SECTION 7:   EXPANDED CONTEXT       (adaptive, fills remaining space)
SECTION 8:   CKF RETRIEVALS         (adaptive, pulled from knowledge fabric when relevant)
SECTION 9:   REASONING SCAFFOLD     (adaptive, present for weak models — see 02_CORE §19)
```

### 2.2 Section Formats

**CRITICAL STATE** — Fixed format, always first:
```
[GOAL] {one-line goal statement}
[PHASE] {current phase} ({N}/{total}) — {phase summary}
[BLOCKER] {blocker description or "None"}
[CONSTRAINT] {scope, rules, user directives}
[WINDOW] {DAG position} — {window index in chain}
```

**TASK BRIEF** — Derived from TaskIntent:
```
[TASK] {What the LLM should do in this window}
[OUTPUT_FORMAT] {Expected output structure, if specified in intent}
```

**DISCOVERIES** — Atomic facts, one per line, from extraction pipeline. When fact graph edges exist (from Stage 5/6 extraction), relationships between facts are serialized inline:
```
[DISCOVERIES]
- {fact 1}: {detail} — {source window/evidence}
- {fact 2}: {detail} — {source window/evidence}
  ↳ [DEPENDS ON fact 1] {relationship description}
- {fact 3}: {detail}
  ↳ [CAUSED BY fact 2] {relationship description}
...
```

**DECISIONS** — Reasoning trail:
```
[DECISIONS]
- {decision 1} — {justification}
- {decision 2} — {justification}
...
```

**TOOL HISTORY** — Compact execution log:
```
[TOOL_HISTORY]
- {tool_name} {key_params} → {one-line result summary} [{status}]
...
```

**EXPANDED CONTEXT** — Full-fidelity data from warm state:
```
[EXPANDED: {source_label}]
{raw or lightly-compressed content}
```

**CKF RETRIEVALS** — Knowledge pulled from the Contextual Knowledge Fabric (cold storage + graph + communities):
```
[KNOWLEDGE: {query}]
{retrieved content, relevance-ranked}
[KNOWLEDGE_GRAPH: {seed_fact}]
{graph-connected facts with relationship annotations}
[KNOWLEDGE_COMMUNITY: {community_name}]
{community summary for holistic context}
```

**LLM SYNTHESIS** — The LLM's own curated understanding, evolved progressively (see 02_CORE §18). Injected between CRITICAL STATE and TASK BRIEF for maximum attention:
```
[LLM_SYNTHESIS (Window {N}, evolution {M})]
CRITICAL FINDINGS:
1. {finding} — {evidence}
2. {finding} — {evidence}
KEY RELATIONSHIPS:
- {relationship 1}
- {relationship 2}
CURRENT ASSESSMENT:
{2-3 sentence synthesis of the overall picture}
GAPS:
- {information gap 1}
- {information gap 2}
```

**SOURCE PASSAGES** — Original verbatim text for high-relevance facts (see 02_CORE §17). Included inline with DISCOVERIES for top-scored facts:
```
[DISCOVERIES]
- {fact}: {detail} — Window {N}
  ↳ [SOURCE: Window {N}, tokens {start}-{end}]
    "{original text verbatim from that window's output...}"
- {fact}: {detail} — Window {M}
  (no source passage — below high-relevance threshold)
```

**REASONING SCAFFOLD** — Step-by-step reasoning template for weak models (see 02_CORE §19). Only present when model capability is below threshold:
```
[REASONING APPROACH]
Follow these steps:
Step 1: {focused micro-task}
Step 2: {focused micro-task}
Step 3: {focused micro-task}
Output your answer after completing all steps.

[SIMILAR SOLVED EXAMPLES]
Example 1: {task} → {approach} → {result}
Example 2: {task} → {approach} → {result}
```

---

## 3. ADAPTIVE SIZING

### 3.1 Maximum Context Saturation

For a window with physical context size $C$:

$$E_{\max} = C - S - T - G$$

Where:
- $C$ = total physical context window (e.g. 128,000 tokens)
- $S$ = system prompt tokens (measured, not budgeted)
- $T$ = task input tokens (measured, not budgeted)
- $G$ = generation reserve (the space reserved for the LLM to write output)

**Generation reserve ($G$)** is determined by:
1. User-specified `max_output_tokens` in TaskIntent → use that value
2. LLM provider's reported `max_output_tokens` → use that value
3. Default → `min(C // 4, 16384)` — ensures the model always has room to write

The envelope fills **everything that isn't system prompt, task input, or generation reserve.**

**Example for a 128K context window (G = 16,384):**

| Scenario | System | Task Input | Gen Reserve | **Envelope Budget** |
|----------|--------|-----------|-------------|---------------------|
| Tool analysis | 800 | 5,000 | 16,384 | **105,816** |
| Report writing | 1,000 | 2,000 | 16,384 | **108,616** |
| Planning | 1,200 | 3,000 | 16,384 | **107,416** |
| Memory compilation | 600 | 60,000 | 16,384 | **51,016** |
| Simple classification | 500 | 500 | 4,096 | **122,904** |

Even the smallest envelope budget (51K tokens for memory compilation with a huge task input) is still **massive** — ~38 pages of dense text.

**What if task input exceeds the available space?** If $S + T + G > C$ (the task input alone is too large for the context window), CRP's auto-ingest mechanism (02_CORE_PROTOCOL Section 4.6) automatically chunks the input, runs extraction on each chunk, stores the facts in warm state, and re-dispatches with a synthesized task that fits. This is how CRP handles input that is larger than the model's context window — transparently, with zero user configuration.

### 3.2 Semantic Scoring and Greedy Priority Packing

The envelope is constructed by **scoring all facts using multi-aspect semantic analysis and cross-encoder reranking**, then greedily packing from highest to lowest. See 02_CORE_PROTOCOL Section 3.2 for the complete algorithm.

```
FUNCTION pack_envelope(budget_tokens, warm_state, task_intent):
  envelope_parts = []
  remaining = budget_tokens
  
  # Phase 1: Critical state (mandatory)
  critical = format_critical_state(warm_state)
  envelope_parts.append(critical)
  remaining -= token_count(critical)
  
  # Phase 2: Task brief (mandatory)
  brief = format_task_brief(task_intent)
  envelope_parts.append(brief)
  remaining -= token_count(brief)
  
  # Phase 3: Multi-aspect task decomposition
  #   Decompose the task into semantic aspects (noun phrases, action verbs,
  #   implicit requirements). A fact only needs to match ONE aspect to score high.
  aspects = decompose_task_aspects(task_intent)
  aspect_embeddings = [embed(a) for a in aspects]
  
  # Phase 4: Bi-encoder fast scoring with ANN retrieval
  #   For >1000 facts: query ANN index for top candidates per aspect (O(log N))
  #   For <=1000 facts: brute-force cosine similarity (still fast)
  scored_items = []
  
  for fact in warm_state.active_facts():
    # Multi-aspect score: MAX similarity across all aspects
    sim = max(cosine_similarity(fact.embedding, ae) for ae in aspect_embeddings)
    
    # Dependency bonus: facts that are graph-connected to high-scoring facts
    # inherit relevance (a firewall rule may not match "SQL injection" directly
    # but is graph-connected to the database host fact)
    dep_bonus = fact_graph_dependency_bonus(fact, warm_state.fact_graph)
    
    recency = exp(-0.1 * fact.age_in_windows)
    novelty = 1.5 if fact.seen_count == 0 else (1.0 if fact.seen_count < 3 else 0.5)
    
    score = (sim + dep_bonus) * recency * novelty
    scored_items.append((score, fact))
  
  scored_items.sort(reverse=True, key=lambda x: x[0])
  
  # Phase 5: Cross-encoder reranking of top candidates
  #   Top-200 candidates are re-scored using cross-encoder (ms-marco-MiniLM-L6-v2)
  #   which processes (task, fact) pairs with full attention for nuanced relevance
  if len(scored_items) > 50:
    top_candidates = scored_items[:200]
    for i, (bi_score, fact) in enumerate(top_candidates):
      ce_score = cross_encoder_score(task_intent.task_input, fact.text)
      blended = 0.6 * ce_score + 0.4 * bi_score  # Cross-encoder weighted higher
      top_candidates[i] = (blended, fact)
    top_candidates.sort(reverse=True, key=lambda x: x[0])
    scored_items = top_candidates + scored_items[200:]
  
  # Phase 6: Dependency-aware graph packing
  #   When a fact is packed, also pull in graph-connected facts (up to 2 hops)
  #   that haven't been packed yet, giving them a relevance floor
  packed_fact_ids = set()
  for score, fact in scored_items:
    fact_text = format_fact(fact)
    fact_tokens = token_count(fact_text)
    if fact_tokens <= remaining:
      envelope_parts.append(fact_text)
      remaining -= fact_tokens
      packed_fact_ids.add(fact.id)
      
      # Pull in graph neighbors (dependency-aware packing)
      for neighbor in warm_state.fact_graph.neighbors(fact.id, max_hops=2):
        if neighbor.id not in packed_fact_ids:
          neighbor_text = format_fact(neighbor)
          neighbor_tokens = token_count(neighbor_text)
          if neighbor_tokens <= remaining:
            envelope_parts.append(neighbor_text)
            remaining -= neighbor_tokens
            packed_fact_ids.add(neighbor.id)
    elif remaining > 50:
      compressed = compress_fact(fact, remaining)
      if compressed:
        envelope_parts.append(compressed)
        remaining -= token_count(compressed)
  
  # Phase 7: If space remains, pull from CKF (Contextual Knowledge Fabric)
  #   Multi-mode retrieval: graph walk → pattern query → semantic fallback
  #   This is where cross-session knowledge and context enhancement happen —
  #   even short-input windows benefit from CKF enrichment.
  if remaining > 500:
    ckf_results = ckf_retrieve(
      query=warm_state.current_goal,
      budget_tokens=remaining,
      seed_facts=list(packed_fact_ids),  # Graph walk starts from already-packed facts
      task_aspects=task_aspects,          # Pattern query uses task noun phrases
      modes=["graph_walk", "pattern_query", "semantic_fallback", "community_summary"]
    )
    for result in ckf_results:
      result_text = format_ckf_result(result)
      result_tokens = token_count(result_text)
      if result_tokens <= remaining:
        envelope_parts.append(result_text)
        remaining -= result_tokens
  
  return "\n\n".join(envelope_parts)
```

### 3.3 Multi-Phase Semantic Relevance Scoring

**v1 used a hardcoded matrix** mapping fact categories × task types to static relevance scores (e.g., "open ports score 1.0 for tool selection, 0.8 for report section"). This approach:
- Required manual tuning for every task type
- Couldn't adapt to new domains or tasks
- Encoded assumptions about what's "relevant" into the protocol

**v2 uses a three-phase scoring pipeline:**

**Phase 1 — Multi-Aspect Task Decomposition**: Instead of a single task embedding, the task is decomposed into semantic aspects (noun phrases, action verbs, implicit requirements). A fact about "firewall rules on port 3306" scores low against a single embedding of "SQL injection analysis" but scores HIGH against the decomposed aspect "database connectivity" — because the fact only needs to be relevant to ONE aspect to score high.

**Phase 2 — Bi-Encoder Fast Scoring + ANN Retrieval**: Using `sentence-transformers/all-MiniLM-L6-v2` (80MB, ~5ms per embedding):

$$\text{aspect\_score}(fact, task) = \max_{a \in \text{aspects}} \cos(\text{embed}(fact), \text{embed}(a))$$

For sessions with >1000 facts, an HNSW approximate nearest neighbor index provides O(log N) retrieval instead of brute-force O(N) scanning. Facts also receive a **dependency bonus** from the fact graph — a fact graph-connected to a high-scoring fact inherits partial relevance.

**Phase 3 — Cross-Encoder Reranking**: The top-200 bi-encoder candidates are re-scored using `cross-encoder/ms-marco-MiniLM-L6-v2` (~80MB, ~500 pairs/sec on CPU), which processes each (task, fact) pair with **full cross-attention** — dramatically improving relevance precision for nuanced relationships that cosine similarity misses. The final score blends cross-encoder (0.6) and bi-encoder (0.4) scores.

**Cross-Encoder Result Caching**: The cross-encoder is the single most expensive per-window operation (~400ms). In continuation chains where facts accumulate gradually, the top-200 candidates are often 80-90% identical between consecutive windows. CRP caches cross-encoder results and skips re-scoring for unchanged (task, fact) pairs:

```python
@dataclass
class CrossEncoderCache:
    """Caches cross-encoder scores to avoid redundant 400ms reranking."""
    _cache: dict[tuple[str, str], float]  # (task_hash, fact_id) → score
    _fact_set_hash: str                    # Hash of active fact IDs
    _task_hash: str                        # Hash of current task intent
    hits: int = 0                          # Telemetry
    misses: int = 0
    
    def get_or_score(self, task_text, fact, cross_encoder):
        key = (hash(task_text), fact.id)
        if key in self._cache and not fact.recently_modified:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        score = cross_encoder.predict([(task_text, fact.text)])[0]
        self._cache[key] = score
        return score
    
    def invalidate_on(self, event):
        """Invalidate cache entries when warm state changes significantly."""
        if event == "compaction":
            self._cache.clear()  # Full reset after compaction
        elif event == "fact_superseded":
            # Remove only the affected fact's entries
            self._cache = {k: v for k, v in self._cache.items() 
                          if k[1] != event.fact_id}

CROSS_ENCODER_CACHE_RULES:
  Scope:           Per-session (reset on session start)
  Invalidation:    On compaction (full), on fact supersession (partial)
  Task change:     If task_intent changes significantly (cosine sim < 0.9), clear cache
  Continuation:    Continuation windows keep same task — cache persists
  Expected hit rate: 50-80% in continuation chains (saves 200-320ms per window)
  Memory cost:     ~50KB per 1000 cached scores (negligible)
  Pressure mode:   Under HIGH resource pressure, cross-encoder is disabled entirely
```

**Recency weight**: More recent facts score higher. Exponential decay:

$$w_{\text{recency}} = e^{-\lambda \cdot \text{age\_in\_windows}}$$

Where $\lambda$ = self-calibrated from the session (observed rate at which facts become irrelevant). Initial default: 0.1 (facts remain relevant for ~20 windows), adjusted as the session progresses.

**Novelty weight**: Facts not yet consumed by any window score 1.5×. Facts consumed once score 1.0×. Facts consumed 3+ times score 0.5× (the LLM has seen them enough).

### 3.4 Compression Strategies

When a high-priority fact doesn't fit at full fidelity:

1. **Truncation**: Keep the first N tokens. Best for tool output where important info is at the start.
2. **Summarization**: Replace verbose description with a one-line summary. Example: `nmap -sV 192.168.1.100 → 4 open ports: 22(ssh), 80(http), 443(https), 3306(mysql)`.
3. **Tabular compression**: Convert verbose records to table format. Cuts tokens by 2-5×.
4. **Reference replacement**: Replace with a pointer: `[See EXPANDED: nmap_full below]` and include full content in expanded section if space allows.

---

## 4. CONTINUATION ENVELOPES

### 4.1 Envelope-Based Continuation (Replaces Raw Text Overlap)

When generation hits the physical context window wall and continuation is needed, the continuation window receives an **envelope built from extraction** — not a raw copy of the last N tokens.

**The old way** (raw overlap):
```
Prior output:    ..."attacker can execute arbitrary SQL queries against the database."
                 ├── Copy last 1000-2000 tokens ──┤
Continuation:    [PRIOR_OUTPUT_TAIL] ...last 1000-2000 tokens...
                 [CONTINUE_FROM_HERE]
```

Problems: magic numbers for overlap size, no semantic understanding, token-expensive, no structural awareness.

**The CRP way** (extraction-built envelope):
```
Continuation envelope:
  [FACTS_ESTABLISHED]
  - WooCommerce 8.4.0 SQLi confirmed (CVE-2024-XXXXX, CVSS 8.1)
  - Blind SQLi in order search endpoint
  - sqlmap extracted: 3 databases, 47 tables
  - 12,543 customer records in wp_users
  
  [STRUCTURAL_STATE]
  - Writing section: "3.2 Vulnerability Analysis"
  - Current subsection: "3.2.1 SQL Injection — Impact"
  - List numbering: item 1 of 3 (Data Exfiltration) complete
  - Next expected: item 2 (Privilege Escalation)
  
  [TASK_GAP]
  - Still needed: Privilege escalation impact
  - Still needed: Lateral movement analysis
  - Still needed: Vulnerability summary table
  
  [STYLE_ANCHOR]
  "...the vulnerability allows an attacker to execute arbitrary SQL
   queries against the backend database. The impact includes:
   1. **Data Exfiltration**: The attacker can extract all customer
      records, including personal information and payment data."
```

**Advantages**:
- Semantically rich: the continuation window knows WHAT has been established, not just the last blob of text
- Structurally aware: knows where in the document/list/section we are
- Gap-driven: explicitly states what's still missing
- Token-efficient: extracted facts are denser than raw prose
- No magic numbers: no `min_overlap_tokens`, no `max_overlap_pct`

### 4.2 Continuation Envelope Construction

```
FUNCTION build_continuation_envelope(window_output, task_intent, warm_state):
  
  # 1. INCREMENTAL extraction: extract facts from THIS window's output only
  #    (not accumulated output — see 02_CORE_PROTOCOL Section 4.7)
  new_facts = graduated_extract(window_output, task_intent)
  warm_state.merge(new_facts)  # Append to warm state, deduplicate
  
  # 2. Analyze structural state from accumulated output
  structural = analyze_structure(warm_state.accumulated_output)
  # Returns: open brackets, list position, section headers, 
  # current section, markdown depth, code block state
  
  # 3. Gap analysis: what did the task ask for vs what has been produced?
  gap = gap_analysis(task_intent, warm_state.active_facts())
  
  # 4. Get the last natural paragraph (style anchor, NOT arbitrary N tokens)
  last_paragraph = extract_last_natural_paragraph(window_output)
  
  # 5. Voice profile and document map (for long-chain coherence)
  #    See 04_TOKEN_GENERATION_PROTOCOL Section 3.5
  voice = warm_state.voice_profile   # Extracted from first window
  doc_map = warm_state.document_map  # Incremental TOC
  
  # 6. Pack into envelope using multi-aspect scoring (Section 3.2)
  envelope = format_continuation_envelope(
    facts_established=warm_state.active_facts(),
    structural_state=structural,
    task_gap=gap.missing_items,
    style_anchor=last_paragraph,
    voice_profile=voice,
    document_map=doc_map,
    warm_state_critical=warm_state.get_critical_state()
  )
  
  return envelope
```

---

## 5. ENVELOPE SERIALIZATION FORMAT

### 5.1 Text Format (Default)

The default envelope format is **plain text with section markers**:
- **Human-readable** for debugging
- **Token-efficient** (no JSON overhead)
- **Universally understood** by all LLMs
- **Easy to parse** for the orchestrator

Section markers use `[BRACKETED_CAPS]` to be visually distinct and easily searchable.

### 5.2 Why Not JSON for Envelopes?

JSON envelopes waste tokens on structure. The same information in CRP text format uses ~30% fewer tokens AND is easier for the LLM to process because it matches natural language patterns.

JSON is used ONLY when the LLM's **output** needs to be structured (via grammar-constrained generation with user-supplied schemas). Never for input context.

### 5.3 Token Counting

Envelope construction MUST use actual tokenizer counts, not estimates:

- **Required**: Use the model's actual tokenizer (`tiktoken`, `sentencepiece`, `llama.cpp` tokenizer)
- **Acceptable**: Use a calibrated estimator measured for the specific model (typically 3.2-3.5 chars per token for English with byte-level BPE)
- **Prohibited**: Hardcoded `// 4` approximations

---

## 6. ENVELOPE INTEGRITY

### 6.1 Consistency Guarantees

The envelope MUST be consistent:
- **No contradictions**: Conflicting facts resolved before injection
- **No stale facts**: Superseded facts replaced, not appended alongside
- **No duplicates**: Each unique fact appears exactly once

### 6.2 Fact Lifecycle
 Every transition is recorded as a **FactEvent** in the append-only event log (see 02_CORE_PROTOCOL Section 3.3), enabling temporal queries and full lifecycle audit.
```
CREATED ──▶ ACTIVE ──▶ SUPERSEDED ──▶ ARCHIVED
   │            │            │              │
   │ Extracted  │ Included   │ Replaced by  │ Moved to
   │ from       │ in         │ newer fact   │ cold
   │ output     │ envelopes  │              │ storage
```

Facts are **never deleted** — they transition through lifecycle states. The envelope builder only includes ACTIVE facts. Superseded facts remain in Tier 2 for history; archived facts move to Tier 3 for cross-session persistence.

### 6.3 Provenance (DAG Tracking)

Each fact carries provenance metadata:
- `source_window_id`: Which window produced this fact
- `extraction_stage`: Which pipeline stage extracted it (regex/statistic
- **Cross-session continuity**: When facts are archived to Tier 3, their provenance and graph edges are preserved, enabling CKF graph walk retrieval in future sessions

### 6.4 Context Enhancement

The envelope provides **context enhancement** — not just context extension. This is a critical distinction:

- **Context extension** (what sliding windows do): carry more tokens from prior output into the next window
- **Context enhancement** (what CRP does): transform the LLM's context with semantically-scored, graph-structured, cross-session knowledge

Even a single-window task with a short prompt benefits from context enhancement. The orchestrator queries the CKF (Contextual Knowledge Fabric) for facts relevant to the current task and injects them into the envelope zone. A task like "analyze this scan output" receives not just the scan data (task zone) but also prior vulnerability findings, network topology facts, and related CVE knowledge from previous sessions — all automatically, with zero configuration.

This means CRP's value is not contingent on multi-window chains. The knowledge fabric enriches EVERY window, making the LLM's context **better** — more informed, more connected, more comprehensive — regardless of whether the task fits in one window or one hundred.al/GLiNER/UIE/discourse/LLM-relational)
- `consumed_by`: List of window IDs that included this fact in their envelope
- `graph_edges`: List of FactEdge connections to other facts (for stages 5-6 extractions)
- `created_at`: Timestamp
- `superseded_by`: ID of fact that replaces this one (if any)

This enables:
- **Debugging**: "Why did window 15 make that decision?" → trace facts back through the DAG
- **Rollback**: Invalidate a window's facts → rebuild downstream envelopes
- **Analysis**: Which extraction stage produces the most valuable facts?

---

## 7. PERFORMANCE CHARACTERISTICS

### 7.1 Construction Time

Envelope construction is **CPU-bound** (no LLM call required):
- Embedding computation: ~5ms per fact (batched: ~50ms for 100 facts, cached after first computation)
- Multi-aspect task decomposition: ~10ms (NLP noun phrase extraction)
- Bi-encoder scoring (brute-force): O(N × A) where N = facts, A = aspects
- ANN index query (>1000 facts): ~1ms per aspect, O(A × log N)
- Cross-encoder reranking (top-200): ~400ms on CPU (~500 pairs/sec with ms-marco-MiniLM-L6-v2)
- Dependency graph packing: O(E) where E = edges in subgraph
- Token counting: O(total envelope text length)

For a typical session with 500 warm state facts: **< 200ms on any modern CPU**. The cross-encoder reranking dominates at scale but runs only on the top-200 candidates, not all facts. For sessions with <50 facts, the cross-encoder pass is skipped entirely (bi-encoder scoring is sufficient).

For large sessions with 5000+ facts: **< 500ms** — the ANN index provides O(log N) candidate retrieval, avoiding brute-force scanning. See 02_CORE_PROTOCOL Section 3.6 for warm state compaction strategies that keep fact counts manageable.

### 7.2 Token Overhead

Envelope section markers and structure consume ~50-100 tokens of overhead. On a 128K window with 100K+ envelope budget, this is < 0.1%.

### 7.3 Memory Usage

Warm state stores facts as structured objects with cached embeddings:
- 500 facts × 200 bytes content × 384-dim embedding = ~1 MB
- Plus raw tool outputs (expanded context): 1-10 MB
- Total: < 20 MB for even the most complex sessions

---

## 8. CONTEXT QUERY SIGNALS (CQS) — Envelope-Side Integration

### 8.1 CQS Detection in Envelope Context

The CQS detector (defined in 02_CORE Section 12) provides real-time feedback to the envelope builder. When context hunger is detected during generation, the envelope builder responds by enriching the NEXT window's envelope with targeted content:

```
NORMAL ENVELOPE: [Priority 1: Critical State] + [Priority 2: Scored Facts] + [Priority 3: CKF]

CQS-ENRICHED:   [Priority 1: Critical State] + [CQS INJECTION: targeted facts for hungry topic]
                 + [Priority 2: Scored Facts (re-scored with CQS topic boost)] + [Priority 3: CKF]
```

### 8.2 CQS Injection Protocol

When `warm_state.pending_enrichment` contains CQS requests (set by the generation protocol), the envelope builder:

1. **Retrieves targeted facts** from CKF using the CQS topic as a focused query
2. **Injects them at Priority 1.5** — after critical state but before general scored facts
3. **Re-scores remaining facts** with a topic boost: facts semantically related to the CQS topic receive a 2× relevance multiplier
4. **Marks the CQS injection** in envelope metadata so downstream audit can track enrichment effectiveness

```python
FUNCTION apply_cqs_enrichment(envelope, pending_enrichments, ckf, warm_state):
  """Modify envelope to address detected context hunger."""
  
  for enrichment in pending_enrichments:
    # Retrieve targeted content from CKF
    targeted_facts = ckf.retrieve(
      query=enrichment.topic,
      modes=[GraphWalkRetrieval, SemanticFallbackRetrieval],
      budget_tokens=min(2000, envelope.remaining_budget // 3)  # Cap at 1/3 of remaining
    )
    
    # Inject at Priority 1.5
    envelope.inject_section(
      priority=1.5,
      header=f"[Relevant context: {enrichment.topic}]",
      facts=targeted_facts,
      metadata={"cqs_signal": enrichment.signal_type, "topic": enrichment.topic}
    )
    
    # Boost related facts in Priority 2 scoring
    envelope.apply_topic_boost(topic=enrichment.topic, multiplier=2.0)
  
  # Clear pending enrichments
  warm_state.pending_enrichment.clear()
  return envelope
```

### 8.3 CQS Effectiveness Tracking

The envelope builder tracks whether CQS enrichment actually helped:
- If the NEXT window's output no longer shows context hunger for that topic → CQS was effective
- If context hunger persists → the enrichment was insufficient; increase retrieval budget
- Tracked as a metric: `cqs_resolution_rate` — the fraction of CQS signals resolved by one enrichment cycle

---

## 9. MID-GENERATION CONTEXT INJECTION (MGCI)

### 9.1 The Problem

Standard envelope construction happens BEFORE the window starts generating. But context hunger is detected DURING generation. The response options are:
1. Enrich the NEXT window (low overhead, delayed response) — handled by Section 8
2. Re-dispatch the CURRENT window (higher overhead, immediate response)
3. **Mid-generation injection** — enrich the current generation without re-dispatch

### 9.2 MGCI Protocol

MGCI inserts additional context into the generation stream by modifying the envelope for the NEXT continuation chunk within the same window (only applicable when the model is generating in streaming mode and the output is long enough to trigger intra-window check-ins):

```python
FUNCTION mgci_check(generation_stream, warm_state, ckf, config):
  """Check for context hunger at mid-generation checkpoints.
  Called every config.mgci_check_interval tokens during streaming generation."""
  
  if not config.cqs_enabled:
    return None
  
  # Check for context hunger in the generation-so-far
  signals = detect_context_hunger(generation_stream, warm_state)
  
  if signals:
    max_strength = max(s.strength for s in signals)
    
    if max_strength >= 0.8 and len(generation_stream) < 500:
      # Strong signal early → re-dispatch is worth it
      return MGCIAction.REDISPATCH
    
    elif max_strength >= 0.5:
      # Moderate signal → enrich next window
      for signal in signals:
        warm_state.pending_enrichment.append(
          EnrichmentRequest(topic=signal.topic, signal_type=signal.signal_type)
        )
      return MGCIAction.ENRICH_NEXT
    
  return MGCIAction.CONTINUE
```

### 9.3 When MGCI Is Not Available

MGCI requires streaming generation mode — the orchestrator must be able to read partial output mid-generation. For batch APIs or non-streaming configurations, MGCI degrades to next-window enrichment (Section 8). This is noted in the quality report.

---

## 10. SCALE-AWARE ENVELOPE STRATEGY

### 10.1 Envelope Strategy by Quality Tier

The envelope construction strategy adapts based on the quality tier (02_CORE Section 10):

| Tier | Envelope Strategy | Key Adjustments |
|------|-------------------|-----------------|
| **S** | Standard Priority Stack | No special treatment — fits in one window |
| **A** | Standard + CKF enrichment | Light CKF retrieval for context enhancement |
| **B** | Standard + CQS + re-grounding facts | CQS active, re-grounding data injected into envelopes |
| **C** | Hierarchical segment envelopes | Each segment level gets its own envelope strategy; reduce-phase envelopes carry cross-segment synthesis |
| **D** | Multi-level hierarchical + validation facts | Validation results (CWCV) injected into final envelope; synthesis windows carry cross-level context |

### 10.2 Hierarchical Envelope Construction

For Tier C/D hierarchical processing, each level of the hierarchy has different envelope needs:

- **Map-phase envelopes**: Standard Priority Stack — each segment is processed independently
- **Reduce-phase envelopes**: Carry cross-segment synthesis from the level below, plus cross-segment pattern facts
- **Validate-phase envelopes**: Carry validation results (contradictions found, corrections needed)
- **Final-phase envelope**: Carries the fully synthesized context from all levels, plus validation notes

---

## 11. SOURCE-GROUNDED ENVELOPE CONSTRUCTION

### 11.1 Dual-Layer Envelope

The source-grounded envelope extends the standard priority stack with a second layer: alongside compressed facts (the standard DISCOVERIES section), high-relevance facts include their **original source passages** — verbatim text from the window that produced them.

This transforms the envelope from "notes about a book" to "highlighted passages from the book, with notes in the margin."

### 11.2 Construction Algorithm

```python
FUNCTION build_source_grounded_envelope(scored_facts, warm_state, budget_tokens, tier):
  """Build envelope with both compressed facts AND original source text."""
  
  # Determine source budget based on quality tier (see 02_CORE §17.5)
  source_ratio = {
    QualityTier.S: 0.0,   # No envelope needed
    QualityTier.A: 0.20,  # 20% for source passages
    QualityTier.B: 0.30,  # 30% for source passages
    QualityTier.C: 0.25,  # 25% (hierarchy provides structure)
    QualityTier.D: 0.20,  # 20% (synthesis-heavy)
  }[tier]
  
  fact_budget = int(budget_tokens * (1 - source_ratio))
  source_budget = int(budget_tokens * source_ratio)
  
  # Phase 1: Pack facts normally (compressed, scored)
  fact_section = pack_facts(scored_facts, fact_budget)
  
  # Phase 2: For top-scored facts, include source passages
  source_section = []
  remaining_source = source_budget
  
  for score, fact in scored_facts:
    if remaining_source <= 0 or score < HIGH_RELEVANCE_THRESHOLD:
      break
    
    passages = warm_state.get_source_passages(fact.id)
    for passage in passages:
      if passage.token_count <= remaining_source:
        source_section.append((fact, passage))
        remaining_source -= passage.token_count
  
  # Phase 3: Interleave sources with their facts in the DISCOVERIES section
  return interleave_facts_and_sources(fact_section, source_section)
```

### 11.3 When Source Grounding Activates

Source grounding is **always active** for Tiers A-D (any multi-window session). For Tier S (single window), the full input is already in context — no source grounding needed.

The source budget allocation is conservative: at most 20-30% of the envelope. The remaining 70-80% carries the standard compressed facts, ensuring breadth of coverage is not sacrificed for depth on a few items.

---

## 12. LLM SYNTHESIS ENVELOPE SECTION

### 12.1 Placement and Priority

The LLM synthesis (02_CORE §18) is injected at **Priority 1.5** — after CRITICAL STATE (most important for orientation) but before TASK BRIEF and DISCOVERIES. This placement ensures the LLM's own accumulated understanding is in the high-attention zone of the context window.

### 12.2 Size Management

The synthesis section is capped at **3% of the total envelope budget** (typically 3,000-4,000 tokens for a 128K window). If the synthesis exceeds this cap, it's truncated to the CRITICAL FINDINGS and CURRENT ASSESSMENT subsections (GAPS and RELATIONSHIPS are trimmed first).

### 12.3 Evolution Tracking

Each synthesis carries metadata about how many times it has evolved. This enables the orchestrator to detect synthesis staleness: if the same synthesis persists for 10+ windows without evolution, it may be outdated. The orchestrator schedules a curation cycle.

---

## 13. REASONING SCAFFOLD ENVELOPE SECTION

### 13.1 When Present

The reasoning scaffold section (02_CORE §19) is included ONLY when:
1. The model's assessed capability is below the threshold for the task's complexity
2. CRP Meta-Learning is enabled (`meta_learning_config.enabled = True`)
3. The task has been classified as requiring multi-step reasoning

For strong models (70B+), this section is NEVER present — it would waste tokens on scaffolding the model doesn't need.

### 13.2 Content Sources

The scaffold is assembled from:
1. **Reasoning Template Library (RTL)**: Matching reasoning traces from CKF, adapted to the current task
2. **Dynamic decomposition**: Orchestrator-generated step-by-step breakdown based on task analysis
3. **Few-shot examples**: 1-3 solved examples of similar reasoning tasks from CKF

### 13.3 Size Budget

| Model Capability | Scaffold Budget | Content |
|---|---|---|
| Tier 1 (0.5B-1B) | Up to 8% of envelope | Full step-by-step template + 2-3 examples |
| Tier 2 (2B-7B) | Up to 4% of envelope | Light guidance + 1-2 examples |
| Tier 3 (7B+) | 0% | No scaffold — model handles reasoning natively |

---

## 14. CONTEXT-SOURCE PROVENANCE *(new in CRP 2.1)*

### 14.1 Motivation

A production LLM request mixes input from many origins: the user's current turn, a system prompt, retrieved RAG chunks, tool-call results, MCP server responses, function-call outputs, agent memory, and the model's own parametric knowledge. Treating all of these as "just text" is the root cause of prompt injection, grounding failures, and audit gaps.

CRP 2.1 introduces **two-sided provenance**: every piece of context carries a declared source, and the full manifest of sources the application intended to expose can be cryptographically signed and verified.

This maps directly to ISO/IEC 42001 §4.1–4.2 (context of the organisation), EU AI Act Art. 10 (data governance), GDPR Art. 30 (records of processing), and NIST AI RMF MAP-4 (context mapping).

### 14.2 Source Kinds

Sixteen canonical `SourceKind` values are defined (see `crp.core.context_source.SourceKind`):

| Kind | Trust default | Typical origin |
|---|---|---|
| `USER_TURN` | UNTRUSTED | End-user input |
| `SYSTEM_PROMPT` | TRUSTED | Application-controlled system message |
| `DEVELOPER_PROMPT` | TRUSTED | Developer-level configuration prompt |
| `RAG_RETRIEVAL` | UNKNOWN | Generic retrieval-augmented generation |
| `VECTOR_DB` | UNKNOWN | Vector-store query result |
| `DATABASE` | UNKNOWN | Structured DB query result |
| `KNOWLEDGE_GRAPH` | UNKNOWN | Graph query result |
| `MCP_TOOL` | UNKNOWN | MCP server response |
| `FUNCTION_CALL` | UNKNOWN | Function/tool execution output |
| `WEB_SEARCH` | UNTRUSTED | Web search result |
| `FILE_UPLOAD` | UNKNOWN | User-uploaded document |
| `AGENT_MEMORY` | UNKNOWN | Multi-turn agent scratchpad |
| `CKF_RETRIEVAL` | TRUSTED | CRP Knowledge Fabric retrieval |
| `WARM_STORE` | TRUSTED | CRP warm-store replay |
| `PARAMETRIC` | UNKNOWN | Model parametric knowledge |
| `UNATTESTED` | UNTRUSTED | Source not declared by application |

### 14.3 ContextManifest (§7.14.3)

The application constructs a `ContextManifest` listing every `ContextSource` it intentionally exposes to the model in a given turn. The manifest is signed with HMAC-SHA256 using a per-session secret and a canonical JSON payload (sorted keys, no whitespace). Verification uses `hmac.compare_digest` for constant-time comparison.

The manifest supports:
- `sign(secret)` / `verify(secret)` — HMAC-SHA256 attestation
- `is_expired()` — TTL enforcement against replay
- `declared_kinds()` / `declared_source_ids()` / `find(source_id)` — lookup helpers
- `to_json()` / `from_json(text)` — safe serialisation for audit logs

Signature is automatically invalidated when `add()` is called on a signed manifest, preventing silent tampering.

### 14.4 Detective-Mode Source Detection

`detect_source_kind(content, role, default)` provides a best-effort classifier for legacy code paths that have not yet been refactored to declare sources explicitly. It uses eleven ordered regex patterns plus role-hint short-circuits (system / developer / tool / function roles map directly). The output is marked `SourceOrigin.HEURISTIC` — never `DECLARED` — so audit downstream consumers can distinguish attested from inferred provenance.

### 14.5 Attestation Mismatch Detection

`check_attestation(observed, manifest)` cross-checks a list of observed `ContextSource` entries against the signed manifest, returning `AttestationMismatch` records for each discrepancy. Four reason codes are emitted:

| Reason | Meaning |
|---|---|
| `no_manifest` | Non-benign source appeared without any manifest attached |
| `manifest_expired` | Manifest TTL elapsed before this source was observed |
| `unattested_kind` | Kind of observed source not declared in manifest |
| `unattested_source_id` | Source ID not declared even though the kind matches |

Each mismatch serialises via `to_audit_event()` into a dict suitable for SIEM ingestion, with category `"context_source_attestation"`.

### 14.6 Error Codes

Two protocol-level error codes are reserved:

| Code | Symbol | Meaning |
|---|---|---|
| 1040 | `CONTEXT_ATTESTATION_MISMATCH` | One or more observed sources failed manifest attestation |
| 1041 | `CONTEXT_MANIFEST_INVALID` | Manifest signature, expiry, or schema check failed |

### 14.7 Envelope Integration

The `CONTEXT_SOURCES` section (see §2.1) is reserved at Tier 3 priority. When populated, it renders a compact table of `source_id → kind → origin → trust → optional HMAC fingerprint` for all retrieval-class sources. Pure user/system turns are not rendered to save tokens — their provenance is carried by role alone.

Facts (see `crp.extraction.types.Fact`) gain an optional `source: ContextSource | None` field, propagating provenance from retrieval through extraction into the envelope and downstream reasoning traces.

### 14.8 Backward Compatibility

All additions are opt-in:

- `Fact.source` defaults to `None` — 2.0 Fact construction is unchanged
- Applications that do not build a manifest pay zero runtime cost
- `detect_source_kind` is invoked only when explicitly called
- The `CONTEXT_SOURCES` envelope section is omitted when empty

---

### 14.9 Enforcement Pipeline *(new in CRP 2.2, §7.14.4)*

CRP 2.1 defines the vocabulary. CRP 2.2 defines the single wire-side
choke-point through which every envelope assembly MUST flow when a
manifest is attached. The pipeline is implemented by
`crp.core.context_enforcer.ContextEnforcer.check()`:

```
observed sources + manifest
    ├─ manifest signature verify        (fails → CONTEXT_MANIFEST_INVALID)
    ├─ manifest expiry check            (fails → CONTEXT_MANIFEST_INVALID)
    ├─ attestation mismatch scan        (mismatches → audit events)
    ├─ injection-signal scan (trusted)  (hits       → audit events)
    └─ return EnforcementResult         (policy decides raise vs observe)
```

**Policies** (`EnforcementPolicy`):

| Policy    | Manifest invalid | Attestation mismatch | Injection signal |
|-----------|------------------|----------------------|------------------|
| `OBSERVE` | audit, continue  | audit, continue      | audit, continue  |
| `WARN`    | audit + WARN log | audit + WARN log     | audit + WARN log |
| `REJECT`  | raise `CRPError(CONTEXT_MANIFEST_INVALID)` | raise `CRPError(CONTEXT_ATTESTATION_MISMATCH)` | raise `CRPError(CONTEXT_ATTESTATION_MISMATCH)` |

**Wire integration.** `crp.core.dispatch_router.assemble_messages()` now
accepts optional `manifest`, `observed_sources`, and `enforcer` kwargs.
When present — or when a process-wide default enforcer is installed
via `set_default_enforcer()` — the pipeline runs **before** any message
is constructed. Applications that do not supply any of these arguments
retain CRP 2.1 behaviour exactly (zero cost, zero observable change).

### 14.10 Injection-Signal Detection *(§7.14.4)*

Trust labels are *declarative*: a developer can mark a `SYSTEM_PROMPT`
as `TRUSTED`, but if that prompt was templated from untrusted user
input, the label is a lie. CRP 2.2 closes this gap with a conservative,
high-precision content scanner that runs only over sources carrying
`trust_level == TRUSTED` and emits `CONTEXT_TRUST_VIOLATION` audit
events for hits.

**Patterns** (`crp.core.context_enforcer._INJECTION_PATTERNS`):

| ID                     | Severity | Shape |
|------------------------|----------|-------|
| `instruction_override` | high     | "ignore [all/any/previous/...] instructions\|rules\|prompts" |
| `role_jailbreak`       | high     | "you are now DAN\|unrestricted\|developer mode\|..." |
| `exfil_secret`         | high     | "reveal\|print\|output the system prompt\|api keys\|..." |
| `delimiter_forgery`    | medium   | `[END VERIFIED CONTEXT]`, `<|im_start|>`, `BEGIN SYSTEM` |
| `payload_url`          | medium   | `data:`, `javascript:`, `vbscript:`, `file:` URIs |
| `embedded_tool_call`   | medium   | `<tool_call>`, `<function_call>`, `exec('rm -rf')` |

Patterns are deliberately narrow to maintain high precision. False
negatives are acceptable; false positives are not. Additions require
an RFC.

### 14.11 Manifest Ledger *(new in CRP 2.2, §7.14.5)*

Cross-turn continuity was missing in 2.1. CRP 2.2 introduces the
manifest ledger — an append-only JSONL record of every manifest ever
attached to a session:

```
crp_sessions/<session_id>.manifest.jsonl
```

One JSON object per line; each line is a complete signed manifest plus
`session_id`, `turn`, and `recorded_at`. Tamper-evident via the HMAC
signature carried inside each record. Implemented by
`crp.core.manifest_ledger.ManifestLedger` with operations:

- `record(session_id, manifest, turn=None)` — append a new entry
- `load(session_id)` — rehydrate from disk into in-memory cache
- `latest(session_id)` / `history(session_id)` — current-turn and full history
- `find_by_source_id(source_id, session_id=None)` — lineage query
- `find_by_kind(kind, session_id=None)` — categorical query
- `verify_signatures(session_id, secret)` — integrity audit

Session IDs are sanitized to `[A-Za-z0-9_-]` before being used as
filenames; identifiers that sanitize to empty are rejected (prevents
directory traversal).

### 14.12 Key Management *(§7.14.5)*

Signing a manifest requires a secret. CRP 2.2 introduces the
`KeyProvider` abstraction so integrators can plug in their existing
secret-management infrastructure:

**`EnvVarKeyProvider`** — minimum viable provider. Reads HMAC secret
from an environment variable (default `CRP_MANIFEST_SECRET`),
auto-detects hex encoding for even-length `[0-9a-f]+` strings,
enforces ≥32-byte minimum (overridable with `allow_short=True` for
tests).

**`RotatingKeyProvider`** — in-process rotation ring. Maintains the
active key plus up to `max_retired` (default 3) retired keys so
manifests signed with the previous key continue to verify during a
grace window. `rotate(new_key)` promotes `new_key` to current and
demotes the previous key. `retire_all()` drops every retired key.
`verify(manifest)` tries candidates in order (current first).

Candidate iteration uses `hmac.compare_digest` for constant-time
comparison; the fail-through verification loop does not leak timing
information that would distinguish which key verified.

### 14.13 Auto-Stamping at Retrieval Sites

Two retrieval surfaces now stamp `ContextSource` provenance on facts
that arrive without an explicit source:

- **Warm store** (`crp.state.warm_store.get_active_facts_as_extraction`):
  every un-sourced fact gets
  `ContextSource(kind=WARM_STORE, origin=OBSERVED, trust_level=TRUSTED)`
  with `source_id="warm_store://fact/<id>"`.

- **CKF** (`crp.ckf.fabric.ContextKnowledgeFabric.retrieve`): every
  un-sourced merged fact gets
  `ContextSource(kind=CKF_RETRIEVAL, origin=OBSERVED, trust_level=TRUSTED)`
  with `source_id="ckf://fact/<id>"` and the retrieval `modes` / `score`
  in `metadata`.

This guarantees that every fact entering the envelope via a CRP-native
retrieval path is labelled — there are no silent "came from nowhere"
facts on the wire.

