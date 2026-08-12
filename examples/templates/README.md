# CRP Agent Templates

Ready-to-run agentic AI templates built on the CRP v6 Agent SDK.
Each template is a self-contained Python script with a mock SLM provider so you
can run it without API keys; swap the provider for OpenAI, Anthropic, Ollama,
or the CRP Gateway in one line.

## Prerequisites

```bash
pip install crprotocol
```

For the optional local-SLM template you will also need a running Ollama or
LM Studio instance.

## Templates

| Template | Use case | Key CRP features |
|----------|----------|------------------|
| `customer_support_agent.py` | Ticket triage + knowledge-base lookup | Tool fabric, CSO carry-forward |
| `code_review_agent.py` | PR review with policy + safety gates | Safety control plane, checkpoint |
| `research_report_agent.py` | Multi-step research → synthesis | Multi-horizon context, continuation |
| `data_analyst_agent.py` | CSV query + chart generation | Structured tool decoding |
| `local_slm_agent.py` | Runs entirely on a local model | SLM-first execution profile |

## Running a template

```bash
cd examples/templates
python customer_support_agent.py
```

## Swapping the provider

Replace the mock `CustomProvider` with any of these:

```python
# OpenAI
from crp.providers.openai_provider import OpenAIProvider
provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")

# Anthropic
from crp.providers.anthropic_provider import AnthropicProvider
provider = AnthropicProvider(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-3-haiku")

# Local Ollama
from crp.providers.ollama_provider import OllamaProvider
provider = OllamaProvider(model="llama3.1", base_url="http://localhost:11434")
```

## From template to product

Every template demonstrates the same CRP v6 contract:

1. **Declare tools + policy** once.
2. **Run the positioned loop** with `agent.run(...)`.
3. **Carry the CSO** forward across turns with `prior_cso=result.cso`.
4. **Inspect governance** via `result.crp.risk`, `result.crp.grounded`, and
   `result.how_it_was_built`.
