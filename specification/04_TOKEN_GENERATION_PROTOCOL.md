<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 04 — Token Generation Protocol

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · [01 Research](01_RESEARCH_FOUNDATIONS.md) · [02 Core Protocol](02_CORE_PROTOCOL.md) · [03 Envelope](03_CONTEXT_ENVELOPE.md) · **04 Generation** · [05 Integration](05_SYSTEM_WIDE_INTEGRATION.md) · [06 Implementation](06_IMPLEMENTATION_PLAN.md)

> Unbounded, high-quality output via chained generation windows with extraction-built envelopes. Quality is tiered — see 02_CORE_PROTOCOL Section 10.

---

## 1. THE OUTPUT PROBLEM

LLMs have two separate limits:
1. **Context window** — how many tokens the model can process (input + output combined in most architectures)
2. **Max output tokens** — how many tokens the model can generate in a single call (set by the API, the inference engine, or a physical limit)
3. **Generation quality ceiling** — how many tokens the model can WRITE before quality degrades

For Youtu-LLM-2B (128K context):
- The context window is 128,000 tokens (input + output combined)
- Max output tokens depends on configuration (e.g., 4,096 default, configurable up to ~16K)
- But generating >4K-8K tokens in a single call produces **severe quality degradation** (repetition, loss of coherence, format drift)

For API models (Claude, GPT-4):
- Context window: 128K-200K tokens
- Max output tokens: typically 4K-32K per call (model-dependent, API-enforced)
- Quality degrades less severely but output length is hard-capped by the API

**The core problem**: Even a model with 1M context can only OUTPUT a limited number of tokens per call. A 200-page textbook (~80K tokens) CANNOT be produced in a single call regardless of context window size.

**CRP's answer: chained generation windows with extraction-built continuation envelopes.**

---

## 2. CHAINED GENERATION

### 2.1 Core Concept

Instead of generating one massive output, generate multiple high-quality segments across dedicated windows:

```
Window 1: Generate freely → model stops naturally or hits physical wall
Window 2: Fresh window + extraction envelope → continues from where Window 1 left off
Window 3: Fresh window + extraction envelope → continues from where Window 2 left off
...
Window N: Generation + extraction → information flow reaches zero → done
```

Each window operates at PEAK quality because:
- Fresh KV cache — no accumulated generation artifacts
- The system prompt is re-injected — instructions are in the attention sink position
- The extraction-built envelope carries the full semantic state — no context loss
- Information flow measurement detects natural completion

### 2.2 Generation Quality Model

Token quality in a single generation window follows approximately:

$$Q(t) = Q_0 \cdot e^{-\alpha t}$$

Where:
- $Q_0$ = initial quality (peak)
- $t$ = tokens generated so far in this window
- $\alpha$ = decay rate (model-dependent, self-calibrated from observed behavior)

This is a **simplified model** for understanding WHY chained generation works. The actual quality monitoring uses the more detailed composite score $Q(t, w)$ defined in Section 8.2, which measures information density, coherence, and cross-window novelty independently.

Chained generation resets the curve at each window:

$$Q_{\text{chained}}(t) = Q_0 \cdot e^{-\alpha (t \bmod W)}$$

Where $W$ = tokens per window. The minimum quality across the entire output is:

$$Q_{\min} = Q_0 \cdot e^{-\alpha W}$$

**Key difference from v1**: There is no hardcoded "recommended window gen budget" table (2K for 2B, 4K for 7B, etc.). The protocol observes the quality decay profile for the specific model+hardware+quantization and adapts. The model generates freely until it stops naturally or hits the physical wall. The quality monitoring system (Section 8) detects degradation in real time.

---

## 3. CONTINUATION PROTOCOL

### 3.1 Continuation Trigger: Physical Wall Only

Continuation triggers when — and **only when** — the LLM's generation reaches the **physical output limit** AND:
1. The task is not yet fulfilled (gap analysis shows missing items)
2. Information flow is still positive (the model was still producing valuable content)

**How the physical wall is detected:**
- **API providers**: The response includes `finish_reason`. If `finish_reason == "length"`, the model was cut off by the output token limit. If `finish_reason == "stop"`, the model finished naturally (EOS token).
- **Local inference** (llama.cpp, vLLM, etc.): The server returns a `stop_reason` or equivalent field. `"limit"` or `"length"` = wall hit. `"stop"` or `"eos"` = natural completion.
- **Fallback**: If the provider doesn't report `finish_reason`, count output tokens. If `output_tokens >= max_output_tokens - 1`, treat as wall hit.

**Continuation does NOT trigger at**:
- An arbitrary token budget (no `min_generation_budget`, no `max_generation_budget`)
- A configured ceiling
- A percentage of context window
- A "recommended window size" based on model class

**Special case — premature EOS with gap non-zero**: If the model naturally emits EOS (`finish_reason == "stop"`) but gap analysis shows the task isn't fulfilled, the orchestrator redispatches with the gap explicitly stated in the envelope. This is NOT a continuation (no stitching) — it's a new targeted dispatch for the missing items.

If the model naturally produces EOS and the task is fulfilled, generation is done — even if it only generated 200 tokens. If the model fills the output limit and the task isn't fulfilled, continuation is triggered.

### 3.2 Extraction-Built Continuation Envelope

When continuation triggers, the continuation window receives an **envelope built from the extraction pipeline** — not a raw copy of the last N tokens.

```
FUNCTION build_continuation_envelope(output_so_far, task_intent):
  
  # 1. Run graduated extraction on all output so far
  facts = graduated_extract(output_so_far, task_intent)
  
  # 2. Analyze structural state
  structural = analyze_structure(output_so_far)
  
  # 3. Gap analysis: what's been asked for vs what's been produced?
  gap = gap_analysis(task_intent, facts)
  
  # 4. Get last natural paragraph (style anchor)
  style_anchor = extract_last_natural_paragraph(output_so_far)
  
  # 5. Pack into continuation envelope
  return format_continuation_envelope(
    facts_established=facts,
    structural_state=structural,
    missing_items=gap.missing_items,
    style_anchor=style_anchor
  )
```

**What's in the continuation envelope:**
1. **Extracted facts from all prior windows** — structured, deduplicated, prioritized
2. **Structural state** — open brackets, list position, section headers, current section
3. **Task gap** — explicitly states what's still missing
4. **Style anchor** — the last natural paragraph (not last N tokens)

**What's NOT in the continuation envelope:**
- Raw text overlap with magic numbers (`min_overlap_tokens: 100`, `max_overlap_pct: 0.15`)
- Arbitrary token counts of prior output
- Hardcoded overlap sizing per task type

### 3.3 Completion Detection via Information Flow

The system detects natural completion via **marginal information flow** — not hardcoded signal weights or threshold scores:

$$\text{InfoFlow}(t) = \frac{\Delta \text{facts}}{\Delta \text{tokens}}$$

Measured as a rolling window: how many NEW facts did the extraction pipeline find in the last chunk of tokens?

**Natural completion** is detected when:
1. Information flow reaches zero (no new facts being produced)
2. AND a natural boundary is reached (EOS token, structural closure, paragraph break)
3. AND task fulfillment gap is zero (bidirectional extraction confirms requirements met)

**Updated in v2.0**: Completion detection now uses **multi-signal analysis** (see 02_CORE_PROTOCOL Section 4.3). Fact flow alone is insufficient for discursive content (conclusions, creative writing, rhetorical argument) where the model produces high-value text with zero new extractable facts. The multi-signal approach combines fact flow, structural flow, vocabulary novelty, and structural completion patterns — weighted by detected content type.

### 3.4 Stitch Strategy

Outputs from multiple windows are stitched seamlessly. The full algorithm is defined in 02_CORE_PROTOCOL Section 4.8, but the core concept:

```
FUNCTION stitch_outputs(prior_output, continuation_output):
  
  # 1. Echo detection: longest common substring between tail of prior and head of continuation
  #    LLMs naturally re-generate text from the style anchor in the continuation envelope
  tail = prior_output[-2000:]
  head = continuation_output[:2000]
  echo_length = longest_common_substring_at_boundary(tail, head)
  #   Match must be >= 20 characters to avoid false positives on common phrases
  
  # 2. Remove echo from continuation
  clean_continuation = continuation_output[echo_length:]
  
  # 3. CONTENT-TYPE AWARE BOUNDARY DETECTION
  #    Different content types need different stitch strategies:
  content_type = detect_stitch_content_type(prior_output, continuation_output)
  stitch_point = find_content_aware_boundary(prior_output, content_type)
  
  # 4. Preserve any trimmed trailing content for audit (never silently discard)
  trimmed = prior_output[stitch_point:]
  if trimmed:
    warm_state.store_trimmed_fragment(window_id, trimmed)
  
  # 5. Join
  stitched = prior_output[:stitch_point] + clean_continuation
  
  # 6. POST-STITCH VALIDATION
  validate_stitch_integrity(stitched, stitch_point, content_type)
  
  return stitched


FUNCTION find_content_aware_boundary(output, content_type):
  """Content-type-specific boundary detection."""
  
  if content_type == "prose":
    # Standard: search backward for paragraph break, sentence end, line break
    return find_clean_boundary_prose(output)
    #   Preferred: paragraph break (\n\n)
    #   Good: sentence end (. ! ? followed by whitespace)
    #   Acceptable: line break (\n)
    #   Fallback: if no boundary in last 500 chars, use full output (no trim)
  
  elif content_type == "code":
    # Code-aware: never split mid-function, mid-block, or mid-expression
    return find_clean_boundary_code(output)
    #   Preferred: between function/class definitions
    #   Good: after a complete statement (line ending with ; or :)
    #   Acceptable: after a closing brace/bracket that reduces nesting to 0
    #   Forbidden: mid-string literal, mid-expression, inside a comment block
  
  elif content_type == "markdown":
    # Heading-aware: prefer splitting between sections
    return find_clean_boundary_markdown(output)
    #   Preferred: before a heading (# line)
    #   Good: paragraph break between sections
    #   Acceptable: paragraph break anywhere
  
  elif content_type == "structured_data":
    # JSON/YAML/CSV-aware: never split mid-record
    return find_clean_boundary_structured(output)
    #   Preferred: between top-level JSON objects/array elements
    #   Good: after a complete CSV row
    #   Forbidden: mid-JSON object, mid-YAML block
  
  else:
    return find_clean_boundary_prose(output)  # Default to prose


FUNCTION handle_no_echo(prior_output, continuation_output, structural_state):
  """Fallback when echo detection finds no common substring >= 20 chars."""
  
  # Case 1: Prior output ends with unclosed structure
  if structural_state.open_blocks:
    # Look for the continuation to open with the closing structure
    # e.g., prior ends mid-code-block, continuation starts with ```
    for block_type in structural_state.open_blocks:
      closer = get_closing_marker(block_type)
      if continuation_output.lstrip().startswith(closer):
        return continuation_output  # Natural structural continuation
  
  # Case 2: Check for semantic overlap (model rephrased instead of echoed)
  tail_sentences = extract_last_sentences(prior_output, n=3)
  head_sentences = extract_first_sentences(continuation_output, n=3)
  for ts in tail_sentences:
    for hs in head_sentences:
      if cosine_similarity(embed(ts), embed(hs)) > 0.85:
        # Semantic echo — remove the rephrased sentence from continuation
        return continuation_output[len(hs):]
  
  # Case 3: No overlap at all — insert structural bridge
  if prior_output.rstrip()[-1] not in '.!?:\n':
    # Prior ended mid-sentence — this is a hard stitch
    return '\n\n' + continuation_output  # Paragraph break as bridge
  
  return continuation_output  # Clean join — prior ended at a boundary


FUNCTION validate_stitch_integrity(stitched, stitch_point, content_type):
  """Post-stitch validation to catch common stitching artifacts."""
  
  # Check 1: No duplicate sentences at the seam
  seam_region = stitched[max(0, stitch_point-500):stitch_point+500]
  sentences = split_sentences(seam_region)
  for i in range(len(sentences)-1):
    if cosine_similarity(embed(sentences[i]), embed(sentences[i+1])) > 0.95:
      LOG_WARNING(f"Possible duplicate sentence at stitch seam: '{sentences[i][:80]}...'")
  
  # Check 2: Bracket/block integrity
  open_before = count_open_blocks(stitched[:stitch_point])
  open_after = count_open_blocks(stitched)
  if open_after > open_before:
    LOG_WARNING(f"Stitch introduced {open_after - open_before} unclosed blocks")
  
  # Check 3: Heading hierarchy continuity (for markdown/document content)
  if content_type == "markdown":
    headings = extract_heading_hierarchy(stitched)
    for i in range(1, len(headings)):
      if headings[i].level > headings[i-1].level + 1:
        LOG_WARNING(f"Heading level jump at stitch: {headings[i-1]} → {headings[i]}")
  
  # Check 4: List numbering continuity
  numbers = extract_numbered_list_items(stitched)
  for i in range(1, len(numbers)):
    if numbers[i] != numbers[i-1] + 1 and numbers[i] != 1:  # Allow restart at 1
      LOG_WARNING(f"List numbering discontinuity: {numbers[i-1]} → {numbers[i]}")
```

**N-way stitching**: For chains of 50+ windows, stitching is applied pairwise and iteratively. After Window 1 + Window 2 are stitched, the result is stitched with Window 3, etc. Each stitch operation is independent — the algorithm doesn't need to see all windows at once.

**Echo detection**: Longest common substring matching between the tail of prior output (last ~2000 chars) and the start of continuation output (first ~2000 chars). Only matches of 20+ characters count. When echo detection fails (no match found), the `handle_no_echo` fallback checks for semantic echoing, structural continuation, and inserts appropriate bridges.

---

## 3.5 Long-Chain Coherence Maintenance

For continuation chains longer than 5 windows, the protocol actively maintains coherence through three mechanisms that prevent semantic drift (the gradual divergence between extracted representation and actual output):

### 3.5.1 Voice Profile

At the end of the first generation window, the orchestrator extracts a **voice profile** — a compact representation of the output's stylistic characteristics:

```
FUNCTION extract_voice_profile(first_window_output):
  """Capture stylistic fingerprint from the first window's output."""
  return VoiceProfile(
    avg_sentence_length=mean_sentence_length(first_window_output),
    vocabulary_level=vocabulary_richness_score(first_window_output),
    tone_markers=extract_tone_markers(first_window_output),
      # e.g., ["formal", "analytical", "technical"] or ["conversational", "explanatory"]
    formatting_patterns=detect_formatting_patterns(first_window_output),
      # e.g., "uses markdown headers", "uses numbered lists", "uses bold for emphasis"
    paragraph_length_distribution=paragraph_length_stats(first_window_output),
    exemplar_paragraphs=select_exemplar_paragraphs(first_window_output, n=2),
      # Two representative paragraphs that best capture the voice
  )
```

The voice profile is stored in warm state and injected into every continuation envelope as part of the style guidance. It provides a *stable anchor* for the LLM's writing style that doesn't erode across extraction-of-extraction cycles because it references the ORIGINAL output, not extracted facts about the output.

### 3.5.2 Progressive Document Map

A running table of contents that tracks the document's overall structure as it grows across windows:

```
FUNCTION update_document_map(document_map, new_output, window_index):
  """Update the progressive document map with new structural elements."""
  
  new_headings = extract_headings(new_output)
  new_sections = extract_section_boundaries(new_output)
  
  for heading in new_headings:
    document_map.add_entry(DocumentMapEntry(
      heading=heading.text,
      level=heading.depth,
      window_index=window_index,
      approximate_position=heading.char_offset,
      word_count=heading.section_word_count
    ))
  
  return document_map


FUNCTION serialize_document_map_for_envelope(document_map):
  """Serialize the document map as a compact outline for the continuation envelope."""
  lines = ["[DOCUMENT MAP]"]
  for entry in document_map.entries:
    indent = "  " * (entry.level - 1)
    marker = "✓" if entry.is_complete else "…"
    lines.append(f"{indent}{marker} {entry.heading} (W{entry.window_index}, ~{entry.word_count}w)")
  return "\n".join(lines)
```

The document map gives every continuation window a birds-eye view of the document it's contributing to. Window 30 doesn't just know "what facts have been established" — it knows "the document has 8 sections, 6 are complete, I'm currently writing section 7.2, and section 8 still needs to be written." This architectural awareness prevents structural drift.

### 3.5.3 Re-Grounding Windows

~~Every N windows (default: every 10 continuation iterations)~~ **When compound degradation exceeds threshold**, the orchestrator inserts a **re-grounding pass** — a non-generating analysis window that refreshes the extracted representation. Re-grounding is **degradation-triggered**, not fixed-interval:

```
FUNCTION maybe_reground(window_metrics: list[WindowMetrics], warm_state, task_intent):
  """Check compound degradation and trigger re-grounding when needed."""
  
  chain_deg = compute_chain_degradation(window_metrics)  # See 02_CORE_PROTOCOL §7.6
  
  REGROUND_THRESHOLD = 0.15   # Re-ground at 15% cumulative degradation
  MIN_SPACING = 3             # Minimum windows between re-groundings
  
  windows_since_last = warm_state.current_window_index - warm_state.last_reground_window
  
  if chain_deg >= REGROUND_THRESHOLD and windows_since_last >= MIN_SPACING:
    run_regrounding_pass(warm_state.get_accumulated_output(), warm_state, task_intent)
    warm_state.last_reground_window = warm_state.current_window_index
    # Reset per-window degradation tracking after re-grounding
    for m in window_metrics[warm_state.last_reground_window:]:
      m.regrounded = True
```

The actual re-grounding pass:

```
FUNCTION run_regrounding_pass(accumulated_output, warm_state, task_intent):
  """Degradation-triggered re-grounding to prevent extraction-of-extraction drift."""
  
  # 1. Re-read the raw per-window outputs (stored in warm state for audit)
  #    NOT the extracted facts — the ACTUAL output
  raw_outputs = warm_state.get_all_raw_outputs()
  
  # 2. Run full extraction on the STITCHED accumulated output
  #    This produces a fresh fact set from the actual document, not from
  #    the chain of extracted-from-extracted facts
  fresh_facts = graduated_extract(accumulated_output, task_intent)
  
  # 3. Reconcile fresh facts with existing warm state facts
  for fresh_fact in fresh_facts:
    existing = warm_state.find_similar_fact(fresh_fact, threshold=0.85)
    if existing:
      # Update existing fact's embedding and text to match the fresh extraction
      # This corrects drift where extracted facts diverge from actual output
      existing.text = fresh_fact.text
      existing.embedding = fresh_fact.embedding
      existing.regrounded_at_window = warm_state.current_window_index
    else:
      # New fact found on re-read that incremental extraction missed
      fresh_fact.source = "regrounding"
      warm_state.add_fact(fresh_fact)
  
  # 4. Update voice profile if style has evolved
  recent_output = raw_outputs[-3:]  # Last 3 windows
  warm_state.voice_profile = update_voice_profile(
    warm_state.voice_profile,
    "\n\n".join(recent_output)
  )
  
  # 5. Rebuild fact graph edges for any corrected facts
  warm_state.fact_graph.rebuild_edges_for(
    [f for f in fresh_facts if f.regrounded_at_window is not None]
  )
```

**Why degradation-triggered re-grounding**: A fixed "re-ground every 10 windows" rule is both wasteful (re-grounds during low-degradation entity-rich chains where extraction fidelity stays high) and insufficient (misses rapid degradation in reasoning-dense chains where conditional relationships are lost). The compound degradation model ($d_{\text{chain}}(n) = 1 - \prod(1-d_i)$) accumulates per-window quality loss from extraction yield, supersession rate, and information flow decline. Re-grounding fires **when needed** based on actual measured degradation — analogous to TCP's congestion-triggered retransmission vs. fixed-interval polling. See 02_CORE_PROTOCOL Section 7.6 for the full formula.

**Over 20+ windows**, the extraction pipeline processes each window independently. Fact A is extracted from window 3. Fact B is extracted from window 12 and references A. Fact C is extracted from window 20 and references B. By window 30, the envelope carries Fact C — which is an extraction of content that was itself written from extracted facts. This is a lossy telephone chain. Re-grounding breaks the chain by going back to the actual accumulated output and re-extracting, maintaining alignment between what the document ACTUALLY says and what the warm state BELIEVES it says.

**Cost**: One re-grounding pass costs ~10-50ms of extraction time (CPU-only, no LLM calls). For entity-rich output, this is negligible. For very large accumulated outputs (>500K tokens), Stage 1+2 run quickly; Stage 3+ are selectively applied to recent sections only.

---

## 4. OUTPUT SCALING MATH

### 4.1 Total Output Capacity

For a model with context window $C$:

**Total output capacity across N continuation windows:**
$$O_{\text{total}} = \sum_{i=1}^{N} O_i$$

Where $O_i$ is the output of window $i$ (variable — the model generates until it naturally stops or hits the wall).

For Youtu-LLM-2B (C = 128,000):
- If each window generates ~4,000 tokens before natural completion: 50 windows → **200,000 tokens**
- If the model fills the full window each time: fewer, denser windows
- The protocol doesn't prescribe window output size — it observes and adapts

### 4.2 Throughput Considerations

Each continuation window requires:
1. **Envelope construction**: < 100ms (CPU — extraction + embedding + packing)
2. **Prompt tokenization**: < 100ms (CPU)
3. **KV cache computation** (prefill): ~2-5 seconds for 128K tokens at 4GB VRAM
4. **Token generation**: model-dependent (~15-25 tok/s for 2B on consumer GPU)

The prefill overhead is typically < 2% of total time. Prompt caching (shared system prompt prefix) reduces it further.

---

## 5. SPECULATIVE ACCELERATION

### 5.1 Within-Window Acceleration

CRP is composable with token-level acceleration techniques:

**Speculative Decoding**: Draft model proposes tokens, main model verifies in parallel. 2-3× speedup per window.

**Medusa Multi-Head**: Multiple decode heads predict subsequent tokens. 2.2-3.6× speedup per window.

**Prompt Caching**: Shared prefix (system prompt + stable critical state) has its KV cache computed once and reused across continuation windows. Saves ~40-60% of prefill time.

### 5.2 Parallel Window Execution

For fan-out operations (analyze N items independently):

```
# Sequential: N items × time_per_window
# Parallel:   N items ÷ batch_size × time_per_window (with continuous batching)
```

Parallel execution options:
- Multiple model instances (memory-hungry)
- Continuous batching (llama-server supports this)
- Pre-computed envelopes for minimal latency between windows

---

## 6. GENERATION GUIDANCE — DEPRECATED

> **Note**: Sections 6.1-6.3 from v1 (EOS Suppression, Temperature, and Stop Sequences **per TaskType**) are **DEPRECATED**. Generation parameters are now derived from TaskIntent, not a TaskType enum.

See Section 10 for the current task-agnostic generation guidance.

---

## 7. FAILURE MODES & RECOVERY

### 7.1 Empty Continuation

If a continuation window generates very few tokens:
- **Diagnosis**: The model believes the task is complete
- **Recovery**: Run gap analysis — if gap is zero, accept as complete. If gap non-zero, redispatch with the gap explicitly stated in the continuation envelope.

### 7.2 Repetitive Continuation

If information flow drops to zero within a continuation window:
- **Diagnosis**: The model is recycling content from prior windows
- **Recovery**: Abort the current generation. Redispatch with: (a) reduced style anchor, (b) explicit "do NOT repeat" instruction, (c) more specific gap statement.

### 7.3 Style Drift

If continuation output doesn't match the style of prior output:
- **Diagnosis**: Insufficient style anchor or system prompt doesn't specify style
- **Recovery**: Include a longer style anchor paragraph. Add explicit style instructions to system prompt.

### 7.4 Runaway Continuation

If continuation chains keep extending without completing:
- **Diagnosis**: No clear completion criteria, or the task is genuinely open-ended
- **Recovery**: If `max_continuations` is set (optional user override), enforce it. Otherwise, detect via information flow: if successive windows produce declining fact yield, the chain is past its productive life — terminate and return accumulated output.

---

## 8. GENERATION QUALITY MATHEMATICS — Detecting Failed & Inadequate Generations

### 8.1 The Problem

The protocol needs mathematical criteria for generation health:
- **Is this generation adequate?** (did it produce useful content?)
- **Is this generation failing?** (is the model stuck, looping, or producing garbage?)
- **When did quality drop?** (at which token position?)

### 8.2 Generation Quality Score: Q(t, w)

$$Q(t, w) = Q_{\text{information}}(t) \cdot Q_{\text{coherence}}(t) \cdot Q_{\text{novelty}}(t, w)$$

Where:
- $t$ = token position within current window
- $w$ = window index in continuation chain
- Each component is in [0, 1]

**Component 1: Information Density — $Q_{\text{information}}(t)$**

$$Q_{\text{information}}(t) = \frac{|\text{unique tokens in } [t-k, t]|}{k}$$

Where $k$ = sliding window size (self-calibrated from observed output). Fresh output: ~0.6-0.8. Repetitive: < 0.3. Completely stuck: < 0.1.

**Component 2: Coherence — $Q_{\text{coherence}}(t)$**

$$Q_{\text{coherence}}(t) = 1 - \frac{\text{error\_signals}(t)}{\text{max\_errors}}$$

Error signals: unclosed brackets open > 500 tokens, encoding errors, broken formatting.

**Component 3: Cross-Window Novelty — $Q_{\text{novelty}}(t, w)$**

$$Q_{\text{novelty}}(t, w) = 1 - \frac{|\text{5-grams in } [t-k, t] \cap \text{prior\_output\_5grams}|}{|\text{5-grams in } [t-k, t]|}$$

High novelty (> 0.8): new content. Low novelty (< 0.4): rehashing. Zero novelty (< 0.1): echoing — abort.

### 8.3 Real-Time Quality Monitoring Protocol

```
DURING GENERATION (periodically):

  1. Update Q_information(t): rolling unique token ratio
  2. Update Q_coherence(t): structural integrity check
  3. Update Q_novelty(t, w): 5-gram overlap with prior output
  4. Compute composite: Q(t, w) = Q_info * Q_coherence * Q_novelty

  DECISION RULES (adaptive — thresholds self-calibrated from session baseline):
  
  IF Q(t, w) ≈ 0 for extended span:
    → ABORT generation — model is degenerate
    → RETRY with mutated parameters
  
  IF Q_novelty ≈ 0 for extended span:
    → ABORT — model is echoing prior output
    → RETRY with reduced overlap, anti-repetition instruction
  
  IF Q_information declining steadily:
    → Natural completion approaching
    → Let EOS happen naturally or soft-terminate at next boundary
  
  IF Q(t, w) drops sharply from high to low:
    → LOG degradation point
    → Post-generation: consider truncating at degradation point
```

### 8.4 Post-Generation Quality Report

Every window produces a quality report:

```python
@dataclass
class GenerationQualityReport:
    """Attached to every WindowResult."""
    
    mean_quality: float
    min_quality: float
    min_quality_position: int
    
    mean_information_density: float
    mean_coherence: float
    mean_novelty: float
    
    quality_cliffs: list[int]
    repetition_episodes: list[tuple[int, int]]
    
    is_adequate: bool
    inadequacy_reason: str | None
```

---

## 9. MULTIPLE GENERATION STRATEGIES PER WINDOW

### 9.1 Strategy Registry

Different content types benefit from different generation strategies:

```python
class GenerationStrategy(Protocol):
    """Interface for pluggable generation strategies."""
    def configure(self, intent: TaskIntent, config: WindowConfig) -> GenerationConfig: ...
    def post_process(self, output: str, config: GenerationConfig) -> ProcessedOutput: ...

class StrategyRegistry:
    strategies: dict[str, GenerationStrategy] = {
        "standard": StandardAutoregressive(),
        "grammar_constrained": GrammarConstrainedStrategy(),
        "checkpoint_sectioned": CheckpointSectionedStrategy(),
        "quality_gated": QualityGatedStrategy(),
        "multi_pass": MultiPassStrategy(),
    }
```

### 9.2 Strategy Descriptions

**Strategy 1: Standard Autoregressive (default)** — Token-by-token generation with real-time quality monitoring. Best for general prose, analytical content.

**Strategy 2: Grammar-Constrained (Outlines/GBNF)** — FSM-based logit masking ensures output matches a user-supplied schema/grammar. Structure is GUARANTEED by FSM acceptance. Best for JSON output, tool calls, code.

**Strategy 3: Checkpoint-Sectioned** — Generates in sections with extraction after each. Can stop mid-window when enough content is generated. Best for multi-section reports.

**Strategy 4: Quality-Gated** — Monitors Q(t,w) in real-time. If quality drops severely (degenerate output), stops the current window early and returns a truncated output. This is NOT a continuation trigger — it's an abort-and-redispatch. The orchestrator treats the truncated output as if the model stopped naturally, runs gap analysis, and redispatches if needed. Best for user-facing content.

**Strategy 5: Multi-Pass** — Splits generation budget into multiple passes with different strategies. Example: grammar-constrained JSON (200 tokens) + free-form reasoning (3800 tokens) in one window.

### 9.3 Automatic Strategy Selection

When the caller doesn't specify a strategy, the orchestrator selects based on TaskIntent:

```python
class AutoStrategySelector:
    def select(self, intent: TaskIntent) -> WindowGenerationPlan:
        passes = []
        
        # If structured output requested → grammar-constrained
        if intent.output_schema or intent.output_grammar:
            passes.append(GenerationPass(
                strategy="grammar_constrained",
                grammar=compile_grammar(intent)
            ))
        
        # Otherwise → standard or quality-gated based on expected length
        if not passes:
            strategy = "quality_gated" if intent.expected_output_length == "long" else "standard"
            passes.append(GenerationPass(strategy=strategy))
        
        return WindowGenerationPlan(passes=passes)
```

### 9.4 SDK Configuration

```python
# Zero-configuration default (works for most cases)
result = crp.dispatch(system_prompt="Analyze these findings.", task_input="...")

# With user-supplied grammar for structured output
result = crp.dispatch(
    system_prompt="Select the next tool.",
    task_input="...",
    output_schema={"type": "object", "properties": {"tool": {"type": "string"}}}
)

# Explicit multi-strategy per window (power user)
result = crp.dispatch(
    system_prompt="Select tool and explain.",
    task_input="...",
    generation_plan=WindowGenerationPlan(
        passes=[
            GenerationPass(strategy="grammar_constrained", grammar=TOOL_GBNF),
            GenerationPass(strategy="standard"),
        ]
    )
)
```

---

## 10. TASK-AGNOSTIC GENERATION PARAMETERS

Generation parameters are derived from **TaskIntent**, not from a TaskType enum:

```python
class TaskAgnosticGenerationConfig:
    @staticmethod
    def from_intent(intent: TaskIntent, model_profile: ModelProfile) -> GenerationConfig:
        # Temperature: from intent or model default
        temp = intent.temperature or model_profile.default_temperature
        
        # No EOS suppression by default — the model stops when it wants to.
        # Information flow measurement detects if it stopped too early (gap non-zero).
        
        # Stop sequences: from intent or none
        stop_seqs = intent.stop_sequences or []
        
        # Grammar: from intent (user-supplied schema → GBNF)
        grammar = None
        if intent.output_schema:
            grammar = json_schema_to_gbnf(intent.output_schema)
        elif intent.output_grammar:
            grammar = intent.output_grammar
        
        # Max tokens: user-imposed cap if provided, otherwise unbounded (physical wall)
        max_tokens = intent.max_output_tokens  # None = generate freely
        
        return GenerationConfig(
            temperature=temp,
            stop_sequences=stop_seqs,
            grammar=grammar,
            max_tokens=max_tokens,
        )
```

**Key principle**: No generation budgets, no EOS suppression, no per-category temperature tables, no per-category stop sequences. The model generates freely. The extraction pipeline measures whether it produced enough. If it didn't, continuation or retry handles it. If it produced too much repetition, quality monitoring detects it.

---

## 11. HIERARCHICAL GENERATION MODE

Chained generation (Section 2) produces output serially — window after window. This works at Tier S/A/B scale but becomes untenable at Tier C/D (see 02_CORE Section 10). Hierarchical Generation extends the chained generation protocol to support the map-reduce-validate pattern.

### 11.1 When Hierarchical Generation Activates

The orchestrator auto-selects hierarchical generation when:
- Estimated input exceeds 100× context window (Tier C+)
- The task requires synthesis across many independent sources
- `task_intent.processing_mode == "hierarchical"` (explicit override)

### 11.2 Map Phase — Parallel Segment Generation

Instead of a single chain, the input is chunked into segments. Each segment spawns its own independent generation chain:

```python
FUNCTION hierarchical_generate(task_intent, segments, model_profile):
  """Generate output using map-reduce-validate hierarchy."""
  
  # MAP: Each segment gets a synthesis generation chain
  segment_outputs = []
  for segment in parallel_dispatch(segments):
    synthesis = chained_generate(
      system_prompt=f"Analyze this segment comprehensively. Extract all key findings, "
                    f"data points, entities, and conclusions.",
      task_input=segment,
      model_profile=model_profile,
      # Continuation still works within each segment’s chain
    )
    segment_outputs.append(synthesis)
  
  # REDUCE: Merge segment outputs hierarchically
  while len(segment_outputs) > model_profile.max_merge_batch:
    batches = chunk_list(segment_outputs, model_profile.max_merge_batch)
    merged = []
    for batch in batches:
      merge_output = chained_generate(
        system_prompt=f"Synthesize these {len(batch)} analyses into a unified summary. "
                      f"Preserve all key findings. Resolve contradictions.",
        task_input="\n\n---\n\n".join(batch),
        model_profile=model_profile
      )
      merged.append(merge_output)
    segment_outputs = merged
  
  # VALIDATE: Cross-segment consistency (02_CORE Section 13)
  validation = run_cross_window_validation(segment_outputs, task_intent)
  
  # FINAL: Generate the requested output with full synthesized context
  final = chained_generate(
    system_prompt=task_intent.system_prompt,
    task_input=format_hierarchical_context(segment_outputs, validation, task_intent),
    model_profile=model_profile
  )
  
  return final
```

### 11.3 Continuation Within Hierarchy

Each level of the hierarchy uses standard chained generation internally. Continuation windows, extraction, and envelope construction work exactly as specified in Sections 2-3. The hierarchy adds an OUTER loop that organizes WHICH chains run and how their outputs merge.

This means extraction yield, quality monitoring, re-grounding, voice profiling, and structural stitching all work unchanged.

---

## 12. REVIEW CYCLE INTEGRATION IN GENERATION

### 12.1 Review Checkpoints in the Chain

Active Review Cycles (02_CORE Section 14) integrate into the generation chain as checkpoint windows:

```
NORMAL CHAIN:  W1 → W2 → W3 → W4 → W5 → W6 → W7 → W8 → W9 → W10

WITH REVIEW:   W1 → W2 → W3 → W4 → W5 → [T1] → W6 → W7 → W8 → W9 → W10 → [T1+T2] → ...
                                          ↑                                    ↑
                                   Tier 1 check                         Tier 1+2 check
                                   (extraction-only,                    (extraction + binary
                                    zero LLM cost)                       LLM probes)
```

Tier 1 validation (extraction-based) runs inline with zero additional LLM calls. Tier 2 adds minimal overhead (10-token binary questions). Tier 3 review windows are full generations but only dispatch for Tier 3-capable models.

### 12.2 Context Query Signal Response During Generation

When Context Query Signals (02_CORE Section 12) detect context hunger during active generation, the response depends on timing:

```python
FUNCTION handle_cqs_during_generation(signals, current_window, warm_state):
  """Handle detected context hunger during active generation."""
  
  max_strength = max(s.strength for s in signals)
  tokens_generated = current_window.tokens_produced
  
  if max_strength >= 0.8 and tokens_generated < 500:
    # Strong hunger early in window → cheaper to re-dispatch with enrichment
    return Action.REDISPATCH_WINDOW
  
  elif max_strength >= 0.5:
    # Moderate hunger → enrich the NEXT window's envelope
    for signal in signals:
      warm_state.pending_enrichment.append(
        EnrichmentRequest(topic=signal.topic, signal_type=signal.signal_type)
      )
    return Action.ENRICH_NEXT_WINDOW
  
  else:
    # Weak signal → log for analytics, don't intervene
    warm_state.cqs_log.append(signals)
    return Action.OBSERVE
```

### 12.3 Quality-Gated Continuation Decision

The continuation decision (Section 3) now includes quality tier awareness:

```python
FUNCTION decide_continuation(window_result, warm_state, quality_report):
  """Enhanced continuation decision that considers quality tier."""
  
  # Standard check: gap analysis, information flow, physical wall
  standard_decision = standard_continuation_check(window_result, warm_state)
  
  if not standard_decision.should_continue:
    return standard_decision
  
  # Quality tier check: warn if degradation is entering Tier C/D
  if quality_report.tier in ('C', 'D') and quality_report.processing_mode == 'serial':
    # Serial chain is degrading — suggest hierarchical switch
    warm_state.blockers.append(
      f"[QUALITY WARNING] Chain degradation at {quality_report.chain_degradation:.1%}. "
      f"Consider hierarchical processing for this scale (Tier {quality_report.tier})."
    )
  
  return standard_decision
```

### 12.3 Hierarchical Generation Cost Model

When hierarchical processing is triggered (Tier C/D), the generation chain restructures from serial to map-reduce. The concrete timing impact:

```
HIERARCHICAL GENERATION TIMING:

  Non-hierarchical fallback (all serial on 1 GPU):
    100M tokens = 781 serial windows × (3s prefill + 2s gen + 0.2s CRP) = 68 minutes
    1B tokens = 7,813 serial windows × 5.2s = 11.3 hours
  
  Hierarchical (1 GPU, serial within levels):
    100M tokens:
      Level 0: 100 segments × ~10 windows/segment = 1,000 map windows × 5.2s = 87 min
      Level 1: 100 syntheses → 10 merge windows × 5.2s = 52s
      Level 2: Final synthesis = 1 window = 5.2s
      Total: ~88 minutes (MORE than serial — hierarchy has coordination overhead)
    
    1B tokens:
      Level 0: 100 segments × ~78 windows = 7,800 map windows × 5.2s = 11.3 hrs
      Level 1: Merge = 20 windows = 104s
      Level 2: Final = 1 window = 5.2s
      Total: ~11.3 hours (same as serial — map phase dominates)
  
  Hierarchical (4 GPUs, parallel map phase):
    100M tokens:
      Level 0: 1,000 map windows / 4 GPUs = 250 serial windows × 5.2s = 21.7 min
      Level 1-2: 11 windows × 5.2s = 57s
      Total: ~22 minutes (3x faster than serial)
    
    1B tokens:
      Level 0: 7,800 / 4 = 1,950 windows × 5.2s = 2.8 hrs
      Level 1-2: 21 windows × 5.2s = 109s
      Total: ~2.9 hours (4x faster than serial)
  
  CRITICAL INSIGHT: Hierarchical processing on a SINGLE GPU does NOT reduce
  wall-clock time for the map phase (same windows, same serial order).
  It reduces wall-clock time only through:
    (a) Parallelism across multiple GPUs/instances
    (b) Reduced REDUCE windows (logarithmic merge)
    (c) Better QUALITY at same time cost (bounded degradation)
  
  The primary benefit on single-GPU is QUALITY, not SPEED.
  The primary benefit on multi-GPU is BOTH quality AND speed.
```

---

## 13. LLM CONTEXT CURATION IN GENERATION CHAINS

### 13.1 Curation Points

During long generation chains (>5 windows), the orchestrator periodically dispatches **curation windows** (02_CORE §18) where the LLM curates what's most important to carry forward:

```
CHAIN WITH CURATION:  W1 → W2 → W3 → W4 → W5 → [CUR] → W6 → W7 → ... → W10 → [CUR+T1] → ...
                                                  ↑                               ↑
                                           LLM curation                  Curation + Tier 1
                                           (LLM decides what              review checkpoint
                                            matters most)
```

Curation windows produce the `[LLM_SYNTHESIS]` envelope section. All subsequent windows carry this synthesis, giving the LLM access to its own accumulated understanding — not just the orchestrator's extracted facts.

### 13.2 Curation Trigger

```python
FUNCTION should_curate(window_index, warm_state, config):
  """Determine if a curation window should run at this point."""
  
  if not config.meta_learning.enabled:
    return False
  
  # Check global overhead budget first
  if not overhead_budget.check("curation"):
    return False  # Overhead budget exceeded — skip curation
  
  # Adaptive interval based on model throughput
  interval = adaptive_curation_interval(config, warm_state)
  
  # Periodic curation
  if window_index % interval == 0 and window_index > 0:
    return True
  
  # Triggered curation: when CQS detects high uncertainty
  if warm_state.pending_enrichment and max(
    e.source_signal.strength for e in warm_state.pending_enrichment
  ) >= 0.8:
    return True
  
  return False

FUNCTION adaptive_curation_interval(config, warm_state):
  """Adapt curation frequency to model speed and resource pressure.
  
  Fixed intervals waste resources on slow models and under-utilize fast models.
  A 2B model at 15 tok/s spends ~53s generating curation output.
  A cloud API at 200 tok/s spends ~4s. Same interval makes no sense."""
  
  base_interval = config.meta_learning.curation_interval  # default: 5
  
  # Measure: average generation time per window (from recent history)
  avg_gen_time = warm_state.telemetry.avg_generation_time_ms()
  
  if avg_gen_time > 30_000:       # >30s per window (slow local model)
    return base_interval * 4      # Curate every 20 windows
  elif avg_gen_time > 10_000:     # 10-30s per window (medium model)
    return base_interval * 2      # Curate every 10 windows
  elif avg_gen_time < 2_000:      # <2s per window (fast cloud API)
    return max(base_interval // 2, 3)  # Curate every 2-3 windows
  
  # Resource pressure adjustment
  if warm_state.resource_pressure >= MODERATE:
    return base_interval * 2      # Double interval under pressure
  if warm_state.resource_pressure >= HIGH:
    return base_interval * 4      # Quadruple interval under high pressure
  
  return base_interval

ADAPTIVE_CURATION_RULES:
  Fast model (<2s/window):      Curate every 2-3 windows (cheap overhead)
  Medium model (2-10s/window):  Curate every 5 windows (default)
  Slow model (10-30s/window):   Curate every 10 windows (expensive overhead)
  Very slow model (>30s/window): Curate every 20 windows (curation nearly costless relative to generation)
  Resource pressure:            Override — double/quadruple interval
  Overhead budget:              Override — skip if overhead budget exceeded
```

### 13.3 Integration with Source Grounding

Curation windows benefit from source grounding (02_CORE §17): the curation window itself receives source passages for the top facts, so the LLM's synthesis is grounded in ORIGINAL TEXT, not just compressed facts. This ensures the progressive understanding doesn't drift from the source material.

---

## 14. REASONING-SCAFFOLDED GENERATION

### 14.1 When Active

For models below the capability threshold for a given task (02_CORE §19), the generation chain is restructured from a linear chain into an **Orchestrated Reasoning Chain (ORC)**:

```
STANDARD CHAIN:     W1 → W2 → W3 → W4 (each window generates freely)

ORC CHAIN:          S1 → S2 → S3 → S4 → SYNTH
                    ↑    ↑    ↑    ↑      ↑
              Identify  Map   Assess  Rank   Synthesize
              services  CVEs  risk    vulns  and conclude
```

Each step (S1-S4) is a focused micro-task within the model's capability. The SYNTH window combines all step results into the final output. The LLM doesn't know it's being orchestrated — each window is a normal, self-contained task.

### 14.2 ORC Output Assembly

ORC outputs are assembled differently from standard continuation stitching:
- Standard continuation: outputs are CONCATENATED (they form a continuous document)
- ORC: outputs are SYNTHESIZED (a final synthesis window combines step results into a coherent answer)

```python
FUNCTION assemble_orc_output(step_results, task_intent, warm_state):
  """Combine ORC step results into a final coherent output."""
  
  # Build a synthesis envelope with all step results
  synthesis_input = "\n\n".join([
    f"[STEP {i+1}: {result.step.description}]\n{result.output}"
    for i, result in enumerate(step_results)
  ])
  
  # Final synthesis window
  final = crp.dispatch(
    system_prompt=task_intent.system_prompt,
    task_input=f"{synthesis_input}\n\n---\n\n"
               f"Based on the analysis above, provide your complete response to: "
               f"{task_intent.task_input[:500]}"
  )
  
  return final
```
