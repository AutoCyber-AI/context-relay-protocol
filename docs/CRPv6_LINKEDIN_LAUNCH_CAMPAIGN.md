# CRPv6 LinkedIn Launch Campaign

> 2-week progressive launch series for CRPv6.  
> Tone: technical, confident, proof-first.  
> Goal: position CRP as the open protocol that turns small local models into governed, tool-using agents.

---

## Campaign narrative arc

1. **Problem:** Big-context prompting breaks agentic AI.
2. **Principle:** Position, don't stuff — every LLM call gets its own scoped envelope.
3. **Proof:** Same 8B model, raw vs. CRPv6, in a terminal recording.
4. **Product:** CRPv6 open-source SDK + managed Gateway, Comply, Scan.
5. **Call to action:** Try it, star the repo, book a managed-cloud demo.

---

## Week 1 — Awareness and proof

### Post 1/10 — The launch announcement

**Day 1 (Monday)**

> We are launching CRPv6.
>
> Context Relay Protocol is an open protocol that turns small local language models into governed, tool-using agents — without relying on massive context windows or cloud APIs.
>
> It is not another chat wrapper. It is a middleware layer that:
> - positions the right task for every LLM call,
> - selects the right tools,
> - carries state forward across steps,
> - and emits governance metadata on every response.
>
> Same 8B model on your laptop. Two results. Video below.
>
> Repo: github.com/AutoCyber-AI/context-relay-protocol  
> Docs: crprotocol.io
>
> #AgenticAI #LocalLLM #OpenSource #CRPv6

**Media:** 90-second demo video (`live_crp_slm_proof.py`).

---

### Post 2/10 — The raw vs. CRP comparison

**Day 2 (Tuesday)**

> Why raw prompting fails for agents.
>
> We ran the same Meta Llama 3.1 8B model twice on the same laptop:
>
> Raw prompt:
> - returns JSON and stops,
> - hallucinates fake function-composition syntax,
> - claims it has no knowledge,
> - and truncates long outputs.
>
> Through CRPv6:
> - the same model executes tools,
> - chains two tools with real intermediate outputs,
> - retrieves from a local knowledge base,
> - and writes a structured 5-paragraph report.
>
> The model did not change. The scaffolding did.
>
> #LLM #ToolUse #LocalAI #CRPv6

**Media:** side-by-side screenshot from the demo.

---

### Post 3/10 — What CRP emits

**Day 3 (Wednesday)**

> Every CRPv6 response carries a governance block.
>
> Not after the fact. At runtime.
>
> - `risk`: LOW | MEDIUM | HIGH | CRITICAL
> - `grounded`: true when the answer is backed by a tool or source
> - `chain_valid`: true when the HMAC audit chain is intact
> - `operations`: RETRIEVE, TRANSFORM, ANALYSE, GENERATE, VERIFY, REVISE
> - `sources`: fact IDs, capability IDs, provenance timestamps
>
> This is what makes an agent auditable. Not slides. Terminal output.
>
> #AIGovernance #Observability #CRPv6

**Media:** terminal screenshot of the JSON governance block.

---

### Post 4/10 — The Agent SDK

**Day 4 (Thursday)**

> Three lines to a governed agent.
>
> ```python
> import crp
>
> agent = crp.Agent(
>     provider=my_local_model,
>     tools=[get_weather, search_docs],
>     system="You are a helpful assistant.",
>     profile="small-local",
> )
>
> result = agent.run("What is the weather in Sydney?")
> ```
>
> `result.answer` gives you the response.  
> `result.crp.risk`, `result.crp.grounded`, `result.sources` give you the proof.
>
> #Python #SDK #AgenticAI #CRPv6

**Media:** code snippet image or terminal recording.

---

### Post 5/10 — ML-first foundation

**Day 5 (Friday)**

> CRPv6 ships with three managed models on Hugging Face under AutoCyberAI:
>
> - `crp-intent-setfit` — task intent classification, 0.934 held-out accuracy
> - `crp-safety-deberta-v1` — adversarial safety detection, 12/12 pass
> - `crp-prm-deberta-v1` — step-level process reward model, AUC 0.793
>
> They are optional. When available, CRP uses them. When they are not, the protocol falls back to rule-based intent and safety checks.
>
> ML is the default. Rules are the degraded path.
>
> #HuggingFace #SmallModels #MachineLearning #CRPv6

**Media:** Hugging Face model cards or benchmark table.

---

## Week 2 — Product depth and call to action

### Post 6/10 — CRP Gateway

**Day 8 (Monday)**

> CRP Gateway is an OpenAI-compatible runtime that wraps any provider with CRP governance.
>
> One `base_url` change and every call through your application gets:
> - safety screening,
> - tool positioning,
> - audit logging,
> - provider routing,
> - and per-tenant quotas.
>
> Self-host or run managed at gateway.crprotocol.io.
>
> #LLMGateway #AIInfrastructure #CRPv6

**Media:** architecture diagram or console screenshot.

---

### Post 7/10 — CRP Comply

**Day 9 (Tuesday)**

> EU AI Act enforcement begins August 2026. Fines go up to €35 million or 7% of global turnover.
>
> CRP Comply is a compliance proxy. Change one line — your `base_url` — and every LLM call is scanned, logged, and mapped to EU AI Act, ISO 42001, GDPR, HIPAA, SOC 2, and NIST AI RMF obligations.
>
> It does not just document compliance. It proves it with a tamper-evident audit chain.
>
> #Compliance #EUAiAct #ISO42001 #GDPR #CRPv6

**Media:** compliance report screenshot or evidence-pack diagram.

---

### Post 8/10 — CRP Scan

**Day 10 (Wednesday)**

> CRP Scan is a GitHub Action that finds ungoverned AI calls in your codebase.
>
> Add one line to your workflow:
> ```yaml
> - uses: AutoCyber-AI/crp-scan@v1
> ```
>
> It detects missing safety policies, hardcoded prompts, missing audit trails, and version drift — then opens a remediation PR, never a direct commit.
>
> #DevOps #GitHubActions #AIGovernance #CRPv6

**Media:** GitHub workflow screenshot or SARIF report.

---

### Post 9/10 — Comparison: MCP, A2A, OpenAI Agents, CRP

**Day 11 (Thursday)**

> Quick comparison without the FUD.
>
> - **MCP** exposes tools to a model.
> - **A2A** connects agents to each other.
> - **OpenAI Agents SDK** gives you an OpenAI-shaped agent loop.
> - **CRP** positions every LLM call on the right task, with the right context and tools, and emits governance metadata — model-agnostic and provider-agnostic.
>
> CRP does not replace them. It sits between your orchestration and the LLM, making every call cheaper, safer, and observable.
>
> #MCP #A2A #OpenAI #AgenticAI #CRPv6

**Media:** simple diagram or table.

---

### Post 10/10 — Call to action

**Day 12 (Friday)**

> CRPv6 is live.
>
> Try it in three minutes:
> ```bash
> pip install crprotocol
> python examples/crp_demos/live_crp_slm_proof.py
> ```
>
> Or book a managed-cloud demo for CRP Gateway, Comply, or Scan.
>
> Repo: github.com/AutoCyber-AI/context-relay-protocol  
> Docs: crprotocol.io  
> Products: crprotocol.io/products
>
> Star the repo. Run the demo. Tell us what you build.
>
> #Launch #OpenSource #AgenticAI #CRPv6

**Media:** terminal recording or product screenshot.

---

## Optional mid-campaign engagement posts

### Engagement post A — poll

> Poll: what is the biggest blocker for running agents on local models?
>
> 1. Tool-use reliability
> 2. Long-form coherence
> 3. Observability / governance
> 4. Latency
>
> Comment below. We will share CRPv6 results for the winner.

### Engagement post B — myth-busting

> Myth: "You need a 70B model to run real agents."
>
> Fact: You need the right scaffolding. An 8B model with CRPv6 can execute tools, chain calls, retrieve from a KB, and emit governance. The model matters less than the architecture around it.
>
> Video proof in the comments.

---

## Hashtags to rotate

Primary: `#CRPv6` `#AgenticAI` `#LocalLLM`  
Secondary: `#OpenSource` `#AIGovernance` `#ToolUse` `#SLM` `#MCP` `#Compliance` `#EUAiAct`

---

## Media checklist

- [ ] 90-second demo video (`live_crp_slm_proof.py`).
- [ ] Side-by-side raw vs. CRP screenshot.
- [ ] Governance JSON screenshot.
- [ ] Agent SDK code snippet image.
- [ ] Hugging Face model cards screenshot.
- [ ] Gateway / Comply / Scan product screenshots.
- [ ] Architecture diagram (CRP vs. MCP/A2A).

---

## Posting cadence

- Week 1: Monday, Tuesday, Wednesday, Thursday, Friday at 9:00 AM local time.
- Week 2: Monday, Tuesday, Wednesday, Thursday, Friday at 9:00 AM local time.
- Optional engagement posts on Saturday or Sunday if engagement is strong.

---

## Success metrics

- Repo stars on `AutoCyber-AI/context-relay-protocol`.
- Demo video views and shares.
- Inbound requests for managed-cloud demos.
- PyPI download velocity for `crprotocol`.
