# CRPv6 Agentic Ecosystem — Complete User-Configurable Capabilities

> This document lists **every** knob, surface, and extension point a user or
> integrator can configure in CRPv6. It is meant to answer: *"What can I trust?
> What can I set? What can I plug in?"*

---

## 1. Agent declaration (`crp.Agent`)

`crp.Agent` is the single entry point. Every public argument is user-configurable.

| Parameter | What it controls | Example value |
|-----------|----------------|---------------|
| `model` | Model identifier string or `None` if `provider` is supplied. | `"local/llama3.1"`, `"openai/gpt-4o"` |
| `provider` | A concrete `LLMProvider` instance (bypasses auto-detection). | `OpenAIAdapter(...)`, `CustomProvider(...)` |
| `tools` | List of callables, dicts, `ToolSpec`, or `CapabilityDescriptor`. | `[get_weather, calculate]` |
| `system` | Base system instruction. Appended to preset system prompt if `preset` is set. | `"You are a research assistant."` |
| `policy` | `Policy` or `PolicyContext` governing capability selection. | `PolicyContext(...)` |
| `profile` | Capability profile for the positioned loop. | `"frontier"`, `"capable-local"`, `"small-local"` |
| `depth` | Query depth / verification gating. | `"auto"`, `"quick"`, `"standard"`, `"thorough"`, `"exhaustive"` |
| `max_operations` | Hard cap on operations per run. | `12` |
| `temperature` | Sampling temperature. | `0.2` |
| `max_tokens` | Max tokens per model call. | `1024` |
| `max_continuation_windows` | Continuation windows for generative ops. | `1` |
| `safety` | Safety profile name or override dict. | `"balanced"`, `{"halt_on": "CRITICAL"}` |
| `oversight_required` | Safety classes that trigger human checkpoints. | `{SafetyClass.DESTRUCTIVE}` |
| `clarify_handler` | Resolves oversight/clarification requests. | `ClarificationHandler(...)` |
| `preset` | Cognitive preset (built-in id, file, dict, or `CognitivePreset`). | `"security_analyst"`, `"./my.yaml"` |

---

## 2. Cognitive presets (`crp.cognition`)

A preset turns user intent into runtime agent configuration. Users can define:

| Section | Fields | What it does |
|---------|--------|--------------|
| **Identity** | `id`, `name`, `description`, `persona`, `voice` | Who the agent is and how it speaks. |
| **Reasoning scaffold** | `reasoning.phases[]` | Ordered thinking phases with `name`, `prompt`, `operations`, `tools`, `depth`. |
| **Operating modes** | `operating_modes[]` | Conditional rules: `when` → `then`. |
| **Safeguards** | `safeguards[]` | `name`, `scope`, `condition`, `action` (`warn`/`ask`/`halt`), `rationale`. |
| **Emotions / affect** | `emotions.enabled`, `default_affect`, `recognizer`, `triggers` | Tone adjustment and optional emotion recognition. |
| **Output profile** | `output.length`, `format`, `tone`, `citation_style` | Response shape constraints. |
| **Tool bundles** | `bundles[]` | Named groups of tools and knowledge sources a preset can reference. |

Users can load presets by:

```python
agent = crp.Agent(preset="security_analyst")        # built-in
agent = crp.Agent(preset="./my_preset.yaml")          # file
agent = crp.Agent(preset={"id": "x", ...})            # dict
agent = crp.Agent(preset=CognitivePreset.from_dict(...))  # object
```

Built-in presets: `default`, `research_assistant`, `security_analyst`, `socratic_tutor`, `compassionate_companion`.

---

## 3. Tools — how they are defined, connected, and verified

### 3.1 Tool forms

CRP accepts tools in four forms:

1. **Plain Python callable** — signature and docstring become the tool schema.
2. **Dict with `impl`** — e.g. `{"capability_id": "x", "input_schema": {...}, "impl": fn}`.
3. **`ToolSpec`** — compiled intermediate.
4. **`CapabilityDescriptor`** — full descriptor with cost profile, safety class, etc.

### 3.2 Connection model

When you pass `[get_weather, calculate]` to `crp.Agent`, the agent SDK:

1. Calls `compile_tools()` to introspect each callable.
2. Extracts `__name__` → `capability_id`, docstring → description, type hints → JSON schema.
3. Registers each in the `ToolCapabilityFabric` (TCF).
4. The positioned loop asks the model to emit JSON with `"capability_id"` matching one of the registered ids.
5. The `CapabilityExecutor` calls the matched Python function by name and stores the observation.

**Plain functions work because CRP resolves them by the function object itself**, not by a string lookup in another file. You can define tools in any module and import them into the list.

### 3.3 MCP vs CRP-specific

CRP has **its own** Tool Capability Fabric (`crp.tools`). It does **not** require MCP. However, CRP also ships an MCP bridge:

- `crp_mcp/` package exposes CRP tools as MCP servers and consumes MCP servers as CRP tools.
- `examples/crp_mcp/` has connector examples.

| Layer | CRP-native | MCP bridge |
|-------|------------|------------|
| Tool registry | `crp.tools.capability_fabric` | `crp_mcp.connectors.*` |
| Tool definition | Python callable / descriptor | MCP tool schema |
| Execution | `CapabilityExecutor` in the agent loop | MCP `call_tool` |
| Discovery | Registered at `crp.Agent(...)` init | `mcp_client.list_tools()` |

### 3.4 Verification that tools are properly connected

Use the agent's compiled fabric:

```python
agent = crp.Agent(tools=[get_weather, calculate])
print(agent._fabric.capability_ids)   # {'get_weather', 'calculate'}
print(agent._fabric.describe("get_weather"))
```

Or run `examples/crp_demos/unified_video_demo.py` against a live model — it prints the actual tool calls and results.

---

## 4. Trust surfaces — reasoning loop, windows, and provenance

### 4.1 Why you can trust the reasoning loop

The positioned loop is deterministic in its *structure*:

1. Classify intent → plan operations.
2. For each operation, select the best tool from the registered fabric.
3. Execute the tool.
4. Verify the observation (if `depth` is `thorough`/`exhaustive`).
5. Integrate into the CSO and emit events.

What the **user** controls:
- The system prompt and preset that shape intent/operations.
- The registered tools (cannot call a tool that is not registered).
- The policy that governs which capabilities are allowed.
- The `depth` that gates verification relay.
- The `oversight_required` safety classes that force checkpoints.

What CRP guarantees:
- Only registered capabilities can be selected.
- A capability cannot execute if the policy forbids it.
- Every window extends the HMAC chain.
- Every operation emits an event into the transparency stream.

### 4.2 Windows and provenance

Each `Agent.run()` call is a window. The window chain:

- Uses `WindowHmacInput` with `session_id`, `window_number`, `timestamp`, `response_hash`, `prev_window_hmac`.
- Key derived from the session id via SHA-256.
- Stored on the agent so consecutive runs form a verifiable sequence.
- Exposed via `client.audit.verify()` / `result.crp.chain_valid`.

Users can verify a chain without trusting CRP code by replaying the HMAC inputs.

### 4.3 How presets fix trust

A user-defined preset lets you **replace** generic reasoning with your own:

```yaml
reasoning:
  phases:
    - name: Understand
      operations: [ANALYSE]
      depth: quick
    - name: Verify evidence
      operations: [VERIFY]
      depth: thorough
    - name: Answer
      operations: [GENERATE]
      depth: standard
```

This makes the agent's *trust contract* explicit and inspectable, not hidden in prompt engineering.

---

## 5. Safety and governance

| Capability | User control | Location |
|------------|--------------|----------|
| Safety scan | Env model: `CRP_SAFETY_MODEL`; rule patterns always active. | `crp.security.injection` |
| Risk tier | `safety` param; policy context; `oversight_required`. | `crp.Agent`, `crp.policy` |
| Checkpoints | `clarify_handler`; web UI in `examples/crp_demos/checkpoint_console.py`. | `crp.security.clarify` |
| Verification Relay | Triggered by `depth="thorough"`/`"exhaustive"`. | `crp.vr` |
| Audit chain | HMAC per window; external anchor optional. | `crp.provenance.window_chain` |

---

## 6. Memory and state

| Capability | User control | Location |
|------------|--------------|----------|
| CSO relay | `prior_cso=` argument on `agent.run()`. | `crp.state.cso` |
| CKF facts | `client.ingest()`, `agent.run()` with `prior_cso`. | `crp.ckf` |
| Bi-temporal facts | Valid-time + transaction-time queries. | `crp.btf` |
| Storage backends | SQLite, Redis, S3, file, memory via config. | `crp.infrastructure` |

---

## 7. Transparency / console outputs

Every run can produce:

- **AG-UI event stream** via `agent.run_tel()`.
- **Readable narrative** via `crp.tel.narrative.NarrativeBuilder`.
- **Markdown / HTML / JSON** narrative outputs.
- **Governance cards** (risk, grounded, tier, confidence, sources).
- **Provenance chain** (HMAC link list).
- **Embedded HTML console** via `crp.frontend.agent_console_html()`.
- **Buildable CDN console** in `frontend/agent-console/`.

---

## 8. SDK / integration

| Capability | How to access | Output location |
|------------|---------------|-----------------|
| Synchronous response | `result = agent.run("...")` | `result.answer`, `result.crp.*` |
| Event stream | `for ev in agent.run_tel("..."):` | AG-UI events |
| Internal events | `agent.run("...", event_callback=fn)` | `AgentEvent` objects |
| Console HTML | `crp.frontend.agent_console_html()` | string |
| FastAPI mount | `crp.frontend.console.mount_fastapi(app, ...)` | `/crp/console` route |
| CDN build | `cd frontend/agent-console && npm run build` | `dist/` |

---

## 9. Configuration hierarchy

CRP uses a 5-layer config stack (SPEC-037):

1. Built-in defaults
2. Environment variables
3. `crp.config.yaml` file
4. `crp.Agent(...)` / `crp.Client(...)` init kwargs
5. Runtime `configure()` calls

Users can set model, safety, infrastructure, storage, audit sinks, and gateway params in one file.

---

## 10. What is NOT user-configurable (by design)

- The HMAC algorithm and chain structure (fixed for interoperability).
- The AG-UI event vocabulary (fixed protocol surface).
- The 8 STL operations (RETRIEVE, COMPARE, ANALYSE, SYNTHESISE, GENERATE, VERIFY, CLARIFY, REVISE).
- The fallback path when ML models are missing (rule-based fallbacks are mandatory).

These boundaries keep the protocol consistent across implementations.
