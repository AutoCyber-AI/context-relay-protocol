# CRP-SPEC-032: Developer Experience & The Progressive Disclosure SDK

**Document:** CRP-SPEC-032  
**Title:** Context Relay Protocol (CRP) - Developer Experience: The Steering Wheel for the Engine  
**Version:** 1.0.0  
**Status:** Foundational - Adoption-Critical  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Governs:** the developer-facing surface of all prior specs  
**Prerequisites:** all, but hides all

---

## Abstract

CRP is specified across 31 documents defining ~58 headers, a 13-stage analysis pipeline, novelty-weighted graph retrieval, cognitive state objects, multi-horizon context tiers, and a semantic positioning layer. This is the **engine**. A developer needs a **steering wheel**. This document defines the developer experience: an SDK surface built on **progressive disclosure**, where the overwhelming majority of developers accomplish what they need with one or two concepts, and the full power is available but never required.

The governing principle: **every CRP capability is invisible by default.** The 58 headers, CDR, CDGR, the CSO, the STL, the DPE - none of these appear in the developer's code unless they deliberately reach for them. A developer gets governance with a one-line change and context quality with one more, never learning what CDR is. The engine's sophistication is the protocol's concern; the developer sees sane defaults and a five-line happy path. A protocol that requires understanding 31 specs to use will not be adopted. A protocol that requires understanding zero specs to start, and reveals depth only as needed, becomes infrastructure.

---

## 1. The Four Levels of Progressive Disclosure

Developers enter at the level matching their need and never descend further than necessary. Each level adds exactly one concept.

```
LEVEL 0 - GOVERNANCE       concepts: 0    "change one line"
LEVEL 1 - QUALITY          concepts: 1    "ingest, then ask"
LEVEL 2 - CONTROL          concepts: few  "positioning, tools, depth"
LEVEL 3 - INFRASTRUCTURE   concepts: all  "headers, policy, conformance"
```

**Distribution target:** 70% of developers never leave Level 0–1. 25% touch Level 2. 5% (infra/compliance teams) reach Level 3. If more than 30% of developers need Level 2+ to accomplish ordinary tasks, the defaults are wrong and MUST be fixed.

---

## 2. Level 0 - Governance (Zero New Concepts)

### 2.1 The One-Line Change

A developer with an existing OpenAI (or Anthropic, etc.) integration gets full CRP governance by changing the base URL and key. Nothing else.

```python
# Before
from openai import OpenAI
client = OpenAI(api_key="sk-...")

# After - full governance, zero new concepts
from openai import OpenAI
client = OpenAI(api_key="crp_gw_...", base_url="https://your-gateway.example/v1")
```

Everything continues to work exactly as before. The developer's code is unchanged beyond the constructor. But now: every call is risk-scored, attributed, audited (tamper-evident), and compliance-classified. If a response is CRITICAL-risk and policy says halt, the call returns a normal-looking error the developer's existing error handling catches.

### 2.2 What the Developer Does NOT Do at Level 0

- Does NOT learn what a header is
- Does NOT configure a Safety Policy (a sane default applies)
- Does NOT populate a CKF (zero-CKF mode, SPEC-017, governs safely)
- Does NOT read DPE reports
- Does NOT change their request or response handling

### 2.3 Reading Governance Results (Optional, Still Level 0)

If a developer wants to see the governance signals, they are on the response object under a single namespace - not 58 headers to parse:

```python
response = client.chat.completions.create(model="gpt-4o", messages=[...])

# Optional: the one governance object (not 58 headers)
print(response.crp.risk)         # "LOW"
print(response.crp.grounded)     # True
print(response.crp.compliant)    # True
print(response.crp.audit_url)    # "https://comply.crprotocol.io/t/..."
```

`response.crp` is a single, friendly summary object. The 58 headers exist on the wire for infrastructure (proxies, SIEMs) but the developer sees a five-field summary.

---

## 3. Level 1 - Quality (One New Concept: "knowledge")

### 3.1 The One Concept

The developer wants CRP's context-quality magic - grounding, unbounded coherent output, no repetition. They learn exactly one concept: **give CRP your knowledge, then ask.**

```python
import crp

client = crp.Client()                  # uses default model + sane everything

client.ingest("./docs/")               # a folder, files, URLs, or strings
                                       # ← the ONE new concept

answer = client.ask("Write a complete guide to our deployment process")
print(answer.text)                     # coherent, grounded, full-length
```

That is the entire Level 1 surface. `ingest` and `ask`. The developer never sees CDR, CDGR, the CSO, windows, envelopes, or depth. Behind `ask`, the full Tier 1 + STL machinery runs - retrieval, positioning, continuation, verification - invisibly.

### 3.2 ingest - Deliberately Forgiving

```python
client.ingest("./docs/")               # directory
client.ingest("manual.pdf")            # single file
client.ingest("https://...")           # URL
client.ingest("Some raw text")         # string
client.ingest(["a.md", "b.pdf", url])  # mixed list
```

One method, any input. Chunking, embedding, graph construction, community detection (SPEC-009) all happen automatically with defaults. The developer never configures HNSW parameters or Leiden resolution.

### 3.3 ask - The Happy Path

```python
answer = client.ask("your task in plain language")

answer.text          # the output
answer.quality       # "A" (quality tier - one letter, not a DPE report)
answer.grounded      # True
answer.sources       # [list of source docs used]
```

`ask` automatically: classifies the task (STL), proposes depth, retrieves with CDR/CDGR, positions the model, continues across windows if needed, verifies with DPE, and assembles the result. The developer wrote one line.

### 3.4 Conversation Is Just a Session

Multi-turn conversation (SPEC-028) requires no new concept - it is a session:

```python
chat = client.session()
chat.ask("How do I configure etcd?")
chat.ask("What about TLS for it?")     # "it" resolved automatically (SPEC-028)
chat.ask("Go back to the backup question")  # thread resumption, automatic
```

Reference resolution, intent classification, multi-horizon tiers - all invisible. The developer sees a chat object with an `ask` method.

---

## 4. Level 2 - Control (For Power Users)

Developers who need more reach for it explicitly. Each capability is one optional parameter or method - never required, always discoverable via autocomplete.

### 4.1 Depth Control

```python
answer = client.ask("...", depth="quick")     # D1–D2
answer = client.ask("...", depth="thorough")  # D4–D5
# default: depth="auto" (STL negotiates, SPEC-031)
```

### 4.2 Tool Registration (Agentic)

```python
@client.tool
def get_metrics(service: str) -> dict:
    return fetch_metrics(service)

answer = client.ask("Should we scale the payment service?")
# CRP calls get_metrics, grounds the decision in the result,
# records tool provenance (SPEC-029), links it to the decision (SPEC-030)
```

Tool output management, freshness gating, TOOL_GROUNDED attribution - all automatic once the tool is registered with a decorator. The developer writes a normal Python function.

### 4.3 Safety Policy (Plain Language)

```python
client = crp.Client(safety="medical")      # named profile (SPEC-006)
# or
client = crp.Client(safety="strict")       # halt on any HIGH+ risk
# or fine-grained, still readable:
client = crp.Client(safety={"halt_on": "CRITICAL", "require_grounding": 0.8})
```

The developer never writes the CSP-style directive string. They pick a profile or a small dict. The SDK compiles it to the wire policy.

### 4.4 Inspecting the Reasoning (CSO)

```python
answer = client.ask("...")
answer.decisions          # [{choice, rationale, sources}] - the CSO, friendly
answer.how_it_was_built   # the operation sequence (STL), human-readable
```

The Cognitive State Object (SPEC-030) is exposed as a readable decisions list, not a raw graph. A developer debugging *why* the model concluded something sees the rationale and sources.

---

## 5. Level 3 - Infrastructure (Compliance / Platform Teams)

The full surface, for the 5% who need it. This is where the 58 headers, raw DPE reports, conformance vectors, and audit exports live.

```python
# Raw header access (for proxy/WAF/SIEM integration)
response.crp.headers          # all 58, raw

# Full DPE report
response.crp.dpe              # complete 13-stage analysis

# Audit trail export
client.audit.export(format="ocsf")    # SPEC-011
client.audit.verify_chain()           # HMAC integrity check

# Conformance
crp.conformance.run(level="standard")  # SPEC-014 test vectors

# Compliance evidence
client.compliance.generate("eu-ai-act-art-11")   # SPEC-010
```

Level 3 is the only level where a developer confronts the protocol's full vocabulary - and only because compliance and infrastructure work genuinely requires it.

---

## 6. The Defaults That Make This Work

Progressive disclosure only works if the defaults are excellent. The SDK ships with:

| Setting | Default | Rationale |
|---------|---------|-----------|
| Safety profile | `balanced` (halt-on CRITICAL, warn-on HIGH) | Safe without being obstructive |
| Depth | `auto` (STL negotiates) | Right depth without the dev deciding |
| Model | first available provider, or local | Works out of the box |
| CKF | zero-CKF mode until ingest | Governance works before any setup |
| Amplification (Tier 4) | OFF | Never imposes latency (SPEC-023) |
| STL positioning | ON for `ask`, transparent | Quality without configuration |
| Headers | hidden behind `response.crp` summary | No header parsing required |

A developer who configures nothing gets: safe governance, automatic depth, automatic positioning, automatic continuation, and a friendly result object. The defaults ARE the product for most users.

---

## 7. Error Experience

Errors must be as well-designed as the happy path. CRP errors are actionable, never cryptic:

```python
# Halt due to safety policy
crp.SafetyHalt: Response halted - CRITICAL hallucination risk.
  The model produced unsupported claims about [topic].
  Audit: https://comply.crprotocol.io/t/abc123
  To allow with review: client.ask(..., on_risk="review")

# CKF exhausted (SPEC-024 exit)
crp.KnowledgeExhausted: Produced 2,400 words then stopped - the
  ingested knowledge was fully covered. Ingest more documents to
  continue, or the task is complete.

# Stale tool result (SPEC-029)
crp.StaleToolData: get_metrics result is 6 minutes old (limit: 30s).
  CRP re-called the tool automatically. [transparent - informational]
```

Each error states what happened, why, and the one thing to do about it. No stack traces of protocol internals.

---

## 8. The Documentation Ladder

Documentation mirrors the disclosure levels. A developer never reads more than their level requires:

| Doc | Audience | Length |
|-----|----------|--------|
| **Quickstart** | Level 0–1 | One page. base_url swap + ingest/ask. |
| **Guides** | Level 2 | Tools, depth, sessions, safety profiles. |
| **Protocol Reference** | Level 3 | The 31 specs, headers, conformance. |

The Quickstart MUST get a developer from zero to a working governed, grounded `ask` in under five minutes and under twenty lines of code. If it cannot, the SDK has failed its primary job.

---

## 9. Why This Determines Adoption

A protocol's headers are for infrastructure. A protocol's SDK is for humans. CRP's 31 specs make it powerful; this spec makes it adoptable. The history of developer tools is unambiguous: the winner is rarely the most capable - it is the most capable thing that is also the easiest to start. Stripe won payments not by having more features but by making the first integration five lines. CRP must do the same: the most governed, highest-quality context layer that is also the one a developer can start using in five minutes without reading a single other spec.

The 31 specs are the moat. This spec is the bridge across it. Without the bridge, the moat keeps developers out instead of keeping competitors out.

---

## 10. Honest Status

The Level 0 surface (gateway base_url swap) depends on the Gateway existing (SPEC-016) - currently the SDK exists but the hosted Gateway does not. The Level 1 surface (`ingest`/`ask`) maps to the verified v3 SDK capabilities plus the v4 CDR/STL additions - the SDK shape is specified here; the v4 internals are being built per the build prompt. Levels 2–3 expose machinery that largely exists in the specs but needs the friendly wrappers defined here.

The work this document defines is not protocol work - it is **interface design**: the wrappers, defaults, error messages, and documentation that turn 31 specs of engine into something a developer drives without thinking about the engine. It is the highest-leverage adoption work remaining, and it is mostly straightforward engineering once the Tier 1 core is built.

---

## 11. References

- SPEC-016 - Gateway Service (Level 0 endpoint)
- SPEC-017 - Zero-CKF Mode (Level 0 works before ingest)
- SPEC-024/025 - CDR/CDGR (hidden behind `ask`)
- SPEC-028/029 - Multi-horizon/Tools (hidden behind sessions/tool decorator)
- SPEC-030 - CSO (exposed as `answer.decisions`)
- SPEC-031 - STL (hidden behind `ask`, exposed as `answer.how_it_was_built`)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
