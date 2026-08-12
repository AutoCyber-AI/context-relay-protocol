# Streaming

Deliver LLM output as it is generated. CRP supports streaming through
`client.stream()`, yielding `StreamEvent` objects for tokens, continuation
windows, extraction progress, and the final summary.

!!! info "Deployment status"
    Streaming works with the self-hosted SDK today. Managed SaaS streaming
    endpoints are on the roadmap.

## Basic streaming

```python
import crp

client = crp.SDKClient(provider="ollama", model="qwen3-4b")

for event in client.stream("Explain the CAP theorem"):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "extraction":
        pass  # Background extraction happening
    elif event.event_type == "continuation":
        print("\n--- New window ---")
    elif event.event_type == "done":
        summary = event.data
        print(f"\n\nRisk: {summary.crp.risk}")
        print(f"Grounded: {summary.crp.grounded}")
        print(f"Compliant: {summary.crp.compliant}")
```

## Stream event types

| Event Type | Data | When |
|-----------|------|------|
| `token` | String (one or more characters) | Each token arrives |
| `extraction` | Extraction progress | Background extraction runs |
| `continuation` | Window metadata | New continuation window starts |
| `window_complete` | Window stats | A window finishes |
| `done` | Response summary | All generation complete |
| `error` | Error details | Something went wrong |

## Streaming with retrieval

Stream an answer while CRP retrieves and grounds it:

```python
client.ingest("./docs/")

for event in client.stream(
    "What are CRP's core safety axioms?",
    depth="standard",
):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "done":
        summary = event.data
        print(f"\n\nSources: {summary.sources}")
        print(f"Quality: {summary.quality}")
        print(f"Risk: {summary.crp.risk}")
```

## Streaming with continuation

Streaming works with continuation - when the model hits its output wall,
CRP starts a new window and continues streaming:

```python
window = 1
for event in client.stream(
    "Write a complete Python web framework tutorial",
    depth="thorough",
):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "continuation":
        window += 1
        print(f"\n[Window {window}]")
    elif event.event_type == "done":
        summary = event.data
        print(f"\nTotal windows: {window}")
        print(f"Risk: {summary.crp.risk}")
        print(f"Grounded: {summary.crp.grounded}")
```

## When to use streaming

| Use Case | Recommended |
|----------|-------------|
| Interactive CLI/chat | `client.stream(...)` |
| Real-time web UI | `client.stream(...)` |
| Background processing | `client.complete(...)` (non-streaming) |
| Extraction-heavy tasks | `client.stream(..., depth="thorough")` |
| Batch processing | `client.complete(...)` (non-streaming) |

## Async streaming

Async SDK methods are not yet implemented. For async code today, run
`client.stream()` in an executor or use the orchestrator's
`async_dispatch_stream()` directly.

[:octicons-arrow-right-24: Async SDK status](../sdk/async.md)
