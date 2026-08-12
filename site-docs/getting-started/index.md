# Getting Started

Start building governed, context-aware LLM applications in minutes. The CRP SDK
gives you unbounded context, automatic continuation, grounded retrieval, and
built-in safety governance - all through a single `crp.SDKClient()` interface.

!!! info "Deployment status"
    **Managed cloud** CRP Gateway and CRP Comply are on the waitlist at
    `gateway.crprotocol.io` and `comply.crprotocol.io`.
    Self-host the SDK today via `pip install crprotocol`.

<div class="grid cards" markdown>

-   [**Installation**](installation.md)

    Install CRP with pip and choose the extras that match your stack.

-   [**CLI Reference**](cli.md)

    Run `python -m crp` commands for shell-based workflows.

-   [**Providers**](providers.md)

    Configure OpenAI, Anthropic, Ollama, or custom providers.

-   [**Local Models**](local-models.md)

    Run CRP with LM Studio, Ollama, llama.cpp, or vLLM - no cloud required.

</div>

## The fastest path to value

```python
import crp

client = crp.SDKClient()              # auto-detects provider from env
response = client.complete("Explain CRP in one paragraph.")

print(response.text)
print(f"Risk: {response.crp.risk}")
print(f"Grounded: {response.crp.grounded}")
```

That's it - one client, one call, and CRP handles headers, safety, provenance,
and context packing behind the scenes.
