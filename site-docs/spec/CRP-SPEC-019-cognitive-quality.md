# CRP-SPEC-019: Cognitive Quality Relay (CQR) & Reasoning Scaffold Protocol

**Document:** CRP-SPEC-019  
**Title:** Context Relay Protocol (CRP) - Cognitive Quality Relay: What Makes LLMs Produce Poor Output and the Protocol Mechanisms That Fix It  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-005 (DPE), CRP-SPEC-018 (AIR)

---

## Abstract

This document defines the problem of LLM intelligence failure at the deployment level - distinct from model capability - and specifies the Cognitive Quality Relay (CQR): protocol-level mechanisms that systematically address each failure class. Where CRP-SPEC-018 (AIR) defines the closed-loop feedback architecture, this document defines the cognitive failure taxonomy and the specific protocol response to each failure type. Together they form CRP's complete answer to the question: *how does a protocol make a weak model produce smarter output?*

---

## 1. The Cognitive Failure Taxonomy

### 1.1 Why This Taxonomy Matters

LLMs fail in specific, repeatable, architecturally-caused ways. Each failure type has a different root cause and requires a different protocol response. Treating "hallucination" as a single phenomenon is why most mitigation approaches are inadequate - they address one failure mode while ignoring others.

CQR defines six cognitive failure classes and maps each to specific protocol interventions:

---

### Class 1 - Factual Confabulation

**Definition:** The model asserts false or unverifiable specific facts - names, numbers, dates, citations - with the same linguistic confidence as verified facts.

**Root cause:** Language models are trained to produce fluent, coherent text. When a specific fact is needed and not available in context, the model fills the gap with a plausible-sounding value derived from patterns in training data. The model has no internal representation of "I don't know this specific fact."

**Benchmark evidence:** Injection strategy - 40 headings vs. 5 requested. The model "discovers" structural patterns from re-injected text and confabulates new sub-sections.

**What confabulation looks like in output:**
- Specific statistics without sources: "Kubernetes has a 99.95% availability SLA"
- Named authorities that don't exist: "According to the CNCF 2024 report..."
- Precise numbers that are plausible but wrong: "etcd supports up to 8,192 concurrent connections"

**Protocol Response (CQR-1):** Fabrication detection (DPE Stage 3a) + Error Quarantine (AIR §4) + `block-fabrication` directive. Detected fabrications are: (a) blocked if Safety Policy requires it, (b) quarantined from subsequent windows, (c) annotated in the Epistemic Map as UNVERIFIED.

---

### Class 2 - Source Distortion

**Definition:** The model references a real source fact but misrepresents it - changing a number, flipping a negation, dropping a qualifying condition. This is more dangerous than confabulation because the output looks grounded.

**Root cause:** The model performs approximate matching between its parametric summary of a fact and the specific instance in context. Small differences in the envelope's phrasing vs. the model's learned phrasing cause substitutions.

**Benchmark evidence:** DPE Stage 3b distortion types: NUMBER_CHANGED, NEGATION_FLIP, DATE_SHIFTED, ENTITY_SUBSTITUTED, MAGNITUDE_ALTERED, CONTEXT_STRIPPED.

**What distortion looks like in output:**
- "etcd uses a Raft-based eventual consistency model" (wrong: Raft provides strong consistency, not eventual consistency)
- "Kubernetes requires at least 8GB RAM per node" (envelope said 4GB minimum)

**Protocol Response (CQR-2):** Fidelity verification (DPE Stage 3b) with direct source comparison for numeric and named-entity claims. Distortions added to Error Quarantine with the **correction** prepended: "The correct fact is: [CKF source]. Do NOT write [distorted version]."

---

### Class 3 - Reasoning Vacuity

**Definition:** The model states conclusions without supporting reasoning. The output is coherent and confident but structurally hollow - conclusions without derivations.

**Root cause:** Reward models in RLHF training favour readable, confident text. Extended reasoning chains are often penalised as "verbose." The model learns to state conclusions concisely, stripping the reasoning that would make them verifiable.

**Benchmark evidence:** Not directly measured in the current benchmark but observable in the output quality of any analytical task. The model writes "etcd is preferred over other KV stores for Kubernetes because it provides strong consistency" without deriving WHY strong consistency matters for the specific use case of Kubernetes controller state.

**Protocol Response (CQR-3):** Reasoning Scaffold Injection (AIR §4.1). When DPE detects UNVERIFIABLE high-specificity claims of a particular type, CQR generates a targeted chain-of-thought scaffold for that claim type in the next window's system prompt. This is not generic CoT - it is specific to the failure mode observed.

---

### Class 4 - Structural Degeneration

**Definition:** The model's output structure diverges from the requested structure across windows. Sections multiply, headings nest unnecessarily, the originally-specified format is abandoned.

**Root cause:** Without a structural anchor in the context, the model treats each window as a new document. It "discovers" structure from the available context rather than maintaining the originally-specified structure.

**Benchmark evidence (most stark in this dataset):**
- CRP: 5 headings - perfect
- Injection: 40 headings - 8× structural degeneration
- RAG: 16 headings - 3.2× deviation
- Hierarchical: 18 headings - 3.6× deviation

**Why Injection degenerates to 40 headings:** The re-injected prior output contains section headers. The model reads those headers as "this is how documents in this domain are structured" and tries to match that density. Each window adds more headers. By window 5, the document is a tree of sub-sub-sections.

**Protocol Response (CQR-4):** Document Map (CRP-SPEC-004 §continuation) + Depth Directives (v3.1.1 improvement) + Goal Re-Anchor (AIR §3.3). The document map carries the structural contract forward. Depth directives specify exactly how many subsections to create. Goal re-anchoring re-states the remaining unfinished sections explicitly in each window.

---

### Class 5 - Semantic Repetition

**Definition:** The model re-states content already produced in prior windows, either verbatim or semantically equivalent. This wastes output tokens and degrades the value of the complete document.

**Root cause:** Without a memory of what has been written, the model re-derives the same conclusions from the available context. The n-gram patterns of "natural" prose in a given domain are finite; the model converges on them repeatedly.

**Benchmark evidence:**
- v3.0: 4.73% 6-gram repetition, 3.23% duplicate sentences - ranked 4th
- v3.1.1: 2.08% repetition - ranked 1st overall after feedback loop

**The key insight from v3.1.1's window progression:**
```
Window 1: 1.70% (blacklist empty - baseline)
Window 4: 1.54% (blacklist ~45 entries - improving)  
Window 5: 1.27% (blacklist ~60 entries - best)
```
The feedback loop becomes MORE effective as the session progresses. This is the core empirical validation of CQR.

**Protocol Response (CQR-5):** N-gram blacklist injection (v3.1.1) + Concept Freshness Budget (AIR §1.6) + DPE Stage 7 repetition detection. The blacklist grows with each window. The Concept Freshness Budget ensures new CKF material is fetched for exhausted concepts rather than recycling parametric phrasing.

---

### Class 6 - Epistemic Overconfidence

**Definition:** The model asserts both well-grounded and ungrounded claims with equivalent linguistic confidence. The reader has no way to distinguish reliable assertions from guesses.

**Root cause:** Training data contains confident text. Models learn to produce confident text. There is no reward signal during RLHF for appropriate hedging on uncertain claims.

**This is the hardest failure class because it is invisible.** The output looks identical whether the claim is grounded or fabricated. Only the DPE's attribution analysis can distinguish them.

**Protocol Response (CQR-6):** Epistemic Map (AIR §1.7). Verified claims and unverified claims from prior windows are presented to the model in the next window's context with explicit labels. The model is instructed to maintain confidence on verified claims and hedge or avoid unverified claims. 

The target is **epistemic calibration** - the linguistic confidence of the output matches the epistemic state of the underlying claims. This is measurable: compare hedging frequency (modals: "may", "typically", "suggests") on PARAMETRIC vs. CONTEXT_GROUNDED claims.

---

## 2. The CQR Cascade

CQR is not six separate mechanisms running in parallel. They cascade - each class of failure, if left unaddressed, enables or amplifies the next:

```
Class 1 (Confabulation)
  ↓ if unaddressed
Class 2 (Distortion) - harder to detect when confabulation is present
  ↓ if unaddressed  
Class 6 (Overconfidence) - reader cannot distinguish real from fabricated
  ↓ if unaddressed
Class 4 (Structural Degeneration) - model loses thread while generating 
                                    confident nonsense
  ↓ if unaddressed
Class 3 (Reasoning Vacuity) - by now, the model is just generating
                               plausible-sounding text
  ↓ if unaddressed
Class 5 (Repetition) - model has run out of coherent things to say
                        and recycles
```

**This is how bad AI output is produced:** Not one dramatic failure, but a cascade. CRP + AIR + CQR interrupt the cascade at every stage.

---

## 3. The Intelligence Augmentation Thesis

### 3.1 The Core Claim

A weak model with CQR is more useful than a strong model without it.

This is not a marketing claim. It is the logical consequence of the failure taxonomy:

1. If Class 1–6 failures are architecturally caused (deployment environment, not model weights), then fixing the architecture improves output regardless of model capability
2. A strong model still suffers from structural degeneration without a document map
3. A strong model still produces epistemic overconfidence without an epistemic map
4. A strong model still repeats concepts without a concept freshness budget
5. Fixing the architecture moves the output quality ceiling up - the gap between model capability and actual output quality narrows

The benchmark validates this: llama-3.1-8b (7B parameters, a weak model by 2026 standards) with CRP v3.1.1 beat Hierarchical summarisation - a quality-optimised strategy that would work on any model including GPT-4. The architecture beat the strategy.

### 3.2 Where Model Quality Still Matters

CQR cannot compensate for:

- **Training data gaps:** If the model has never seen a concept, the Reasoning Scaffold cannot help it reason about that concept correctly
- **Context window limits:** At 4096 tokens, even perfect IAP design is constrained. The IAP token budget (512 tokens) competes with the context budget
- **Fundamental reasoning failures:** Some tasks require multi-step mathematical or logical reasoning that small models cannot perform regardless of scaffolding

These are model-level limitations. CQR addresses deployment-level limitations. Both matter. The distinction is important for honest positioning.

### 3.3 The Practical Implication for CRP Positioning

The benchmark data, combined with CQR's failure taxonomy, supports a specific positioning claim:

> **"CRP v3 with AIR allows a 7B local model to produce output that competes with - and on production metrics beats - a 70B+ model using naive deployment."**

This is testable (H2 in the benchmark hypotheses). It is the central value proposition for CRP in an era where every company wants local AI (WASA AI's value proposition) but worries that local models are too weak.

CQR's answer: the model is not the bottleneck. The architecture is. Fix the architecture.

---

## 4. CQR Header

One new response header:

### 4.1 CRP-CQR-Class-Flags

**Direction:** RES  
**Definition:** Comma-separated list of cognitive failure classes detected in this window's DPE analysis.

**Syntax:**
```
CRP-CQR-Class-Flags = class-flag *( "," class-flag )
class-flag = "C1-CONFABULATION" / "C2-DISTORTION" / "C3-VACUITY" /
             "C4-DEGENERATION" / "C5-REPETITION" / "C6-OVERCONFIDENCE"
```

**Example:**
```
CRP-CQR-Class-Flags: C5-REPETITION, C6-OVERCONFIDENCE
```

This header allows consuming applications, monitoring dashboards, and CRP Visualise to surface the specific cognitive failure profile of each AI call - not just a composite risk score but the specific types of reasoning failures present.

---

## 5. References

- CRP-SPEC-005 - Decision Provenance Engine (signal sources)
- CRP-SPEC-018 - Adaptive Intelligence Relay (feedback loop)
- CRP v3.1.1 Benchmark Results (empirical validation)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
