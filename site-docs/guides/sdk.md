# SDK Guide

!!! tip "Complete SDK reference"
    For the canonical interface map covering every public method and return field, see the **[SDK Reference](../sdk/index.md)**. This guide is task-oriented; the reference is the authoritative surface documentation.

CRP ships a **progressive-disclosure SDK** (SPEC-032). Start with one line of code and unlock deeper control only when you need it. No rewrites. No architecture changes.

!!! tip "Who this is for"
    - **Developers** who want governance without learning a new API
    - **Compliance teams** who need audit trails and risk scores
    - **Engineers** who want full control over routing, safety, and provenance

---

## Installation

```bash
pip install crprotocol
```

Verify the install:

```bash
python -m crp --version
```

??? question "Need a specific provider?"
    CRP works with OpenAI, Anthropic, Google Gemini, Mistral, Cohere, Ollama, LM Studio, vLLM, TGI, and any OpenAI-compatible endpoint. Install the provider SDK you already use -- CRP does not replace it.

---

## Level 0 -- Governance (Zero New Concepts)

Change one line and every call is governed, risk-scored, and audited.

=== "Gateway (Recommended)"

    ```python
    from openai import OpenAI

    client = OpenAI(
        api_key="your-provider-key",
        base_url="https://your-gateway.example/v1",
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # Governance signals are attached automatically
    print(response.crp.risk)       # LOW | MEDIUM | HIGH | CRITICAL
    print(response.crp.grounded)   # True | False
    print(response.crp.compliant)  # True | False
    ```

    !!! note "Gateway availability"
        Managed cloud at `gateway.crprotocol.io` is on the waitlist. You can also self-host the Gateway runtime.

=== "Native SDK"

    ```python
    import crp

    client = crp.SDKClient()
    response = client.complete("Summarise the EU AI Act")

    print(response.crp.risk)       # LOW | MEDIUM | HIGH | CRITICAL
    print(response.crp.grounded)   # True | False
    print(response.crp.compliant)  # True | False
    ```

!!! success "That's it"
    No new imports. No new concepts. Your existing code stays the same.

### Understanding the `.crp` object

Every response carries a governance summary. Here is what each field means:

| Field | Type | Meaning |
|-------|------|---------|
| `risk` | `str` | Overall risk level: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `grounded` | `bool` | Whether the response is anchored to provided context |
| `compliant` | `bool` | Whether the response passes configured safety policies |
| `fabrications` | `int` | Number of unsupported claims detected |
| `chain_valid` | `bool` | Whether the audit chain is intact |
| `injection_detected` | `bool` | Whether prompt-injection patterns were found |
| `pii_detected` | `bool` | Whether personal data was detected in output |
| `safety_budget_remaining` | `float` | Remaining safety budget (0.0--1.0) |
| `session_id` | `str` | Stable session identifier |
| `window_id` | `str` | Turn-scoped window identifier |

??? example "Handle high-risk responses"
    ```python
    response = client.complete("Generate a medical diagnosis")

    if response.crp.risk == "CRITICAL":
        raise ValueError("Critical risk detected -- human review required")

    if not response.crp.grounded:
        print("Warning: response is not grounded in provided documents")
    ```

---

## Level 1 -- Quality (One New Concept: "knowledge")

Give CRP your documents, then ask questions with grounded, coherent answers.

```python
import crp

client = crp.SDKClient()

# Ingest documents, directories, URLs, or raw strings
client.ingest("./docs/")
client.ingest("https://example.com/spec.pdf")

# Ask questions -- CRP retrieves, reasons, and cites sources
answer = client.ask("Write a deployment guide")

print(answer.text)                     # The generated response
print(answer.quality)                  # S | A | B | C | D
print(answer.complete)                 # Did it cover the whole task?
print(answer.sources)                  # [{title, doc_id, used_facts, relevance_score}]
```

### Source attribution

Each source tells you exactly where the information came from:

```python
for src in answer.sources:
    print(f"{src.title} (relevance: {src.relevance_score:.2f})")
    print(f"  Used {src.used_facts} facts from doc {src.doc_id}")
```

!!! info "What happens behind the scenes"
    `ask()` runs the full CRP quality pipeline invisibly:
    1. **CDR** -- Contextual Document Retrieval finds relevant chunks
    2. **CDGR** -- Cross-Document Graph Reasoning connects facts across sources
    3. **STL** -- Semantic Topic Labelling positions the query in knowledge space
    4. **Continuation** -- Multi-turn coherence maintenance
    5. **Verification** -- Grounding check against source documents

---

## Level 2 -- Control

### Depth control

Control how thorough the response should be:

```python
# quick | standard | thorough | exhaustive
answer = client.ask("Explain transformers", depth="thorough")
```

| Depth | Use when | Behaviour |
|-------|----------|-----------|
| `quick` | Simple FAQs, low stakes | Short answer, low token cap |
| `standard` | General tasks | Balanced coverage |
| `thorough` | Complex analysis, research | Higher token cap, deeper envelope |
| `exhaustive` | Critical decisions, compliance | Continuation loop with gap analysis and stitching |

### Tool registration

Register Python functions as tools. They are invoked automatically during `complete()` and `ask()` when the provider supports tool calling.

```python
@client.tool
def search_docs(query: str) -> str:
    """Search internal documentation."""
    return vector_db.search(query)

@client.tool
def get_metrics(service: str) -> dict:
    """Get service health metrics."""
    return monitoring.get(service)

# Call directly
print(client.call_tool("get_metrics", "auth-service"))

# CRP invokes the tool automatically when the model asks for it
answer = client.ask("What does our auth service do?")
```

!!! tip "Tool outputs become context"
    Tool outputs are fed back to the model and also extracted into the warm store/CKF, so later questions in the same session can build on them.

[:octicons-arrow-right-24: Full Tools & Agents reference](../sdk/tools-and-agents.md)

### Reasoning transparency

Inspect how the answer was built:

```python
answer = client.ask("Should we use microservices?")

print(answer.how_it_was_built)   # simple construction summary
print(answer.open_questions)     # Gaps identified
print(answer.decisions)          # Trade-offs if available
```

??? tip "Use this for compliance documentation"
    `how_it_was_built` and `decisions` give you an audit-ready explanation of why the model produced a specific output. Save these for regulatory evidence packs.

### Application manifest

Most applications already have their own provider, tool registry, RAG pipeline,
or context-management strategy before CRP is introduced. Rather than discarding
that work, you can hand CRP an **ApplicationProfile** so it discovers or is told
what the application already does. CRP then:

- selects a compatible relay strategy (`push`, `reflexive`, `progressive`,
  `stream_augmented`, `agentic`) from the profile's `ContextStrategy`;
- resolves the right provider adapter from the profile's `ProviderKind`;
- emits a `CRP-Application-Context-Manifest` attestation on every dispatch;
- avoids duplicating existing retrieval or tool registries where possible.

#### Declared profile

```python
from crp.core.app_profile import ApplicationProfile, ProviderKind, ContextStrategy

profile = ApplicationProfile(
    framework="custom",
    provider=ProviderKind.OPENAI,
    provider_model="gpt-4o-mini",
    context_window=128_000,
    context_strategy=ContextStrategy.RAG,
)

client = crp.CRPClient(app_profile=profile)
```

#### Derived profile

```python
from crp.core.app_profile import build_profile_from_messages

profile = build_profile_from_messages(
    messages=[{"role": "user", "content": "Hello"}],
    tools=[{"type": "function", "function": {"name": "search_docs"}}],
    provider=ProviderKind.OPENAI,
    context_window=128_000,
)

client = crp.CRPClient(app_profile=profile)
```

#### Strategy mapping

| `ContextStrategy` | CRP dispatch path | Best for |
|-------------------|-------------------|----------|
| `rag` | `push` | Apps that already retrieve relevant chunks |
| `summarization` | `reflexive` | Apps that condense old turns |
| `sliding_window` | `progressive` | Apps that keep last N turns |
| `long_context` | `stream_augmented` | Apps relying on a huge native window |
| `hybrid` | `agentic` | Mixed strategies |
| `full_history` / `unknown` | `push` | Default safe path |

The manifest attestation is included automatically in `dispatch_router` when a
profile is present, so downstream evidence packs can record *which* application
context was active for each call.

---

## Configuration

CRP loads `crp.config.yaml` automatically if it exists in the working directory.

```yaml
# crp.config.yaml
version: "4"
model:
  default: gpt-4o-mini
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}

safety:
  profile: balanced

context:
  mode: auto
  depth: auto
  retrieval:
    min_relevance: 0.55

audit:
  enabled: true
  retention_days: 90
```

!!! note "Environment variable substitution"
    Values prefixed with `${}` are resolved from environment variables at load time.

### Safety profiles

| Profile | Description | Best for |
|---------|-------------|----------|
| `permissive` | Minimal intervention | Internal tools, low-risk domains |
| `balanced` | Default protection | Most production workloads |
| `strict` | Require approval, halt on injection/PII | Financial, legal, high-stakes |
| `research` | Informative logging, no halts | Experimentation, non-production |

Configure at init or runtime:

```python
client = crp.SDKClient(safety="strict")
# or
client.configure(safety.profile="strict")
```

---

## Session Persistence

The SDK maintains one session per client instance. Sequential calls share CKF state automatically.

```python
client = crp.SDKClient()

r1 = client.complete("What is the EU AI Act?")
print(r1.crp.session_id)

s = client.session()
print(s.id, s.fact_count, s.window_count)
```

!!! warning "Cross-process persistence"
    Explicit `crp.SDKClient(session=session_id)` resurrection and durable session persistence are not implemented. Use the Gateway or orchestrator persistence APIs for cross-process state.

---

## Streaming

Synchronous streaming is available via `client.stream()`. It yields
`StreamEvent` objects for tokens, continuation windows, and the final summary:

```python
for event in client.stream("Explain the CAP theorem"):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
```

See the [Streaming guide](streaming.md) for full event types and examples.
Async streaming (`aask_stream`) is not yet implemented.

---

## Multi-turn Conversations

Build conversational agents with persistent context:

```python
import crp

client = crp.SDKClient()

# Turn 1
r1 = client.ask("What is the EU AI Act?")
print(r1.text)

# Turn 2 -- context is automatic
r2 = client.ask("What are the penalties for non-compliance?")
print(r2.text)

# Turn 3 -- references earlier turns
r3 = client.ask("How does that compare to GDPR fines?")
print(r3.text)
```

!!! note "No explicit chat object"
    Multi-turn context is shared through the client instance. Use `client.session()` for a live view.

---

## CLI

The `crp` CLI provides governance tools without writing code:

```bash
# Scan a codebase for ungoverned AI calls
python -m crp scan --paths ./src --format sarif

# Start the HTTP sidecar
python -m crp serve

# Create a session, dispatch, ingest, preview envelope, status
python -m crp init
python -m crp dispatch --task "..."
python -m crp ingest --session <id>
python -m crp status --session <id>
python -m crp preview --session <id>
```

!!! warning "Commands not implemented"
    `validate`, `benchmark`, and `audit` CLI commands do **not** exist.

See the [CLI Guide](../getting-started/cli.md) for full reference.

---

## Error Handling

CRP uses graceful degradation. If a safety check fails, you get a governed response instead of a raw exception:

```python
import crp

client = crp.SDKClient()

response = client.complete("Generate a medical diagnosis")

if response.finish_reason == "error":
    print("Dispatch failed -- check logs")
    print(f"Risk level: {response.crp.risk}")
else:
    print(response.text)
```

!!! danger "Always check `.crp.risk`"
    Even when `finish_reason` is `stop`, the response may be `HIGH` or `CRITICAL` risk. Your application logic should decide whether to show, flag, or block the output.

---

## Next Steps

- [Quickstart](../getting-started/quickstart.md) -- Get running in 5 minutes
- [CLI Reference](../getting-started/cli.md) -- Command-line tools
- [Configuration](../sdk/configuration.md) -- `crp.config.yaml` reference
- [Error Reference](../sdk/errors.md) -- Exceptions and remediation

---

## API Reference

### `crp.SDKClient` (alias `crp.CRPClient`)

```python
class CRPClient:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        config: CRPConfig = CRPConfig(),
        safety: str | dict = "balanced",
        depth: str = "auto",
        model: str | None = None,
        api_key: str | None = None,
    )
```

### Methods

| Method | Level | Description |
|--------|-------|-------------|
| `complete(prompt, system="...", **kwargs)` | 0 | Single-turn completion with governance |
| `ask(question, system="...", depth=None, **kwargs)` | 1 | Multi-turn quality-aware query |
| `ingest(path)` | 1 | Ingest documents into CKF; returns `None` |
| `tool(fn)` | 2 | Decorator to register a callable tool |
| `call_tool(name, ...)` | 2 | Execute a registered tool |
| `session()` | 2 | Live session view |
| `configure(**kwargs)` | 2 | Runtime configuration overrides |
| `knowledge.*` | 2 | CKF search/query/health |
| `storage.*` | 2 | Warm-store visibility |
| `audit.*` | 3 | Tamper-evident audit trail |
| `compliance.*` | 3 | EU AI Act / ISO 42001 helpers |

### Response Types

**`CRPCompletionResponse`** (Level 0)
- `text: str` -- Generated text
- `crp: CRPResponseMeta` -- Governance summary
- `finish_reason: str` -- `stop` | `error` | `halted`
- `usage: dict` -- Token counts
- `raw_headers: dict` -- Raw response headers

**`CRPAskResponse`** (Level 1--2)
- All fields from `CRPCompletionResponse`, plus:
- `quality: str` -- `S` | `A` | `B` | `C` | `D`
- `sources: list[SourceAttribution]` -- Cited documents
- `complete: bool` -- Whether the whole task was covered
- `how_it_was_built: str` -- Simple construction summary
- `open_questions: list[str]` -- Identified gaps
- `decisions: list[dict]` -- Trade-off log if available

For the full progressive-disclosure specification, see
`SPECS_5_06_2026_CRP_v4/specs/CRP-SPEC-032-developer-experience.md`.
