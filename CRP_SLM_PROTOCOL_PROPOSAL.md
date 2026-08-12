# CRP Agentic AI Protocol — SLM Execution Reframe

> **Status:** revised proposal — aligned with CRP-SPEC-049 (SLM Agent Execution Profile) and CRP-SPEC-050 (Tool Capability Fabric)  
> **Target:** CRP v4.1+ and `crp-comply` v0.2.x  
> **Companion research:** [`crp-comply/SLM_INTEGRATION_RESEARCH.md`](https://github.com/AutoCyber-AI/crp-comply/blob/master/SLM_INTEGRATION_RESEARCH.md) and [`crp-comply/LOCAL_8B_MODEL_ANALYSIS.md`](https://github.com/AutoCyber-AI/crp-comply/blob/master/LOCAL_8B_MODEL_ANALYSIS.md)

---

## 1. TL;DR

The current CRP Comply agent loop fails on 8 B local models because it was designed as if the model should be the planner, tool selector, and executor at the same time. The fix is **not** to limit the model or to fall back to a frontier model. The fix is to make CRP the **agentic AI protocol** — the protocol layer that reasons *around* the model so the model only has to generate the next focused output.

The concrete additions are:

1. **Tool Capability Fabric (TCF)** — a protocol-level registry and retrieval system that selects the 1–3 capabilities the current operation actually needs (CRP-SPEC-050).
2. **Operation State Machine** — explicit tracking of where the agent is (`OPERATION_POSITIONED`, `TOOL_SELECTED`, `TOOL_EXECUTED`, `OPERATION_VERIFIED`, etc.) so the protocol, not the model, manages progress (CRP-SPEC-050).
3. **Tool Positioning Frame** — the minimal set of tools and schemas presented to the model for one STL operation, keeping tool selection out of the prompt (CRP-SPEC-050).
4. **Capability advertisement** — `CRP-Agent-Capability-Profile` (`frontier` / `capable-local` / `small-local`) and `CRP-Agent-Model-Capabilities` tell the protocol how much scaffolding to provide, not what the model is forbidden from doing (CRP-SPEC-049).
5. **Structured-decoding directives** — CRP carries JSON-schema / grammar hints that the gateway translates into provider-specific constrained decoding (CRP-SPEC-049).
6. **Prompt-cache lifecycle hints** — CRP tells the inference server which prefix must stay byte-stable so llama.cpp / vLLM / SGLang can reuse KV state across turns (CRP-SPEC-049).
7. **Preventive safety** — the safety gate inspects the operation frame and tool parameters *before* generation/execution, and returns the problematic frame if it must halt (CRP-SPEC-050).
8. **No hybrid auto-routing** — the assigned model does the work. Frontier models are explicit providers, not silent fallbacks (CRP-SPEC-049 §4.9).

These changes are formalised as **CRP-SPEC-049** and **CRP-SPEC-050**.

---

## 2. Reframing: CRP as the agentic AI protocol

CRP's founding insight is **positioning, not injection**: instead of dumping everything into one context window, the protocol places the LLM on a focused task with a curated envelope. The SLM problem is the extreme version of the same insight: a small model needs *more* positioning, not less.

> **The smaller the model, the more the surrounding protocol must do.**

CRP is therefore repositioned as:

> **CRP — Context Relay Protocol for Agentic AI**  
> *The protocol that places every LLM on exactly the right task, with exactly the right context and tools, at exactly the right time — so even small local models operate as part of an extremely capable agent ecosystem.*

The competitive map becomes clean:

- **MCP** exposes tools.
- **A2A** connects agents.
- **CRP** positions every agent on the right task, context, and tools — the missing layer that makes MCP and A2A work at scale, especially for SLMs.

This is a reframe, not a full rebrand. The CRP acronym, package name (`crprotocol`), and code base are preserved.

---

## 3. Why SLMs can outperform their weight class

Recent work consistently shows that ecosystem factors let small models punch above their parameter count:

- **TinyAgent** (Erdogan et al., EMNLP 2024): a 1.1 B / 7 B fine-tuned model with tool retrieval and constrained decoding surpasses GPT-4-Turbo on a narrow tool space.
- **Gorilla** (Patil et al., NeurIPS 2024): a 7 B retrieval-aware model reduces API hallucinations from 78 % to 11 % by retrieving the right API docs at inference time.
- **ToolLLM / ToolChain\*** (Qin et al., 2023; Zhu et al.): depth-first search decision trees and A\* planning over tool-action spaces let smaller models solve multi-step tool-use problems.
- **Tool-to-Agent Retrieval** (arXiv 2511.01854): joint retrieval over tools and parent agents in a shared vector space outperforms both tool-only and agent-only retrieval.
- **RATS / Dynamic Tool Allocation**: separating "find the capability" from "execute the task" is now an established production pattern.
- **XGrammar-2**: raises Llama-3.2-3B correct-call rates from ~33 % to ~78 % and schema validity to 100 % when structured decoding is enforced.

The unifying pattern: **tool selection and task sequencing belong outside the model**. CRP already has the primitives to do this (STL, CSO, CKF, CDR, DPE, safety budget, audit chain). What is missing is the **tool orchestration layer** that ties them together.

---

## 4. The tool-injection problem

Current agent frameworks (OpenAI function calling, LangChain tools, MCP) inject every tool schema into the system prompt and ask the model to choose. This is the injection pattern CRP was designed to avoid:

- Tool schemas consume 10 K–50 K tokens.
- The model must reason about tool semantics *and* task semantics simultaneously.
- Tool outputs are dumped back into the same context window, contaminating later reasoning.
- There is no protocol-level record of *why* a tool was selected at that point.

CRP's alternative is **protocol-level tool orchestration**:

1. The STL classifies the current cognitive operation (`RETRIEVE`, `ANALYSE`, `COMPARE`, ...).
2. The TCF returns capabilities that serve that operation type.
3. A policy filter removes disallowed capabilities.
4. A dependency resolver builds the minimal execution DAG.
5. The protocol composes a **Tool Positioning Frame** with 1–3 capabilities.
6. The model emits the tool call with constrained decoding.
7. The orchestrator executes the call, validates the result, and stores the observation in the CSO as a typed fact.

The model never sees the full tool catalogue. It sees only the tools the protocol has determined are relevant to *this* operation.

---

## 5. The Tool Capability Fabric (TCF)

The TCF is a protocol-level registry of every tool, MCP server capability, sub-agent, and callable primitive available to a session. Each entry is a **Capability Descriptor** with:

- `capability_id`, `kind`, `version`
- `operation_types` — which STL operations it serves
- `input_schema` / `output_schema`
- `produces_facts`, `consumes_facts`
- `dependencies`, `mutually_exclusive_with`
- `cost_profile` — tokens, latency, safety class
- `data_residency`, `allowed_policy_domains`
- `embedding_vector`, `embedding_model`
- `metadata`

The canonical JSON Schema is in `schemas/capability-descriptor.json`.

For each operation, the TCF runs a selection algorithm:

1. Filter by operation type.
2. Apply the policy pre-filter (allowlist/blocklist/residency/safety class).
3. Score by semantic similarity, schema compatibility, intent overlap, and inverse cost.
4. Resolve dependencies and mutual exclusions.
5. Select the top-K capabilities, where K is determined by the model's capability profile.

The result is a **Tool Positioning Frame** — a compact prompt fragment that tells the model exactly which tools it may use for this operation and what each returns.

---

## 6. Operation State Machine

CRP explicitly tracks the lifecycle of an agentic task in the session token / CSO:

| State | Meaning |
|-------|---------|
| `INTENT_CLASSIFIED` | STL mapped the request to an operation plan |
| `OPERATION_POSITIONED` | Operation Frame + Tool Positioning Frame built |
| `TOOL_SELECTED` | Model emitted a valid tool-selection output |
| `TOOL_EXECUTED` | Capability ran; observation stored in CSO |
| `OPERATION_VERIFIED` | DPE / safety verifier checked output |
| `INTEGRATED` | Result merged into CSO; next operation prepared |
| `COMPLETE` | Final response assembled |
| `HALTED` | Preventive safety or failure halt |

This state machine is exposed via `CRP-Agent-Operation-State`, `CRP-Agent-Operation-Type`, and `CRP-Agent-Operation-Plan`. It lets observability, the UI, and safety know exactly where the agent is at any moment.

---

## 7. Preventive safety

Current `halt-on` returns HTTP 451 after detecting a problem. For agentic tool use, safety must be **preventive**: the frame is inspected *before* the model generates output or the tool executes.

The safety gate checks:

- Is the capability allowed by policy / allowlist / data residency?
- Do the tool arguments violate parameter-level rules?
- Does the operation type require an oversight token?
- Does the operation-state transition violate the plan?

If a gate fires, the response is HTTP 451 with the **actual problematic frame**:

```json
{
  "crp_halt_reason": "PREVENTIVE_SAFETY_VIOLATION",
  "halt_point": "TOOL_SELECTED",
  "problematic_frame": {
    "operation_type": "RETRIEVE",
    "capability_id": "web_search",
    "violation": "data_residency_policy_EU_only",
    "blocked_parameter": "region=us-east-1"
  },
  "session_id": "crp_sess_...",
  "audit_trail_uri": "https://comply.crprotocol.io/t/..."
}
```

The LLM never receives the problematic frame, so it cannot generate an AI-unsafe response from it.

---

## 8. No hybrid auto-routing

The first draft of this proposal included `CRP-Routing-Target: hybrid` and automatic escalation to frontier models. That approach is rejected because:

- It violates the SLM-first design principle.
- It is unacceptable for air-gapped, privacy-first, and cost-constrained deployments.
- It hides the real problem: the protocol should make the local model capable, not give up on it.

CRP-SPEC-049 therefore **removes** `CRP-Routing-Target`, `CRP-Routing-Decision`, and the `CRP-Agent-Model-Tier` limiting label. Instead:

- The assigned model is the model that does the work.
- Frontier models are configured explicitly as providers.
- The protocol amplifies the local model through STL decomposition, TCF retrieval, CSO state relay, verifier operations, and constrained decoding.

---

## 9. SLM Amplification Rule

The protocol follows a simple rule:

> **For every halving of effective model capability, double the use of positioning, tool retrieval, operation decomposition, and verification.**

| Model class | Profile | Ecosystem scaffolding |
|-------------|---------|----------------------|
| Frontier (70B+) | `frontier` | Full tool frame; model may plan and reflect |
| Capable local (8B–14B) | `capable-local` | 3–4 tools per frame; STL plan; verifier on ANALYSE/EVALUATE |
| Small local (≤8B) | `small-local` | 1–2 tools per frame; strict structured output; explicit state machine; CSO carries all progress |

This is **amplification**, not limitation. The protocol adds structure so the model can focus on the one cognitive job it is positioned to do.

---

## 10. Protocol surface (summary)

### Added / reshaped headers

- `CRP-Agent-Capability-Profile` (`frontier` / `capable-local` / `small-local`)
- `CRP-Agent-Model-Capabilities` (`tool-call`, `grammar`, `prefix-cache`, ...)
- `CRP-Agent-Tool-Subset` (tools enabled for this window)
- `CRP-Agent-Execution-Mode` (`single-shot`, `planner-actor`, `react`, `verifier`, `retrieval-then-answer`, `positioned-tool-loop`)
- `CRP-Agent-Loop-Guard` (safety bounds, not capability limits)
- `CRP-LLM-Structured-Output-Mode` / `CRP-LLM-Structured-Output-Schema`
- `CRP-LLM-Prompt-Cache-Hint`
- `CRP-Agent-Operation-State` / `CRP-Agent-Operation-Type` / `CRP-Agent-Operation-Plan`
- `CRP-Tool-Positioning-Frame` / `CRP-Tool-Observation-Count`
- `CRP-Tool-Allowlist` / `CRP-Tool-Blocklist`
- `CRP-Structured-Output-Contract`
- `CRP-Safety-Preventive-Halt`

### Removed headers

- `CRP-Agent-Model-Tier` — replaced by capability profile.
- `CRP-Routing-Target` / `CRP-Routing-Decision` — hybrid routing removed.

### Session token / CSO additions

- `capability_profile`, `operation_state`, `operation_type`, `operation_plan_hash`
- `tcf_selection` — selected capability IDs and why
- `tool_observations` — typed facts from executed capabilities
- `preventive_halt_history` — record of halted frames
- `structured_output_contract`

Full normative definitions are in CRP-SPEC-049 and CRP-SPEC-050.

---

## 11. Implementation roadmap

### Phase 1 — Reframe and specify (now)

- Update README and AGENTS.md tagline to "Context Relay Protocol for Agentic AI."
- Publish CRP-SPEC-049 (revised) and CRP-SPEC-050 (new).
- Publish `schemas/capability-descriptor.json`.
- Add new header constants to `crp/headers/names.py`.

### Phase 2 — Tool Capability Fabric and operation state machine

- Implement `crp/tools/capability_fabric.py`, `descriptor.py`, `executor.py`.
- Implement `crp/stl/operation_state.py` and `tool_positioner.py`.
- Extend `crp/state/cso.py` with `tool_observations` and `preventive_halt_history`.

### Phase 3 — Tool positioning frame and constrained execution

- Build Tool Positioning Frame composer.
- Translate `CRP-Structured-Output-Contract` to OpenAI/Ollama/vLLM/SGLang/llama.cpp.
- Enforce byte-stable prefixes for KV-cache reuse.

### Phase 4 — Preventive safety

- Extend `CRP-Safety-Policy` grammar with `allow-tools`, `block-tools`, `require-oversight-for`, `block-parameter`.
- Implement safety gate that inspects operation frame and tool parameters.
- Add preventive halt response format and audit logging.

### Phase 5 — CRP Comply agent rewrite

- Replace the single ReAct loop with STL-driven operation state machine.
- Register all Comply tools in the TCF with operation-type tags.
- Use TCF retrieval to select 1–3 tools per operation for the SLM path.
- Add verifier operation and constrained decoding.
- Remove frontier fallback; local model is the assigned provider.

### Phase 6 — Benchmark and prove the claim

- Build benchmark comparing:
  - Baseline: 8B model with all 13 tools injected.
  - CRP agentic: 8B model with TCF + STL + CSO + verifier.
- Measure: task success rate, token consumption, latency, schema validity, safety halt rate.
- Publish results in BENCHMARKS.md.

---

## 12. Why this is a defensible strategic move

- **No existing protocol owns "agentic positioning."** MCP owns tool access; A2A/ACP own agent-agent messaging; CRP can own the layer that decides *what the model should do with what context and tools*.
- **SLM-first is a differentiated moat.** Most protocols are designed for frontier models and then retrofitted. Building for the smallest model first forces token efficiency and clean separation of concerns.
- **The codebase is already 80 % there.** CKF, CDR, CDGR, CSO, STL, safety budget, and audit chain are the hard parts. The TCF and operation state machine are the missing glue.
- **The market timing is right.** Local/edge SLM deployment is accelerating; enterprises need a protocol that makes small models trustworthy and capable without cloud dependency.

---

## 13. References

- `SPECS_5_06_2026_CRP_v4/specs/CRP-SPEC-049-slm-agent-execution.md`
- `SPECS_5_06_2026_CRP_v4/specs/CRP-SPEC-050-tool-capability-fabric.md`
- `schemas/capability-descriptor.json`
- `crp-comply/SLM_INTEGRATION_RESEARCH.md`
- `crp-comply/LOCAL_8B_MODEL_ANALYSIS.md`
