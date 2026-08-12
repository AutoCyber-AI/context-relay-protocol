# CRP-SPEC-021: Reasoning Orchestration & Self-Consistency (ROS)

**Document:** CRP-SPEC-021  
**Title:** Context Relay Protocol (CRP) — Reasoning Orchestration & Self-Consistency: Protocol-Level Reliability Amplification  
**Version:** 3.0.0  
**Status:** Draft — Frontier Innovation  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-005, CRP-SPEC-008, CRP-SPEC-018, CRP-SPEC-020

---

## Abstract

This document specifies Reasoning Orchestration & Self-Consistency (ROS) — the protocol mechanism that amplifies the *reliability* of a sub-scale model's output to approach that of a larger model. Where CLD (SPEC-020) addresses capability (can the model do the task), ROS addresses consistency (does the model do it reliably).

A larger model is more self-consistent per single pass — ask it the same hard question twice and you get more reliably correct answers. A smaller model has higher variance: sometimes right, sometimes wrong, on the same input. ROS closes this gap by orchestrating multiple model passes and reconciling them through consensus, debate, and verification — so that the protocol-level output reliability of a 7B model approaches the single-pass reliability of a 70B model.

This is the final piece of the capability amplification stack: CLD makes the model *able*, AIR/CQR make it *less wrong*, and ROS makes it *reliable*.

---

## 1. The Reliability Gap

### 1.1 What Self-Consistency Means

Self-consistency is the property that a model gives the same (correct) answer when asked the same question multiple times, or via slightly different phrasings. A highly self-consistent model has low variance — its outputs cluster tightly around the correct answer. A model with poor self-consistency has high variance — its outputs scatter, sometimes landing on correct answers and sometimes on plausible-but-wrong ones.

Larger models are generally more self-consistent on reasoning tasks. A smaller model, on a hard reasoning step, might be correct 60% of the time and wrong 40% — high variance.

### 1.2 The Key Statistical Insight

If a 7B model is correct 60% of the time on a reasoning step, a single pass is unreliable. But if you run the step independently multiple times and take the majority answer, reliability climbs sharply:

```
Single pass:        60% reliable
3 passes, majority:  ~68% reliable
5 passes, majority:  ~73% reliable
7 passes, majority:  ~77% reliable
```

(Assuming errors are independent and scattered — which holds when temperature is non-zero and the model's errors are not systematic.)

And if the multiple passes are not just voted but *reconciled* — each pass critiques the others, disagreements are resolved by re-examination against evidence — reliability climbs further, because systematic errors (where the model is consistently wrong the same way) get surfaced when one pass produces a different answer and the reconciliation examines why.

### 1.3 The ROS Thesis

A smaller model, orchestrated to produce multiple independent reasoning passes that are then reconciled through consensus and evidence-grounded debate, achieves output reliability approaching a larger model's single-pass reliability — at the cost of more inference time, which is acceptable for tasks where correctness matters more than latency.

---

## 2. The Three Orchestration Modes

ROS defines three reliability-amplification modes, selected based on the criticality of the reasoning step (as flagged by CLD complexity rating or Safety Policy).

### 2.1 Mode 1 — Consensus Voting (fastest)

For micro-tasks with a discrete or constrained answer space (a decision, a classification, a specific value):

1. Execute the micro-task N times (default N=3) with temperature > 0 for variance
2. Cluster the N outputs by semantic equivalence
3. Select the majority cluster as the answer
4. Record agreement ratio (e.g., 3/3 = high confidence, 2/3 = moderate)

If agreement is unanimous, confidence is high. If split, escalate to Mode 2.

### 2.2 Mode 2 — Evidence-Grounded Debate (balanced)

For micro-tasks where consensus voting split, or where reasoning quality matters:

1. Take the divergent answers from the consensus pass (e.g., Answer A and Answer B)
2. Construct a debate prompt: "Two analyses reached different conclusions. Analysis 1 concluded [A]. Analysis 2 concluded [B]. Using ONLY the provided evidence [CKF facts], determine which is better supported and why. Cite the specific evidence."
3. The model adjudicates against evidence, not against its own prior
4. The DPE verifies the adjudication's grounding
5. The evidence-grounded answer wins

This surfaces systematic errors: if the model was confidently wrong in the same way across passes, forcing it to adjudicate against external evidence (rather than its internal prior) breaks the systematic bias.

### 2.3 Mode 3 — Decompose-and-Verify (most rigorous)

For CRITICAL micro-tasks (flagged by Safety Policy or high stakes):

1. The reasoning step is itself decomposed (via CLD) into its logical premises
2. Each premise is independently verified against CKF evidence
3. The conclusion is checked to follow from the verified premises
4. If any premise is unverifiable, the conclusion is flagged as resting on unverified ground

This is the most expensive mode but produces the highest reliability — it converts a single reasoning leap into a verifiable chain of grounded premises.

---

## 3. Reliability Mode Selection

```
Micro-task complexity / criticality
     │
     ├── TRIVIAL/SIMPLE, low stakes → single pass (no ROS)
     │
     ├── MODERATE, normal stakes → Mode 1 (consensus voting, N=3)
     │
     ├── MODERATE, high stakes → Mode 2 (evidence debate)
     │
     └── CRITICAL (any complexity) → Mode 3 (decompose-and-verify)
```

Criticality is determined by:
- Safety Policy `require-grounding` threshold (higher = more ROS)
- EU AI Act classification (HIGH-risk systems get more ROS)
- Explicit `CRP-Reliability-Mode` request header
- CLD complexity rating of the micro-task

---

## 4. The Variance-Reduction Mechanism

### 4.1 Why Independent Passes Matter

For consensus to improve reliability, the passes must be genuinely independent — their errors must not be correlated. ROS ensures independence by:

1. **Temperature variation:** Each pass uses a different temperature (e.g., 0.3, 0.6, 0.9) so the model explores different reasoning paths
2. **Phrasing variation:** Each pass receives the micro-task instruction phrased differently (the protocol generates paraphrases) so the model is not anchored to one framing
3. **Order variation:** When evidence is presented, the order is shuffled across passes so position bias doesn't correlate errors

These ensure the N passes are diverse samples, not N copies of the same systematic error.

### 4.2 Detecting Systematic Error

If all N passes agree but the answer is wrong, consensus voting cannot catch it — this is systematic error (the model is reliably wrong). ROS detects suspected systematic error when:

- Consensus is unanimous AND
- The answer is PARAMETRIC (not CKF-grounded) AND
- The claim is high-specificity (a precise number, name, or fact)

In this case, even unanimous consensus is treated with suspicion and escalated to Mode 2 (evidence debate) or flagged in the Epistemic Map (AIR §1.7) as "high-confidence but unverified — possible systematic error."

This is the honest guard against the failure mode where a small model is confidently, consistently wrong.

---

## 5. ROS Headers

### 5.1 CRP-ROS-Mode

**Direction:** RES  
**Definition:** The reliability mode applied to this task (or the most rigorous mode applied to any micro-task within it).

```
CRP-ROS-Mode: consensus-voting
CRP-ROS-Mode: evidence-debate
CRP-ROS-Mode: decompose-and-verify
```

### 5.2 CRP-ROS-Agreement

**Direction:** RES  
**Definition:** The consensus agreement ratio for the most critical reasoning step.

```
CRP-ROS-Agreement: 3/3
CRP-ROS-Agreement: 2/3
```

### 5.3 CRP-ROS-Passes

**Direction:** RES  
**Definition:** Total number of model passes executed for reliability amplification across the task.

```
CRP-ROS-Passes: 7
```

### 5.4 CRP-ROS-Systematic-Error-Flags

**Direction:** RES  
**Definition:** Count of reasoning steps flagged as suspected systematic error (unanimous but unverified high-specificity claims).

```
CRP-ROS-Systematic-Error-Flags: 1
```

### 5.5 CRP-Reliability-Mode (request)

**Direction:** REQ  
**Definition:** Client-requested minimum reliability mode.

```
CRP-Reliability-Mode: evidence-debate
```

---

## 6. The Complete Capability Amplification Stack

With ROS, CRP's capability amplification is complete. The full stack:

```
┌──────────────────────────────────────────────────────────────┐
│  CLD (SPEC-020) — CAPABILITY                                  │
│  Makes the model ABLE to do complex tasks                     │
│  by distributing cognitive load: decompose, plan, track,      │
│  execute, verify, compose                                     │
├──────────────────────────────────────────────────────────────┤
│  ROS (SPEC-021) — RELIABILITY                                 │
│  Makes the model's output RELIABLE                            │
│  by orchestrating multiple passes: consensus, debate, verify  │
├──────────────────────────────────────────────────────────────┤
│  AIR (SPEC-018) — LEARNING                                    │
│  Makes the session SMARTER over time                          │
│  by feeding quality signals forward into each window          │
├──────────────────────────────────────────────────────────────┤
│  CQR (SPEC-019) — CORRECTNESS                                 │
│  Makes the model LESS WRONG                                   │
│  by detecting and interrupting the six failure-mode cascade   │
├──────────────────────────────────────────────────────────────┤
│  DPE (SPEC-005) — VERIFICATION                                │
│  Makes every output MEASURABLE                                │
│  via the 13-stage analysis pipeline                           │
├──────────────────────────────────────────────────────────────┤
│  CKF + Envelope (SPEC-003/009) — KNOWLEDGE                    │
│  Makes the model INFORMED                                     │
│  by supplying external, verified context                      │
└──────────────────────────────────────────────────────────────┘
```

### 6.1 The Complete Thesis

A small model is weak in six ways: it knows less (knowledge), it loses track (working memory), it can't hold long reasoning (depth), it overloads on complex tasks (capacity), it's inconsistent (reliability), and it's wrong in confident ways (correctness).

CRP addresses every one of these at the protocol level:
- **Knowledge** → CKF supplies it
- **Working memory** → CLD externalises it into the protocol
- **Reasoning depth** → CLD decomposes it into atomic steps
- **Capacity** → CLD distributes the cognitive load
- **Reliability** → ROS orchestrates multiple passes to consensus
- **Correctness** → CQR detects and interrupts failure modes; AIR feeds corrections forward

What remains genuinely model-bound: emergent capabilities that don't decompose, and atomic reasoning steps beyond the model's floor. For these, CRP routes to tools rather than pretending the model can do them.

**Everything else — the vast majority of what makes a 70B "better" than a 7B on real tasks — is architectural, and CRP supplies the architecture.**

---

## 7. Honest Limits and Cost

### 7.1 The Latency Trade-off

ROS multiplies inference passes. A Mode 1 task is 3× the inference of a single pass. Mode 3 can be 5–10×. This is acceptable for:
- High-stakes tasks (medical, legal, financial) where correctness dominates
- Asynchronous/batch generation where latency is not user-facing
- Tasks where a small local model's per-pass cost is near-zero (local GPU)

It is NOT acceptable for:
- Real-time conversational latency-critical applications
- Tasks where the small model's per-pass speed advantage is the whole point

ROS is therefore mode-gated: low-stakes tasks skip it entirely, high-stakes tasks invoke it. The Safety Policy controls this.

### 7.2 The Honest Claim

The fully-amplified claim, stated precisely:

> A 7B local model, running CRP with CLD + ROS + AIR + CQR active, can match or exceed a 70B model's naive single-pass output on complex, decomposable, knowledge-grounded tasks — at the cost of higher total inference (more passes) and higher latency. For tasks requiring genuine emergent reasoning that does not decompose, the gap persists and CRP routes to deterministic tools.

This is testable, honest, and — based on the v3.1.1 benchmark trajectory — likely true for a large and commercially important class of tasks.

---

## 8. The Quantity-at-Quality Guarantee

A specific consequence of the full stack: **when more output is requested, more is delivered without quality loss.**

Naive generation degrades as length increases (the failure cascade compounds). CRP inverts this:

- More output requested → CLD decomposes into more micro-tasks
- Each micro-task is independently scoped, executed, and verified
- Quality is enforced per micro-task, so it does not degrade with total length
- AIR's feedback loop becomes MORE effective as more windows accumulate (validated: repetition dropped across windows in v3.1.1)
- ROS ensures each step is reliable regardless of position in the sequence

The result: a request for 10,000 words produces 10,000 words at the same per-section quality as a request for 1,000 words — because quality is enforced atomically, not globally. This is the formal guarantee that quantity and quality scale together rather than trading off.

---

## 9. References

- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-008 — Dispatch Strategy Specification
- CRP-SPEC-018 — Adaptive Intelligence Relay
- CRP-SPEC-020 — Cognitive Load Distribution

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
