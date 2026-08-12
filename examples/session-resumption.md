<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Cross-Session Knowledge Persistence

CRP's Contextual Knowledge Fabric (CKF) persists knowledge across sessions. When you start a new session, it can build on everything learned in previous sessions.

## How It Works

```
Session 1:                      Session 2:
  W1 → W2 → W3                   W1 → W2 → W3
  (facts → warm state)           (warm state starts enriched)
       ↓                              ↑
  warm → cold storage            cold → warm (restored)
```

1. **During a session**: facts accumulate in warm state (Tier 2, in-memory)
2. **On close()**: warm state flushes to cold storage (Tier 3, persistent — SQLite + vector DB + graph)
3. **On init()**: cold state from prior sessions is available for CKF retrieval into envelopes

## Basic Usage

```python
import crp
from crp.providers import OllamaAdapter

# Session 1: Analyze a codebase
client = crp.Client(provider=OllamaAdapter(model="llama3.1"), app_id="code-review")
output1, report1 = client.dispatch(
    system_prompt="You are a code reviewer.",
    task_input=file1_content,
)
output2, report2 = client.dispatch(
    system_prompt="You are a code reviewer.",
    task_input=file2_content,
)
client.ingest(architecture_docs)
client.close()  # Flushes to cold storage

# ... later, even after restart ...

# Session 2: Continue the review — CKF retrieves relevant prior knowledge
client = crp.Client(provider=OllamaAdapter(model="llama3.1"), app_id="code-review")
output, report = client.dispatch(
    system_prompt="You are a code reviewer.",
    task_input="Write a summary of all architectural issues found so far."
)
# The envelope includes facts from Session 1 — the LLM sees prior discoveries
```

## How CKF Retrieves Cross-Session Knowledge

When building an envelope, CKF uses 4 retrieval modes on cold storage:

1. **Graph Walk**: Starting from seed facts in the current task, traverse edges into cold storage to find connected knowledge
2. **Pattern Query**: Content-addressable matching — find facts by structured attributes
3. **Semantic Fallback**: Embedding similarity when graph structure is insufficient
4. **Community Summaries**: High-level topic summaries from Leiden community detection

## Cold Storage Structure

```
~/.crp/
  └── storage/
      └── {app_id}/
          ├── facts.db          # SQLite WAL — fact content, metadata, provenance
          ├── vectors.idx        # HNSW index — fact embeddings for ANN search
          ├── graph.db           # Edge storage — typed relationships between facts
          └── communities.json   # Leiden community partitions and summaries
```

## Session Isolation

- Each `app_id` has its own cold storage — no cross-contamination
- Sessions within the same `app_id` share knowledge
- `export_state()` creates an encrypted, portable snapshot
- `reset_session()` clears warm state but preserves cold storage

## Practical Example: Multi-Day Penetration Test

```python
import crp

# Day 1: Recon
client = crp.Client(model="llama3.1", app_id="pentest-acme-corp")
output, report = client.dispatch(
    system_prompt="You are a penetration tester.",
    task_input="Plan recon for acme.com",
)
client.ingest(nmap_results)
client.ingest(whois_data)
client.close()

# Day 2: Vulnerability assessment (picks up where Day 1 left off)
client = crp.Client(model="llama3.1", app_id="pentest-acme-corp")
output, report = client.dispatch(
    system_prompt="You are a vulnerability analyst.",
    task_input="Analyze all services discovered so far for vulnerabilities."
)
# Envelope includes: IPs, ports, services, versions from Day 1 — all ranked by relevance

# Day 3: Reporting
client = crp.Client(model="llama3.1", app_id="pentest-acme-corp")
output, report = client.dispatch(
    system_prompt="You are a security report writer.",
    task_input="Write the final pentest report for Acme Corp."
)
# Envelope includes: ALL findings from Day 1 + Day 2 — complete context
```
