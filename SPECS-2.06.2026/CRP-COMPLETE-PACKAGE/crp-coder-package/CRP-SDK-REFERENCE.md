# CRP SDK — Complete Interface Reference ("The Steering Wheel")

**Companion to:** CRP-SPEC-032 (Developer Experience)
**Audience:** Developers using CRP, and the engineers building the SDK
**Principle:** Progressive disclosure — Level 0/1 is 99% of usage. Everything below Level 1 is optional and discoverable, never required.

This is the complete developer-facing surface. Every CRP capability
across the 32 specs is reachable from here, but the common path is
five lines. Python shown; the same shape applies to the TypeScript SDK.

---

## INSTALL

```bash
pip install crprotocol            # core SDK
pip install crprotocol[full]      # + local model support, all ingest formats
```

```python
import crp
```

---

## LEVEL 0 — GOVERNANCE (drop-in, zero new concepts)

### 0.1 The drop-in client (existing OpenAI/Anthropic code)

```python
# Works with the official OpenAI SDK unchanged — just point it at CRP
from openai import OpenAI
client = OpenAI(api_key="crp_gw_...", base_url="https://gateway.crprotocol.io/v1")
# Every call now governed. Nothing else changes.
```

### 0.2 The native client (recommended for new code)

```python
client = crp.Client()                          # sane defaults, auto provider
client = crp.Client(model="gpt-4o-mini")       # pick a model
client = crp.Client(model="local:llama-3.1-8b")# local via LM Studio/Ollama
client = crp.Client(api_key="crp_gw_...")      # hosted gateway
```

### 0.3 The governance summary on every result

```python
r = client.complete("Summarise the EU AI Act")   # plain completion

r.text                 # the output string
r.crp.risk             # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
r.crp.risk_score       # 0.0–1.0
r.crp.grounded         # bool — was it grounded in provided context
r.crp.grounding_pct    # 0.0–1.0
r.crp.fabrications     # int — count of unsupported invented claims
r.crp.compliant        # bool — passed configured compliance checks
r.crp.eu_ai_act        # "MINIMAL" | "LIMITED" | "HIGH" | "UNACCEPTABLE"
r.crp.audit_url        # tamper-evident audit trail deep link
r.crp.chain_valid      # bool — HMAC provenance chain intact
```

### 0.4 Governance is enforced, not just reported

```python
# If policy says halt-on CRITICAL and the model produces critical-risk
# output, the call raises — caught by normal error handling:
try:
    r = client.complete("...")
except crp.SafetyHalt as e:
    print(e.reason)        # "CRITICAL hallucination risk"
    print(e.audit_url)     # evidence
    # optional: allow with human review
    r = client.complete("...", on_risk="review")
```

---

## LEVEL 1 — QUALITY (one concept: give CRP knowledge, then ask)

### 1.1 ingest — give CRP your knowledge (forgiving, any input)

```python
client.ingest("./docs/")                       # a directory (recursive)
client.ingest("manual.pdf")                    # a single file
client.ingest("https://example.com/guide")     # a URL
client.ingest("Raw text as a string")          # a string
client.ingest(["a.md", "b.pdf", url, text])    # any mix

# Optional metadata (still Level 1, still one concept)
client.ingest("./regs/", authority="regulatory", tags=["eu-ai-act"])
client.ingest("./news/", freshness="volatile")  # ages out faster (SPEC-027/029)

# ingest returns a handle you can inspect or remove
doc = client.ingest("manual.pdf")
doc.id                 # "doc_a7f3..."
doc.facts              # number of facts extracted
doc.status             # "ready"
client.forget(doc.id)  # GDPR erasure — removes from CKF (SPEC-009 §8.3)
```

### 1.2 ask — the happy path (everything automatic behind it)

```python
a = client.ask("Write a complete guide to our deployment process")

a.text                 # the full, grounded, coherent output
a.quality              # "S" | "A" | "B" | "C" | "D" — one letter
a.grounded             # bool
a.sources              # [{title, doc_id, used_facts}]
a.words                # int
a.complete             # bool — did it cover the whole task
a.crp                  # the same governance summary as Level 0
```

Behind `ask`: task classification + depth negotiation (STL, SPEC-031),
CDR/CDGR retrieval (024/025), multi-window continuation with CSO relay
(030/004), DPE verification (005), assembly. The developer sees none of it.

### 1.3 stream — same, token by token

```python
for chunk in client.ask_stream("Write the guide"):
    print(chunk.text, end="")
# final governance summary available after the stream:
print(client.last.crp.risk)
```

### 1.4 Conversation — just a session (no new concept)

```python
chat = client.session()

chat.ask("How do I configure etcd?")
chat.ask("What about TLS for it?")          # "it" auto-resolved (SPEC-028)
chat.ask("Actually, back to backups")        # thread switch, auto
chat.ask("What did you say about ports?")    # reference resolution, auto

chat.history            # list of turns
chat.active_thread      # "etcd-config"
chat.reset()            # clear conversational context (CKF persists)
```

---

## LEVEL 2 — CONTROL (power users; each is one optional knob)

### 2.1 Depth (plain words; default auto)

```python
client.ask("...", depth="quick")       # D1–D2: fast, shallow
client.ask("...", depth="standard")    # D3: default-ish
client.ask("...", depth="thorough")    # D4: deep analysis
client.ask("...", depth="exhaustive")  # D5: full decomposition + revision
client.ask("...", depth="auto")        # STL negotiates (default)
```

### 2.2 Tools (a decorator; agentic grounding automatic)

```python
@client.tool
def get_metrics(service: str) -> dict:
    """Current CPU/memory for a service."""   # docstring = tool description
    return fetch(service)

@client.tool(freshness="realtime")             # result stales in 30s (SPEC-029)
def get_price(symbol: str) -> float:
    return market.price(symbol)

# Now ask — CRP calls tools as needed, grounds decisions in results,
# records tool provenance, links results to decisions (SPEC-030 §8)
a = client.ask("Should we scale the payment service?")
a.decisions            # [{choice, rationale, from_tool: "get_metrics", ...}]
a.tool_calls           # [{tool, args, result_summary, provenance_hash}]
```

### 2.3 Safety (profile or small dict; never raw directives)

```python
client = crp.Client(safety="balanced")    # default
client = crp.Client(safety="strict")      # halt on HIGH+
client = crp.Client(safety="medical")     # SPEC-006 industry profile
client = crp.Client(safety="financial")
client = crp.Client(safety="public")      # public-facing chatbot profile

# fine-grained but still readable
client = crp.Client(safety={
    "halt_on": "CRITICAL",
    "require_grounding": 0.80,
    "block_fabrication": True,
    "oversight": "human-review",           # route risky outputs to a human
})

# per-call override
client.ask("...", safety="strict")
```

### 2.4 Inspecting reasoning (the CSO, made friendly)

```python
a = client.ask("Design our database architecture")

a.decisions                 # the Cognitive State Object, readable
# [
#   {choice: "PostgreSQL", rationale: "ACID + team expertise",
#    alternatives: ["MongoDB", "DynamoDB"], sources: [...]},
#   ...
# ]
a.how_it_was_built          # STL operation sequence, human-readable
# ["RETRIEVE requirements", "COMPARE 3 databases",
#  "ANALYSE tradeoffs", "GENERATE recommendation"]
a.open_questions            # things CRP flagged as unresolved
```

### 2.5 Knowledge control

```python
client.knowledge.stats()              # facts, communities, coverage depth
client.knowledge.search("etcd")       # inspect what CRP knows
client.knowledge.mode                 # "zero-ckf" | "partial" | "full" (SPEC-017)
client.knowledge.packs(["eu-ai-act", "iso-42001"])   # default knowledge packs
```

### 2.6 Output shaping

```python
client.ask("...", format="markdown")          # or "json", "html"
client.ask("...", max_words=5000)
client.ask("...", style="technical")           # register/tone
client.ask("...", schema=MyPydanticModel)       # structured output, validated
```

---

## LEVEL 3 — INFRASTRUCTURE (compliance / platform teams)

### 3.1 Raw protocol surface

```python
r = client.complete("...")
r.crp.headers          # all ~58 CRP-* headers, raw (for proxy/SIEM)
r.crp.dpe              # full 13-stage DPE report (SPEC-005)
r.crp.cso              # raw Cognitive State Object + dependency graph
r.crp.envelope         # what was retrieved and packed (SPEC-003)
```

### 3.2 Audit & provenance (SPEC-011)

```python
client.audit.export(format="ocsf")             # SIEM
client.audit.export(format="sarif")            # code scanning
client.audit.export(format="ndjson")           # raw
client.audit.verify_chain(session_id)          # → VALID | BROKEN at window N
client.audit.events(session_id)                # 30+ event types
```

### 3.3 Compliance evidence (SPEC-010)

```python
client.compliance.generate("eu-ai-act-art-11")  # Technical Documentation
client.compliance.generate("dpia")              # GDPR
client.compliance.generate("iso-42001")
client.compliance.controls_met                  # "33/35"
client.compliance.connect_comply(org_key="...") # stream to CRP Comply
```

### 3.4 Conformance (SPEC-014 / SPEC-026)

```python
crp.conformance.run(level="standard")           # test vectors
crp.conformance.sqb(testcase, baseline)         # Semantic Quality Benchmark
# → {factual_f1, multi_hop_recall, judge_score, beats_baseline: bool}
```

### 3.5 Amplification (SPEC-018–023; OPT-IN, async, off by default)

```python
# Only for weak local models on async, quality-critical tasks.
# NEVER on by default. Declares cost up front.
a = client.ask(
    "Complex analysis task",
    amplify="full",            # air,cqr,cld,ros — SPEC-023 boundary
    amplify_async=True,        # required for multi-pass
)
a.amplification.passes         # how many inference passes were used
a.amplification.estimate       # cost shown before running
# On a strong model, amplify is ignored with a warning (SPEC-023 §3.4)
```

### 3.6 Multi-agent (SPEC-012)

```python
orchestrator = client.agent(role="orchestrator", safety="strict")
specialist    = client.agent(role="legal", safety="medical")

orchestrator.delegate(specialist, task="review the contract clause")
# safety budget propagates across agents; policy inheritance enforced;
# circuit breaker halts the chain if cumulative risk depletes the budget
orchestrator.safety_budget     # 0.0–1.0, shared across the chain
```

---

## THE COMPLETE METHOD MAP (quick reference)

```
Client()                          create a client
  .complete(prompt)               single governed completion (Level 0)
  .ingest(source)                 add knowledge (Level 1)
  .forget(doc_id)                 GDPR erasure
  .ask(task)                      the happy path — full pipeline (Level 1)
  .ask_stream(task)               streaming ask
  .session()                      conversational session (Level 1)
  .tool / @client.tool            register a tool (Level 2)
  .agent(role)                    multi-agent (Level 3)
  .knowledge.*                    inspect/control the CKF (Level 2)
  .audit.*                        provenance & export (Level 3)
  .compliance.*                   evidence generation (Level 3)
  .last                           the most recent result object

Result (.ask / .complete return):
  .text .quality .grounded .sources .words .complete
  .decisions .how_it_was_built .open_questions     (reasoning)
  .tool_calls .amplification                        (if used)
  .crp.{risk, grounded, compliant, eu_ai_act, audit_url, chain_valid}
  .crp.{headers, dpe, cso, envelope}                (Level 3 raw)

Client config:
  model=, api_key=, base_url=, safety=, depth=
```

---

## DESIGN RULES FOR THE SDK ENGINEER

1. **Level 0/1 methods must require zero protocol vocabulary.**
   No "envelope", "window", "CDR", "DPE" in any Level 0/1 signature,
   return field, or error message.
2. **Every return object degrades gracefully.** `r.crp.risk` always
   exists even in zero-CKF mode. `a.sources` is `[]`, never an error.
3. **Errors state what + why + the one fix.** Never surface a stack
   trace of protocol internals (see SPEC-032 §7).
4. **Defaults are the product.** A developer who configures nothing
   gets safe, grounded, well-positioned output. (SPEC-032 §6)
5. **Autocomplete is the documentation.** Level 2/3 capabilities are
   discoverable via IDE autocomplete on the client and result objects.
6. **The OpenAI-compatible path must be truly drop-in.** A developer
   swapping base_url changes nothing else and nothing breaks.
7. **Async mirrors sync.** Every method has an `await client.a*` form.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
