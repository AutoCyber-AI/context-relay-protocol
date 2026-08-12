# Context Envelope

<div class="cr-hero" markdown>

## Stop wasting context window on noise

The **context envelope** is CRP's answer to the flat-text prompt. Instead of
dumping documents, history, and instructions into one window, CRP builds a
**dynamically packed payload** that fills all available space with the highest-
scoring, least-redundant facts. The model sees exactly what it needs - and the
business result is higher quality, lower cost, and fewer hallucinations.

</div>

## Business impact

| Without envelope packing | With CRP envelope |
|--------------------------|-------------------|
| Raw text competes for token budget | Every token is scored and earns its place |
| Critical facts buried at position 50K | Most relevant facts placed first and repeated at the end |
| Same context repeated every turn | CDR removes already-known facts |
| No provenance | Every packed fact is traceable to a source |

## Maximum Context Saturation

$$E_{\max} = C - S - T - G$$

| Symbol | Meaning | Example (128K) |
|--------|---------|-----------------|
| $C$ | Context window size | 131,072 |
| $S$ | System prompt tokens | ~500 |
| $T$ | Task input tokens | ~8,756 |
| $G$ | Generation reserve | 16,384 |
| $E_{\max}$ | **Envelope capacity** | **105,816** |

$G$ is automatically determined: user's `max_output_tokens` → provider's reported
max → `min(C // 4, 16384)`.

!!! tip "In practice"
    CRP achieves **0.939–1.021 saturation** (mean 0.994) - virtually every
    available token is used for relevant context.

## Envelope Sections

The envelope is structured with 11 priority-ordered sections. Higher-priority
sections survive when space is limited:

| Priority | Section | Tokens | Purpose |
|----------|---------|--------|---------|
| 1 | **Critical State** | 100–500 | GOAL, PHASE, BLOCKER, CONSTRAINT, WINDOW |
| 2 | **LLM Synthesis** | Adaptive | LLM's own curated understanding |
| 3 | **Task Brief** | Varies | What to do + output format |
| 4 | **Discoveries** | Bulk | Atomic facts with graph edges |
| 5 | **Source Passages** | Variable | Verbatim text for high-relevance facts |
| 6 | **Decisions & Plan** | Variable | Reasoning trail with justifications |
| 7 | **Error Log** | Small | What failed and why |
| 8 | **Tool History** | Small | Compact execution summaries |
| 9 | **Expanded Context** | Overflow | Full-fidelity data from warm state |
| 10 | **CKF Retrievals** | Variable | Cross-session knowledge |
| 11 | **Reasoning Scaffold** | Small | Step-by-step templates (weak models) |

## Fact Selection Algorithm

CRP uses a 3-phase pipeline to select which facts go into the envelope:

### Phase 1: Multi-Aspect Task Decomposition

The task is broken into noun phrases / aspects. A fact matching **any** aspect
scores high:

$$\text{score}(f) = \max_{a \in \text{aspects}} \cos\bigl(\text{embed}(f),\; \text{embed}(a)\bigr)$$

### Phase 2: Bi-Encoder Fast Scoring

All facts scored using `all-MiniLM-L6-v2` embeddings. For >1,000 facts, an
HNSW ANN index provides $O(\log N)$ retrieval.

**Composite score:**

$$\text{final}(f) = \text{sim}(f) \times \text{recency}(f) \times \text{novelty}(f) + \text{dep\_bonus}(f)$$

| Factor | Formula | Range |
|--------|---------|-------|
| Recency | $e^{-0.1 \times \text{age\_in\_windows}}$ | 0 → 1 |
| Novelty | Unseen: 1.5×, <3 uses: 1.0×, 3+: 0.5× | 0.5 → 1.5 |
| Dependency | Graph-connected facts inherit relevance | 0 → 0.5 |

### Phase 3: Cross-Encoder Reranking

Top 200 candidates re-scored with `ms-marco-MiniLM-L-6-v2`:

$$\text{blended} = 0.6 \times \text{CE\_score} + 0.4 \times \text{BE\_score}$$

Cache hit rate: **50–80%** in continuation chains (saves 200–320 ms/window).

## Packing Strategy

After scoring, facts are packed using **greedy bin-packing** with:

- **Dependency-aware graph pulling** - up to 2 hops of connected facts
- **Bookend strategy** - top 3 facts duplicated at envelope end (counters
  "lost in the middle" attention bias)
- **Progressive compression** - truncation → summarization → tabular → reference
  replacement

## Continuation Envelopes

When output is truncated, CRP builds a **continuation envelope** containing:

| Component | Purpose |
|-----------|---------|
| Extracted facts | From the truncated output |
| Structural state | Open blocks, list position, section headers |
| Task gap | Missing items from original task |
| Style anchor | Last natural paragraph for voice consistency |
| Voice profile | Sentence length, vocabulary, tone markers |
| Document map | Running TOC with section completion status |

!!! note "Note"
    Continuation envelopes use **extraction results**, not raw text overlap.
    This is key to CRP's quality preservation across windows.

## Inspecting the Envelope

You can inspect the live session state to see how much context CRP has accumulated
and how many facts are available for packing:

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")
answer = client.ask("Explain Kubernetes networking.", depth="standard")

s = client.session()
print(f"Session ID:     {s.id}")
print(f"Facts gathered: {s.fact_count}")
print(f"Windows used:   {s.window_count}")
print(f"Status:         {s.status()}")
print(f"Quality tier:   {answer.quality}")
print(f"Risk:           {answer.crp.risk}")
print(f"Grounded:       {answer.crp.grounded}")
```

!!! tip "Visibility API"
    Use `client.storage.overview()` and `client.knowledge.location` to see where
    facts are stored without reaching into internal state.
