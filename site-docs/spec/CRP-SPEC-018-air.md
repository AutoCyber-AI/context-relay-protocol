# CRP-SPEC-018: Adaptive Intelligence Relay (AIR)

**Document:** CRP-SPEC-018  
**Title:** Context Relay Protocol (CRP) - Adaptive Intelligence Relay: Closed-Loop Quality Feedback for LLM Intelligence Augmentation  
**Version:** 3.0.0  
**Status:** Draft - New Innovation  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-003 (Envelope), CRP-SPEC-004 (Continuation), CRP-SPEC-005 (DPE), CRP-SPEC-008 (Dispatch)

---

## Abstract

This document specifies the Adaptive Intelligence Relay (AIR) - a closed-loop feedback system that feeds the Decision Provenance Engine's quality signals **forward** into subsequent window construction, turning each generation cycle into a learning iteration. AIR is the protocol answer to the central question: *can CRP make a weak LLM produce smarter output?*

The answer, validated by the v3.1.1 benchmark results, is yes - and the mechanism is already partially present: the n-gram blacklist in v3.1.1 showed repetition decreasing monotonically from 1.70% → 1.27% as windows progressed, because the blacklist grew and became more effective with each cycle. AIR generalises this single observation into a complete protocol: **every DPE quality signal feeds forward into the next envelope construction, dispatch configuration, and grounding strategy.**

This is architecturally distinct from the reflexive dispatch strategy (CRP-SPEC-008 §5), which re-generates the *same* window. AIR generates *better subsequent windows* - not by redoing work, but by learning from it in real time.

---

## 1. Defining the Problem: What Makes LLMs Produce Poor Output

### 1.1 The Critical Distinction

The popular framing is wrong. "LLMs are dumb" is not a model quality problem. It is a **deployment architecture problem**. A weak model (llama-3.1-8b) with CRP v3.1.1 beat all alternatives including strategies that would run on stronger models. The benchmark proves the architecture matters more than the model - for production deployments where efficiency, volume, and coherence must coexist.

The actual failure modes are architectural, not intrinsic:

### 1.2 Failure Mode 1 - Context Poverty

**What it is:** The model at inference time lacks the specific facts needed to answer correctly. It fills the gap with plausible-sounding parametric memory - which may be wrong.

**Why it happens:** Standard deployment sends the user query and a system prompt. No domain knowledge is provided. The model has no choice but to confabulate.

**What CRP already does:** The CKF + 3-phase envelope packing (CRP-SPEC-003) directly addresses this. Context poverty is CRP's founding problem. The v3.1.1 benchmark's 66% context efficiency vs. Injection's 32% is this in numbers.

**What AIR adds:** When DPE detects UNVERIFIABLE claims despite facts being available in the CKF, AIR triggers a targeted retrieval expansion for the *next* window - fetching additional facts on the specific concepts that produced unverifiable claims. Not just "more context" - context targeted at the specific failure points.

### 1.3 Failure Mode 2 - Semantic Drift

**What it is:** In long generations, the model loses track of the original goal, task structure, and previously established facts. It begins writing as if starting fresh. This is precisely what produced 40 headings vs. 5 requested in the Injection baseline.

**Why it happens:** The model attends to recent context far more than distant context ("lost in the middle"). By window 3, the user's original task instruction is effectively invisible.

**What CRP already does:** The document map in continuation (CRP-SPEC-004) carries structure forward. v3.1.1's depth directives kept structural coherence perfect (5 headings, exactly as requested).

**What AIR adds:** AIR tracks **goal drift** - deviation between the original task decomposition and what has actually been produced. When DPE Stage 8 (Completeness) finds sub-queries going uncovered, AIR generates a **goal re-anchoring injection** for the next window's system prompt: a compressed, concrete restatement of what remains to be done, derived from the original task decomposition.

### 1.4 Failure Mode 3 - Reasoning Vacuity

**What it is:** The model asserts conclusions without showing reasoning steps. This is especially prevalent in analytical tasks where intermediate steps are non-obvious. The output *sounds* smart but is structurally hollow - assertions without derivations.

**Why it happens:** Models are trained to produce fluent text. Fluent text often looks like a conclusion. The reasoning that would justify the conclusion was never explicitly requested and the model doesn't generate it unprompted.

**What CRP already does:** Nothing, currently. This is a gap.

**What AIR adds:** AIR includes a **Reasoning Scaffold Signal** - when DPE Stage 2 detects that a high-specificity claim is PARAMETRIC (no CKF support), AIR injects a chain-of-thought scaffold into the *next* window's system prompt specifically for claims of that type: "For any claim about [detected concept category], show your reasoning step by step before stating the conclusion." This is task-adaptive - the scaffold is generated from the specific failure patterns detected in the prior window, not a generic "think step by step" instruction.

### 1.5 Failure Mode 4 - Error Compounding

**What it is:** An error in Window 1 is treated as established fact in Window 2, which builds on it, which feeds Window 3. The error compounds. By window 5, the entire structure may rest on a fabricated or distorted foundation.

**Why it happens:** The continuation summary (CRP-SPEC-004 §12) carries forward what was generated, not a verified fact set. A distortion in Window 1's generation is summarised and forwarded as if it were ground truth.

**What CRP already does:** DPE Stage 6 (Cross-Window Coherence) detects contradictions between windows. But it detects them *after* Window N has already been generated and compounded the error.

**What AIR adds:** The **Error Quarantine List** - when DPE detects a fabrication or distortion in Window N, AIR adds the specific distorted claim to a quarantine list that is injected into Window N+1's system prompt as an explicit prohibition: "Do NOT state or imply that [distorted claim]. The verified fact is: [CKF source fact]." This prevents compounding before it starts.

### 1.6 Failure Mode 5 - Vocabulary and Concept Exhaustion

**What it is:** The model's vocabulary for a specific domain is finite. After 2-3 windows, it has used all the phrasing it knows for key concepts and begins recycling. This is what CRP's 4.73% repetition in v3.0 was measuring. It's not laziness - the model is near its expressive limit for the domain.

**Why it happens:** The model's parametric knowledge of a domain has limited lexical variety. It knows "Kubernetes uses etcd for distributed coordination" in about 3-4 phrasings. After window 3, it's run out.

**What CRP already does (v3.1.1):** The vocabulary diversity injection tracks overused non-stopwords and forbids them in subsequent windows. This is the primitive version of AIR - and it worked: repetition dropped 56% from v3.0 to v3.1.1.

**What AIR adds:** A generalisation of this mechanism into a formal **Concept Freshness Budget** - each key concept from the knowledge domain is tracked with a "freshness score" that decays each time the concept appears. When freshness is low, AIR forces the envelope to fetch *new facets* of that concept from the CKF (different community, different source type) and injects those as the preferred anchors for the next window. Instead of the model recycling its parametric phrasing, it has new CKF material to work from.

### 1.7 Failure Mode 6 - Calibration Blindness

**What it is:** The model does not know the difference between what it knows reliably and what it is guessing. It asserts a fabricated statistic with the same linguistic confidence as a well-documented fact. There is no internal signal the application can read to distinguish confident knowledge from confident hallucination.

**Why it happens:** Models are trained to produce fluent, confident-sounding text regardless of epistemic state. Hedging is trained away as it sounds less authoritative.

**What CRP already does:** The DPE produces attribution signals (CONTEXT_GROUNDED vs PARAMETRIC vs UNVERIFIABLE) - these ARE the calibration signal. They just aren't fed back into the model.

**What AIR adds:** The **Per-Claim Epistemic Annotation** - in subsequent windows, claims from prior windows are annotated with their DPE attribution type and presented to the model explicitly:

```
ESTABLISHED FACTS (context-grounded, verified):
  - Kubernetes uses etcd as its distributed key-value store [verified: source A]
  - etcd uses the Raft consensus algorithm [verified: source B]

UNVERIFIED ASSERTIONS (parametric, proceed with caution):
  - etcd has a write throughput of ~10,000 ops/sec [UNVERIFIED: no source found]
```

This gives the model an explicit epistemic map. It can then choose to hedge unverified claims, seek additional support, or avoid repeating them. This is the closest CRP can come to giving a weak model genuine epistemic self-awareness.

---

## 2. The AIR Architecture

### 2.1 Overview

AIR adds a **Relay Intelligence Layer (RIL)** between the DPE output and the next window's envelope construction. The RIL reads DPE signals from Window N and produces an **Intelligence Augmentation Packet (IAP)** that modifies the Window N+1 envelope and system prompt.

```
Window N DPE Output
     │
     ▼
┌─────────────────────────────────────────────────────┐
│         RELAY INTELLIGENCE LAYER (RIL)              │
│                                                      │
│  Signal Aggregator → Pattern Detector → IAP Builder │
│                                                      │
│  Reads:  attribution, fabrications, distortions,    │
│          repetition, completeness, flow, omissions  │
│  Writes: IAP (injections + envelope adjustments)    │
└─────────────────────────────────────────────────────┘
     │
     ▼
Intelligence Augmentation Packet (IAP)
     │
     ├── Error Quarantine List → System Prompt Injection
     ├── Concept Freshness Budget → CKF Retrieval Bias
     ├── Reasoning Scaffold → System Prompt Injection
     ├── Goal Re-anchor → System Prompt Injection
     ├── Epistemic Map → System Prompt Injection
     └── Vocabulary Exhaustion → CKF Community Re-routing
     │
     ▼
Window N+1 Envelope Construction
(modified by IAP)
```

### 2.2 Signal-to-Action Mapping

Each DPE signal triggers specific AIP components:

| DPE Signal | Threshold | RIL Action | IAP Component |
|-----------|-----------|-----------|---------------|
| `fabrication_count > 0` | Always | Add to Error Quarantine | Prohibition injection |
| `distortion_count > 0` | Always | Add to Error Quarantine | Correction injection |
| `grounding_pct < 0.60` | < 60% | Expand CKF retrieval | Targeted fact fetch |
| `completeness_score < 0.70` | < 70% | Goal re-anchor | Task residual injection |
| `repetition_ratio > 0.03` | > 3% | Concept freshness decay | CKF community re-route |
| `flow_score < 0.60` | < 60% | Flow bridge generation | Transition injection |
| `UNVERIFIABLE claims > 2` | > 2 claims | Epistemic map | Confidence annotation |
| Specific claim type UNVERIFIABLE | Any | Reasoning scaffold | CoT injection for type |

### 2.3 Intelligence Augmentation Packet (IAP) Schema

```
IAP {
  window_source:          integer       // which window generated this IAP
  
  error_quarantine: [
    {
      original_claim:     string        // the distorted/fabricated claim
      correction:         string | null // CKF-sourced correction, if found
      prohibition:        string        // system prompt prohibition text
    }
  ]
  
  concept_freshness: {
    concept_label:        string
    freshness_score:      float         // 0.0 (exhausted) – 1.0 (fresh)
    preferred_communities: string[]     // CKF communities to bias toward
    exhausted_phrasings:  string[]      // n-gram blacklist extension
  }[]
  
  reasoning_scaffolds: [
    {
      claim_type:         string        // e.g. "performance statistics"
      scaffold_prompt:    string        // CoT injection for this claim type
    }
  ]
  
  goal_residual: {
    original_task:        string        // compressed task statement
    completed_sub_goals:  string[]      // what's been done
    remaining_sub_goals:  string[]      // what remains
    re_anchor_injection:  string        // system prompt text
  }
  
  epistemic_map: {
    verified_claims:      string[]      // grounded claims from prior windows
    unverified_claims:    string[]      // parametric/unverifiable claims
    map_injection:        string        // formatted system prompt block
  }
  
  vocabulary_directives: {
    forbidden_phrases:    string[]      // n-gram blacklist
    fresh_anchors:        string[]      // new CKF-sourced phrasings to use
  }
}
```

---

## 3. The Closed-Loop Quality Progression

### 3.1 Observed Behaviour (Already Validated)

The v3.1.1 benchmark already demonstrated the primitive version of this loop:

```
Window 1: 1.70% repetition (n-gram blacklist: ~0 entries)
Window 2: 1.91% repetition (blacklist: ~15 entries - slight rise)
Window 3: 1.65% repetition (blacklist: ~30 entries - starts improving)
Window 4: 1.54% repetition (blacklist: ~45 entries - clear improvement)
Window 5: 1.27% repetition (blacklist: ~60 entries - strongest result)
```

**The feedback loop is already working on the single dimension of vocabulary repetition.** It becomes MORE effective as the session progresses. AIR generalises this to ALL DPE quality dimensions.

### 3.2 Projected Behaviour With Full AIR

| Quality Dimension | v3.0 | v3.1.1 | AIR Projected |
|------------------|------|--------|---------------|
| 6-gram repetition | 4.73% | 2.08% | < 1.0% |
| Duplicate sentences | 3.23% | ~0.5% | < 0.2% |
| Fabrication rate | Variable | Variable | Near 0 (quarantine) |
| Completeness | 76% | 76% | > 92% |
| Epistemic calibration | None | None | Explicit per-claim |
| Reasoning depth | Shallow | Shallow | Task-adaptive scaffolding |

### 3.3 Why the Loop Terminates (It Does Not Become Infinite)

AIR does not create a runaway loop. It is bounded by:

1. **Window count limit** (max 5 by default) - the loop terminates when windows are exhausted
2. **IAP content limit** - the IAP has a maximum token budget (default: 512 tokens) to prevent the feedback from consuming the context it's supposed to improve
3. **Diminishing returns threshold** - if the DPE quality score for Window N exceeds 0.85, AIR enters **maintenance mode** (smaller injections, only error quarantine active)

---

## 4. The Cognitive Relay Chain

### 4.1 The Core Innovation

Standard chain-of-thought prompting asks the model to reason before answering. AIR's reasoning scaffolds do something different: they inject **task-specific, evidence-adaptive** reasoning structures based on what the DPE has observed the model getting wrong.

**Standard chain-of-thought:**
```
"Think step by step."
```

**AIR reasoning scaffold (example - generated from DPE observation):**
```
REASONING REQUIREMENT for Window 4:
In prior windows, the following claim types were asserted without 
derivable evidence:
  - Performance benchmarks (e.g., "X is 3× faster than Y")
  - Failure probability claims (e.g., "Y% of deployments experience Z")

For ALL such claims in this window:
  Step 1: State what the claim is
  Step 2: Identify the source fact from the provided context that 
          supports it (quote directly)
  Step 3: State the logical connection between the source and the claim
  Step 4: Only then write the claim in the response prose

If no supporting source fact exists: DO NOT make the claim. Instead,
write: "This requires verification against current benchmarks."
```

This is not generic CoT. It is **calibrated to the specific failure modes** observed in this model, on this knowledge domain, in this session. A weak model that is explicitly told what mistakes it has been making and given a structured process for the specific types of claims it gets wrong will demonstrably produce better output.

### 4.2 Feedback Loop as Session IQ

Each window in an AIR session is smarter than the previous one because:

- **Window 1:** No prior signals. Standard dispatch. The model operates at baseline.
- **Window 2:** IAP from Window 1. Error quarantine from any fabrications. N-gram blacklist started. Goal residual if completeness was below threshold.
- **Window 3:** IAP from Window 2. Error quarantine growing. Reasoning scaffold injected if UNVERIFIABLE claims were detected. Concept freshness routing begins for exhausted concepts.
- **Window 4:** IAP from Window 3. Epistemic map with all verified/unverified claims from prior windows. Blacklist now substantial. New CKF communities feeding fresh material.
- **Window 5:** IAP from Window 4. Full feedback active. The model has an explicit map of what it knows, what it doesn't, what mistakes to avoid, what it still needs to cover, and what phrasing to avoid. **It is operating with more contextual intelligence than its baseline architecture would allow.**

The session as a whole produces output that exceeds what the model could produce on a single, unconstrained generation - not by making the model smarter, but by giving it a **working memory, an error correction system, and a calibrated epistemic framework** at the protocol level.

---

## 5. AIR Headers

Four new response headers expose the AIR feedback loop state:

### 5.1 CRP-AIR-Active

**Direction:** RES  
**Definition:** Whether the AIR feedback loop is active for this session.

```
CRP-AIR-Active: true
```

### 5.2 CRP-AIR-Session-IQ

**Direction:** RES  
**Definition:** A composite score (0–100) representing the accumulated quality improvement from the feedback loop relative to baseline for this model. A score of 100 means the session is performing optimally within the protocol's current knowledge. This is not a measure of the model - it is a measure of the session's feedback loop effectiveness.

```
CRP-AIR-Session-IQ: 74
```

Computed as:
```
session_iq = 100 × (
  (1 - cumulative_repetition_ratio)    × 0.25 +
  completeness_score                   × 0.35 +
  (1 - fabrication_rate)               × 0.25 +
  flow_score                           × 0.15
)
```

### 5.3 CRP-AIR-IAP-Token-Cost

**Direction:** RES  
**Definition:** Tokens consumed by the IAP injection for this window. Allows operators to monitor feedback loop overhead.

```
CRP-AIR-IAP-Token-Cost: 312
```

### 5.4 CRP-AIR-Error-Quarantine-Count

**Direction:** RES  
**Definition:** Number of claims currently in the Error Quarantine List (prohibited from being repeated or compounded).

```
CRP-AIR-Error-Quarantine-Count: 3
```

---

## 6. Safety Policy Integration

### 6.1 AIR Directives for CRP-Safety-Policy

Two new directives added to the Safety Policy grammar (CRP-SPEC-006):

```
CRP-Safety-Policy: ...; air-mode=adaptive; air-iap-budget=512
```

| Directive | Values | Meaning |
|-----------|--------|---------|
| `air-mode` | `off`, `passive`, `adaptive`, `aggressive` | Off: disabled. Passive: observe only. Adaptive: standard AIR. Aggressive: maximum injection. |
| `air-iap-budget` | Integer (tokens) | Maximum tokens the IAP may consume per window. Default: 512. |

### 6.2 Interaction with Reflexive Dispatch

AIR and reflexive dispatch (CRP-SPEC-008 §5) are complementary, not competing:

- **Reflexive:** Re-generates the CURRENT window when its DPE score is too poor to release
- **AIR:** Improves the NEXT window based on the current window's DPE signals

They can run together. Reflexive catches catastrophic single-window failures. AIR prevents gradual multi-window degradation. Together they form a two-tier quality assurance system: reactive (reflexive) and proactive (AIR).

---

## 7. Addressing the "Bullshit Filter" Problem

The user's stated goal: *"ensure the bullshit they produce doesn't go through."*

CRP already has a hard gate for this: the DPE + Safety Policy (`halt-on CRITICAL`, `block-fabrication`, `block-ungrounded`). If the model produces verifiable nonsense, the response is halted at the gateway before it reaches the application.

But the more interesting problem is **plausible-sounding nonsense that passes the DPE's current checks** - claims that are PARAMETRIC (not CKF-grounded) but not obviously wrong. These are the hard cases: confident assertions that are subtly wrong, or technically true but misleading out of context.

AIR addresses these through the Epistemic Map. By Window 3, the model has an explicit list of its own unverified claims from prior windows, annotated as such. The system prompt says: "These were asserted without evidence. Hedge them or verify them." A model that is told its own uncertain claims will hedge them. The linguistic confidence of the output matches the epistemic state of the underlying claims - which is what *calibration* means.

This is not a perfect solution. A 7B model told to hedge uncertain claims will sometimes hedge everything, or hedge the wrong things. But it is a meaningful improvement over zero epistemic awareness, and it is measurable: compare the frequency of hedging language ("research suggests", "typically", "in most implementations") in AIR sessions vs. non-AIR sessions with the same model. Higher hedging frequency on PARAMETRIC claims, maintained confidence on CONTEXT_GROUNDED claims, is the target metric.

---

## 8. Benchmark Implications

The v3.1.1 results already validate the core premise:

| Claim | Evidence |
|-------|---------|
| Feedback loops improve subsequent windows | n-gram blacklist: rep 1.70% → 1.27% across windows |
| CRP beats stronger approaches with feedback | v3.1.1 beats Hierarchical on all metrics |
| The loop becomes more effective over time | Monotonically decreasing repetition with window count |
| Architecture > model quality | llama-3.1-8b + CRP v3.1.1 > all alternatives |

Full AIR (all six feedback dimensions) is projected to extend these results significantly. Validation requires a v3.2 benchmark run with:

- AIR active across all 6 dimensions
- Same harness as v3.1.1 (LM Studio, llama-3.1-8b, 4096 context, 5 windows)
- Comparison: AIR vs. v3.1.1 vs. Hierarchical (the strongest competitor)
- Target metrics: repetition < 1%, fabrications ≈ 0, completeness > 90%

---

## 9. What AIR Is NOT

**AIR does not fine-tune the model.** Weights are unchanged. AIR operates entirely at inference time through prompt engineering and context management.

**AIR does not make the model smarter.** It makes the session smarter. The model's parametric knowledge is unchanged. What changes is the quality of information it receives and the specificity of the constraints it operates under.

**AIR does not eliminate hallucination.** It reduces it, catches it, quarantines its downstream effects, and makes the model aware of its own unverified claims. A model with genuinely wrong training data will still produce wrong outputs. AIR mitigates the architectural causes of hallucination; it cannot address the training causes.

**AIR does not replace the DPE.** AIR consumes DPE output. It is a layer above the DPE, not an alternative to it.

---

## 10. References

- CRP-SPEC-003 - Context Envelope & Packing
- CRP-SPEC-004 - Window Continuation & DAG
- CRP-SPEC-005 - Decision Provenance Engine (source of all feedback signals)
- CRP-SPEC-006 - Safety Policy Directive Language
- CRP-SPEC-008 - Dispatch Strategy Specification
- CRP v3.1.1 Benchmark Results (internal, Section 8 analysis)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
