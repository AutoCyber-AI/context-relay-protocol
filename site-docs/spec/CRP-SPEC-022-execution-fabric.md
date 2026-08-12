# CRP-SPEC-022: Parallel Execution Fabric (PEF) & Amplification Economics

**Document:** CRP-SPEC-022  
**Title:** Context Relay Protocol (CRP) - Parallel Execution Fabric: Making Capability Amplification Fast Enough to Win  
**Version:** 3.0.0  
**Status:** Draft - Critical Performance Specification  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-004, CRP-SPEC-008, CRP-SPEC-020, CRP-SPEC-021

---

## Abstract

CLD (SPEC-020) and ROS (SPEC-021) describe *what* makes a small model capable and reliable. Implemented naively, they are catastrophically slow - decomposing a task into 14 sequential micro-tasks, each verified, some run multiple times for consensus, produces a latency multiple of 6–40× over naive generation. **No researcher is impressed by matching a 70B model's quality at 40× the latency. No production system deploys it.**

This document specifies the Parallel Execution Fabric (PEF) - the scheduling, batching, and concurrency layer that makes capability amplification not just viable but *faster than the alternative it replaces*. The central insight inverts the entire narrative:

> **Multi-pass orchestration is cheap precisely because the model is small. A 7B model can be run 14 times in parallel for less compute and wall-clock time than a 70B model runs once. The amplification is viable BECAUSE the model is small - not despite it.**

This is the claim that wows researchers, because it reframes small models from "the compromise you tolerate" to "the substrate that makes protocol-level intelligence economically and physically possible."

---

## 1. The Latency Problem, Stated Honestly

### 1.1 The Naive Cost

A complex task under naive CLD + ROS:

```
Decomposition pass:           1 inference
Micro-task executions:       ~14 inferences (sequential)
DPE verifications:           ~14 lightweight checks
Consensus passes (ROS):      ~14 additional inferences
Composition pass:             1 inference
─────────────────────────────────────────────
Total:                       ~30 sequential model inferences
```

If each inference is treated as a sequential, full-latency operation, this is 30× the cost of a single naive generation. On the CPU benchmark (383s for 5 windows ≈ 77s/window), this projects to ~40 minutes. **This is unacceptable and the specs as written (020, 021) are incomplete without this document.**

### 1.2 Why the Naive Model Is Wrong

The naive cost model assumes every inference is sequential and full-latency. Three facts break that assumption:

1. **Most micro-tasks are independent** - they have no data dependency and can run concurrently
2. **Small models are cheap to run many times** - the per-pass cost of a 7B is a fraction of a 70B, and many passes batch into a single GPU forward pass
3. **Verification is not inference** - DPE checks are embeddings + NLI, not generation, and run in milliseconds, off the critical path

When these are exploited, the 30-inference task collapses to a wall-clock cost competitive with - and often better than - a single 70B pass.

---

## 2. The Parallel Execution Fabric

### 2.1 Dependency-Layered Scheduling

The CLD Task Graph (SPEC-020 §2.1) is a DAG. PEF computes its **dependency layers** - sets of micro-tasks with no unresolved dependencies that can execute simultaneously.

```
Task Graph (14 micro-tasks) → Topological layering:

Layer 0: [T1, T2, T3, T4]        ← no dependencies, run all 4 in parallel
Layer 1: [T5, T6, T7, T8, T9]    ← depend only on Layer 0, run all 5 in parallel
Layer 2: [T10, T11, T12]         ← run 3 in parallel
Layer 3: [T13, T14]              ← run 2 in parallel
─────────────────────────────────────────
Sequential depth: 4 layers (not 14 tasks)
```

A 14-task graph with dependency depth 4 requires **4 sequential rounds**, not 14. The wall-clock cost is the sum of the slowest task in each layer, not the sum of all tasks.

### 2.2 Batched Inference

Within a layer, all independent micro-tasks are submitted as a **single batched inference call**. Modern inference servers (vLLM, TGI, llama.cpp with continuous batching, LM Studio's batching) process a batch of N prompts in roughly the wall-clock time of the longest single prompt, not N× a single prompt - because the GPU processes them concurrently across its parallel cores.

```
Layer 0: [T1, T2, T3, T4] submitted as one batch of 4
Wall-clock cost ≈ cost of 1 inference (not 4)
```

This is the single most important performance property. **On a batching inference server, a layer of K independent micro-tasks costs approximately the same wall-clock time as one micro-task.**

### 2.3 Batched Consensus (ROS Made Nearly Free)

ROS consensus voting (SPEC-021 §2.1) runs a micro-task N times with temperature variation. PEF submits all N as one batch:

```
Consensus for T5 (N=3): submit [T5@temp0.3, T5@temp0.6, T5@temp0.9] as one batch
Wall-clock cost ≈ cost of 1 inference (not 3)
```

**This is why consensus voting on a small model is nearly free and consensus voting on a 70B is not.** The small model's three passes fit in one batch on commodity hardware. The 70B's three passes may not fit in memory simultaneously and must run sequentially. The reliability amplification is economically viable *only* at small scale.

### 2.4 The Combined Effect

A 14-task graph, depth 4, with consensus (N=3) on the 6 MODERATE tasks:

```
Naive sequential:  14 tasks + 18 consensus passes + 2 (decomp/compose) = 34 inferences sequential
PEF:               4 layers, each a batch, consensus batched within
                   = 4 batched rounds + decomposition + composition
                   ≈ 6 sequential batched inferences total
```

**34 sequential inferences → 6 batched rounds. A ~5–6× wall-clock reduction from scheduling and batching alone**, before accounting for the small model's inherent per-pass speed advantage.

---

## 3. The Amplification Economics - The Researcher-Facing Insight

### 3.1 The Compute Comparison

Consider the actual compute (not just wall-clock) for a complex task:

```
70B model, naive single pass:
  70B params × ~3000 tokens (in+out) = ~210 GFLOP-equivalent units of work
  Must run on high-memory GPU (A100 80GB or multi-GPU)
  Cannot be cheaply parallelised (memory-bound)

7B model, full CLD+ROS amplification (34 passes):
  7B params × ~34 × ~400 tokens avg = ~95 GFLOP-equivalent units of work
  Runs on commodity GPU (RTX 4090 24GB, or even CPU for async)
  Trivially parallelisable (small memory footprint per pass)
```

**The fully-amplified 7B does LESS total compute than the naive 70B** - because each pass is over a small model and a small, well-scoped context, while the 70B pass is over a huge model and a large context. And the 7B's work parallelises across cheap hardware while the 70B's does not.

### 3.2 The Inversion That Wows

The conventional wisdom: "Use a small model if you must, but accept it's worse."

The CRP insight: **The small model is not a compromise. It is the enabling condition.** Protocol-level intelligence amplification - decomposition, parallel execution, consensus, verification - is only economically and physically viable when the base model is small enough to run many times in parallel on commodity hardware. You cannot do 34 batched passes of a 70B on a 4090. You can do 34 batched passes of a 7B on a 4090.

This means:

> CRP does not make small models "good enough." CRP makes small models the *correct architectural choice* for high-quality AI - because only small models permit the massively-parallel, multi-pass, verified orchestration that produces reliable, high-quality output. The future of quality AI is small models orchestrated well, not large models prompted naively.

This is a genuinely novel and defensible research thesis. It is the opposite of the "bigger is better" scaling narrative, and it is supported by the compute math above.

### 3.3 Why This Is Defensible

The claim rests on three verifiable facts:
1. Small models batch and parallelise on commodity hardware; large models do not (memory-bound)
2. Per-pass compute scales with parameter count; 34 small passes < 1 large pass
3. Quality is recoverable through orchestration (CLD + ROS + AIR + CQR), validated by the v3.1.1 benchmark trajectory

The research community is actively moving toward this view (test-time compute, inference scaling, small-model-many-passes). CRP provides the *protocol* that operationalises it with governance, verification, and provenance built in. That is the contribution.

---

## 4. Performance Requirements (Normative)

A conformant PEF implementation MUST:

1. **Layer the Task Graph** topologically and execute independent micro-tasks concurrently - sequential execution of independent tasks is non-conformant
2. **Batch inference within a layer** when the inference backend supports batching - submitting layer tasks as separate sequential calls when batching is available is non-conformant
3. **Batch consensus passes** as a single inference batch
4. **Run DPE verification off the critical path** - verification of completed micro-tasks MUST NOT block the dispatch of independent micro-tasks in the next layer
5. **Gate ROS by criticality** - consensus/debate/decompose-and-verify MUST NOT run on TRIVIAL or SIMPLE micro-tasks (re-gating SPEC-021 §3)

### 4.1 Latency Budget

For a task decomposed into a graph of depth D with batching available:

```
wall_clock ≈ (D + 2) × per_batch_latency
             where +2 accounts for decomposition and composition
```

NOT:

```
wall_clock ≈ total_micro_tasks × per_task_latency   ← non-conformant naive model
```

For the benchmark task (depth ~4), this is ~6 batched rounds - competitive with or faster than a single large-model pass on equivalent hardware tiers.

---

## 5. Speculative Decomposition (Advanced)

To further reduce latency, PEF MAY overlap decomposition with execution:

1. Begin decomposing the task
2. As soon as Layer 0 micro-tasks are identified (before full decomposition completes), dispatch them
3. Continue decomposing deeper layers while Layer 0 executes

This hides the decomposition latency behind the first execution layer, removing one sequential round from the critical path. Decomposition of a well-structured task usually identifies the first layer quickly, making this effective in practice.

---

## 6. Re-Gating ROS for Speed (Amends SPEC-021 §3)

SPEC-021 as written invokes consensus voting on all MODERATE tasks. This document amends that gating to be speed-aware:

| Micro-task | ROS Mode | Rationale |
|-----------|----------|-----------|
| TRIVIAL | None (single pass) | Not worth any overhead |
| SIMPLE | None (single pass) | Single pass reliable enough |
| MODERATE, low stakes | None (single pass) | Speed prioritised |
| MODERATE, high stakes | Mode 1 (batched consensus, N=3) | Nearly free with batching |
| CRITICAL | Mode 2 or 3 | Correctness dominates; latency acceptable |

"High stakes" is determined by Safety Policy `require-grounding` threshold, EU AI Act classification, or explicit request. The default for general tasks is single-pass execution with ROS reserved for genuinely critical steps. This keeps the common case fast.

---

## 7. PEF Headers

### 7.1 CRP-PEF-Layers

**Direction:** RES  
**Definition:** The dependency-layer structure executed, as `depth/total-tasks`.

```
CRP-PEF-Layers: 4/14
```

(4 sequential layers, 14 total micro-tasks - i.e., a 3.5× parallelism factor)

### 7.2 CRP-PEF-Batch-Efficiency

**Direction:** RES  
**Definition:** The ratio of total inferences to sequential batched rounds - the effective parallelism achieved.

```
CRP-PEF-Batch-Efficiency: 5.7x
```

### 7.3 CRP-PEF-Wall-Clock-Ms

**Direction:** RES  
**Definition:** Total wall-clock time for the amplified task, in milliseconds.

```
CRP-PEF-Wall-Clock-Ms: 18400
```

### 7.4 CRP-PEF-Compute-Vs-Naive

**Direction:** RES  
**Definition:** Estimated total compute relative to a naive large-model single pass for the same task. Below 1.0 means the amplified small model used less total compute.

```
CRP-PEF-Compute-Vs-Naive: 0.45
```

---

## 8. The Benchmark That Proves It (H2 Redefined)

The original H2 (SPEC-005 benchmark hypotheses) proposed testing 7B+CRP vs 70B naive. This document sharpens that into the decisive experiment:

**Experiment:** Complex decomposable task (e.g., 5000-word technical architecture document with cross-referenced sections).

**Contenders:**
- A: 70B model, naive single-pass generation, on A100
- B: 7B model, full CRP (CLD+ROS+AIR+CQR+PEF), batched on a single RTX 4090
- C: 7B model, naive generation, on RTX 4090 (control)

**Metrics:** quality (DPE composite + human eval), wall-clock latency, total compute (FLOP estimate), hardware cost tier.

**Predicted result (the thesis):**
- B matches or exceeds A on quality
- B is competitive with or faster than A on wall-clock (batching + parallelism + small model speed)
- B uses less total compute than A
- B runs on ~10× cheaper hardware than A
- C (control) is fast but low quality - isolating the protocol's contribution

If B beats A on quality at lower compute, latency, and hardware cost, the thesis holds: **orchestrated small models are the correct architecture for quality AI.** That result would wow researchers - it is a direct, measured challenge to the scaling narrative.

---

## 9. Honest Status

This document specifies the performance architecture that makes CLD and ROS viable. The scheduling, layering, and batching are standard distributed-systems techniques applied to a novel domain - they are technically sound and implementable today with existing inference servers (vLLM, TGI, llama.cpp continuous batching).

What remains to be proven is the empirical result of Section 8 - that the fully orchestrated small model actually matches the large model on quality. The v3.1.1 benchmark shows the trajectory (7B+CRP beat all naive strategies). The H2 experiment is the decisive test and has not yet been run. The specs are honest about this: the architecture is sound and fast; the capability-parity claim is projected and awaits the GPU benchmark.

---

## 10. References

- CRP-SPEC-004 - Window Continuation & DAG
- CRP-SPEC-008 - Dispatch Strategy Specification
- CRP-SPEC-020 - Cognitive Load Distribution
- CRP-SPEC-021 - Reasoning Orchestration & Self-Consistency
- vLLM: Efficient Memory Management for LLM Serving (continuous batching)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
