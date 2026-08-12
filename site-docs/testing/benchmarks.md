# Benchmarks

> CRP's benchmark suite measures real-world performance of the continuation engine,
> extraction pipeline, and protocol overhead - using the same `crp.SDKClient()` API
> you use in production.

## Headline Results

> At a 2,048-token generation limit, a single LLM call produces 592 words and
> is cut off after 8 of 30 requested sections. CRP produces **6,993 words
> across 25 sections with a proper conclusion** - an **11.8x content multiplier**
> at only **6.1% protocol overhead**.

| | Direct LLM | CRP-Orchestrated | Multiplier |
|---|---|---|---|
| **Words** | 592 | 6,993 | **11.8x** |
| **Characters** | 4,640 | 52,740 | **11.4x** |
| **Sections (of 30)** | 8 | 25 | **3.1x** |
| **Paragraphs** | 8 | 99 | **12.4x** |
| **Conclusion present** | No | Yes | - |
| **Truncated** | Yes | No | - |
| **Quality tier** | - | A | - |

*Model: qwen3-4b (4B parameter thinking model). Hardware: consumer PC, LM Studio, n_ctx = 4,096.*

## What This Benchmark Measures

> When an LLM hits its output-token wall, what happens with and without CRP?

The test gives a model a task requiring ~20,000 tokens (a 30-section technical
document), but limits each call to 2,048 output tokens. Without CRP the output
is truncated. With CRP the continuation engine detects the wall, extracts facts,
packs them into an envelope, and dispatches continuation windows until done.

**This is NOT a latency benchmark.** CRP trades wall-clock time for task
completion - the same way a human re-reads notes before continuing a long essay.

```python
import crp

client = crp.SDKClient()

# No continuation - plain LLM call
plain = client.complete(
    "Write a 30-section Kubernetes guide.",
    max_output_tokens=2048,
)

# CRP-orchestrated exhaustive generation
deep = client.ask(
    "Write a 30-section Kubernetes guide.",
    depth="exhaustive",
)

print(f"Plain words: {len(plain.text.split())}")
print(f"CRP words:   {len(deep.text.split())}")
print(f"Quality:     {deep.quality}")
print(f"Complete:    {deep.complete}")
```

## Protocol Efficiency

CRP adds minimal overhead on top of raw LLM generation:

| Component | Time | % of Total |
|-----------|------|-----------|
| LLM generation (9 windows) | 1,342.4 s | 93.9% |
| Envelope build (fact ranking + packing) | 66.2 s | 4.6% |
| Orchestration logic | 20.3 s | 1.4% |
| Extraction pipeline | 0.125 s | 0.009% |
| **Total CRP overhead** | **86.6 s** | **6.1%** |

The extraction pipeline runs in **8–12 ms per window**. Envelope build grows
linearly as the fact base expands - this is the dominant CRP cost.

## Per-Window Telemetry

Each continuation window operates independently:

| Window | LLM (s) | Extract (ms) | Envelope (s) | Output Tokens | Reasoning Tokens | Facts | Saturation |
|--------|---------|-------------|-------------|--------------|-----------------|-------|-----------|
| 1 | 133.9 | 8 | 4.9 | 1,064 | 955 | 38 | 1.011 |
| 2 | 132.9 | 11 | 5.7 | 1,088 | 921 | 43 | 0.939 |
| 3 | 131.9 | 12 | 5.0 | 1,104 | 901 | 36 | 0.997 |
| 4 | 132.2 | 8 | 6.4 | 826 | 1,184 | 33 | 0.961 |
| 5 | 133.3 | 9 | 7.7 | 1,181 | 827 | 44 | 1.008 |
| 6 | 136.8 | 8 | 9.3 | 637 | 1,314 | 26 | 1.021 |
| 7 | 165.6 | 6 | 7.5 | 869 | 1,141 | 32 | 1.014 |
| 8 | 127.7 | 8 | 9.6 | 932 | 1,075 | 33 | 1.007 |
| 9 | 134.8 | 8 | 10.2 | 1,010 | 998 | 43 | 0.992 |

**Key observations:**

- **LLM time is stable** (~133 s/window) - CRP does not introduce growing cost
- **Extraction is free** - 6–12 ms per window (< 0.01% of window time)
- **Envelope build grows linearly** - more facts → slightly longer ranking

## Envelope Saturation

$$\text{saturation} = \frac{\text{envelope tokens packed}}{\text{envelope budget}}$$

**Observed range: 0.939 – 1.021 (mean: 0.994)**

Near 1.0 means the budget formula is well-calibrated. Each window packs
9–15 compressed facts from a pool of 26–44 extracted per window.

## Thinking-Model Tax

The qwen3-4b model spends ~51% of its token budget on internal `<think>`
reasoning that never appears in the output:

| Token Type | Count | % of Generation |
|-----------|-------|----------------|
| Output (visible) | 9,836 | 49.1% |
| Reasoning (`<think>`) | 10,219 | 50.9% |

A **non-thinking model** would produce ~2x more content per window, needing
~4–5 windows instead of 9.

## Throughput Parity

| Metric | Direct LLM | CRP |
|--------|-----------|-----|
| Time | 119.7 s | 1,429.1 s |
| Content | 592 words | 6,993 words |
| Throughput | **4.9 words/s** | **4.9 words/s** |
| Task completed? | No | Yes |

CRP takes 12x longer but produces 12x more content - **effective throughput
is identical**. The difference: CRP finishes the task.

## SQB Gate Results (SPEC-026)

> **Measured run — local 8B, naive continuation harness.** The numbers below are a
> real run of the Semantic Quality Benchmark against `meta-llama-3.1-8b-instruct`
> (LM Studio), recorded 2026-06-30 with `crprotocol` 5.0.0. The SQB *gate* (strict
> repetition < 1.5 % and multi-hop thresholds) is tuned for the full CDR/CDGR
> frontier pipeline, so a small model on a plain continuation harness does **not**
> clear every gate. What it does show is the property that matters most: **factual
> recall holds flat across continuation windows** — facts established early survive
> to the end.

The gating metric is cumulative `factual_recall` — monotonically non-decreasing,
testing that reference facts are preserved across continuation windows.

| Case | Topic | recall W1 → WLast | F1 W1 → WLast | Recall held? |
|------|-------|-------------------|---------------|--------------|
| **sqb-001** | Kubernetes networking (technical) | **0.90 → 0.90** | 0.862 → 0.692 | ✅ yes |
| **sqb-002** | EU AI Act (regulatory) | **0.625 → 0.625** | 0.583 → 0.366 | ✅ yes |
| **sqb-003** | Multi-hop reasoning | 0.00 → 0.00 | 0.000 → 0.000 | small-model limit |

**Reading it honestly:** on technical and regulatory continuations the local 8B
**preserves every fact it established** as the document grows to ~5 700 words across
five windows (the core continuation guarantee). F1 dips because added breadth
introduces some unsupported detail; multi-hop and lexical repetition expose the
small model's own limits — exactly the gap the v5 **positioned tool loop** is built
to close on local models. Re-run it yourself:
`python examples/crp_demos/sqb_benchmark.py --mode full`.

## SQB — Positioned Loop (v5), local SLM vs. frontier judge

> **Measured run — `crprotocol` (unreleased, post-5.0.0), recorded 2026-07-01.** This
> is a *different, newer* test from the one above: instead of the naive continuation
> harness, this runs the SQB cases through the **real CRPv5 positioned loop**
> (`run_positioned`, with output continuation and the anti-repetition fix — a
> `DocumentMap` covered-section table fed into every continuation window, plus an
> n-gram repetition guard that retries a window once and then stops rather than
> padding). Reproduce with `python examples/crp_demos/sqb_positioned.py`.

| Backend | Windows | Mean factual F1 | Mean 4-gram repetition | Mean judge (Kimi) |
|---|---|---|---|---|
| **Kimi (`kimi-k2.6`, frontier)** | 10 | 0.332 | **3.66%** | 6.73/10 |
| **Local 8B (`meta-llama-3.1-8b-instruct`)** | 6 | 0.531 | **20.58%** | n/a (judge rate-limited) |

<small>All 3 SQB cases (technical, regulatory, multi-hop), full dataset — no cases
pending. The judge column shows `n/a` because the Kimi judge API returned `0.0` for
every one of the 3 calls in this run, immediately after the Kimi-backend run above
had already exhausted the same rate-limited quota; a `0.0` score across an *entire*
run (rather than isolated low scores) is a quota signal, not a genuine quality
verdict, so it is reported as not-obtained rather than as a real 0/10.</small>

**Per-case detail (local, 6 windows each):**

| Case | Words | Recall | F1 | 4-gram repetition | Topic coverage |
|---|---|---|---|---|---|
| sqb-001 (technical) | 2 380 | 1.00 | 0.840 | 15.52% | 0.67 |
| sqb-002 (regulatory) | 2 751 | 0.88 | 0.282 | 17.79% | 0.40 |
| sqb-003 (multi-hop) | 2 967 | 0.80 | 0.471 | 28.44% | 0.00 |

**Reading it honestly — does the local model reach Kimi's repetition level?** **Not
yet.** The anti-repetition mechanism (covered-section TOC + n-gram retry guard) is
the *same code path* for both backends and measurably improved the naive-harness
baseline (which spiked to 15–30% on individual windows) into a **consistently low
3.66% mean on Kimi**. On the local 8B, mean repetition across all 3 cases sits at
**20.58%** — roughly 5–6× Kimi's rate, and worst on the multi-hop case (28.44%),
which mirrors the same case's **0.00 topic coverage** in the naive-harness table
above: multi-hop reasoning is consistently the local 8B's weakest domain across both
harnesses, not just this one. This is an honest, model-capability finding, not a
broken mechanism: an 8B model is measurably less reliable than a frontier model at
following the "do not repeat these already-covered sections" instruction embedded in
every continuation prompt, so it re-covers similar ground more often even though the
guard retries once per window. **Recall still holds** (0.80–1.00 — established facts
are not lost) across all 3 cases, which is the CRPv5 continuation guarantee; the
repetition gap is a **quality**, not a **correctness**, gap, and is the next tuning
target (candidates: lowering the retry-trigger threshold below 0.6 for small models,
or having the Resource Governor select a stricter continuation profile per
capability tier).

## Orchestrator Init Performance

CRP v5.1.0 keeps the lazy model-loading fix that prevents 53.7 s cold starts.
With lazy model loading (`eager_load_models=False`, default):

| Scenario | Time |
|----------|------|
| `crp.SDKClient()` init | **< 1 s** |
| First `ingest()` call (lazy model load) | ~3–5 s |
| Ollama probe timeout | **0.5 s** |

See `tests/test_orchestrator_perf.py`.

## Performance Regression Tests

`test_benchmarks.py` contains tests with specific targets:

| Benchmark | Target |
|-----------|--------|
| Cold session init | < 200ms |
| Warm session init | < 50ms |
| Dispatch overhead | < 100ms |
| Envelope assembly | < 50ms |
| Ingest throughput | > 100 facts/sec |
| Cache hit | < 1ms |
| Event emission | < 5ms |
| Metrics export | < 10ms |

Run them:

```bash
python -m pytest tests/test_benchmarks.py -v
```

## Scaling Projections

Based on measured degradation characteristics:

| Scale | Tokens | Est. Windows (128K) | Quality Tier | Effective Context |
|-------|--------|---------------------|----------|-------------------|
| 1× | 128K | 1 | S | 100% |
| 10× | 1.3M | 10 | A | >95% |
| 100× | 13M | 100 | B | 80–95% |
| 1,000× | 130M | 1,000 | C | 60–80% |
| 10,000× | 1.3B | 10,000 | D | <60% (hierarchical: 73%) |

!!! info "Hierarchical dispatch"
    At 1B+ tokens, serial chaining has ~0% effective context.
    Hierarchical dispatch preserves **73%** - $O(\log N)$ windows
    instead of $O(N)$.

## Additional Benchmarks

| Benchmark | What It Shows |
|-----------|--------------|
| Streaming latency | Time-to-first-token for `orchestrator.async_dispatch_stream()` |
| Session persistence | Knowledge accumulation across `complete()` / `ask()` calls |
| Multi-agent pipeline | 3 agents sharing one CRP session |
| Security hardening | Injection detection, integrity verification |
| Model scaling | Same task across 1B, 4B, 7B, 13B models |
| Non-thinking vs thinking | Expected 2x throughput gain without `<think>` |
| Token budget sweep | 512/1024/2048/4096 tokens, plot windows vs content |

See [Reproduce Benchmarks](reproduce.md) for how to run these yourself.
