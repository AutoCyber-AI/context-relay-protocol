<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

<p align="center">
  <img src="https://raw.githubusercontent.com/AutoCyber-AI/context-relay-protocol/main/site-docs/assets/logo-full-readme.png" alt="CRP protocol logo" width="200" />
</p>

<h1 align="center">Context Relay Protocol (CRP)™</h1>

<p align="center">
  <strong>An open protocol for agentic context and tool orchestration across LLM invocations.</strong>
</p>

<p align="center">
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/Spec-CC_BY--SA_4.0-blue.svg" alt="Spec: CC BY-SA 4.0"></a>
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/Code-ELv2-orange.svg" alt="Code: Elastic License 2.0"></a>
  <img src="https://img.shields.io/badge/Spec_Version-6.0.0-brightgreen.svg" alt="Spec Version: 6.0.0">
  <img src="https://img.shields.io/badge/RFC_2119-Conformant-orange.svg" alt="RFC 2119">
  <img src="https://img.shields.io/badge/Language_Neutral-JSON_Schema-yellow.svg" alt="Language Neutral">
  <img src="https://img.shields.io/badge/Status-v6.0.0-blue.svg" alt="Status: v6.0.0">
  <a href="https://github.com/AutoCyber-AI/context-relay-protocol/actions"><img src="https://img.shields.io/github/actions/workflow/status/AutoCyber-AI/context-relay-protocol/ci.yml?label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-3%2C232%2B-brightgreen.svg" alt="3,232+ tests">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#the-problem">The Problem</a> •
  <a href="#what-crp-does">Solution</a> •
  <a href="#inter-llm-context-sharing-http-sidecar">Inter-LLM Sharing</a> •
  <a href="BENCHMARKS.md">Benchmarks</a> •
  <a href="#specification-documents">Specification</a> •
  <a href="#sdk-status">SDKs</a> •
  <a href="#community">Community</a>
</p>

---

> MCP exposes tools. A2A connects agents. **CRP positions every agent on the right task, with the right context and tools, at the right time** — now with a declarative `crp.Agent` SDK, ML-driven intent, verification, safety, and an AG-UI transparency stream. Built for SLM-first agentic AI.

---

## CRPv6 Status & Roadmap

**Current version:** `v6.0.0`  
**Test status:** `3232 passed, 3 skipped` in the non-live suite (live-LLM tests require a local endpoint).

CRPv6 is **launch-ready for building governed, tool-using agents with local/SLM models**. The protocol runtime, Agent SDK, managed ML models, Gateway capability router, transparency emission layer, verification relay, and storage backends are implemented, tested, and published to PyPI and Hugging Face.

The remaining work to make CRPv6 a **complete ML-first agentic AI ecosystem** is documented below and in the detailed roadmap:

- [`docs/CRPv6_Completeness_Roadmap.md`](docs/CRPv6_Completeness_Roadmap.md) — full strategic roadmap
- [`docs/CRPv6_Operational_Readiness_Report.md`](docs/CRPv6_Operational_Readiness_Report.md) — current operational state
- [`docs/CRPv6_Model_Training_Recipe.md`](docs/CRPv6_Model_Training_Recipe.md) — how to train the missing models
- [`docs/CRPv6_Deployment_Backend_Guide.md`](docs/CRPv6_Deployment_Backend_Guide.md) — hosted backend wiring
- [`docs/CRPv6_Agent_SDK_Usage_Guide.md`](docs/CRPv6_Agent_SDK_Usage_Guide.md) — Agent SDK usage

The big philosophical shift: **ML is the default, rule-based is the degraded/offline path.**

---

## Table of Contents

1.  [CRPv6 Status & Roadmap](#crpv6-status--roadmap)
2.  [The Problem](#the-problem)
3.  [What CRP Does](#what-crp-does)
4.  [Key Differentiators](#key-differentiators)
5.  [Quick Start](#quick-start)
6.  [Agent Templates](#agent-templates)
7.  [Interactive Demo Apps (Local LLM)](#interactive-demo-apps-local-llm)
8.  [How CRP Works](#how-crp-works)
9.  [Architecture Overview](#architecture-overview)
10. [Core Capabilities](#core-capabilities)
11. [Inter-LLM Context Sharing (HTTP Sidecar)](#inter-llm-context-sharing-http-sidecar)
12. [End-to-End Example: Penetration Test](#end-to-end-example-a-penetration-test)
13. [CRP in the AI Stack](#crp-in-the-ai-stack)
14. [Extraction Quality](#extraction-quality)
15. [Efficiency and Cost](#efficiency-and-cost)
16. [Observability and Auditing](#observability-and-auditing)
17. [Limitations and Trade-offs](#limitations-and-trade-offs)
18. [Why Large Context Windows Are Not Enough](#why-large-context-windows-are-not-enough)
19. [Specification Documents](#specification-documents)
20. [JSON Schemas](#json-schemas)
21. [API Surface](#api-surface)
22. [SDK Status](#sdk-status)
23. [Comparison with Alternatives](#comparison-with-alternatives)
24. [Hardware Requirements](#hardware-requirements)
25. [Configuration](#configuration)
26. [Use Cases](#use-cases)
27. [Roadmap & TODOs](#roadmap--todos)
28. [Contributing](#contributing)
29. [Governance](#governance)
30. [Security](#security)
31. [Community](#community)
32. [Built With](#built-with)
33. [Intellectual Property & License](#license)

---

## The Problem

Every agentic AI system forces its LLM to work inside a single, shared context window. Planning, reasoning, tool calling, analysis, memory, and output generation all compete for the same finite token budget. This creates three compounding failures:

| Failure | What Happens | Impact |
|---------|-------------|--------|
| **Context Contamination** | Tool output from step 3 dilutes reasoning for step 12 | The LLM "forgets" early discoveries. Later decisions degrade |
| **Attention Collapse** | At 30K+ tokens, attention spreads thin over irrelevant content | Critical facts in the middle are effectively invisible ([Liu et al., 2023](https://arxiv.org/abs/2307.03172)) |
| **Hard Ceiling** | When the context window fills, the system truncates or stops | Reports are incomplete. Analysis is shallow. Output is arbitrarily cut short |

These aren't edge cases — they happen on **every non-trivial agentic task** and get worse the more capable your agent becomes.

---

## What CRP Does

CRP is a **middleware layer** that wraps your existing LLM calls. It does NOT replace your LLM — it **amplifies** it by structuring the agentic ecosystem around it: task positioning, tool selection, state relay, and preventive safety.

For every LLM call you already make, CRP:

1. **Builds a better prompt** — adds an envelope of relevant historical facts, source passages, and the LLM's own synthesis alongside your system prompt and task input
2. **Calls YOUR LLM** — through your existing provider and infrastructure
3. **Returns the raw output unchanged** — exactly what the LLM generated, not a filtered version
4. **Observes the output** (read-only) — extracts facts into the knowledge fabric so future windows benefit
5. **Carries the LLM's understanding forward** — progressive synthesis evolves across windows
6. **Scaffolds reasoning** — decomposes complex tasks into micro-steps for models that can't chain-of-thought natively

```
   WITHOUT CRP                                WITH CRP

   One shared window,                         N dedicated windows,
   everything competing:                      each pristine:

   +---------------------------+              +----------+   +----------+   +----------+
   | System prompt             |              | System   |   | System   |   | System   |
   | + Tool schemas (10K tok)  |              | Envelope |   | Envelope |   | Envelope |
   | + Tool output #1-#3       |              | Task     |   | Task     |   | Task     |
   | + Reasoning history       |              |          |   |          |   |          |
   | + Prior conversation      |              | Full     |   | Full     |   | Full     |
   | + Current task (buried)   |              | 128K     |   | 128K     |   | 128K     |
   +---------------------------+              +----------+   +----------+   +----------+

    Total capacity: 128K (fixed)              Total capacity: N × 128K (unbounded)
    Quality: degrades with length             Quality: peak per window (tier-reported)
    Input limit: context window               Input limit: unbounded (auto-ingest)
    Output limit: max_output_tokens           Output limit: unbounded (continuation)
```

---

## Key Differentiators

- **Embedded library, not a server** — zero deployment overhead. `pip install crprotocol` and you're running. No Docker, no infrastructure. Optional HTTP sidecar (`crp serve`) for [inter-LLM context sharing](#inter-llm-context-sharing-http-sidecar) — never started automatically
- **Works with any LLM provider** — auto-detected, 3 fields to configure. Built-in adapters for OpenAI, Anthropic, Ollama, and llama.cpp — plus `CustomProvider` to wrap any LLM in 3 lines
- **Structured knowledge extraction** — 6-stage graduated pipeline (regex → statistical NLP → GLiNER NER → UIE relations → RST discourse → LLM-assisted relational). Not just text chunking
- **Contextual Knowledge Fabric (CKF)** — graph-structured knowledge with 4-mode retrieval (graph walk + pattern query + semantic fallback + community summaries), event-sourced history, and cross-session persistence
- **Two-sided provenance** — CRP classifies every model *output* as `CONTEXT_GROUNDED | PARAMETRIC | MIXED | UNCERTAIN` **and** records every *input* fact's upstream source (RAG chunk, vector DB, MCP tool, function call, web search, user turn, file upload, agent memory, or parametric). `ContextManifest` lets you sign a declaration of intended sources; anything observed outside the declaration is flagged as `CONTEXT_ATTESTATION_MISMATCH` in the audit log. Foundational for **ISO/IEC 42001 §4**, **EU AI Act Art. 10**, and **GDPR Art. 30**
- **Unbounded input** — automatically ingests documents larger than any model's context window through structure-aware chunking with protected spans
- **Unbounded output** — automatic continuation with voice profile preservation, document maps, degradation-triggered re-grounding, and content-type-aware stitching
- **Honest quality guarantees** — a degradation model, not magic claims. Quality tiers S through D, reported with every dispatch. Extraction recall percentages published per stage
- **Cross-session knowledge** — sessions build on each other. CKF persists facts, reasoning traces, and graph structure across sessions
- **Reasoning amplification** — meta-learning scaffolds (ORC + ICML + RTL) enable 2B–7B models to perform multi-step reasoning they cannot do natively
- **Protocol-level tool orchestration** — CRP selects and sequences tools outside the model, then positions the model on a focused operation frame instead of injecting every tool schema into the prompt
- **Control-evidence layer for AI security & safety** — HMAC-signed, tamper-evident proof that safety and security controls operate on every call, for EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, and SOC 2-for-AI. [Full mapping →](site-docs/control-evidence.md)
- **Full observability** — per-window metrics, session dashboards, window DAG traceability, telemetry export. Debug "why did it do that?" by tracing decisions through the DAG

---

## Quick Start

### Minimal Integration (3 lines)

```python
import crp

# Auto-detects your LLM from environment (OPENAI_API_KEY, ANTHROPIC_API_KEY, or Ollama)
client = crp.Client()
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Summarize this document: ..."
)
# output = raw LLM output, unmodified
# report.quality_tier = "S" | "A" | "B" | "C" | "D"
```

### Explicit Provider

```python
from crp import Client
from crp.providers import OpenAIAdapter

client = Client(provider=OpenAIAdapter(model="gpt-4o"))
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Summarize this document: ..."
)
```

### Model Name Shortcut

```python
import crp

# Pass model= for automatic provider detection
client = crp.Client(model="claude-sonnet-4-20250514")   # → AnthropicAdapter
client = crp.Client(model="gpt-4o")              # → OpenAIAdapter
client = crp.Client(model="llama3.1")             # → OllamaAdapter
```

### Agent Templates

Ready-to-run agentic AI templates are in [`examples/templates/`](examples/templates/):

```bash
pip install crprotocol
cd examples/templates
python customer_support_agent.py
```

Templates include: customer support, code review, research report, data analyst,
and a fully local SLM agent. Each template works with a mock provider out of
the box and can be switched to OpenAI, Anthropic, Ollama, or the CRP Gateway
in one line.

### Local Models (Zero-Config)

```python
from crp import Client
from crp.providers import OllamaAdapter

client = Client(provider=OllamaAdapter())  # Auto-detects localhost:11434
output, report = client.dispatch(
    system_prompt="You are a security analyst.",
    task_input="Analyze these scan results: ..."
)
```

### llama.cpp / vLLM

```python
from crp import Client
from crp.providers import LlamaCppAdapter

client = Client(provider=LlamaCppAdapter(server_url="http://localhost:8080"))
output, report = client.dispatch(system_prompt=system, task_input=user_message)
```

### Any Custom Setup

```python
from crp import Client
from crp.providers import CustomProvider

def my_generate(messages, **kw):
    # Your existing LLM function
    return ("response text", "stop")  # (output, finish_reason)

client = Client(provider=CustomProvider(
    generate_fn=my_generate,
    count_tokens_fn=lambda text: len(text) // 4,
    context_size=128000,
))
output, report = client.dispatch(system_prompt=system, task_input=user_message)
```

### Direct Ingestion (No LLM Window)

```python
client.ingest(nmap_output)      # ~7ms, extraction only — no LLM call
client.ingest(nikto_output)     # Facts go to warm state automatically
client.ingest(api_response)     # Available in next window's envelope
```

### LLM Compatibility

| API Style | Provider | Examples |
|-----------|---------|----------|
| Chat completions | `OpenAIAdapter`, `AnthropicAdapter`, `OllamaAdapter` | OpenAI, Anthropic, Ollama |
| HTTP completions | `LlamaCppAdapter` | llama.cpp, any OpenAI-compatible HTTP endpoint |
| Any custom setup | `CustomProvider` | Any function that takes messages → returns (text, reason) |

### Configuration

```bash
# .env — ALL optional (CRP auto-detects LLM from API keys or local Ollama)
CRP_ENABLED=true                   # Master switch (default: enabled)
CRP_LOG_ENVELOPES=false            # Debug logging (default: false)
CRP_MAX_CONTINUATIONS=50           # Safety limit on continuation windows
```

### Async Support

```python
# Works with FastAPI, asyncio, any async framework
output, report = await client.async_dispatch("You are helpful.", "Explain CRP.")
facts_count = await client.async_ingest(text, label="docs")
async for event in client.async_dispatch_stream("You are helpful.", "Explain CRP."):
    if event.event_type == "token":
        print(event.data, end="")
await client.async_close()
```

> **More examples**: See [`examples/`](examples/) for runnable scripts — quickstart, multi-turn, ingestion, streaming, async, and provider selection.

---

## Interactive Demo Apps (Local LLM)

Live browser-based applications that demonstrate CRP governing a **real local LLM**
end-to-end. They live in [`examples/crp_demos/`](examples/crp_demos).

### 🚀 Real-World API Demo (recommended for launch)

A terminal demo that runs a local 8B model against live public APIs — no API keys, no cloud provider, no hardcoded data:

- **Open-Meteo** — live weather
- **CoinGecko** — live cryptocurrency prices
- **Wikipedia REST** — article summaries

```bash
# Requires LM Studio or any OpenAI-compatible endpoint
export CRP_LMSTUDIO_URL=http://localhost:1234/v1
export CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
python examples/crp_demos/live_real_world_api_proof.py
```

The script shows the same model twice: once prompting it directly (it returns JSON), and once through `crp.Agent` (it executes the API, synthesises a natural-language answer, and emits governance metadata).

### 🛰️ CRP v4 Protocol Demo

- OpenAI-compatible provider discovery
- Full `X-CRP-*` header namespace
- SPEC-007 signed session tokens
- HMAC-SHA256 audit chain + tamper detection
- CKF memory (fact extraction & recall)
- DPE-style risk scoring
- Policy enforcement with automatic halt

```bash
# Requires fastapi, httpx, uvicorn (pip install fastapi httpx uvicorn)
python -m examples.crp_demos.v4.server    # http://127.0.0.1:8774
```

Then open **http://127.0.0.1:8774/**.

A recorded walkthrough is embedded on the [CRP website](https://crprotocol.io),
[CRP Gateway](https://gateway.crprotocol.io), and [CRP Comply](https://comply.crprotocol.io)
landing pages.

### Legacy CRP v3 demos

The original stdlib-based demos are still available:

| App | URL | Demonstrates |
|-----|-----|--------------|
| **Live LLM Detection** (landing) | `/` | CRP detecting every local runtime + model: architecture, quantization, true context ceiling vs. loaded window, tool-calling and reasoning capability. |
| **App 1 — AI Safety & Governance Console** | `/safety.html` | Prompt-injection shield, Decision Provenance Engine, declarative safety-policy enforcement, **HTTP 451 halt**, and a tamper-evident audit trail. |
| **App 2 — Context Management & Provenance Explorer** | `/context.html` | CKF persistent memory + recall, per-window **HMAC provenance chain**, **Tamper** button, signed session tokens, and the full `CRP-*` header set. |

```bash
python -m examples.crp_demos.server          # serves on http://127.0.0.1:8770
python -m examples.crp_demos.server --port 9000
```

### Prerequisites

1. Install CRP: `pip install -e .` from a clone.
2. Run a local LLM. **LM Studio** is recommended:
   - Load a chat model (e.g. `meta-llama-3.1-8b-instruct`).
   - Start its server (Developer tab → Start Server). It listens on `http://127.0.0.1:1234`.
   - **Ollama** (`http://127.0.0.1:11434`) and **llama.cpp** (`http://127.0.0.1:8080`)
     are auto-detected too. The demos work without any model loaded — detection, chain,
     CKF and tokens still function; only the generated replies will be empty.

> Use `127.0.0.1`, not `localhost` — some runtimes only bind IPv4.

Open **http://127.0.0.1:8774/** (v4) or **http://127.0.0.1:8770/** (v3) in a browser.

### How to verify each capability

- **Detection** — On the landing page, the banner names your loaded model and its real
  context ceiling vs. loaded window (e.g. `131,072` max → `4,096` loaded = `3.1%`). Every
  discovered model is listed with its architecture, quantization and capabilities.
- **Safe answer (App 1)** — Click **Analyze with CRP** with the default grounded prompt.
  Expect `HTTP 200 · PASS`, grounding near 100%, 0 fabrications, and a valid hash-chained
  audit trail (the OCSF export is shown).
- **Halt (App 1)** — Click **Try a risky prompt**, then **Analyze with CRP**. Expect
  `HTTP 451 · HALTED`, policy violations (`SOURCE_NOT_TRUSTED`, grounding threshold), and
  a machine-readable halt body.
- **Injection (App 1)** — Click **Try a prompt injection**, then analyze. The
  prompt-injection shield reports `instruction_override` / `exfil_secret`.
- **Memory (App 2)** — Send "My name is Alex and I am building a protocol called CRP…",
  then ask "What is the name of the protocol I told you I am building?". The model recalls
  **CRP** from the Contextual Knowledge Fabric, and the *Recalled* counter is non-zero.
- **Tamper-evidence (App 2)** — After two turns the HMAC chain shows `VALID`. Click
  **Tamper window 1** and the chain flips to **BROKEN at window 1**, with the affected
  nodes highlighted red.

### Programmatic check (no browser)

```bash
python -m examples.crp_demos.server &
curl http://127.0.0.1:8770/api/detect
curl -X POST http://127.0.0.1:8770/api/safety/analyze \
  -H "Content-Type: application/json" \
  -d '{"system_prompt":"You are a support assistant.","question":"What is the uptime SLA?","context_facts":["Acme guarantees a 99.95% uptime SLA."],"policy":"default-src context; halt-on CRITICAL; require-grounding 0.70"}'
```

---

## How CRP Works

### Four Core Mechanisms

All operate **outside the LLM** — zero protocol tokens inside the model's window.

#### 1. Task Isolation

Every LLM call gets its own dedicated context window containing: system prompt, context envelope, and task input. Nothing else. CRP does NOT add LLM calls — every `crp.dispatch()` maps 1:1 to calls your application already makes. The only "extra" windows are continuations when output hits the physical limit.

#### 2. Context Envelopes + Knowledge Fabric

Between windows, an **envelope** carries forward everything the next window needs. Built by **extraction** (not summarization) — atomic facts and relationships are pulled from output using a graduated 6-stage pipeline, stored in the **Contextual Knowledge Fabric (CKF)** — a fact graph with typed edges, event-sourced history, community detection, and multi-mode retrieval:

- **Graph Walk** — traverse edges from seed facts (2-hop BFS) to reconstruct the subgraph around the task's focal point
- **Pattern Query** — content-addressable structured matching inspired by tuple spaces (Gelernter, 1985)
- **Semantic Fallback** — traditional ANN cosine similarity when graph structure is insufficient
- **Community Summaries** — Leiden community detection produces topic clusters; summaries provide high-level context

Facts are scored by **multi-aspect semantic similarity** with cross-encoder reranking, and packed greedily with dependency-aware graph packing until the window is full.

#### 3. Multi-Signal Completion Detection

The protocol monitors four signals across windows:

| Signal | What It Measures | Dominates For |
|--------|-----------------|---------------|
| **Fact Flow** | New facts per token | Entity-rich content |
| **Structural Flow** | New headings/paragraphs/list items | Structured documents |
| **Vocabulary Novelty** | New n-grams vs. seen n-grams | Creative/discursive content |
| **Structural Completion** | Conclusion detection | Summaries and conclusions |

Signals are weighted by content type — preventing premature termination of conclusions, summaries, and rhetorical passages that produce few new facts but are genuine content.

#### 4. Envelope-Based Continuation

When output hits the physical limit, CRP:

1. Incrementally extracts facts from the new window's output — `O(N)` per window, not `O(N²)` accumulated
2. Identifies what's missing via multi-level gap analysis
3. Builds a continuation envelope with voice profile + document map + structural state for long-chain coherence
4. Dispatches a fresh window — the continuation sees extracted essence, not raw overlap

### What CRP Sends to Your LLM

```python
# You call:
response = client.dispatch(
    system_prompt="You are a security analyst.",
    task_input="Analyze these nmap results: ..."
)

# CRP constructs and sends to YOUR LLM:
messages = [
    {"role": "system", "content": "You are a security analyst."},    # UNCHANGED
    {"role": "user", "content": envelope_text + "\n\n" + task_input} # envelope ADDED
]
```

Your system prompt and task input pass through unchanged. The envelope is additional context — historical facts from prior windows, scored by relevance. The LLM doesn't know CRP exists. **Zero protocol overhead inside the window.**

### Output Guarantee

`dispatch()` returns the complete, unmodified LLM output. Always. Extraction is a read-only side effect — it never modifies, filters, or summarizes the returned string.

---

## Architecture Overview

```
+---------------------------------------------------------------------+
|                        YOUR APPLICATION                              |
|   (any code that calls an LLM — agents, pipelines, reports)         |
+---------------------------------------------------------------------+
                                |
                                |  crp.dispatch(system_prompt, task_input)
                                v
+---------------------------------------------------------------------+
|                        CRP ORCHESTRATOR                              |
|                                                                      |
|   +-----------------+  +-----------------+  +----------------------+ |
|   | Envelope        |  | Warm State      |  | Extraction Pipeline  | |
|   | Builder         |  | Store + Fact    |  | (Blackboard-Reactive)| |
|   | (multi-aspect   |  | Graph + Event   |  | regex → stat → NER → | |
|   |  scoring +      |  | Log             |  | UIE → discourse →    | |
|   |  cross-encoder  |  | (session facts, |  | LLM-relational       | |
|   |  reranking +    |  |  scored +       |  | (graduated, content- | |
|   |  CKF multi-mode |  |  embedded +     |  |  type-adaptive,      | |
|   |  retrieval +    |  |  graph edges +  |  |  self-gating)        | |
|   |  source         |  |  FactEvents)    |  |                      | |
|   |  grounding)     |  |                 |  |                      | |
|   +-----------------+  +-----------------+  +----------------------+ |
|                                                                      |
|   +-----------------+  +-----------------+  +----------------------+ |
|   | Multi-Signal    |  | Continuation    |  | CKF (Knowledge       | |
|   | Completion +    |  | Manager         |  |  Fabric)             | |
|   | Degradation     |  | (auto-ingest,   |  | graph walk +         | |
|   | Monitor         |  |  gap analysis,  |  | pattern query +      | |
|   | (fact flow +    |  |  stitch,        |  | semantic fallback +  | |
|   |  structural +   |  |  voice profile, |  | community summary +  | |
|   |  vocabulary +   |  |  document map,  |  | pub-sub events +     | |
|   |  chain degr.)   |  |  re-grounding)  |  | cross-session graph) | |
|   +-----------------+  +-----------------+  +----------------------+ |
|                                                                      |
|   +-----------------+  +-----------------+  +----------------------+ |
|   | Source          |  | LLM Context     |  | Meta-Learning        | |
|   | Grounding       |  | Curator         |  | Engine               | |
|   | Engine          |  | (periodic       |  | (ORC: orchestrated   | |
|   | (original text  |  |  curation       |  |  reasoning chains,   | |
|   |  passages in    |  |  windows,       |  |  ICML: in-context    | |
|   |  envelopes,     |  |  progressive    |  |  meta-learning,      | |
|   |  dual-layer     |  |  understanding, |  |  RTL: reasoning      | |
|   |  fact+source)   |  |  LLM synthesis) |  |  template library)   | |
|   +-----------------+  +-----------------+  +----------------------+ |
+---------------------------------------------------------------------+
                                |
                                |  Standard LLM API call (unchanged)
                                v
                    +------------------------+
                    |    LLM (any model)     |
                    |    Local or cloud      |
                    +------------------------+
```

---

## Core Capabilities

### Unbounded Context: Input > Model's Window

**Problem**: Your input is 1M tokens but your model has 128K context.

CRP's **auto-ingest** handles this transparently:

1. Detects overflow: `system_prompt + task_input + generation_reserve > context_window`
2. Structure-aware chunking at natural boundaries with protected spans (code blocks, tables, JSON objects are never split). 500-token overlap with boundary reconciliation
3. Extracts facts from each chunk — zero LLM calls for typical content
4. Builds envelope with multi-aspect scoring, cross-encoder reranking, and dependency-aware graph packing
5. Dispatches with a maximally-saturated context window

```python
# Transparent — the user doesn't manage chunking
result = crp.dispatch(
    system_prompt="You are a legal analyst.",
    task_input=million_token_contract  # CRP handles the rest
)
```

Strictly better than truncation (which loses 87% of 1M input on a 128K model). See [02_CORE_PROTOCOL.md §7.6](specification/02_CORE_PROTOCOL.md) for the honest degradation model.

### Unbounded Generation: Output > Model's Limit

**Problem**: Your model outputs 4K tokens per call, but you need 100K.

CRP's **continuation loop** handles this automatically:

1. LLM generates → hits output limit (`finish_reason: "length"`)
2. CRP incrementally extracts facts from the output — `O(N)` not `O(N²)`
3. Runs multi-level gap analysis
4. Builds continuation envelope: facts + structural state + remaining items + voice profile + document map
5. Dispatches fresh window — full context capacity, no attention degradation
6. Stitches outputs with content-type-aware boundary detection, echo detection, heading hierarchy validation
7. Periodically runs re-grounding windows that re-extract from accumulated output to correct warm state drift
8. Repeats until multi-signal completion detection indicates genuine completion

```python
result = crp.dispatch(
    system_prompt="Write a comprehensive security report.",
    task_input="All findings here...",
    max_continuations=50  # Optional safety limit
)
# result contains the full output, stitched from multiple windows
```

### Peak Quality Per Window

Every window gets the model's full context capacity. The envelope fills all remaining space with semantically-ranked facts. Fresh KV cache per window eliminates attention degradation. Self-calibrating weights and thresholds require zero configuration.

### Concurrency Model

Each `CRPOrchestrator` instance is **single-threaded by design** — one dispatch at a time per session. Different sessions (separate `CRPOrchestrator` instances) are fully isolated and can run concurrently without interference. Each session has its own `WarmStateStore`, `FactGraph`, `WindowDAG`, and event log. To process multiple tasks concurrently, create one orchestrator per task.

---

## Inter-LLM Context Sharing (HTTP Sidecar)

> **Optional.** The sidecar is never started automatically. You must explicitly run `crp serve` to enable it.

CRP includes an HTTP sidecar that exposes the **full protocol surface** over REST, enabling multiple applications — potentially using different LLMs — to share extracted knowledge without direct LLM-to-LLM communication.

### Why This Matters

Application A (Claude) extracts facts about code architecture. Application B (GPT-4) receives those facts via the `/facts/share` endpoint. Both benefit from the other's knowledge — without API key sharing, without prompt injection, without any LLM talking to another LLM. The knowledge flows through CRP's structured extraction layer.

This is **not** a chat relay. It is structured, scored, ranked knowledge transfer.

### Quick Start

```bash
# Start the sidecar (loopback only, no auth — local development)
crp serve

# Start with authentication (recommended)
crp serve --auth-token "my-secret-token"

# Bind to all interfaces (REQUIRES auth token)
crp serve --bind-all --auth-token "my-secret-token" --port 9470
```

### Example: Two LLMs Sharing Knowledge

```bash
# 1. Create sessions for two different applications
SESSION_A=$(curl -s -X POST http://localhost:9470/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-app", "context_window": 128000}' | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

SESSION_B=$(curl -s -X POST http://localhost:9470/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt4-app", "context_window": 128000}' | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 2. Application A ingests data and dispatches
curl -X POST http://localhost:9470/sessions/$SESSION_A/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "The authentication module uses bcrypt with cost factor 12..."}'

curl -X POST http://localhost:9470/sessions/$SESSION_A/dispatch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"system_prompt": "You are a security analyst.", "task_input": "Analyze the auth module."}'

# 3. Share Application A's knowledge → Application B
curl -X POST http://localhost:9470/sessions/$SESSION_A/facts/share \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_session_id": "'$SESSION_B'", "min_confidence": 0.5}'

# 4. Application B now has A's extracted facts in its warm state.
#    Its next dispatch will include those facts in the envelope.
curl -X POST http://localhost:9470/sessions/$SESSION_B/dispatch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"system_prompt": "You are a code reviewer.", "task_input": "Review the auth module for best practices."}'
# → GPT-4 now sees Claude's extracted security facts in its context envelope
```

### Full Endpoint Reference

**Session Lifecycle**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create a new CRP session |
| `GET` | `/sessions` | List sessions (owned by caller only) |
| `GET` | `/sessions/:id/status` | Session metrics and health |
| `POST` | `/sessions/:id/close` | Close and clean up session |

**Dispatch (All 6 Variants)**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions/:id/dispatch` | Basic dispatch |
| `POST` | `/sessions/:id/dispatch/tools` | Tool-mediated dispatch |
| `POST` | `/sessions/:id/dispatch/reflexive` | Reflexive (verify) dispatch |
| `POST` | `/sessions/:id/dispatch/progressive` | Progressive dispatch |
| `POST` | `/sessions/:id/dispatch/stream-augmented` | Stream-augmented dispatch |
| `POST` | `/sessions/:id/dispatch/agentic` | Agentic dispatch |

**Knowledge**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions/:id/ingest` | Ingest raw text (extraction only, no LLM call) |
| `GET` | `/sessions/:id/facts` | Query extracted facts (with `?limit=` and `?min_confidence=`) |
| `POST` | `/sessions/:id/facts/share` | **Share facts to another session** (core feature) |
| `POST` | `/sessions/:id/facts/feedback` | Boost, penalize, or reject a fact |
| `GET` | `/sessions/:id/envelope` | Preview envelope contents |

**Admin**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions/:id/providers` | Register a fallback provider |
| `POST` | `/sessions/:id/estimate` | Cost estimation |
| `GET` | `/health` | Health check (session count, auth status, version) |

### Security Model

The sidecar is designed with defense-in-depth. Every layer is enforced on every request.

| Layer | Protection | Detail |
|-------|-----------|--------|
| **Bind address** | Loopback by default | Binds to `127.0.0.1` — only local processes can connect |
| **Authentication** | Bearer token | `--auth-token` enables timing-safe (`secrets.compare_digest`) token verification |
| **Bind-all gate** | `--bind-all` requires auth | Cannot expose to network without `--auth-token` (or explicit `--allow-unauthenticated` override) |
| **Session ownership** | Token-hash binding | Sessions are bound to the SHA-256 hash of the token that created them. Other tokens get `403 Forbidden` |
| **Rate limiting** | Per-IP burst window | Default 120 req/60s per IP. Configurable via `--rate-limit`. Uses monotonic clock (immune to clock drift) |
| **Body size limit** | 10 MB cap | Requests exceeding 10 MB receive `413 Payload Too Large`. Prevents memory exhaustion |
| **Session cap** | 64 concurrent sessions | Returns `503 Service Unavailable` when exceeded. Configurable via `--max-sessions` |
| **Security headers** | On every response | `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` |
| **No HTTPS** | By design | Deploy behind a TLS-terminating reverse proxy (nginx, Caddy) for production |

### CLI Options

```
crp serve [OPTIONS]

Options:
  --port INTEGER                    Port number (default: 9470)
  --bind-all                        Bind to 0.0.0.0 (requires --auth-token)
  --auth-token TEXT                 Bearer token for authentication
  --allow-unauthenticated           Override auth requirement for --bind-all
  --max-sessions INTEGER            Max concurrent sessions (default: 64)
  --rate-limit INTEGER              Max requests per IP per 60s (default: 120)
```

### Integration with CRP Protocol

The sidecar is a thin HTTP layer over the same `CRPOrchestrator` that the Python SDK uses directly. Every session created via the sidecar is a full CRP session with:

- All 6 extraction stages (regex → statistical → NER → UIE → discourse → LLM-relational)
- Contextual Knowledge Fabric (CKF) with graph walk, pattern query, semantic fallback, community summaries
- Multi-signal completion detection and automatic continuation
- Envelope building with multi-aspect scoring and cross-encoder reranking
- Event emission for all pipeline stages (`fact.shared`, `fact.received`, `dispatch.completed`, etc.)
- RBAC enforcement, budget tracking, and cost estimation

The sidecar adds no protocol modifications. A fact extracted via the sidecar is identical to one extracted via `client.dispatch()`. A session created via HTTP behaves identically to one created via Python.

---

## End-to-End Example: A Penetration Test

Your pentest application already has separate LLM calls for planning, tool selection, analysis, and reporting. With CRP, each `llm.generate()` becomes `crp.dispatch()`. **CRP does not add, remove, or restructure your calls.**

### Step 1: Planning

```python
plan = crp.dispatch(
    system_prompt="You are a penetration testing planner...",
    task_input="Create a pentest plan for target 192.168.1.50. Scope: external, web focus."
)
```

| Phase | What Happens | Time |
|-------|-------------|------|
| Envelope | Empty (first window — cold start) | 0ms |
| LLM generates | Phase 1: Recon. Phase 2: Web vuln. Phase 3: Exploitation. Phase 4: Reporting | ~3s |
| Extraction | regex captures "192.168.1.50"; statistical: "nmap", "nikto" = 8 facts | ~6ms |
| Warm state | 8 facts with embeddings | — |

### Step 2: Tool Selection

```python
tool_choice = crp.dispatch(
    system_prompt="You are a security tool selector...",
    task_input="Select and configure the first tool for recon of 192.168.1.50"
)
```

| Phase | What Happens | Time |
|-------|-------------|------|
| Envelope | 8 facts from Step 1, scored by similarity to "tool selection for recon" | ~3ms |
| LLM generates | "Run: nmap -sV -sC -p- 192.168.1.50" | ~2s |
| Extraction | regex: full nmap command; statistical: "version detection" = 6 new facts | ~5ms |
| Warm state | Now 14 facts (8 + 6) | — |

### Step 3: Tool Execution + Ingestion

```python
nmap_result = run_tool("nmap", "-sV -sC -p- 192.168.1.50")  # Your tool runner
crp.ingest(nmap_result)  # ~7ms extraction; 22 new facts (ports, services, versions)
```

No LLM call. Extraction pipeline processes raw tool output directly. Warm state: 36 facts.

### Step 4: Analysis

| Phase | What Happens | Time |
|-------|-------------|------|
| Envelope | 36 facts scored for "vulnerability analysis". ~4200 tokens of dense, relevant context | ~4ms |
| LLM generates | "Critical: Apache 2.4.52 — CVE-2024-XXXX. High: OpenSSH 8.2 — known auth bypass..." | ~5s |
| Extraction | 12 new facts: CVEs, severity ratings, affected services, attack vectors | ~8ms |
| Warm state | 48 facts | — |

### Step 5: Report Generation + Continuation

| Phase | What Happens | Time |
|-------|-------------|------|
| Envelope | 48 facts scored for "report writing". All CVEs, findings, recommendations ranked | ~5ms |
| LLM generates | "Executive Summary... Finding 1: Critical..." → hits output limit | ~8s |
| Continuation | Extract from partial report, identify missing sections, build continuation envelope | ~15ms |
| Window 2 | Fresh context, continues report. 6 more findings + recommendations | ~6s |
| Stitch | Window 1 + Window 2 joined. Echo detection removes overlap. Clean 12-page report | ~2ms |

### Total CRP Overhead

| Step | CRP Time | LLM Time | Overhead |
|------|----------|----------|----------|
| Planning | ~6ms | ~3,000ms | 0.2% |
| Tool selection | ~8ms | ~2,000ms | 0.4% |
| Ingestion | ~7ms | 0ms | N/A |
| Analysis | ~12ms | ~5,000ms | 0.2% |
| Report + continuation | ~22ms | ~14,000ms | 0.2% |
| **Total** | **~55ms** | **~24,000ms** | **0.2%** |

---

## CRP in the AI Stack

### The Three-Layer Architecture

```
+-----------------------------------------------------------+
|  Layer 3:  A2A  —  Agent-to-Agent Communication            |
|  "How agents talk to each other"                           |
+-----------------------------------------------------------+
|  Layer 2:  MCP  —  Model Context Protocol                  |
|  "How agents access tools"                                 |
+-----------------------------------------------------------+
|  Layer 1:  CRP  —  Context Relay Protocol for Agentic AI   |
|  "How each agent is positioned on the right task, context, |
|   and tools"                                               |
|  THE FOUNDATION LAYER                                      |
+-----------------------------------------------------------+
```

**CRP is complementary to MCP and A2A.** MCP defines how agents access tools. A2A defines how agents communicate. CRP defines how each agent is **positioned on the right task with the right context and tools** — the foundation that makes both work at scale, especially for small local models.

- Without CRP, every MCP tool call competes for context space
- Without CRP, every A2A message accumulates in a degrading window
- With CRP + MCP: tool results are extracted into facts, not piled into the window
- With CRP + A2A: inter-agent messages are structured knowledge, not raw text

---

## Extraction Quality

| Stage | Method | What It Extracts | Accuracy | When It Runs |
|-------|--------|-----------------|----------|-------------|
| **1** | Regex | IP addresses, CVEs, JSON, version strings | ~99% | Always |
| **2** | Statistical (TextRank) | Key sentences by term frequency | ~85-90% recall | Always |
| **3** | GLiNER NER | Entity spans (software, vulnerabilities) | ~80-90% F1 | When yield is low |
| **4** | UIE Relations | Entity relationships (X vulnerable to Y) | ~70-80% F1 | When yield is low |
| **5** | Discourse Structure | Logical relations (cause→effect, condition→consequence) via RST | ~65-75% F1 | Reasoning-dense content |
| **6** | LLM-Assisted Relational | Implicit logical relationships | ~85-90% F1 | Optional, high-complexity only |

Stages are graduated — 3-6 activate selectively based on content complexity and prior stage yield. Content is auto-classified as `ENTITY_RICH`, `REASONING_DENSE`, or `NARRATIVE` to route through appropriate strategies.

| Content Type | Typical Stages | Typical Time |
|-------------|---------------|-------------|
| Structured/factual | 1-2 | ~10-15ms |
| Mixed content | 1-4 | ~50-80ms |
| Reasoning-dense | 1-5 | ~160ms |
| High-complexity | 1-6 | ~500ms+ (Stage 6 uses LLM) |

---

## Efficiency and Cost

### Per-Window Overhead

| Operation | Time | When |
|-----------|------|------|
| Multi-aspect scoring + graph packing | ~5-10ms | Every window |
| Cross-encoder reranking (top-200) | ~400ms | When >50 facts (amortized) |
| Extraction Stages 1-2 | ~6ms | Every window |
| Extraction Stage 3 (GLiNER) | ~50ms | Only when yield is low |
| Extraction Stage 4 (UIE) | ~100ms | Only when yield is low |
| Extraction Stage 5 (Discourse) | ~150ms | Reasoning-dense content |
| **Typical total** | **~15-20ms** | **0.1-1% of LLM time** |

### Token Efficiency: CRP vs MCP

| Cost Factor | MCP | CRP |
|-------------|-----|-----|
| Tool schemas in prompt | ALL repeated every call (10K-50K) | Zero — only for tool-selection windows |
| Accumulated context | All prior results stay, attention degrades | Only relevant extracted facts |
| Redundant content | Same schemas repeated N times | No repetition — envelope carries only what's relevant |

**Example**: 20-step agentic loop, 50 tools:
- **MCP**: 20 × 10K schema tokens = **200K tokens** on tool definitions alone
- **CRP**: Schemas in tool-selection windows only. **~90% fewer protocol tokens**

### Cloud API Cost

| Scenario | Without CRP | With CRP | Savings |
|----------|------------|----------|---------|
| 20-step agentic loop (50 tools) | ~400K tokens | ~120K tokens | ~70% |
| Long report (3 continuations) | Truncated at limit | 4 windows, complete | N/A (impossible before) |
| Simple single-turn task | ~2K tokens | ~2K tokens | 0% (no penalty) |

### Real-World: 200-Page Textbook Generation

| Provider | Total Cost | Windows |
|----------|-----------|---------|
| Claude Opus | ~$17 | ~32 |
| Claude Sonnet | ~$3.30 | ~32 |
| GPT-4o | ~$2.50 | ~32 |
| DeepSeek | ~$0.27 | ~32 |
| Local model (Ollama) | **$0** | ~32 |

Naive approach (paste all prior chapters into context): ~800K+ input tokens and worse quality.

### Cost Controls

```python
client = Client(
    llm=adapter,
    max_windows_per_session=50,
    max_total_input_tokens=1_000_000,
    max_total_output_tokens=500_000,
)

# Pre-flight estimation
estimate = client.estimate_session(planned_dispatches=32, avg_output_tokens=4000)
print(f"Estimated cost: ${estimate.estimated_cost_usd:.2f}")

# Live tracking
status = client.session_status()
print(f"Running total: ${status.total_cost:.2f}")
```

Budget caps raise `BudgetExhaustedError` when hit. Rate limits are respected automatically.

---

## Observability and Auditing

### Per-Window Metrics (Automatic)

Every `crp.dispatch()` records:

```json
{
  "window_id": "w-a3f2c1",
  "session_id": "pentest-192.168.1.50",
  "parent_windows": ["w-b7e4d2"],
  "envelope_tokens": 4200,
  "saturation": 0.94,
  "extraction_stages_used": ["regex", "statistical"],
  "extraction_time_ms": 7,
  "facts_extracted": 12,
  "information_flow_rate": 0.0018,
  "quality_tier": "S",
  "gap_analysis": {"required": 7, "fulfilled": 7, "missing": 0},
  "continuation_triggered": false
}
```

### Session Dashboard

| Metric | Alert Threshold | What It Means |
|--------|-----------------|---------------|
| Total windows | >>2× your call count | Runaway continuations |
| Continuation rate | >30% | Tasks may be too large for one window |
| Average saturation | <60% | Extraction yield is low |
| Extraction yield | <2 facts/window | Content type may need different strategy |
| Stage escalation rate | >50% | Structured output would help |

### Window DAG Traceability

Every session produces a directed acyclic graph:

```
W1 (plan) → W2 (tool select) → W3 (analysis) → W4 (report) → W5 (report cont.)
```

Each node shows facts produced, facts consumed, information flow, and envelope saturation. Enables "why did it do that?" debugging by tracing decisions through the DAG.

---

## Limitations and Trade-offs

| Limitation | Severity | Mitigation |
|-----------|----------|-----------|
| **Extraction is lossy** | MEDIUM | 6-stage pipeline covers spectrum. ~85-90% recall on structured, ~70-80% on reasoning-dense, ~50-65% on implicit. See [§7.6](specification/02_CORE_PROTOCOL.md) for degradation model |
| **Fact granularity mismatch** | MEDIUM | Graduated pipeline from tight entities (regex) through relationships (UIE, discourse). Fact graph preserves inter-fact relationships |
| **Hallucinations may pass fact gate** | MEDIUM | Three-tier validation: structural, confidence, anomaly detection. Not perfect for structurally-valid hallucinations |
| **Cold start** | LOW | First window: empty envelope. First ~5 windows: calibrating. System bootstraps safely — never prematurely terminates |
| **Not beneficial for single-turn** | N/A | CRP adds zero value (and zero cost) for tasks that fit in one window |

---

## Why Large Context Windows Are Not Enough

"But my model has 1M context!" — Three problems:

1. **Output limits are NOT 1M.** Models with 1M *input* have *output* limits of 8K-32K. You still need continuation
2. **Attention degrades with length.** "Lost in the middle" means content at position 30K is invisible at position 200K ([Liu et al., 2023](https://arxiv.org/abs/2307.03172))
3. **Cost scales quadratically.** Growing context = $O(N^2)$ total tokens. CRP envelopes = $O(N)$ linear scaling

But more fundamentally, **context size is only 1 of CRP's 9 permanent value propositions**:

| # | Value Proposition | Why Native Context Cannot Provide It |
|---|---|---|
| 1 | **Context Quality** | CRP's scored, graph-structured envelopes put the right facts first. Raw text has no ranking |
| 2 | **Task Isolation** | One window per task. No cross-task attention contamination |
| 3 | **Attention Optimization** | Critical facts placed in the attention sink, not buried at position 500K |
| 4 | **Cost Efficiency** | $O(N)$ total tokens vs $O(N^2)$ for growing native context |
| 5 | **Cross-Session Knowledge** | CKF persists facts and reasoning across sessions |
| 6 | **Structured Knowledge** | Typed fact graph with edges, communities, temporal history |
| 7 | **Multi-Agent Coordination** | Envelope = structured state transfer between agents |
| 8 | **Observability** | Full provenance: every fact has source, confidence, lifecycle |
| 9 | **Reasoning Amplification** | Meta-learning scaffolds turn 2B models into reasoning systems |

**Even a model with infinite native context needs CRP** for propositions 1-4, 6-9.

Scientific backing: "Retrieval can significantly improve the performance of LLMs **regardless of their extended context window sizes**" — Xu et al., ICLR 2024.

---

## Specification Documents

The complete CRP v2.0 specification:

| # | Document | Description | Lines |
|---|----------|-------------|-------|
| 1 | [01_RESEARCH_FOUNDATIONS.md](specification/01_RESEARCH_FOUNDATIONS.md) | Academic research backing — 9 research areas, 40+ papers, meta-learning, retrieval augmentation | ~1,200 |
| 2 | [02_CORE_PROTOCOL.md](specification/02_CORE_PROTOCOL.md) | **The core specification** — 29 sections: axioms, state model, CKF, extraction, completion detection, quality tiers, hierarchical processing, meta-learning, security, concurrency, observability, deployment, publication | ~6,800 |
| 3 | [03_CONTEXT_ENVELOPE.md](specification/03_CONTEXT_ENVELOPE.md) | Context envelope — multi-phase scoring, CKF retrieval, source grounding, continuation envelopes | ~1,200 |
| 4 | [04_TOKEN_GENERATION_PROTOCOL.md](specification/04_TOKEN_GENERATION_PROTOCOL.md) | Unbounded output — continuation, stitching, voice profiles, document maps, completion detection | ~950 |
| 5 | [05_SYSTEM_WIDE_INTEGRATION.md](specification/05_SYSTEM_WIDE_INTEGRATION.md) | Integration architecture — 87+ call sites mapped, component inventory, migration strategy | ~1,750 |
| 6 | [06_IMPLEMENTATION_PLAN.md](specification/06_IMPLEMENTATION_PLAN.md) | Implementation plan — phased rollout, 13 modules, ~3,890 lines of code planned | ~2,000 |
| 7 | [07_SECURITY.md](specification/07_SECURITY.md) | Security architecture — threat model, input validation, fact integrity, RBAC, encryption, OWASP, quantum resistance | ~1,300 |
| 8 | [08_MONETIZATION.md](specification/08_MONETIZATION.md) | Business model — PostgreSQL model (full capability free), 5 revenue pillars, competitive positioning | ~2,000 |
| 9 | [09_DEPLOYMENT.md](specification/09_DEPLOYMENT.md) | Deployment — embedded library rationale, resource footprint, Lambda/K8s/MCP comparison, containerization | ~2,000 |

**Total specification**: ~19,200 lines across 9 documents.

---

## JSON Schemas

All API types are defined as [JSON Schema (Draft 2020-12)](https://json-schema.org/draft/2020-12/schema) for language-neutral consumption:

| Schema | Description | Source |
|--------|-------------|--------|
| [task-intent.json](schemas/task-intent.json) | `TaskIntent` — declarative, all-optional dispatch input | §6.10.2 |
| [quality-report.json](schemas/quality-report.json) | `QualityReport` — returned with every dispatch | §6.10.2 |
| [session-status.json](schemas/session-status.json) | `SessionStatus` — session health snapshot | §6.10.2 |
| [cost-estimate.json](schemas/cost-estimate.json) | `CostEstimate` — pre-flight cost estimation | §6.10.2 |
| [envelope-preview.json](schemas/envelope-preview.json) | `EnvelopePreview` — inspect without dispatching | §6.10.2 |
| [session-handle.json](schemas/session-handle.json) | `SessionHandle` — returned by init() | §6.10.8 |
| [stream-event.json](schemas/stream-event.json) | `StreamEvent` — streaming dispatch events | §6.10.5 |
| [crp-error.json](schemas/crp-error.json) | `CRPError` — standard error format | §6.10.4 |
| [persisted-state-header.json](schemas/persisted-state-header.json) | `PersistedStateHeader` — cold state versioning | §6.10.10 |

---

## API Surface

CRP exposes a synchronous + async + streaming API. All operations use **direct function invocation** (not network RPC). SDKs MAY expose JSON-RPC or gRPC transports for cross-process access.

### Core Operations

| Operation | Stability | Description |
|-----------|-----------|-------------|
| `Client(provider=..., app_id=...)` | **Stable** | Create session, init subsystems, restore cold state |
| `dispatch(system_prompt, task_input, ...)` | **Stable** | Execute LLM window with envelope, extract facts |
| `dispatch_stream(...)` | Provisional | Streaming variant — emits token/extraction/continuation/done events |
| `ingest(raw_text, ...)` | **Stable** | Extract facts without LLM invocation (~7ms) |
| `session_status()` | **Stable** | Session health: windows, tokens, facts, budget remaining, cost |
| `estimate_session(...)` | **Stable** | Pre-flight cost estimation with USD pricing |
| `preview_envelope(...)` | **Stable** | Inspect what the envelope would contain |
| `configure(config)` | **Stable** | Update security/cost config (ADMIN) |
| `export_state(...)` | Provisional | Export encrypted session state |
| `close()` | **Stable** | Flush warm → cold, persist CKF, clean up |

### Error Taxonomy

| Code | Error | Comparable To |
|------|-------|---------------|
| 1001 | `BudgetExhaustedError` | gRPC `RESOURCE_EXHAUSTED` |
| 1002 | `RateLimitExceeded` | HTTP 429 |
| 1003 | `SessionExpired` | gRPC `DEADLINE_EXCEEDED` |
| 1005 | `SessionClosed` | gRPC `FAILED_PRECONDITION` |
| 1010 | `ValidationError` | gRPC `INVALID_ARGUMENT` |
| 1011 | `SecurityInvariantError` | gRPC `ABORTED` |
| 1012 | `SignatureInvalidError` | gRPC `UNAUTHENTICATED` |
| 1020 | `ProviderError` | gRPC `INTERNAL` |
| 1021 | `ProviderTimeoutError` | gRPC `DEADLINE_EXCEEDED` |
| 1030 | `StateCorruptedError` | gRPC `DATA_LOSS` |
| 1031 | `ChainVerificationFailedError` | gRPC `DATA_LOSS` |
Full error taxonomy with all codes in [§6.10.4](specification/02_CORE_PROTOCOL.md).

### RBAC Roles (Planned)

| Role | Permissions |
|------|------------|
| **OBSERVER** | `session_status`, `estimate_session` |
| **OPERATOR** | All OBSERVER + `dispatch`, `ingest`, `preview_envelope` |
| **ADMIN** | All OPERATOR + `configure`, `reset_session`, `export_state` |

> RBAC is fully enforced in the SDK. Every dispatch, ingest, and admin operation checks `RBACEnforcer.check_permission()` and `check_rate_limit()` before proceeding. Default role is OPERATOR (dispatch + ingest). Set via `CRPConfig(default_role="ADMIN")` or `CRPConfig(default_role="OBSERVER")`.

---

## SDK Status

| Language | Status | Package | Repository |
|----------|--------|---------|------------|
| **Python** | ✅ v6.0.0-alpha | `pip install crprotocol` | This repository |
| **TypeScript** | 📋 Planned | `npm install @crp/sdk` | `crp-typescript` |
| **Rust** | 📋 Planned | `cargo add crp` | `crp-rust` |

### Python SDK — Quick Start

```bash
pip install -e ".[dev]"
```

```python
import crp


def get_weather(city: str) -> dict:
    """Fetch current weather for a city."""
    return {"city": city, "temp": 22, "condition": "sunny"}


# Declarative agent: tools + policy + model
agent = crp.Agent(model="local/llama3.1", tools=[get_weather])
result = agent.run("What's the weather in Sydney?")

print(result.answer)
print(result.crp.risk)
print(result.how_it_was_built)
```

**Built-in Providers:**

| Provider | Import | Requirements |
|----------|--------|-------------|
| Auto-detect | `crp.Client()` | Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or run Ollama |
| Custom (any LLM) | `crp.providers.CustomProvider` | None |
| OpenAI / Azure | `crp.providers.OpenAIAdapter` | `openai>=1.0`, `tiktoken` |
| Anthropic | `crp.providers.AnthropicAdapter` | `anthropic>=0.25` |
| Ollama | `crp.providers.OllamaAdapter` | Running Ollama instance |
| llama.cpp | `crp.providers.LlamaCppAdapter` | `llama-cpp-python` or HTTP server |

**Key Features:**
- `3232+` tests passing (non-live suite)
- Declarative `crp.Agent(tools=[...])` with policy, verification, and clarification
- Tool Capability Fabric + Gateway capability router
- ML-driven intent (SetFit), PRM step verification, NLI semantic entropy
- AG-UI-compatible Transparency Emission Layer (`run_tel()`)
- Quality-tier / supervised routing (`quick` | `standard` | `thorough` | `exhaustive`)
- Multi-horizon context, bi-temporal CKF, ephemeral scratch buffers
- Full observability (events, audit log, metrics export)
- Budget enforcement (windows, input/output tokens)
- State export (encrypted AES-256-GCM)

The specification is language-neutral. JSON Schemas in [`/schemas/`](schemas/) enable code generation for any language.

---

## Comparison with Alternatives

| Approach | What It Does | Limitation | In-Window Overhead |
|----------|-------------|------------|-------------------|
| **Naive Prompting** | Everything in one window | Context contamination, attention collapse | None (quality degrades) |
| **RAG** | Retrieves relevant documents (flat vectors) | No output management, no continuation, no graph | Retrieved chunks only |
| **MemGPT / Letta** | Virtual memory via LLM self-management | LLM burns tokens managing its own memory | High (memory function calls) |
| **GraphRAG** | Knowledge graph + community summaries | Static offline indexing, no real-time extraction | Low (query overhead) |
| **Sliding Window** | Truncates old context | Early context permanently lost | Low (but lossy) |
| **MCP** | Standardized tool interface | Manages tool *access*, not tool *output context* | Very High (10K-50K schemas) |
| **A2A** | Inter-agent communication | Manages *messages between agents*, not context *within* | Varies |
| **CRP** | Task isolation + CKF + extraction envelopes + tool orchestration + continuation | Extraction is imperfect | **Zero** |

**Key distinction**: MCP and A2A solve *different problems*. MCP connects LLMs to tools. A2A connects agents to each other. CRP positions each agent on the right task, context, and tools. They are complementary and can be used together.

---

## Hardware Requirements

| Component | Size | Required? |
|-----------|------|-----------|
| Your LLM | Varies | Yes (already running) |
| all-MiniLM-L6-v2 (embeddings) | ~80MB | Yes |
| ms-marco-MiniLM-L6-v2 (reranker) | ~80MB | No (bi-encoder sufficient for <50 facts) |
| GLiNER (NER) | ~200MB | No (lazy-loaded, degrades gracefully) |
| UIE (relations) | ~400MB | No (lazy-loaded, degrades gracefully) |

**Minimum**: Any machine running an LLM can run CRP. **80MB required** + 0-680MB optional.

---

## Configuration

CRP follows a 5-layer configuration hierarchy (see [§25](specification/02_CORE_PROTOCOL.md)):

```
Layer 5: Runtime API  (highest priority)
Layer 4: Environment Variables
Layer 3: Session Config File
Layer 2: User Config File
Layer 1: Built-in Defaults  (lowest priority)
```

All configuration is optional. CRP works with zero configuration if you pass your LLM adapter directly.

### Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRP_ENABLED` | `true` | Master switch |
| `CRP_LLM_ENDPOINT` | — | Fallback LLM endpoint if no adapter passed |
| `CRP_LOG_ENVELOPES` | `false` | Debug: log envelope contents |
| `CRP_MAX_WINDOWS` | `100` | Session window limit |
| `CRP_TELEMETRY_FILE` | `crp_telemetry.jsonl` | Telemetry output path |

---

## Use Cases

| Domain | How CRP Helps |
|--------|--------------|
| **Penetration Testing** | Each tool selection, analysis, and report section gets a fresh window with full findings context |
| **Report Generation** | Unbounded-length reports with per-section windows, gap-aware continuation, quality-tiered output |
| **Multi-Step Reasoning** | Each step gets full context; prior conclusions carried as facts. ORC decomposes complex reasoning |
| **Agentic Tool Use** | Protocol selects the right tool subset for each operation; results extracted into facts; next operation sees only what it needs |
| **Code Generation** | Large codebases across multiple windows; each sees full architecture via envelopes |
| **Research & Analysis** | Long-form analysis exceeding any single window; information flow detects genuine completion |
| **Small Model Amplification** | Positioning, tool retrieval, and state relay let 2B–8B local models perform agentic tasks they cannot do natively |
| **Legal Document Analysis** | Million-token contracts auto-ingested; cross-reference tracking via fact graph |
| **Medical Literature Review** | Cross-session knowledge accumulates across papers; community detection groups related findings |

---

## Roadmap & TODOs

> **Assumption:** Phase A (ML-first local model weights + delivery) is complete. All remaining work is listed below with repo locations, required skills, AI components, rationale, and how to do it.

### Legend

- ✅ Complete
- 🔄 In Progress / Partial
- ⬜ Not Started
- **AI component** — the ML/AI model or technique involved
- **Skill gained** — what a contributor learns by doing it
- **Why needed** — why it blocks completeness
- **Where** — file(s) or directory in this repo
- **How** — high-level implementation path

---

### Phase A — ML-First Local Defaults ✅

These are the foundations. Once done, `pip install crprotocol[full]` gives a genuinely ML-first local SDK.

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| A1 | Publish SetFit intent model | SetFit text classifier on `sentence-transformers/all-MiniLM-L6-v2` | Few-shot intent classification, speech-act theory | Replaces rule-based intent as default | [`crp/isa/intent.py`](crp/isa/intent.py), [`scripts/train_crp_intent_setfit.py`](scripts/train_crp_intent_setfit.py) | Train on Banking77+SNIPS+synthetic templates, push to `AutoCyberAI/crp-intent-setfit`, flip default |
| A2 | Publish PRM DeBERTa model | DeBERTa-v3-small sequence classifier | Process reward modeling, step verification | Replaces UNKNOWN/symbolic default in verification relay | [`crp/vr/prm.py`](crp/vr/prm.py), [`scripts/train_crp_prm.py`](scripts/train_crp_prm.py) | Fine-tune on `trl-lib/prm800k`, push to `AutoCyberAI/crp-prm-deberta-v1`, flip default |
| A3 | Publish safety classifier | Small DeBERTa multi-label classifier | AI safety, prompt-injection detection | Replaces regex/heuristic safety scan | [`crp/security/injection.py`](crp/security/injection.py), [`crp/security/privacy.py`](crp/security/privacy.py) | Collect injection/toxicity/PII datasets, train `AutoCyberAI/crp-safety-deberta-v1`, wire into control plane |
| A4 | Replace GLiNER on Windows | Small NER/span model or quantized GLiNER | NER under resource constraints | Eliminates `CRP_GLINER_DISABLED=1` workaround | [`crp/extraction/stage3_gliner.py`](crp/extraction/stage3_gliner.py), [`crp/extraction/pipeline.py`](crp/extraction/pipeline.py) | Evaluate `urchade/gliner_small` / BERT-NER / distillation; default to Windows-safe model |
| A5 | Ship model manifest + offline download | Model registry + Hugging Face caching | MLOps, model versioning, air-gapped deployment | Users need reproducible, offline-capable weights | [`crp/ml/registry.py`](crp/ml/registry.py), `crp/ml/manifest.json` (new) | Add manifest schema, `crp download-models` CLI, `CRP_MODEL_DIR` support |
| A6 | Default local embedding + vector index | `sentence-transformers/all-MiniLM-L6-v2` + FAISS/HNSW | Dense retrieval, vector indexing | CKF needs semantic retrieval beyond graph walk | [`crp/state/backends/sqlite.py`](crp/state/backends/sqlite.py), [`crp/ckf/`](crp/ckf/) | Add FAISS helper, default embedding model, hybrid graph+vector retrieval |

**Phase A exit criteria:** `pip install crprotocol[full]` auto-downloads all default models; `pytest tests/` passes without `CRP_GLINER_DISABLED`; rule-based paths are explicit fallbacks only.

---

### Phase B — SLM Runtime Excellence ⬜

Make local small models truly capable agentic citizens.

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| B1 | Local model catalog | SLM family templates (Qwen2.5, Phi-4, Llama-3.2, Gemma-2) | Prompt engineering for small models | Users need tested defaults, not trial-and-error | [`crp/providers/`](crp/providers/) | Add `crp/providers/local_model_catalog.py` with per-family chat templates |
| B2 | Tool-call parsing for non-function-call SLMs | Constrained decoding + retry loops | Structured generation without tool-native APIs | 7B models often lack native function calling | [`crp/gateway/structured_decoder.py`](crp/gateway/structured_decoder.py), [`crp/tools/executor.py`](crp/tools/executor.py) | Regex/JSON-schema parsers + fallback LLM repair |
| B3 | `crp serve --local-model` | llama.cpp / vLLM launcher | Local model serving, quantization | One-command local agent runtime | [`crp/cli/main.py`](crp/cli/main.py), [`crp/providers/llamacpp.py`](crp/providers/llamacpp.py) | Add CLI command, auto-download GGUF, start server, connect adapter |
| B4 | Built-in tool library | Web search, Python exec, filesystem, DB, HTTP | Tool design, sandboxing | Agents need useful tools out of the box | [`crp/tools/builtins/`](crp/tools/builtins/) (new) | Implement safe built-ins with schemas and result summarization |
| B5 | Tool-result summarization | Small encoder/extractive summarizer | Observation compression | SLMs need compact tool observations | [`crp/tools/executor.py`](crp/tools/executor.py) | Summarize JSON/structured tool output before next turn |
| B6 | Agent templates | Task-specific prompts and tool sets | Agent pattern design | Users should not build every agent from scratch | [`crp/agent_sdk/agent.py`](crp/agent_sdk/agent.py) | Add `crp.Agent.research()`, `.coder()`, `.analyst()`, etc. |
| B7 | Multi-tool planner for long horizons | Small planning model or LLM-based planner | Hierarchical task planning | Long tasks need explicit planning beyond single-turn positioning | [`crp/stl/orchestrator.py`](crp/stl/orchestrator.py), [`crp/pp/`](crp/pp/) | Extend predictive positioning with plan decomposition |

---

### Phase C — Hosted SaaS ⬜

Turn the local SDK into a multi-tenant service.

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| C1 | Gateway auth + tenant isolation | — | Multi-tenant API design | SaaS needs per-tenant boundaries | [`crp/gateway/api.py`](crp/gateway/api.py), `crp/gateway/auth.py` (new) | Clerk/Auth0 middleware, org-scoped sessions |
| C2 | Provider key vault | Encryption at rest (KMS) | Secrets management | Tenant API keys must never leak | [`crp/gateway/key_vault.py`](crp/gateway/key_vault.py) | Encrypt provider keys per tenant, rotation support |
| C3 | Rate limiting + quotas | Token-bucket / Redis counters | Scalable API governance | Prevent abuse, enforce plans | `crp/gateway/rate_limit.py` (new) | Redis-backed quotas, plan-tier mapping |
| C4 | Console CDN build | Vite + React/Vue frontend | Frontend build pipelines | Console must be cacheable and themeable | [`crp/frontend/console.py`](crp/frontend/console.py), `frontend/agent-console/` (new) | Extract HTML/JS to Vite project, CI upload to S3/R2+CloudFront |
| C5 | Hosted model serving | vLLM/TGI microservices | Model serving at scale | Hosted SLM option for users without GPUs | Infrastructure repo / Docker Compose | Deploy managed-model containers behind Gateway |
| C6 | Production backend defaults | Redis + S3/R2 + PostgreSQL | Cloud-native state management | Memory/SQLite are not multi-tenant defaults | [`crp/infrastructure.py`](crp/infrastructure.py) | Add Postgres backend, make Redis/S3 default in hosted config |
| C7 | Observability | OpenTelemetry traces/metrics | SRE for AI systems | Operators need latency/cost/quality dashboards | [`crp/observability/`](crp/observability/) | OTLP exporter, Grafana templates |
| C8 | Billing + monetization | Stripe webhooks + usage metering | AI product billing | SaaS needs paid tiers | [`crp/monetisation/`](crp/monetisation/) | End-to-end Stripe/Clerk flow, token/operation metering |

---

### Phase D — Ecosystem Integrations ⬜

CRP must play nicely with the rest of the agentic stack.

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| D1 | MCP server implementation | MCP protocol (stdio/SSE) | Model Context Protocol | CRP should expose its tools/knowledge as an MCP server | [`crp/mcp/`](crp/mcp/) (new) | Implement MCP server wrapping Tool Capability Fabric + CKF |
| D2 | MCP client / tool consumer | MCP tool discovery + execution | Consuming external tools | CRP agents should use any MCP server | [`crp/tools/adapters.py`](crp/tools/adapters.py), [`crp/agent_sdk/`](crp/agent_sdk/) | Add MCP client adapter converting MCP tools to CRP capabilities |
| D3 | Coding agent compatibility | Repository-aware context, code graph | Code intelligence, RAG over code | IDE/coding agents need CRP governance | [`crp/scan/`](crp/scan/), [`crp/ckf/`](crp/ckf/) | Semantic code ingestion, repo-wide fact graph, AST-aware extraction |
| D4 | LangChain / LlamaIndex adapters | Adapter pattern | Framework interoperability | Lower friction for existing framework users | [`crp/integrations/`](crp/integrations/) | Add `CRPAgentExecutor`, `CRPCallbackHandler`, LlamaIndex memory/query engine |
| D5 | A2A integration | A2A protocol (task cards) | Inter-agent communication | CRP agents should negotiate tasks with other agents | `crp/a2a/` (new) | Implement A2A task card parsing + CRP positioning |
| D6 | GitHub App for Scan | GitHub App auth, remediation PRs | DevSecOps for AI | Auto-remediation of ungoverned AI calls | [`crp/scan/github_app.py`](crp/scan/github_app.py) | Installation tokens, branch creation, PR templates |

---

### Phase E — Standards & Adoption ⬜

| # | TODO | Why Needed | Where | How |
|---|------|------------|-------|-----|
| E1 | Publish SQB benchmark results | Prove CRPv6 quality gains | [`BENCHMARKS.md`](BENCHMARKS.md), [`examples/crp_demos/sqb_benchmark.py`](examples/crp_demos/sqb_benchmark.py) | Run SQB on baseline vs. CRPv6, document F1/usefulness scores |
| E2 | Conformance test suite pass | Claim protocol compliance | [`tests/conformance/`](tests/conformance/) | Extend vectors, run full conformance |
| E3 | arXiv technical report | Academic/standards credibility | `docs/` | Write empirical evaluation paper |
| E4 | IETF Internet-Draft | Formal standards track | `rfcs/` | Submit draft for CRP headers / session protocol |
| E5 | PyPI `v6.0.0` release | Distribution milestone | [`pyproject.toml`](pyproject.toml) | Bump version, build wheel, publish |

---

### How to pick something to work on

1. **Want ML research?** Pick A1, A2, A3, B5, B7.
2. **Want systems/SRE?** Pick C4, C6, C7, D1, D6.
3. **Want frontend/product?** Pick C4, console UX.
4. **Want developer tools?** Pick B3, B4, B6, D2, D4.
5. **Want standards?** Pick E2, E3, E4.

Each TODO links to a specific file or directory above. Open an issue with the TODO number (e.g., `TODO-A1`) to claim it.

---

## Contributing

Contributions are **approval-only** while the protocol and reference
implementation are being stabilised for the v6 launch. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- How to request approval before opening a pull request
- The RFC process for non-trivial specification changes
- Code of conduct
- Contributor License Agreement (CLA)

---

## Governance

CRP follows an open governance model inspired by the Apache Software Foundation. See [GOVERNANCE.md](GOVERNANCE.md) for:

- Roles: Maintainers, Committers, Contributors
- Decision-making process (consensus-seeking, lazy consensus for minor changes, formal vote for breaking changes)
- Specification versioning and deprecation policy

---

## Security

See [SECURITY.md](SECURITY.md) for:

- Responsible disclosure policy
- Security contact information
- What constitutes a security vulnerability in CRP
- How security issues in reference implementations are handled

The protocol's security architecture is documented in [07_SECURITY.md](specification/07_SECURITY.md) — covering threat modeling, input validation, fact integrity, RBAC, encryption at rest, OWASP mapping, and quantum resistance planning.

---

## Community

- **GitHub Discussions**: [Join the conversation](https://github.com/AutoCyber-AI/context-relay-protocol/discussions)
- **GitHub Issues**: Bug reports, spec clarifications, feature requests
- **General enquiries**: [info@crprotocol.io](mailto:info@crprotocol.io)
- **Enterprise & licensing**: [contact@crprotocol.io](mailto:contact@crprotocol.io)

---

## Built With

| Component | Technology |
|-----------|-----------|
| **Knowledge Layer** | CKF — graph walk + pattern query + semantic fallback + community summaries, event-sourced history |
| **Extraction** | 6-stage graduated blackboard-reactive pipeline (regex → TextRank → GLiNER → UIE → RST discourse → LLM-relational) |
| **Source Grounding** | Dual-layer envelopes — extracted facts paired with original text passages |
| **Meta-Learning** | ORC + ICML + RTL — structured reasoning scaffolding for small models |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 (~80MB, CPU) |
| **Reranking** | cross-encoder/ms-marco-MiniLM-L6-v2 (~80MB, ~500 pairs/sec on CPU) |
| **Indexing** | HNSW approximate nearest neighbor — O(log N) retrieval |
| **Storage** | Warm state (in-memory fact graph + event log) + CKF cold storage (SQLite WAL + vector DB + graph) |
| **Coherence** | Voice profiles, progressive document maps, degradation-triggered re-grounding |
| **Validation** | Pydantic v2 / JSON Schema Draft 2020-12 |

---

## Positioning Statement

**For developers building LLM-powered applications** who need reliable context management across multiple LLM invocations, **CRP (Context Relay Protocol)** is an open protocol that provides structured knowledge extraction, cross-session persistence, and honest quality guarantees. **Unlike** ad-hoc prompt chaining, proprietary context APIs, or vector-only RAG, CRP offers a **formally specified, LLM-agnostic, embedded-library protocol** with a graduated extraction pipeline, graph-structured knowledge fabric, and transparent degradation model — all deployable with zero infrastructure overhead.

---

## License

Context Relay Protocol (CRP) is the original work of **Constantinos Vidiniotis**, created in 2026.

### Specification

The protocol specification documents are licensed under the **Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)**. You may read, share, and adapt the specification with attribution. Full terms: https://creativecommons.org/licenses/by-sa/4.0/

### Implementation Code

SDK and implementation code is licensed under the **Elastic License 2.0 (ELv2)**. You may use CRP freely in your own applications. You may NOT offer CRP as a hosted/managed service without a commercial license.

### Commercial Licensing

For enterprise licensing, managed-service rights, or OEM inquiries:

**AutoCyber AI Pty Ltd** · ABN 22 697 087 166
Email: [contact@crprotocol.io](mailto:contact@crprotocol.io) · General: [info@crprotocol.io](mailto:info@crprotocol.io) · Web: [crprotocol.io](https://crprotocol.io)

### Trademark

"Context Relay Protocol" is a trademark of Constantinos Vidiniotis (application pending, Class 9 — IP Australia).
Use of the name to refer to this project is welcomed; use implying endorsement or affiliation without authorization is not permitted.

See [LICENSE.md](LICENSE.md) for the full license text.

**Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.**

---

<p align="center">
  <strong>Context Relay Protocol v6.0.0-alpha</strong><br>
  Zero configuration. Unbounded input. Unbounded output. Amplified reasoning.<br>
  Better context at every scale. Honest degradation. Quality-tiered.<br>
  Peak quality. Every window.
</p>
