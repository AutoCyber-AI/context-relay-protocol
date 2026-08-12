# SDK Configuration Reference

CRP loads configuration from a layered hierarchy. The unified config drives the native SDK, and relevant keys are forwarded to the core orchestrator and Gateway sidecar.

---

## Configuration sources (precedence order)

Later sources override earlier sources.

1. **Built-in defaults** - safe production defaults
2. **`crp.config.yaml`** - project-local config file
3. **Client init kwargs** - arguments passed to `crp.SDKClient(...)`
4. **Runtime override** - `client.configure()` and `layer_override()`

!!! note "Environment variables"
    Environment variables are **not** automatically folded into `CRPConfig`. Gateway and CLI deployments read `CRP_*` env vars via the core configuration resolver. Use `crp.config.yaml` or `client.configure()` for SDK applications.

---

## Minimal `crp.config.yaml`

```yaml
version: "4"
model:
  default: gpt-4o-mini
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}

safety:
  profile: balanced

context:
  mode: auto
  depth: auto
  retrieval:
    min_relevance: 0.55

audit:
  enabled: true
  retention_days: 90
```

---

## Full schema overview

### `version`

| Key | Description |
|-----|-------------|
| `version` | Config schema version (default `"4"`) |

### `model`

| Key | Description |
|-----|-------------|
| `default` | Default model identifier |
| `fallback` | Fallback model identifier |
| `providers` | Provider-specific settings keyed by provider name |

### `safety`

| Key | Description |
|-----|-------------|
| `profile` | `permissive`, `balanced`, `strict`, `research` |
| `settings` | Dict of arbitrary safety settings |
| `coverage` | Coverage-map overrides |
| `checkpoints` | List of checkpoint declarations |
| `custom_rules` | List of custom rule declarations |

!!! note "Profile mapping"
    Built-in profiles map to the orchestrator's human-oversight configuration. Custom profiles can be expressed as a dict with `profile: strict` plus `alert_on_quality_below` overrides.

### `context`

| Key | Description |
|-----|-------------|
| `mode` | `auto`, `document`, `conversation`, `hybrid`, `zero-ckf` *(NOT `full`)* |
| `depth` | Default depth: `auto`, `quick`, `standard`, `thorough`, `exhaustive` |
| `windows.max` | Maximum windows per session (forwarded to `max_windows_per_session`) |
| `windows.token_budget` | Token budget per window (forwarded to `max_total_input_tokens`) |
| `retrieval.min_relevance` | Minimum relevance threshold (0.0–1.0) |
| `retrieval.graph_retrieval` | Enable CDGR graph retrieval |
| `retrieval.max_hops` | Maximum graph hops |
| `retrieval.recency_weighting` | Weight recent facts higher |
| `storage.backend` | `memory`, `sqlite`, `redis`, `s3` *(backend wiring is infrastructure-level)* |
| `storage.rolling_log_size` | Rolling log capacity |
| `storage.hot_cache_size` | Hot cache capacity |

### `knowledge`

| Key | Description |
|-----|-------------|
| `sources` | Default knowledge sources |
| `embedding_model` | Embedding model identifier (default `all-MiniLM-L6-v2`) |
| `auto_ingest` | Auto-ingest configured sources |

### `audit`

| Key | Description |
|-----|-------------|
| `enabled` | Enable audit trail |
| `retention_days` | Audit retention window |
| `forward_url` | HTTPS endpoint for event streaming |

### `gateway`

| Key | Description |
|-----|-------------|
| `url` | Gateway base URL |
| `api_key` | Gateway API key |

---

## Loading config programmatically

```python
from crp import CRPConfig

cfg = CRPConfig.load("crp.config.yaml")     # load from file
cfg = CRPConfig.load()                       # load default path or defaults

# Read and write values
cfg.set("safety.profile", "strict")
print(cfg.get("context.retrieval.min_relevance", 0.55))

# Runtime override
overridden = cfg.layer_override({"safety.profile": "strict"})

client = crp.SDKClient(config=cfg)
```

!!! note "Runtime configuration"
    After creating a client, use `client.configure(context.windows.max=20, safety.profile="strict")` to apply Layer 5 overrides.

!!! warning "No from_yaml / from_env / from_dict / validate"
    `CRPConfig` exposes `load()`, `get()`, `set()`, `layer_override()`, `get_config_hash()`, `to_dict()`, `to_yaml()`, `to_json()`, and `save()`. It does **not** have `from_yaml()`, `from_env()`, `from_dict()`, or `validate()` methods.

---

## Environment variable mapping

For Gateway and CLI deployments, the core resolver reads `CRP_*` prefixed
environment variables. The exact mapping between YAML keys and variable names
is documented in the deployment runbook shared with Enterprise and white-label
customers.

The unified `CRPConfig` used by the SDK does **not** automatically ingest
environment variables; use `client.configure()` or `crp.config.yaml` for SDK
applications.

---

## Validation

Validation runs automatically when `CRPConfig.load()` parses a file; warnings are logged for unknown or invalid keys. For a programmatic check, load the config and inspect the logs.
