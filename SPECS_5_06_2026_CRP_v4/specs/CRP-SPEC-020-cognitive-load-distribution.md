# CRP-SPEC-020: Cognitive Load Distribution (CLD)

**Document:** CRP-SPEC-020  
**Title:** Context Relay Protocol (CRP) — Cognitive Load Distribution: Protocol-Level Capability Amplification for Sub-Scale Models  
**Version:** 3.0.0  
**Status:** Draft — Frontier Innovation  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-003, CRP-SPEC-004, CRP-SPEC-005, CRP-SPEC-008, CRP-SPEC-018, CRP-SPEC-019

---

## Abstract

This document specifies Cognitive Load Distribution (CLD) — the protocol mechanism by which CRP makes a smaller, inherently weaker model perform complex tasks that would normally require a larger model. AIR (SPEC-018) and CQR (SPEC-019) make a model *less wrong*. CLD makes it *more capable*.

The core insight: a 7-billion-parameter model fails complex tasks not because it cannot perform the individual sub-steps, but because it cannot simultaneously hold decomposition, planning, state tracking, execution, verification, and composition in a single generation pass. A 70-billion-parameter model does all six at once. **CLD moves five of those six functions out of the model and into the protocol**, leaving the model to do only what it does well: atomic language generation over well-scoped, fully-contextualised micro-tasks.

The protocol becomes the prefrontal cortex. The model becomes the language faculty. This is capability amplification, not error reduction.

---

## 1. The Capability Gap — Precisely Defined

### 1.1 What a Larger Model Actually Has

The performance gap between a 7B and a 70B model decomposes into six distinct capabilities. Critically, only some are scale-bound:

| Capability | What it is | Scale-bound? | Addressable by protocol? |
|-----------|-----------|--------------|-------------------------|
| **Parametric knowledge** | Knows more facts | Yes | ✅ Already solved — CKF supplies external knowledge |
| **Working memory** | Holds more in-flight state coherently | Partially | ✅ Protocol can BE the working memory |
| **Reasoning depth** | More sequential steps per pass | Partially | ✅ Protocol can decompose into atomic steps |
| **Cognitive load capacity** | More simultaneous operations per generation | Partially | ✅ Protocol can size tasks to the model |
| **Self-consistency** | More reliable per single pass | Partially | ✅ Protocol can ensemble multiple passes |
| **Emergent reasoning** | Genuinely scale-bound complex logic/math | Yes | ❌ Cannot fully fix — route to tools |

Five of six are partially or fully addressable at the protocol level. This is the basis of the capability amplification thesis.

### 1.2 The Core Failure: Simultaneous Cognitive Demand

When a weak model is given a complex task — "Write a complete technical architecture document for a distributed payment system" — it must simultaneously:

1. **Decompose** the task into sections and sub-problems
2. **Plan** the order and dependencies
3. **Track** what it has already covered and what variables/decisions are established
4. **Execute** the actual writing of each part
5. **Verify** that what it wrote is correct and consistent
6. **Compose** the parts into a coherent whole

A 7B model attempting all six at once does each one poorly. The cognitive load exceeds its capacity. The result is the failure cascade described in CRP-SPEC-019: it loses the plan (Class 4 degeneration), forgets prior decisions (working memory failure), and fills gaps with confabulation (Class 1).

**A 70B model has the headroom to do all six adequately in one pass. A 7B does not. But a 7B can do any ONE of them well in isolation.**

### 1.3 The CLD Thesis

If the protocol performs decomposition, planning, state tracking, verification, and composition — and the model performs only atomic execution over a fully-scoped, fully-contextualised micro-task — then the model is operating within its cognitive capacity at every step. The composite output approaches what a larger model produces, because the larger model's advantage (doing everything at once) has been replaced by the protocol doing everything in sequence.

---

## 2. The Six-Function Distribution

CLD redistributes the six cognitive functions between protocol and model:

```
┌────────────────────────────────────────────────────────────┐
│  PROTOCOL (the prefrontal cortex)                          │
│                                                             │
│  1. DECOMPOSE  — break task into atomic micro-tasks        │
│  2. PLAN       — order micro-tasks, resolve dependencies   │
│  3. TRACK      — maintain working memory state across steps│
│  5. VERIFY     — check each output (DPE) before proceeding │
│  6. COMPOSE    — assemble verified outputs into whole      │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼ (one atomic, fully-scoped task at a time)
┌────────────────────────────────────────────────────────────┐
│  MODEL (the language faculty)                              │
│                                                             │
│  4. EXECUTE    — generate language for ONE micro-task      │
│                  with complete context and no other demands │
└────────────────────────────────────────────────────────────┘
```

### 2.1 Function 1 — Decomposition (Protocol)

The protocol decomposes the task into a dependency graph of atomic micro-tasks. An atomic micro-task is one a 7B model can complete in a single generation without exceeding its cognitive capacity.

**Decomposition method:** The protocol uses the model itself for decomposition (a planning pass), but the decomposition pass is itself an atomic task — "list the components of X" is something a 7B does well. The output is structured into a Task Graph:

```
TaskGraph {
  root_task:        string
  micro_tasks: [
    {
      task_id:        string
      description:    string         // atomic, single-focus instruction
      dependencies:   string[]       // task_ids that must complete first
      est_complexity: enum           // TRIVIAL | SIMPLE | MODERATE
      required_facts: string[]       // CKF concepts needed for this task
      output_type:    enum           // PROSE | LIST | DECISION | ANALYSIS | CODE
    }
  ]
}
```

**Complexity gating:** If decomposition produces a micro-task rated COMPLEX (beyond MODERATE), CLD recursively decomposes that task further until all leaf tasks are at most MODERATE. This guarantees every task the model sees is within its capacity.

### 2.2 Function 2 — Planning (Protocol)

The protocol topologically sorts the Task Graph, resolving dependencies. It determines execution order such that every micro-task's dependencies are complete before it executes. This is a graph algorithm, not a model operation — it is deterministic and reliable, exactly where a model would be unreliable.

The plan also identifies parallelisable micro-tasks (no shared dependencies) that can use fan-out dispatch (CRP-SPEC-004 §6).

### 2.3 Function 3 — State Tracking / Working Memory (Protocol)

This is the single most important CLD function. The protocol maintains a **Working Memory State** that persists across all micro-task executions:

```
WorkingMemoryState {
  established_facts:    Fact[]          // verified outputs from completed tasks
  decisions:            Decision[]      // choices made (e.g., "chose PostgreSQL")
  variables:            map<str, str>   // named values established during the task
  constraints:          string[]        // constraints discovered or imposed
  open_questions:       string[]        // unresolved items flagged for later
  completed_task_ids:   string[]
  composition_outline:  OutlineNode[]   // where each output fits in the whole
}
```

When micro-task N executes, the protocol injects ONLY the relevant subset of Working Memory State — the decisions, facts, and variables that micro-task N depends on. The model never has to "remember" anything. The protocol remembers. The model receives exactly what it needs, no more.

**This is what replaces the larger model's working memory.** A 70B model holds the entire task state in its activations. A 7B cannot. CLD externalises that state into the protocol and feeds the model precisely the slice it needs for each atomic step.

### 2.4 Function 4 — Execution (Model)

The model receives a single micro-task with:
- The atomic instruction (one focused thing to do)
- The exact CKF facts needed (from `required_facts`)
- The relevant Working Memory slice (only dependencies)
- The output type constraint (PROSE / LIST / DECISION / etc.)
- AIR/CQR augmentations (error quarantine, reasoning scaffold if needed)

The model does one thing. It does it with complete context and no competing cognitive demands. This is where a 7B performs at its best.

### 2.5 Function 5 — Verification (Protocol via DPE)

Each micro-task output is verified by the DPE (CRP-SPEC-005) before it is accepted into Working Memory State. If verification fails (fabrication, distortion, low grounding), the micro-task is re-executed with AIR feedback (error quarantine) before proceeding. **Errors are caught at the micro-task level, before they can propagate** — this is far more effective than catching them in a monolithic output.

### 2.6 Function 6 — Composition (Protocol)

Once all micro-tasks are verified and complete, the protocol composes them into the final output according to the `composition_outline`. Composition includes:
- Ordering outputs per the plan
- Inserting transitions (flow stitching, CRP-SPEC-005 §11.5)
- Final cross-output coherence check (DPE Stage 6)
- Final completeness verification against the original task (DPE Stage 8)

The composition step may use one final model pass to smooth transitions, but the substance is already generated and verified.

---

## 3. Why This Produces 70B-Class Output From a 7B Model

### 3.1 The Mechanism

A 70B model's advantage on a complex task is that it can juggle all six functions simultaneously with enough headroom to do each adequately. Its disadvantage is that even it does each one *less than perfectly* under simultaneous load — the 70B is also splitting its capacity six ways, just with more total capacity.

CLD gives the 7B model 100% of its capacity for each function in turn:
- 100% capacity on decomposition (one atomic planning task)
- Protocol handles planning (deterministic, perfect)
- Protocol handles state (perfect recall, no drift)
- 100% capacity on each execution micro-task
- Protocol handles verification (DPE, systematic)
- Protocol handles composition (deterministic assembly)

The 7B, focused entirely on one well-scoped task at a time, with perfect external memory and systematic verification, produces output whose quality on each atomic step rivals the 70B's — because the atomic steps are within both models' capabilities. The 70B's advantage was never the atomic steps; it was holding them all together. CLD holds them together with the protocol.

### 3.2 The Honest Boundary

CLD cannot make a 7B do something genuinely beyond its capability at the atomic level. If a single micro-task requires emergent reasoning that only manifests at scale (certain mathematical proofs, complex multi-constraint optimisation in one step), decomposition cannot help — the atomic step itself is too hard.

For these cases, CLD does two things:
1. **Recursive decomposition** until the step IS within capacity (works for most cases)
2. **Tool routing** — if a step cannot be decomposed below the capability threshold, route it to a deterministic tool (calculator, solver, code execution) rather than the model

This is the honest limit: CLD amplifies capability for tasks that decompose into atomic steps the model can perform. It cannot conjure capability that isn't present at any decomposition level. But the class of tasks that truly resist decomposition is far smaller than the class of tasks a 7B fails at monolithically.

---

## 4. CLD Headers

### 4.1 CRP-CLD-Active

**Direction:** RES  
**Definition:** Whether Cognitive Load Distribution is active for this task.

```
CRP-CLD-Active: true
```

### 4.2 CRP-CLD-Task-Graph-Size

**Direction:** RES  
**Definition:** The number of micro-tasks the task was decomposed into, expressed as `total/completed`.

```
CRP-CLD-Task-Graph-Size: 14/14
```

### 4.3 CRP-CLD-Max-Complexity

**Direction:** RES  
**Definition:** The highest complexity rating among all micro-tasks after decomposition. If this is MODERATE or below, all tasks were within model capacity.

```
CRP-CLD-Max-Complexity: MODERATE
```

### 4.4 CRP-CLD-Tool-Routed

**Direction:** RES  
**Definition:** Number of micro-tasks routed to deterministic tools rather than the model (because they could not be decomposed below the capability threshold).

```
CRP-CLD-Tool-Routed: 2
```

### 4.5 CRP-CLD-Amplification-Estimate

**Direction:** RES  
**Definition:** An estimate of the effective capability multiplier achieved — the ratio of task complexity successfully completed to the complexity the model could handle monolithically. Derived from task graph depth and verification pass rate. Informational only.

```
CRP-CLD-Amplification-Estimate: 3.2x
```

---

## 5. Safety Policy Integration

```
CRP-Safety-Policy: ...; cld-mode=auto; cld-max-decomposition-depth=4
```

| Directive | Values | Meaning |
|-----------|--------|---------|
| `cld-mode` | `off`, `auto`, `force` | Off: monolithic. Auto: decompose if task complexity warrants. Force: always decompose. |
| `cld-max-decomposition-depth` | Integer | Maximum recursive decomposition depth. Default: 4. |

---

## 6. Interaction With Other CRP Subsystems

| Subsystem | Interaction |
|-----------|-------------|
| **CKF (SPEC-009)** | Supplies `required_facts` for each micro-task |
| **Continuation/DAG (SPEC-004)** | Micro-tasks ARE the windows; the Task Graph IS the DAG |
| **DPE (SPEC-005)** | Verifies each micro-task output |
| **Dispatch (SPEC-008)** | Parallelisable micro-tasks use fan-out; composition uses fan-in |
| **AIR (SPEC-018)** | Error quarantine and feedback applied per micro-task |
| **CQR (SPEC-019)** | Cognitive failure detection per micro-task |

CLD is the orchestration layer that ties all of these together for capability amplification. It is the highest-level CRP subsystem — it uses everything below it.

---

## 7. References

- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-008 — Dispatch Strategy Specification
- CRP-SPEC-018 — Adaptive Intelligence Relay
- CRP-SPEC-019 — Cognitive Quality Relay

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
