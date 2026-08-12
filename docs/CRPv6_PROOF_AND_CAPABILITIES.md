# CRPv6 — What It Is, What It Does, and Proof

This document is the single source of truth for launch claims about the Context
Relay Protocol v6. Every capability listed below is implemented in code and has
a reproducible proof step.

## The one-sentence claim

**CRPv6 is an open Python SDK and protocol that turns any LLM — including small
local models — into a governed, tool-using agent by giving each LLM call its own
positioned context envelope instead of stuffing everything into one shared window.**

## Core capabilities

| Capability | What it means | Proof |
|------------|---------------|-------|
| **Unbounded context** | Ingest documents larger than any model context window; CRP packs the right facts into each call. | `examples/ingestion.py`, benchmark continuation tests |
| **Unbounded generation** | Auto-continue when output hits token limits and stitch results transparently. | `examples/benchmark_continuation.py`, continuation tests |
| **Amplified reasoning** | Scaffold weak models with intent classification, step validation, and safety checks. | ML models on Hugging Face, `crp/ml/registry.py` |
| **Tool orchestration** | Declare typed Python tools once; CRP builds the Tool Capability Fabric and runs the loop. | `examples/templates/live_lmstudio_test.py` with LM Studio |
| **Governance by default** | Every window extends HMAC-signed provenance, safety surface, and audit chain. | `crp/security/`, `crp/provenance/`, audit tests |
| **SLM-first** | Same agent code runs on 8B local models and frontier APIs. | Live LM Studio test passes with `meta-llama-3.1-8b-instruct` and `qwen3-4b` |
| **Model-agnostic** | Swap provider in one line: OpenAI, Anthropic, Ollama, llama.cpp, LM Studio, custom. | Provider adapter tests |
| **Progressive SDK** | Start with `crp.Client()` drop-in, grow to `crp.Agent()` declarative agents. | `examples/quickstart.py`, `examples/agents/` |

## Managed ML models (Hugging Face `AutoCyberAI/`)

| Model | Purpose | Held-out metric |
|-------|---------|-----------------|
| `crp-intent-setfit` | Classify user intent into STL operation | 0.934 accuracy |
| `crp-prm-deberta-v1` | Score intermediate reasoning steps | AUC 0.793 (advisory) |
| `crp-safety-deberta-v1` | Detect policy / injection / unsafe inputs | 12/12 adversarial pass |

Load lazily via `crp.ml.registry.ModelManager` or `crp download-models`.

## Proof matrix

| Claim | How to verify | Command / location |
|-------|---------------|--------------------|
| Package installs from PyPI | `pip install crprotocol` and import | `python -c "import crp; print(crp.__version__)"` |
| Tests pass | Run non-live suite | `pytest tests/ -q` (3,232 passed, 3 skipped) |
| Agent SDK works with local SLM | LM Studio test | `python examples/templates/live_lmstudio_test.py` |
| Templates compile and lint | Ruff | `ruff check examples/templates/*.py` |
| Wheel / sdist build | Hatchling | `python -m hatchling build` |
| Safety surface is wired | Security tests | `pytest tests/test_security_modules.py tests/test_compliance_wiring.py` |
| Audit chain is unbroken | Decision provenance tests | `pytest tests/test_decision_provenance*.py` |

## What it is NOT

- CRP is **not** a model. It is middleware around your existing LLM.
- CRP is **not** a replacement for MCP or A2A. It is complementary:
  - MCP exposes tools; CRP positions which tools and context to use per call.
  - A2A connects agents; CRP orchestrates the context and reasoning inside each agent.
- CRP is **not** a hosted SaaS by default. The SDK runs locally/embedded; Gateway and
  Comply are optional hosted products.

## Launch-ready scope

For the protocol/SDK launch, CRPv6 is ready:

- Core protocol: implemented, tested, documented.
- ML models: trained, published, lazy-loadable.
- Agent SDK: declarative agents, tool fabric, state relay, live SLM proof.
- PyPI package: `crprotocol 6.0.0` published.
- Examples + templates: ready-to-run, mock + live provider variants.
- LinkedIn campaign: 8-post series drafted.

For the hosted SaaS (Gateway + Comply + Scan money funnel), Wave 3 hardening
remains. The protocol launch does not block on that.

## How to demo in 60 seconds

```bash
pip install crprotocol
python -m crp download-models
python examples/templates/live_lmstudio_test.py
```

With a local LM Studio server running, the script proves an 8B model can act
as a tool-using agent with CRP governance.
