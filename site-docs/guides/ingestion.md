# Ingestion

CRP's `ingest()` lets you feed external data into a session **without making an
LLM call**. Facts are extracted using the graduated extraction pipeline
(stages 1–5, statistical/ML only - no LLM tokens consumed).

!!! info "Status"
    Ingestion works in the self-hosted SDK today. Managed SaaS ingestion endpoints
    are on the roadmap.

## Why ingest?

| Scenario | Use `complete()` | Use `ingest()` |
|----------|-----------------|----------------|
| Generate a response | ✓ | |
| Pre-load reference material | | ✓ |
| Feed API responses | | ✓ |
| Load documentation | | ✓ |
| Process search results | | ✓ |

`ingest()` is free - no LLM tokens consumed. It populates CKF with facts that
future `ask()` calls will retrieve and ground against.

## Basic usage

```python
import crp

client = crp.SDKClient(provider="ollama", model="qwen3-4b")

article = """
TLS 1.3 reduces the handshake from 2-RTT to 1-RTT, eliminating
an entire round trip. It removes support for vulnerable cipher
suites like RC4 and 3DES. Forward secrecy is now mandatory via
ephemeral Diffie-Hellman. The 0-RTT resumption mode enables
instant reconnection but is vulnerable to replay attacks.
"""

client.ingest(article)
print(f"Facts in warm store: {client.storage.fact_count()}")

# Now ask - the TLS facts are automatically in the envelope
answer = client.ask("Write a security assessment of TLS 1.3 migration risks")
print(f"Quality: {answer.quality}")
print(f"Sources: {len(answer.sources)}")
```

## The extraction pipeline

`ingest()` runs stages 1–5 of the extraction pipeline:

| Stage | Method | What it does | Cost |
|-------|--------|-------------|------|
| 1 | Regex patterns | Structured data (dates, URLs, emails, IPs) | ~1ms |
| 2 | TextRank | Graph-based keyword extraction | ~5ms |
| 3 | GLiNER | Zero-shot NER with task-derived labels | ~50ms |
| 4 | Sentence scoring | Key sentences by TF-IDF + position | ~10ms |
| 5 | Fact consolidation | Deduplicate, merge, score confidence | ~5ms |

Stage 6 (LLM-based relational extraction) runs during `ask()`/`complete()`,
when the LLM is available.

## Multiple ingestions

You can ingest from multiple sources:

```python
client.ingest("./api-docs/")
client.ingest("./changelog.md")
client.ingest("https://example.com/release-notes")

answer = client.ask(
    "Summarize the current state of the API and recent user feedback",
    depth="thorough",
)
```

## Ingestion with source labels

The SDK automatically labels files by path. For raw strings, the label is
`"raw-text"`. Inspect what was loaded with `client.storage.overview()`:

```python
client.ingest("./docs/")
print(client.storage.overview())
# {'facts': 142, 'files': 8, 'sources': [...]}
```

## Supported input types

```python
client.ingest("./docs/")                       # directory (recursive)
client.ingest("manual.pdf")                    # single file
client.ingest("https://example.com/guide")     # URL
client.ingest("Raw text as a string")          # string
client.ingest(["a.md", "b.pdf", url, text])    # any mix
```

URLs are fetched and treated as raw text. PDF/text extraction uses available
Python packages; install `crprotocol[full]` for the widest format support.

[:octicons-arrow-right-24: Context Management SDK Reference](../sdk/context-management.md)
