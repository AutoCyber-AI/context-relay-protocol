<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Extraction Pipeline

CRP's 6-stage graduated extraction pipeline extracts atomic facts and relationships from LLM output and ingested data.

## How Extraction Works

Extraction is **automatic** — it runs after every `dispatch()` and `ingest()` call. You don't need to configure it for most use cases.

```python
# Extraction happens automatically after dispatch
response = client.dispatch(
    system_prompt="You are a vulnerability analyst.",
    task_input="Analyze port scan results: ..."
)
# Facts are now in warm state, available for future windows

# Extraction also runs on ingested data
client.ingest(nmap_output)  # ~7ms, no LLM call
```

## The 6 Stages

### Stage 1: Regex (~1ms)
Captures structured patterns: IP addresses, CVEs, URLs, version strings, JSON objects, email addresses.

### Stage 2: Statistical / TextRank (~5ms)
Identifies key sentences by term frequency and graph centrality. No ML model required.

### Stage 3: GLiNER NER (~50ms, lazy-loaded)
Zero-shot Named Entity Recognition. Extracts entity spans: software names, vulnerability types, organization names, etc.

**Activates when**: Stage 2 yield is below threshold for the content type.

### Stage 4: UIE Relations (~100ms, lazy-loaded)
Universal Information Extraction. Captures entity relationships: "Apache 2.4.52 is vulnerable to CVE-2024-XXXX."

**Activates when**: Stage 3 entities lack relationship context.

### Stage 5: Discourse Structure (~150ms)
RST-inspired paragraph-level parsing. Captures logical relations: cause→effect, condition→consequence, evidence→claim.

**Activates when**: Content is classified as `REASONING_DENSE`.

### Stage 6: LLM-Assisted Relational (~500ms+)
Uses an LLM call to extract implicit logical relationships that pattern-based stages miss.

**Activates when**: Content complexity is high AND Stage 5 edge yield is low. **Optional** — can be disabled.

## Content Type Classification

CRP auto-classifies content to route through appropriate stages:

| Content Type | Description | Typical Stages | Typical Time |
|-------------|-------------|---------------|-------------|
| `ENTITY_RICH` | Structured data, tool output, logs | 1-3 | ~50ms |
| `REASONING_DENSE` | Analysis, arguments, explanations | 1-5 | ~160ms |
| `NARRATIVE` | Creative writing, documentation | 1-2 | ~10ms |

## Extraction Output

Each extracted fact includes:

```python
Fact(
    content="Apache 2.4.52 is running on port 80",
    source_window="w-a3f2c1",
    extraction_stage="regex",
    confidence=0.99,
    embedding=[...],       # 384-dim all-MiniLM-L6-v2
    timestamp=1712419200,
    edges=[                # Relationships to other facts
        Edge(target="fact-xyz", type="runs_on", confidence=0.85)
    ]
)
```

## Fact Quality Gate

Between extraction and warm state, facts pass through three-tier validation:

1. **Structural validation** — well-formed content, reasonable length
2. **Confidence threshold** — minimum confidence per stage
3. **Anomaly detection** — flags facts that contradict existing knowledge (supersession detection)
