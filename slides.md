---
marp: true
theme: default
paginate: true
title: "Context Relay Protocol (CRP) — Dispatch/SecDispatch interim 2026"
---

<!--
Speaker deck for interim-2026-dispatch-02 (Joint Dispatch/SecDispatch).
Render with Marp:  marp slides.md -o slides.html   (or --pdf)
Last slot is 15 min; have the 3-slide compressed path ready (you are last).
-->

# Context Relay Protocol (CRP)

### A runtime governance, safety & provenance layer for AI **execution**

Constantinos Vidiniotis — AutoCyber AI Pty Ltd

`draft-vidiniotis-crp-core` · `-crp-headers` · `-crp-spec-006-safety-policy`

> Production-deployed. Seeking the right home to standardise it openly.

---

## The gap nobody fills

AI calls today have **no standard, interoperable way to express, enforce, or prove**
the safety/governance status of what an agent actually did — risk, grounding,
human-oversight, provenance, audit.

| Layer | Standardises |
|-------|--------------|
| **MCP / A2A** | AI *transport* — tool-calling, agent-to-agent |
| **AIPREF** | *training-time* preferences |
| **→ CRP ←** | **runtime governance + provenance of the execution itself** |

> Everyone is building agents. Nobody has standardised how to **govern and prove**
> what the agent's execution did.

---

## What CRP is

A **sidecar layer carried over existing HTTP** — a header vocabulary plus a
declarative, CSP-style policy language — **stripped before the provider**, so
existing proxies, gateways and SIEMs enforce it with no new plumbing.

- **Context Envelope** — structured state in/out
- **Decision Provenance Engine (DPE)** — risk / grounding / halt decision
- **Safety Policy** — declarative rules, **HTTP 451** halt
- **HMAC Audit Chain** — tamper-evident evidence

> The headers are the transport choice. The contribution is the **interoperable
> governance layer** they carry.

---

## Interoperability — and *why* it's the whole point

CRP is deliberately a **thin, neutral layer on plain HTTP**, not a runtime or a model:

- **Model-agnostic** — identical governance contract on GPT‑5, Claude, a 70 B, or a
  1 B model on a laptop. The model never sees a `CRP-*` header (**Axiom 4** — stripped
  before forwarding, enforced by a security test).
- **Provider- & transport-neutral** — rides the OpenAI-compatible call you already
  make; **composes with MCP / A2A** (they move the work, CRP governs and proves it).
- **Enforced by infrastructure you already run** — because it's HTTP headers + a
  CSP-style policy, existing **proxies, API gateways, and SIEMs** can read, enforce,
  and log it with **no new plumbing and no SDK lock-in**.
- **Evidence is portable** — HMAC-chained audit exports as **NDJSON / OCSF**, so the
  proof outlives any single vendor or tool.

> **Why it matters:** the AI stack is heterogeneous and changing weekly. Governance
> that is welded to one vendor's runtime isn't governance — it's lock-in. CRP makes
> the *contract* portable so risk, grounding, oversight and provenance mean the same
> thing across every model, agent and hop. **That portability is exactly why it
> belongs at the IETF, not in one company's product.**

---

## It's real — and it measures

<!-- Embed the recorded clips here (≈15–25s each, pre-recorded, no live risk).
     ALL clips come from the local demo at http://127.0.0.1:8774 (CRP v5 Protocol Demo).
     See the "Demo recording map" presenter notes at the end of this deck. -->

- **Clip A — the halt:** policy violation → **HTTP 451**, response stopped before the user.
  <br/>*Record: tab "1. Governed dispatch" → click "Halt trigger" → "Send with CRP" → the red `[HALTED — HTTP 451]` + Risk HIGH.*
- **Clip B — the governance panel:** risk / grounding / sources populate live.
  <br/>*Record: tab "1. Governed dispatch" → click "Introduce CRP" → "Send" → the Risk / Grounding / Quality-tier / Fabrications metrics filling in.*
- **Clip C — the audit entry:** the signed, tamper-evident event being written.
  <br/>*Record: tab "4. Audit chain" → "Verify chain" (green) → "Tamper with window #1" → chain breaks red.*
- **Clip D — v5 agentic loop:** the model positioned one operation at a time; the
  per-operation window stays **bounded** no matter how many tool calls run.
  <br/>*Record: tab "★ Positioned loop (v5)" → "Multi-step audit" template → "Run positioned loop" → the operation plan, event stream, tool catalogue, and 1–3 tool frame.*

**Verified, reproducible:**

- **11.8× more completed content at 6.1% protocol overhead** (continuation engine; `BENCHMARKS.md`).
- **< 50 ms** governance overhead per call (regression-gated invariant).
- **v5 positioned loop validated on a local 8B** (laptop-class): bounded **191-token**
  per-operation window even with the full catalogue available, typed state carried
  forward, full event-stream = audit.
- **Model-agnostic, measured today:** the *same* positioned agentic tasks run on a
  **local 8B** and on **Kimi (frontier)** — **3/3 correct on both**, with the working
  window held to a **≤ 206-token** per-operation frame on both. Positioning, not
  injection: identical governance + bounded-window contract from laptop to frontier.
- **SQB (continuation quality), local 8B:** cumulative **factual recall holds flat
  across windows** — technical **0.90 → 0.90**, regulatory **0.625 → 0.625**.

---

## In production today

- Shipped in **CRP Gateway** and **CRP Comply** managed cloud
  (`gateway.crprotocol.io`, `comply.crprotocol.io`).
- Reference implementation: `pip install crprotocol` — conformance suite included.
- **3 external clients in active adoption.**
- **v4 in production; v5 just completed** — extends the same governed, provable
  contract from a single inference call to an agent's full positioned tool-loop.

> Which is exactly why we want to standardise the **stable core** openly — not
> iterate it privately.

---

## The ask

We're seeking **guidance on the right home** to standardise this layer:

- a work item / profile in an existing WG, **or**
- a new WG via BoF, **or**
- Independent-stream RFC(s) as a stable reference while a community forms.

Why IETF: *a governance layer owned by one company isn't a standard — we're here
to make it neutral ground.*

Happy to post further I-Ds — threat model, agent-chain propagation, conformance —
if the group wants them.

---

## Backup — what the benchmark measures

- **SQB** runs a task that needs ~20k tokens but caps each call; it measures
  whether **factual recall / F1** holds as generation continues across windows,
  plus repetition and an LLM-as-judge usefulness score.
- **11.8×** is the unbounded-generation result: same per-window token budget, but
  CRP finishes the task (25 sections + conclusion) where a single call truncates
  at 8 sections. Effective throughput is identical (~4.9 words/s); CRP just finishes.
- **Axiom 4:** no `CRP-*` header ever reaches the provider — a dedicated security
  test enforces the allowlist strip.
