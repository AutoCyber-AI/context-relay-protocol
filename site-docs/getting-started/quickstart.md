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

## Next Steps

- [SDK Guide](../guides/sdk.md) - progressive-disclosure SDK reference
- [All 9 Dispatch Strategies](../protocol/dispatch-strategies.md) - choose the right
  strategy for your use case
- [Providers](providers.md) - configure different LLM backends
- [Compliance](../compliance/index.md) - EU AI Act and GDPR features
- [Demo App](https://github.com/AutoCyber-AI/context-relay-protocol/tree/main/examples/demo_app) -
  comprehensive interactive demo
