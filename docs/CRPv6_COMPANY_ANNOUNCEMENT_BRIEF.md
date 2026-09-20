# CRP v6 Company Announcement — Messaging Brief

> **Prepared for:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
> **Date:** 2026-09-02  
> **Version:** CRP 6.1.1  
> **Status:** Ready for developer announcement; Wave 3 hosted SaaS remains future work.

---

## 1. The one-sentence mission

**Context Relay Protocol (CRP) v6 is the first agentic positioning layer that turns any LLM — especially small, local models — into a governed, tool-using agent with built-in safety, grounding, provenance, and transparency evidence.**

---

## 2. The announcement headline options

Pick one primary and one secondary:

1. **Primary:** *AutoCyber AI releases CRP v6.1.1: a governed, SLM-first agentic protocol you can install today.*
2. **Secondary:** *CRP v6 proves every AI call: signed audit chains, safety scans, and grounding evidence out of the box.*
3. **Alternative:** *CRP v6 lets developers declare agents in 5 lines — and define how they reason, safeguard, and show their work.*

---

## 3. What CRP v6 actually ships today

Use this section to anchor every claim in verifiable fact. Every bullet below maps to real code and tests.

| Claim | Evidence in the repo | How to verify |
|-------|----------------------|---------------|
| **Installable today** | `pip install crprotocol` works; `dist/crprotocol-6.1.1-*` built and verified | `python -c "import crp; print(crp.__version__)"` |
| **3 trained ML models published** | `AutoCyberAI/crp-intent-setfit`, `crp-prm-deberta-v1`, `crp-safety-deberta-v1` on Hugging Face | `crp download-models` or browse Hugging Face |
| **Agent SDK (`crp.Agent`)** | `crp/agent_sdk/agent.py` — declarative `tools + policy + model` | `examples/templates/*.py` |
| **Cognitive presets** | `crp/cognition/` — user-defined reasoning, safeguards, emotions, output profile | `examples/crp_demos/robot_safeguard_live_proof.py` |
| **Transparency stream (AG-UI + CRP)** | `crp/tel/` emits `RUN_STARTED`, `REASONING_*`, `TOOL_CALL_*`, `crp.quality`, `crp.provenance` | `agent.run_tel(...)` or `examples/crp_demos/live_crp_slm_proof.py` |
| **HMAC-signed audit chain** | `crp/provenance/window_chain.py`, `crp/security/audit_trail.py` | `client.audit.verify()` |
| **Human-in-the-loop checkpoints** | `crp/security/clarify.py`, `examples/templates/security_analyst_agent.py` | `CRP_DEMO_DENY=1 python security_analyst_agent.py` |
| **Tool Capability Fabric** | `crp/tools/capability_fabric.py`, `crp/tools/descriptor.py` | `tests/test_tcf.py`, `tests/test_tool_relay.py` |
| **Verification Relay** | `crp/vr/` — PRM + symbolic verifiers | `tests/test_vr.py` |
| **Quality tiers + provenance** | `AgentResponse.crp.risk`, `.grounded`, `.chain_valid`, `.quality_tier` | `examples/crp_demos/live_llm_vs_crp.py` |
| **Model-agnostic** | Adapters for OpenAI, Anthropic, Ollama, llama.cpp, LM Studio, custom | `crp/providers/` |
| **Full test gate** | 3,291 non-live tests pass | `pytest tests/` |
| **SQB benchmark** | All cases pass against Kimi-k2.6 | `examples/crp_demos/sqb_benchmark.py --mode kimi` |

---

## 4. The three target audiences

### Audience A — AI-native developers and startups
**Pain:** Building agents means hand-writing tool loops, safety gates, memory, and audit trails.
**Message:** `crp.Agent(model="local/llama3.1", tools=[...])` gives you a governed agent in 5 lines. No infrastructure. No tool-calling while-loop. No prompt engineering for safety.

### Audience B — Regulated enterprises / security teams
**Pain:** EU AI Act, ISO 42001, NIST AI RMF, SOC 2-for-AI require evidence that controls operate — not just that they exist.
**Message:** Every CRP call emits an HMAC-signed, tamper-evident audit trail with risk scores, grounding verdicts, and safety scan results. Evidence packs from runtime data, not consultant interviews.

### Audience C — Open-source and standards communities
**Pain:** The agentic ecosystem is fragmenting around incompatible tool and agent protocols.
**Message:** CRP is model-agnostic, provider-agnostic, and AG-UI-compatible. It positions agents rather than replacing MCP or A2A; it adds the governance and reasoning layer they lack.

---

## 5. Core value propositions (use these exactly)

1. **Positioned agentic execution.**  
   CRP does not just expose tools (MCP) or connect agents (A2A). It classifies intent, selects operations, positions only the relevant tools, runs safety checks, and carries state forward.

2. **User-defined reasoning and safeguards.**  
   Developers and end users can declare how the agent thinks (reasoning phases), what it must never do (safeguards with halt/ask/warn), and how it should respond (emotions, output profile) — all in a simple YAML/Python preset.

3. **Governance by default.**  
   13-stage safety scan, prompt-injection shield, PII detection, human-in-the-loop checkpoints, and policy enforcement run on every call — not as an afterthought.

4. **Prove it, don't claim it.**  
   Every response carries `risk`, `grounded`, `chain_valid`, sources, and an HMAC audit link. Regulators and auditors get runtime evidence, not architecture diagrams.

5. **Small-model first.**  
   CRP is designed for local 8B and smaller models. The 3 published CRP models (intent, PRM, safety) are CPU-friendly and fallback-safe.

6. **Progressive disclosure.**  
   Start with `crp.Client()` (1 line), grow into `crp.SDKClient()`, then `crp.Agent()` — the same protocol engine at every level.

---

## 6. Key differentiators vs alternatives

| Against | CRP's difference |
|---------|------------------|
| **Raw OpenAI/Anthropic SDK** | CRP adds context lifecycle, safety, provenance, and tool-positioning without touching the model output. |
| **MCP (Model Context Protocol)** | MCP exposes tools; CRP decides which agent uses which tool, when, and with what context. |
| **A2A (Agent-to-Agent)** | A2A connects agents; CRP positions each agent on the right task with the right state and tools. |
| **LangChain / LlamaIndex** | CRP is a protocol, not a framework. It has a smaller API surface and is model/provider-agnostic by design. |
| **MemGPT / Letta** | CRP manages context *outside* the window with zero in-window overhead; no memory-management prompts inside the model input. |

---

## 7. Honest boundaries — what v6 is *not* yet

Do not announce the following as complete:

- **Hosted multi-tenant SaaS:** Gateway production auth, Stripe/Clerk billing, and CDN-hosted console are Wave 3 and not yet live.
- **Turnkey no-code UI:** The console works as an embedded page and is being extracted into a CDN package; full SaaS console is in progress.
- **Universal long-horizon planning:** Multi-step plans with backtracking work for bounded tasks; open-ended, hours-long autonomy remains research.
- **Weight-level continual learning:** CRP does not fine-tune models from user data in this release.

**Safe framing:** *"CRP v6 is a production-ready library and self-hosted protocol today. Managed-cloud SaaS is on the roadmap for Wave 3."*

---

## 8. Recommended press release / LinkedIn skeleton

### Headline
> AutoCyber AI Releases CRP v6, a Governed, SLM-First Agentic Protocol Installable Today

### Subhead
> New open-source protocol turns small local models into tool-using agents with built-in safety, grounding, and tamper-evident audit evidence.

### Lead paragraph
> AutoCyber AI today announced Context Relay Protocol (CRP) v6, the first agentic positioning layer designed to run governed AI agents on small, local language models. CRP v6 is available now via `pip install crprotocol` and includes a declarative Agent SDK, three trained open-source models published on Hugging Face, an AG-UI-compatible transparency stream, and an HMAC-signed audit chain.

### Three supporting bullets
> - **Declarative agents in 5 lines:** `crp.Agent(model="local/llama3.1", tools=[...])` runs the tool loop, safety checks, memory, and verification automatically.
> - **Evidence by default:** Every call emits `risk`, `grounded`, `chain_valid`, sources, and audit-hash metadata required by EU AI Act, ISO 42001, and NIST AI RMF.
> - **Model-agnostic and local-first:** Works with OpenAI, Anthropic, Ollama, LM Studio, llama.cpp, and custom endpoints; ships with CPU-friendly intent, PRM, and safety models.

### Quote placeholder
> *"Most AI governance is a promise. CRP is proof. Every call produces signed evidence that safety, grounding, and policy controls actually ran."* — Constantinos Vidiniotis, Founder, AutoCyber AI

### Closing / CTA
> CRP v6 is available under the Elastic License 2.0 at https://crprotocol.io and https://github.com/AutoCyber-AI/context-relay-protocol. Managed-cloud Gateway and Comply services are planned for the next wave.

---

## 9. Messaging do's and don'ts

### Do
- Say **"governed agentic protocol"** and **"agentic positioning layer."**
- Say **"SLM-first"** or **"small-model-first."**
- Say **"evidence"** and **"tamper-evident audit chain."**
- Say **"install today"** because `pip install crprotocol` works.
- Say **"model-agnostic"** and give examples (OpenAI, Anthropic, local).

### Don't
- Don't call CRP a "framework" — it is a protocol and SDK.
- Don't claim CRP replaces MCP or A2A; it complements them.
- Don't claim the hosted SaaS is live today.
- Don't claim the PRM is a strict gate today; it is advisory with symbolic verifiers handling hard gating.
- Don't claim 100% hallucination elimination; say "risk-scored" and "grounding evidence."

---

## 10. Benchmark and evidence claims

Only make claims backed by data in the repo:

| Claim | Source | Safe wording |
|-------|--------|--------------|
| 11.8× more completed output | `docs/Analysis_of_benchmark_results.md` / `examples/crp_demos/quality_benchmark.py` | "Up to 11.8× more content completed in benchmarks" |
| <50 ms overhead | SPEC-026 / `tests/test_benchmarks.py` | "Designed for <50 ms overhead per call" |
| 0.934 intent accuracy | `docs/CRPv6_Operational_Readiness_Report.md` | "CRP intent classifier: 0.934 held-out accuracy" |
| 12/12 adversarial safety pass | `docs/CRPv6_Operational_Readiness_Report.md` | "Safety classifier: 12/12 adversarial pass rate in eval" |
| 3232 tests pass | `tests/` full suite | "Verified by 3232 non-live tests" |

---

## 11. Related links to include in any announcement

- Website: https://crprotocol.io
- GitHub: https://github.com/AutoCyber-AI/context-relay-protocol
- PyPI: https://pypi.org/project/crprotocol/ (after user uploads 6.0.1)
- Hugging Face: https://huggingface.co/AutoCyberAI
- Docs: `docs/CRPv6_Operational_Readiness_Report.md`, `docs/CRP_SDK_HARDENING_STATUS_2026-08-26.md`
