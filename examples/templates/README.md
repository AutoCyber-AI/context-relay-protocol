# CRP Agent Templates

Ready-to-run agentic AI templates built on the CRP v6 Agent SDK. Every
template in this directory runs against a **real** LLM — LM Studio, OpenAI,
Anthropic, or Ollama — auto-detected by [`_shared.py`](_shared.py). None of
them depend on a scripted/mocked model: what you see is what the protocol
actually does.

## Prerequisites

```bash
pip install crprotocol requests beautifulsoup4
```

Then have ONE of the following available (the templates auto-detect in this order):

1. **LM Studio** — load any tool-calling model (e.g. `meta-llama-3.1-8b-instruct`, `qwen3-4b`) and start its local server (default `http://localhost:1234`).
2. **Ollama** — `ollama serve` (default `http://localhost:11434`).
3. `export OPENAI_API_KEY=...` or `export ANTHROPIC_API_KEY=...`

## The 3 flagship templates

These three are designed to each exercise a different slice of the full
protocol surface — tool use, streaming, memory, safety, verification — end
to end, on real-world agent shapes chosen because small/local models are
genuinely good at them (narrow, repetitive, tool-heavy tasks).

| Template | Real-world use case | Protocol features exercised |
|----------|---------------------|------------------------------|
| [`security_analyst_agent.py`](security_analyst_agent.py) | SOC/blue-team triage: look up a CVE, check threat intel, decide remediation | Tool Capability Fabric · **human-in-the-loop oversight gate** (`oversight_required` + `clarify_handler`) on a DESTRUCTIVE action · Verification Relay (`depth="thorough"`) · CSO memory relay across 3 turns · `run_tel()` AG-UI/governance event streaming · explicit `Policy` |
| [`research_assistant_agent.py`](research_assistant_agent.py) | Research any topic using the live web | Real `web_search`/`read_page` tools (DuckDuckGo, no API key) · ISA intent + **coreference resolution** ("the top result" → last turn's search) · CSO memory relay · Verification Relay · quality/source reporting |
| [`daily_assistant_agent.py`](daily_assistant_agent.py) | The most universally relatable shape: a personal daily/study assistant | Multi-tool fabric (weather, unit conversion, memory, quiz) · **CSO memory relay as the star feature** — recalls facts from 3+ turns back · `profile="small-local"` (tuned for genuinely small models) |

Run any of them directly:

```bash
python examples/templates/security_analyst_agent.py
python examples/templates/research_assistant_agent.py "your topic here"
python examples/templates/daily_assistant_agent.py
```

`security_analyst_agent.py` and `code_review_agent.py` both demonstrate the
oversight gate. Set `CRP_DEMO_DENY=1` to see the deny/halt path instead of
the approve path.

## The other 5 templates

Narrower, single-scenario references — still real, still runnable, useful
as smaller copy-paste starting points.

| Template | Use case | Notes |
|----------|----------|-------|
| [`customer_support_agent.py`](customer_support_agent.py) | Ticket triage + KB lookup | Builds a **fresh agent per ticket** — see the `new_agent()` docstring for why that matters (ISA turn-history isn't reset by `prior_cso=None`) |
| [`code_review_agent.py`](code_review_agent.py) | PR review with a real oversight gate on `merge_pr` | Same `oversight_required`/`clarify_handler` pattern as the security analyst template |
| [`data_analyst_agent.py`](data_analyst_agent.py) | CSV query + chart-spec generation | 3 single-tool turns with CSO carry-forward (more reliable than one combined multi-tool request) |
| [`research_report_agent.py`](research_report_agent.py) | Search → read → write a report section | Uses a small in-memory mock corpus (not live web) — see `research_assistant_agent.py` for the live-web version |
| [`local_slm_agent.py`](local_slm_agent.py) | Fully local via Ollama | Minimal example, no fallback providers |

## From template to product

Every template demonstrates the same CRP v6 contract:

1. **Declare tools + policy** once — plain Python callables, or a dict with
   an `"impl"` key + `cost_profile={"safety_class": "destructive"}` for an
   action that needs human sign-off.
2. **Run the positioned loop** with `agent.run(...)` (or stream it with
   `agent.run_tel()`).
3. **Carry the CSO** forward across turns with `prior_cso=result.cso` — or
   deliberately don't, for an independent case.
4. **Inspect governance** via `result.crp.risk`, `result.crp.grounded`, and
   `result.how_it_was_built`.

See [`docs/CRPv6_Agent_SDK_Usage_Guide.md`](../../docs/CRPv6_Agent_SDK_Usage_Guide.md)
and the root [`CHEATSHEET.md`](../../CHEATSHEET.md) for the full API reference.
