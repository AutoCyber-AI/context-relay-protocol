---
Document: CRP-SPEC-055
Title: Epistemic Profiles — Per-Model, Per-Task Calibration Tracking and Semantic-Entropy Uncertainty
Version: 6.0.0
Status: Roadmap (semantic-entropy tracking only; calibration curves not yet built)
Author: Constantinos Vidiniotis, AutoCyber AI Pty Ltd
Contact: contact@crprotocol.io
License: CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)
Prerequisites: CRP-SPEC-009, CRP-SPEC-026, CRP-SPEC-021, CRP-SPEC-049, CRP-SPEC-031
---

# CRP-SPEC-055: Epistemic Profiles & Calibration (EP)

## Abstract

Quality tiers measure the *output* of a CRP-managed invocation; they do not measure the *model's self-knowledge*. This specification defines **Epistemic Profiles (EP)**: a per-model, per-task tracking layer that closes the gap between a model's implicit confidence and its externally verified correctness, and a lightweight **semantic-entropy** signal that turns divergence across sampled reasoning paths into an explicit uncertainty value.

Two signals are specified:

1. **Semantic entropy** clusters sampled conclusions by meaning (bidirectional entailment) and computes a normalised uncertainty score. It is cheap, runs on self-consistency samples already produced by CRP-SPEC-021 (ROS), and feeds directly into quality-tier and risk scoring.
2. **Calibration curves** compare a model's confidence to empirical correctness per task kind, stored as CKF nodes. As of this version, calibration-curve storage and updating are **roadmap** primitives: the data structure and expected-calibration-error metric are defined, but a conformant implementation is only required to expose the semantic-entropy signal and reserved hooks for calibration.

EP does not solve the industry-wide calibration problem. It makes the residual uncertainty honest, governable, and visible to downstream positioning.

---

## 1. Introduction

### 1.1 Motivation

Models do not reliably know what they do not know. That problem remains unsolved, and any protocol that pretends otherwise becomes less trustworthy, not more. CRP can, however, surface two partial, cheap signals that improve governance:

* **Calibration drift.** Over many verified outcomes, a model's confidence-versus-correctness curve becomes measurable. A model that is systematically overconfident on a task kind is a known, correctable risk.
* **Semantic entropy.** Clustering sampled answers by meaning — rather than by surface string — measures how much the model's reasoning paths disagree. It is one of the strongest cheap uncertainty estimators available, and CRP-SPEC-021 already produces the samples.

Both signals turn latent uncertainty into explicit protocol state.

### 1.2 Goals

1. Compute a normalised semantic-entropy score from self-consistency samples.
2. Define a per-model, per-task calibration profile and expected-calibration-error metric.
3. Wire entropy (and, when built, calibration) into CRP quality tiers, risk scores, and STL positioning hints.
4. Keep EP honest: never present entropy or calibration as a solved problem.

### 1.3 Non-Goals

- EP does not train, fine-tune, or modify model weights.
- It does not provide a definitive "the model is certain" verdict; it narrows the uncertainty gap.
- Calibration curves are not required to be populated in this version; the roadmap stage is stated explicitly.

### 1.4 Relationship to other specifications

EP consumes multi-sample reasoning output from CRP-SPEC-021, correctness labels from CRP-SPEC-005 and CRP-SPEC-049, and persists profiles through CRP-SPEC-009. It influences CRP-SPEC-026 quality tiers, CRP-SPEC-031 positioning, and CRP-SPEC-056 transparency events. It does not replace any of these; it adds an epistemic lens.

---

## 2. Terminology

**Semantic entropy.** Entropy computed over *meaning-clusters* of sampled answers, not over raw token strings. Two answers belong to the same cluster when they entail each other.

**Meaning-cluster.** A set of sampled answers that are mutually semantically equivalent under bidirectional entailment.

**Bidirectional entailment.** A symmetric equivalence test between two texts: `A` entails `B` and `B` entails `A`.

**Calibration profile.** A per-model, per-task-kind record that bins verified outcomes by the model's stated or implicit confidence.

**Expected calibration error (ECE).** The weighted average absolute gap between confidence and empirical accuracy across bins.

**Overconfidence threshold.** A configurable ECE value above which the system emits a positioning hint warning that the model is overconfident for the current task kind.

**Verified outcome.** A correctness label produced by the Decision Provenance Engine (CRP-SPEC-005) or the Verification Relay (CRP-SPEC-049).

---

## 3. Specification

### 3.1 Semantic entropy from self-consistency samples

EP consumes the `N` sampled answers produced by CRP-SPEC-021 (ROS) for a reasoning step. Samples are grouped into meaning-clusters, then entropy is computed over the cluster size distribution.

The algorithm is:

1. For each pair of samples `(a, b)`, decide whether `a` and `b` are semantically equivalent by testing bidirectional entailment.
2. Build clusters such that every member of a cluster is equivalent to the cluster's first member.
3. Compute `H = -sum(p_i * log(p_i))` where `p_i` is the fraction of samples in cluster `i`.
4. Normalise by `log(N)` when `N > 1`, yielding a score in the range `[0.0, 1.0]`. A value of `0.0` means all samples collapsed to one meaning; a value of `1.0` means every sample fell into a distinct meaning-cluster.

A reference implementation:

```python
# crp/ep/semantic_entropy.py — uncertainty from meaning-level divergence across samples
import math
from transformers import pipeline

_nli = pipeline("text-classification", model="microsoft/deberta-large-mnli", top_k=None)


def _equivalent(a: str, b: str) -> bool:
    ab = max(_nli(f"{a} [SEP] {b}"), key=lambda d: d["score"])["label"]
    ba = max(_nli(f"{b} [SEP] {a}"), key=lambda d: d["score"])["label"]
    return ab == "ENTAILMENT" and ba == "ENTAILMENT"  # bidirectional => same meaning


def semantic_entropy(samples: list[str]) -> float:
    clusters: list[list[str]] = []
    for s in samples:
        for c in clusters:
            if _equivalent(s, c[0]):
                c.append(s)
                break
        else:
            clusters.append([s])
    n = len(samples)
    probs = [len(c) / n for c in clusters]
    h = -sum(p * math.log(p) for p in probs)        # entropy over meaning-clusters
    return round(h / math.log(n) if n > 1 else 0.0, 3)  # normalised 0..1
```

Implementations MAY substitute a different NLI model or an equivalent semantic-equivalence test, provided the test is symmetric and meaning-based rather than string-based.

### 3.2 Calibration profile structure (roadmap)

The calibration component is specified structurally but is **not required to be implemented** in this version. A conformant implementation MUST reserve the profile schema and hook points so that future builds can populate curves without breaking existing sessions.

A calibration profile bins verified outcomes by confidence and computes ECE:

```python
# crp/ep/calibration.py — per-model, per-task calibration curves in the CKF
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class CalibrationProfile:
    model_id: str
    task_kind: str
    bins: dict = field(
        default_factory=lambda: defaultdict(lambda: [0, 0])  # conf_bin -> [correct, total]
    )

    def observe(self, confidence: float, correct: bool) -> None:
        b = round(confidence, 1)          # 0.0..1.0 in 0.1 bins
        self.bins[b][1] += 1
        if correct:
            self.bins[b][0] += 1

    def expected_calibration_error(self) -> float:
        total = sum(t for _, t in self.bins.values())
        if not total:
            return 0.0
        ece = 0.0
        for conf, (correct, n) in self.bins.items():
            if n:
                acc = correct / n
                ece += (n / total) * abs(acc - conf)
        return round(ece, 3)

    def overconfident_on(self, threshold: float = 0.15) -> bool:
        return self.expected_calibration_error() >= threshold
```

Only outcomes that have passed through DPE (CRP-SPEC-005) or VR (CRP-SPEC-049) MAY be written to the profile. Confidence values MUST be normalised to `[0.0, 1.0]`.

### 3.3 Applying entropy and calibration to tier, risk, and positioning

EP adjustments are advisory inputs to the quality tier, risk classification, and STL positioning hint.

A reference application function:

```python
# crp/ep/apply.py — wire calibration + entropy into tier, risk, and positioning
def epistemic_adjust(base_tier: str, risk: str, entropy: float, profile) -> dict:
    out = {"tier": base_tier, "risk": risk, "positioning_hint": None}
    if entropy > 0.6:                              # samples disagree in meaning
        out["risk"] = _raise(risk)                 # high semantic entropy => raise risk
        out["tier"] = _cap(base_tier, "B")         # and cap the tier
    if profile and profile.overconfident_on():
        out["positioning_hint"] = (
            f"{profile.model_id} is overconfident on {profile.task_kind}; "
            "apply stricter grounding thresholds"
        )
        out["risk"] = _raise(out["risk"])
    return out
```

The helpers `_raise` and `_cap` MUST be implemented in terms of the CRP risk and tier enumerations defined in CRP-SPEC-026 and CRP-SPEC-031. The entropy threshold `0.6` and the overconfidence threshold `0.15` are defaults; deployments MAY tune them through policy.

### 3.4 Entailment-equivalence contract

The semantic-equivalence relation used to build meaning-clusters MUST satisfy three properties:

1. **Symmetry.** `equivalent(a, b)` implies `equivalent(b, a)`.
2. **Reflexivity.** `equivalent(a, a)` is true.
3. **Transitivity approximation.** Because neural entailment models are not strictly transitive, implementations MUST document the model and any known failure modes. Clusters are built transitively through the first member of each cluster, which is sufficient for an uncertainty signal but not a formal equivalence proof.

Implementations MAY use an exact symbolic entailment engine when available; they MUST NOT use string identity, edit distance, or embedding cosine similarity alone.

### 3.5 Sampling and edge-case requirements

Semantic entropy is only meaningful when the input samples are independent reasoning paths for the same task:

- Samples SHOULD be generated with non-zero temperature or other diversity-inducing decoding.
- The sample count `N` SHOULD be at least `3`. If fewer than `2` samples are supplied, the normalised entropy is `0.0`.
- If all samples are empty or degenerate, entropy is `0.0` and a warning SHOULD be logged.
- Samples MUST be answers or conclusions, not full reasoning traces, so that clustering reflects output meaning rather than path variation.

---

## 4. Integration Points

### 4.1 Inputs

| Source spec | Data supplied |
|-------------|---------------|
| CRP-SPEC-021 (ROS) | Multiple sampled reasoning paths / answers for a single step. |
| CRP-SPEC-049 (VR) | Verified correctness labels and repair verdicts. |
| CRP-SPEC-005 (DPE) | Decision-provenance verdicts and confidence estimates. |
| CRP-SPEC-009 (CKF) | Persistent graph nodes for storing per-model, per-task calibration profiles. |

### 4.2 Outputs

| Consumer spec | Data consumed |
|---------------|---------------|
| CRP-SPEC-026 (SQB) | Semantic-entropy-adjusted quality tier and risk. |
| CRP-SPEC-031 (STL) | Positioning hint describing model blind spots or grounding advice. |
| CRP-SPEC-056 (TEL) | `crp.quality` event carrying tier, calibrated confidence, and semantic entropy. |

### 4.3 Placement in the pipeline

EP runs after sampling (CRP-SPEC-021) and after verification (CRP-SPEC-049), but before final tier/risk assignment and before STL re-positioning for the next operation. The recommended order for a governed reasoning step is:

1. Generate sampled reasoning paths.
2. Verify claims with VR.
3. Compute semantic entropy from samples.
4. Look up or initialise the calibration profile for `(model_id, task_kind)`.
5. Apply `epistemic_adjust` to tier and risk.
6. Emit adjusted values and any positioning hint to downstream consumers.

### 4.4 CKF node shape for calibration profiles

Calibration profiles are stored as CKF nodes keyed by `(model_id, task_kind)`. The node payload SHOULD include at minimum:

```json
{
  "model_id": "qwen3-coder-7b",
  "task_kind": "legal-reasoning",
  "bins": {
    "0.9": [12, 15],
    "1.0": [3, 7]
  },
  "expected_calibration_error": 0.183,
  "updated_at": "2026-08-08T10:00:00Z",
  "provenance": "audit://<session>/<window>/vr"
}
```

The `provenance` field MUST reference the HMAC-verified audit record that supplied the labels. Implementations MAY also store a sample-count floor below which the ECE is considered unreliable.

---

## 5. Conformance Requirements

A CRP-SPEC-055 conformant implementation MUST:

1. Compute semantic entropy over meaning-clusters using a bidirectional entailment or equivalent semantic-equivalence test, not surface-string equality.
2. Normalise the semantic-entropy score to `[0.0, 1.0]` when more than one sample is provided.
3. Wire semantic entropy into quality-tier and risk scoring, capping the tier and raising risk when entropy exceeds the configured threshold.
4. Reserve the calibration-profile schema, `observe`, and ECE computation hooks for future population.
5. Only update calibration profiles from verified outcomes (DPE/VR).
6. Surface an overconfidence positioning hint when a populated calibration profile's ECE exceeds the configured threshold.
7. Record all EP-derived adjustments in the audit trail (CRP-SPEC-011) or equivalent governance event stream.

A conformant implementation MUST NOT:

1. Present semantic entropy or calibration as a solution to the general calibration problem.
2. Use unverified, self-rated confidence to update calibration profiles.
3. Permit surface-string clustering to satisfy the semantic-entropy requirement.

At this roadmap stage, calibration-curve population and overconfidence detection are OPTIONAL. Implementations that do not yet build curves MUST still expose the reserved profile hooks and MUST document the omission in their conformance statement.

---

## 6. Security Considerations

### 6.1 Semantic-equivalence supply-chain integrity

Semantic-entropy computation depends on a semantic-equivalence model. If that model is poisoned, fine-tuned on misleading entailment pairs, or chosen from an untrusted source, EP can silently mis-cluster answers and suppress the uncertainty signal. Implementations MUST:

- Use a known, integrity-protected NLI or entailment model.
- Treat the NLI model as part of the governed supply chain, with version pinning and checksum verification where possible.
- Avoid exposing raw sample text in log events if those samples contain sensitive user data; emit only cluster counts, entropy, and normalised scores unless the disclosure policy (CRP-SPEC-006) explicitly permits more.
- Prevent EP signals from being used to auto-escalate to a frontier model. Escalation is a deployment configuration decision, not a protocol mechanism.

### 6.2 Calibration-profile integrity

Calibration profiles are long-lived CKF nodes. An attacker who can write false verified outcomes into a profile can distort its ECE and therefore the positioning hints. All writes MUST be integrity-checked and traceable to HMAC-verified audit records (CRP-SPEC-011).

Profile reads SHOULD also verify the node's integrity hash before use. Profile writes SHOULD require that the `correct` flag comes from a VR or DPE verdict whose own chain hash is present in the current session audit.

### 6.3 Disclosure and anti-gaming

Because EP exposes internal uncertainty and model weaknesses, the disclosure tier (CRP-SPEC-006) governs who may see entropy scores and calibration hints. End users SHOULD receive a coarse uncertainty indicator; operators and auditors MAY receive the full score and profile metadata. Implementations MUST ensure that the model cannot game the entropy signal by optimising for low-entropy output at the expense of correctness.

---

## 7. References

- CRP-SPEC-005: Decision Provenance Engine
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-009: Contextual Knowledge Fabric
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-021: ROS — Reasoning Orchestration & Synthesis
- CRP-SPEC-026: Semantic Quality Benchmark
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-049: Verification Relay
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
- CRP-SPEC-056: Transparency Emission Layer
