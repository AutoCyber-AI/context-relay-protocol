# CRP Cheatsheet — Everything You Need on One Page

**Context Relay Protocol (CRP)** turns any LLM — especially small, local
models — into a governed, tool-using agent. This is the practical reference:
every class, every method, when to reach for it, and copy-pasteable code.
For the "why," see [README.md](README.md) and [site-docs/why-crp.md](site-docs/why-crp.md).
For deep dives, see [`docs/CRPv6_Agent_SDK_Usage_Guide.md`](docs/CRPv6_Agent_SDK_Usage_Guide.md).

> Verified against the running package (not aspirational) — every snippet on
> this page was executed against a real LLM (LM Studio, `meta-llama-3.1-8b-instruct`)
> while writing it.

---

## 1. Install

```bash
pip install crprotocol
# Optional extras this cheatsheet uses:
pip install requests beautifulsoup4   # real web search in Template 2
pip install crprotocol[full]          # NLP extraction, ML models, everything
```

No infrastructure, no server, no Docker. `import crp` and you're running.

---

## 2. The three ways to use CRP — pick the shallowest that solves your problem

| You want... | Use | Effort |
|---|---|---|
| Drop-in governance on an existing LLM call | `crp.Client()` / `crp.SDKClient()` | 3 lines |
| Ingest docs + ask grounded questions | `client.ingest()` + `client.ask()` | 5 lines |
| An agent that calls tools, remembers state, streams, and is safe | `crp.Agent()` | ~10 lines |

---

## 3. Level 0 — Drop-in governance (no tools, no agent)

```python
import crp

client = crp.Client()   # auto-detects OPENAI_API_KEY / ANTHROPIC_API_KEY / Ollama
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Summarise this document: ...",
)
print(output)                    # raw LLM output, unmodified
print(report.quality_tier)       # "S" | "A" | "B" | "C" | "D"
```

**When to use:** you already call an LLM directly and just want context
management, extraction, and quality reporting — no tools, no multi-step
reasoning.

---

## 4. Level 1 — Ingest + ask (grounded Q&A)

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")                       # extraction only, no LLM call, ~7ms/doc
answer = client.ask("Write a complete deployment guide", depth="thorough")

print(answer.text)
print(answer.quality)      # S | A | B | C | D
print(answer.sources)      # [{title, doc_id, used_facts}, ...]
print(answer.crp.risk)     # LOW | MEDIUM | HIGH | CRITICAL
```

**When to use:** RAG over your own documents, with quality/risk reporting
built in — no tool-calling agent loop needed.

---

## 5. Level 2 — `crp.Agent`: the declarative agent SDK

This is the core of CRP v6. **Declare tools + policy + model. The loop is
the protocol's** — you never write a tool-calling while-loop yourself.

```python
import crp

def get_weather(city: str) -> dict:
    """Return the current weather for a city."""
    return {"city": city, "temp": 22, "condition": "sunny"}

agent = crp.Agent(model="local/llama3.1", tools=[get_weather])
result = agent.run("What's the weather in Sydney?")

print(result.answer)              # the final natural-language answer
print(result.crp.risk)            # LOW | MEDIUM | HIGH | CRITICAL
print(result.how_it_was_built)    # e.g. "retrieve → transform"
```

### 5.1 Full `Agent(...)` constructor reference

```python
agent = crp.Agent(
    model=None,                # "local/llama3.1" shortcut, or None if provider= is set
    provider=None,             # a real LLMProvider (see §6) — takes precedence over model=
    tools=None,                # list of callables / dicts / CapabilityDescriptor (§5.2)
    policy=None,                # Policy or PolicyContext (§5.4)
    system="You are a helpful agent.",
    profile=None,               # "frontier" | "capable-local" | "small-local" (§5.3)
    depth="auto",                # "quick" | "standard" | "thorough" | "exhaustive" (§5.5)
    max_operations=12,           # hard cap on operations per run (loop guard)
    temperature=0.2,
    max_tokens=1024,
    max_continuation_windows=1,   # >1 lets long-form ops span multiple windows
    safety="balanced",            # safety profile name or override dict
    intent_classifier=None,       # custom IntentClassifier (defaults to ManagedIntentClassifier)
    oversight_required=None,      # set[SafetyClass] gated behind human approval (§5.6) — NEW
    clarify_handler=None,         # resolves oversight/clarification requests (§5.6) — NEW
)
```

### 5.2 Tools — three ways to declare one

**Plain callable** (the common case — schema + implementation inferred from the signature/docstring):

```python
def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9/5 + 32:.1f}°F"

agent = crp.Agent(provider=provider, tools=[convert_temp])
```

**Dict with an explicit safety class + a real implementation** — the only
way to attach BOTH a real `impl` and a non-default `safety_class` (e.g. to
gate a destructive action — see §5.6):

```python
def _quarantine_host(ip: str, reason: str) -> dict:
    return {"status": "quarantined", "ip": ip}

quarantine_tool = {
    "capability_id": "quarantine_host",
    "description": "Isolate a host from the network. IRREVERSIBLE.",
    "impl": _quarantine_host,
    "input_schema": {
        "type": "object",
        "properties": {"ip": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["ip", "reason"],
    },
    "cost_profile": {"safety_class": "destructive"},   # read-only | mutating | destructive | network | human-oversight
}
```

**`CapabilityDescriptor`** — the lowest-level form (used internally; reach
for this only if you're building your own Tool Capability Fabric registry).

> ⚠️ A dict or `CapabilityDescriptor` WITHOUT `"impl"` registers the tool for
> selection but with no implementation — the agent will select it but never
> actually execute it ("selection-only mode"). Always include `"impl"` for a
> tool you want to actually run.

### 5.3 Capability profiles — how many tools the model sees per step

| Profile | Max tools per step | Use for |
|---|---|---|
| `"frontier"` | 7 | GPT-4o, Claude, large cloud models |
| `"capable-local"` | 4 | 7-8B local models (Llama 3.1 8B, Qwen2.5 7B) |
| `"small-local"` | 2 | ≤4B local models |

This is **positioning, not injection** — the model never sees your whole
tool catalogue, only the 1-7 tools the protocol decided are relevant to the
current step.

### 5.4 Policy

```python
from crp.agent_sdk.policy import Policy

policy = Policy.balanced()                       # default: warn on HIGH, halt on CRITICAL
policy = Policy.strict()                          # halt on HIGH, require grounding ≥0.8
policy = Policy.permissive()                       # halt only on CRITICAL
policy = Policy.grounded(threshold=0.7)            # custom grounding floor

# Builder methods (chainable):
policy = (
    Policy.balanced()
    .block("dangerous_tool")            # blocklist by capability_id
    .allow_only("get_weather", "search")  # allowlist — nothing else is selectable
    .domain("security")                  # restrict to capabilities tagged this domain
    .scope("10.0.0.0/24")                 # authorised_scope for invocation targets
    .clarify(0.3)                          # ambiguity threshold to trigger CLARIFY
)

agent = crp.Agent(provider=provider, tools=[...], policy=policy)
```

### 5.5 Depth — how hard the agent thinks

| Depth | What it enables |
|---|---|
| `"quick"` | Minimal positioning, fastest |
| `"standard"` | Default balance |
| `"thorough"` | **Enables the Verification Relay** (VR) — grounding/step checks run automatically; inspect via `result.verification` |
| `"exhaustive"` | Maximum verification + deepest positioning |

```python
agent = crp.Agent(provider=provider, tools=[...], depth="thorough")
result = agent.run("...")
print(result.verification)
# {'stage': 'dpe_14_verification', 'verification_ratio': 1.0, 'checked': 0,
#  'invalid': 0, 'repairs': 0, 'tier_cap': None, 'risk_floor': 'LOW', 'labels': []}
```

### 5.6 Human-in-the-loop oversight — gate a destructive action at call time

Plan-level "approve this plan" review is not enough for an agent that can
take irreversible actions mid-run. `oversight_required` + `clarify_handler`
gate the *individual tool call*, at the moment the model tries to invoke it —
not just once at the start.

```python
from crp.tools.descriptor import SafetyClass
from crp.security.clarify import ClarificationAction, ClarificationRequest, ClarificationResolution

def approval_handler(request: ClarificationRequest) -> ClarificationResolution:
    print(f"APPROVE? {request.question}  context={request.context}")
    decision = input("y/n: ")
    action = ClarificationAction.ANSWER if decision == "y" else ClarificationAction.ABORT
    return ClarificationResolution(action, answer="approve" if decision == "y" else "deny")

agent = crp.Agent(
    provider=provider,
    tools=[..., quarantine_tool],          # quarantine_tool has safety_class="destructive"
    oversight_required={SafetyClass.DESTRUCTIVE},
    clarify_handler=approval_handler,
)
result = agent.run("Quarantine the compromised host.")
# → the agent halts BEFORE executing quarantine_host, calls approval_handler(),
#   and only executes if the resolution is an approval. Fail-safe default deny.
```

Safety classes: `SafetyClass.READ_ONLY` (default) · `MUTATING` · `DESTRUCTIVE`
· `NETWORK` · `HUMAN_OVERSIGHT`.

### 5.7 Memory / state relay across turns (CSO)

The **Cognitive State Object (CSO)** is what makes multi-turn agents coherent
— it carries established facts, tool observations, and decisions forward
without you re-stating them.

```python
turn1 = agent.run("What's the weather in Sydney?")
turn2 = agent.run("Convert that to Fahrenheit.", prior_cso=turn1.cso)   # "that" resolves via coreference
turn3 = agent.run("What have I asked about so far?", prior_cso=turn2.cso)

print(len(turn3.cso.established_facts))   # grows across the conversation
```

**Do NOT** pass `prior_cso=` across genuinely *independent* cases (e.g. two
unrelated support tickets) — reuse it only for a real continuation of the
same task. Note also that an `Agent` instance's ISA-level turn history
(used for intent classification and coreference) is **not** reset by
`prior_cso=None` — for fully independent cases, construct a fresh `Agent`.

### 5.8 Streaming — `run_stream()` and `run_tel()`

```python
# Simple incremental events:
for event in agent.run_stream("Explain CRP."):
    print(event.kind, event.detail)

# Full AG-UI + governance event stream (for building a UI / CLI dashboard):
for ev in agent.run_tel("What's the weather in London?", prior_cso=turn1.cso):
    print(ev.type.value, ev.payload)
# RUN_STARTED, CUSTOM(crp.intent), REASONING_CONTENT, STEP_STARTED,
# TEXT_MESSAGE_CONTENT, TOOL_CALL_START/ARGS/END, TOOL_CALL_RESULT,
# STEP_FINISHED, CUSTOM(crp.quality), STATE_DELTA, CUSTOM(crp.run_complete),
# STATE_SNAPSHOT, CUSTOM(crp.provenance — HMAC chain), RUN_FINISHED
```

### 5.9 `AgentResponse` — every field

| Field | Type | Meaning |
|---|---|---|
| `.answer` / `.text` | `str` | Final natural-language answer |
| `.cso` | `CognitiveStateObject` | Pass to the next turn's `prior_cso=` |
| `.operations` | `list[str]` | e.g. `["retrieve", "transform"]` |
| `.how_it_was_built` | `str` | `"retrieve → transform"` |
| `.halted` | `bool` | `True` if the run stopped early (oversight denial, policy violation, provider failure) |
| `.crp.risk` | `str` | `LOW \| MEDIUM \| HIGH \| CRITICAL` |
| `.crp.grounded` | `bool` | Whether the run completed without halting |
| `.crp.chain_valid` | `bool` | HMAC audit-chain integrity |
| `.sources` | `list[dict]` | Tool observations surfaced as sources |
| `.verification` | `dict \| None` | Set when `depth="thorough"`/`"exhaustive"` (§5.5) |
| `.intent` | `dict` | ISA speech-act/intent classification for this turn |
| `.open_questions` | `list[str]` | Carried in the CSO |
| `.complete` | `bool` | Finished without halting and goal fully integrated |

---

## 6. Providers — point at any LLM

```python
from crp.providers.openai import OpenAIAdapter        # OpenAI + any OpenAI-compatible server
from crp.providers.anthropic import AnthropicAdapter
from crp.providers.ollama import OllamaAdapter
from crp.providers.custom import CustomProvider         # wrap anything in 3 lines

# Cloud
provider = OpenAIAdapter(model="gpt-4o-mini")                          # reads OPENAI_API_KEY
provider = AnthropicAdapter(model="claude-3-5-haiku-20241022")         # reads ANTHROPIC_API_KEY

# Local — LM Studio / vLLM / any OpenAI-compatible server
provider = OpenAIAdapter(model="meta-llama-3.1-8b-instruct", base_url="http://localhost:1234/v1", api_key="lm-studio")

# Local — Ollama
provider = OllamaAdapter(model="llama3.1", base_url="http://localhost:11434")

# Anything else
provider = CustomProvider(
    generate_fn=lambda messages, **kw: ("response text", "stop"),
    count_tokens_fn=lambda text: len(text) // 4,
    context_size=128_000,
)
```

> ⚠️ The class names are **`OpenAIAdapter`**, **`AnthropicAdapter`**,
> **`OllamaAdapter`** — not `OpenAIProvider`/`AnthropicProvider`/`OllamaProvider`.
> These import from `crp.providers.openai` / `.anthropic` / `.ollama`, not
> `..._provider` modules.

### Auto-detect the best available provider (used by every template in `examples/templates/`)

```python
# examples/templates/_shared.py — copy this pattern into your own project
import os, urllib.request

def resolve_provider(default_model="meta-llama-3.1-8b-instruct"):
    if _reachable("http://localhost:1234/v1/models"):
        from crp.providers.openai import OpenAIAdapter
        return OpenAIAdapter(model=os.environ.get("CRP_LMSTUDIO_MODEL", default_model),
                              base_url="http://localhost:1234/v1", api_key="lm-studio")
    if os.environ.get("OPENAI_API_KEY"):
        from crp.providers.openai import OpenAIAdapter
        return OpenAIAdapter(model="gpt-4o-mini")
    # ... Anthropic, Ollama, then raise a clear error
```

---

## 7. Local / small-model gotchas CRP already handles for you

| Problem | What CRP does |
|---|---|
| LM Studio loads a model at a smaller context than its family max | `OpenAIAdapter` probes the server's native `/api/v0/models` for `loaded_context_length` — never guesses from a static table |
| A local model emits OpenAI-style `{"name":..., "parameters":...}` instead of CRP's `{"capability_id":..., "arguments":...}` | `parse_tool_call` normalizes both shapes |
| A model ignores "answer in prose, not JSON" | The synthesis step retries once with a stronger instruction, then falls back to a deterministic bullet-list of facts — you will **never** see raw JSON as a final answer |
| A provider call genuinely fails mid-run | The run halts honestly (`risk=CRITICAL`, `grounded=False`) instead of silently reporting success on empty output |
| Total context overflow across a long tool chain | `guard_prompt_budget()` trims the oldest carried-forward state, never the current task frame |

---

## 8. Full protocol surface — where to find each capability

| Capability | Module | Spec |
|---|---|---|
| Agent SDK (`crp.Agent`) | `crp.agent_sdk` | SPEC-059 |
| Policy | `crp.agent_sdk.policy` | SPEC-059 §4 |
| Tool Capability Fabric | `crp.tools.capability_fabric` | SPEC-050 |
| Positioned loop (low-level) | `crp.stl.positioned` | SPEC-049/050 |
| Cognitive State Object | `crp.state.cso` | SPEC-030 |
| Intent + coreference (ISA) | `crp.isa` | SPEC-052 |
| Clarification protocol | `crp.clr` / `crp.security.clarify` | SPEC-053/033 |
| Verification Relay | `crp.vr` | SPEC-049 |
| Transparency stream (TEL) | `crp.tel` | SPEC-056 |
| Structured decoding | `crp.gateway.structured_decoder` / `gbnf.py` | SPEC-054 |
| Quality-tier routing | `crp.qsr` | SPEC-050 |
| Epistemic profiles (semantic entropy) | `crp.ep` | SPEC-055 |
| Bi-temporal knowledge | `crp.btf` | SPEC-057 |
| Predictive positioning | `crp.pp` | SPEC-051 |
| Gateway (OpenAI-compatible endpoint) | `crp.gateway` | SPEC-016 |
| Safety Control Plane | `crp.security.control_plane` | SPEC-033/034 |
| HMAC audit chain | `crp.provenance.window_chain` | SPEC-011 |

---

## 9. Where to go next

- **3 flagship templates** — [`examples/templates/`](examples/templates/README.md) (security analyst, research assistant, daily assistant)
- **Live proof scripts** — [`examples/crp_demos/`](examples/crp_demos/README.md) (raw LLM vs. CRP, same model, same task)
- **Full spec index** — [`specification/`](specification/) and [`SPECS_5_06_2026_CRP_v4/specs/`](SPECS_5_06_2026_CRP_v4/specs/)
- **Public docs site** — [crprotocol.io](https://crprotocol.io)
