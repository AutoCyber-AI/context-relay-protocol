# Demo App

The CRP demo app is the fastest way to see the SDK's core value: governed
single-turn completions, grounded retrieval over your own documents, multi-turn
sessions, and built-in safety reporting - all through one `crp.SDKClient()`.

!!! info "Deployment status"
    Run the demo locally with the self-hosted SDK today. A hosted interactive
    demo is on the roadmap.

## Quick start

```bash
# Run with auto-detected provider
python examples/demo_app/demo.py

# Or specify a provider
python examples/demo_app/demo.py --provider ollama --model qwen3-4b
```

## What the demo shows

The demo walks through four modes that mirror real SDK usage:

### Mode 1: Quick complete

A single `client.complete()` call with automatic safety scoring:

```python
import crp

client = crp.SDKClient()
response = client.complete("Write a haiku about context windows.")

print(response.text)
print(f"Risk: {response.crp.risk}")
print(f"Grounded: {response.crp.grounded}")
print(f"Compliant: {response.crp.compliant}")
```

### Mode 2: Retrieval over documents

Ingest a folder, then ask questions with source attribution:

```python
client.ingest("./examples/demo_app/sample_docs/")
answer = client.ask(
    "What are CRP's safety axioms?",
    depth="standard",
)

print(answer.text)
print(f"Sources: {answer.sources}")
print(f"Quality: {answer.quality}")
print(f"Risk: {answer.crp.risk}")
```

### Mode 3: Interactive

A REPL where each turn extends the session. Facts extracted from earlier turns
automatically appear in later envelopes, so follow-up questions build on prior
context.

### Mode 4: Full benchmark

Runs a comprehensive benchmark across multiple tasks and produces detailed
statistics.

## Reading the output

### Safety fields

Every SDK response exposes a `.crp` summary:

| Field | Meaning |
|------|----------|
| `risk` | Overall risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `grounded` | Fraction of claims with extracted evidence (`0.0–1.0`) |
| `compliant` | Whether the output passes the active safety profile |
| `fabrications` | Number of detected unsupported claims |
| `chain_valid` | Whether the HMAC audit chain is intact |

### Depth levels

When using `client.ask()`, the `depth` parameter controls how much retrieval and
reasoning work is performed:

| Depth | Best For |
|-------|----------|
| `quick` | Fast answers, low cost |
| `standard` | Balanced quality and speed |
| `thorough` | Multi-pass retrieval with contradiction checks |
| `exhaustive` | Maximum coverage; use sparingly |

### Session metrics

```python
s = client.session()
print(f"Session ID: {s.id}")
print(f"Status: {s.status()}")
print(f"Facts: {s.fact_count}")
print(f"Windows: {s.window_count}")
```

## Command-line options

```bash
python examples/demo_app/demo.py [OPTIONS]

Options:
  --provider TEXT    Provider name (ollama, openai, anthropic, lm-studio)
  --model TEXT       Model name/path
  --base-url TEXT    Custom API base URL
  --api-key TEXT     API key for cloud providers
  --mode TEXT        Demo mode (quick, retrieval, interactive, benchmark)
  --task TEXT        Custom task description
  --docs PATH        Folder of documents to ingest for retrieval mode
```

## Example: compare providers

```bash
# Start LM Studio with qwen3-4b loaded
# Then run the retrieval demo:
python examples/demo_app/demo.py \
  --provider lm-studio \
  --model qwen3-4b \
  --mode retrieval \
  --docs ./examples/demo_app/sample_docs/ \
  --task "What is the Context Relay Protocol?"
```

The demo prints the final answer, the sources that grounded it, and the safety
summary - the same fields your production code should inspect before acting on
LLM output.
