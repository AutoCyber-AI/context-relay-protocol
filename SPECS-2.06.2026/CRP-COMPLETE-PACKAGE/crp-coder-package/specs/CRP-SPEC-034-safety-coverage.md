# CRP-SPEC-034: AI Safety Coverage Map & Checkpoint Lifecycle

**Document:** CRP-SPEC-034  
**Title:** Context Relay Protocol (CRP) — Complete AI Safety Coverage Map, Gap Analysis, and the Checkpoint Resolution Lifecycle  
**Version:** 1.0.0  
**Status:** Foundational — Safety Completeness  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-033 (checkpoint lifecycle)  
**Prerequisites:** CRP-SPEC-005, CRP-SPEC-015, CRP-SPEC-033

---

## Abstract

This document does two things. First, it completes the Checkpoint primitive (SPEC-033) by specifying exactly what happens after a human decision — the full resolution lifecycle for approve, reject, edit, and timeout, including how execution progresses, what the end user sees, and how each path is recorded. Second, it provides an honest, complete map of the AI safety landscape: every safety concern that exists, which ones CRP addresses today, which ones CRP *can* address and should add, and which ones are genuinely outside CRP's reach because they are model-internal. The guiding distinction throughout: CRP governs the **observable surface** (inputs and outputs) and can address any safety concern detectable there; it cannot address concerns that live in the model's weights or training. For each gap, this document states plainly whether it is addable or out of scope, so expectations are accurate.

---

## PART A — THE CHECKPOINT RESOLUTION LIFECYCLE

### 1. The Problem SPEC-033 Left Open

SPEC-033 defined how a checkpoint *fires* and what the human *sees*, but not what happens *after* the human decides. A checkpoint that pauses execution must define, precisely, how execution resumes on each possible decision. This is that specification.

### 2. The Checkpoint State Machine

```
                    ┌──────────────┐
                    │   CREATED    │  checkpoint() called
                    └──────┬───────┘
                           │ package built (decision + reasoning + evidence + risk)
                           ▼
                    ┌──────────────┐
                    │   PENDING    │  routed to human; execution paused
                    └──────┬───────┘
                           │ human responds (or timeout)
          ┌────────────────┼────────────────┬─────────────────┐
          ▼                ▼                ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
   │ APPROVED  │    │ REJECTED  │    │  EDITED   │    │  TIMEOUT  │
   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
         │                │                │                │
         ▼                ▼                ▼                ▼
   resume with      run rejection     re-verify edited  apply timeout
   approved value   handler (§5)      value, then       policy (§7)
         │                │            resume            │
         ▼                ▼                │              ▼
   ┌─────────────────────────────────────────────────────────┐
   │  RESOLVED — recorded in audit chain (who/when/what/why)  │
   └─────────────────────────────────────────────────────────┘
```

### 3. APPROVE — Execution Resumes

On approval, the checkpointed value is released unchanged and execution continues from exactly where it paused:

```python
approved = crp.checkpoint(decision, reason="...", route_to="...")
# Human approves → `approved` resolves to the original `decision`
# Code continues normally with the approved value
process(approved)
```

- The return value of `crp.checkpoint()` resolves to the original value.
- Execution continues on the next line.
- A `CHECKPOINT_RESOLVED` audit event records: approver identity, timestamp, decision=APPROVED, the value hash, the reason.
- `CRP-Safety-Checkpoint-Status: approved` is emitted.

### 4. EDIT — Approve With Modification

A reviewer may approve a modified version (e.g., soften wording, correct a figure). The edited value is **re-verified by the DPE** before release — a human edit does not bypass safety, it is checked like any output:

```python
result = crp.checkpoint(draft_email, reason="External email", route_to="comms@co")
# Human edits the draft and approves the edit
# → CRP re-runs DPE on the EDITED value (catch new issues the edit introduced)
# → if the edit passes: `result` resolves to the edited value
# → if the edit fails DPE: reviewer is notified; checkpoint returns to PENDING
```

- The edited value replaces the original.
- DPE re-verification runs on the edit (an edit could introduce a new fabrication).
- Audit records: decision=EDITED, original hash, edited hash, approver, re-verification result.
- `CRP-Safety-Checkpoint-Status: edited`.

### 5. REJECT — The Rejection Handler (the critical, previously-undefined path)

Rejection is the path SPEC-033 left most underspecified. A rejection must not simply throw an unhandled error — the developer needs defined, graceful options for what happens when a human says no.

```python
result = crp.checkpoint(
    decision,
    reason="Loan approval",
    route_to="risk@co",
    on_reject="fallback",          # ← what to do on rejection
    fallback=lambda: "Application requires manual review by a loan officer.",
)
```

**Five rejection behaviours** (developer chooses per checkpoint):

| `on_reject` | Behaviour | Use case |
|-------------|-----------|----------|
| `"raise"` (default) | Raises `crp.CheckpointRejected` with the reviewer's reason; developer's try/except handles it | Explicit control flow |
| `"fallback"` | Returns the `fallback` value/callable instead of the rejected value | Graceful degradation — serve a safe alternative |
| `"retry"` | Re-runs the operation that produced the value (with the rejection reason fed back as guidance), then re-checkpoints | "Try again, better" — the AIR feedback loop (SPEC-018) applies the rejection as a constraint |
| `"abort"` | Cancels the whole operation cleanly; returns a defined `Aborted` result the caller can inspect | Stop the task entirely |
| `"escalate"` | Routes to a higher approver tier instead of failing | Hierarchical approval |

The reviewer's **rejection reason** is always captured and made available:

```python
try:
    result = crp.checkpoint(decision, ..., on_reject="raise")
except crp.CheckpointRejected as e:
    e.reason          # the human's stated reason for rejecting
    e.reviewer        # who rejected
    e.suggestion      # optional reviewer guidance for a retry
    # developer decides what the END USER sees
    return f"This request needs adjustment: {e.reason}"
```

**On `"retry"`, the rejection becomes a constraint.** The rejected value and the reviewer's reason are fed into the operation's next attempt via AIR (SPEC-018) — "the reviewer rejected this because X; produce a version that addresses X." This makes human rejection a *teaching signal*, not just a stop. This is a meaningful interaction: the human's judgment improves the next attempt automatically.

- Audit records: decision=REJECTED, reviewer, reason, the on_reject action taken.
- `CRP-Safety-Checkpoint-Status: rejected`.

### 6. What the END USER Sees (each path)

A critical UX point: the checkpoint is between the *system* and a *reviewer*, but there is also an *end user* waiting. The developer controls what the end user experiences:

```python
result = crp.checkpoint(
    decision,
    route_to="risk@co",
    user_message_pending="Your request is being reviewed (usually <2 min)...",
    on_reject="fallback",
    fallback="We couldn't auto-approve this; a specialist will follow up.",
)
```

- While PENDING: the end user can be shown `user_message_pending` (or the call blocks/streams a waiting state).
- On APPROVE: the end user gets the result seamlessly.
- On REJECT: the end user gets the fallback/handled message — never a raw error.
- On TIMEOUT: the end user gets the timeout-policy outcome.

### 7. TIMEOUT — Completed Specification

```python
crp.checkpoint(value, ..., timeout="2h", on_timeout="reject")
```

| `on_timeout` | Behaviour |
|--------------|-----------|
| `"reject"` (default, fail-safe) | Treated as a rejection; runs the `on_reject` path |
| `"approve"` (fail-open) | Treated as approval — **use only for low-stakes**; emits a warning and a distinct audit flag |
| `"escalate"` | Routes to a backup approver |
| `"extend"` | Extends the window once and re-notifies |

Timeout outcomes are audited distinctly (`decision=TIMEOUT_<action>`) so an auditor can see oversight that lapsed versus oversight that was actively given.

### 8. Async Checkpoints (non-blocking)

For systems that cannot block (web requests, queues), checkpoints resolve via callback:

```python
crp.checkpoint(
    decision, route_to="risk@co", async_=True,
    on_resolved=lambda outcome: handle(outcome),   # called when human decides
)
# execution continues immediately; the operation is parked server-side
# and resumed/finalised when the human responds
```

The parked operation's full state (CSO, session) is persisted (SPEC-030) so it can resume correctly even hours later, on a different server instance.

---

## PART B — THE COMPLETE AI SAFETY COVERAGE MAP

### 9. The Governing Distinction

CRP governs the **observable surface**: what goes into the model and what comes out. Any safety concern detectable in inputs or outputs, CRP can address. Any concern that requires inspecting the model's weights, training data, or internal activations, CRP cannot address — and claims to the contrary would be false. The map below classifies every concern on this basis.

### 10. What CRP Addresses Today (Covered)

| Concern | How | Spec | Adequate? |
|---------|-----|------|-----------|
| **Hallucination** | DPE risk scoring, 4 levels | 005 | Yes — core strength |
| **Fabrication** | Invented-entity detection | 005 §3a | Yes |
| **Distortion** | Source-fidelity checking | 005 §3b | Yes |
| **Ungrounded output** | Grounding ratio + threshold | 005, 006 | Yes |
| **Contradiction** | Intra/cross-window + envelope (027) | 005 §6, 027 | Yes |
| **Degeneration/repetition** | n-gram + semantic overlap | 005 §7, 024 | Yes |
| **PII exposure** | GDPR personal-data detection | 005 §11 | Adequate; extensible (§12) |
| **Prompt injection** | Input pattern shield | 015 | Adequate; see jailbreak (§11) |
| **Cumulative agent risk** | Safety budget + circuit breaker | 012 | Yes — novel |
| **Missing human oversight** | Checkpoints (inline HITL) | 033, this doc | Yes — novel |
| **Untraceable decisions** | HMAC audit chain | 011 | Yes |
| **Unsafe output reaching user** | HTTP 451 halt | 002 | Yes |
| **Regulatory non-compliance** | EU AI Act/GDPR/ISO/NIST classification | 010 | Yes |

### 11. What CRP Can Address and SHOULD Add (Addable Gaps)

These are detectable on the observable surface — CRP can and should cover them. They become **custom rules** (SPEC-033 §4) shipped as built-in DPE checks:

| Gap | Why it's addable | How CRP adds it |
|-----|-----------------|-----------------|
| **Jailbreak detection** (distinct from injection — adversarial *intent* to bypass safety, e.g. "ignore your rules," role-play exploits) | Visible in input patterns + output divergence | New DPE input-analysis stage; pattern + semantic classifier. **Add to SPEC-015.** |
| **Toxicity / harmful content** (output contains hate, violence, self-harm facilitation) | Visible in output text | DPE output-classification stage using a safety classifier; severity feeds risk scoring. **Add as built-in rule.** |
| **Secret / credential leakage** (output contains API keys, passwords, tokens) | Visible in output via pattern detection (high-entropy strings, key formats) | Output scanner, like PII but for secrets; `block` by default. **Add to SPEC-005 §11 family.** |
| **Copyright / verbatim reproduction** (output reproduces large verbatim copyrighted text) | Visible as long verbatim matches against known sources or training-data signatures | Verbatim-overlap detector; flag long exact reproductions. **Addable as a rule.** |
| **Excessive agency / tool misuse** (agent invokes dangerous tools beyond intent) | Visible in tool-call stream | Tool-call gating via checkpoints + tool rules (SPEC-033 §4.2). **Already expressible; make built-in profiles.** |
| **Goal drift** (agent's actions diverge from the original objective) | Visible by comparing actions to goal_state (CSO, SPEC-030) | Drift detector comparing operations to the stated goal; flag divergence. **Add as STL/CSO check.** |
| **Output non-determinism** (same input → wildly different safety outcomes) | Visible across repeated runs | Reproducibility seed + variance check (ROS, SPEC-021, when enabled). **Partially covered; expose as a setting.** |

All seven are within CRP's observable-surface reach. The recommendation: ship them as built-in safety rules in the Control Plane (SPEC-033), each toggleable and tunable like existing checks. This meaningfully expands coverage without changing the architecture — they are new detectors feeding the same risk/halt/checkpoint/audit machinery.

### 12. What CRP CANNOT Fully Address (Honest Out-of-Scope)

These require model-internal access and are genuinely beyond a surface-governance protocol. CRP can *partially* mitigate some via output observation, but cannot *solve* them:

| Concern | Why out of scope | What CRP can still do |
|---------|-----------------|----------------------|
| **Model alignment** (does the model have good values) | Lives in weights/training | Nothing internal; checkpoints insert human judgment where it matters |
| **Training-data bias** (systematic skew from training corpus) | Lives in training data | Can detect *some* biased *outputs* via a fairness rule, but cannot fix the underlying bias |
| **Output bias/fairness** (discriminatory outputs) | Partially observable | Can flag detectable discriminatory patterns as a custom rule; cannot guarantee fairness (this is an active research problem, not a detection problem) |
| **Sycophancy** (model tells users what they want to hear) | Subtle, semantic, context-dependent | Hard to detect reliably on the surface; checkpoints for high-stakes agreement |
| **Emergent capability** (novel abilities at scale) | Latent in the model | Cannot predict; governs only what manifests as output |
| **Deceptive alignment** (model strategically hides misbehaviour) | Model-internal, adversarial | Beyond surface governance; an alignment-research problem |

**The honest framing for users:** CRP comprehensively governs the observable surface and, with the additions in §11, covers essentially every *detectable* safety concern. The concerns in §12 are model-internal — they are the domain of alignment research (Anthropic, DeepMind, safety institutes), and CRP's checkpoints are precisely the mechanism for inserting human judgment where automated surface-governance is insufficient. CRP does not claim to solve them; it claims to govern everything observable and to route the rest to humans.

### 13. Are the Ones We Have Adequate?

Yes, for the observable surface. The core detection (hallucination, fabrication, distortion, grounding, contradiction) is CRP's proven strength. The §11 additions close the remaining *detectable* gaps (jailbreak, toxicity, secrets, copyright, agency, drift). After §11, CRP's observable-surface coverage is comprehensive. The §12 concerns are not inadequacies in CRP — they are categorically outside what any surface-governance protocol can do, and CRP is honest about that boundary rather than pretending to cover it.

---

## PART C — RELATIONSHIP TO CRP COMPLY

### 14. Safety Control Plane: Feature, Not Separate Product

The Safety Control Plane (SPEC-033) and these safety capabilities are **a feature surface of CRP, exposed through CRP Comply** — not a separate product. The reasoning:

- The *detection* lives in the protocol core (the DPE) — it runs on every call regardless of product.
- The *control/visibility/checkpoint-resolution* needs a UI and a human-routing backend — that is exactly what CRP Comply is. Comply is the management and evidence surface for CRP's governance.
- Splitting safety into a separate product would fragment the value: customers want one place. CRP Comply *is* that place.

**Decision:** The Safety Control Plane is the safety-management surface of **CRP Comply**. Comply gains: the safety registry UI, checkpoint routing/resolution (the human-in-the-loop inbox), custom-rule management, and the coverage/regulation view. This makes Comply not just a compliance-evidence tool but the **AI safety control centre** — a stronger product position. The checkpoint "human inbox" (where reviewers see and resolve checkpoints) is a natural, high-value Comply feature.

---

## 15. Headers (additions)

| Header | Meaning |
|--------|---------|
| `CRP-Safety-Checkpoint-Resolution` | `approved` / `rejected` / `edited` / `timeout-reject` / `timeout-approve` |
| `CRP-Safety-Checkpoint-Reviewer` | Identity hash of the resolving reviewer |
| `CRP-Safety-Reject-Action` | The on_reject action taken: `raise`/`fallback`/`retry`/`abort`/`escalate` |
| `CRP-Safety-Coverage-Level` | Which safety rules are active, e.g. `core+jailbreak+toxicity+secrets` |

---

## 16. References

- CRP-SPEC-005 — DPE (detection home for added rules)
- CRP-SPEC-015 — Security (jailbreak/injection additions)
- CRP-SPEC-018 — AIR (rejection-as-constraint on retry)
- CRP-SPEC-030 — CSO (parked async checkpoint state; goal-drift detection)
- CRP-SPEC-033 — Safety Control Plane (the surface this completes)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
