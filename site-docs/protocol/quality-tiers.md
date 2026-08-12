# Quality Tiers

> CRP honestly reports the quality tier of every generation, so you can trust the
> answer and decide when to dig deeper - quality degrades predictably as content
> scale increases, and CRP quantifies this degradation rather than hiding it.

## Tier Definitions

| Tier | Scale | Windows (128K) | Effective Context | Mechanism |
|------|-------|----------------|-------------------|-----------|
| **S** | ≤ C | 1 | Lossless | Single native window |
| **A** | C – 10C (~1.3M) | 2–10 | Near-lossless (<5%) | Linear chain + CKF |
| **B** | 10C – 100C (~13M) | 10–100 | Good (5–20%) | Chain + re-grounding |
| **C** | 100C – 1KC (~130M) | 100–1,000 | Structured (20–40%) | Hierarchical required |
| **D** | >1KC (1B+) | 1,000+ | Synthesis (>40%) | Multi-level hierarchy |

## Degradation Model

### Chain Degradation

For linear continuation chains, compound degradation follows:

$$d_{\text{chain}}(N) = 1 - (1 - d_i)^N$$

Where $d_i$ is per-window degradation (typically 0.5–2%).

### Hierarchical Effective Context

Hierarchical dispatch dramatically reduces degradation:

$$\text{EffCtx} = C \times \bigl(1 - d_{\text{chain}}(\lceil\log_k(N)\rceil)\bigr)$$

| Tokens | Windows (serial) | Windows (hierarchical) | Serial Eff. | Hierarchical Eff. |
|--------|-----------------|----------------------|-------------|-------------------|
| 1M | 8 | 3 levels | 92% | 97% |
| 10M | 78 | 4 levels | 46% | 94% |
| 100M | 781 | 5 levels | 0.04% | 90% |
| 1B | 7,813 | 6 levels | ~0% | 73% |

!!! success "Key insight"
    At 1B tokens, serial chaining is useless (0% effective context).
    Hierarchical dispatch preserves **73%** - making it viable.

## Quality Score

Each generation window is scored in real time:

$$Q(t, w) = Q_{\text{information}}(t) \cdot Q_{\text{coherence}}(t) \cdot Q_{\text{novelty}}(t, w)$$

### Information Density

Unique token ratio in a sliding window:

- **Fresh content**: 0.6 – 0.8
- **Repetitive**: 0.1 – 0.3
- **Stuck / looping**: < 0.1 → triggers termination

### Coherence

$$Q_{\text{coherence}} = 1 - \frac{\text{error\_signals}}{\text{max\_errors}}$$

Error signals: unclosed brackets, encoding errors, broken list numbering,
heading hierarchy violations.

### Cross-Window Novelty

$$Q_{\text{novelty}} = 1 - \text{5-gram overlap ratio with prior output}$$

- **Novel content**: > 0.5
- **Some overlap**: 0.1 – 0.5
- **Echo / repetition**: < 0.1 → triggers **abort + redispatch**

## Re-Grounding

When cumulative degradation exceeds **15%**, CRP triggers re-grounding:

1. Re-extract facts from all accumulated output
2. Rebuild the warm state from scratch
3. Correct drift in fact graph
4. Resume generation with refreshed context

Cost: ~10–50 ms. Not on a fixed schedule - triggered by measured degradation.

## Generation Strategies

CRP supports 5 generation strategies within each window:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Standard Autoregressive** | Default - real-time quality monitoring | General tasks |
| **Grammar-Constrained** | FSM logit masking (GBNF/Outlines) | JSON, code, structured output |
| **Checkpoint-Sectioned** | Extract after each section | Long documents |
| **Quality-Gated** | Abort on quality drop, redispatch | High-accuracy tasks |
| **Multi-Pass** | Multiple strategies per window | Hybrid tasks |

## Continuation Mechanics

Continuation triggers **only** on physical wall hit:

- `finish_reason == "length"` (LLM ran out of tokens)
- Task is not yet fulfilled (gap analysis)
- Information flow is still positive

**Never triggers on**: arbitrary budgets, configured ceilings, or "recommended
window sizes."

### Stitch Algorithm

When continuing, CRP stitches windows using:

1. **Echo detection** - Longest common substring (tail 2K chars × head 2K chars)
2. **Content-type boundary** - prose: paragraph break; code: between functions;
   markdown: before headings
3. **Semantic echo fallback** - Embedding similarity > 0.85 detects rephrased
   echoes
4. **Post-stitch validation** - Duplicate sentences, bracket integrity, heading
   hierarchy, list numbering

### Long-Chain Coherence (>5 windows)

For extended generations, CRP maintains coherence via:

- **Voice Profile** - Extracted from Window 1: sentence length, vocabulary level,
  tone markers, formatting patterns, 2 exemplar paragraphs
- **Progressive Document Map** - Running TOC tracking headings, completion status,
  word counts per section
- **Re-Grounding** - Degradation-triggered (see above)

## Accessing Quality

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")

answer = client.ask(
    "Summarize our incident response policy.",
    depth="standard",
)

print(f"Quality tier: {answer.quality}")
print(f"Complete:     {answer.complete}")
print(f"Risk:         {answer.crp.risk}")
print(f"Grounded:     {answer.crp.grounded}")

s = client.session()
print(f"Windows used: {s.window_count}")
```

The `CRPAskResponse` quality fields include:

| Field | Type | Description |
|-------|------|-------------|
| `text` | str | Complete stitched text |
| `quality` | str | S / A / B / C / D |
| `complete` | bool | Whether the answer covered the whole task |
| `sources` | list | Source documents cited |
| `crp.risk` | str | LOW / MEDIUM / HIGH / CRITICAL |
| `crp.grounded` | bool | Grounding verification result |
| `crp.compliant` | bool | EU AI Act / ISO 42001 mapping result |
| `crp.chain_valid` | bool | HMAC provenance chain integrity |
| `how_it_was_built` | str | STL operation sequence, human-readable |
| `open_questions` | list | Gaps the engine could not resolve |
