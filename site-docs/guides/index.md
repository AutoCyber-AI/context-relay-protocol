---
seo_title: CRP Guides — SDK, Ingestion, Streaming, Sidecar & Self-Hosting
description: Practical guides for using the CRP SDK, Gateway, ingestion, streaming, session persistence, and self-hosting.
---

# Guides

Practical, hands-on guides for using CRP in real-world scenarios. Each guide
focuses on a concrete outcome - running the demo, building multi-turn retrieval
sessions, or streaming tokens to a UI.

!!! info "Deployment status"
    All guides work with the self-hosted SDK today. Managed SaaS endpoints for
    Gateway and Comply are on the waitlist at `*.crprotocol.io`.

## Getting Started

| Guide | What You'll Learn |
|-------|------------------|
| [Demo App](demo-app.md) | Run the interactive demo to see CRP's safety, retrieval, and continuation features in action |
| [Streaming](streaming.md) | Stream tokens and continuation-window events with `client.stream()` |
| [Multi-Turn](multi-turn.md) | Build knowledge across multiple conversations with `client.ingest()` and `client.ask()` |

## Data & Persistence

| Guide | What You'll Learn |
|-------|------------------|
| [Ingestion](ingestion.md) | Feed external data into CRP without an LLM call |
| [Session Persistence](session-persistence.md) | Resume sessions across restarts with CKF cold storage |

## Deployment

| Guide | What You'll Learn |
|-------|------------------|
| [HTTP Sidecar](sidecar.md) | Run CRP as a REST API for cross-process integration |

## Prerequisites

All guides assume you have CRP installed:

```bash
pip install crprotocol
```

And a provider configured (see [Providers](../getting-started/providers.md) or
[Local Models & LM Studio](../getting-started/local-models.md)).

## The SDK in one page

```python
import crp

client = crp.SDKClient()            # auto-detects provider

# Single-turn generation
r = client.complete("Explain CRP.")
print(r.text, r.crp.risk, r.crp.grounded)

# Retrieval over ingested documents
client.ingest("./docs/")
a = client.ask("What does CRP govern?", depth="standard")
print(a.text, a.sources, a.crp.risk)

# Session inspection
s = client.session()
print(s.id, s.status(), s.fact_count, s.window_count)
```
