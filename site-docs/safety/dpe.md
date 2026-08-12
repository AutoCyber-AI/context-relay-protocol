# The Decision Provenance Engine (DPE)

<div class="cr-hero" markdown>

## Prove what the model did, not what it is

The DPE is CRP's runtime answer to the AI black-box problem. It does not try to
understand the model's weights. It breaks every response into claims, checks each
claim against verifiable sources, and binds the verdict to a tamper-evident
audit trail. The result: you can ship AI outputs with measurable evidence of
grounding, safety, and quality.

</div>

The DPE runs **13 stages** on every response before it is delivered. It is fully
specified in [SPEC-005](../spec/CRP-SPEC-005-dpe.md).

This page explains each stage in plain English for non-technical readers.

| # | Stage | What it checks | Latency budget |
|---|-------|----------------|----------------|
| 1 | Claim Detection | Decomposes the response into atomic, verifiable claims. | < 5 ms |
| 2 | Attribution Analysis | Maps each claim back to facts in the envelope. | < 3 ms |
| 3 | Fabrication Detection | Flags claims with no envelope support and no plausible inferential path. | < 4 ms |
| 4 | Distortion Detection | Detects altered numbers, dates, names, quantities. | < 3 ms |
| 5 | Entailment Scoring | Scores claim-to-source semantic entailment. | < 8 ms |
| 6 | Contradiction Detection | Cross-checks against the current envelope and prior windows. | < 4 ms |
| 7 | Repetition Detection | n-gram and semantic overlap against prior windows. | < 2 ms |
| 8 | Completeness Verification | Tracks how many required sections / outputs were produced. | < 2 ms |
| 9 | Flow Analysis | Opening coherence, topic continuity, register, transitional markers. | < 4 ms |
| 10 | Hallucination Risk Scoring | Aggregates 1-6 into a calibrated risk score. | < 2 ms |
| 11 | Quality Tiering | S / A / B / C / D classification. | < 1 ms |
| 12 | Safety Policy Evaluation | Applies the active `CRP-Safety-Policy` directives. | < 2 ms |
| 13 | Provenance Binding | HMAC-chains the verdict to the audit trail. | < 5 ms |

Total budget: **< 50 ms** for an average 1,500-token response.

---

## Why 13 Stages Is the Right Number

Each stage answers a question that a regulator, auditor, or safety reviewer
genuinely asks:

- "Did the model invent something?" → Stage 3
- "Did the model change a number or date?" → Stage 4
- "Does the answer logically follow from the source?" → Stage 5
- "Did it contradict an earlier turn?" → Stage 6
- "Did it just rephrase what it already said?" → Stage 7
- "Did it finish the job?" → Stage 8
- "Does the prose actually read as continuous?" → Stage 9
- "How risky is this response overall?" → Stage 10
- "Can I prove all of this happened?" → Stage 13

If any one stage is removed, a class of safety question goes unanswered.
