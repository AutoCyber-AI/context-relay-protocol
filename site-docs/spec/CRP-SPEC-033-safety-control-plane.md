# CRP-SPEC-033: The Safety Control Plane & Inline Human-in-the-Loop

**Document:** CRP-SPEC-033  
**Title:** Context Relay Protocol (CRP) - The Safety Control Plane: Centralised, Visible, Tunable, Extensible AI Safety with Inline Human-in-the-Loop Checkpoints  
**Version:** 1.0.0  
**Status:** Foundational - Experience-Defining  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Unifies:** CRP-SPEC-005, 006, 011, 012 (all safety mechanisms) under one control surface  
**Prerequisites:** CRP-SPEC-005, CRP-SPEC-006, CRP-SPEC-032

---

## Abstract

CRP's safety mechanisms are powerful but scattered: the DPE risk pipeline (SPEC-005), the Safety Policy language (SPEC-006), the HTTP 451 halt (SPEC-002), the multi-agent safety budget (SPEC-012), PII detection, compliance classification. A developer cannot see the whole safety surface in one place, cannot easily tune it, and cannot extend it with their own checks. Worse, human-in-the-loop is today an all-or-nothing global oversight mode - there is no way to say "pause *this specific decision* for a human" at the point in the code where it matters.

This specification introduces the **Safety Control Plane (SCP)** - the single place from which all CRP safety is seen, tuned, and extended - and the **Checkpoint primitive**, an inline, code-level, granular human-in-the-loop mechanism that lets a developer declare "a human must approve this" anywhere in their code, like a breakpoint for human judgment. The SCP makes AI safety: **centralised** (one catalogue of every capability), **visible** (each setting, its default, and its effect shown plainly), **tunable** (change any value), and **extensible** (register your own rules and checkpoints as first-class citizens of the DPE pipeline). One source of truth - the Safety Manifest - drives both a code-as-config interface and a dashboard UI. This is what turns CRP's safety from "powerful but expert-only" into "the one place you control AI safety, and it's easy."

---

## 1. What CRP Safety Actually Solves (Honest Capability Map)

Before centralising, state plainly what the safety surface does and does not do. This map is the content of the Control Plane's "what each thing does" view.

### 1.1 What CRP Safety Solves (the capabilities, centralised)

| Capability | What it catches/does | Spec | Default |
|-----------|---------------------|------|---------|
| Hallucination risk scoring | Flags unsupported/invented output, 4 levels | 005 | warn HIGH, halt CRITICAL |
| Fabrication detection | Invented entities, fake citations, false specifics | 005 §3a | on |
| Distortion detection | Changed numbers, flipped negations, altered facts | 005 §3b | on |
| Grounding verification | % of output supported by provided context | 005 | require 0.70 |
| Contradiction detection | Self-contradiction within & across windows | 005 §6 | on |
| Repetition / degeneration | Looping, recycled content | 005 §7 | warn |
| PII detection | GDPR personal data in inputs/outputs | 005 §11 | flag |
| Prompt-injection shield | Override/exfiltration patterns in inputs | 015 | on |
| Safety budget (multi-agent) | Cumulative risk across agent chains → circuit breaker | 012 | start 1.0 |
| Compliance classification | EU AI Act / GDPR / ISO / NIST per call | 010 | classify |
| Tamper-evident audit | HMAC chain - proves what happened, detects edits | 011 | on |
| HTTP 451 halt | Hard stop - unsafe output never reaches caller | 002 | on CRITICAL |
| Human oversight | Route risky output to a human | 006, this doc | manual |

### 1.2 What CRP Safety Does NOT Solve (state it in the Control Plane too)

Honesty is a feature. The Control Plane shows these limits explicitly so users have accurate expectations:

- **Model alignment** - CRP does not change model weights or values.
- **Training-data bias** - CRP does not audit the model's training set.
- **Emergent capability risk** - CRP governs observable I/O, not latent capability.
- **Semantic subtlety** - technically-true-but-misleading output may pass automated checks (this is exactly what Checkpoints, §3, are for - human judgment where automation is insufficient).

CRP governs the **observable surface** of the model - inputs and outputs - comprehensively, in real time, with evidence. It does not govern the model's internals. The Control Plane makes this boundary visible rather than letting users assume more.

---

## 2. The Safety Registry - One Catalogue, Visible and Tunable

### 2.1 The Registry

The Safety Registry is the single catalogue of every safety capability, each entry showing: what it does, its current setting, its default, its allowed range, and its effect. This is what a developer sees when they ask "what safety is in place and how do I change it?"

```python
client.safety.registry()        # the full catalogue, as data
client.safety.show()            # human-readable printout
```

Example output (printout form):

```
CRP SAFETY CONTROL PLANE - current settings
════════════════════════════════════════════════════════════
  hallucination_halt      CRITICAL    [default: CRITICAL]  what: hard-stop on critical-risk output
  hallucination_warn      HIGH        [default: HIGH]      what: flag high-risk output
  require_grounding       0.70        [range 0.0–1.0]      what: min % output supported by context
  block_fabrication       on          [default: on]        what: refuse invented entities/specifics
  block_distortion        on          [default: on]        what: refuse altered source facts
  pii_handling            flag        [flag|redact|block]  what: GDPR personal data response
  injection_shield        on          [default: on]        what: block prompt-injection patterns
  safety_budget_start     1.00        [range 0.0–1.0]      what: starting risk budget per session
  budget_floor            0.10        [range 0.0–1.0]      what: halt when budget drops below
  oversight_default       manual      [manual|auto|halt]   what: default human-in-loop behaviour
  audit                   on          [always on]          what: tamper-evident provenance chain
  checkpoints             3 active                          what: inline human-in-loop points (§3)
  custom_rules            2 active                          what: your own checks (§4)
════════════════════════════════════════════════════════════
  Change a value:   client.safety.set("require_grounding", 0.85)
  Add your own:     client.safety.rule(...)  /  crp.checkpoint(...)
  Full reference:   client.safety.explain("require_grounding")
```

### 2.2 Tuning Any Value

```python
client.safety.set("require_grounding", 0.85)        # tighten grounding
client.safety.set("hallucination_halt", "HIGH")     # halt earlier
client.safety.set("pii_handling", "redact")         # auto-redact PII
client.safety.profile("medical")                    # apply a whole profile
```

Each `set` validates against the allowed range and takes effect immediately
for subsequent calls. Changes are recorded in the audit trail (changing a
safety setting is itself a governed, logged event).

### 2.3 Explaining Any Setting

```python
client.safety.explain("require_grounding")
```
```
require_grounding (currently 0.85)
  What:    Minimum fraction of the response that must be supported by
           provided context. Below this, the output is flagged (or
           halted, per hallucination_halt).
  Effect:  Higher = stricter, fewer ungrounded claims, more halts.
           Lower = more permissive, allows more model-knowledge answers.
  Default: 0.70    Range: 0.0–1.0
  Maps to: CRP-Safety-Policy require-grounding (SPEC-006)
  Regulation: EU AI Act Art. 13 (transparency), Art. 9 (risk mgmt)
```

Every setting explains itself, including which regulation it serves. This
is the "education built into the tool" that makes safety approachable.

---

## 3. The Checkpoint Primitive - Inline Human-in-the-Loop (The Revolutionary Part)

### 3.1 The Problem With Today's HITL

Human oversight today is global and coarse: a session is in "human-review mode" or it is not. There is no way to say *"this particular decision needs a human, but everything else can proceed automatically."* Developers who want granular human judgment must build their own approval queues, state machines, and routing - outside the protocol. This is the single biggest gap in practical AI safety DX.

### 3.2 The Checkpoint: A Breakpoint for Human Judgment

A **Checkpoint** is an inline, declarative marker a developer places anywhere in their code to require human approval for a specific decision, value, or action - without building any approval infrastructure. CRP halts at the checkpoint, routes the decision to a human through the configured channel, and resumes (or aborts) based on the human's response.

```python
# Anywhere in the code - declare a human-in-the-loop point inline
decision = client.ask("Should we approve this $2M loan application?")

approved = crp.checkpoint(
    decision,
    reason="Loan approvals over $1M require human sign-off",
    route_to="risk-team@company.com",
)
# Execution PAUSES here. A human sees the decision, the reasoning (CSO),
# the evidence (sources), and the risk signals - and approves or rejects.
# `approved` resolves only after the human responds.
```

### 3.3 Three Ways to Declare a Checkpoint

**As a call (imperative - pause a specific value):**
```python
result = crp.checkpoint(value, reason="...", route_to="...")
```

**As a decorator (guard a whole function/action):**
```python
@crp.checkpoint(reason="External emails need approval", route_to="comms@co")
def send_customer_email(draft):
    email.send(draft)
# Calling send_customer_email() pauses for human approval first
```

**As a policy condition (declarative - auto-checkpoint on a condition):**
```python
client.safety.checkpoint_when(
    condition="risk >= HIGH",          # any DPE signal
    reason="High-risk output needs review",
    route_to="ai-safety@company.com",
)
client.safety.checkpoint_when(
    condition="output mentions a competitor",   # custom predicate
    route_to="legal@company.com",
)
client.safety.checkpoint_when(
    condition="tool_call == 'execute_trade'",    # agentic action gating
    route_to="trading-desk@company.com",
)
```

### 3.4 What the Human Sees

When a checkpoint fires, the human reviewer receives a complete, decision-ready package (via dashboard, email, Slack, or webhook):

```
CHECKPOINT - awaiting your decision
  Reason:     Loan approvals over $1M require human sign-off
  The output: "Recommend approval based on debt-to-income ratio of 0.3..."
  Reasoning:  [the CSO decisions with rationale - SPEC-030]
  Evidence:   [the sources CRP grounded this in]
  Risk:       MEDIUM (grounding 0.88, 0 fabrications)
  Requested by: loan-service (AI system), session crp_sess_7f3a
  ┌─────────────┬─────────────┬──────────────────────────┐
  │  APPROVE    │   REJECT    │  APPROVE WITH EDIT        │
  └─────────────┴─────────────┴──────────────────────────┘
```

The reviewer's decision is signed, recorded in the audit chain as a
`CHECKPOINT_RESOLVED` event (who, when, what), and execution resumes.
This gives tamper-evident proof of human oversight - exactly what EU AI
Act Art. 14 (human oversight) requires as evidence.

### 3.5 Checkpoint Resolution Modes

```python
crp.checkpoint(value, ..., on_timeout="reject")     # if no human responds in time
crp.checkpoint(value, ..., on_timeout="approve")    # fail-open (use carefully)
crp.checkpoint(value, ..., timeout="2h")
crp.checkpoint(value, ..., approvers=2)             # require N approvals
crp.checkpoint(value, ..., async_=True)             # don't block; resolve via callback
```

### 3.6 Why This Is Revolutionary

No existing AI framework offers an inline, code-level, granular human-in-the-loop primitive that:
- Works **anywhere** in the code (a value, a function, a condition)
- Requires **zero approval infrastructure** (CRP routes and resolves it)
- Carries the **full decision context** (reasoning, evidence, risk) to the human
- Produces **tamper-evident oversight evidence** (audit chain) for compliance
- Is **declarative** (checkpoint_when) as well as imperative

It turns human oversight from a global mode or a custom-built system into a one-line primitive a developer drops exactly where human judgment is needed. This is the feature that makes CRP's safety not just comprehensive but *usable* and genuinely differentiated.

---

## 4. Custom Rules - Extend the Safety Pipeline

### 4.1 First-Class Custom Checks

Developers can register their own safety checks that run as first-class
stages in the DPE pipeline - not bolted on afterward, but evaluated and
enforced exactly like built-in checks.

```python
@client.safety.rule(name="no_competitor_mentions", severity="HIGH")
def check_competitors(output, context):
    competitors = ["AcmeCorp", "RivalInc"]
    found = [c for c in competitors if c in output.text]
    if found:
        return crp.Violation(f"Mentioned competitor: {found}")
    return crp.OK()
```

Once registered, this rule:
- Runs on every relevant call as part of the DPE pipeline
- Its severity feeds the same risk scoring, halt, and budget logic
- Appears in the Safety Registry (§2) alongside built-in checks
- Can trigger checkpoints (`checkpoint_when(condition="rule:no_competitor_mentions")`)
- Is recorded in the audit trail when it fires

### 4.2 Custom Rule Types

```python
# Content rule - inspect output text
@client.safety.rule(name="...", severity="...")
def r(output, context): ...

# Value rule - validate a structured value
@client.safety.value_rule(name="loan_limit")
def r(value, context):
    if value.amount > 1_000_000:
        return crp.Checkpoint(route_to="risk@co")   # auto-checkpoint!
    return crp.OK()

# Tool rule - gate an agentic action
@client.safety.tool_rule(name="...", tool="execute_trade")
def r(args, context): ...
```

### 4.3 Custom Rules + Checkpoints Compose

A custom rule can *return* a checkpoint - meaning a developer can express
"when my custom condition is met, require a human" in one place. This is
the full extensibility: your logic, your checks, your human-in-the-loop,
all plugged into CRP's governed, audited pipeline.

---

## 5. The Safety Manifest - One Source of Truth (Code + UI)

### 5.1 Code-as-Config

All of the above - settings, checkpoints, custom rules - can be declared
in one manifest, version-controlled with the code:

```python
# safety.py - the single source of truth for this app's AI safety
import crp

safety = crp.SafetyManifest(
    profile="financial",                       # start from a profile
    settings={
        "require_grounding": 0.85,
        "hallucination_halt": "HIGH",
        "pii_handling": "redact",
    },
    checkpoints=[
        crp.CheckpointRule(
            condition="value.amount > 1_000_000",
            reason="Large transactions need sign-off",
            route_to="risk-team@company.com",
        ),
        crp.CheckpointRule(
            condition="tool_call == 'execute_trade'",
            route_to="trading-desk@company.com",
            approvers=2,
        ),
    ],
    custom_rules=[check_competitors, loan_limit],
)

client = crp.Client(safety=safety)
```

### 5.2 The Dashboard - Same Source of Truth, Visual

The CRP Comply dashboard renders the exact same manifest as an editable UI:

```
┌─ AI SAFETY CONTROL PLANE ─────────────────────────────────────┐
│  Profile: Financial                              [change ▾]    │
│                                                                │
│  CORE SETTINGS                                    edit         │
│    Grounding required      [████████░░] 0.85      ─────        │
│    Halt on risk level      [ HIGH ▾ ]                          │
│    PII handling            [ Redact ▾ ]                        │
│    Injection shield        [ ●ON ]                             │
│                                                                │
│  CHECKPOINTS (inline human-in-the-loop)          + add        │
│    ● Transactions > $1M    → risk-team@company.com            │
│    ● execute_trade action  → trading-desk (2 approvers)       │
│                                                                │
│  YOUR CUSTOM RULES                               + add         │
│    ● no_competitor_mentions   HIGH    [edit] [disable]        │
│    ● loan_limit               →checkpoint   [edit]            │
│                                                                │
│  WHAT THIS DOESN'T COVER  (honest limits)        [learn]      │
│    Model alignment · training bias · emergent capability      │
└────────────────────────────────────────────────────────────────┘
```

Changes in the dashboard update the manifest; changes in code update the
dashboard. One source of truth, two interfaces - code for developers, UI
for safety/compliance teams who don't write code. A compliance officer can
tighten grounding or add a checkpoint without touching the codebase, and a
developer sees it in their manifest.

### 5.3 Settings, Tunable AND Extensible (the exact ask)

The manifest delivers precisely what was requested:
- **Shown the general settings** → the Registry (§2) and dashboard show every built-in setting with its default.
- **Change them in value** → `client.safety.set(...)` or the dashboard sliders/dropdowns.
- **Add their own** → custom rules (§4) and checkpoints (§3), first-class in the same pipeline and the same view.

---

## 6. Everything Managed From One Place

### 6.1 The Single Control Surface

```python
client.safety            # THE one object for all AI safety
  .show()                # see everything (Registry)
  .set(key, value)       # tune any built-in setting
  .profile(name)         # apply an industry profile
  .explain(key)          # understand any setting + its regulation
  .rule(...)             # add a custom check
  .checkpoint_when(...)  # add a declarative human-in-loop
  .checkpoints()         # list active checkpoints
  .manifest()            # export the full manifest
  .audit()               # see every safety event + every checkpoint decision
  .coverage()            # what regulations the current config satisfies
```

And `crp.checkpoint(...)` as the inline primitive, usable anywhere.

### 6.2 Regulation Coverage View

```python
client.safety.coverage()
```
```
Your current safety config satisfies:
  EU AI Act:  Art. 9 ✓  Art. 13 ✓  Art. 14 ✓ (3 checkpoints = human oversight)
              Art. 12 ✓ (audit chain)   Art. 11 ✓ (Comply evidence)
  GDPR:       Art. 5 ✓  Art. 22 ✓ (checkpoints on automated decisions)
  ISO 42001:  A.6.2.2 ✓  A.9.2 ✓
  Gaps:       none for HIGH-risk classification
```

This connects the safety settings directly to regulatory outcomes - the
developer sees not just "grounding is 0.85" but "this satisfies EU AI Act
Art. 13." Safety configuration becomes compliance configuration.

---

## 7. Headers

| Header | Meaning |
|--------|---------|
| `CRP-Safety-Checkpoint` | A checkpoint fired; awaiting/with human decision |
| `CRP-Safety-Checkpoint-Id` | The checkpoint instance id (for resolution) |
| `CRP-Safety-Checkpoint-Status` | `pending` / `approved` / `rejected` / `edited` / `timeout` |
| `CRP-Safety-Custom-Rules-Fired` | Names of custom rules that triggered this call |
| `CRP-Safety-Manifest-Hash` | Hash of the active Safety Manifest (config provenance) |

The `CRP-Safety-Manifest-Hash` makes the safety configuration itself
tamper-evident and auditable - you can prove which safety config was in
force for any given call.

---

## 8. The Experience This Creates

**Before:** AI safety in CRP was real but scattered across six specs,
expert-only, globally configured, with no way to insert human judgment at
a specific point without building custom infrastructure.

**After:** One object (`client.safety`) and one inline primitive
(`crp.checkpoint`). See everything. Tune anything. Add your own. Drop a
human-in-the-loop anywhere in one line. Manage it all from code or a
dashboard sharing one source of truth. Every safety decision and every
human approval recorded in a tamper-evident chain that doubles as
regulatory evidence.

A developer can make their AI system safe, compliant, and human-overseen
in the exact places it matters - in minutes, in plain language, without
becoming an expert in the underlying protocol. That is the experience
that makes CRP not just the most capable AI safety layer but the easiest
to actually use.

---

## 9. Honest Status & Limits

The Checkpoint primitive requires the resolution infrastructure (routing
to human channels, the approval UI, the resolution callback) - this is the
CRP Comply / Gateway product surface (SPEC-016), and it is real engineering
to build well, though the protocol contract is fully defined here.

The Control Plane centralises and exposes existing mechanisms; it does not
add new detection capability (that lives in the DPE, SPEC-005). Its value
is making the existing power visible, tunable, and extensible - a DX and
control contribution, honestly, not a new detection algorithm.

Custom rules run developer code in the safety path. They must be sandboxed
and time-bounded (a custom rule cannot be allowed to hang the pipeline).
The implementation must enforce execution limits on custom rules.

The honest boundary of §1.2 still holds: the Control Plane governs the
observable surface comprehensively and makes human judgment insertable
anywhere, but it does not solve model-internal alignment. Checkpoints are
precisely the acknowledgement that some judgments must remain human.

---

## 10. References

- CRP-SPEC-005 - Decision Provenance Engine (detection the SCP exposes)
- CRP-SPEC-006 - Safety Policy (settings the Registry surfaces)
- CRP-SPEC-011 - Audit Trail (checkpoint decisions recorded here)
- CRP-SPEC-012 - Multi-Agent Safety (budget shown in the Control Plane)
- CRP-SPEC-030 - Cognitive State Object (the reasoning shown to reviewers)
- CRP-SPEC-032 - Developer Experience (the SCP is the safety steering wheel)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
