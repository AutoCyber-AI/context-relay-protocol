<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Local Model Setup

CRP works with any local LLM with zero configuration. No API keys, no cloud, no cost.

## Ollama (Recommended)

```bash
# Install Ollama: https://ollama.ai
ollama pull llama3.1
```

```python
import crp

# Auto-detects running Ollama on localhost:11434
client = crp.Client(model="llama3.1")

output, report = client.dispatch(
    system_prompt="You are a code reviewer.",
    task_input="Review this function for bugs: ..."
)
```

### Custom Ollama Settings

```python
from crp import Client
from crp.providers import OllamaAdapter

client = Client(provider=OllamaAdapter(
    base_url="http://192.168.1.100:11434",  # Remote Ollama server
    model="codellama",                       # Specific model
))
```

## llama.cpp

```bash
# Start llama.cpp server
./llama-server -m model.gguf -c 8192 --port 8080
```

```python
from crp import Client
from crp.providers import LlamaCppAdapter

client = Client(provider=LlamaCppAdapter(server_url="http://localhost:8080"))

output, report = client.dispatch(
    system_prompt="You are a security analyst.",
    task_input="Analyze these scan results: ..."
)
```

## vLLM / TGI / Any OpenAI-Compatible Server

```bash
# Start vLLM server (exposes OpenAI-compatible API)
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct
```

```python
from crp import Client
from crp.providers import OpenAIAdapter

# vLLM/TGI expose OpenAI-compatible APIs — use OpenAIAdapter with base_url
client = Client(provider=OpenAIAdapter(
    model="meta-llama/Llama-3.1-8B-Instruct",
    base_url="http://localhost:8000/v1",
    api_key="dummy",  # vLLM doesn't require a real key
))
```

## Any Custom Function

```python
from crp import Client
from crp.providers import CustomProvider

def my_llm(messages, **kwargs):
    # Your custom LLM call — return (text, finish_reason)
    return ("response text", "stop")

client = Client(provider=CustomProvider(
    generate_fn=my_llm,
    count_tokens_fn=lambda text: len(text) // 4,
    context_size=8192,
))
```

## Notes

- CRP auto-detects the model's context window size from the provider
- All extraction runs locally — no data leaves your machine
- Embedding model (all-MiniLM-L6-v2, ~80MB) downloads automatically on first use
- GLiNER and UIE models are optional and lazy-loaded only when needed
