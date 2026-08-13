# Demos & Live Proofs

CRPv6 ships with a set of runnable demos that prove the protocol works against real
local language models. Each demo is a plain Python script; no managed cloud or paid
API key is required.

---

## Quick start: run the live SLM proof

1. Start LM Studio and load any 8B instruct model.
2. Run:

```bash
export CRP_LMSTUDIO_URL=http://localhost:1234/v1
export CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
python examples/crp_demos/live_crp_slm_proof.py
```

The script compares raw LLM output with CRPv6 output on four tasks:

- **Single tool** — execute one tool and return a natural answer.
- **Tool chain** — run two tools in sequence with real intermediate results.
- **RAG retrieval** — search a local knowledge base and synthesise an answer.
- **Long-form report** — produce a structured, non-repetitive multi-paragraph report.

For a step-by-step video guide, see the [Video Demo Guide](../crpv6/CRPv6_VIDEO_DEMO_GUIDE.md).

---

## All demos

| Demo | File | What it proves |
|------|------|----------------|
| Live SLM proof | `examples/crp_demos/live_crp_slm_proof.py` | Raw LLM vs. CRPv6 on 4 tasks with full governance output. |
| LLM vs. CRP | `examples/crp_demos/live_llm_vs_crp.py` | One-question side-by-side comparison. |
| Agent test harness | `examples/crp_demos/live_agent_test_harness.py` | 4-case pass/fail harness against a live SLM. |
| Real-world API research agent | `examples/agents/real_world_research_agent.py` | SLM agent calling live weather, crypto, and Wikipedia APIs (no API keys). |
| Real-world API proof | `examples/crp_demos/live_real_world_api_proof.py` | Side-by-side raw LLM vs. CRPv6 on live public APIs. |
| Weather agent | `examples/agents/slm_weather_agent.py` | SLM-ready agent with weather tools. |
| RAG agent | `examples/agents/slm_rag_agent.py` | SLM-ready RAG over an in-memory corpus. |
| Mock weather agent | `examples/agents/weather_agent.py` | Same agent, mock provider, works without a model. |
| Mock RAG agent | `examples/agents/rag_agent.py` | Same RAG agent, mock provider. |
| GDPR DSR agent | `examples/agents/gdpr_dsr_agent.py` | Sensitive workflow with checkpoint and audit. |
| Report agent | `examples/agents/report_agent.py` | Scan → summarise → report pipeline. |

---

## What is real vs. hardcoded

| Real | Hardcoded |
|------|-----------|
| Model output, both raw and CRP | Weather tool return value (`22°C and sunny`) so the demo works offline |
| CRP governance metadata | Pass/fail assertions in the harness |
| Tool selection and execution | Mock provider responses in non-live templates |
| RAG search results | Sample corpus documents |

The protocol's value is in the governance wrapper and tool loop, not in the sample
data. Hardcoded sample data is acceptable; hardcoded governance would defeat the point.

---

## Run the test suite

The non-live test suite proves the protocol without requiring API keys:

```bash
pytest tests/ -q --tb=short
```

Expected: 3232+ tests pass.

For a full public test/demo runbook, see the [Public Demo & Test Guide](../crpv6/CRPv6_PUBLIC_DEMO_AND_TEST_GUIDE.md).
