# CRPv6 Agent SDK — Usage Guide

The CRPv6 Agent SDK (`crp.Agent`) is a declarative surface for building governed, tool-using agents. You declare `tools + policy + model` once and write zero loop code.

---

## 1. Installation

```bash
pip install crprotocol
```

For the optional ML models:

```bash
pip install crprotocol[full]
```

For local-model support only:

```bash
pip install crprotocol[nlp]
```

---

## 2. Minimal example

```python
import crp


def get_weather(city: str) -> dict:
    """Fetch current weather for a city."""
    return {"city": city, "temp": 22, "condition": "sunny"}


agent = crp.Agent(model="local/llama3.1", tools=[get_weather])
result = agent.run("What's the weather in Sydney?")
print(result.answer)
print(result.how_it_was_built)
print(result.crp.risk)
```

---

## 3. `crp.Agent` constructor

```python
crp.Agent(
    model: str | LLMProvider | None = None,
    provider: LLMProvider | None = None,
    tools: list[Any] | None = None,
    policy: Policy | PolicyContext | None = None,
    system: str = "You are a helpful agent.",
    profile: CapabilityProfile | str | None = CapabilityProfile.FRONTIER,
    depth: str = "auto",          # quick | standard | thorough | exhaustive
    max_operations: int = 12,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    max_continuation_windows: int = 1,
    safety: str | dict[str, Any] | None = "balanced",
    intent_classifier: IntentClassifier | None = None,
)
```

Either `model` (string identifier resolved lazily) or `provider` (a CRP `LLMProvider` instance) must be supplied.

---

## 4. Tool registration

Tools can be:

### 4.1 Python callables

```python
def get_weather(city: str) -> dict:
    return {"city": city, "temp": 22}

agent = crp.Agent(provider=provider, tools=[get_weather])
```

The intent compiler reads the function signature and docstring to build:

- `capability_id` = function name
- `input_schema` from type hints and defaults
- `description` from the docstring

### 4.2 ToolSpec dicts

```python
from crp.agent_sdk.tool_manifest import ToolSpec
from crp.stl.classifier import STLOperation

spec = ToolSpec(
    capability_id="get_weather",
    description="Fetch current weather for a city.",
    input_schema={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
    output_schema={"type": "object"},
    operation_types=[STLOperation.RETRIEVE],
)

agent = crp.Agent(provider=provider, tools=[spec])
```

### 4.3 Chaining registrations

```python
agent = crp.Agent(provider=provider, tools=[])
agent.register_tool(get_weather).register_tool(get_time)
```

---

## 5. Running the agent

### 5.1 Synchronous run

```python
result = agent.run("What's the weather in Sydney?")
```

### 5.2 Streaming internal events

```python
for event in agent.run_stream("What's the weather in Sydney?"):
    print(event.kind, event.detail)
```

### 5.3 Transparency / AG-UI stream

```python
for event in agent.run_tel("What's the weather in Sydney?"):
    print(event.type, event.data)
```

This produces AG-UI-compatible lifecycle, text, tool, state, and CRP governance events.

### 5.4 Multi-turn with CSO relay

```python
r1 = agent.run("What is CRP?")
r2 = agent.run("How does it compare to MCP?")   # CSO from r1 is carried forward
```

The Cognitive State Object (`CSO`) is relayed automatically across calls on the same `Agent` instance.

---

## 6. `AgentResponse` fields

```python
result = agent.run("...")

result.text                 # final answer text
result.answer               # alias for text
result.cso                  # CognitiveStateObject
result.operations           # list of operations performed
result.headers              # CRP headers emitted
result.halted               # True if the run was halted
result.observation_count    # number of tool observations
result.frame_tokens_total   # tokens used in the positioned frame
result.continuation_windows # number of continuation windows
result.events               # internal AgentEvent list
result.usage                # token usage dict
result.crp                  # CRPResponseMeta (risk, grounded, fabrications, chain_valid)
result.verification         # VerificationRelay output (on thorough/exhaustive)
result.intent               # intent section (speech act, confidence, etc.)

# Convenience properties
result.sources              # tool observations as sources
result.decisions            # decisions recorded in the CSO
result.how_it_was_built     # narrative of operations
result.open_questions       # unresolved questions carried forward
result.complete             # True if finished without halting
```

---

## 7. Policy

```python
from crp.agent_sdk.policy import Policy
from crp.tools.descriptor import SafetyClass

policy = (
    Policy.strict()
    .block("dangerous_tool")
    .domain("eu_ai_act")
    .safety(SafetyClass.DESTRUCTIVE)
    .clarify(0.5)
)

agent = crp.Agent(provider=provider, tools=[get_weather], policy=policy)
```

Built-in policies:

- `Policy.balanced()` — warn on HIGH, halt on CRITICAL.
- `Policy.strict()` — halt on HIGH, require grounding, block fabrications.
- `Policy.permissive()` — halt only on CRITICAL.
- `Policy.grounded(threshold=0.6)` — require grounding confidence.

---

## 8. Capability profiles

Profiles bound how many tools are shown to the model at once:

```python
from crp.tools.profiles import CapabilityProfile

agent = crp.Agent(
    provider=provider,
    tools=[get_weather, get_time, search_web],
    profile=CapabilityProfile.SMALL_LOCAL,  # max 2 tools per frame
)
```

| Profile | Max tools per frame |
|---|---|
| `FRONTIER` | 7 |
| `CAPABLE_LOCAL` | 4 |
| `SMALL_LOCAL` | 2 |

---

## 9. Depth and verification

Depth controls reasoning thoroughness:

```python
agent = crp.Agent(provider=provider, depth="thorough")
```

| Depth | Verification Relay | Use case |
|---|---|---|
| `quick` | off | Chat, low-stakes |
| `standard` | off | General Q&A |
| `thorough` | on | Compliance, security review |
| `exhaustive` | on + symbolic | High-stakes reasoning |

Override per-run:

```python
result = agent.run("Prove this config is safe", verify=True)
```

---

## 10. Using with `CRPClient`

```python
import crp
from crp.sdk.client import CRPClient

client = CRPClient(provider=provider, depth="standard")
agent = client.make_agent(tools=[get_weather])
result = agent.run("Weather in Sydney?")
```

`make_agent()` binds the Agent to the client's provider and config.

---

## 11. Tool result envelope

The executor stores tool observations in the CSO. Each observation includes:

```python
{
    "capability_id": "get_weather",
    "payload": {"city": "Sydney", "temp": 22},
    "status": "ok",
    "invocation_id": "...",
}
```

Access via:

```python
for obs in result.cso.tool_observations:
    print(obs.to_dict())
```

---

## 12. Clarification protocol

When intent confidence is low or parse divergence is high, the agent returns a clarification response instead of guessing:

```python
result = agent.run("Scan it")   # ambiguous target
if result.halted and "Clarification" in str(result.headers):
    print(result.text)          # JSON with candidate interpretations
```

Configure threshold:

```python
agent = crp.Agent(provider=provider, policy=Policy.balanced().clarify(0.4))
```

---

## 13. Full example: local pentest recon agent

```python
import crp
from crp.agent_sdk.policy import Policy
from crp.tools.profiles import CapabilityProfile


def port_scan(target: str, ports: str = "top-100") -> dict:
    """Scan an authorised target for open ports."""
    return {"target": target, "open_ports": [22, 80, 443]}


def service_probe(target: str, port: int) -> dict:
    """Probe a specific port to identify the running service."""
    return {"target": target, "port": port, "service": "ssh"}


agent = crp.Agent(
    model="local/qwen2.5-7b",
    tools=[port_scan, service_probe],
    policy=Policy.strict().block("exploit_tool"),
    profile=CapabilityProfile.CAPABLE_LOCAL,
    depth="thorough",
    system="You are an authorised reconnaissance agent. Only scan in-scope targets.",
)

result = agent.run("Scan 10.10.14.20 and tell me what services are running.")
print(result.answer)
print("Risk:", result.crp.risk)
print("Sources:", result.sources)
```

---

## 14. Environment variables the Agent SDK honours

| Variable | Purpose |
|---|---|
| `CRP_INTENT_MODEL` | SetFit model for speech-act classification |
| `CRP_PRM_MODEL` | PRM verifier model |
| `CRP_NLI_MODEL` | NLI model for semantic entropy |
| `CRP_COREF_MODEL` | Coreference model (fastcoref-compatible) |
| `CRP_ML_DEVICE` | Device for managed ML (`auto`, `cpu`, `cuda`, `mps`) |
| `CRP_ML_CACHE_DIR` | Hugging Face cache directory |
| `CRP_LM_STUDIO_URL` | Base URL for LM Studio intent classifier fallback |
| `CRP_LM_STUDIO_MODEL` | Model name for LM Studio intent classifier |

---

## 15. When to use `crp.Agent` vs. `crp.SDKClient`

| Use case | Use |
|---|---|
| Drop-in governance wrapper around existing LLM calls | `crp.SDKClient` |
| Declarative tool-using agent with loop, policy, transparency | `crp.Agent` |
| Multi-turn assistant with memory, clarification, verification | `crp.Agent` |
| Gateway OpenAI-compatible API | `CapabilityRouter` + Gateway |

`crp.Agent` is the higher-level, v6-native surface. `crp.SDKClient` remains the lower-level orchestrator wrapper and can produce an Agent via `make_agent()`.
