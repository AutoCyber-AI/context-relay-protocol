# Dispatch Methods

CRP exposes a small set of high-level methods for the most common interaction
patterns. Strategy selection - PUSH, PULL, reflexive, progressive,
streaming, agentic, hierarchical, and batch - is handled internally by the
orchestrator based on the task, context size, and configured quality profile.

## complete()

Single-turn generation with built-in safety and provenance.

```python
response = client.complete(
    "Summarise the EU AI Act",
    # Optional:
    # temperature=0.2,
    # max_output_tokens=2048,
)
print(response.text)
print(response.crp.risk)
print(response.crp.grounded)
print(response.crp.fabrications)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `str` | The task or question |
| `temperature` | `float` | Sampling temperature (optional) |
| `max_output_tokens` | `int` | Generation token limit (optional) |

Returns `CRPCompletionResponse` with `.text` and `.crp` metadata.

---

## ask()

Retrieval-augmented multi-turn Q&A. Ingest documents first, then ask questions.

```python
client.ingest("./docs/")
answer = client.ask(
    "What are the high-risk AI system requirements?",
    depth="standard",
)
print(answer.text)
print(answer.quality)
print(answer.sources)
print(answer.complete)
print(answer.decisions)
print(answer.how_it_was_built)
print(answer.open_questions)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | `str` | - | The question |
| `depth` | `str` | `"standard"` | `quick`, `standard`, `thorough`, `exhaustive` |

Returns `CRPAskResponse` with `.text`, `.sources`, `.quality`, `.complete`,
`.decisions`, `.how_it_was_built`, `.open_questions`, and `.crp` metadata.

---

## ingest()

Load documents into the session's knowledge base.

```python
summary = client.ingest("./docs/")
```

Returns an extraction summary. After ingestion, use `client.ask()` or
`client.knowledge.search()` to query the loaded knowledge.

---

## Tools

Register a Python function as a tool with the `@client.tool` decorator and
call it by name.

```python
@client.tool
def search_kb(query: str) -> str:
    """Search the internal knowledge base."""
    ...

result = client.call_tool("search_kb", query="...")
```

| Method | Use |
|--------|-----|
| `@client.tool(fn)` | Register a function as an available tool |
| `client.call_tool(name, **kwargs)` | Invoke a registered tool by name |

---

## Dispatch strategies (orchestrator internals)

The nine dispatch strategies are now orchestrator internals. They remain
available through the core orchestrator for advanced use, but the recommended
SDK surface is the high-level API above.

| Strategy | Concept | SDK equivalent |
|----------|---------|----------------|
| PUSH | Pre-pack context envelope | `complete()` / `ask()` |
| PULL | Tool-based context retrieval | `ask()` + `@client.tool` |
| Reflexive | Verify-then-refine | Internal quality loop |
| Progressive | Index-then-detail | Internal envelope building |
| Stream-augmented | Mid-stream context injection | Internal streaming |
| Agentic | 8-phase cognitive engine | Internal orchestration |
| Streaming | Real-time token events | Internal streaming |
| Batch | Multiple tasks in one session | Loop over `complete()` / `ask()` |
| Hierarchical | Map-reduce over large input | Internal segmentation |

If you need direct access to these strategies, use `crp.core.CRPOrchestrator`
directly.
