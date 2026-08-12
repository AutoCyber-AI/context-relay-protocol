# CRP-SPEC-050: The Quality-Tier-Supervised Router

**Document:** CRP-SPEC-050  
**Title:** Context Relay Protocol (CRP) — The Quality-Tier-Supervised Router:
Learned, Capability-Aware Dispatch with an Escalation Ladder  
**Version:** 6.0.0  
**Status:** Implemented (capability-profile fallback active); learned routing model is roadmap  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-006 (Safety Policy), CRP-SPEC-008 (Dispatch), CRP-SPEC-011 (Audit), CRP-SPEC-026 (Semantic Quality Benchmark), CRP-SPEC-031 (Semantic Task Layer), CRP-SPEC-049 (Verification Relay)

---

## Abstract

CRP dispatch (CRP-SPEC-008) decides which operation, tools, and reasoning depth to invoke for each call. In earlier protocol versions that decision was heuristic and its rationale was not explicitly audited. This specification defines the **Quality-Tier-Supervised Router (QSR)**, a dispatch component that is trained and evaluated using the quality labels CRP already produces as governance exhaust. The QSR re-uses three signals that are unique to CRP deployments: the quality tier produced by the Semantic Quality Benchmark (CRP-SPEC-026), the verification ratio produced by the Verification Relay (CRP-SPEC-049), and the provenance-verified audit chain (CRP-SPEC-011).

The QSR introduces:

1. **Free labelled training data** harvested from existing audit records: `(task features, routing decision, quality tier, verification verdict)`.
2. **Capability-aware routing** across heterogeneous local SLM fleets, using per-model capability profiles benchmarked through CRP-SPEC-026.
3. **An escalation ladder** expressed as a Safety-Policy Definition Language (SPDL) primitive: "try small, escalate only on observed failure signals".

**Implementation status.** In CRP v6.0 the capability-profile cold-start router, the schema-complexity ceiling guard, and the escalation-ladder SPDL directive are implemented and active. The learned classifier component is validated in evaluation scripts but is treated as a roadmap feature until a deployment has accumulated the minimum number of provenance-verified training examples and completed hold-out evaluation. Conformant implementations MUST therefore behave correctly in capability-profile fallback mode at all times; learned routing is OPTIONAL and MUST NOT be promoted to active dispatch until the cold-start thresholds and trust tests in §5 are satisfied.

---

## 1. Introduction

### 1.1 Motivation

The SLM-first design of CRP relies on heterogeneous specialist fleets rather than a single frontier model. A Qwen-class model may be strongest for code, a Phi-class model for math, and a Gemma-class model for prose. A right-sized specialist can outperform a general giant on cost, latency, and sometimes quality for narrow, repetitive tasks. The value of the fleet, however, depends entirely on the router.

CRP has three structural advantages over ad-hoc routing solutions such as RouteLLM:

- CRP already computes a **quality tier** for every completed dispatch (CRP-SPEC-026).
- CRP already computes a **verification ratio** for every verified window (CRP-SPEC-049).
- CRP already writes both results to a **tamper-evident audit chain** (CRP-SPEC-011).

Together these form free, continuously replenished training labels for a learned router. The QSR turns that exhaust into a self-improving flywheel: every dispatch becomes a labelled example that can be used to improve future routing decisions.

### 1.2 Goals

1. Replace heuristic dispatch with a measurable, auditable routing decision.
2. Use quality-tier labels and verification ratios as free supervision for a learned router.
3. Route to heterogeneous local SLM fleets using benchmark-derived capability profiles.
4. Provide a safe, policy-controlled escalation ladder from smaller to larger models when observed failure signals demand it.
5. Adapt tool schemas to the schema-complexity ceiling of the selected model before the tool-selection window is built.
6. Remain operational and correct in cold-start mode (no learned model) until sufficient trusted data has accumulated.

### 1.3 Non-Goals

- This specification does not train or fine-tune foundation models.
- It does not define automatic, opaque escalation to frontier models. Escalation is explicit, policy-controlled, and audited.
- It does not replace provider-specific dispatch adapters; it sits above them and selects the target model/worker.
- It does not introduce new logging requirements. All training data is a projection of records CRP already writes.

---

## 2. Terminology

**Quality-tier-supervised router (QSR):** The dispatch component defined by this specification. It selects the model and execution profile for a task using learned, capability-profile, or policy-driven logic.

**Routing example:** A single training tuple `(task features, routing decision, quality tier, verification verdict, latency, cost)` harvested from the audit chain.

**Capability profile:** A per-model record of measured competence by task kind, context-window size, schema-complexity ceiling, throughput, and cost. Profiles are derived from SQB benchmark runs, not from self-reported model metadata.

**Schema-complexity ceiling:** The maximum JSON schema nesting depth a model can reliably follow, expressed as an integer. A ceiling of `2` means schemas with more than two levels of nested objects must be flattened before the model is asked to emit them.

**Verification ratio (vr_ratio):** The fraction of claims or operations in a window that passed verification, as produced by CRP-SPEC-049. Values range from `0.0` to `1.0`.

**Escalation ladder:** An ordered list of models or rungs defined in SPDL policy. Dispatch tries the smallest eligible rung first and climbs only when observed failure signals cross policy thresholds.

**Failure signal:** An observed outcome that triggers escalation. The canonical signals are: quality tier below a policy threshold, verification ratio below a policy threshold, grounding score below a policy threshold, or self-consistency divergence above a policy threshold.

**Cold-start mode:** QSR operation before the learned classifier has been trained and promoted. Routing uses capability profiles and the escalation ladder only.

**Capability-profile fallback:** The required active path in CRP v6.0. The learned classifier may run in shadow or evaluation mode, but dispatch decisions that have not passed promotion gates MUST fall back to capability-profile routing.

---

## 3. Specification

### 3.1 Overview

The QSR is a pluggable dispatch selector invoked by the CRP Gateway or local orchestrator immediately before the provider adapter builds the final LLM request. Its inputs are:

- The task features produced by the Semantic Task Layer (CRP-SPEC-031).
- The candidate tool set produced by the Tool Capability Fabric (CRP-SPEC-050).
- The capability profiles of the available models/workers.
- The learned classifier, if it has been trained and promoted.
- The escalation policy from SPDL (CRP-SPEC-006).

Its outputs are:

- The selected `model_id`.
- The selected `capability_profile` (e.g. `small-local`, `capable-local`, `frontier`).
- The selected `execution_mode` (CRP-SPEC-049).
- The adapted tool schema, if the selected model's schema-complexity ceiling requires it.
- A routing decision record written to the audit chain.

### 3.2 Harvesting Training Tuples from the Audit Chain

Every completed dispatch already writes an audit record under stage `dispatch_complete` (CRP-SPEC-011). The QSR projects those records into routing examples without introducing new log events.

A routing example MUST contain at least the following fields:

| Field | Source | Description |
|-------|--------|-------------|
| `task_kind` | STL classification (CRP-SPEC-031) | The coarse task category, e.g. `code`, `math`, `prose`, `extract`. |
| `complexity` | Task analysis | `ENTITY_RICH`, `REASONING_DENSE`, or `NARRATIVE`. |
| `est_tokens` | Task analysis | Estimated prompt/tool tokens for the dispatch. |
| `tool_count` | Tool Capability Fabric | Number of tools selected for the operation frame. |
| `depth` | STL depth model | `quick`, `standard`, `thorough`, or `exhaustive`. |
| `model_id` | Dispatch decision | The model that executed the call. |
| `quality_tier` | SQB (CRP-SPEC-026) | `S`, `A`, `B`, `C`, or `D`. |
| `vr_ratio` | Verification Relay (CRP-SPEC-049) | Ratio of verified claims/operations. |
| `escalated` | Escalation ladder | `true` if the final result required escalation. |
| `latency_ms` | Audit record | End-to-end dispatch latency. |
| `cost` | Audit record | Normalised cost of the call. |

The example below illustrates the projection. Implementations MAY use equivalent data structures; the field semantics MUST remain identical.

```python
# crp/qsr/harvest.py — build router training data from the audit chain
from dataclasses import dataclass

@dataclass
class RoutingExample:
    # Features the router observes BEFORE dispatch.
    task_kind: str            # code / math / prose / extract ...
    complexity: str           # ENTITY_RICH | REASONING_DENSE | NARRATIVE
    est_tokens: int
    tool_count: int
    depth: str
    # Decision the router made.
    model_id: str
    # Labels generated after the call as governance exhaust.
    quality_tier: str         # S/A/B/C/D (CRP-SPEC-026)
    vr_ratio: float           # verification ratio (CRP-SPEC-049)
    escalated: bool
    latency_ms: int
    cost: float

def harvest(audit_records) -> list[RoutingExample]:
    out = []
    for r in audit_records:
        if r.get("stage") != "dispatch_complete":
            continue
        out.append(RoutingExample(
            task_kind=r["task"]["kind"],
            complexity=r["task"]["complexity"],
            est_tokens=r["task"]["est_tokens"],
            tool_count=len(r["task"]["tools"]),
            depth=r["task"]["depth"],
            model_id=r["decision"]["model_id"],
            quality_tier=r["result"]["tier"],
            vr_ratio=r["result"].get("vr_ratio", 1.0),
            escalated=r["result"].get("escalated", False),
            latency_ms=r["result"]["latency_ms"],
            cost=r["result"]["cost"]))
    return out
```

Implementations MUST only use audit records whose HMAC chain verifies. Poisoned, incomplete, or unverified records MUST be excluded from training.

### 3.3 Capability Profiles

Each model in the fleet MUST have a capability profile derived from a sealed SQB run (CRP-SPEC-026). The profile records measured competence, not vendor claims.

A capability profile MUST contain at least:

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | string | Stable identifier for the model or worker. |
| `competence` | map<string, float> | Measured mean quality per task kind, range `0.0`–`1.0`. |
| `ctx_window` | integer | Maximum context window in tokens. |
| `schema_complexity_ceiling` | integer | Maximum reliable JSON nesting depth. |
| `tokens_per_sec` | float | Observed generation throughput. |
| `cost_per_1k` | float | Normalised cost per 1K tokens; `0.0` for local inference. |

The example below is illustrative. Production deployments MUST use their own benchmark runs or the shared CRP model registry artefacts.

```python
# crp/qsr/profiles.py — per-model capability profiles (benchmark-derived)
from dataclasses import dataclass, field

@dataclass
class CapabilityProfile:
    model_id: str
    competence: dict[str, float] = field(default_factory=dict)
    ctx_window: int = 8192
    schema_complexity_ceiling: int = 3
    tokens_per_sec: float = 40.0
    cost_per_1k: float = 0.0

    def score_for(self, task_kind: str) -> float:
        return self.competence.get(task_kind, 0.5)

FLEET = {
    "qwen3-coder-7b": CapabilityProfile(
        "qwen3-coder-7b",
        {"code": 0.86, "math": 0.63, "prose": 0.55},
        ctx_window=32768,
        schema_complexity_ceiling=5),
    "phi4-math-4b": CapabilityProfile(
        "phi4-math-4b",
        {"code": 0.58, "math": 0.84, "prose": 0.60},
        schema_complexity_ceiling=3),
    "gemma3-4b": CapabilityProfile(
        "gemma3-4b",
        {"code": 0.52, "math": 0.55, "prose": 0.81},
        schema_complexity_ceiling=2),
}
```

A model MUST be excluded from eligibility for a task if its `ctx_window` is smaller than the estimated prompt tokens plus the requested max-output tokens, OR if its `schema_complexity_ceiling` is below the task's schema depth and schema adaptation (§3.6) is not applied.

### 3.4 Learned Router

The learned router maps task features to the model most likely to achieve tier `A` or better at the lowest cost. Before enough trusted examples accumulate, the router MUST remain in cold-start mode and route by capability profile.

Training and promotion MUST obey the following rules:

1. Only examples with provenance-verified audit records MAY be used.
2. Only examples whose `quality_tier` is `S` or `A` are used as positive training labels.
3. The minimum positive-example count for promotion is **200**. Implementations MAY configure a higher threshold, but MUST NOT configure a lower one.
4. Before promotion, the trained classifier MUST be evaluated on a held-out test set drawn from the same provenance-verified audit stream.
5. The hold-out evaluation MUST measure per-task-kind accuracy, per-tier recall, and the rate at which the router selects a model whose `schema_complexity_ceiling` is too low for the task.
6. A classifier that degrades average quality below the cold-start baseline MUST NOT be promoted.

The example below shows a minimal implementation. It is informative; conformant routers MAY use any classifier architecture that satisfies §5.

```python
# crp/qsr/router.py — learned, capability-aware router with cold-start fallback
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from crp.qsr.profiles import FLEET

class LearnedRouter:
    def __init__(self):
        self._clf: GradientBoostingClassifier | None = None
        self._models = list(FLEET.keys())

    def _featurize(self, task) -> list[float]:
        kinds = ["code", "math", "prose", "extract"]
        complexity = {"ENTITY_RICH": 0, "REASONING_DENSE": 1, "NARRATIVE": 2}
        depth = {"quick": 0, "standard": 1, "thorough": 2, "exhaustive": 3}
        return [
            *(1.0 if task.kind == k else 0.0 for k in kinds),
            complexity.get(task.complexity, 0),
            task.est_tokens / 1000.0,
            task.tool_count,
            depth.get(task.depth, 0),
        ]

    def train(self, examples) -> bool:
        good = [e for e in examples if e.quality_tier in ("S", "A")]
        if len(good) < 200:
            return False  # remain in cold-start mode
        X = [self._featurize_ex(e) for e in good]
        y = [self._models.index(e.model_id) for e in good]
        self._clf = GradientBoostingClassifier(max_depth=3).fit(np.array(X), y)
        return True

    def route(self, task) -> str:
        eligible = [
            m for m, p in FLEET.items()
            if p.schema_complexity_ceiling >= task.schema_depth
        ]
        if self._clf is not None:
            probs = self._clf.predict_proba([self._featurize(task)])[0]
            ranked = sorted(zip(self._models, probs), key=lambda t: -t[1])
            for model_id, _ in ranked:
                if model_id in eligible:
                    return model_id
        return max(eligible, key=lambda m: FLEET[m].score_for(task.kind))
```

A promoted classifier MAY be run in shadow mode alongside the capability-profile fallback. A routing decision produced by the classifier MUST NOT override the schema-complexity ceiling guard.

### 3.5 Escalation Ladder

The escalation ladder is an SPDL primitive that codifies "try small locally; escalate on observed failure signals". It is NOT a fixed retry loop. Escalation to the next rung is triggered only by observed failure signals, and it MUST respect `max_rungs`.

The SPDL policy schema is:

```yaml
# safety-policy.yaml extension for CRP-SPEC-050
escalation:
  escalate_on:
    tier_below: B
    vr_ratio_below: 0.9
    grounding_below: 0.8
    max_divergence: 0.3
  max_rungs: 2
  ladder:
    - local-small
    - local-specialist
    - cloud-large
```

`ladder` is an ordered list of model identifiers or capability-profile names. `max_rungs` limits how many times dispatch may climb. The first rung is chosen by the router; subsequent rungs are the remaining entries in `ladder` order.

The dispatch executor returns a result for each rung and tests the failure signals. If no failure signal fires, the result is accepted and `escalated` is reported as `true` if any climb occurred. If `max_rungs` is reached, the last result is accepted regardless of failure signals.

```python
# crp/qsr/escalation.py — escalate-on-failure ladder driven by SPDL
ESCALATION_LADDER = ["gemma3-4b", "qwen3-coder-7b", "cloud-large"]

def run_with_escalation(task, execute_fn, policy) -> dict:
    """
    policy example:
    {
      'escalate_on': {
        'tier_below': 'B',
        'vr_ratio_below': 0.9,
        'grounding_below': 0.8,
        'max_divergence': 0.3,
      },
      'max_rungs': 2,
    }
    """
    router = LearnedRouter()
    first = router.route(task)
    ladder = [first] + [m for m in ESCALATION_LADDER if m != first]
    rungs = 0
    for model_id in ladder:
        result = execute_fn(task, model_id)
        if not _should_escalate(result, policy) or rungs >= policy["max_rungs"]:
            result["escalated"] = rungs > 0
            return result
        rungs += 1
    result["escalated"] = True
    return result

def _should_escalate(result, policy) -> bool:
    triggers = policy.get("escalate_on", {})
    tier_ok = _tier_rank(result["tier"]) >= _tier_rank(triggers.get("tier_below", "D"))
    vr_ok = result.get("vr_ratio", 1.0) >= triggers.get("vr_ratio_below", 0.0)
    grounding_ok = result.get("grounding", 1.0) >= triggers.get("grounding_below", 0.0)
    divergence_ok = result.get("divergence", 0.0) <= triggers.get("max_divergence", 1.0)
    return not (tier_ok and vr_ok and grounding_ok and divergence_ok)

def _tier_rank(t):
    return {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}[t]
```

Escalation to a `cloud-large` or any non-local rung is a change in the data-governance posture. The audit record for such a dispatch MUST include a `trust_boundary_crossed` flag and the Transparency Emission Layer (CRP-SPEC-056) SHOULD surface it to the user.

### 3.6 Schema Adaptation

Small models fail on deep nested JSON schemas that frontier models handle naturally. When a selected model's `schema_complexity_ceiling` is below the task's schema depth, the QSR MUST transform the schema before it enters the operation frame built by CRP-SPEC-031.

Permitted transformations include:

- Flattening nested objects beyond the ceiling into dotted or natural-language field names.
- Replacing deep subtrees with a single string field that asks the model to describe the subtree in plain words.
- Constraining enums to smaller, task-relevant subsets via the Tool Capability Fabric.

```python
# crp/qsr/schema_adapt.py — flatten/simplify tool schemas per model capability
def adapt_schema(schema: dict, ceiling: int) -> dict:
    """Flatten nested objects beyond `ceiling` into natural-language fields."""
    def flatten(obj, prefix="", depth=0):
        out = {}
        for k, v in obj.get("properties", {}).items():
            name = f"{prefix}{k}"
            if v.get("type") == "object" and depth >= ceiling:
                nl = name.replace("_", " ")
                out[nl] = {
                    "type": "string",
                    "description": f"describe {nl} in plain words",
                }
            elif v.get("type") == "object":
                out.update(flatten(v, prefix=f"{name}.", depth=depth + 1))
            else:
                nl = name.replace("_", " ")
                out[nl] = v
        return out
    return {"type": "object", "properties": flatten(schema)}
```

Schema adaptation MUST preserve the semantic intent of the original tool and MUST be recorded in the audit chain so that downstream verification (CRP-SPEC-049) knows the schema was transformed.

### 3.7 Routing Decision Record

Every routing decision MUST be written back to the audit chain as a `dispatch_complete` record with the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| `qsr_version` | yes | Protocol version of the QSR component, e.g. `6.0.0`. |
| `router_mode` | yes | `capability-profile` or `learned`. |
| `selected_model` | yes | The model identifier returned by the router. |
| `selected_profile` | yes | Capability profile used, e.g. `small-local`. |
| `execution_mode` | yes | Execution mode from CRP-SPEC-049. |
| `task_features` | yes | The feature vector or object observed by the router. |
| `eligible_models` | yes | List of models that passed the capability-profile guard. |
| `schema_adapted` | yes | `true` if the tool schema was flattened for the selected model. |
| `escalated` | yes | `true` if the final result required escalation. |
| `failure_signals` | no | Signals that triggered escalation, if any. |

This record closes the flywheel: the next training harvest will include it as a labelled example.

---

## 4. Integration Points

### 4.1 CRP-SPEC-008 (Dispatch)

The QSR replaces or augments the heuristic router. The CRP dispatch layer MUST call `QSR.route(task)` and use the returned `model_id` and `execution_mode` when building the provider request. The dispatch layer MUST NOT override the schema-complexity ceiling guard.

### 4.2 CRP-SPEC-011 (Audit) and CRP-SPEC-026 (SQB)

The audit chain is both the input and the output of the QSR. The SQB quality tier is the primary training label. The QSR MUST NOT require any logging that CRP does not already perform.

### 4.3 CRP-SPEC-049 (Verification Relay)

The verification ratio is used both as a routing feature (models with low historical `vr_ratio` for a task kind are less likely to be selected) and as an escalation trigger after a call completes.

### 4.4 CRP-SPEC-031 (Semantic Task Layer)

The STL supplies `task_kind`, `complexity`, `depth`, and the operation frame. Schema adaptation runs between the QSR and the STL frame builder. The STL MUST honour the adapted schema and the selected `execution_mode`.

### 4.5 CRP-SPEC-006 (Safety Policy)

The escalation ladder, failure-signal thresholds, and `max_rungs` are SPDL directives. They are policy-controlled so that deployments can disable escalation entirely, cap it at local models only, or require explicit human approval for cloud rungs.

### 4.6 CRP-SPEC-056 (Transparency Emission Layer)

When escalation crosses a trust boundary (e.g. from local to cloud), the Transparency Emission Layer MUST surface the boundary change to the user interface and the audit consumer.

---

## 5. Conformance Requirements

To be **CRP-SPEC-050 conformant**, an implementation MUST satisfy all of the following requirements.

### 5.1 Capability-Profile Mode (Required)

1. The implementation MUST maintain capability profiles for every model in the fleet.
2. Each profile MUST be derived from sealed SQB benchmark runs or equivalent trusted measurement, not from self-reported model metadata.
3. The router MUST fall back to capability-profile mode whenever the learned classifier is unavailable, untrained, or not promoted.
4. In capability-profile mode, the router MUST select the eligible model with the highest competence score for the task kind.

### 5.2 Schema-Complexity Guard (Required)

1. The implementation MUST compute or receive the schema depth required by the selected tools.
2. The implementation MUST exclude models whose `schema_complexity_ceiling` is below the required schema depth unless schema adaptation is applied.
3. If schema adaptation is applied, the implementation MUST record `schema_adapted: true` in the routing decision record.

### 5.3 Learned Router (Optional, with Promotion Gates)

1. The learned router MAY be implemented as a shadow evaluator.
2. The learned router MUST NOT be used for live dispatch until it has been trained on at least **200** positive (tier `S` or `A`) provenance-verified examples.
3. The learned router MUST be evaluated on a held-out test set before promotion.
4. A promoted learned router MUST NOT degrade the average quality tier below the capability-profile cold-start baseline.
5. If a promoted learned router degrades during operation, the implementation MUST automatically fall back to capability-profile mode and raise an observability event.

### 5.4 Escalation Ladder (Required when escalation is enabled)

1. If escalation is enabled in SPDL policy, the implementation MUST support an ordered ladder of rungs.
2. Escalation MUST be triggered only by observed failure signals, not by a fixed retry count.
3. The implementation MUST respect `max_rungs`.
4. The implementation MUST record every escalation rung and the triggering signal in the audit chain.
5. Escalation that crosses a trust boundary MUST set `trust_boundary_crossed: true` in the audit record.

### 5.5 Audit Flywheel (Required)

1. Every routing decision MUST be written to the audit chain.
2. The audit record MUST be sufficient to reconstruct a routing example for training.
3. Training harvests MUST only use records whose HMAC chain verifies.

### 5.6 Header and Session Behaviour

The QSR does not define new CRP HTTP headers. It sets the following existing fields for downstream CRP components:

- `CRP-Agent-Capability-Profile` (CRP-SPEC-049): selected profile.
- `CRP-Agent-Execution-Mode` (CRP-SPEC-049): selected execution mode.
- `CRP-Agent-Tool-Subset` (CRP-SPEC-049): the adapted tool subset.

All CRP headers remain subject to Axiom 4: they MUST be stripped before forwarding to the LLM provider.

---

## 6. Security Considerations

### 6.1 Training-Data Poisoning

The QSR is trained on audit data. If an adversary can inject audit records or induce spuriously high quality tiers, they can bias routing. Implementations MUST:

- Use only provenance-verified audit records (CRP-SPEC-011 HMAC chain) for training.
- Reject records whose chain integrity is `BROKEN`.
- Hold out a trusted evaluation set to detect distribution shift or poisoning before promoting a new router.

### 6.2 Capability-Profile Trust

Capability profiles MUST be derived from sealed SQB runs, not from self-reported model metadata. A model that claims a high competence score but has not been benchmarked MUST be treated as unmeasured and assigned a default competence score no higher than `0.5` for all task kinds.

### 6.3 Escalation Boundaries

Escalation to a non-local or cloud rung changes the data-governance and compliance posture of the call. Implementations MUST:

- Re-apply the full Decision Provenance Engine and safety policy envelope after crossing a trust boundary.
- Surface the boundary change via the Transparency Emission Layer (CRP-SPEC-056).
- Allow SPDL policy to disable cloud escalation entirely or require explicit human approval.

### 6.4 Privacy

Routing examples contain task metadata but SHOULD NOT contain user content. Implementations MUST NOT include raw prompts, user messages, or tool outputs in training examples unless those examples are subject to the same retention and erasure policies as the underlying audit records.

### 6.5 Denial of Service

A slow or failing model can block the escalation ladder. Implementations MUST:

- Apply per-rung timeouts.
- Apply `max_rungs` strictly.
- Fall back to capability-profile mode if the learned router becomes computationally expensive relative to the cold-start baseline.

---

## 7. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-007: Session Token
- CRP-SPEC-008: Dispatch and Provider Adaptation
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-016: Gateway Service
- CRP-SPEC-026: Semantic Quality Benchmark
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-049: Verification Relay
- CRP-SPEC-056: Transparency Emission Layer
