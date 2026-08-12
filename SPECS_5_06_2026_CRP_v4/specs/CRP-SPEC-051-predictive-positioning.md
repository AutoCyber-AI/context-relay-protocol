# CRP-SPEC-051: Predictive Positioning & World-Model Induction

**Document:** CRP-SPEC-051  
**Title:** Predictive Positioning — World-Model Rule Induction over the
Action Log, Causal CKF Edges, and Simulation-Before-Action  
**Version:** 6.0.0  
**Status:** Roadmap (Wave 3 frontier)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-006 (Safety Policy), CRP-SPEC-009 (Contextual Knowledge Fabric), CRP-SPEC-011 (Audit Trail), CRP-SPEC-029 (Tier-E Action Log), CRP-SPEC-031 (Semantic Task Layer), CRP-SPEC-033 (Safety Control Plane), CRP-SPEC-056 (Transparency Emission Layer)

---

## Abstract

A knowledge graph of extracted facts (CRP-SPEC-009) is a *descriptive* model; strong agentic understanding requires a *predictive* model that anticipates the consequences of an action before it is taken. This specification defines **predictive positioning**: the induction of a lightweight world model from CRP's event-sourced Tier-E action log (CRP-SPEC-029). The world model takes the form of symbolic transition rules `(state_pattern, action) → outcome_pattern`, learned from actions the fleet has already taken. It adds **causal edge types** (`causes`, `enables`, `prevents`) to the Contextual Knowledge Fabric for counterfactual retrieval, and a **simulation-before-action** check for HIGH-risk operations that predicts the outcome against the rule set and causal graph before dispatch. This turns human oversight from reactive into *anticipatory* and is the protocol-level bridge from descriptive context to predictive agent understanding.

This specification is **Wave 3 frontier** work: it is research-credible, depends on the enriched action log, and is intended for deployment only after the positioned tool loop (CRP-SPEC-031), the safety control plane (CRP-SPEC-033), and Tier-E logging (CRP-SPEC-029) are mature.

---

## 1. Terminology

**Action log (Tier-E):** The event-sourced record of every tool invocation, its precondition state, and its observed postcondition state, as defined by CRP-SPEC-029.

**Transition:** A single Tier-E record of the form `(pre_state, action, post_state)`.

**Transition rule:** A symbolic pattern of the form `(action, condition) → predicts`, where `condition` is a set of state-feature preconditions and `predicts` is a set of outcome features that hold with at least the configured confidence across observed transitions.

**World model:** A queryable index of transition rules used to predict the outcome of a proposed action from the current state.

**Predictive positioning:** The practice of enriching an agent's operation frame with predicted outcomes from the world model, not only with retrieved facts.

**Causal edge:** A CKF edge typed `causes`, `enables`, or `prevents`, representing a directed influence relationship between two entities or facts.

**Interventional support:** The number of action-log transitions in which an action reliably preceded an outcome change, treated as causal evidence stronger than textual co-occurrence.

**Simulation-before-action:** A HIGH-risk safety gate that queries the world model for the predicted outcome of an action and, if the prediction violates policy at sufficient confidence, diverts to a human-in-the-loop checkpoint rather than executing.

**Neural fallback:** An optional learned predictor used when no symbolic rule matches, aligned to the symbolic rule layer rather than replacing it.

---

## 2. Specification

### 2.1 Transition Rule Induction

Each Tier-E record is a transition `(pre_state, action, post_state)`. Rule induction abstracts these into reusable patterns: which state features, under which action, predict which outcome features. The baseline induction is rule-based and gradient-free, prioritising sample efficiency and inspectability.

A conformant implementation MUST support rule induction with the following semantics:

- Rules are grouped by `(action, frozenset of pre_state features)`.
- For each group, outcome features that hold in at least `min_conf` fraction of transitions are retained as predictions.
- Each rule records its `support` count, `confidence`, source action, precondition, and predicted outcome.
- Rules whose support is below the configured minimum MUST NOT be used to gate actions.

```python
# crp/pp/induction.py — induce (state_pattern, action) -> outcome_pattern rules from Tier-E
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Transition:
    pre: dict            # state features before (e.g. {"host_up": True, "port_22": "closed"})
    action: str          # the tool action taken (e.g. "port_scan:stealth")
    post: dict           # observed outcome features


@dataclass
class Rule:
    action: str
    condition: dict      # state-feature preconditions
    predicts: dict       # predicted outcome features
    support: int = 0     # how many transitions support it
    confidence: float = 0.0


def induce_rules(transitions: list[Transition], min_support=5, min_conf=0.8) -> list[Rule]:
    # group by (action, frozenset of pre-features) -> outcome distribution
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for t in transitions:
        key = (t.action, frozenset(t.pre.items()))
        buckets[key].append(t.post)
    rules = []
    for (action, pre_items), posts in buckets.items():
        if len(posts) < min_support:
            continue
        # find outcome features that hold in >= min_conf of cases (the prediction)
        feature_counts = defaultdict(int)
        for post in posts:
            for k, v in post.items():
                feature_counts[(k, v)] += 1
        predicted = {k: v for (k, v), c in feature_counts.items()
                     if c / len(posts) >= min_conf}
        if predicted:
            conf = min(feature_counts[(k, v)] / len(posts) for k, v in predicted.items())
            rules.append(Rule(action=action, condition=dict(pre_items),
                              predicts=predicted, support=len(posts), confidence=round(conf, 3)))
    return rules
```

### 2.2 Predictive World Model

Given a proposed action and the current state, the world model predicts the outcome by matching against induced rules. This is the core of predictive positioning: the agent is positioned not only with what is true, but with what the model expects to happen.

```python
# crp/pp/world_model.py — predict outcomes; align with a neural fallback (WALL-E-style)
from crp.pp.induction import Rule


class WorldModel:
    def __init__(self, rules: list[Rule]):
        # index rules by action for fast lookup
        self._by_action: dict[str, list[Rule]] = {}
        for r in rules:
            self._by_action.setdefault(r.action, []).append(r)

    def predict(self, state: dict, action: str) -> dict | None:
        """Return predicted outcome features + confidence, or None if no rule matches."""
        best = None
        for r in self._by_action.get(action, []):
            if all(state.get(k) == v for k, v in r.condition.items()):   # precondition holds
                if best is None or r.confidence > best.confidence:
                    best = r
        if best:
            return {"predicted": best.predicts, "confidence": best.confidence,
                    "support": best.support, "source": "symbolic_rule"}
        return None      # caller MAY fall back to a neural predictor (see §2.5)
```

A prediction returned by the world model MUST include:

- `predicted`: the predicted outcome features.
- `confidence`: the empirical confidence of the matched rule.
- `support`: the number of transitions supporting the rule.
- `source`: the origin of the prediction (symbolic rule or neural fallback).

### 2.3 Causal Edges in the CKF

This specification adds the causal edge types `causes`, `enables`, and `prevents` to the Contextual Knowledge Fabric (CRP-SPEC-009). These edges are populated by the LLM-assisted extraction stage when it encounters causal language, and are strengthened by interventional support from the action log. Because agent actions are interventions on the environment, an action reliably followed by an outcome is stronger causal evidence than textual co-occurrence alone.

```python
# crp/pp/causal_ckf.py — causal edges + counterfactual (causal-upstream) retrieval
from enum import Enum


class CausalEdge(str, Enum):
    CAUSES = "causes"
    ENABLES = "enables"
    PREVENTS = "prevents"


def add_causal_edge(ckf, src: str, dst: str, kind: CausalEdge,
                    textual_conf: float, interventional_support: int = 0):
    # interventional support = # of action-log transitions where doing src changed dst
    # this is the key move: agent actions are interventions, so this is causal evidence
    conf = min(1.0, textual_conf + 0.1 * interventional_support)
    ckf.add_edge(src, dst, type=kind.value, confidence=conf,
                 evidence={"textual": textual_conf, "interventional": interventional_support})


def causal_upstream(ckf, node: str, max_depth=3) -> list[dict]:
    """Counterfactual retrieval: what is causally upstream of `node`? (CDGR causal-walk)"""
    frontier, seen, out = [(node, 0)], set(), []
    while frontier:
        n, d = frontier.pop()
        if n in seen or d > max_depth:
            continue
        seen.add(n)
        for edge in ckf.in_edges(n, types=[CausalEdge.CAUSES.value, CausalEdge.ENABLES.value]):
            out.append({"cause": edge.src, "effect": n, "kind": edge.type, "conf": edge.confidence})
            frontier.append((edge.src, d + 1))
    return out
```

Causal edges MUST keep textual and interventional evidence separate. A purely textual causal edge MUST NOT be presented or stored as verified causality.

### 2.4 Simulation-Before-Action

For operations the safety policy tags HIGH, the runtime MUST predict the outcome before executing. If the prediction violates policy at or above the configured confidence floor, the runtime MUST divert to a human-in-the-loop checkpoint instead of acting. This unifies the world model with the Safety Control Plane (CRP-SPEC-033) and makes oversight anticipatory.

```python
# crp/pp/simulate.py — predict-then-gate for HIGH-risk actions (anticipatory oversight)
from crp.pp.world_model import WorldModel


def guarded_dispatch(state: dict, action: str, risk: str,
                     world: WorldModel, policy, execute_fn, checkpoint_fn):
    pred = None
    if risk == "HIGH":
        pred = world.predict(state, action)
        if pred:
            violation = policy.check_predicted_outcome(pred["predicted"])   # CRP-SPEC-006 eval
            if violation and pred["confidence"] >= policy.sim_confidence_floor:
                # the world model predicts a policy-violating outcome -> don't act; ask a human
                return checkpoint_fn(reason=f"predicted {violation} "
                                     f"(conf {pred['confidence']}, n={pred['support']})",
                                     prediction=pred)
        # no confident prediction of harm -> proceed, but record the prediction for audit
    return execute_fn(state, action, prediction=pred if risk == "HIGH" else None)
```

The simulation-before-action policy is configured through the existing Safety Policy (CRP-SPEC-006):

```yaml
# safety-policy.yaml (CRP-SPEC-006 extension)
predictive_positioning:
  simulate_risk_levels: [HIGH]        # which risk tiers get simulation-before-action
  sim_confidence_floor: 0.75          # only block on predictions at/above this confidence
  neural_fallback: true               # if no symbolic rule matches, query neural predictor
  induction_schedule: nightly         # re-induce rules from the growing action log
```

A conformant implementation MUST:

- Run simulation-before-action for every operation whose risk tier is listed in `simulate_risk_levels`.
- Fail *open to a checkpoint* (human oversight) when a policy-violating outcome is predicted with sufficient confidence.
- Never fail *closed to silent execution* and never fail *open to silent skipping*.
- Record the prediction, the matched rule, and any checkpoint outcome in the audit chain.

### 2.5 Neural Fallback (Optional)

When no symbolic rule matches, a conformant implementation MAY use an aligned neural predictor as a fallback. In this hybrid design, symbolic rules act as an energy term that corrects the neural distribution in structured domains. The neural fallback is optional and depth/risk-gated; the symbolic layer alone already delivers the compliance and safety value. Implementations that enable the neural fallback MUST declare it in predictions via `source: "neural_fallback"` and MUST still gate on confidence.

---

## 3. Integration Points

- **CRP-SPEC-029 (Tier-E Action Log):** The action log is the training data. Rule induction is a scheduled pass over existing Tier-E records; no new logging surface is required.

- **CRP-SPEC-009 (Contextual Knowledge Fabric):** Causal edges are new CKF edge types. Counterfactual retrieval is a causal-walk variant of Context Differential Graph Retrieval (CRP-SPEC-025).

- **CRP-SPEC-031 (Semantic Task Layer):** Predictions enrich the operation frame ("what will happen") alongside facts ("what is true"). STL selects operations; the world model informs the expected outcome of those operations.

- **CRP-SPEC-033 (Safety Control Plane):** Simulation-before-action hooks the existing HIGH-risk checkpoint path. It adds a *predicted-outcome* trigger to the existing *observed-outcome* triggers.

- **CRP-SPEC-006 (Safety Policy):** Which risk levels simulate, the confidence floor, the induction schedule, and whether a neural fallback is permitted are all policy-controlled.

- **CRP-SPEC-011 (Audit Trail):** Predictions used to gate actions, and any anticipatory checkpoint, MUST be written to the tamper-evident audit chain with their supporting rule.

- **CRP-SPEC-056 (Transparency Emission Layer):** Predicted outcomes and anticipatory checkpoints SHOULD be streamable as governance events (e.g. "the agent predicted this would breach scope, so it paused").

---

## 4. Conformance Requirements

A CRP predictive-positioning conformant implementation MUST satisfy all of the following:

1. **Rule quality.** Induced rules MUST record support count and confidence. A rule with support below the configured minimum MUST NOT be used to block or gate an action.

2. **Simulation coverage.** Simulation-before-action MUST run for every operation at a configured HIGH-risk level.

3. **Fail-open to human oversight.** When simulation predicts a policy-violating outcome with confidence at or above `sim_confidence_floor`, the implementation MUST escalate to a checkpoint (human oversight). It MUST NOT silently execute or silently skip the action.

4. **Causal evidence separation.** Causal edges in the CKF MUST distinguish textual evidence from interventional evidence. A purely textual causal edge MUST NOT be presented as verified causality.

5. **Auditability.** Predictions used to gate actions MUST be written to the audit chain, including the supporting rule, its support, its confidence, and the policy violation (if any). Anticipatory checkpoint outcomes MUST likewise be recorded.

6. **Induction provenance.** Rule induction MUST run only over provenance-verified Tier-E records (CRP-SPEC-011). It SHOULD weight by identity trust and SHOULD flag rules whose support comes from a narrow set of sessions.

7. **Optional fallback declaration.** If a neural fallback is used, predictions MUST identify `source: "neural_fallback"`, and the same confidence-floor and audit rules apply.

8. **No silent policy override.** Predictions inform oversight; they do not replace it. A missing prediction MUST NOT be interpreted as safety clearance.

---

## 5. Security Considerations

Two cautions apply to predictive positioning because overclaiming here is both a technical and a reputational risk.

**Textual causality is not verified causality.** Causal edges extracted from text report causal language, not experimentally verified causality. Only interventional support from the action log is genuine causal evidence, and even that assumes the logged action was the operative intervention. Implementations MUST keep the two evidence types separate and MUST NOT present textual causality as verified.

**A poisoned action log poisons the world model.** An adversary who can inject misleading transitions could teach the model that a harmful action is safe. Rule induction MUST therefore:

- Run only over provenance-verified Tier-E records (CRP-SPEC-011).
- Weight transitions by identity trust where available.
- Flag rules whose support comes from a narrow set of sessions, which may indicate poisoning.

The world model is a safety aid that can itself be attacked. Its predictions inform oversight; they do not replace the Safety Control Plane or policy enforcement.

---

## 6. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-009: Contextual Knowledge Fabric
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-025: Context Differential Graph Retrieval
- CRP-SPEC-029: Tier-E Action Log
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-033: Safety Control Plane
- CRP-SPEC-056: Transparency Emission Layer

External references:

- Neurosymbolic world-model alignment literature (WALL-E line of work): symbolic rules aligned to environment dynamics as gradient-free world models.
- Hybrid neurosymbolic prediction literature: symbolic rules used as an energy term over neural distributions for structured-dynamics domains.
