# CRP-SPEC-046: User-Defined Cognition — The Thinking Process Compiler

**Document:** CRP-SPEC-046  
**Title:** Context Relay Protocol (CRP) — User-Defined Cognition: Compiling Human-Described Thinking Processes Into Executable Reasoning Patterns  
**Version:** 1.0.0  
**Status:** Foundational — Frontier  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Builds on:** CRP-SPEC-021 (ROS), CRP-SPEC-031 (STL)  
**Prerequisites:** CRP-SPEC-021, 030, 031

---

## Abstract

Models can reason, but they do not *know how to think* about a specific problem the way an expert does — and the user cannot easily tell them. Prompt engineering is the current, crude answer: describe the desired reasoning in prose and hope the model follows it. This document specifies **User-Defined Cognition (UDC)** — a system where a user describes a thinking process at a surface level (in plain language or a simple visual flow), and CRP compiles that description into an executable reasoning pattern: a structured sequence of cognitive operations (STL, SPEC-031), verification steps (DPE), and reasoning strategies (ROS, SPEC-021) that the model executes to perform tailored reasoning for that task. The user defines *how to think*; CRP turns it into *how the model thinks*. This addresses a real gap — there is no clean way today to encode domain-specific reasoning methodology into an agent without brittle prompt-hacking — and it does so by compiling human-described process into the cognitive primitives CRP already has, rather than hoping a prose instruction is obeyed.

---

## 1. The Gap: Knowing How to Think

### 1.1 The Problem

An expert doesn't just know facts — they have a *method*: a way of approaching problems in their domain. A diagnostician follows a differential process. An auditor follows a verification process. An engineer follows a debugging process. These are *thinking processes* — structured ways of reasoning toward a reliable answer.

LLMs have no native access to a user's preferred thinking process. The user's only current tool is prose prompting ("think step by step, first consider X, then Y...") which is brittle: the model may ignore it, half-follow it, or lose it over a long task. There is no way to *define* a thinking process and have it *reliably executed*.

### 1.2 What's Needed

A way for a user to:
1. Describe a thinking process at a surface level — plainly, or as a simple visual flow ("first gather the evidence, then list hypotheses, then test each against the evidence, then rank by likelihood, then state the conclusion with confidence").
2. Have CRP **compile** that description into an executable reasoning pattern — a real sequence of cognitive operations with verification, not a prose hope.
3. Have the model **reliably execute** that pattern for the task, with each step governed and verified.

This is "teaching the model how to think" about a class of problems — defining cognition, not just providing context.

---

## 2. User-Defined Cognition

### 2.1 The Surface: How a User Defines Thinking

A user defines a thinking process at one of three levels of formality:

**Plain language:**
```
"To diagnose a production incident: first gather all the symptoms and
recent changes. Then list possible causes. For each cause, check it
against the evidence. Rule out what doesn't fit. Rank what remains by
likelihood. Recommend the most likely with a confidence level and the
next diagnostic step."
```

**Visual flow (in the Gateway console, SPEC-043):**
```
[Gather: symptoms + changes] → [Generate: candidate causes]
   → [For each: test against evidence] → [Eliminate: non-fits]
   → [Rank: by likelihood] → [Conclude: top cause + confidence + next step]
```

**Structured (for power users):**
```yaml
thinking_process: incident_diagnosis
steps:
  - gather:    { inputs: [symptoms, recent_changes] }
  - generate:  { operation: hypotheses, from: gathered }
  - test:      { operation: evaluate, each: hypothesis, against: evidence }
  - eliminate: { rule: remove_unsupported }
  - rank:      { by: likelihood }
  - conclude:  { output: [top_cause, confidence, next_step] }
```

All three describe the same process at different formality. The user picks their comfort level.

### 2.2 The Compiler: Surface → Executable Pattern

CRP compiles the user's description into an executable reasoning pattern built from primitives it already has:

```
USER DESCRIPTION (any of the three levels above)
   │
   ▼
PARSE — extract the steps, their operations, inputs, and flow
   │
   ▼
MAP each step to CRP cognitive primitives:
   - "gather"    → STL RETRIEVE operation (SPEC-031)
   - "generate"  → STL GENERATE (hypotheses)
   - "test/eval" → STL EVALUATE + DPE verification per hypothesis
   - "eliminate" → a filter rule + DPE grounding check
   - "rank"      → STL ANALYSE (ordering)
   - "conclude"  → STL SYNTHESISE + confidence from DPE grounding scores
   │
   ▼
ADD verification & reliability:
   - each reasoning step verified by DPE (SPEC-005)
   - high-stakes steps use ROS consensus/debate (SPEC-021)
   - the whole pattern carried in the CSO (SPEC-030)
   │
   ▼
EXECUTABLE REASONING PATTERN — a governed, verified sequence the
   model executes for this task class
```

The compilation target is CRP's existing cognitive infrastructure (STL operations, DPE verification, ROS reliability, CSO state). UDC is not a new reasoning engine — it is a *front-end* that lets users define which of CRP's cognitive primitives run, in what order, for their problem. That reuse is what makes it real rather than aspirational: the primitives already exist and are governed; UDC just lets the user compose them by describing a process.

### 2.3 Why This Beats Prose Prompting

| Prose prompt | Compiled UDC pattern |
|--------------|---------------------|
| Model may ignore/half-follow | Steps are executed operations, not suggestions |
| No verification | Each step DPE-verified |
| Lost over long tasks | Carried in the CSO, re-anchored each step |
| No reliability control | High-stakes steps use ROS consensus |
| Opaque | Each step's execution is observable (headers) |

The user's thinking process becomes governed, verified, reliably-executed structure — not a hope that the model read the prompt carefully.

---

## 3. Reusable Thinking Processes

### 3.1 Define Once, Apply Many

A compiled thinking process is reusable. A diagnostician defines their differential process once; it applies to every incident. An auditor defines their verification process once; it applies to every audit. The thinking process becomes a named, reusable cognitive asset:

```python
client.cognition.define("incident_diagnosis", process_description)
answer = client.ask("Diagnose this outage", thinking="incident_diagnosis")
```

### 3.2 A Library of Thinking

Organisations build a library of their expert thinking processes — encoding institutional reasoning methodology into reusable patterns. This is valuable IP capture: the *way your best people think* about problems, encoded as executable patterns any agent can apply. A consultancy's analysis method, a hospital's diagnostic protocol, a firm's due-diligence process — defined as cognition, applied consistently.

### 3.3 Relationship to Authoritative Domain Agents (SPEC-044)

UDC + ADA compose powerfully: an Authoritative Domain Agent (grounded in an official corpus) executing a user-defined thinking process (the expert method for that domain) is a domain expert that both *knows the right things* (ADA) and *thinks the right way* (UDC). A clinical ADA grounded in guidelines, reasoning through a defined diagnostic process, is far more than either alone.

---

## 4. The Honest Boundary

### 4.1 What UDC Does

It lets users define a reasoning *structure* and have CRP execute it reliably with verification. It makes the model *follow a thinking process* far more reliably than prompting, because the steps are governed operations, not instructions.

### 4.2 What UDC Does Not Do

**It does not make the model more intelligent at each step.** UDC structures and sequences reasoning; it does not increase the model's raw reasoning power within a step (that's CLD/ROS amplification, SPEC-020/021, and even those have limits). A model that cannot perform a reasoning step well will perform it poorly even in a perfectly-defined process. UDC ensures the *right steps happen in the right order with verification* — it does not guarantee each step is brilliant.

**It does not invent good thinking processes.** UDC executes the *user's* defined process. If the user defines a poor thinking process, UDC executes a poor process faithfully. It is a tool for encoding and reliably executing human expertise, not for generating expertise. (It can *suggest* processes, but the quality is the user's.)

**Compilation is imperfect.** Mapping a plain-language description to the right cognitive primitives is a hard NLP problem; the compiler will sometimes mis-map a step. The structured level (§2.1) exists for when precision matters; plain-language is convenient but less precise. Compiled patterns should be reviewable and editable before use.

### 4.3 The Honest Novelty

The pieces (chain-of-thought, reasoning structures, prompt patterns) exist. UDC's contribution is *compiling user-described process into governed, verified, reusable executions on existing cognitive primitives* — making "how to think" a definable, reliable, reusable asset rather than brittle prose. That is a real interface and reliability contribution. It is not a new reasoning capability; it is reliable orchestration of described reasoning. Claimed precisely, it is valuable and defensible; claimed as "we made the model think better," it would be overreach.

---

## 5. Headers

| Header | Meaning |
|--------|---------|
| `CRP-UDC-Process` | The named thinking process applied |
| `CRP-UDC-Steps` | The compiled step sequence executed |
| `CRP-UDC-Step-Current` | The step currently executing |
| `CRP-UDC-Verified-Steps` | How many steps passed DPE verification |

---

## 6. The Product Framing

> "Define how your AI thinks. Describe your expert reasoning process in plain
> language or a visual flow; CRP compiles it into a governed, verified
> reasoning pattern your agents execute reliably — your institutional
> thinking, encoded and applied consistently."

Surfaced in the Gateway console (SPEC-043) as a visual thinking-process
builder, and in the SDK as `client.cognition.define(...)`. Composes with
ADAs (SPEC-044) for agents that know the right things and think the right way.

---

## 7. References

- CRP-SPEC-021 — ROS (reliability for high-stakes reasoning steps)
- CRP-SPEC-030 — CSO (carries the reasoning pattern state)
- CRP-SPEC-031 — STL (the cognitive operations UDC compiles to)
- CRP-SPEC-043 — Gateway console (the visual thinking-process builder)
- CRP-SPEC-044 — Authoritative Domain Agent (composes with UDC)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
