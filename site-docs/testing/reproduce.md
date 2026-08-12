# Reproduce Benchmarks

<div class="cr-hero" markdown>

## Reproduce CRP's published benchmark results on your own hardware

This guide walks you through running the continuation benchmark with a local
OpenAI-compatible endpoint. You get the same telemetry, quality tiers, and
audit evidence the CRP team uses to validate releases.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## Prerequisites

- Python 3.10+
- An OpenAI-compatible LLM endpoint
- CRP installed: `pip install crprotocol`

## Option 1: LM Studio (Recommended for Local)

### Step 1: Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai/) and install.

### Step 2: Download a Model

In the **Discover** tab, search for and download one of:

| Model | Size | VRAM | Good For |
|-------|------|------|----------|
| qwen3-4b | 2.5 GB | 4 GB | Exact reproduction of published results |
| llama-3.1-8b | 4.9 GB | 6 GB | Non-thinking model, ~2x more output/window |
| qwen3-8b | 4.9 GB | 6 GB | Thinking model, higher quality |

### Step 3: Configure Context Length

In the **My Models** tab, select the model and set:

- **Context Length (n_ctx)**: `4096`
- **GPU Offload**: Maximum layers your GPU supports

!!! warning "Thinking models"
    If using a thinking model (qwen3), expect ~50% of each window's tokens
    to be internal `<think>` reasoning. This is normal - see
    [Benchmarks](benchmarks.md#thinking-model-tax).

### Step 4: Start the Server

Click **Start Server** in the **Developer** tab. Default: `http://localhost:1234`.

### Step 5: Run the Benchmark

```bash
git clone https://github.com/Constantinos-uni/context-relay-protocol.git
cd context-relay-protocol
pip install -e ".[dev]"

python examples/benchmark_continuation.py \
  --base-url http://localhost:1234/v1 \
  --model qwen3-4b \
  --api-key lm-studio \
  --max-tokens 2048 \
  --max-continuations 10 \
  --context-size 4096 \
  --sections 30
```

## Option 2: Ollama

```bash
# Install and pull a model
ollama pull llama3.1

# Run the benchmark
python examples/benchmark_continuation.py \
  --base-url http://localhost:11434/v1 \
  --model llama3.1 \
  --api-key ollama \
  --max-tokens 2048 \
  --max-continuations 10
```

## Option 3: Cloud API

```bash
# OpenAI
python examples/benchmark_continuation.py \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --api-key $OPENAI_API_KEY \
  --max-tokens 2048 \
  --max-continuations 10

# Anthropic (via OpenAI-compatible proxy)
python examples/benchmark_continuation.py \
  --base-url https://api.anthropic.com/v1 \
  --model claude-sonnet-4-20250514 \
  --api-key $ANTHROPIC_API_KEY \
  --max-tokens 2048
```

## SDK Equivalent

The benchmark exercises the same underlying engine that `crp.SDKClient()` uses.
For an interactive equivalent:

```python
import crp

client = crp.SDKClient()
client.configure(safety_profile="balanced")

# Streamed completion; tokens arrive as events.
for event in client.stream(
    "Write a 30-section deployment guide. Number every section.",
    depth="exhaustive",
):
    if event.event_type == "token":
        print(event.data, end="")
    elif event.event_type == "continuation":
        print("\n[continuation window started]")
    elif event.event_type == "done":
        print("\n[done]")
```

## Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--base-url` | `http://localhost:1234/v1` | LLM API endpoint |
| `--model` | `qwen3-4b` | Model name |
| `--api-key` | `lm-studio` | API key |
| `--max-tokens` | `2048` | Max tokens per window |
| `--max-continuations` | `10` | Max continuation windows |
| `--context-size` | `4096` | Model context size |
| `--sections` | `30` | Number of sections to request |

## What to Expect

### Timing

| Setup | Approx. Time | Windows |
|-------|-------------|---------|
| 4B thinking model, 4K ctx | ~25 min | 8–10 |
| 7–8B non-thinking, 4K ctx | ~15 min | 4–6 |
| 7–8B thinking, 8K ctx | ~20 min | 6–8 |
| Cloud API (GPT-4o-mini) | ~3 min | 4–6 |

### Output Files

The benchmark produces:

| File | Format | Contents |
|------|--------|---------|
| `_crp_benchmark_report.txt` | Text | Full metrics, telemetry, complete outputs |
| `_crp_benchmark_report.json` | JSON | Structured telemetry for analysis |

### Good Results

- **Content multiplier ≥ 5x** - CRP is delivering value
- **Overhead < 10%** - protocol cost acceptable
- **Envelope saturation 0.85–1.05** - budget formula tuned
- **Quality tier A or S** - output meets standards

### Investigate If

- **Overhead > 15%** - extraction may be expensive; try Stage 3/4 off
- **Saturation < 0.5** - context size override wrong; verify with `adapter._context_size`
- **Multiplier < 3x** - task fits in one window; increase `--sections` or decrease `--max-tokens`
- **Repeated sections** - thinking model restarts; this is model behavior

## Comparing Models

Run the same benchmark with different models to see how CRP adapts:

```bash
# Small thinking model
python examples/benchmark_continuation.py --model qwen3-4b --max-tokens 2048

# Medium non-thinking model
python examples/benchmark_continuation.py --model llama3.1 --max-tokens 2048

# Large model with more context
python examples/benchmark_continuation.py --model qwen3-8b --context-size 8192
```

Key differences you'll observe:

| Factor | Small Thinking | Medium Non-Thinking | Large |
|--------|---------------|-------------------|-------|
| Windows needed | 8–10 | 4–6 | 3–5 |
| Thinking tax | ~50% | 0% | Varies |
| Content quality | Good | Good | Better |
| Section coverage | 80–85% | 85–90% | 90–95% |
| Time | Longest | Medium | Shortest |

CRP adapts automatically - no configuration changes needed between models.
