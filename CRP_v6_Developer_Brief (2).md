# CRP v6 — Engineering Brief & Developer Prompt

**From:** Constantinos Vidiniotis, Founder, AutoCyber AI Pty Ltd
**To:** Lead Engineer (human) — or paste into an agentic coding tool (e.g. Claude Code) run against the CRP monorepo
**Re:** Audit, correct, and complete CRP v6 for the one-month open-protocol launch
**Prime directive:** Make CRP a protocol that *any* developer — and I — can reuse to build full agentic/AI products by **declaring tools and policy, not re-implementing the loop.** Everything below serves that.

---

## 0. How to use this brief

You are being handed the complete research and specification corpus for the Context Relay Protocol (CRP). Your job is **not** to trust it — it was written partly from the live site and partly from inference, and it explicitly flags where it guessed. Your job is to **verify it against the real codebase, correct it to the real names and conventions, close the genuine gaps, and implement the launch cut.**

Work in the phases in §4. Produce the deliverables in §5. Hold the constraints in §3 as non-negotiable — especially the marketing position (§3.1) and the reusability north star (§3.2). When you find the corpus is wrong about the code, **the code wins and you correct the document** — and log it (§5.1).

This brief can be executed by a senior engineer directly, or given to an agentic coding assistant with repo access; in the latter case, treat §4 as an ordered task list and open a PR per phase.

---

## 1. Context: what CRP is (the agreed position — do not drift from this)

CRP is **the agentic positioning layer for SLM-first AI.** MCP exposes tools; A2A connects agents; **CRP positions every agent on the right task, with the right context and tools — so small local models can complete agentic tasks reliably, without context overload — and proves it operated safely.** Safety, grounding, and provenance are enforced *in the same loop*, not bolted on. This is already the live positioning at crprotocol.io and it is correct; your work must reinforce it, never quietly reframe the product away from it.

Products (one funnel, three buyers — keep them distinct):
- **CRP Scan** (free, VS Code extension): finds ungoverned AI calls, opens remediation PRs. Top of funnel — awareness. Do not monetise.
- **CRP Gateway** (runtime): routes every AI/agent call through governed positioning + context management + structured tool-calling + streaming governance. This is where the *positioning and agent-security* story is a product. Adoption.
- **CRP Comply** (monetisation capstone): turns Gateway's runtime evidence into audit-ready deliverables for EU AI Act / ISO 42001 / NIST AI RMF / GDPR. **Keep Comply on the compliance budget line** — that is where the money is. Claim "evidence, not certification" precisely; over-claiming compliance has legal downside.

The funnel that must work for launch: **Scan → Gateway → Comply.**

---

## 2. The deliverables to ingest (read all of these first)

Five documents were produced (each has a `.docx` and a `_source.md`; read the `.md`). Ingest in this order:

1. **`Architecture_of_Understanding_in_Agentic_AI` (source.md).** The eight/ten-component model of machine cognition; reasoning ladder; memory; world models; meta-cognition. **Part IV is the R1–R5 roadmap** and the honest open-problems list. This is the "what the protocol must eventually do for reasoning/understanding" reference.

2. **`Architecture_of_Tool_Use_in_Agentic_AI` (source.md).** The nine-stage tool loop; intent-compiler DSL; constrained decoding; the trusted policy gate; grounding/faithfulness. **Chapter 29 is the T1–T6 roadmap.** T1/T2/T4 (typed tool manifest, intent-compiler, tool-result envelope) are the gap you will close as SPEC-059.

3. **`Architecture_of_Transparency_in_Agentic_AI` (source.md).** What to display; SSE/WebSockets; the AG-UI event standard; faithful narration; engagement. **Chapter 26 is the D1–D6 roadmap.** D1–D3 are in the launch cut. Templates 1–12 are real streaming code to adapt.

4. **`CRP_v6_Implementation_Specification` (source.md).** The nine specs SPEC-049…057 (Verification Relay, Learned Router, Predictive Positioning, Intent/Speech-Act, Clarification, Structured Decoding, Epistemic Profiles, Transparency Emission, Bi-Temporal CKF), each with code, integration points, conformance, and security. **Appendix A traces one request through all nine; Appendix B is the wave-by-wave build checklist.** This is the forward roadmap; most of it is post-launch (see §3.3).

5. **`CRP_v6_Agent_SDK_and_Launch_Completion` (source.md).** The coverage verdict (research → spec map), **SPEC-059** (tool manifest + intent-compiler + result envelope — the real gap), the **`crp.Agent` SDK** with runnable code, the one-month launch cut, and product positioning. **This document is your primary work order; the other four are its evidence base.**

Also ingest the live protocol reality:
- **crprotocol.io** — the spec catalogue (SPEC-001…048), the shipped SDK surface (`crp.SDKClient`, progressive disclosure levels, `@client.tool`, `ask/complete/ingest`), and product pages.
- **comply.crprotocol.io** — Comply's current messaging (verify positioning against §1).
- **CRP Scan** on the VS Code Marketplace — the funnel entry.
- The **actual monorepo** — the source of truth that overrides every document.

### 2.1 The complete new-spec inventory — WRITE a document for EVERY one of these

There are **eleven** new specifications across the corpus (SPEC-049…059). **Write and publish a formal spec document for all eleven, in the real CRP house style, into the catalogue** — the open protocol must be *documentation-complete* at launch. Nothing here is omitted. What differs per spec is only whether it is **implemented in the launch month** or **published as documented roadmap** (see §3.3 and Phase 3): a roadmap spec still ships as a complete, numbered document, just not as running code yet.

| Spec | Name | Closes research | Write doc? | Implement in month? |
|---|---|---|---|---|
| **SPEC-049** | Verification Relay (PRM + symbolic + LLM-Modulo) | R1 | **Yes** | Symbolic only; PRM judge → roadmap |
| **SPEC-050** | Quality-Tier-Supervised Router | R2, T5 | **Yes** | Capability-profile fallback only; learned model → roadmap |
| **SPEC-051** | Predictive Positioning & World-Model Induction | R3 | **Yes** | Roadmap (year-scale) |
| **SPEC-052** | Intent & Speech-Act Positioning | R4 | **Yes** | Yes if intent/coref already shipped in extraction; else roadmap |
| **SPEC-053** | Clarification Protocol (`CRP-Clarification-Required`) | R4 | **Yes** | Roadmap (novel; low effort — pull forward if time allows) |
| **SPEC-054** | Structured Decoding Enforcement (XGrammar) | T3 | **Yes** | **Yes — launch** |
| **SPEC-055** | Epistemic Profiles & Calibration | R5 | **Yes** | Semantic-entropy only; calibration curves → roadmap |
| **SPEC-056** | Transparency Emission Layer (AG-UI + governance events) | D1–D6 | **Yes** | **D1–D3 launch; D4–D6 roadmap** |
| **SPEC-057** | Bi-Temporal CKF | R5 | **Yes** | Roadmap |
| **SPEC-058** | Governed Delegation (multi-agent) | Multi-agent frontier | **Yes (as Draft/preview)** | Roadmap (Wave 4) |
| **SPEC-059** | Agent Capability Layer (manifest + compiler + envelope) | T1, T2, T4 | **Yes** | **Yes — launch (the reuse gap)** |

Rule: **every row gets a written spec document; only the "Yes — launch" rows get built now.** A published open protocol with eleven coherent specs and a clearly-labelled implemented-vs-roadmap split is exactly the right launch posture — complete on paper, honest about code. Also update the master index/roadmap doc so the catalogue reads 001…059 cleanly.

---

## 3. Hard constraints (non-negotiable)

### 3.1 Preserve the marketing position
Every design decision must keep CRP framed as **agentic positioning for SLM-first AI, proven safe.** Do not let an engineering convenience reframe the product as "another agent framework" or "MCP-plus-headers." Keep Comply on the **compliance budget line**; keep security/positioning as the **Gateway/protocol** story. If a technical choice would force a positioning drift, flag it (§5.1) rather than silently taking it.

### 3.2 Reusability is the north star
The definition of success: **building a new agent = declaring its tools (typed manifest) + policy + model. The loop is the protocol's.** When SPEC-049/050/051 later ship, every existing agent must inherit them for free, with no per-agent rewrite. If any design forces per-agent re-implementation of positioning, tool-calling, safety, or narration, it is wrong — fix it.

### 3.3 Honesty rule (ship what's real, name what's not)
The corpus deliberately marks things `[OPEN]` and defers data-dependent specs. Preserve this. **Do not implement, and do not let marketing claim,** capabilities that need a trained model or data volume we do not have at ~3 clients (learned router SPEC-050, PRM judge in SPEC-049, world-model induction SPEC-051, calibration SPEC-055). These are *published roadmap*, not launch. Over-claiming in a governance product is a legal and reputational risk, not just a marketing one.

---

## 4. Your tasks, in order

### Phase 0 — Ingest & build the traceability matrix
Read all five documents and the live catalogue. Produce a **traceability matrix**: every research roadmap item (R1–R5, T1–T6, D1–D6) → the spec that covers it (existing SPEC-00x or v6 SPEC-04x/05x/059) → the actual code module in the repo that implements it (or "MISSING") → status (`shipped` / `partial` / `specced-only` / `gap`). This matrix is the map for everything after.

### Phase 1 — Proof-check & correct against the real code
The Agent SDK code in deliverable #5 uses **inferred** method names (`SDKClient.position`, `fill_intent`, `narrate_faithful`, `dpe`, `ckf.index_manifest`, `stream_sink`, `tokenizer_key`, `new_session`, `execute`). These are shape-real, not name-real. Your job:
- Map each inferred call to the **actual** `crp.SDKClient` / Gateway / CKF / DPE method and signature in the repo. Rewrite SPEC-059 and the `crp.Agent` class to bind to the **real API and naming conventions**.
- For every spec claim (SPEC-049…059) that asserts the protocol "does X," verify the repo actually does X. Where it doesn't, mark the spec `specced-only` and note the delta.
- Confirm integration-point spec numbers are right (e.g. the corpus assumes DPE=005, SPDL=006, dispatch=008, CKF=009, audit=011, Gateway=016, ROS=021, SQB=026, Tier-E=029, CSO=030, STL=031, Safety Control Plane=033, Multi-Agent Safety=012). Correct any that are wrong against the live catalogue.

### Phase 2 — Close the real gap: SPEC-059 (tool manifest + compiler + envelope)
Implement the T1/T2/T4 layer against the real substrate:
- **Typed Tool Manifest (T1):** the `Intent` base + per-tool metadata (`effect`, `safety_class`, `requires_privilege`, `when_to_use`), indexed in the **real** CKF for selection-as-retrieval (T5).
- **Intent-Compiler (T2):** the `compile()` convention — model fills a safe typed intent; a deterministic, versioned compiler emits the real invocation + provenance. Wire dangerous-binary tools (e.g. the pentest scanner) through it.
- **Tool-Result Envelope (T4):** structured capture, raw-by-reference, confidence, hashed into the **real** HMAC audit chain (SPEC-011).
Bind all three to the actual dispatch/CKF/audit APIs from Phase 1.

### Phase 3 — Validate & finalise the launch cut
Confirm the §3.3 launch cut is buildable in the month **against the real code**. Re-sequence if reality disagrees. The launch build is:
- **SPEC-059 + `crp.Agent` SDK** (the reuse surface) — bound to real API.
- **SPEC-054 Structured Decoding** — XGrammar in the Gateway generation path (verify XGrammar is compatible with the runtime we use — vLLM/SGLang/Ollama; if Ollama-only, identify the grammar path or a fallback).
- **SPEC-056 D1–D3 only** — AG-UI event emission, the `crp.*` governance-event vocabulary, and faithful (entailment-checked) narration. Defer D4–D6.
- **One reference agent** end-to-end via the SDK + **quickstart docs**.
- **Scan → Gateway → Comply funnel** wired and tested; Comply generates an evidence pack from a real Agent-SDK run.
- **All eleven new spec documents (049–059) written and published** (§2.1) — the *documents* ship even where the *code* is roadmap.

Implemented-in-code is only the "Yes — launch" rows. The remainder — **SPEC-049 PRM judge, SPEC-050 learned model, SPEC-051, SPEC-052 (if not already shipped), SPEC-053, SPEC-055 calibration curves, SPEC-057, SPEC-058** — are **published as documented roadmap**, not built. (SPEC-053 clarification is low-effort and novel; pull it into the launch if the reference-agent work finishes early.)

### Phase 4 — Implement
Build Phase 3's list. One PR per component. Each PR must show the reusability invariant (§3.2) holds: the reference agent, and a *second* trivially-different agent, both run on the unmodified loop.

### Phase 5 — Further-investigate the research (feasibility pass)
For each deferred/roadmap spec, do a short feasibility spike and write a one-paragraph verdict: is the approach in the research still current (check the cited libraries — XGrammar, Z3, semantic entropy, WALL-E-style induction, RouteLLM, Graphiti — are current as of mid-2026), is it feasible on our stack, and what is the real trigger to build it (usually data volume). Flag anything the research over-optimistically assumed. This protects us from building on a stale or infeasible premise later.

---

## 5. What to deliver back

### 5.1 A correction log
Every place the corpus was wrong about the code, the real name/convention, or an infeasible assumption — with the correction. This is how the specs become trustworthy.

### 5.2 The traceability matrix (Phase 0), completed.

### 5.3 Corrected, real-API-bound SPEC-059 and `crp.Agent` SDK
Copy-paste-real, not shape-real. Plus the reference agent and the second-agent reuse proof.

### 5.4 A gap list with severity × effort
Every `specced-only` or `gap` item, sized, with a recommendation: launch / roadmap / drop.

### 5.5 The launch PR plan
The ordered PRs for Phase 4, with the acceptance criteria (§6) per PR.

### 5.6 The feasibility verdicts (Phase 5).

### 5.7 All eleven new spec documents (049–059), published
Written in house style into the catalogue, each labelled `implemented` or `roadmap`, with the master index updated to 001…059. **Nothing from §2.1 is omitted from the documentation**, regardless of what is coded this month.

---

## 6. Definition of done (launch acceptance criteria)

- [ ] A developer can build a new governed agent by declaring tools + policy + model — **no loop code** — and it runs positioning, grammar-valid tool calls, safety-class gating/HITL, DPE on every step, faithful narration, and a signed audit. *(Reusability proven.)*
- [ ] A second, unrelated agent is built the same way in ~15 lines on the **unmodified** loop. *(Reuse invariant.)*
- [ ] Local-SLM tool calls are structurally valid by construction (structured decoding live). *(Reliability.)*
- [ ] A run streams AG-UI + `crp.*` governance events; narration is entailment-checked against the trace. *(Legibility + faithfulness.)*
- [ ] Comply produces an audit-ready evidence pack from an Agent-SDK run; the Scan → Gateway → Comply path converts end-to-end. *(Monetisation path.)*
- [ ] The SPEC docs match the code (correction log applied); roadmap specs are clearly labelled roadmap. *(Honesty rule.)*
- [ ] **All eleven new spec documents (049–059) are written and published** (§2.1), catalogue index reads 001…059, each marked `implemented` or `roadmap`. *(Documentation-complete — nothing omitted.)*
- [ ] The marketing position (§1, §3.1) is intact across protocol, Gateway, and Comply. *(No drift.)*

---

## 7. One-line summary for the developer

**Verify the corpus against the repo; bind SPEC-059 and the `crp.Agent` SDK to the real API; write all eleven new spec documents (049–059) so the protocol is documentation-complete; implement the launch subset (059 + Agent SDK + 054 + 056 D1–D3 + one reference agent) so anyone can build governed SLM agents by declaring tools and policy; publish the heavy specs as clearly-labelled roadmap; keep Comply on the compliance budget line and the position exactly as agreed. Reusability is the whole point.**

---

*Attachments: the five `_source.md` deliverables above. Source of truth: the CRP monorepo and crprotocol.io. When they conflict, the repo wins and the docs get corrected.*
