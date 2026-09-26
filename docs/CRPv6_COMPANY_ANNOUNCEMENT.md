# CRPv6 — Company Announcement Draft

> **Headline:** CRPv6 is live on PyPI. Build agents that think the way you want, and show your users exactly why.

---

## What we are announcing

We are releasing **CRPv6** — the latest version of the Context Relay Protocol — as `crprotocol 6.1.1` on PyPI. CRPv6 is a model-agnostic agentic SDK that turns any LLM into a governed, observable, user-configurable agent.

---

## The problem we solve

Today's AI agents hide their reasoning. They call tools as black boxes, forget rules between windows, and give users no audit trail. Developers who want transparency, safety, or custom reasoning have to rebuild the same scaffolding on top of every provider.

CRPv6 replaces that scaffolding with a single protocol.

---

## What CRPv6 actually is

- A **Python SDK** (`crp`) you install with `pip install crprotocol`.
- A **progressive agent API** — `crp.Agent(model=..., tools=..., preset=...)`.
- A **Tool Capability Fabric** that turns plain Python functions into structured tools.
- A **Semantic Task Layer** that classifies intent, plans operations, and runs them with small, positioned context windows.
- A **Transparency Emission Layer** that streams every step as AG-UI + CRP events.
- A **provenance chain** with per-window HMAC links.
- A **buildable agent console** that renders the chain-of-thought live.

---

## Two core selling points

### 1. User-defined reasoning, operating modes, and safeguards

CRPv6 lets developers and end users define how an agent thinks and acts through **cognitive presets**. A preset is a small YAML or Python declaration that specifies:

- identity, persona, and voice;
- reasoning phases (e.g. Understand → Research → Verify → Answer);
- operations per phase (RETRIEVE, ANALYSE, VERIFY, GENERATE, …);
- tools and knowledge bundles per phase;
- declarative safeguards with actions: warn, ask, or halt;
- emotional tone and affect rules;
- output length, format, tone, and citation style.

A two-line safeguard such as `Do not harm humans` becomes a runtime rule, not just prompt text. A reasoning scaffold such as `first understand, then break down, then explore sub-purposes, then research, then answer` becomes the agent's actual operating plan.

### 2. A live console that shows what is happening

The CRP Agent Console consumes the transparency event stream and renders:

- a readable chain-of-thought narrative;
- tool calls with full JSON arguments;
- tool results and source counts;
- governance cards (risk, grounding, chain validity, quality tier);
- a visual HMAC provenance chain;
- the raw AG-UI / CRP event stream for audit and debugging.

Every CRP run can output a Markdown narrative, a JSON event log, or a live web console.

---

## What is different

| Capability | CRPv6 | Typical agent framework |
|---|---|---|
| User-defined reasoning phases | yes, via presets | limited or prompt-only |
| Runtime safeguards | yes, with halt/ask/warn | mostly post-hoc filters |
| Per-window HMAC provenance | yes | rare |
| Model-agnostic governance | identical contract on any provider | often provider-specific |
| Live transparency stream | AG-UI + CRP events | usually black box |
| Unbounded context / generation | CDR/CDGR + continuation | single-context window |

---

## Who it is for

- **AI product builders** who need observable, governed agents without rebuilding infrastructure.
- **Enterprise teams** who need audit trails, safety rules, and regulatory alignment.
- **Researchers and tinkerers** who want to experiment with reasoning scaffolds on local models.

---

## Live proof (not a mock)

- `examples/crp_demos/unified_video_demo.py` runs a real LM Studio model and a live Open-Meteo API call side-by-side with a raw LLM call. Raw LLM emits tool JSON and does nothing; CRP executes the tool and returns live weather.
- `examples/crp_demos/sqb_benchmark.py --mode hosted` passes all three Semantic Quality Benchmark cases against the hosted API.
- The full non-live regression suite passes: **3277 passed, 1 skipped**.

---

## Market readiness

**What is functioning now:**

- `pip install crprotocol` works.
- `crp.Agent` works with LM Studio, OpenAI, Anthropic, Ollama, and custom providers.
- Tools are registered from plain Python functions and executed live.
- Presets load and shape reasoning.
- The transparency stream, narrative builder, and embedded console work.
- The SQB gate passes with the hosted model.
- The full non-live test suite passes.

**What remains before a hard marketing push:**

- Local 8B models are reliable for single-purpose prompts but fragile for compound tool tasks; use frontier models for polished demos.
- The CDN-hosted console is buildable but not yet backed by a public CDN.
- Gateway/Comply managed cloud (multi-tenant auth, billing, Stripe/Clerk webhooks) is Wave 3 work and not released.
- The robot-safeguard demo shows the preset is active, but small local models do not always obey the safeguard; frontier models behave more predictably.

**Bottom line:** CRPv6 is marketable today for developers, early adopters, and self-hosted products. The managed-cloud revenue layer is intentionally deferred to Wave 3.

---

## Call to action

```bash
pip install crprotocol
python examples/crp_demos/unified_video_demo.py
```

Define your agent's reasoning, wire up your tools, and stream the proof.

---

## Notes on secrets

The PyPI token shared for this session has not been committed to the repository. It should be moved to a GitHub secret or environment variable before any automated publish step.
