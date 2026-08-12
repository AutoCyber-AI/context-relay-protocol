# Installation

Get the CRP SDK running locally in under five minutes. This page covers Python
requirements, package variants, provider setup, and a one-line verification.

!!! info "Deployment status"
    **Self-hosted CRP** is available today. Managed cloud CRP Gateway and CRP
    Comply are on the managed-cloud waitlist at `gateway.crprotocol.io` and `comply.crprotocol.io`.

## Requirements

- Python 3.10 or later
- pip 21.0 or later

## Install with pip

=== "Full (recommended)"

    ```bash
    pip install crprotocol[full]
    ```

    Includes NLP models (GLiNER, spaCy), security features, and all extraction stages.

=== "Core only"

    ```bash
    pip install crprotocol
    ```

    Minimal install with core protocol, extraction stages 1-2, and basic security.

=== "Development"

    ```bash
    git clone https://github.com/AutoCyber-AI/context-relay-protocol.git
    cd context-relay-protocol
    pip install -e ".[dev]"
    ```

## Provider dependencies

CRP is provider-agnostic. Install the SDK for your preferred LLM:

```bash
pip install openai          # For OpenAI / Azure OpenAI
pip install anthropic       # For Anthropic Claude
# Ollama: no pip package needed - just run the Ollama server
```

## Verify installation

```python
import crp

print(crp.__version__)  # Should print "4.x"

client = crp.SDKClient()
response = client.complete("Hello, CRP!")
print(response.text)
print(f"Risk: {response.crp.risk}, Grounded: {response.crp.grounded}")
```

## Optional dependencies

| Package | Purpose |
|---------|---------|
| `gliner` | Stage 3 Named Entity Recognition |
| `spacy` | Stage 5 discourse analysis |
| `sentence-transformers` | Semantic similarity for fact deduplication |
| `prompt-injection-detector` | ML-based injection detection |
