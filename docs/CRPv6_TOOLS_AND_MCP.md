# CRPv6 Tools — Definition, Connection, and MCP Relationship

> This document answers the concrete question: *"I wrote a Python function. How
> does CRP know it is a tool? Does CRP use MCP? How can I be certain the tool
> is properly connected and used?"*

---

## 1. The short answer

CRP has **its own** tool system called the **Tool Capability Fabric (TCF)**. You
pass Python functions to `crp.Agent(tools=[...])` and CRP turns them into
machine-readable descriptors. The agent loop asks the LLM to pick one by
`capability_id`, then CRP executes the matching function.

MCP is **optional**. CRPv6 ships a separate `crp_mcp/` bridge so you can:
- expose CRP tools as MCP servers, and
- import MCP servers as CRP tools.

But you do **not** need MCP to use CRP tools.

---

## 2. How a Python function becomes a CRP tool

### 2.1 Minimal example

```python
import crp

def get_weather(city: str) -> dict:
    """Fetch current weather for a city."""
    return {"city": city, "condition": "sunny", "temp_c": 22}

agent = crp.Agent(
    model="local/llama3.1",
    tools=[get_weather],
)
```

### 2.2 What CRP extracts automatically

`compile_tools()` in `crp.agent_sdk.intent_compiler` inspects the function:

| Source | CRP uses it as |
|--------|---------------|
| `function.__name__` | `capability_id` |
| First line of `function.__doc__` | description |
| Type hints on arguments | JSON Schema `input_schema` |
| Return annotation | JSON Schema `output_schema` |

So the function *is* the tool definition. No decorator, no YAML, no separate
schema file is required.

### 2.3 Three equivalent forms

```python
import crp
from crp.tools.descriptor import CapabilityDescriptor

# Form 1: plain callable
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

# Form 2: dict with implementation
tool_dict = {
    "capability_id": "add",
    "description": "Add two integers.",
    "input_schema": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
    "output_schema": {"type": "integer"},
    "impl": add,
}

# Form 3: full CapabilityDescriptor
desc = CapabilityDescriptor(
    capability_id="add",
    description="Add two integers.",
    input_schema={...},
    output_schema={...},
    cost_profile=CostProfile(safety_class=SafetyClass.READ_ONLY),
)

agent = crp.Agent(tools=[add, tool_dict, desc])
```

---

## 3. How CRP ensures the tool is properly connected

### 3.1 Registration happens at agent construction

When `crp.Agent(tools=[...])` is called:

1. `compile_tools()` converts each source into a `CompiledTool`.
2. The agent builds a `ToolCapabilityFabric` with all compiled tools.
3. The `CapabilityExecutor` stores the original callable/impl in `_tools_by_id`.

### 3.2 Verify at runtime

```python
agent = crp.Agent(tools=[get_weather, calculate])

# All registered capability ids
print(agent._fabric.capability_ids)
# {'get_weather', 'calculate'}

# Descriptor for a specific tool
print(agent._fabric.describe("get_weather"))

# Direct execution without the LLM
print(agent._executor.call("get_weather", {"city": "Sydney"}))
```

### 3.3 What happens if the model picks an unknown capability

The positioned loop only offers registered capability ids to the model. If the
model ignores the prompt and emits an unknown id, the loop logs a warning and
retries. If it keeps failing, the run halts rather than executing arbitrary
code.

### 3.4 Tools from other files / modules

There is no magic directory scanning. Tools are connected by Python object
identity at the moment you pass them to `crp.Agent`:

```python
# my_tools.py
def search_web(query: str) -> list[dict]: ...

# main.py
from my_tools import search_web
import crp

agent = crp.Agent(tools=[search_web])
```

As long as the function object is imported and passed to `tools=[...]`, it is
connected. If you only put the function name in a list as a string, it will not
work — CRP expects the actual callable.

---

## 4. CRP vs MCP — relationship

### 4.1 They are independent protocols

| | CRP TCF | MCP |
|---|---|---|
| Purpose | Tool selection + execution inside the CRP agent loop | Tool description and invocation between separate processes/hosts |
| Scope | Inside one Python process | Inter-process / network |
| Schema | Derived from Python signatures | JSON-RPC style tool schema |
| Execution | Direct Python call | `mcp_client.call_tool()` |
| Required? | No | No |

### 4.2 When to use MCP with CRP

Use MCP when you have:
- Tools implemented in another language or service.
- Tools you want to share across multiple AI systems, not just CRP.
- A need for dynamic discovery from a remote server.

Use native CRP tools when:
- The tool is a Python function in the same process.
- You want lower latency.
- You want the CRP safety/policy layer to govern the tool.

### 4.3 How the bridge works

`crp_mcp/` contains:
- `connectors/mcp_to_crp.py` — wrap an MCP client as a CRP tool source.
- `connectors/crp_to_mcp.py` — expose CRP's `ToolCapabilityFabric` as an MCP server.

Example: import an MCP server as CRP tools

```python
import crp
from crp_mcp.connectors.mcp_to_crp import load_mcp_tools

tools = load_mcp_tools(command=["python", "-m", "my_mcp_server"])
agent = crp.Agent(tools=tools)
```

---

## 5. Live verification

Run the unified demo to see tools connected and executed against a real model:

```bash
python examples/crp_demos/unified_video_demo.py "What is the weather in Sydney and what is 12 times 7?"
```

Expected output:
- Raw LLM emits JSON tool-call strings but **does not execute** them.
- CRP agent calls `get_weather` and `calculate`, gets real data, and answers.

The generated `_unified_demo.json` contains the exact tool calls and results.

---

## 6. Summary

- CRP tools are Python functions passed directly to `crp.Agent(tools=[...])`.
- CRP compiles signatures/docstrings into descriptors automatically.
- The `ToolCapabilityFabric` ensures only registered tools can be selected.
- MCP is optional; CRP has its own execution fabric and a separate bridge.
- To be certain a tool is connected, inspect `agent._fabric.capability_ids` or
  run the live demo and read the produced artifact.
