---
title: "CRP v6 — The Agent SDK & Launch-Ready Completion"
---

# CRP v6 — The Agent SDK & Launch-Ready Completion

### Making the Protocol Reusable: The Coverage Verdict, the Agent-Builder SDK (with Exact Code That Fills the Real Gap), the One-Month Launch Cut, and Product Positioning for Comply, Gateway, and Scan

**Prepared for Constantinos Vidiniotis, AutoCyber AI Pty Ltd**

**July 2026**

*This document does one job: turn CRP from "a protocol with fifty specs and a governance SDK" into "a protocol you build full agents on without re-innovating." It maps the four research reports against the shipped spec catalogue to find what is actually missing, specifies the missing reuse layer as an Agent SDK with runnable code, and separates what must ship for the one-month open-protocol launch from what is post-launch roadmap.*

---

# Part 1 — The Coverage Verdict: Do the Specs Cover the Research?

## 1.1 The honest answer, up front

Yes — with one real, specific gap. The v6 specification set (SPEC-049 through -057) *is* the research roadmaps rendered as documents; it was derived from them, so it covers them almost by construction. And a large fraction of the research is already marked `[SHIPPED]` in the existing catalogue (001–048). The single place where coverage is genuinely thin is the **Tool-Use roadmap's manifest / compiler / envelope layer (T1, T2, T4)** — and that is precisely the layer your stated goal depends on, because it is what lets you *declare* an agent's tools rather than *re-implement* them each time. Filling that is the substance of this document.

## 1.2 The three roadmaps, mapped to specs

The four reports produced three concrete roadmaps. Here is each item, where it lands, and an honest status.

**Understanding roadmap (R1–R5):**

| Item | Lands in | Status |
|---|---|---|
| R1 Verification Relay (PRM + symbolic + LLM-Modulo) | SPEC-049 | Specced; **build post-launch** (symbolic part cheap, PRM needs a trained judge) |
| R2 Quality-Tier-Supervised Routing | SPEC-050 | Specced; **needs data scale** — premature at 3 clients |
| R3 Predictive Positioning (world-model induction) | SPEC-051 | Specced; **research-tier, year-scale** |
| R4 Interpretation (intent/coref) + Clarification | SPEC-052 + SPEC-053; intent/coref already `[SHIPPED]` in extraction | Partly shipped; clarification is the novel add |
| R5 Epistemic Profiles + bi-temporal CKF | SPEC-055 + SPEC-057 | Specced; rides on R1 data |

**Tool-Use roadmap (T1–T6):**

| Item | Lands in | Status |
|---|---|---|
| **T1 Typed Tool Manifest** | *no v6 spec* | **REAL GAP → SPEC-059 (this doc)** |
| **T2 Intent-Compiler convention** | *no v6 spec* | **REAL GAP → SPEC-059 (this doc)** |
| T3 Constrained Dispatch at Gateway | SPEC-054 | Specced; **low-regret, ship now** |
| **T4 Tool-Result Envelope** | *no v6 spec* | **REAL GAP → SPEC-059 (this doc)** |
| T5 Selection-as-Retrieval over CKF | partial in SPEC-050 | Partial; the manifest (T1) unblocks it |
| T6 Narration Faithfulness | SPEC-049/056 | Specced; **low-regret, ship now** |

**Transparency roadmap (D1–D6):** all six land in SPEC-056 (AG-UI mapping, governance events, faithful narration, live provenance, quality streaming, resumable transparency). D1/D2/D3 are the low-regret, ship-now subset.

## 1.3 What this reveals

Three things fall out of the map, and they redirect the work:

First, **the Understanding and Transparency research is covered on paper; the Tool-Use *mechanics* are not.** T1/T2/T4 — manifest, compiler, envelope — were treated as "conventions" in the tool-use report and never specced. But they are not optional polish: they are the *interface through which a developer declares an agent's capabilities*. Without them, every new agent re-hand-codes tool wiring, which is exactly the re-innovation you want to eliminate. This is the gap that matters most for your goal, and it is small and concrete to close.

Second, **coverage is not the constraint; implementation and sequencing are.** Everything in R1–R5 is specced. The reason CRP is not yet "reusable for building agents" is not missing design — it is that the design is spread across fifty specs with no single *builder surface* that composes them. A developer today can make a governed `ask()` call in one line, but building a *full agent* (positioned loop + typed tools + memory + safety + streaming) means reading a dozen specs and wiring them by hand. The missing artifact is an **Agent SDK**, not another protocol layer.

Third, **the heavy specs are correctly roadmap, not launch.** R1's PRM judge, R2's learned router, R3's world model all need either a trained model or data volume you do not yet have. Publishing them as the open protocol's forward roadmap is right and even attractive to adopters; *implementing* them before launch would burn the month and delay Comply. The launch needs the reuse layer and the low-regret specs, nothing heavier.

So the completion of v6, correctly scoped, is: **(a) close the T1/T2/T4 gap as one new spec, SPEC-059; (b) expose the whole protocol through an Agent SDK that makes building an agent a declaration, not an implementation; (c) ship the low-regret specs (T3/SPEC-054, T6+D1–D3/SPEC-056 subset); (d) publish R1–R5 and R3's paper as roadmap.** Parts 2–4 do exactly this.

\newpage
# Part 2 — The Reuse Layer: SPEC-059 and the Agent SDK

This is the heart of the completion. It closes the one real gap (T1/T2/T4) and exposes the entire protocol through a builder so that **creating a new agent is declaring its tools and policy, not re-implementing the loop.** All code is runnable shape, built on the shipped SDK (`crp.SDKClient`, the Gateway, the CKF, the DPE) rather than replacing it.

## 2.1 CRP-SPEC-059 — Typed Tool Manifest, Intent-Compiler, and Result Envelope

```
Spec:     CRP-SPEC-059
Title:    The Agent Capability Layer — Typed Tool Manifest, Intent-Compiler,
          and Tool-Result Envelope
Status:   Proposed (Wave 1 — required for the Agent SDK)
Requires: CRP-SPEC-008 (Dispatch), 009 (CKF), 011 (Audit), 031 (STL),
          054 (Structured Decoding)
Closes:   Tool-Use roadmap T1, T2, T4
```

### 2.1.1 The typed tool manifest (T1)

A tool is declared once, as a governable artifact carrying everything selection, parameterisation, gating, and audit need. This is "disposable runtime knowledge" made into a first-class object — and it is the thing a developer writes to add a capability to an agent.

```python
# crp/agent/manifest.py — the typed tool manifest (T1) + intent-compiler base (T2)
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from typing import ClassVar

class Effect(str, Enum):
    READ_ONLY    = "read_only"      # no state change (a scan that only reads)
    IDEMPOTENT   = "idempotent"     # safe to repeat
    IRREVERSIBLE = "irreversible"   # a real, non-repeatable side effect

class SafetyClass(str, Enum):
    AUTO  = "auto"      # may run without approval
    GATED = "gated"     # must pass a policy check (SPDL, SPEC-006)
    HITL  = "hitl"      # requires human approval (SPEC-033)

class Intent(BaseModel):
    """T2: the model fills this SAFE typed intent; compile() emits the real invocation.
    The model never touches raw argv, so it cannot emit a dangerous/malformed call."""
    # --- manifest metadata (T1), declared per tool as class attributes ---
    name: ClassVar[str]
    description: ClassVar[str]
    when_to_use: ClassVar[str]
    when_not_to_use: ClassVar[str] = ""
    effect: ClassVar[Effect] = Effect.READ_ONLY
    safety_class: ClassVar[SafetyClass] = SafetyClass.AUTO
    requires_privilege: ClassVar[str | None] = None

    def compile(self) -> list[str] | dict:
        """Deterministic, versioned transform: safe intent -> real invocation + provenance.
        Override per tool. This is where dangerous binaries are wrapped PROVABLY safely."""
        raise NotImplementedError

    @classmethod
    def manifest(cls) -> dict:
        """The governable artifact: indexed in the CKF for selection-as-retrieval (T5)."""
        return {"name": cls.name, "description": cls.description,
                "when_to_use": cls.when_to_use, "when_not_to_use": cls.when_not_to_use,
                "effect": cls.effect.value, "safety_class": cls.safety_class.value,
                "requires_privilege": cls.requires_privilege,
                "arg_schema": cls.model_json_schema()}   # feeds structured decoding (SPEC-054)
```

A concrete tool — the pentest scanner — is now ~15 lines, and it is *complete*: selectable, parameterisable under grammar constraint, gated by safety class, and auditable.

```python
# tools/port_scan.py — a complete, governed tool in one declaration
from crp.agent.manifest import Intent, Effect, SafetyClass

class PortScan(Intent):
    name = "port_scan"
    description = "Fingerprint open services on a single host."
    when_to_use = "when a target host is in authorised scope and needs service discovery"
    when_not_to_use = "any host outside the authorised CIDR list"
    effect = Effect.READ_ONLY
    safety_class = SafetyClass.GATED          # must pass scope policy before running
    requires_privilege = "pentest"

    target: str                                # the model fills these (typed, validated)
    stealth: bool = True

    def compile(self) -> list[str]:            # deterministic: intent -> argv (+ provenance)
        flags = ["-sS"] if self.stealth else ["-sT"]
        return ["nmap", *flags, "-oX", "-", self.target]
```

### 2.1.2 The tool-result envelope (T4)

Every tool result is captured as a structured envelope: parsed structure stays in-window, raw output goes out-of-window by reference, confidence is attached, and everything is hashed into the audit chain. This solves context-bloat and makes results dedupable and governable.

```python
# crp/agent/envelope.py — the Tool-Result Envelope (T4)
from pydantic import BaseModel
from typing import Any
import hashlib, json

class ToolResult(BaseModel):
    invocation: dict            # what was called (compiled, with provenance)
    outcome: str                # "ok" | "error" | "timeout"
    parsed: dict                # structured result kept in-window
    parse_confidence: float
    raw_ref: str                # pointer to raw output in the store (out-of-window)
    provenance_hash: str        # links into the HMAC audit chain (SPEC-011)

def capture(invocation: dict, raw: str, parse_fn) -> ToolResult:
    parsed, conf = parse_fn(raw)                      # structured-first capture
    raw_ref = _store_raw(raw)                         # keep raw out of the context window
    h = hashlib.sha256((json.dumps(invocation) + raw_ref).encode()).hexdigest()
    return ToolResult(invocation=invocation, outcome="ok" if parsed else "error",
                      parsed=parsed, parse_confidence=conf, raw_ref=raw_ref,
                      provenance_hash=h)
```

## 2.2 The Agent SDK — building an agent is a declaration

Now the payoff. `crp.Agent` composes the positioned loop, typed tools, memory, safety, and streaming from the specs above and the shipped catalogue. Building an agent is declaring `tools + policy + model`; the loop is the protocol's, not yours.

```python
# crp/agent/agent.py — the Agent builder: compose the protocol, don't re-implement it
from crp import SDKClient                              # the shipped governance client
from crp.agent.manifest import Intent, SafetyClass
from crp.agent.envelope import capture
from crp.agent.gate import trusted_gate               # SPDL policy gate (SPEC-006)
from crp.sde import GrammarEnforcer, compile_tool_grammar   # SPEC-054
from crp.tel import CRPEmitter                         # SPEC-056 streaming (optional)

class Agent:
    def __init__(self, model: str, tools: list[type[Intent]], policy,
                 memory: str = "ckf", stream: bool = False, depth: str = "standard"):
        self.client = SDKClient(model=model, depth=depth)   # reuse shipped client
        self.tools = {t.name: t for t in tools}
        self.policy = policy
        self.stream = stream
        # index tool manifests in the CKF for selection-as-retrieval (T5)
        for t in tools:
            self.client.ckf.index_manifest(t.manifest())

    def run(self, goal: str, session=None) -> "AgentResult":
        emit = CRPEmitter(self.client.stream_sink) if self.stream else _noop
        session = session or self.client.new_session(goal)
        emit.run_started(goal)

        while not session.done:
            # 1) POSITION: pick the next operation + only the tools it needs (STL, SPEC-031)
            step = self.client.position(session)              # returns operation + 1-3 tools
            emit.reasoning(step.rationale)

            if step.tool:                                     # a tool step
                ToolCls = self.tools[step.tool]
                # 2) PARAMETERISE under grammar constraint — valid args guaranteed (SPEC-054)
                grammar = compile_tool_grammar(json.dumps(ToolCls.model_json_schema()),
                                               self.client.tokenizer_key)
                intent = self.client.fill_intent(ToolCls, step, GrammarEnforcer(grammar))
                emit.tool_start(ToolCls.name, intent.dict())

                # 3) GATE: safety class -> policy check / HITL before ANY side effect
                decision = trusted_gate(intent, ToolCls.safety_class, self.policy, session)
                if decision.blocked:
                    emit.blocked(decision.reason); session.record_block(decision); continue
                if decision.needs_human and not decision.approved:
                    emit.interrupt(decision.reason)            # SPEC-033 HITL, fail-closed
                    if not session.await_approval(decision):   # times out -> not approved
                        continue

                # 4) EXECUTE the compiled invocation + 5) CAPTURE the envelope (T4)
                argv = intent.compile()
                raw = self.client.execute(argv, sandbox=ToolCls.effect)   # sandboxed
                result = capture({"argv": argv}, raw, parse_fn=step.parser)
                emit.tool_result(ToolCls.name, result.parsed)
                session.add_result(result)                    # dedup via CDR; carry in CSO
            else:                                             # a reasoning/synthesis step
                out = self.client.complete(session)           # governed generation
                session.add_output(out)

            # 6) SAFETY + QUALITY on every step (DPE, SPEC-005) — already shipped
            scan = self.client.dpe(session.last)
            emit.safety(scan.stage, scan.risk, scan.ms); emit.quality(scan.tier, scan.confidence)
            session.advance(scan)

        # 7) FAITHFUL narration from the trace (T6/D3) + provenance close-out
        narrative = self.client.narrate_faithful(session)     # entailment-checked
        emit.narrative(narrative); emit.provenance(session.audit.head())
        emit.run_finished()
        return AgentResult(output=narrative, session=session,
                           quality=session.quality, audit=session.audit.head())

_noop = type("N", (), {m: staticmethod(lambda *a, **k: None)
                       for m in ("run_started","reasoning","tool_start","tool_result",
                                 "blocked","interrupt","safety","quality","narrative",
                                 "provenance","run_finished")})()
```

The wiring is the point. Every numbered step is an existing or Wave-1 spec, composed for you:

| Step | What happens | Spec |
|---|---|---|
| Position | pick operation + only needed tools | 031 (STL) |
| Parameterise | fill typed intent under grammar constraint | 059 (T2) + 054 |
| Gate | safety-class policy / HITL before side effects | 006 + 033 |
| Execute | run the compiled, sandboxed invocation | 059 (T2) |
| Capture | structured result envelope, raw by reference | 059 (T4) |
| Safety/Quality | DPE scan + tier on every step | 005 + 026 |
| Memory | dedup + carry state across windows | 009 (CKF) + 030 (CSO) |
| Narrate | entailment-checked faithful summary | 049/056 |
| Stream | AG-UI governance events (optional) | 056 |

## 2.3 The reuse proof: a second agent in fifteen lines

The test of the whole design is whether the *next* agent is cheap. It is — you declare tools and policy; you never touch the loop.

```python
# a completely different agent — a GDPR data-subject-request handler — built on the same protocol
from crp import Agent, Policy
from crp.agent.manifest import Intent, Effect, SafetyClass

class RedactPII(Intent):
    name = "redact_pii"; description = "Redact personal data from a document."
    when_to_use = "when a document must be shared outside its lawful basis"
    effect = Effect.IRREVERSIBLE; safety_class = SafetyClass.HITL     # irreversible -> human approves
    document_id: str; fields: list[str]
    def compile(self): return {"op": "redact", "doc": self.document_id, "fields": self.fields}

class LookupSubject(Intent):
    name = "lookup_subject"; description = "Find all records for a data subject."
    when_to_use = "to fulfil a GDPR Article 15 access request"
    effect = Effect.READ_ONLY; safety_class = SafetyClass.GATED
    subject_email: str
    def compile(self): return {"op": "lookup", "email": self.subject_email}

dsr_agent = Agent(model="phi4-4b", tools=[LookupSubject, RedactPII],
                  policy=Policy.from_file("gdpr-policy.yaml"), stream=True)
result = dsr_agent.run("Handle the access request from alice@example.com")
```

Same protocol, same loop, same guarantees (positioning, grammar-valid calls, HITL on the irreversible redaction, DPE on every step, faithful narration, signed audit) — a completely different agent, built by declaring two tools and a policy. **That is the reuse you asked for: update the protocol, and every agent inherits the improvement; add an agent, and you write only what is unique to it.** When you later ship SPEC-049 verification or SPEC-050 routing, *both* agents get them for free, because they run the same loop.

\newpage
# Part 3 — The One-Month Launch Cut

You launch the open protocol in a month and need to be ready for adoption *through Comply*. That constraint dictates the cut cleanly. The question is not "is the spec good?" — it is "does an adopter need it to succeed in month one, and can it ship without a trained model or data you don't have?"

## 3.1 Ship (in the month)

These are buildable now, from data and code you already have, and they are exactly what an adopter touches on day one:

- **SPEC-059 + the Agent SDK (Part 2).** This is the launch. It is what makes CRP *reusable* and what an adopter uses to build their first agent. Without it, "adopt CRP" means "read fifty specs"; with it, it means "declare your tools and policy." Highest priority, and it is composition of shipped pieces plus the small T1/T2/T4 layer — no new models, no data dependency.
- **SPEC-054 (structured decoding at the Gateway).** Wiring XGrammar into the Gateway generation path. Low-regret, low-risk, immediately makes local-SLM tool calls reliable — the difference between "the demo works" and "the demo hallucinates a tool call." Ship it.
- **SPEC-056, the D1–D3 subset only.** Emit AG-UI events (D1), the governance-event vocabulary (D2), and faithful narration (D3). This makes CRP's governance *legible* and gives you the demo that sells: an agent whose safety, quality, and provenance stream live. Skip D4–D6 (live client-side verification, quality-badge polish, resumable transparency) for month one — they are enhancements, not blockers.
- **Docs + one reference agent.** A quickstart that builds the pentest agent (or a compliance agent) end-to-end with the Agent SDK, plus the manifest/compiler pattern documented. Adoption dies without a copy-pasteable path from zero to a running governed agent.

That is a realistic month: a reuse layer, a reliability spec, a legibility subset, and the docs to adopt them.

## 3.2 Defer (publish as roadmap, do not build)

These are genuinely valuable and belong in the *published* v6 roadmap — an open protocol with a credible forward roadmap is *more* attractive to adopters, not less — but building them now would consume the month and delay Comply:

- **SPEC-049 PRM stage** (the symbolic verifiers are cheap and *can* sneak into the month; the trained PRM judge cannot). Ship symbolic-only if you have time; defer the judge.
- **SPEC-050 learned router** — needs data volume three clients won't produce. Ship the *capability-profile* fallback (static, useful) now; defer the learned model.
- **SPEC-051 predictive positioning** — year-scale research. Publish the roadmap entry and the paper abstract; build later.
- **SPEC-053 clarification, SPEC-055 calibration, SPEC-057 bi-temporal** — real, but not month-one adoption blockers. Roadmap.

The framing for the launch announcement writes itself: *"CRP v6 ships the Agent SDK — build governed SLM agents by declaring tools and policy — with a published roadmap to verified reasoning, learned routing, and predictive oversight."* You get to announce the vision and deliver the reusable core, which is exactly the right posture for an open-protocol launch.

## 3.3 The launch-readiness checklist (Comply-adoption-focused)

- [ ] Agent SDK (`crp.Agent`, manifest, compiler, envelope) shipped and documented — the reuse surface.
- [ ] Structured decoding live in the Gateway — reliable local-SLM tool calls.
- [ ] AG-UI + governance-event streaming (D1–D3) — the legibility demo.
- [ ] One reference agent, end-to-end, copy-pasteable.
- [ ] **The Scan → Gateway → Comply funnel wired and tested** (Part 4) — because "ready for adoption via Comply" means the *path into Comply* works, not just that Comply exists.
- [ ] Comply generates an evidence pack from a real Agent-SDK run — the proof that governed runtime → audit-ready deliverable actually closes.

\newpage

# Part 4 — Positioning: Comply, Gateway, Scan, and the Protocol

You asked whether Comply should be repositioned. My answer distinguishes the *protocol's* identity from the *products'* jobs, because they are not the same thing and conflating them is where positioning usually goes wrong.

## 4.1 The protocol keeps its identity — and it's already right

Your site already says it: *"the agentic positioning layer for SLM-first AI… positions every agent… and proves it with safety, grounding, and compliance evidence."* That is the correct protocol identity and you should not touch it. The Agent SDK (Part 2) *strengthens* it by making it concrete: positioning is no longer an abstract claim, it is `crp.Agent(...)`. The one addition I'd make to the protocol narrative is the reuse message — *"build governed agents by declaring tools and policy, not by re-implementing the loop"* — because that is your actual differentiator against "MCP + a framework + glue," and it is what your own stated goal is about.

Where does the agent-security angle from our earlier conversation live? **At the protocol and Gateway level, not Comply.** "The trusted gate, the tool-result envelope, structured decoding, scope enforcement, and provenance make each agent injection-resistant and its actions provable" is a *protocol/runtime* security story. It sharpens the protocol's identity and it is Gateway's differentiator. It is not Comply's job.

## 4.2 The three products have three different buyers — keep them distinct

The mistake to avoid is making all three products say the same thing. They sit at different points in the funnel and speak to different budgets:

- **CRP Scan — top of funnel, free, developer-triggered.** Job: *find the problem.* "You have ungoverned AI calls in your codebase; here they are; here's a PR." Its only job is to create awareness and pull developers in. Keep it free, keep it sharp, keep it a funnel. Do not monetise it; it is the hook.
- **CRP Gateway — the runtime, developer/platform buyer.** Job: *fix the problem at runtime.* This is where positioning, structured decoding, the trusted gate, and streaming governance live as a product. This is also where the *agent-security and agentic-positioning* identity surfaces commercially — "route every agent call through governed, injection-resistant positioning." Gateway is the technical adopter's product.
- **CRP Comply — the monetisation capstone, compliance/CISO buyer.** Job: *prove the problem is solved, to a regulator.* And here is the crucial positioning judgement: **keep Comply as the compliance and evidence product. Do not reposition it around agent security or agentic positioning.** The reason is budget. "Compliance" is a line item that CISOs and compliance officers already have money allocated against — EU AI Act, ISO 42001, NIST AI RMF are board-level obligations with budgets attached. "Agentic positioning" is a developer-interest story with no budget line. Comply is your main monetisation precisely *because* it sits on the compliance budget. Repositioning it toward the (cooler, but budget-less) agent-security/positioning story would move it *off* the money. Leave it where the money is.

## 4.3 The funnel is the product strategy

The three products are not three businesses; they are one funnel, and "ready for adoption via Comply" means the funnel flows:

```
CRP Scan (free)          CRP Gateway (runtime)         CRP Comply (evidence)
finds ungoverned    →    governs every agent call  →   turns runtime governance
AI calls, opens PR       (positioning + safety +       into audit-ready EU AI Act /
[awareness]              structured tool calls)        ISO 42001 / NIST evidence
                         [adoption]                    [monetisation]
```

Scan creates the *"oh, we have a problem"* moment for free. Gateway is the *"and here's the governed runtime that fixes it"* adoption. Comply is the *"and here's the regulator-ready proof, generated automatically"* monetisation — and it's the capstone because it converts a technical adoption into a compliance-budget purchase. The launch-readiness bar is therefore not "is Comply good" but "does a developer who runs Scan land in Gateway and convert to Comply." Wire and test that path; it is the actual product.

## 4.4 The one honest caution on Comply

Comply's value claim is "audit-ready evidence for EU AI Act, ISO 42001, GDPR, NIST AI RMF." That claim is strong *and* legally adjacent, so it carries a risk the others don't: an adopter may treat Comply's output as a *guarantee* of compliance rather than *evidence toward* it. Position it precisely — Comply generates the *evidence* frameworks require (that controls exist, operate, and are provable), which is exactly your site's excellent "controls are easy to claim; CRP proves they operate" framing. Keep that "evidence, not certification" line bright, because over-claiming compliance is the one positioning error in this space that has legal, not just marketing, downside — and for a governance brand, precision *is* the product.

## 4.5 The bottom line

Protocol: keep the positioning identity, add the reuse message, let security be the runtime story. Scan: free funnel, don't touch. Gateway: the runtime where positioning and agent-security become a product. Comply: **leave it on the compliance budget line — that's the money — and keep its claim to "evidence, not certification."** Build the Agent SDK so adoption is a declaration, wire the Scan→Gateway→Comply funnel so adoption converts, and launch the heavy specs as roadmap. That is a month you can actually ship, aimed exactly at adoption through Comply.

\newpage

# Appendix — Sources and Provenance

This document synthesises: the four research reports (*Understanding*, *Tool Use*, *Transparency*, and the *v6 Implementation Specification*); the live CRP catalogue and product pages at crprotocol.io (retrieved July 2026), including the shipped SDK surface (`crp.SDKClient`, progressive levels, `@client.tool`), the 001–048 spec list, and the Gateway/Comply/Scan product descriptions; and current library ground-truth for the code (XGrammar as the default structured-generation backend for vLLM/SGLang/TensorRT-LLM in 2026; Pydantic for typed intents; the AG-UI event model for streaming). The tool-manifest/compiler/envelope layer (SPEC-059) closes the Tool-Use roadmap's T1/T2/T4, which the prior v6 set left unspecced. Where a downstream spec (SPEC-049 PRM, 050, 051, 055, 057) depends on a trained model or on data volume not yet available, this document defers it to the published roadmap rather than the launch — consistent with the honesty rule carried through the series: ship what is real, name what is not yet.

*End of document.*
