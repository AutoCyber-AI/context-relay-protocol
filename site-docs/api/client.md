# Client

The `SDKClient` class (also exported as `CRPClient`) is the main entry point
for the CRP progressive SDK. This page combines hand-written examples with
auto-generated reference docs from the source code.

## Quick example

```python
import crp

client = crp.SDKClient()
response = client.complete("Summarise the EU AI Act")
print(response.text)
print(response.crp.risk)   # LOW | MEDIUM | HIGH | CRITICAL
print(response.crp.grounded)
print(response.crp.fabrications)
```

## Auto-generated reference

::: crp.sdk.client.CRPClient
    options:
      show_source: false

## Response types

::: crp.sdk.response.CRPCompletionResponse
    options:
      show_source: false

::: crp.sdk.response.CRPAskResponse
    options:
      show_source: false

::: crp.sdk.response.CRPResponseMeta
    options:
      show_source: false

## Provider selection

`SDKClient` auto-detects the LLM provider from the environment:

| Source | Provider selected |
|--------|-------------------|
| `OPENAI_API_KEY` set | OpenAI |
| `ANTHROPIC_API_KEY` set | Anthropic |
| Ollama reachable on localhost | Ollama |

Override explicitly when needed:

```python
client = crp.SDKClient(provider="openai", model="gpt-4o")
```

## Session management

```python
s = client.session()
print(s.id)
print(s.status())
print(s.fact_count)
print(s.window_count)
```

## Configuration

```python
client.configure(safety_profile="strict")
```

Safety profiles adjust the trade-off between autonomy and oversight. See
[Safety and compliance](../sdk/ai-safety.md) and
[Configuration](../sdk/configuration.md) for details.
