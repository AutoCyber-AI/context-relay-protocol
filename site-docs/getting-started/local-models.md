# Local Models & LM Studio

Run CRP entirely on your own hardware - no API keys, no cloud egress, no per-token
costs. This guide covers LM Studio, Ollama, llama.cpp, and vLLM.

!!! info "Deployment status"
    Local inference is fully supported in the self-hosted SDK today. Managed
    SaaS inference is on the roadmap.

## LM Studio (recommended for beginners)

[LM Studio](https://lmstudio.ai/) provides a GUI for downloading and running
local models. CRP's own benchmarks were run on LM Studio.

### Step 1: Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai/) for Windows, macOS, or Linux.

### Step 2: Download a model

1. Open LM Studio
2. Go to the **Discover** tab
3. Search for a model. Recommended starting points:

| Model | Size | VRAM Needed | Best For |
|-------|------|-------------|----------|
| `qwen3-4b` | ~2.5 GB | 4 GB | Testing, low-resource machines |
| `llama-3.1-8b-instruct` | ~4.5 GB | 6 GB | General use, good quality |
| `mistral-7b-instruct-v0.3` | ~4 GB | 6 GB | Fast inference, good quality |
| `qwen3-14b` | ~8 GB | 10 GB | Higher quality, needs decent GPU |
| `llama-3.1-70b-instruct` | ~40 GB | 48+ GB | Best quality, needs high-end GPU |

4. Click **Download** on your chosen model

### Step 3: Start the local server

1. Go to the **Developer** tab (or **Local Server** in older versions)
2. Select your downloaded model
3. Configure context length:
    - Set **Context Length** (`n_ctx`) - this is the model's context window
    - Start with `4096` for testing, increase to `8192` or `32768` for production
4. Click **Start Server**
5. The server starts on `http://localhost:1234/v1` (OpenAI-compatible API)

!!! tip "Context length matters"
    CRP's continuation engine shines when the context window is **small relative
    to the task**. With `n_ctx=4096` and a 30-section document request, CRP will
    chain 8-10 windows and produce 10-12x more content than a single call.

### Step 4: Connect CRP to LM Studio

```python
import crp
from crp.providers import OpenAIAdapter

client = crp.SDKClient(provider=OpenAIAdapter(
    model="qwen3-4b",                    # Must match LM Studio model name
    base_url="http://localhost:1234/v1",  # LM Studio default
    api_key="lm-studio",                 # Any non-empty string works
))
```

### Step 5: Run a completion

```python
response = client.complete(
    "Write a comprehensive guide to container orchestration.",
    depth="standard",
)

print(response.text)
print(f"Grounded: {response.crp.grounded}")
print(f"Risk: {response.crp.risk}")
```

### Step 6: Run the benchmark

```bash
python examples/benchmark_continuation.py \
  --base-url http://localhost:1234/v1 \
  --model qwen3-4b \
  --api-key lm-studio \
  --max-tokens 2048 \
  --context-size 4096
```

### LM Studio tips

!!! warning "Thinking models"
    Models like `qwen3-4b` use internal `<think>` reasoning that consumes
    ~51% of the token budget invisibly. A non-thinking model (like
    `llama-3.1-8b-instruct`) produces ~2x more visible output per window.

- **GPU offloading**: In LM Studio settings, set GPU layers to maximum for best
  speed. If you run out of VRAM, reduce by 5 layers at a time.
- **Flash Attention**: Enable if your GPU supports it (most modern NVIDIA GPUs).
- **Batch size**: Leave at default (512) unless you're running multiple sessions.
- **Temperature**: CRP passes temperature to the model. Default is usually fine.

---

## Ollama

```bash
# Install: https://ollama.ai
ollama pull llama3.1
```

```python
import crp

# Auto-detects running Ollama on localhost:11434
client = crp.SDKClient(provider="ollama", model="llama3.1")

response = client.complete(
    "Review this function for security issues: def add(a, b): return a + b",
    depth="quick",
)
print(response.text)
```

### Custom Ollama server

```python
import crp
from crp.providers import OllamaAdapter

client = crp.SDKClient(provider=OllamaAdapter(
    model="codellama",
    base_url="http://192.168.1.100:11434",  # Remote server
))
```

---

## llama.cpp

```bash
# Build and start llama.cpp server
./llama-server -m model.gguf -c 8192 --port 8080
```

```python
import crp
from crp.providers import LlamaCppAdapter

client = crp.SDKClient(provider=LlamaCppAdapter(
    server_url="http://localhost:8080",
))
response = client.complete("Explain continuations.")
print(response.text)
```

---

## vLLM / TGI / any OpenAI-compatible server

Any server exposing an OpenAI-compatible API works with the `openai` provider:

=== "vLLM"

    ```bash
    python -m vllm.entrypoints.openai.api_server \
      --model meta-llama/Llama-3.1-8B-Instruct
    ```

    ```python
    import crp

    client = crp.SDKClient(
        provider="openai",
        model="meta-llama/Llama-3.1-8B-Instruct",
        base_url="http://localhost:8000/v1",
        api_key="dummy",
    )
    ```

=== "Text Generation Inference"

    ```bash
    docker run --gpus all -p 8080:80 \
      ghcr.io/huggingface/text-generation-inference \
      --model-id meta-llama/Llama-3.1-8B-Instruct
    ```

    ```python
    import crp

    client = crp.SDKClient(
        provider="openai",
        model="meta-llama/Llama-3.1-8B-Instruct",
        base_url="http://localhost:8080/v1",
        api_key="dummy",
    )
    ```

---

## Custom function (any LLM)

For any LLM not covered above:

```python
import crp
from crp.providers import CustomProvider

def my_llm(messages, **kwargs):
    # Call your LLM however you want
    # Return (output_text, finish_reason)
    return ("response text", "stop")

client = crp.SDKClient(provider=CustomProvider(
    generate_fn=my_llm,
    count_tokens_fn=lambda text: len(text) // 4,
    context_size=8192,
))
```

---

## Choosing a model

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| First test / low resources | `qwen3-4b` | Small, fast, good enough to see CRP work |
| General development | `llama-3.1-8b-instruct` | Non-thinking model, good quality/speed ratio |
| Quality-sensitive tasks | `qwen3-14b` or `llama-3.1-70b` | Better instruction following |
| Code tasks | `codellama-13b` or `deepseek-coder-v2` | Code-optimized |
| Benchmarking CRP | `llama-3.1-8b-instruct` | Non-thinking = clean benchmark data (no `<think>` tax) |

## Notes

- CRP auto-detects the model's context window size from the provider
- All extraction runs locally - no data leaves your machine
- The embedding model (`all-MiniLM-L6-v2`, ~80 MB) downloads automatically on first use
- First dispatch takes ~10-15 seconds for model loading; subsequent calls are fast
