---
seo_title: "CRP Agent SDK — declarative agents with tools, policy, and SLM-first execution"
description: "Build governed, tool-using agents with crp.Agent. Declare Python tools + policy + model and let CRPv6 run the positioned loop. Works with local SLMs, OpenAI, Anthropic, and the CRP Gateway."
---

# CRP Agent SDK

`crp.Agent` is the CRPv6 declarative agent surface. You declare **tools + policy
+ model** once and the protocol runs the positioned loop, executes tools,
carries state forward, and emits governance metadata on every turn.

It is the fastest way to build agents that are **provably grounded,
auditable, and SLM-first**.

## One-line pitch

```python
import crp

agent = crp.Agent(tools=[get_weather, convert_temp], profile="small-local")
result = agent.run("What's the weather in Sydney?")
print(result.answer)                 # natural-language answer
print(result.how_it_was_built)       # operation chain
print(result.crp.risk)               # LOW | MEDIUM | HIGH | CRITICAL
print(result.crp.grounded)           # True if sourced from tools/facts
```

## Why `crp.Agent` over a raw tool loop

| Raw tool loop | CRPv6 Agent SDK |
|---------------|-----------------|
| You write prompt engineering, parser, retry, state, and safety glue. | Declare tools and policy; CRP builds the positioned frame. |
| Whole tool catalogue competes for context window. | Only the tools an operation needs are positioned per call. |
| Tool results are text; provenance is manual. | Every tool observation becomes a typed, grounded fact. |
| No built-in audit, safety, or continuation. | HMAC audit chain, safety surface, and continuation are automatic. |
| Works only on frontier models. | Same agent runs on 8B / 4B local models via LM Studio / Ollama. |

## Quick start

### 1. Install

```bash
pip install crprotocol
```

For local model support:

```bash
pip install crprotocol[full]
```

### 2. Declare an agent

```python
from __future__ import annotations

import crp


def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


agent = crp.Agent(
    model="local:llama-3.1-8b",
    tools=[get_weather],
    system="You are a helpful weather assistant.",
    profile="small-local",
)

result = agent.run("What is the weather in Sydney?")
print(result.answer)
```

### 3. Inspect governance

```python
print(result.crp.risk)            # LOW
print(result.crp.grounded)        # True
print(result.crp.chain_valid)       # True
print(result.how_it_was_built)    # retrieve
print(result.sources)             # tool observations with provenance
```

## Execution profiles

The `profile` argument tells CRP how many capabilities to place in each Tool
Positioning Frame (SPEC-049/050). Pick the one that matches your model.

| Profile | Use case | Max tools per frame |
|---------|----------|---------------------|
| `frontier` | GPT-4o, Claude, Gemini | 7 |
| `capable-local` | Qwen2.5-7B, Llama-3.1-8B | 4 |
| `small-local` | Qwen3-4B, Gemma-3-270M, Phi-4 | 2 |

## Multi-turn state relay

Carry the Cognitive State Object (CSO) across turns so the agent remembers prior
tool results without re-sending them in the prompt.

```python
step1 = agent.run("What is the weather in London?")
step2 = agent.run("What was the temperature I just asked about?", prior_cso=step1.cso)

print(step2.answer)
print(step2.how_it_was_built)   # may include recall or retrieve
```

## Local SLM proof

The CRPv6 Agent SDK has been proven live with LM Studio on:

- `meta-llama-3.1-8b-instruct`
- `qwen3-4b`

Example side-by-side demo:

```python
python examples/crp_demos/live_llm_vs_crp.py
```

The script runs the same task with the same model and tools:

- **Raw LLM** returns a JSON tool call and stops; the caller must parse and execute it.
- **CRPv6 Agent** executes the tool, returns a natural-language answer, and emits
  governance metadata.

Live test harness:

```python
python examples/crp_demos/live_agent_test_harness.py
```

## Agent templates

Ready-to-run templates are in `examples/templates/`:

- `customer_support_agent.py`
- `code_review_agent.py`
- `research_report_agent.py`
- `data_analyst_agent.py`
- `local_slm_agent.py`

Each template works with a mock provider out of the box and can be switched to a
real model by changing one line.

## Reference

- SPEC-049 — SLM Agent Execution Profile
- SPEC-050 — Tool Capability Fabric & Operation Orchestration
- SPEC-059 — Agent SDK
- `crp/agent_sdk/agent.py`
- `crp/tools/capability_fabric.py`
- `crp/stl/positioned.py`
