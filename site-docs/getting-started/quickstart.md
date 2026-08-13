---
seo_title: CRP Quick Start — Governed AI in 5 Minutes
description: Get started with CRP in 5 minutes. Install the SDK, make your first governed AI call, and inspect safety headers.
---

# Quick Start

This guide walks you through your first CRP dispatch in 5 minutes.

## 1. Create a Client

```python
import crp

# Auto-detect provider from environment variables
client = crp.SDKClient()

# Or specify a model explicitly
client = crp.SDKClient(model="gpt-4o-mini")
```

CRP checks for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or a running Ollama server
and selects the appropriate provider automatically.

!!! warning "Legacy client"
    `crp.Client` is the legacy `CRPOrchestrator`. New code should use `crp.SDKClient`.

## 2. Ingest Domain Knowledge

```python
client.ingest("""
    Kubernetes uses etcd as its distributed key-value store for all cluster
    state. The API server is the only component that directly interacts with
    etcd. Pod scheduling is handled by kube-scheduler which considers resource
    requirements, affinity rules, taints, and tolerations.
""")

print(f"Facts in warm store: {client.storage.fact_count()}")
```

CRP's 6-stage extraction pipeline processes the text, identifies entities,
extracts structured facts, and stores them in the warm store.

## 3. Ask a Question

```python
answer = client.ask(
    "Explain Kubernetes pod networking architecture.",
    depth="thorough",          # quick | standard | thorough | exhaustive
)

print(answer.text)
print(f"Quality: {answer.quality}")       # S, A, B, C, or D
print(f"Sources used: {len(answer.sources)}")
print(f"Risk: {answer.crp.risk}")         # LOW, MEDIUM, HIGH, CRITICAL
```

CRP packs the most relevant facts into a context envelope, dispatches to the LLM,
runs the safety control plane, and handles continuation if the output is truncated.

## 4. Check Session Status

```python
s = client.session()
print(s.id, s.fact_count, s.window_count)
print(s.status())
```

## 5. Clean Up

```python
client.close()
```

## Build an Agent in 5 Lines

CRPv6 also ships a declarative `crp.Agent` surface for tool-using agents. The same code
runs on OpenAI, Anthropic, or a local SLM via LM Studio:

```python
import crp
from crp.providers.openai import OpenAIAdapter

def get_weather(city: str) -> str:
    return f"The weather in {city} is 22°C and sunny."

agent = crp.Agent(
    provider=OpenAIAdapter(
        model="meta-llama-3.1-8b-instruct",
        base_url="http://localhost:1234/v1",
        api_key="lm-studio",
    ),
    tools=[get_weather],
    profile="small-local",
)

result = agent.run("What's the weather in Sydney?")
print(result.answer)
print(result.operations)
print(result.crp.risk, result.crp.grounded, result.crp.chain_valid)
```

See the [Agent SDK reference](../sdk/agent-sdk.md) for profiles, multi-turn state,
templates, and the live SLM proof.

## Next Steps

- [SDK Guide](../guides/sdk.md) - progressive-disclosure SDK reference
- [Agent SDK](../sdk/agent-sdk.md) - declarative `crp.Agent` documentation
- [All 9 Dispatch Strategies](../protocol/dispatch-strategies.md) - choose the right
  strategy for your use case
- [Providers](providers.md) - configure different LLM backends
- [Compliance](../compliance/index.md) - EU AI Act and GDPR features
- [Live Demos](https://github.com/AutoCyber-AI/context-relay-protocol/tree/main/examples/crp_demos) -
  run the proof against a local SLM
