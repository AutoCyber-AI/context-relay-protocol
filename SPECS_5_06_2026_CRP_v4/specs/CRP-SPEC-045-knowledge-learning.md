# CRP-SPEC-045: Session & Persistent Knowledge Learning

**Document:** CRP-SPEC-045  
**Title:** Context Relay Protocol (CRP) — Knowledge Learning: Enabling an LLM to Acquire, Consolidate, and Innately Use New Knowledge Without Retraining  
**Version:** 1.0.0  
**Status:** Foundational — Frontier, With an Honest Boundary  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-009, 024, 030, 035, 038

---

## Abstract

LLMs do not learn. They are trained once, then frozen; everything after is context or tool output that vanishes when the window closes. There is no reinforcement, discovery, exploration, or iterative loop through which a model accumulates knowledge it can later use as if it knew it. This document specifies **Knowledge Learning** — a CRP capability that lets a model acquire new knowledge during operation (from a completed task, from research, from corrected mistakes), consolidate it into structured, retrievable form, and use it so seamlessly in subsequent work that it functions *as if internal* — for a session, or permanently. It must be read with one boundary stated up front and without softening: **CRP does not change model weights.** True internalisation — knowledge living in the parameters — is fine-tuning/training, which CRP does not do and does not claim to do. What CRP can do is make *externally-learned* knowledge so well-consolidated, so precisely retrieved, and so seamlessly positioned that it closes most of the practical gap with internal knowledge. This spec specifies that achievable system honestly, and names exactly where it stops.

---

## 1. The Problem: LLMs Don't Learn

### 1.1 What "Doesn't Learn" Means

A trained LLM is frozen. During use it receives context (which disappears after the call) and tool outputs (likewise). It cannot:
- Retain what it figured out solving a task, for the next task.
- Research a topic, understand it, and *keep* that understanding.
- Learn from a correction so it doesn't repeat the mistake.
- Build, over time, a growing body of knowledge it can draw on innately.

Every session starts from the same frozen baseline. This is the single biggest difference between an LLM and a learning agent — and it is a real, unsolved, commercially valuable gap.

### 1.2 Why "Skills" and Instruction Files Don't Solve It

Loading a `.md` skill file or a system-prompt instruction is not learning — it is re-injection. The model doesn't *know* the skill; it reads it each time, consuming context, with no consolidation, no growth, no integration with prior knowledge. The user's framing is exactly right: this is not real knowledge the model can implement; it is a note taped to the monitor. Real learning means the knowledge is acquired, understood, structured, and available without re-reading the note every time.

---

## 2. The Honest Boundary (read before anything else)

### 2.1 What CRP Cannot Do

**CRP cannot make a model innately know something in its weights.** Knowledge "in the parameters" comes from training/fine-tuning. CRP operates at inference time on the observable surface (its founding axiom). It does not and will not modify weights. Any claim that CRP makes a model "internally learn" in the neurological sense is false, and this spec does not make it.

### 2.2 What CRP Can Do

CRP can build an **external learned-knowledge system** so effective that, from the user's and the application's perspective, the model behaves as if it learned — because the right knowledge is always present, perfectly consolidated and retrieved, at the moment it's needed. The gap between "the model knows this in its weights" and "the protocol supplies this knowledge so seamlessly the model uses it as its own" is, for most practical purposes, narrow. CRP closes the practical gap, not the architectural one.

### 2.3 Why This Is Still Groundshaking

The honest version is still a major advance: most of the *value* of learning is having the right knowledge available and using it correctly — not the specific substrate it lives in. A system that genuinely acquires, consolidates, and seamlessly applies new knowledge across sessions delivers most of what "a learning LLM" promises, commercially and practically, even though the knowledge is external. Selling "teach your LLM to learn" is honest if it means "your LLM accumulates and innately-feeling-ly uses real knowledge it didn't have" — which this delivers — and dishonest only if it claims weight-level internalisation, which this spec explicitly disclaims.

---

## 3. The Learning Loop

CRP Knowledge Learning adds a loop the frozen model lacks: acquire → understand → consolidate → integrate → retrieve-as-known.

```
        ┌──────────────────────────────────────────────┐
        │  1. ACQUIRE                                   │
        │     New knowledge enters from:                │
        │     - a completed task (what was figured out) │
        │     - research (the model explored a topic)   │
        │     - a correction (a mistake, now fixed)     │
        │     - tool output worth keeping               │
        ├──────────────────────────────────────────────┤
        │  2. UNDERSTAND (consolidation)                │
        │     The raw acquisition is processed into     │
        │     structured knowledge: claims extracted,   │
        │     verified (DPE), linked to existing facts  │
        ├──────────────────────────────────────────────┤
        │  3. CONSOLIDATE (into the CKF)                │
        │     Structured knowledge written to the CKF   │
        │     (SPEC-009) with provenance, embeddings,   │
        │     graph edges to related knowledge          │
        ├──────────────────────────────────────────────┤
        │  4. INTEGRATE (reconcile)                     │
        │     New knowledge reconciled with existing:   │
        │     contradictions resolved (SPEC-027),       │
        │     duplicates merged, the graph re-linked    │
        ├──────────────────────────────────────────────┤
        │  5. RETRIEVE-AS-KNOWN                         │
        │     In future work, CDR/CDGR surface it       │
        │     seamlessly — the model uses it as if it   │
        │     always knew it. The note is gone; the     │
        │     knowledge is just there when needed.      │
        └──────────────────────────────────────────────┘
                  │                              ▲
                  └──────── loops each cycle ────┘
```

This is the reinforcement/discovery/iteration loop the model lacks — implemented externally, around the frozen model.

---

## 4. Two Scopes: Session Learning and Persistent Learning

### 4.1 Session Learning (the achievable, immediate version)

Within a session, knowledge acquired is consolidated into a session-scoped CKF and is available for the rest of that session as if internal. Example: the model researches a new API in turn 3, understands it; by turn 12 it uses that API knowledge fluently without re-reading — because it was consolidated into the session CKF and CDR retrieves it precisely when relevant. When the session ends, session-scoped knowledge is either discarded or promoted (§4.3).

This is fully achievable today with CRP's existing primitives (CKF + CDR + CSO) plus the consolidation step. It is the immediate product: *"your LLM learns within a session — what it figures out early, it knows for the rest of the work."*

### 4.2 Persistent Learning (the harder, still-external version)

Knowledge marked durable is consolidated into the *persistent* CKF and survives across sessions. The model, in a session next week, retrieves knowledge it "learned" last month. This is persistent learning — still external (CKF, not weights), but permanent from the user's perspective. Achievable, with care around the integration/reconciliation step (knowledge accumulated over time must stay consistent, SPEC-027) and storage (SPEC-038, the user owns where their learned knowledge lives).

### 4.3 Promotion: Session → Persistent

The bridge (consistent with SPEC-035 §4.2): session-learned knowledge that proves durable and valuable (used repeatedly, explicitly retained, verified correct) is promoted to the persistent CKF. Transient session knowledge evaporates. This mirrors human memory consolidation — most of what you process today you forget; what matters consolidates into long-term memory. CRP's promotion rule is the engineering analogue.

---

## 5. The Consolidation Engine (the new piece)

The genuinely new component beyond existing CRP. Acquiring knowledge is not just storing text — it is *understanding* it into usable form.

### 5.1 What Consolidation Does

```
Raw acquisition (e.g. "I researched OAuth2 PKCE flow and learned X, Y, Z")
   │
   ▼
CLAIM EXTRACTION — atomic, individual knowledge claims (DPE Stage 1)
   ▼
VERIFICATION — each claim checked: is it actually supported / correct?
   (DPE; discard or flag unverified claims — don't learn falsehoods)
   ▼
STRUCTURING — claims become CKF facts with type, entities, relations
   ▼
LINKING — graph edges to existing knowledge (this connects to what
   the model already knows — CDGR-style; new knowledge integrated,
   not isolated)
   ▼
RECONCILIATION — contradictions with existing knowledge resolved
   (SPEC-027 authority/recency); the model doesn't hold conflicting
   beliefs
   ▼
CONSOLIDATED KNOWLEDGE — written to CKF, now retrievable as known
```

### 5.2 Learning From Mistakes (the reinforcement piece)

A specific, valuable case: when a correction occurs (the model was wrong, a human or a tool corrected it), consolidation records *both* the correction *and* the error pattern. Future retrieval surfaces the corrected knowledge AND, via the AIR error-quarantine mechanism (SPEC-018), prevents the mistake from recurring. This is reinforcement-style learning at the knowledge level: the model "learns from its mistakes" — externally, but functionally.

### 5.3 Don't Learn Falsehoods

A critical guard: the verification step means CRP does not consolidate unverified or contradicted claims as knowledge. A model that "learns" wrong things is worse than one that doesn't learn. Consolidation is gated by DPE verification — only knowledge that survives verification enters the CKF. Unverified acquisitions are held as provisional (flagged) or discarded, never silently learned as fact.

---

## 6. How Learned Knowledge Feels Innate

The seamlessness that approaches internal knowledge comes from the existing CRP stack doing its job on consolidated knowledge:
- **CDR (SPEC-024)** retrieves learned knowledge exactly when relevant, without the user asking for it.
- **CDGR (SPEC-025)** connects learned knowledge to the current task multi-hop.
- **STL (SPEC-031)** positions it into the model's operation frame as part of the context the model treats as its own working knowledge.
- **The CSO (SPEC-030)** carries learned facts as established knowledge across the reasoning.

The model never "looks something up" in a way that feels external — the knowledge is simply present in its working context at the moment of need, indistinguishable in use from parametric knowledge. That seamlessness is the product. It is not weights; it is retrieval so good it feels like weights.

---

## 7. The Product

> "Teach your LLM to learn — so the knowledge it gains from tasks, research, and corrections becomes knowledge it can actually use."

Two tiers:
- **Session learning** — the model learns within a session; what it figures out, it knows for the rest of the work. (Immediate, fully achievable.)
- **Persistent learning** — the model accumulates knowledge across sessions; it knows next month what it learned today. (Achievable, external, user-owned storage.)

Honestly positioned: this is *real knowledge the model uses*, not skills files or prompt notes — acquired, verified, consolidated, and seamlessly applied. It is external to the weights, and the marketing must not claim otherwise; but functionally, it delivers most of what "a learning LLM" means, and that is genuinely new and valuable.

---

## 8. Headers

| Header | Meaning |
|--------|---------|
| `CRP-Learn-Acquired` | Count of knowledge claims acquired this cycle |
| `CRP-Learn-Consolidated` | Count consolidated into the CKF (passed verification) |
| `CRP-Learn-Rejected` | Count rejected (unverified/contradicted — not learned) |
| `CRP-Learn-Scope` | `session` or `persistent` |
| `CRP-Learn-Promoted` | Count promoted session → persistent |

`CRP-Learn-Rejected` is the honesty signal: it shows the system refused to learn things it couldn't verify.

---

## 9. Honest Status & Limits (the hard truths)

**The weight boundary is absolute.** CRP does not internalise knowledge into parameters. Period. This is external learned knowledge, seamlessly applied. Anyone who needs true weight-level internalisation needs fine-tuning, which is a different technology CRP does not provide. State this plainly to customers.

**Consolidation quality is the hard engineering.** Extracting correct, well-structured, properly-linked knowledge from raw acquisition is non-trivial — bad consolidation produces a polluted CKF that degrades rather than improves the model. The verification gate (§5.3) is essential and imperfect; consolidation will sometimes learn wrong things or miss connections. This needs the SQB (SPEC-026) extended to measure whether learned knowledge actually improves task performance over time, not just accumulates.

**Persistent learning risks knowledge drift.** A CKF that grows across months can accumulate contradictions, stale facts, and errors. The reconciliation step (SPEC-027) mitigates but does not eliminate this; persistent learning needs periodic consolidation review (a "knowledge GC") that is itself non-trivial.

**"Feels innate" is a UX claim, not an architectural one.** It feels innate because retrieval is excellent — but it remains retrieval, with retrieval's failure modes (a missed retrieval = the model "forgets" something it "learned"). Honest framing: very good externally-supported recall, not infallible internal memory.

---

## 10. References

- CRP-SPEC-009 — CKF (where learned knowledge lives)
- CRP-SPEC-018 — AIR (learning from mistakes / error quarantine)
- CRP-SPEC-024/025 — CDR/CDGR (retrieving learned knowledge seamlessly)
- CRP-SPEC-027 — Retrieval Integrity (reconciling accumulated knowledge)
- CRP-SPEC-030 — CSO (carrying learned knowledge as established)
- CRP-SPEC-035/038 — Storage lifecycle & backends (promotion, user-owned)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
