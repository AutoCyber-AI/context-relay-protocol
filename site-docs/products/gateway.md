# CRP Gateway

**One line of code turns any LLM call into a governed, audited, continuation-aware AI system.**

CRP Gateway is a drop-in HTTPS proxy that sits between your application and any OpenAI-compatible provider. It adds the Decision Provenance Engine (DPE), Safety Control Plane, context envelope packing, automatic continuation, and tamper-evident audit trails - without touching your application logic.

!!! info "Status"
    **Managed cloud** at `gateway.crprotocol.io` is **on the waitlist**.
    Self-hosted and white-label deployments are available for Enterprise.
    [Contact sales →](mailto:sales@crprotocol.io)

---

## The value in one minute

| Without Gateway | With Gateway |
|-----------------|--------------|
| Every LLM call is a black box | Every call returns risk, grounding, and provenance |
| Output truncates; task stalls | Continuation engine finishes multi-section work automatically |
| Safety code is optional and scattered | Safety policy is enforced at the network boundary |
| Compliance evidence is manual | HMAC-chained audit events stream to CRP Comply |
| Context is flat text | CKF-scored envelope puts the most relevant facts first |

---

## Why teams choose CRP Gateway

- **Non-bypassable safety.** Because enforcement lives at the `base_url` boundary, application code cannot accidentally skip the DPE pipeline or Safety Policy evaluation.
- **Finish long tasks automatically.** The continuation engine detects output limits and dispatches fresh windows until the task is complete - 11.8× more output on the same model.
- **One integration, every provider.** OpenAI, Anthropic, Gemini, Ollama, vLLM, and any OpenAI-compatible endpoint get the same governance contract.

### Who it's for

| Role | Problem | How Gateway helps |
|------|---------|-------------------|
| **Platform Engineer** | Need governance without a full app rewrite | Change `base_url`; get safety, audit, and continuation instantly |
| **AI Product Manager** | Safety reviews slow down launches | Ship with risk scores and provenance from the first call |
| **CISO / Security Lead** | Can't enforce safety across scattered services | Centralised policy enforcement at the network boundary |
| **Startup CTO** | Need enterprise-grade governance on a budget | Start at $29/mo and scale usage without re-architecting |

---

## How it works

```text
┌──────────────┐     base_url = gateway     ┌─────────────────┐     vendor SDK     ┌────────────┐
│ Your App     │ ─────────────────────────► │ CRP Gateway     │ ─────────────────► │ OpenAI /   │
│ (no changes) │ ◄───────────────────────── │ DPE + Policy +  │ ◄───────────────── │ Anthropic /│
└──────────────┘   CRP-* headers added      │ Audit + Comply  │                    │ Local /…   │
                                            └─────────────────┘
```

1. **Your app sends a normal OpenAI request** to the Gateway URL.
2. **Gateway packs context** using CDR/CDGR retrieval and the maximally-saturated envelope.
3. **Safety Control Plane runs** 13+ checks in <50ms.
4. **DPE scores** hallucination risk, grounding, fabrications, and contradictions.
5. **If output hits a window limit**, the continuation engine starts the next window automatically.
6. **HMAC-signed audit events** are emitted to your configured store or CRP Comply.
7. **Your app receives a normal response** with extra `CRP-*` headers containing governance metadata.

---

## Integration options

### Option A: Change `base_url` (zero code changes)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-gateway.example/v1",  # or your self-hosted URL
    api_key="your-provider-api-key"
)

# Every call is now risk-scored, audited, and continuation-aware
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

### Option B: Use the native Python SDK

```python
import crp

client = crp.SDKClient(provider="openai", model="gpt-4o")
client.ingest("./docs/")
answer = client.ask("Write a deployment guide", depth="thorough")

print(answer.text)
print(answer.quality)   # S | A | B | C | D
print(answer.sources)   # cited facts from your documents
print(answer.crp.risk)  # LOW | MEDIUM | HIGH | CRITICAL
```

[:octicons-arrow-right-24: SDK Guide](../guides/sdk.md)

---

## What you get on every call

| Capability | What it does | Spec |
|------------|--------------|------|
| **Context envelope** | Packs the best facts into a dedicated task window | [SPEC-003](../spec/CRP-SPEC-003-envelope.md) |
| **CDR / CDGR retrieval** | Scored, graph-walked retrieval from CKF | [SPEC-005](../spec/CRP-SPEC-005-dpe.md) |
| **Continuation engine** | Auto-continues when output limits hit | [SPEC-004](../spec/CRP-SPEC-004-continuation.md) |
| **Safety policy enforcement** | Configurable halt/flag/audit actions | [SPEC-006](../spec/CRP-SPEC-006-safety-policy.md) |
| **DPE scoring** | Risk, grounding, fabrication, contradiction signals | [SPEC-005](../spec/CRP-SPEC-005-dpe.md) |
| **Audit trail** | HMAC-chained, tamper-evident event log | [SPEC-011](../spec/CRP-SPEC-011-audit-trail.md) |
| **Multi-agent safety** | Budget headers, chain provenance, cross-agent controls | [SPEC-012](../spec/CRP-SPEC-012-multi-agent-safety.md) |

---

## Deployment options

| Mode | When to use |
|------|-------------|
| **Self-hosted container** | You want the gateway inside your VPC / on-prem. |
| **Sidecar** | Per-pod injection in Kubernetes. |
| **Managed cloud** (`gateway.crprotocol.io`) | Fastest path - waitlist open. |
| **Edge** | Cloudflare Worker / Fastly Compute deployment for global low-latency *(roadmap)*. |

[:octicons-arrow-right-24: Self-hosting options →](../guides/gateway-railway.md)

---

## Compatible APIs

OpenAI Chat Completions, Anthropic Messages, Google Gemini, Mistral, Cohere,
Ollama, LM Studio, vLLM, TGI, and any OpenAI-compatible endpoint.

---

## Conformance

CRP Gateway is **Level 2 conformant** per [SPEC-014](../spec/CRP-SPEC-014-conformance.md).

---

## Get started

Use CRP Gateway self-hosted today, join the managed-cloud waitlist, or talk to sales about white-label deployments.

[Join waitlist →](mailto:info@crprotocol.io){ .md-button .md-button--primary }
[View Pricing →](../pricing.md){ .md-button }
[SDK Guide →](../guides/sdk.md){ .md-button }

---

## Pricing

See the [Pricing](../pricing.md) page for current Gateway plans and quotas.
