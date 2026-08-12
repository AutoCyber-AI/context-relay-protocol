<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Multi-Provider Usage

CRP supports multiple LLM providers through a unified adapter interface.

## Switching Providers

```python
import crp
from crp.providers import OpenAIAdapter, AnthropicAdapter, OllamaAdapter

# OpenAI (GPT-4o)
client = crp.Client(provider=OpenAIAdapter(model="gpt-4o"))

# Anthropic (Claude)
client = crp.Client(provider=AnthropicAdapter(model="claude-sonnet-4-20250514"))

# Ollama (local)
client = crp.Client(provider=OllamaAdapter(model="llama3.1"))

# Or use auto-detection via model name:
client = crp.Client(model="gpt-4o")        # → OpenAIAdapter
client = crp.Client(model="claude-sonnet-4-20250514")  # → AnthropicAdapter
client = crp.Client(model="llama3.1")       # → OllamaAdapter
```

## Manual Fallback

```python
from crp import Client
from crp.providers import OpenAIAdapter, OllamaAdapter

providers = [
    OpenAIAdapter(model="gpt-4o"),       # Primary (cloud)
    OllamaAdapter(model="llama3.1"),     # Fallback (local, $0)
]

for provider in providers:
    try:
        client = Client(provider=provider)
        output, report = client.dispatch(
            system_prompt="You are a data analyst.",
            task_input="Analyze this dataset: ..."
        )
        break  # Success
    except Exception:
        continue  # Try next provider
```

## Provider-Specific Configuration

Each adapter accepts provider-specific keyword parameters:

```python
OpenAIAdapter(
    model="gpt-4o",
    api_key="sk-...",              # Or set OPENAI_API_KEY env var
    base_url="https://...",        # For Azure, proxies, vLLM
    max_tokens=4096,               # Max output tokens
    timeout=120.0,                 # HTTP timeout (seconds)
)

AnthropicAdapter(
    model="claude-sonnet-4-20250514",
    api_key="sk-ant-...",          # Or set ANTHROPIC_API_KEY env var
    max_tokens=4096,
    timeout=120.0,
)

OllamaAdapter(
    model="llama3.1",
    base_url="http://localhost:11434",  # Or set OLLAMA_HOST env var
    context_size=32768,                 # Context window override
    max_tokens=2048,
    timeout=300.0,                      # Local models can be slow
)
```

## Custom Provider Interface

Building a custom provider requires implementing three methods:

```python
from crp.providers import LLMProvider

class MyProvider(LLMProvider):
    def generate_chat(self, messages: list[dict], **kwargs) -> tuple[str, str]:
        """Send messages to LLM, return (output_text, finish_reason)."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using this provider's tokenizer."""
        ...

    @property
    def context_window(self) -> int:
        """Return the model's context window size in tokens."""
        ...
```

Or use `CustomProvider` for quick integration:

```python
from crp.providers import CustomProvider

provider = CustomProvider(
    generate_fn=my_generate_function,
    count_tokens_fn=my_token_counter,
    context_size=8192,
)
client = crp.Client(provider=provider)
```
