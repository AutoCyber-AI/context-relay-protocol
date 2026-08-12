# CLI Reference

Run CRP from the shell for automation, one-off tasks, and CI/CD pipelines. The
CLI exposes the same SDK capabilities as the Python API through a lightweight
command-line interface.

!!! info "Deployment status"
    The CLI is bundled with the self-hosted SDK today. The managed SaaS console
    for CRP Comply is on the waitlist at `comply.crprotocol.io`.

## Installation

The CLI installs automatically with the SDK:

```bash
pip install crprotocol
python -m crp --help
```

## Commands

### `python -m crp dispatch`

Run a single-turn completion from the command line:

```bash
python -m crp dispatch \
  --system "You are a technical writer." \
  --task "Write a guide to Kubernetes networking." \
  --provider ollama \
  --model llama3.1
```

### `python -m crp init`

Initialize a new CRP session with persistent CKF storage:

```bash
python -m crp init --app-id my-project --ckf-path ./knowledge_base
```

### `python -m crp ingest`

Ingest documents into a session without making an LLM call:

```bash
python -m crp ingest \
  --session-id <session-id> \
  --path ./docs/
```

### `python -m crp status`

Check session status:

```bash
python -m crp status --session-id <session-id>
```

### `python -m crp preview`

Preview the envelope that would be sent for a task:

```bash
python -m crp preview \
  --session-id <session-id> \
  --task "Summarize the uploaded documents."
```

### `python -m crp serve` (HTTP sidecar)

Start CRP as an HTTP service for polyglot deployments:

```bash
python -m crp serve --port 9470 --provider ollama --model llama3.1
```

This exposes a REST API on `http://localhost:9470` that any language can call.
See [HTTP Sidecar](../guides/sidecar.md) for details.

### `python -m crp scan`

Run the static AI-governance scanner on a codebase:

```bash
python -m crp scan --path ./src
```

## Pipeline composition

CRP's CLI composes with standard Unix tools:

```bash
# Pipe document content through CRP
cat document.txt | python -m crp dispatch \
  --system "Summarize this document." \
  --provider ollama --model llama3.1

# Process multiple files
for f in docs/*.txt; do
  python -m crp dispatch --system "Extract key facts." --task "$(cat $f)" >> facts.txt
done
```

## Environment variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI provider auth | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic provider auth | `sk-ant-...` |
| `CRP_PROVIDER` | Default provider | `ollama` |
| `CRP_MODEL` | Default model | `llama3.1` |
| `CRP_CKF_PATH` | Default CKF storage path | `~/.crp/ckf` |

## Global options

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Enable detailed logging |
| `--quiet` / `-q` | Suppress non-essential output |
| `--json` | Output in JSON format |
| `--version` | Show CRP version |
