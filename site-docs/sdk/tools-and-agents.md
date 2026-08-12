# Tools & Agents

The CRP SDK gives LLM calls access to external tools while keeping the same
progressive-disclosure design. You register Python functions, the SDK dispatches
them when the model asks for a tool, and the results flow back into CKF as
structured facts.

!!! tip "CRPv6 Agent SDK"
    For the modern declarative agent surface, see the dedicated
    [Agent SDK reference](agent-sdk.md). The page below documents the lower-level
    `crp.SDKClient` tool loop.

---

## Register a tool

Use the `@client.tool` decorator to expose a plain Python function to the model:

```python
import crp

client = crp.SDKClient()

@client.tool
def search_knowledge(query: str) -> str:
    """Search the ingested knowledge base."""
    hits = client.knowledge.search(query, top_k=5)
    return "\n".join(f"- {h['fact']}" for h in hits)

@client.tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    return str(eval(expression, {"__builtins__": {}}, {}))
```

CRP derives the JSON Schema for the tool from the function signature and
docstring. The tool is automatically offered to providers that support tool
calling.

---

## Automatic tool loop

When you call `complete()` or `ask()` and the provider supports tool calling,
the SDK will:

1. Send the user message and available tools to the model.
2. If the model requests a tool, execute the registered function.
3. Extract structured facts from the tool result and add them to CKF.
4. Send the tool result back to the model.
5. Repeat until the model produces a final answer.

```python
answer = client.ask(
    "What is 153 * 42, and which docs mention the scheduler?",
    depth="standard",
)

print(answer.text)
print(answer.sources)   # includes tool result citations
print(answer.quality)   # S/A/B/C/D
```

Tool outputs are treated as first-class context: they are ranked, scored, and
packed into subsequent envelopes exactly like ingested documents.

---

## Positioned tool loop (v5)

CRP v5 adds `dispatch_positioned()` — a **positioned** agentic loop for small and
local models (SPEC-049/050). Instead of injecting the whole tool catalogue into the
prompt, CRP classifies the request into operations and positions the model on **one
operation at a time with only the 1–3 tools that operation needs**. Each tool result
becomes a typed fact in a Cognitive State Object (CSO), so the working window stays
**bounded** no matter how many tools run — *positioning, not injection*.

```python
import crp

client = crp.SDKClient(provider=my_provider)

@client.tool
def lookup_port_service(port: str) -> dict:
    """Map a TCP port to its well-known service."""
    return {"port": port, "service": {"443": "HTTPS", "22": "SSH"}.get(port, "unknown")}

result = client.dispatch_positioned(
    "Look up the service on port 443, then summarise what it is used for."
)

print(result.text)                 # assembled answer
print(result.operations)           # e.g. ['retrieve', 'synthesise']
print(result.observation_count)    # typed CSO observations stored
print(result.frame_tokens_total)   # bounded per-operation window size
print(result.headers)              # CRP-Agent-Operation-State / -Plan / -Type …
for e in result.event_stream:      # live visibility == audit
    print(e["state"], e["operation"], e["detail"])
```

`dispatch_positioned()` returns a `PositionedResult` with `.text`, `.cso`,
`.event_stream`, `.operations`, `.observation_count`, `.frame_tokens_total`,
`.continuation_windows`, `.headers`, and `.halted`.

### Multi-turn (state relay)

The easiest way to run a multi-turn agent is `client.conversation()`, which relays the
Cognitive State Object forward automatically — no manual state threading:

```python
convo = client.conversation()
r1 = convo.say("Look up the service on port 443.")
r2 = convo.say("Based on what we found, is it safe for a login page?")
print(convo.turns)   # 2
```

If you prefer explicit control, pass the previous result's `.cso` as `prior_cso`:

```python
turn1 = client.dispatch_positioned("Look up the service on port 443.")
turn2 = client.dispatch_positioned(
    "Based on what we found, is it safe for a login page?",
    prior_cso=turn1.cso,          # ← carry state forward
)
```

### Output continuation (long generations)

For long documents, allow the operation to span multiple windows. CRP re-positions
each window with the residual task and stops when the output is structurally complete
(or the cap is hit). The working prompt stays bounded across all windows:

```python
result = client.dispatch_positioned(
    "Write a comprehensive multi-section guide to Kubernetes networking.",
    max_continuation_windows=10,
)
print(result.continuation_windows)   # e.g. 10
print(result.headers["CRP-Continuation-Windows"])
```

### Safety checkpoints & oversight

Gate destructive or mutating tools behind a human-in-the-loop checkpoint. When the
model selects a gated capability, CRP raises a CLARIFY checkpoint; your handler
approves or rejects it, and rejection halts safely (never a raw error):

```python
from crp.tools import SafetyClass

def approve(request) -> "ClarificationResolution":
    # show request.question to a human; return their decision
    from crp.security.clarify import ClarificationResolution, ClarificationAction
    return ClarificationResolution(action=ClarificationAction.ANSWER, answer="approve")

result = client.dispatch_positioned(
    "Delete stale records.",
    oversight_required={SafetyClass.DESTRUCTIVE},
    clarify_handler=approve,
)
print(result.halted)   # True if the checkpoint rejected the action
```

Preventive-safety halts, policy pre-filters (`policy=PolicyContext(...)`), and
resource-governed profiles (`governor=ResourceGovernor()`) compose the same way.

---

## Tool result extraction

After a tool runs, CRP applies a lightweight extraction pipeline to turn the
raw output into typed facts:

| Stage | What it does |
|-------|--------------|
| Regex | Dates, identifiers, numbers |
| NER | Named entities (GLiNER) |
| Relations | Subject-verb-object triples |
| Discourse | RST structure for long outputs |
| Relational | LLM-assisted fact consolidation |

These facts are stored in the warm CKF layer and become candidates for future
retrieval.

---

## Multi-turn agents

For agentic workflows, combine tools with `ask()` and session persistence:

```python
with crp.SDKClient() as client:
    client.ingest("./docs/")

    # Turn 1: plan
    plan = client.ask("Plan a 10-section Kubernetes troubleshooting guide")

    # Turn 2: execute with tools
    for section in plan.decisions:
        result = client.ask(
            f"Write section: {section}",
            depth="thorough",
        )
        print(result.text)

    # Session status and audit trail
    print(client.session().status())
    print(client.audit.summary())
```

The session object keeps window history, fact graph, and audit trail across
turns.

---

## Agent namespace

`client.agent` exposes multi-agent safety budgets and oversight primitives without requiring you to construct them manually:

```python
budget = client.agent.budget(role="researcher")
print(budget.remaining)
print(budget.allow_dispatch())
```

## Providers namespace

`client.providers` lets you inspect and select LLM providers at runtime:

```python
print(client.providers.list_available())
adapter = client.providers.get("openai")
print(adapter.context_window_size)
```

## Safety and budgets

Every tool call inherits the active safety profile:

```python
client.configure(safety_profile="strict")
```

- Input to tools is scanned for PII and injection.
- Tool outputs are checked against the same DPE pipeline as model outputs.
- Multi-agent budgets can be enforced via headers when using the Gateway.

---

## Declarative agents with `crp.Agent` (SPEC-059)

For full agentic workflows, use `crp.Agent`. Declare the model, tools, and policy once; the protocol runs the positioned loop, selects capabilities, enforces safety, and carries state across turns.

```python
import crp

def get_weather(city: str) -> dict:
    """Return current weather for a city."""
    return {"city": city, "temperature_c": 22, "condition": "sunny"}

agent = crp.Agent(
    model="local/llama-3.1-8b",
    tools=[get_weather],
    system="You are a helpful weather assistant.",
    profile="capable-local",   # or "frontier", "small-local"
)

result = agent.run("What's the weather in Sydney?")
print(result.answer)
print(result.how_it_was_built)   # e.g. "retrieve → generate"
print(len(result.sources))       # tool observations stored in CSO
```

Reference implementations that run without an API key are in
[`examples/agents/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/main/examples/agents):
[`weather_agent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/examples/agents/weather_agent.py),
[`rag_agent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/examples/agents/rag_agent.py)
(search → read with CSO carry-forward),
[`gdpr_dsr_agent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/examples/agents/gdpr_dsr_agent.py)
(list / export / deletion-token gate), and
[`report_agent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/examples/agents/report_agent.py)
(scan → summarize → report).

### Multi-turn state relay

Pass the previous result's CSO to the next turn, or use `agent.run()` repeatedly — the agent keeps the last CSO automatically.

```python
r1 = agent.run("What's the weather in Sydney?")
r2 = agent.run("Convert that temperature to Fahrenheit", prior_cso=r1.cso)
print(r2.answer)
```

### Capability profiles

The `profile` argument tells the protocol how much scaffolding the model needs:

| Profile | Tools per frame | Best for |
|---|---|---|
| `frontier` | 5–7 | Claude, GPT-4o, large tool-tuned models |
| `capable-local` | 3–4 | 8–14 B local models (Qwen, Llama, xLAM) |
| `small-local` | 1–2 | ≤8 B local models, constrained decoding on |

### Policy and safety

```python
from crp.agent_sdk import Policy

agent = crp.Agent(
    model="local/llama-3.1-8b",
    tools=[get_weather, delete_record],
    policy=Policy.strict(),  # or Policy.balanced(), Policy.grounded(0.8)
    profile="capable-local",
)
```

Destructive or irreversible tools are gated by the policy before execution; rejection returns a safe `halted` response rather than a raw error. Use the fluent API for fine-grained control:

```python
from crp.agent_sdk import Policy
from crp.tools.descriptor import SafetyClass

policy = (
    Policy.balanced()
    .scope("10.0.0.0/24")
    .approve_sinks("soc@example.com")
    .block("web_search")
    .safety(SafetyClass.IRREVERSIBLE)
)
```

### Typed tool manifest

For explicit control over the descriptor passed to the model, use `ToolSpec`:

```python
from crp.agent_sdk import ToolSpec
from crp.stl.classifier import STLOperation

spec = ToolSpec(
    capability_id="query_regulation",
    name="Query regulation corpus",
    description="Find articles relevant to a topic.",
    input_schema={"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
    output_schema={"type": "object", "properties": {"articles": {"type": "array", "items": {"type": "string"}}}},
    operation_types=[STLOperation.RETRIEVE],
)
```

### Transparency stream

```python
for event in agent.run_stream("What's the weather in Sydney?"):
    print(event.kind, event.operation, event.detail)
```

`run_stream()` yields `AgentEvent` objects for intent classification, operation positioning, tool selection, verification, and completion.

---

## What is implemented today

| Feature | Status | Notes |
|---------|--------|-------|
| `@client.tool` registration | ✅ Implemented | Schema derived from signature |
| Automatic tool loop | ✅ Implemented | Provider tool-calling only |
| Tool result extraction to CKF | ✅ Implemented | Via extraction pipeline |
| Multi-turn `ask()` | ✅ Implemented | Session state persists |
| Manual `call_tool()` | ✅ Implemented | For explicit tool execution |
| Declarative `crp.Agent` | ✅ Implemented | SPEC-059 — tools + policy + model |
| Parallel tool calls | ⚠️ Partial | Sequential loop today |
| Streaming tool events | ✅ Implemented | `agent.run_stream()` and TEL stream |

---

## Design rule

CRP never modifies LLM output. Tool results are extracted into CKF, but the
original model text is returned untouched. This preserves Axiom 9 (output
integrity) while still giving the system structured memory of what the tool
produced.

[:octicons-arrow-right-24: Context Management](context-management.md)
[:octicons-arrow-right-24: AI Safety](ai-safety.md)
