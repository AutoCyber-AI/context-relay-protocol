# LLM Providers

CRP works with any LLM through a standard adapter interface. The SDK
auto-detects your provider from environment variables or a running local server,
so you can switch between OpenAI, Anthropic, and local models without changing
application code.

!!! info "Deployment status"
    Self-hosted provider keys are configured locally today. Managed SaaS routing
    through Gateway and Comply is on the waitlist at `*.crprotocol.io`.

## Auto-detection

When no provider is specified, `crp.SDKClient()` checks (in order):

1. `OPENAI_API_KEY` environment variable → OpenAI
2. `ANTHROPIC_API_KEY` environment variable → Anthropic
3. Ollama server at `localhost:11434` → Ollama
4. Model name pattern matching (e.g., `gpt-*` → OpenAI, `claude-*` → Anthropic)

```python
import crp

# Auto-detect from environment
client = crp.SDKClient()

# Auto-detect from model name
client = crp.SDKClient(model="gpt-4o-mini")
client = crp.SDKClient(model="claude-sonnet-4-20250514")
```

## OpenAI

```python
import crp

client = crp.SDKClient(provider="openai", model="gpt-4o-mini")

response = client.complete("What is the Context Relay Protocol?")
print(response.text)
print(f"Risk: {response.crp.risk}, Compliant: {response.crp.compliant}")
```

Supports: GPT-4o, GPT-4o-mini, GPT-4, o1, o3, and all OpenAI chat models.
Also works with Azure OpenAI via the `openai` SDK's Azure configuration.

## Anthropic

```python
import crp

client = crp.SDKClient(provider="anthropic", model="claude-sonnet-4-20250514")
response = client.complete("Summarize the EU AI Act.")
print(response.text)
```

Supports: Claude Opus, Claude Sonnet, Claude Haiku, and all Anthropic chat models.

## Ollama (Local)

```python
import crp

client = crp.SDKClient(provider="ollama", model="llama3.1")
response = client.complete("Review this Python function for bugs.")
print(response.text)
```

Requires Ollama running locally. No API key needed. Supports any model available
in your Ollama installation.

## llama.cpp

```python
import crp
from crp.providers import LlamaCppAdapter

client = crp.SDKClient(provider=LlamaCppAdapter(
    model_path="/path/to/model.gguf",
))
response = client.complete("Explain continuations.")
print(response.text)
```

Direct integration with llama.cpp for maximum control over local inference.

## Custom provider

Build your own provider for any LLM backend by passing a callable:

```python
import crp
from crp.providers import CustomProvider

def my_generate(messages, **kwargs):
    # Call your LLM API
    response = my_api.chat(messages)
    return response.text, response.finish_reason

def my_tokenizer(text):
    return len(text.split())  # Simple word-count tokenizer

provider = CustomProvider(
    generate_fn=my_generate,
    count_tokens_fn=my_tokenizer,
    context_size=128_000,
)
client = crp.SDKClient(provider=provider)
```

## Provider interface

All providers implement the `LLMProvider` abstract base class:

| Method | Required | Description |
|--------|----------|-------------|
| `generate_chat(messages, **kwargs)` | Yes | Generate a response. Returns `(output, finish_reason)` |
| `count_tokens(text)` | Yes | Count tokens in text |
| `context_window_size()` | Yes | Return max context window in tokens |
| `supports_tools()` | No | Whether the provider supports tool/function calling |
| `generate_chat_stream(messages, **kwargs)` | No | Streaming generation |
| `cost_per_1k_tokens()` | No | Returns `(input_cost, output_cost)` per 1K tokens |
