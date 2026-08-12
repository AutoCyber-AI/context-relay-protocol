# CRP-SPEC-005: Decision Provenance Engine (DPE) Specification

**Document:** CRP-SPEC-005  
**Title:** Context Relay Protocol (CRP) — Decision Provenance Engine  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Repository:** https://github.com/crprotocol/spec  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope), CRP-SPEC-004 (Continuation)

---

## Abstract

This document specifies the Decision Provenance Engine (DPE) — CRP's post-generation analysis pipeline that runs after every LLM dispatch. The DPE performs claim segmentation, attribution analysis, fidelity verification, entailment scoring, fabrication detection, contradiction analysis, omission detection, and cross-window coherence verification. It produces the hallucination risk score, the provenance record, and the quality signals emitted as CRP response headers.

Critically, this document also specifies the **Response Quality Assurance (RQA) subsystem** — the mechanisms ensuring that multi-window responses are complete, non-redundant, coherently flowing, and stylistically consistent. The RQA is the layer that transforms a chain of independent LLM calls into what reads as a single, unified, high-quality response.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Stage 1: Claim Segmentation](#3-stage-1-claim-segmentation)
4. [Stage 2: Attribution Analysis](#4-stage-2-attribution-analysis)
5. [Stage 3: Fidelity Verification](#5-stage-3-fidelity-verification)
6. [Stage 4: Entailment Scoring](#6-stage-4-entailment-scoring)
7. [Stage 5: Risk Classification](#7-stage-5-risk-classification)
8. [Stage 6: Cross-Window Coherence](#8-stage-6-cross-window-coherence)
9. [Stage 7: Repetition Detection](#9-stage-7-repetition-detection)
10. [Stage 8: Completeness Verification](#10-stage-8-completeness-verification)
11. [Stage 9: Flow & Continuity Analysis](#11-stage-9-flow--continuity-analysis)
12. [Stage 10: Omission Detection](#12-stage-10-omission-detection)
13. [Stage 11: PII Detection](#13-stage-11-pii-detection)
14. [Stage 12: Regulatory Classification](#14-stage-12-regulatory-classification)
15. [Stage 13: Report Generation](#15-stage-13-report-generation)
16. [Composite Risk Scoring Algorithm](#16-composite-risk-scoring-algorithm)
17. [Regulatory Amplifiers](#17-regulatory-amplifiers)
18. [Response Quality Assurance (RQA)](#18-response-quality-assurance-rqa)
19. [Re-Dispatch Protocol](#19-re-dispatch-protocol)
20. [Header Outputs](#20-header-outputs)
21. [Security Considerations](#21-security-considerations)
22. [References](#22-references)

---

## 1. Introduction

### 1.1 The Problem: LLMs Produce Unverified Output

An LLM generates text that appears authoritative but carries no intrinsic guarantee of accuracy, completeness, or consistency. Without post-generation verification:

- Fabricated entities (names, dates, statistics) pass undetected
- Source facts are distorted (numbers changed, negations flipped)
- Responses contradict earlier windows in the same session
- Multi-window responses repeat content verbatim
- Continuation responses lack coherent flow — each window reads as an isolated answer
- Material omissions go undetected — the model silently ignores critical context

### 1.2 The DPE Solution

The DPE is a 13-stage pipeline that runs after every LLM dispatch and before the response is released to the client. It produces:

1. A per-claim provenance record (which claims are grounded, which are fabricated)
2. A composite hallucination risk score (0.0 – 1.0, classified as CRITICAL/HIGH/MEDIUM/LOW)
3. A quality assessment covering coherence, repetition, completeness, and flow
4. A regulatory classification mapping the output to EU AI Act, GDPR, and NIST controls
5. The HMAC audit record for this window

### 1.3 What's New in v3.0

CRP v3.0 introduces the **Response Quality Assurance (RQA)** subsystem — Stages 6 through 9. These stages specifically address the quality problems that emerge in multi-window continuation:

| Problem | Stage | What It Does |
|---------|-------|-------------|
| Cross-window contradictions | Stage 6 | Detects when Window N contradicts Window N-1 |
| Content repetition | Stage 7 | Detects when Window N repeats content from earlier windows |
| Incomplete answers | Stage 8 | Detects when the query was not fully answered across all windows |
| Incoherent flow | Stage 9 | Detects when Window N reads as a disjointed fragment rather than a continuation |

These stages transform CRP from a safety-verification protocol into a **quality-assurance protocol** — ensuring that what the user receives is not just safe but genuinely good.

---

## 2. Pipeline Architecture

```
LLM Response
     │
     ▼
┌──────────────────────────────────────────────────────┐
│  PROVENANCE STAGES (verify truthfulness)              │
│                                                        │
│  Stage 1: Claim Segmentation                          │
│  Stage 2: Attribution Analysis                        │
│  Stage 3: Fidelity Verification                       │
│       3a: Fabrication Detection                       │
│       3b: Distortion Detection                        │
│       3c: Contradiction Detection                     │
│  Stage 4: Entailment Scoring                          │
│  Stage 5: Risk Classification                         │
├──────────────────────────────────────────────────────┤
│  QUALITY STAGES (verify quality & coherence)          │
│  ★ NEW IN v3.0                                        │
│                                                        │
│  Stage 6: Cross-Window Coherence                      │
│  Stage 7: Repetition Detection                        │
│  Stage 8: Completeness Verification                   │
│  Stage 9: Flow & Continuity Analysis                  │
├──────────────────────────────────────────────────────┤
│  COMPLIANCE STAGES (classify & record)                │
│                                                        │
│  Stage 10: Omission Detection                         │
│  Stage 11: PII Detection                              │
│  Stage 12: Regulatory Classification                  │
│  Stage 13: Report Generation + HMAC                   │
└──────────────────────────────────────────────────────┘
     │
     ▼
CRP Response Headers + Audit Record
```

The pipeline is sequential. Each stage can trigger a **re-dispatch** if the computed risk or quality score exceeds the policy threshold and an `upgrade-on-risk` directive is set (see §19).

---

## 3. Stage 1: Claim Segmentation

### 3.1 Purpose

Decompose the LLM response into discrete factual claims for individual verification. A "claim" is an atomic assertion that can be independently evaluated as true or false.

### 3.2 Algorithm

**Input:** LLM response text  
**Output:** List of `Claim` objects

```
Claim {
  claim_id:       string      // Unique identifier
  text:           string      // The claim text
  sentence_index: integer     // Position in response (sentence number)
  claim_type:     enum        // FACTUAL | OPINION | PROCEDURAL | META
  specificity:    float       // 0.0 – 1.0 (how specific/verifiable)
  entities:       Entity[]    // Named entities within the claim
}
```

### 3.3 Claim Types

| Type | Definition | Verifiable? |
|------|-----------|------------|
| `FACTUAL` | Assertion about the world that can be checked against evidence | Yes |
| `OPINION` | Subjective evaluation or judgment | No — flagged, not scored |
| `PROCEDURAL` | Instruction or process description | Partially — against source procedures |
| `META` | Statement about the response itself ("As mentioned above...") | Used for coherence analysis |

### 3.4 Implementation

Claim segmentation uses an NLI-trained classifier to split sentences into atomic claims. Compound sentences ("X is true and Y happened in 2024") are decomposed into separate claims. The classifier is calibrated to over-segment rather than under-segment — it is better to check two simple claims than miss a fabrication in a compound sentence.

### 3.5 Output

```
claims_detected: 47
  FACTUAL: 34
  OPINION: 6
  PROCEDURAL: 5
  META: 2
```

Header output: `CRP-Provenance-Claim-Count: 47`

---

## 4. Stage 2: Attribution Analysis

### 4.1 Purpose

For each FACTUAL claim, determine whether it is grounded in the Context Envelope or drawn from the LLM's parametric memory.

### 4.2 Attribution Types

| Type | Definition | Risk Contribution |
|------|-----------|------------------|
| `CONTEXT_GROUNDED` | Claim is semantically supported by ≥1 fact in the envelope | Low — this is the ideal |
| `PARAMETRIC` | Claim has no matching fact in envelope; drawn from model weights | Medium — may be accurate but unverifiable |
| `MIXED` | Claim combines envelope content with parametric additions | Medium — partial grounding |
| `UNVERIFIABLE` | Claim is specific (names a number, date, entity) but matches nothing | High — possible fabrication |

### 4.3 Matching Algorithm

For each FACTUAL claim:

1. Compute claim embedding using the same model as CKF
2. Search the envelope facts for cosine similarity ≥ 0.75
3. If match found: classify as `CONTEXT_GROUNDED`
4. If no match but claim is generic (specificity < 0.30): classify as `PARAMETRIC`
5. If no match and claim is specific (specificity ≥ 0.30): classify as `UNVERIFIABLE`
6. If partial match (similarity 0.60 – 0.74): classify as `MIXED`

### 4.4 Grounding Percentage

```
grounding_pct = count(CONTEXT_GROUNDED) / count(FACTUAL claims)
```

### 4.5 Output

```
attribution_dominant: CONTEXT_GROUNDED
grounding_pct: 0.912
breakdown:
  CONTEXT_GROUNDED: 31 / 34
  PARAMETRIC: 1 / 34
  MIXED: 2 / 34
  UNVERIFIABLE: 0 / 34
```

Header outputs:
```
CRP-Safety-Attribution: CONTEXT_GROUNDED
CRP-Safety-Grounding-Pct: 0.912
CRP-Provenance-Attribution-Score: 0.912
```

---

## 5. Stage 3: Fidelity Verification

### 5.1 Purpose

For claims classified as `CONTEXT_GROUNDED`, verify that the claim accurately represents its source fact — not just that a source exists, but that the claim faithfully reproduces the source's content.

### 5.2 Sub-Stage 3a: Fabrication Detection

**Definition:** A fabrication is a named entity (person, organisation, date, statistic, citation, URL) in the response that has no basis in the envelope or any verifiable source.

**Algorithm:**
1. Extract all named entities from the response
2. For each entity, search the envelope for a matching entity
3. Entities not found in the envelope AND not identifiable as common-knowledge entities → flagged as fabricated
4. Numbers, dates, and statistics receive extra scrutiny — each must trace to a source fact

**Output:** `CRP-Safety-Fabrications: 0`

### 5.3 Sub-Stage 3b: Distortion Detection

**Definition:** A distortion is a claim that references a real source fact but misrepresents it.

**Distortion types:**

| Type | Example |
|------|---------|
| `NUMBER_CHANGED` | Source: "revenue was $4.2M" → Response: "revenue was $4.8M" |
| `NEGATION_FLIP` | Source: "the policy does not apply" → Response: "the policy applies" |
| `DATE_SHIFTED` | Source: "enacted in 2024" → Response: "enacted in 2023" |
| `ENTITY_SUBSTITUTED` | Source: "according to NIST" → Response: "according to ISO" |
| `MAGNITUDE_ALTERED` | Source: "increased by 15%" → Response: "increased by 50%" |
| `CONTEXT_STRIPPED` | Source: "conditionally approved pending review" → Response: "approved" |

**Algorithm:** For each CONTEXT_GROUNDED claim, align it with its matched source fact. Apply NLI contradiction detection. For numeric claims, extract and compare values directly.

**Output:** `CRP-Safety-Distortions: 1; types=NUMBER_CHANGED`

### 5.4 Sub-Stage 3c: Contradiction Detection (Intra-Window)

**Definition:** An intra-window contradiction is two claims within the same response that contradict each other.

**Algorithm:** For every pair of FACTUAL claims, run NLI entailment/contradiction classification. Pairs classified as CONTRADICTION → flagged.

**Output:** Contributes to `CRP-Safety-Contradictions`

### 5.5 Fidelity Score

```
fidelity_score = 1.0 - (
  (fabrication_count × 0.30) +
  (distortion_count × 0.20) +
  (contradiction_count × 0.15)
) / max(1, factual_claim_count)
```

Clamped to [0.0, 1.0].

Header output: `CRP-Provenance-Fidelity-Score: 0.978`

---

## 6. Stage 4: Entailment Scoring

### 6.1 Purpose

Measure the degree to which the entire response is logically entailed by the Context Envelope, using an NLI cross-encoder model.

### 6.2 Algorithm

1. Concatenate all envelope facts into a single premise document
2. Treat the LLM response as the hypothesis
3. Run an NLI cross-encoder (e.g., DeBERTa-v3-large-MNLI) to produce:
   - P(entailment)
   - P(neutral)
   - P(contradiction)

4. Entailment score = P(entailment)

For responses longer than the cross-encoder's max sequence length, chunk the response and compute per-chunk entailment scores, then take the minimum (weakest-link principle).

### 6.3 Output

```
entailment_score: 0.912
contradiction_probability: 0.023
neutral_probability: 0.065
```

Header output: `CRP-Safety-Entailment-Score: 0.912`

---

## 7. Stage 5: Risk Classification

### 7.1 Purpose

Compute the composite hallucination risk score from the four DPE signals and classify into CRITICAL/HIGH/MEDIUM/LOW.

### 7.2 Composite Score Formula

```
attribution_signal  = 1.0 - grounding_pct           weight: 0.35
fidelity_signal     = 1.0 - fidelity_score           weight: 0.25
entailment_signal   = 1.0 - entailment_score         weight: 0.25
specificity_signal  = unverifiable_pct               weight: 0.15

composite = (attribution_signal × 0.35) +
            (fidelity_signal × 0.25) +
            (entailment_signal × 0.25) +
            (specificity_signal × 0.15)
```

Where `unverifiable_pct = count(UNVERIFIABLE) / max(1, count(FACTUAL))`.

### 7.3 Regulatory Amplifiers

After computing the base composite, regulatory amplifiers are applied (see §17):

```
if GDPR_PII_detected:              composite *= 1.30
if EU_AI_Act_HIGH_risk_domain:      composite *= 1.25
if financial_or_medical_domain:     composite *= 1.20
if agentic_loop_depth > 2:         composite *= 1.15
if cross_window_contradiction:      composite *= 1.20

composite = min(composite, 1.0)  // cap at 1.0
```

### 7.4 Classification Thresholds

| Risk Level | Score Range | Protocol Action |
|-----------|-------------|----------------|
| `CRITICAL` | ≥ 0.70 | HTTP 451 if `halt-on CRITICAL`; report-uri webhook |
| `HIGH` | ≥ 0.45 | Strategy upgrade if `upgrade-on-risk`; safety budget -0.15 |
| `MEDIUM` | ≥ 0.20 | Pass with warning headers; budget -0.05 |
| `LOW` | < 0.20 | Pass clean; budget unchanged |

### 7.5 Output

```
CRP-Safety-Hallucination-Risk: LOW
CRP-Safety-Hallucination-Score: 0.14
```

---

## 8. Stage 6: Cross-Window Coherence

### 8.1 Purpose

**★ NEW IN v3.0.** Detect contradictions between the current response and prior windows in the session. A response that says "revenue increased 20%" when a previous window said "revenue decreased 5%" is a cross-window contradiction that single-window DPE cannot catch.

### 8.2 Algorithm

**Input:** Current response + summary/content of all prior windows in the session (stored in the WindowDAG).

**Step 6.1 — Extract key assertions:** From the current response, extract all FACTUAL claims that reference entities, numbers, dates, or states also mentioned in prior windows.

**Step 6.2 — Cross-reference:** For each such claim, find the corresponding claim in the prior window(s). If the prior window's claim was summarised (per CRP-SPEC-004 §12), use the summary — the summary was verified for fidelity against the original.

**Step 6.3 — NLI contradiction check:** Run NLI on each pair (current_claim, prior_claim). If P(contradiction) > 0.75 → flag as cross-window contradiction.

**Step 6.4 — Severity classification:**

| Contradiction Type | Severity | Example |
|-------------------|----------|---------|
| Numeric contradiction | CRITICAL | W1: "$4.2M revenue" vs W2: "$5.1M revenue" |
| Logical contradiction | HIGH | W1: "policy approved" vs W2: "policy rejected" |
| Temporal contradiction | HIGH | W1: "launched in 2024" vs W2: "launched in 2025" |
| Stance contradiction | MEDIUM | W1: "generally positive" vs W2: "largely negative" |
| Minor inconsistency | LOW | W1: "about 15%" vs W2: "approximately 16%" |

### 8.3 Impact on Risk Score

Cross-window contradictions apply a regulatory amplifier of ×1.20 to the composite score (see §17). If a CRITICAL-severity contradiction is detected, the response is flagged for re-dispatch regardless of the overall composite score.

### 8.4 Output

```
CRP-Safety-Contradictions: 1; scope=cross-window
```

If contradictions found, the DPE report includes:
- The contradicting claims (current and prior)
- The window IDs involved
- The contradiction severity

---

## 9. Stage 7: Repetition Detection

### 9.1 Purpose

**★ NEW IN v3.0.** Detect when the current response repeats content from prior windows — verbatim or near-verbatim. Repetition wastes the user's context and indicates the LLM is not building on prior output but re-generating it.

### 9.2 Algorithm

**Step 7.1 — N-gram overlap:** Compute 4-gram overlap between the current response and all prior window responses in the session.

```
overlap_ratio = count(shared_4grams) / count(current_4grams)
```

**Step 7.2 — Semantic overlap:** Compute sentence-level cosine similarity between each sentence in the current response and all sentences in prior responses.

```
for each sentence_current in current_response:
    max_sim = max(cosine_sim(sentence_current, sentence_prior) for sentence_prior in prior_responses)
    if max_sim > 0.92:
        repeated_sentences.append(sentence_current)

semantic_repetition_ratio = len(repeated_sentences) / len(current_sentences)
```

**Step 7.3 — Classification:**

| Repetition Level | N-gram Overlap | Semantic Overlap | Action |
|-----------------|---------------|-----------------|--------|
| `NONE` | < 0.05 | < 0.10 | Pass |
| `MINOR` | 0.05 – 0.15 | 0.10 – 0.25 | Log warning |
| `SIGNIFICANT` | 0.15 – 0.30 | 0.25 – 0.50 | Flag in quality report; recommend re-dispatch |
| `SEVERE` | > 0.30 | > 0.50 | Trigger re-dispatch with anti-repetition instruction |

### 9.3 Anti-Repetition Re-Dispatch

When `SEVERE` repetition is detected and `upgrade-on-risk` is set in the Safety Policy, the gateway triggers re-dispatch with an augmented system prompt:

```
System prompt addition:
"IMPORTANT: The following content has already been provided to the user in prior responses.
DO NOT repeat this content. Build upon it, extend it, or address different aspects.

[Prior response summary — flagged repeated sections marked]

Continue from where the prior response ended. Provide NEW information only."
```

The re-dispatched response goes through the full DPE pipeline again, including another repetition check.

### 9.4 Output

A new response header for quality:

```
CRP-Quality-Repetition: NONE
CRP-Quality-Repetition: SIGNIFICANT; overlap=0.28
```

---

## 10. Stage 8: Completeness Verification

### 10.1 Purpose

**★ NEW IN v3.0.** Verify that the response (or the cumulative response across all windows in the session) actually answers the user's query — completely. An LLM may produce a confident, well-grounded response that addresses only half the question.

### 10.2 Algorithm

**Step 8.1 — Query decomposition:** Decompose the user's query into constituent information needs (same decomposition used in CRP-SPEC-003 §5.2).

```
Query: "Compare EU AI Act and GDPR approaches to automated decision-making 
        and list the compliance requirements for each"

Sub-queries:
  1. EU AI Act approach to automated decision-making
  2. GDPR approach to automated decision-making
  3. Comparison between the two approaches
  4. EU AI Act compliance requirements
  5. GDPR compliance requirements
```

**Step 8.2 — Coverage check:** For each sub-query, check whether the response (cumulative across all session windows) contains content that addresses it.

```
for each sub_query:
    max_relevance = max(
        cosine_sim(sub_query_embedding, sentence_embedding)
        for sentence in all_session_responses
    )
    if max_relevance > 0.70:
        covered.append(sub_query)
    else:
        uncovered.append(sub_query)

completeness_score = len(covered) / len(sub_queries)
```

**Step 8.3 — Classification:**

| Completeness | Score | Action |
|-------------|-------|--------|
| `COMPLETE` | ≥ 0.90 | Pass |
| `MOSTLY_COMPLETE` | 0.70 – 0.89 | Log; if continuation windows remain, recommend continuation |
| `PARTIAL` | 0.40 – 0.69 | Flag in quality report; recommend continuation or broader query |
| `INCOMPLETE` | < 0.40 | If continuation windows remain: auto-continue. If exhausted: warn client |

### 10.3 Auto-Continuation on Incompleteness

When completeness is `PARTIAL` or `INCOMPLETE` AND the session has remaining continuation windows AND `CRP-Context-Cache` does not contain `no-cache`:

1. Gateway automatically issues a continuation window focused on the uncovered sub-queries
2. The continuation's envelope prioritises facts related to uncovered sub-queries
3. The system prompt includes: "The prior response addressed [covered topics]. Now address: [uncovered topics]."
4. This auto-continuation is transparent to the client — they receive the combined response

The auto-continuation is logged as a `COMPLETENESS_CONTINUATION` event in the audit trail.

### 10.4 Output

```
CRP-Quality-Completeness: COMPLETE; sub-queries=5/5
CRP-Quality-Completeness: PARTIAL; sub-queries=3/5; uncovered=eu-ai-act-requirements,gdpr-requirements
```

---

## 11. Stage 9: Flow & Continuity Analysis

### 11.1 Purpose

**★ NEW IN v3.0.** Ensure that multi-window responses read as a single coherent document, not as N independent answers stapled together. This is the hardest quality problem in multi-window AI and the area where CRP provides the most novel contribution.

### 11.2 The Flow Problem

Without flow analysis, a 3-window response might read:

```
[Window 1]: "The EU AI Act classifies AI systems into four risk levels..."
[Window 2]: "The EU AI Act introduces a risk-based approach to AI regulation. 
             Systems are classified into four categories..."  ← REPEATS W1
[Window 3]: "In conclusion, the EU AI Act..."  ← ABRUPT, no bridge from W2
```

With flow analysis, it should read:

```
[Window 1]: "The EU AI Act classifies AI systems into four risk levels..."
[Window 2]: "Building on this classification framework, the Act defines specific 
             obligations for each risk level..."  ← EXTENDS W1
[Window 3]: "These obligations translate into concrete compliance requirements. 
             Specifically..."  ← BRIDGES naturally from W2
```

### 11.3 Flow Signals

The DPE evaluates four flow signals for continuation windows (window_number > 1):

**Signal 9a — Opening coherence:** Does the response's opening sentence connect to the prior window's closing content?

```
opening_coherence = cosine_sim(
    current_response.first_2_sentences.embedding,
    prior_response.last_2_sentences.embedding
)
```

A low opening coherence (< 0.40) indicates the response starts as if the prior window didn't exist.

**Signal 9b — Topic continuity:** Does the response maintain or logically extend the topic trajectory?

```
prior_topics = extract_topics(prior_response)  // Top-5 topic clusters
current_topics = extract_topics(current_response)
topic_continuity = jaccard_similarity(prior_topics, current_topics)
```

A topic_continuity of 0.0 indicates a complete topic shift (may be valid for a new sub-query; context-dependent).

**Signal 9c — Register consistency:** Does the response maintain the same formality, style, and person as the prior window?

```
register_signals:
  - sentence_length_mean (current vs prior — should be within 20%)
  - vocabulary_complexity (current vs prior — should be within 15%)
  - passive_voice_ratio (current vs prior — should be within 10%)
  - personal_pronoun_usage (current vs prior — should match)
```

Large register shifts indicate stylistic incoherence.

**Signal 9d — Transitional markers:** Does the response contain explicit continuation markers ("Furthermore", "Building on this", "As noted previously", "The next aspect")?

```
has_transition = any(
    sentence starts with transitional_phrase
    for sentence in current_response.first_3_sentences
)
```

### 11.4 Flow Score

```
flow_score = (
    opening_coherence × 0.35 +
    topic_continuity × 0.25 +
    register_consistency × 0.20 +
    transition_presence × 0.20
)
```

### 11.5 Flow Remediation

When flow_score < 0.50 and the session has used continuation:

**Option A — Prompt augmentation (default):** Re-dispatch with a system prompt that explicitly instructs continuation flow:

```
System prompt addition:
"This is a continuation of a prior response. The prior response ended with:

'[last 3 sentences of prior response]'

Continue naturally from that point. Do NOT re-introduce the topic.
Do NOT repeat content from the prior response.
Use transitional language to bridge from the prior content.
Maintain the same style, formality, and level of detail."
```

**Option B — Post-processing stitch (if re-dispatch would exceed budget):** The gateway generates a 1-2 sentence bridge between the prior window's end and the current window's beginning, using a dedicated "stitch call" with temperature 0.2:

```
Stitch prompt:
"Write a 1-2 sentence bridge connecting these two passages:

PASSAGE A ends with: '[last 2 sentences of Window N-1]'
PASSAGE B begins with: '[first 2 sentences of Window N]'

The bridge should create a natural transition. Be concise."
```

The stitch is inserted between the windows. The stitch call is logged as a `FLOW_STITCH` event.

### 11.6 Output

```
CRP-Quality-Flow: 0.82
CRP-Quality-Flow: 0.34; remediation=prompt-augmented
```

---

## 12. Stage 10: Omission Detection

### 12.1 Purpose

Detect when the Context Envelope contained critical information that the LLM ignored. An omission is different from incompleteness (Stage 8) — omission means the relevant facts were in the envelope but the model didn't use them. Incompleteness means the query wasn't fully answered.

### 12.2 Algorithm

For each fact in the envelope with `importance_weight ≥ 0.70`:

1. Search the response for semantic coverage of this fact
2. If no sentence in the response has cosine similarity ≥ 0.60 with the fact → flag as omission
3. Classify omission severity based on `importance_weight`:
   - ≥ 0.90 → CRITICAL omission
   - ≥ 0.80 → HIGH omission
   - ≥ 0.70 → MEDIUM omission

### 12.3 Output

```
CRP-Safety-Omissions: CRITICAL:0, HIGH:1, MEDIUM:2
```

---

## 13. Stage 11: PII Detection

### 13.1 Purpose

Detect personal data (as defined under GDPR Art. 4(1)) in both the request prompt and the LLM response.

### 13.2 Detection Categories

| Category | Pattern | Examples |
|----------|---------|---------|
| Direct identifiers | Named entity recognition | Full names, email addresses, phone numbers |
| Quasi-identifiers | Pattern matching + context | Dates of birth, addresses, employee IDs |
| Sensitive data | Classifier | Health data, political opinions, ethnic origin |
| Financial data | Pattern matching | Credit card numbers, bank accounts, salaries |

### 13.3 Output

```
CRP-Compliance-GDPR-PII: true
```

When `true`, the gateway also checks whether `CRP-Context-Cache: no-store` is set. If not, a compliance warning is emitted.

---

## 14. Stage 12: Regulatory Classification

### 14.1 Purpose

Classify the AI call against regulatory frameworks based on the registered AI system type, deployment domain, and the DPE analysis results.

### 14.2 EU AI Act Classification

Based on the system's registered risk category (set during gateway configuration):

| Registered Domain | Default Class | Override Conditions |
|------------------|--------------|-------------------|
| Biometric identification | UNACCEPTABLE | — |
| Employment/recruitment | HIGH | — |
| Education access | HIGH | — |
| Critical infrastructure | HIGH | — |
| General information | LIMITED | Upgrades to HIGH if PII detected in decisions |
| Creative/entertainment | MINIMAL | — |

### 14.3 Output

```
CRP-Compliance-EU-AI-Act: LIMITED
CRP-Compliance-NIST-Tier: TIER-2
CRP-Compliance-ISO-42001: A.6.1.2, A.9.4
CRP-Compliance-Controls-Met: 33/35
```

---

## 15. Stage 13: Report Generation

### 15.1 Purpose

Generate the complete DPE provenance report and the HMAC audit record for this window.

### 15.2 Report Contents

```
DPE_Report {
  session_id:               string
  window_id:                string
  window_number:            integer
  timestamp:                ISO 8601
  
  // Provenance
  claims_total:             integer
  claims_by_type:           map<string, integer>
  attribution_dominant:     string
  grounding_pct:            float
  fabrication_count:        integer
  distortion_count:         integer
  distortion_types:         string[]
  contradiction_count:      integer
  contradiction_scope:      string
  omission_summary:         map<string, integer>
  fidelity_score:           float
  entailment_score:         float
  
  // Quality (NEW v3.0)
  repetition_level:         string
  repetition_overlap:       float
  completeness_score:       float
  uncovered_sub_queries:    string[]
  flow_score:               float
  flow_remediation:         string | null
  cross_window_contradictions: Contradiction[]
  
  // Risk
  composite_score:          float
  amplifiers_applied:       string[]
  risk_level:               string
  
  // Compliance
  eu_ai_act_class:          string
  nist_tier:                string
  gdpr_pii_detected:        boolean
  iso_42001_controls:       string[]
  
  // Chain
  hmac:                     string
  chain_integrity:          string
  
  // Hashes for verification
  response_content_hash:    string
  report_hash:              string
}
```

### 15.3 HMAC Generation

See CRP-SPEC-004 §9 and CRP-SPEC-011 for the complete HMAC chain algorithm.

### 15.4 Report Storage

The report is:
1. Stored in the gateway's audit trail database
2. Streamed to CRP Comply (if configured)
3. Referenced via `CRP-Provenance-Report-URI` header
4. Included in the HMAC chain via its hash

---

## 16. Composite Risk Scoring Algorithm

### 16.1 Complete Formula

```python
# Stage outputs (0.0 = best, 1.0 = worst for signal inputs)
attribution_signal  = 1.0 - grounding_pct             # weight: 0.35
fidelity_signal     = 1.0 - fidelity_score             # weight: 0.25
entailment_signal   = 1.0 - entailment_score           # weight: 0.25
specificity_signal  = unverifiable_count / max(1, factual_count)  # weight: 0.15

base_composite = (
    attribution_signal  * 0.35 +
    fidelity_signal     * 0.25 +
    entailment_signal   * 0.25 +
    specificity_signal  * 0.15
)

# Apply regulatory amplifiers (§17)
amplified = base_composite
for amplifier in applicable_amplifiers:
    amplified *= amplifier.factor

# Apply quality penalty (NEW v3.0)
if cross_window_contradiction_count > 0:
    amplified *= 1.20
if repetition_level == "SEVERE":
    amplified *= 1.10

composite = min(amplified, 1.0)

# Classify
if composite >= 0.70: risk = "CRITICAL"
elif composite >= 0.45: risk = "HIGH"
elif composite >= 0.20: risk = "MEDIUM"
else: risk = "LOW"
```

### 16.2 Why These Weights

The weights are empirically calibrated against a test corpus of known-good and known-bad LLM outputs:

- **Attribution (0.35):** The strongest predictor of hallucination. An ungrounded response is the primary failure mode.
- **Fidelity (0.25):** Distortion is the second most dangerous failure — the response references real sources but misrepresents them.
- **Entailment (0.25):** Measures overall logical consistency between context and response.
- **Specificity (0.15):** Catches fabricated specifics (fake citations, invented numbers) that other signals may miss.

### 16.3 Weight Configuration

Weights are configurable per CRP gateway deployment. The specification defines the default weights above but does NOT mandate them. Conformant implementations MUST document their weight configuration.

---

## 17. Regulatory Amplifiers

Amplifiers increase the composite score when the regulatory context raises the stakes of a given risk level:

| Condition | Amplifier | Justification |
|-----------|-----------|--------------|
| `CRP-Compliance-GDPR-PII: true` | ×1.30 | PII in AI outputs raises GDPR Art. 5(1)(d) accuracy obligation |
| EU AI Act HIGH-risk domain | ×1.25 | HIGH-risk systems have stricter Art. 9 risk management requirements |
| Financial or medical domain | ×1.20 | Sector-specific accuracy regulations (MiFID II, MDR) |
| `CRP-Agent-Loop-Depth > 2` | ×1.15 | Deeper agent chains compound error risk |
| Cross-window contradiction | ×1.20 | Contradictions across windows indicate systemic generation failure |
| `CRP-Quality-Repetition: SEVERE` | ×1.10 | Severe repetition indicates model degradation |

---

## 18. Response Quality Assurance (RQA)

### 18.1 Overview

The RQA subsystem (Stages 6–9) ensures that multi-window CRP responses meet production quality standards. It addresses the four failure modes unique to continuation:

| Failure Mode | Stage | Signal | Remediation |
|-------------|-------|--------|-------------|
| Cross-window contradiction | 6 | NLI contradiction score | Re-dispatch with context correction |
| Content repetition | 7 | N-gram + semantic overlap | Re-dispatch with anti-repetition prompt |
| Incomplete answer | 8 | Sub-query coverage | Auto-continuation to uncovered topics |
| Incoherent flow | 9 | Opening coherence + transitions | Prompt augmentation or stitch insertion |

### 18.2 RQA as a Composite Quality Score

A new composite quality score (separate from the safety risk score):

```
quality_score = (
    (1.0 - repetition_ratio)     × 0.25 +
    completeness_score            × 0.35 +
    flow_score                    × 0.25 +
    coherence_score               × 0.15    // 1.0 - contradiction_ratio
)
```

### 18.3 Quality Score Header

```
CRP-Quality-Score: 0.91
```

This is a new response header — distinct from `CRP-Safety-Hallucination-Risk`. Safety measures truthfulness. Quality measures usefulness. Both matter.

### 18.4 Quality Tier Interaction

The quality score can downgrade the `CRP-Context-Quality-Tier`:

| Quality Score | Maximum Quality Tier |
|-------------|---------------------|
| ≥ 0.85 | S (no restriction) |
| 0.70 – 0.84 | A |
| 0.50 – 0.69 | B |
| 0.30 – 0.49 | C |
| < 0.30 | D |

If the envelope quality tier is `A` but the RQA quality score is 0.62, the emitted tier is downgraded to `B`.

### 18.5 The Stitching Pipeline (Complete Flow)

For a multi-window response, the complete quality pipeline is:

```
Window N response received from LLM
     │
     ▼
[Stage 6] Cross-window coherence check
     │── Contradiction found? → Flag, apply amplifier, consider re-dispatch
     ▼
[Stage 7] Repetition detection
     │── SEVERE repetition? → Re-dispatch with anti-repetition prompt
     ▼
[Stage 8] Completeness verification
     │── PARTIAL/INCOMPLETE? → Auto-continue to uncovered sub-queries
     ▼
[Stage 9] Flow analysis
     │── Low flow score? → Insert stitch OR re-dispatch with flow prompt
     ▼
Quality Score computed → Quality Tier adjusted
     │
     ▼
Response released to client (with quality + safety headers)
```

---

## 19. Re-Dispatch Protocol

### 19.1 When Re-Dispatch Is Triggered

Re-dispatch occurs when:
1. `CRP-Safety-Policy` contains `upgrade-on-risk <strategy>` AND risk level exceeds threshold
2. SEVERE repetition detected (Stage 7)
3. CRITICAL cross-window contradiction detected (Stage 6)
4. Flow score < 0.30 and prompt augmentation is configured (Stage 9)

### 19.2 Re-Dispatch Parameters

| Parameter | Adjustment |
|-----------|-----------|
| Temperature | Reduced to 0.2 (from default 0.7) |
| Strategy | Upgraded to `reflexive` (or strategy named in `upgrade-on-risk`) |
| System prompt | Augmented with specific remediation instructions |
| Seed | Changed (different from original dispatch) to avoid regenerating same output |
| Max re-dispatches | 2 per window (prevent infinite loops) |

### 19.3 Re-Dispatch Accounting

Re-dispatches:
- Count as additional LLM calls (token cost)
- Are billed at CRP Gateway usage rates
- Are logged as `RE_DISPATCH` events in the audit trail
- Do NOT decrement the safety budget (they are remediation, not new risk)
- The final response's DPE analysis is the one that determines headers

---

## 20. Header Outputs

Complete list of headers populated by the DPE pipeline:

| Stage | Header |
|-------|--------|
| 1 | `CRP-Provenance-Claim-Count` |
| 2 | `CRP-Safety-Attribution`, `CRP-Safety-Grounding-Pct`, `CRP-Provenance-Attribution-Score` |
| 3a | `CRP-Safety-Fabrications` |
| 3b | `CRP-Safety-Distortions` |
| 3c/6 | `CRP-Safety-Contradictions` |
| 4 | `CRP-Safety-Entailment-Score`, `CRP-Provenance-Fidelity-Score` |
| 5 | `CRP-Safety-Hallucination-Risk`, `CRP-Safety-Hallucination-Score` |
| 7 | `CRP-Quality-Repetition` ★ NEW |
| 8 | `CRP-Quality-Completeness` ★ NEW |
| 9 | `CRP-Quality-Flow` ★ NEW |
| RQA | `CRP-Quality-Score` ★ NEW |
| 10 | `CRP-Safety-Omissions` |
| 11 | `CRP-Compliance-GDPR-PII` |
| 12 | `CRP-Compliance-EU-AI-Act`, `CRP-Compliance-NIST-Tier`, `CRP-Compliance-ISO-42001`, `CRP-Compliance-Controls-Met` |
| 13 | `CRP-Provenance-HMAC`, `CRP-Provenance-Chain-Integrity`, `CRP-Provenance-Report-URI` |

---

## 21. Security Considerations

### 21.1 DPE as a Trust Boundary

The DPE runs within the CRP gateway and its outputs (headers) are authoritative. If the DPE is compromised, all safety signals become unreliable. Mitigations:
- DPE code MUST be integrity-checked on gateway startup
- DPE outputs MUST be included in the HMAC chain (report hash is part of the HMAC input)
- DPE models (NLI cross-encoder, NER model) MUST be pinned to specific versions and hash-verified

### 21.2 Adversarial LLM Responses

An LLM that has been prompt-injected may attempt to produce output that evades DPE detection. Mitigations:
- NLI entailment scoring is resistant to stylistic manipulation — it measures logical relationship, not surface features
- Fabrication detection uses entity extraction + envelope search, not pattern matching — harder to evade
- The DPE pipeline runs on the complete response, not on a model-selected excerpt

### 21.3 DPE Scoring Weights as Proprietary Information

The default scoring weights are published in this specification. However, production CRP deployments MAY use custom weights calibrated to their specific domain. Custom weights SHOULD be treated as proprietary and SHOULD NOT be exposed in headers or API responses.

---

## 22. References

### Normative References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-006 — Safety Policy Directive Language
- CRP-SPEC-011 — Audit Trail & HMAC Chain

### Informative References

- Williams, A., Nangia, N., & Bowman, S.R. (2018). "A Broad-Coverage Challenge Corpus for Sentence Understanding through Inference" (MNLI)
- He, P., Gao, J., & Chen, W. (2021). "DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing"
- EU Regulation 2024/1689 (EU AI Act)
- GDPR Art. 4(1) — Definition of personal data
- NIST AI RMF 1.0 — MEASURE function

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*
