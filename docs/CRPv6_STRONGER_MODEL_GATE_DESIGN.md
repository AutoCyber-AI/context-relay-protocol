# CRPv6 — Stronger Model Gate Design

> How to make the SQB benchmark gate rigorous enough for a production marketing claim.

## Current state

The SQB harness already supports tiered thresholds:

- `frontier` — for Kimi-k2.6, GPT-4o, Claude 3.5+.
- `capable-local` — for 7–8B local models (e.g. Qwen2.5-7B, Llama 3.1 8B).
- `small-local` — for ≤4B local models (e.g. Qwen3-4B, Gemma 3 270M).

Each tier has relaxed lexical and coverage thresholds that reflect realistic small-model performance. This is honest, but it is not a *strong* gate.

## What makes a gate "stronger"?

A stronger gate reduces false positives and makes the benchmark harder to game. Concrete levers:

1. **Multiple independent judges** — run the LLM-as-judge with 2–3 different models and require consensus.
2. **Pass@k reliability** — run each case k times (e.g. k=3) and require all k passes.
3. **Adversarial perturbation** — rephrase the prompt and verify the answer is stable.
4. **Symbolic verifiers** — check arithmetic, dates, and counts with code, not just a judge.
5. **Coverage per fact** — require every reference fact to appear, not just an aggregate F1.
6. **Repetition penalty** — measure exact and semantic repetition across windows and reject if above threshold.
7. **Human spot-checks** — a percentage of cases are reviewed by a human before claiming pass.

## Recommended stronger gate implementation

Add a `--strict` flag to `examples/crp_demos/sqb_benchmark.py` that enables:

```python
STRICT_GATE = {
    "judges": ["kimi-k2.6", "gpt-4o", "claude-3-5-sonnet"],  # require 2/3 consensus
    "pass_at_k": 3,
    "perturb": True,  # rephrase prompt and check answer consistency
    "symbolic_verify": True,  # check dates, numbers, counts
    "per_fact_coverage": True,  # every reference fact must appear
    "max_repetition": 0.01,  # 1% exact repetition
    "human_spot_check_ratio": 0.10,  # 10% of passing cases
}
```

### Consensus judge

For each case, each judge scores 0–10. The case passes only if the median score ≥ threshold and the inter-judge range ≤ 2 points. This prevents one lenient judge from carrying a bad answer.

### Pass@k

Run the same case k times with temperature > 0. The case passes only if all k runs pass every criterion. This proves reliability, not luck.

### Perturbation check

Rephrase the task prompt slightly (e.g. "Write a guide" → "Produce a detailed guide"). The answer must still pass coverage and fact checks. This ensures the result is robust to prompt wording.

### Symbolic verifier

Add a small verifier step:

- Extract all numbers, dates, and percentages from the answer.
- Cross-check against the reference corpus.
- Flag contradictions (e.g. corpus says "1 August 2024", answer says "2025").

### Per-fact coverage

Instead of aggregate F1, require each reference fact to appear with ≥0.5 semantic similarity. A single missing fact fails the case.

## How to operationalise

1. **Short term** — add `--strict` to the existing harness with consensus judge + pass@k + symbolic verifier.
2. **Medium term** — add perturbation and per-fact coverage.
3. **Long term** — integrate human spot-check workflow via the Checkpoint / HITL path.

## What the user needs to do

- Provide API keys for at least two strong judge models (Kimi, OpenAI, Anthropic).
- Run: `python examples/crp_demos/sqb_benchmark.py --mode kimi --strict`
- Budget: strict gate costs ~3–5x more tokens than the current gate.
- Marketing claim: only say "passes the strict SQB gate" after `--strict` passes.

## Honest framing

The current `capable-local` and `small-local` profiles are honest benchmarking tools. They should be used for "works on your laptop" marketing. The `frontier` profile (and future `--strict`) is the right gate for "production-grade reasoning" claims.
