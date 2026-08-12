# Session Persistence

CRP supports in-process knowledge accumulation via the **Contextual Knowledge
Fabric (CKF)**. Facts extracted during a `crp.SDKClient()` session are available
to every subsequent `ask()`/`complete()` call in the same process.

!!! warning "Cross-process persistence is not yet implemented"
    The current `SDKClient` keeps CKF state in memory for the lifetime of the
    client. Saving a session to disk and reloading it in another process is on
    the roadmap. Today, persist knowledge by keeping the client open or by
    re-ingesting source material at startup.

## Memory tiers

| Tier | Name | Lifetime | Storage |
|------|------|----------|---------|
| 1 | Hot (Envelope) | Current window | In-memory |
| 2 | Warm (Session) | Current `SDKClient` | In-memory |
| 3 | Cold (CKF) | Persistent *(planned)* | SQLite + vectors + graph |

Facts flow downward: Hot → Warm → Cold on session close *(planned)*.
Facts flow upward: Cold → Warm → Hot on relevance match *(planned)*.

## Example: multi-turn analysis

```python
import crp

client = crp.SDKClient(provider="ollama", model="qwen3-4b")

# Reconnaissance turns
client.complete("Enumerate subdomains for acme.com")
client.complete("Scan discovered hosts for open ports")
client.complete("Identify running services and versions")

# Later turn uses accumulated facts
answer = client.ask(
    "Based on the discovered services, identify potential vulnerabilities",
    depth="thorough",
)
print(answer.text)
print(answer.sources)
```

## Inspect session state

```python
s = client.session()
print(s.id)
print(s.status())
print(s.fact_count, s.window_count)
print(client.storage.overview())
```

## What is persisted today

- Fact graph and warm state for the current `SDKClient` instance.
- Audit trail via `client.audit.export()` and `client.audit.verify()`.

## What is planned

- Named sessions loaded by `session_id` or `app_id`.
- Cold storage flush/load across process restarts.
- SQLite/Redis/S3 backend selection via `crp.config.yaml`.

[:octicons-arrow-right-24: Storage SDK Reference](../sdk/context-management.md#7-storage-and-extraction)
