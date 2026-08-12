# CRP Tooling Reality Check & v5 Unification Proposal

**Document ID:** CRP-TOOL-AUDIT-001  
**Version:** 1.0  
**Date:** 2026-07-04  
**Author:** CRP Engineering Agent (AutoCyber AI Pty Ltd)  
**Status:** Draft for review  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What “Tools” Are in CRP Today](#2-what-tools-are-in-crp-today)
3. [How Tools Are Semantically Retrieved](#3-how-tools-are-semantically-retrieved)
4. [Is CRPv5 / Tool Positioning Being Used as Intended?](#4-is-crpv5--tool-positioning-being-used-as-intended)
5. [Gap Analysis vs. Larger Multi-Tool Platforms](#5-gap-analysis-vs-larger-multi-tool-platforms)
6. [What Is Solid and Should Be Preserved](#6-what-is-solid-and-should-be-preserved)
7. [Innovation Opportunities](#7-innovation-opportunities)
8. [CRPv5 Unification Proposal](#8-crpv5-unification-proposal)
9. [Cross-Product Applicability](#9-cross-product-applicability)
10. [Roadmap & Success Metrics](#10-roadmap--success-metrics)
11. [Bottom Line](#11-bottom-line)

---

## 1. Executive Summary

CRP has a **well-designed, spec-driven v5 positioned-tool layer** (`crp/tools/`, `crp/stl/`, `CRPClient.dispatch_positioned()`), but it is **not the default execution path** of the platform. The Gateway still behaves like a context-augmenting proxy, the legacy orchestrator still forwards full OpenAI-style tool arrays to the provider, and the MCP server is a static CRP-as-a-tool surface with keyword retrieval.

This report documents the current state, identifies gaps relative to mature multi-tool agent platforms, and proposes a **unified CRPv5 architecture** that makes the Tool Capability Fabric (TCF) and Semantic Task Layer (STL) the single execution substrate for CRP Comply, Scan, Gateway, and any third-party product that adopts CRP.

---

## 2. What “Tools” Are in CRP Today

The codebase contains **three separate tool concepts that are not unified**:

| Layer | What it is | Where it lives |
|-------|-----------|----------------|
| **Native CRP capabilities / Tool Capability Fabric (TCF)** | Python functions wrapped as `CapabilityDescriptor` objects, scored and selected by the TCF, then executed by `CapabilityExecutor`. This is the CRP “v5” / SPEC-049-050 positioned-tool layer. | `crp/tools/*`, `crp/stl/positioned.py`, `crp/sdk/client.py` |
| **Provider-native tool calling (legacy v3)** | OpenAI-style `tools`/`function` arrays forwarded straight to the LLM provider. The provider decides what to call. | `crp/core/dispatch_router.py`, `crp/providers/openai.py`, `crp/core/orchestrator.py` |
| **MCP product server tools** | ~59 static `crp_*` tools exposed through a FastMCP server so external agents can call CRP. | `crp_mcp/server.py`, `crp_mcp/*_tools.py` |

**In short: yes, they are mostly “just functions.”** The native TCF turns Python callables into capabilities, the MCP server turns CRP helpers into MCP tools, and the legacy orchestrator forwards JSON tool schemas to the provider. There is no single runtime where all three worlds meet.

---

## 3. How Tools Are Semantically Retrieved

There are **two retrieval models**, and they are not connected:

### 3.1. Inside the positioned loop (`crp/tools/capability_fabric.py`)

This is the **only real semantic retrieval path**:

- Capabilities carry `embedding_vector` and `embedding_model`.
- `ToolCapabilityFabric.select()` filters by `STLOperation`, then scores by:
  - cosine similarity of embedding vs. query,
  - lexical Jaccard fallback,
  - intent overlap,
  - schema compatibility with available CSO facts,
  - inverse cost (`tokens`, `latency_ms`, `safety_class`).
- It resolves dependencies and mutual exclusions, then returns top-K capabilities bounded by the `CapabilityProfile`.

**Verdict:** well-designed, spec-aligned, but **only used by `run_positioned()` / `CRPClient.dispatch_positioned()`**.

### 3.2. In the MCP server (`crp_mcp/`)

Retrieval is **keyword/heuristic only**:

- `crp_recommend_capability()` scores a static `CRP_CAPABILITY_MAP` by keyword hits.
- `crp_mcp/corpus.py` indexes spec Markdown by headings and token frequency.
- **No embeddings, no vector DB, no HNSW/FAISS, no sentence-transformers** are used for tool discovery.

**Verdict:** the MCP server advertises semantic capability discovery but does not actually perform semantic retrieval.

---

## 4. Is CRPv5 / Tool Positioning Being Used as Intended?

**Short answer: no** — not at the Gateway, not in the legacy orchestrator, and not bidirectionally with MCP.

### What exists and works

- `run_positioned()` in `crp/stl/positioned.py` is real and tested.
- `ToolPositioningFrame` in `crp/stl/tool_positioner.py` correctly renders 1–3 selected tools into a compact prompt with a constrained JSON output schema.
- `CRPClient.dispatch_positioned()` and `@client.tool` make it usable from Python.
- `CapabilityExecutor` validates inputs and produces typed `ToolObservation`s.

### What is not happening

- **`crp/gateway/capability_router.py` does not exist.** `AGENTS.md` lists it as the “capability-profile mapper & structured-output translation” module; the Gateway has no such router.
- The Gateway’s `/v1/chat/completions` lifecycle **does not invoke `run_positioned()` or the TCF**. It builds a CDR/CDGR envelope and proxies to the provider. Incoming `tools`/`tool_choice` are effectively ignored.
- The legacy `CRPOrchestrator.dispatch()` path still uses provider-native tool calling and **never imports the TCF**.
- The MCP server is **server-only**: it exposes CRP tools but cannot consume external MCP servers as CRP capabilities.
- SPEC-049/050 headers (`CRP-Agent-Capability-Profile`, `CRP-Agent-Tool-Subset`, `CRP-LLM-Prompt-Cache-Hint`, etc.) are defined in `crp/headers/names.py` but **not parsed/acted on by the Gateway**.
- Session tokens do not carry the SPEC-050 §8 fields: `capability_profile`, `operation_state`, `tcf_selection`, `tool_observations`, etc.

**So the v5 positioned layer is a parallel, SDK-only subsystem, not the default execution path of the platform.**

---

## 5. Gap Analysis vs. Larger Multi-Tool Platforms

Compared to OpenAI Assistants, LangGraph/LangChain, AutoGPT, Semantic Kernel, CrewAI, or Copilot, CRP is missing the following:

### Orchestration & planning
- **No plan repair / backtracking.** `run_positioned()` executes a fixed operation plan once. If a tool fails or returns insufficient data, it does not replan.
- **No parallel tool execution.** Tools are selected and executed one at a time per operation.
- **No dynamic sub-task decomposition.** Operations come from a keyword classifier; complex goals are not recursively broken down.
- **No tool-output-driven branching.** The next operation is chosen upfront, not based on what the tool returned.
- **No long-horizon memory of tool usage.** Observations live in the per-turn CSO; no persistent tool-call trace, replay, or learned shortcuts.

### Tool ecosystem
- **No MCP client consumption.** `crp_mcp` only serves tools; it does not discover or call external MCP servers.
- **No persistent tool registry.** Capabilities are registered per session/request; no runtime discovery, versioning, or negotiation.
- **No tool result caching.** Identical calls are re-executed.
- **No provider-native constrained decoding.** `provider_model_call()` passes a JSON schema but does not inject OpenAI/Anthropic `response_format`, Ollama `format`, vLLM `guided_json`, or llama.cpp GBNF grammar.
- **No cross-modal or embedding-based MCP tool discovery** in the MCP server.

### Integration
- **Gateway does not honor `tools`/`tool_choice`.** An OpenAI-compatible caller sending a tool array gets those tools dropped.
- **Legacy orchestrator and positioned loop are not unified.** Users must choose between `client.ask()` (legacy envelope) and `client.dispatch_positioned()` (new loop).
- **No `capability_router.py` in Gateway** to bridge TCF/STL with the OpenAI-compatible endpoint.

### State, memory, context
- **No scratch-buffer integration for tool output.** `ToolObservation.scratch_ref` exists, but the executor does not write raw tool output to the Scratch Buffer.
- **No persistent checkpoint backend.** MCP checkpoints live in memory + optional JSONL; production needs a database with HA and WebSocket/polling resolution.
- **No long-term tool memory.** No recall of “this tool worked for that kind of question before.”

### Observability, quality & safety
- **No tool-use quality benchmark in SQB.** SPEC-026 measures continuation/context quality, not tool-selection accuracy, argument correctness, or multi-tool plan success.
- **No automatic tool hallucination detection.** A model emitting a wrong capability id or malformed args is only handled by parser fallback, not audited as fabrication.
- **No per-tool safety budget.** `AgentSafetyBudget` works per window, not per tool.
- **No PII/secret scanning on tool arguments.** Arguments are type-validated but not checked for sensitive data.
- **No distributed tracing / metrics.** Only file audit logs; no OpenTelemetry or Prometheus.

### Product / deployment
- **No live backend for the MCP server to call.** Gateway, Comply, and Scan are code/stubs or separate projects; hosted MCP tools degrade to stubs.
- **No real tenant API-key service.** `tenant_api_key()` returns an env variable, not a per-org scoped key.
- **No rate limiting / quota enforcement in the MCP server.** Entitlements are read but not enforced per call.

---

## 6. What Is Solid and Should Be Preserved

Do not tear it down — the core is good:

- `CapabilityDescriptor`, `ToolCapabilityFabric`, `CapabilityExecutor`, and `ToolPositioningFrame` are spec-compliant and tested.
- `run_positioned()` is a real agentic loop with CSO relay, continuation, clarification, preventive safety halts, and resource governor integration.
- `CRPClient.dispatch_positioned()` and `@client.tool` make the SDK usable.
- The MCP server has auth, permissions, audit, checkpoint connectors, and billing scaffolding.
- The TCF selection algorithm is sound: operation filter → policy filter → semantic score → dependencies/mutex → profile cap.

---

## 7. Innovation Opportunities

1. **Bidirectional MCP hub** — make CRP an MCP client as well as a server.
2. **Vector-backed capability registry** — embedding-based retrieval everywhere.
3. **Gateway capability router** — bridge TCF/STL with the OpenAI-compatible endpoint.
4. **Unified execution path** — merge legacy `dispatch_with_tools()` and `run_positioned()`.
5. **Plan repair and parallel execution** — planner-actor mode with fan-out/fan-in.
6. **Tool result cache + scratch buffer integration** — avoid re-execution and bound context.
7. **Tool-use quality benchmark** — extend SQB to measure selection, argument, and plan success.
8. **Per-tool safety and PII scanning** — scan arguments and attribute safety budget per call.
9. **Persistent operation trace** — store full state machines across sessions.
10. **Provider-native constrained decoding** — wire `response_format`, `guided_json`, GBNF grammar per provider.

---

## 8. CRPv5 Unification Proposal

### 8.1. Design Goal

Make the **Tool Capability Fabric (TCF) + Semantic Task Layer (STL)** the single, default execution substrate for every CRP product — Comply, Scan, Gateway, and any third-party application — while preserving provider-agnosticism, auditability, and the <50 ms overhead invariant.

> **Definition of “CRPv5” for this proposal:** the positioned agentic execution layer defined by SPEC-049 (SLM Agent Execution Profile) and SPEC-050 (Tool Capability Fabric & Operation Orchestration), extended with the unification primitives described below.

### 8.2. Guiding Principles

| Principle | Meaning |
|-----------|---------|
| **Positioning, not injection** | Operation frames are built *up* from the operation’s requirements, not trimmed down from a full tool catalogue. |
| **One capability fabric** | Every capability — native Python, MCP tool, external API, or product-specific function — is a `CapabilityDescriptor` in the same registry. |
| **Semantic everything** | Intent, operations, capabilities, CSO facts, and tool observations share one embedding space and one model id. |
| **Policy by construction** | Safety class, data residency, policy domain, and cost profile are first-class selectors, not afterthought filters. |
| **Provider-agnostic constrained output** | The runtime translates `ToolPositioningFrame.output_schema()` into whatever constrained-decoding mechanism the target provider supports. |
| **Observable, auditable, repairable** | Every operation state transition, tool selection, and observation extends the HMAC chain and is replayable. |

### 8.3. Target Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        User / API / Frontend                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              CRP Gateway  ──  CapabilityRouter (NEW)                │
│  /v1/chat/completions  ──►  parse tools/tool_choice ──► STL/TCF     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│        STL Operation Classifier  +  Plan Engine (extended)          │
│  classify → decompose → negotiate depth → build operation frame     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Tool Capability Fabric (TCF) — unified registry        │
│  native capabilities │ MCP client bridge │ product modules          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│     CapabilityExecutor  ──►  Provider/Backend + Scratch Buffer      │
│     validate args ──► execute ──► extract ──► ToolObservation       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Cognitive State Object (CSO)  ──►  HMAC Audit Chain / Session      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.4. New / Extended Components

#### 8.4.1. `crp/gateway/capability_router.py` (missing)

Responsibilities:
- Parse incoming OpenAI `tools`/`tool_choice`.
- Decide whether the request should use the legacy proxy path or the positioned-tool path.
- Map the request to one or more `STLOperation`s.
- Invoke `run_positioned()` with the Gateway’s configured fabric, executor, and provider model call.
- Translate `ToolPositioningFrame.output_schema()` to provider-specific constrained output.
- Emit all SPEC-049/050 headers and persist operation state in the session token.

#### 8.4.2. Unified Execution Runtime

A single runtime class that both the legacy orchestrator and the Gateway use:

```text
UnifiedExecutionRuntime
├── select_strategy(request, profile)  → legacy_envelope | positioned_tools
├── run_positioned(...)                → existing loop, enhanced
└── run_legacy_envelope(...)           → existing CDR/CDGR path
```

This removes the current split where `client.ask()` and `client.dispatch_positioned()` are separate worlds.

#### 8.4.3. Semantic Capability Registry (persistent)

Replace the ad-hoc per-session registry with a persistent, versioned registry:
- Store `CapabilityDescriptor` records in SQLite/Postgres with an HNSW or simple cosine index.
- Index by operation type, safety class, policy domain, embedding, and product tag.
- Support runtime registration/unregistration and semantic search across all products.
- Reject mismatched embedding models (enforces Axiom 5 of the existing invariants).

#### 8.4.4. MCP Client Bridge

Make `crp_mcp` bidirectional:
- Discover external MCP servers (stdio, HTTP+SSE).
- Convert each external tool into a `CapabilityDescriptor` (`kind=CapabilityKind.MCP_TOOL`).
- Let the TCF score external and native capabilities together.
- Execute selected external tools through the MCP client and normalize results into `ToolObservation`s.

#### 8.4.5. Plan Repair & Parallel Execution Engine

Extend `run_positioned()`:
- **Parallel fan-out:** when an operation has independent sub-operations or when `PolicyContext` allows, execute multiple tools concurrently.
- **Verifier step:** after tool execution, run a lightweight VERIFY operation to check sufficiency.
- **Replan trigger:** if verification fails, the planner emits a revised operation frame with new tool selections.
- **Dependency graph:** `ExecutionPlan` becomes a DAG of operations, not a linear list.

#### 8.4.6. Provider Structured-Output Translator

Translate `ToolPositioningFrame.output_schema()` to:
- OpenAI: `response_format.type = "json_schema"` or `tools[].function.parameters`.
- Anthropic: `tool_choice` + tool definitions.
- Ollama: `format = "json"` or JSON schema.
- vLLM / SGLang: `guided_json` or `guided_grammar`.
- llama.cpp: GBNF grammar.
- Local SLMs: fallback to prompt + regex validator.

#### 8.4.7. Cross-Product Capability Profiles

Introduce product tags on descriptors:
- `comply:regulatory-mapping`, `comply:audit`, `comply:policy-diff`
- `scan:sast`, `scan:secrets`, `scan:remediation-pr`
- `gateway:provider-routing`, `gateway:key-vault`
- `wasa:recon`, `wasa:exploit`, `wasa:correlation`

The same runtime executes all of them; the product only registers its descriptors and policies.

#### 8.4.8. Persistent Operation Trace & Learning

- Store full operation state machines and tool observations in the storage engine.
- Enable replay, post-hoc audit, and meta-learning:
  - Which capabilities succeed for which operation/intent pairs?
  - Which tool selections led to clarification or halt?
  - Auto-suggest new capability descriptions or parameter defaults.

---

## 9. Cross-Product Applicability

The unification proposal is intentionally **product-agnostic**:

| Product | Native capabilities today | How CRPv5 helps |
|---------|---------------------------|-----------------|
| **CRP Comply** | RAG search, web search, regulatory mapping, policy diff, report generation | TCF selects the minimal tool set per user intent; STL depth negotiation tailors answers; MCP bridge could consume external legal-research MCP servers. |
| **CRP Scan** | SAST, secrets scanning, remediation plan, GitHub PR | TCF routes between scan tools; verifier checks coverage; plan repair retries with alternative tools; scratch buffer holds large code snippets. |
| **CRP Gateway** | Provider routing, key vault, safety policy | CapabilityRouter makes Gateway an agentic OpenAI-compatible endpoint; structured-output translator supports every provider. |
| **WASA AI** | 150+ security tools, subagents, VM executors | Unified registry consolidates fragmented registries; TCF semantic retrieval replaces keyword matching; persistent operation trace and learning improve tool selection; parallel execution and plan repair make the 11-phase lifecycle more robust. |
| **Third-party apps** | Their own functions | They register `CapabilityDescriptor`s and get CRP’s governance, audit, and constrained decoding for free. |

---

## 10. Roadmap & Success Metrics

### Phase 1 — Gateway Router (highest priority)
- Implement `crp/gateway/capability_router.py`.
- Wire Gateway `/v1/chat/completions` to use `run_positioned()` when `tools` are present.
- Emit SPEC-049/050 headers and session-token fields.

### Phase 2 — Unified Execution Runtime
- Refactor `CRPOrchestrator` to delegate to `UnifiedExecutionRuntime`.
- Make `client.ask()` automatically use TCF when tools are registered.

### Phase 3 — Persistent Registry + MCP Client Bridge
- Build semantic capability registry with embedding index.
- Add MCP client discovery/execution to `crp_mcp`.

### Phase 4 — Plan Repair, Parallelism, and Learning
- Add verifier/replan loop and parallel fan-out.
- Add persistent operation trace and meta-learning feedback.

### Success metrics
- **Tool-selection accuracy** ≥ 90% on a new tool-use benchmark.
- **End-to-end latency overhead** < 50 ms per call (existing invariant).
- **Provider coverage:** OpenAI, Anthropic, Ollama, vLLM, llama.cpp all support constrained tool output.
- **Audit coverage:** 100% of tool calls extend the HMAC chain.
- **Adoption:** Comply, Scan, Gateway, and WASA AI all run through the same runtime in production.

---

## 11. Bottom Line

CRP has a **strong, spec-driven v5 positioned-tool layer**, but it is **not yet wired into the Gateway, the legacy orchestrator, or the MCP server as a client**. The immediate priority is unification: make the TCF/STL the default execution substrate across all CRP products and any product that registers capabilities. Doing so will solve the fragmentation, semantic retrieval, constrained decoding, planning, and observability gaps identified in this report — and will directly benefit large-scale tool consumers such as **WASA AI**.

---

*End of report.*
