# CRP-SPEC-026: Semantic Quality Benchmark (SQB)

**Document:** CRP-SPEC-026  
**Title:** Context Relay Protocol (CRP) — Semantic Quality Benchmark: Proving Output Is Better, Not Just Longer  
**Version:** 1.0.0  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Extends:** CRP-SPEC-014 (Conformance)  
**Prerequisites:** CRP-SPEC-005, CRP-SPEC-024, CRP-SPEC-025

---

## Abstract

This document closes the most uncomfortable gap in CRP's evidence base: every benchmark to date measures *mechanical* properties — repetition percentage, word count, token efficiency, latency. None measures whether the output is actually *correct, complete, and useful*. CRP has proven it makes output less repetitive and longer. It has not proven it makes output better. Low repetition does not imply high quality; a document can be fluent, non-repetitive, well-structured, and confidently wrong.

The Semantic Quality Benchmark (SQB) specifies the measurement infrastructure that proves the core value claim. It defines factual recall, factual precision, factual F1, coverage completeness, and an LLM-as-judge protocol with a fixed rubric and blind A/B comparison. The decisive metric is explicit: CRP must improve **Factual F1 AND judge-assessed usefulness**, not merely reduce repetition. If a CRP configuration reduces repetition but does not improve Factual F1, that configuration has not improved quality — it has only improved a proxy. This document makes the distinction measurable and binding.

---

## 1. Why Mechanical Metrics Are Insufficient

### 1.1 What the Existing Benchmark Proves and Does Not Prove

The v3.1.1 benchmark established:

| Metric | What it proves | What it does NOT prove |
|--------|---------------|----------------------|
| 6-gram repetition ↓ | Less verbatim recycling | Content is correct |
| Word count ↑ | More output produced | Output is useful |
| Context efficiency ↑ | Fewer wasted tokens | Retrieved facts were the right ones |
| Latency ↓ | Faster generation | Faster generation of correct content |

Every one of these is a proxy. A model can produce 3,000 non-repetitive, efficient, fast words that are factually wrong, incomplete, or useless. The mechanical metrics would score that output highly. **This is the gap that makes "revolutionary quality" an unproven claim.**

### 1.2 The Three Questions SQB Must Answer

1. **Recall:** Did the output include the information it should have?
2. **Precision:** Is everything the output stated actually correct and supported?
3. **Usefulness:** Would a human (or expert judge) rate this output as genuinely better?

These are semantic questions. They require semantic measurement.

---

## 2. The SQB Metrics

### 2.1 Ground Truth Construction

Each SQB test case consists of:

```
SQBTestCase {
  task:               string         // the generation prompt
  source_corpus:      Document[]      // what the CKF is populated with
  reference_facts:    Fact[]          // facts the output SHOULD contain
  required_topics:    string[]        // sub-topics that must be addressed
  forbidden_claims:   string[]        // known-false claims that must NOT appear
}
```

Reference facts are constructed by domain experts (or extracted from authoritative source documents) BEFORE any generation. They represent the ground truth the output is measured against.

### 2.2 Factual Recall

```
factual_recall = |reference_facts entailed by output| / |reference_facts|
```

For each reference fact, an NLI (natural language inference) cross-encoder checks whether the output entails it. Recall is the fraction of reference facts the output successfully conveys. This is the same entailment engine used by DPE Stage 4 (SPEC-005), reused here against ground truth rather than the envelope.

**Low recall** = the output omitted information it should have included. The model had the facts available (they were in the CKF) but failed to use them, OR retrieval failed to surface them. SQB distinguishes these by checking whether the missed facts were in the envelope.

### 2.3 Factual Precision

```
factual_precision = |output claims that are supported| / |total output claims|
```

Each claim in the output (segmented by DPE Stage 1) is checked for support against the source corpus. A claim is supported if it is entailed by some source fact. Unsupported claims are either fabrications (Class 1, SPEC-019) or distortions (Class 2).

**Low precision** = the output contains fabricated or distorted content. This is the dangerous failure — confident, fluent, wrong.

### 2.4 Factual F1

```
factual_f1 = 2 × (recall × precision) / (recall + precision)
```

The harmonic mean. A high F1 requires BOTH completeness (recall) AND correctness (precision). An output cannot game F1 by being exhaustive but wrong (high recall, low precision) or correct but sparse (high precision, low recall). **Factual F1 is the primary SQB metric.**

### 2.5 Coverage Completeness

```
coverage_completeness = |required_topics addressed| / |required_topics|
```

Distinct from recall: recall measures specific facts, completeness measures topic breadth. An output might convey all facts about three of five required topics (high partial recall) while ignoring two topics entirely (low completeness). Both matter.

### 2.6 Forbidden Claim Violations

```
forbidden_violations = |forbidden_claims appearing in output|
```

A direct test for known failure modes. If the source corpus contains a common misconception that should NOT be reproduced, or a stale fact that has been superseded, SQB checks the output does not state it. Any violation is a hard quality failure regardless of other scores.

### 2.7 LLM-as-Judge (Usefulness)

Mechanical and entailment metrics still miss subjective usefulness — coherence, organisation, actionability. SQB specifies a blind LLM-as-judge protocol:

```
1. Generate output_A (CRP) and output_B (baseline) for the same task
2. Strip all identifying markers; randomise which is labelled "1" and "2"
3. A strong judge model (GPT-4o-class or stronger) scores each on a
   fixed 1-5 rubric across: completeness, accuracy, coherence,
   organisation, usefulness
4. The judge does NOT know which output used CRP
5. Run the comparison N times (default 5) with the A/B order shuffled
   to control for position bias
6. Report mean scores and win rate
```

The rubric is fixed and published so judge scoring is reproducible:

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| Completeness | Major gaps | Some gaps | Comprehensive |
| Accuracy | Multiple errors | Minor errors | Fully accurate |
| Coherence | Disjointed | Mostly coherent | Seamless |
| Organisation | No structure | Adequate | Excellent |
| Usefulness | Not useful | Somewhat | Highly useful |

### 2.8 Output Quality Disclosure Header

When SQB has been run against a CRP configuration in testing, the conformance report carries:

```
CRP-Quality-Factual-F1: 0.87
CRP-Quality-Coverage-Completeness: 0.92
CRP-Quality-Judge-Score: 4.3/5.0
```

Note: these are produced in BENCHMARKING, not on every live call (computing factual F1 requires ground truth, which live calls don't have). They are conformance evidence, not runtime headers.

---

## 3. The Binding Quality Criterion

### 3.1 The Decisive Rule

A CRP feature, configuration, or version improves quality if and only if:

```
ΔFactual_F1 > 0  AND  ΔJudge_Score > 0
```

relative to the baseline (naive generation, same model, same task, no CRP).

**Reducing repetition is necessary but not sufficient.** A change that reduces repetition but does not improve Factual F1 has not improved quality — it has improved a proxy. This rule is binding for all quality claims in CRP marketing, documentation, and standards submissions.

### 3.2 Why This Protects CRP

This rule is a guard against self-deception. It is easy to optimise mechanical metrics (repetition, length) and convince yourself quality improved. SQB forces every quality claim to survive a semantic test against ground truth. If CRP genuinely improves output quality — and the architecture strongly suggests it does — SQB proves it rigorously. If a particular feature does not improve Factual F1, SQB catches it before it ships as a false claim.

---

## 4. The Decisive CRP Benchmark (SQB Applied)

### 4.1 The Experiment That Proves the Thesis

```
Task: A complex, knowledge-grounded generation task with a known
      ground-truth reference fact set (e.g., "Explain the complete
      failure-and-recovery path of a Kubernetes pod losing database
      connectivity after node restart" — 40 reference facts, 8 required
      topics, 5 forbidden stale claims).

Contenders:
  A: Naive generation, target model, no CRP
  B: CRP Core + CDR (SPEC-024)
  C: CRP Core + CDR + CDGR (SPEC-025, graph-aware)

Measure for each: Factual F1, Coverage Completeness, Forbidden
                  Violations, Judge Score, plus the mechanical metrics.

Predicted result (the thesis to prove):
  - B > A on Factual F1 (CDR surfaces fresher, more complete facts)
  - C > B on Factual F1 (CDGR adds connector facts → higher recall
    on multi-hop reference facts specifically)
  - C has highest Coverage Completeness (graph reaches more topics)
  - C lowest Forbidden Violations (recency + grounding)
  - C highest Judge Score
```

### 4.2 The Multi-Hop Sub-Metric

SQB introduces a metric specifically for CDGR validation:

```
multi_hop_recall = |multi-hop reference facts entailed by output|
                 / |multi-hop reference facts|
```

Where a "multi-hop reference fact" is one that requires connecting two or more source facts to state correctly. This metric isolates CDGR's contribution: if CDGR works, multi_hop_recall should improve markedly from B to C, even if single-hop recall is similar. This is the precise, falsifiable test of whether graph retrieval delivers.

---

## 5. Integration with Conformance (SPEC-014)

SQB becomes the quality conformance suite within SPEC-014. A CRP implementation claiming CRP-Standard conformance SHOULD publish SQB results showing positive ΔFactual_F1 and ΔJudge_Score versus baseline. CRP-Full conformance SHOULD additionally publish multi_hop_recall improvement demonstrating CDGR effectiveness.

The SQB test corpus is published at `github.com/autocyberai/crp-sqb` with reference fact sets, required topics, and forbidden claims for a standard set of domains (technical documentation, regulatory analysis, medical information, financial reporting). Implementations run their CRP against the published corpus and report results in a standard format.

---

## 6. What SQB Does Not Measure

SQB measures factual correctness, completeness, and judged usefulness. It does not measure:
- **Subjective stylistic preference** beyond the rubric dimensions
- **Domain-specific quality** that requires specialist judgment (e.g., whether legal reasoning is sound — this needs a domain expert, not an LLM judge)
- **Long-term factual drift** as the underlying domain changes

These require human expert evaluation. SQB provides the automated, reproducible layer; expert evaluation remains necessary for high-stakes domains. SQB is honest that it is a strong automated proxy for quality, not a replacement for domain expertise.

---

## 7. References

- CRP-SPEC-005 — Decision Provenance Engine (claim segmentation, NLI engine)
- CRP-SPEC-014 — Conformance & Test Suite (SQB integrates here)
- CRP-SPEC-024 — Coverage-Differential Retrieval
- CRP-SPEC-025 — Coverage-Differential Graph Retrieval

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
