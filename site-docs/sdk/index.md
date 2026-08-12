---
seo_title: "CRP SDK Reference — Context Management, Safety & Tools"
description: "SDK reference for CRP: context management, AI safety, AIUC-1 aligned controls, tools and agents, configuration, async usage, and errors."
---

# CRP SDK Reference

The CRP SDK is the developer-facing surface for the entire Context Relay Protocol. It is designed around **progressive disclosure**: the common path is five lines of code, and every advanced capability across all 48 CRP specs is reachable through the same client. Every capability is **AIUC-1 aligned** where applicable, from real-time input filtering to tamper-evident audit export.

- **Level 0 - Governance:** drop-in replacement for OpenAI/Anthropic clients; every call becomes governed, risk-scored, and audited.
- **Level 1 - Quality:** give CRP knowledge, then ask questions with grounded, cited answers.
- **Level 2 - Control:** depth, tools, safety profiles, reasoning transparency, and output shaping.
- **Level 2+ - Agent SDK (SPEC-059):** declarative agents with `crp.Agent` — declare tools + policy + model and let the protocol run the positioned loop.
- **Level 3 - Infrastructure:** raw protocol headers, audit export, compliance evidence, conformance tests, amplification, and multi-agent safety budgets.

This reference is the canonical map from installation to every public capability. For task-oriented tutorials, see the [SDK Guide](../guides/sdk.md) and [Quickstart](../getting-started/quickstart.md).

!!! info "Implementation status"
    The CRP Python SDK is shipping with v6.0.0. CRPv6 Agent SDK (`crp.Agent`) is
    implemented, tested, and proven live with local SLMs. Advanced features such
    as amplification and agent-dispatch safety budgets are opt-in and declared
    upfront.

---

## Install

```bash
pip install crprotocol            # core SDK
pip install crprotocol[full]      # + local model support, all ingest formats
```

```python
import crp
print(crp.__version__)            # 6.0.0
```

!!! tip "Provider-agnostic"
    CRP does not replace your provider SDK. For hosted models install `openai` or `anthropic`; for local models point at LM Studio, Ollama, or vLLM.

---

## Level 0 - Governance

### 0.1 Drop-in with the OpenAI SDK

Point any OpenAI-compatible client at the CRP Gateway. Nothing else changes.

```python
from openai import OpenAI

client = OpenAI(
    api_key="crp_gw_...",
    base_url="https://your-gateway.example/v1",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

!!! note "Gateway availability"
    Managed cloud at `gateway.crprotocol.io` is on the waitlist. You can also self-host the
    Gateway runtime locally or in your own infrastructure.

### 0.2 Native client

```python
client = crp.SDKClient()                           # sane defaults, auto provider
client = crp.SDKClient(model="gpt-4o-mini")        # pick a model
client = crp.SDKClient(model="local:llama-3.1-8b") # local via LM Studio / Ollama
client = crp.SDKClient(api_key="crp_gw_...")       # hosted gateway
```

!!! warning "Legacy client"
    `crp.Client` is the legacy `CRPOrchestrator`. New code should use `crp.SDKClient` (also importable as `crp.CRPClient`).

### 0.3 Governance summary on every result

```python
r = client.complete("Summarise the EU AI Act")

r.text                  # the output string
r.crp.risk              # LOW | MEDIUM | HIGH | CRITICAL
r.crp.grounded          # bool
r.crp.fabrications      # count of unsupported invented claims
r.crp.compliant         # bool - passed configured compliance checks
r.crp.audit_url         # tamper-evident audit deep link
r.crp.chain_valid       # bool - HMAC provenance chain intact
r.crp.injection_detected # bool - prompt injection markers found
r.crp.pii_detected      # bool - personal data detected in output
r.crp.safety_budget_remaining # 0.0–1.0
```

### 0.4 Enforcement, not just reporting

Policy is enforced automatically. If a call violates a `halt-on` rule, CRP raises a first-class exception that carries the evidence.

```python
try:
    r = client.complete("...")
except crp.SecurityInvariantError as e:
    print(e.message)       # e.g. "CRITICAL hallucination risk"
    print(e.code)          # 1011
    print(e.details)       # evidence dict
```

---

## Level 1 - Quality

### 1.1 `ingest()` - give CRP knowledge

```python
client.ingest("./docs/")                       # directory (recursive)
client.ingest("manual.pdf")                    # single file
client.ingest("https://example.com/guide")     # URL
client.ingest("Raw text as a string")          # string
client.ingest(["a.md", "b.pdf", url, text])    # any mix
```

`ingest()` returns `None`. Extraction runs in the background; use `client.knowledge.health()` or `client.storage.overview()` to inspect progress.

### 1.2 `ask()` - the happy path

```python
a = client.ask("Write a complete guide to our deployment process")

a.text                 # full grounded output
a.quality              # S | A | B | C | D
a.sources              # [{title, doc_id, used_facts, relevance_score}]
a.complete             # bool - covered the whole task
a.crp                  # same governance summary as Level 0
```

Behind `ask()` the SDK runs task classification, CDR/CDGR retrieval, multi-window continuation with CSO relay, DPE verification, and assembly. The developer sees none of it.

### 1.3 Streaming

Use `client.stream()` for token-by-token output with continuation-window events.
Async streaming (`aask_stream`) is not yet implemented.

```python
for event in client.stream("Explain the CAP theorem"):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
```

See the [Streaming guide](../guides/streaming.md) for event types and examples.

### 1.4 Conversations

```python
client = crp.SDKClient()
r1 = client.complete("What is the EU AI Act?")
r2 = client.ask("Which articles apply to high-risk systems?")

# Both calls share the same session and CKF state.
s = client.session()
print(s.id, s.fact_count, s.window_count)
```

---

## Level 2 - Control

### 2.1 Depth

```python
client.ask("...", depth="quick")       # short answer, low token cap
client.ask("...", depth="standard")    # balanced coverage
client.ask("...", depth="thorough")    # higher token cap, deeper envelope
client.ask("...", depth="exhaustive")  # continuation loop with stitching
client.ask("...", depth="auto")        # default
```

### 2.2 Tools

```python
@client.tool
def get_metrics(service: str) -> dict:
    """Current CPU/memory for a service."""
    return fetch(service)

# Call the registered tool directly
metrics = client.call_tool("get_metrics", "payment-service")

# Or let the model invoke it during ask()
a = client.ask("Should we scale the payment service?")
```

!!! note "Tool support requires a tool-capable provider"
    Automatic tool invocation uses the provider's `generate_chat_with_tools()` path. `CustomProvider` and other providers that do not report `supports_tools()` will skip the tool loop and fall back to standard dispatch.

### 2.3 Safety

```python
client = crp.SDKClient(safety="balanced")   # default
client = crp.SDKClient(safety="strict")     # require approval, halt on injection/PII
client = crp.SDKClient(safety="permissive") # fully autonomous
client = crp.SDKClient(safety="research")   # informed logging, no halts

# Fine-grained
client = crp.SDKClient(safety={
    "profile": "strict",
    "alert_on_quality_below": "B",
})

# Runtime tuning
client.configure(safety.profile="strict")
```

!!! note "Safety enforcement"
    Safety profiles are mapped to the orchestrator's human-oversight configuration. Gateway deployments enforce the same profile via the `CRP-Safety-Policy` header.

### 2.4 Reasoning transparency

```python
a = client.ask("Design our database architecture")

a.decisions            # list of decisions / trade-offs if available
a.how_it_was_built     # simple human-readable construction summary
a.open_questions       # unresolved gaps
```

### 2.5 Application profile

Pass an existing application contract so CRP chooses the right provider,
strategy, and provenance attestation.

```python
from crp.core.app_profile import (
    ApplicationProfile,
    ProviderKind,
    ContextStrategy,
    build_profile_from_messages,
)

profile = ApplicationProfile(
    provider=ProviderKind.OPENAI,
    provider_model="gpt-4o-mini",
    context_window=128_000,
    context_strategy=ContextStrategy.RAG,
)
client = crp.CRPClient(app_profile=profile)

# Or derive it from existing messages/tools
profile = build_profile_from_messages(messages, tools=tools)
client = crp.CRPClient(app_profile=profile)
```

See the [SDK Guide](../guides/sdk.md#application-manifest) for the strategy
mapping and manifest attestation details.

### 2.6 Knowledge control

```python
client.knowledge.search("etcd")       # inspect what CRP knows
client.knowledge.query(...)           # CKF pattern query
client.knowledge.health()             # CKF health snapshot
client.knowledge.location             # "CKF"
```

### 2.7 Output shaping

!!! warning "Not yet implemented"
    `format`, `max_words`, `style`, and `schema` parameters are not currently implemented on `ask()`.

---

## Level 3 - Infrastructure

### 3.1 Raw protocol surface

```python
r = client.complete("...")
r.raw_headers          # raw response headers, including CRP-* when present
```

!!! warning "Partial surface"
    Full DPE report (`r.crp.dpe`), raw CSO (`r.crp.cso`), and envelope details (`r.crp.envelope`) are not exposed on `SDKClient` responses today.

### 3.2 Audit & provenance

```python
print(client.audit.summary())
print(client.audit.verify())         # (valid, broken_at_sequence)
export = client.audit.export()       # tamper-evident audit document
```

### 3.3 Compliance evidence

```python
assessment = client.compliance.classify(
    intended_purpose="Customer support chatbot",
    processes_personal_data=True,
)
report = client.compliance.report()
controls = client.compliance.controls()
```

### 3.4 Conformance

!!! warning "Not yet implemented"
    `crp.conformance.run()` and `crp.conformance.sqb()` are not exposed on the SDK client.

### 3.5 Amplification (opt-in, async)

!!! warning "Not yet implemented"
    `amplify`, `amplify_async`, and `client.amplify*` methods do not exist.

### 3.6 Multi-agent

The `client.agent` namespace exposes multi-agent safety budgets, delegation
checks, fan-in quality results, and oversight approvals:

```python
budget = client.agent.budget()
print(budget.health)
```

High-level `client.agent(role)` task dispatch is not yet implemented.

---

## Complete method map

```
SDKClient()
  .complete(prompt)              # single governed completion (Level 0)
  .stream(prompt)                 # synchronous streaming completion (Level 0)
  .ingest(source)                 # add knowledge (Level 1); returns None
  .ask(task)                      # happy path - full pipeline (Level 1)
  .tool / @client.tool            # register a tool (Level 2)
  .call_tool(name, ...)           # execute a registered tool (Level 2)
  .session()                      # live session view (Level 2)
  .knowledge.query()              # CKF pattern query (Level 2)
  .knowledge.search()             # semantic search (Level 2)
  .knowledge.health()             # CKF health snapshot (Level 2)
  .storage.overview()             # storage visibility (Level 2)
  .storage.fact_count()           # fact count (Level 2)
  .audit.export()                 # tamper-evident audit export (Level 3)
  .audit.verify()                 # HMAC chain verification (Level 3)
  .compliance.classify()          # EU AI Act risk classification (Level 3)
  .compliance.report()            # compliance status report (Level 3)

# Not yet implemented
  .ask_stream()                   # async streaming (planned)
  .agent(role)                    # multi-agent
  .amplify*                       # amplification
  .forget()                       # targeted erasure
  .last                           # most recent result object
```

---

## Namespace map

Every advanced subsystem is reachable through a typed namespace on the client. Each namespace is documented in the [API Reference](../api/index.md).

| Namespace | One-line description |
|-----------|----------------------|
| `client.activation` | Activation modes and onboarding stages. |
| `client.agent` | Multi-agent safety budgets and oversight chains. |
| `client.audit` | Tamper-evident audit trail export and verification. |
| `client.ckf` | Contextual Knowledge Fabric: search, query, and inspect the fact graph. |
| `client.compliance` | Regulatory classification and compliance reports. |
| `client.comply` | Comply Gateway client, quota gate, no-code governance, and billing webhooks. |
| `client.cso` | Cognitive State Object relay across continuation windows. |
| `client.events` | Observability event bus for telemetry and logging. |
| `client.extract` | Document and tool-result extraction pipeline. |
| `client.gateway` | Gateway session, router, and key vault accessors. |
| `client.headers` | CRP HTTP header emission, parsing, and halt detection. |
| `client.knowledge` | Semantic search and CKF health. |
| `client.observability` | Audit logs, metrics, telemetry, and structured logging. |
| `client.policy` | Safety policy enforcement, profiles, and violation reporting. |
| `client.providers` | Provider discovery, adapters, and selection. |
| `client.provenance` | Claim grounding, fabrication detection, and DPE controls. |
| `client.reasoning` | Meta-learning and reasoning-scaffolding controls. |
| `client.safety` | Safety rules, checkpoints, and human-in-the-loop control plane. |
| `client.scan` | GitHub App, remediation proposals, and semantic code ingestion. |
| `client.storage` | Warm-state visibility and fact counts. |
| `client.core` | Orchestrator, session, DAG, config, and manifest ledger. |
| `client.continuation` | Continuation manager, document map, flow, voice, and residual gap. |
| `client.envelope` | Envelope builder, packer, reranker, CDR, and formatter. |
| `client.state` | Warm store, cold storage, snapshots, event log, and facts. |
| `client.security` | Audit trail, consent, RBAC, checkpoints, and encryption. |
| `client.resources` | Adaptive allocator, cost model, and resource manager. |
| `client.advanced` | Curator, feedback, meta-learning, and source grounding. |
| `client.cli` | Sidecar handler and startup helpers. |
| `client.errors` | Public exception classes. |

---

## Full coverage escape hatches

The namespace proxies above cover the most common subsystems. For the remaining 1,400+ classes and 700+ functions, the client exposes two dynamic accessors:

| Accessor | What it reaches | Example |
|----------|-----------------|---------|
| `client.orchestrator` | The live `CRPOrchestrator` instance and all its subsystems | `client.orchestrator.dispatch(...)` |
| `client.modules` | Any public class/function in any `crp.*` module | `client.modules.envelope.cdr.cdr_rank(...)` |

These accessors are documented in the [API Reference](../api/index.md) and keep the SDK in sync automatically as the codebase grows.

---

## Design rules

1. **Level 0/1 methods require zero protocol vocabulary.** No "envelope", "window", "CDR", or "DPE" in signatures, return fields, or error messages.
2. **Every return object degrades gracefully.** `r.crp.risk` always exists, even in zero-CKF mode.
3. **Errors state what + why + the one fix.** No internal stack traces.
4. **Defaults are the product.** A developer who configures nothing gets safe, grounded output.
5. **Autocomplete is the documentation.** Level 2/3 capabilities are discoverable via IDE autocomplete.
6. **The OpenAI-compatible path is truly drop-in.** Swapping `base_url` changes nothing else.
7. **Async mirrors sync.** *(Planned - async methods are not yet implemented.)*
