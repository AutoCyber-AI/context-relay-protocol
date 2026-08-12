# CRP-SPEC-049: The Verification Relay

**Document:** CRP-SPEC-049  
**Title:** The Verification Relay — Step-Level Reasoning Verification  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;and Symbolic Verifier Dispatch  
**Version:** 6.0.0  
**Status:** Implemented (symbolic verifiers active; PRM model trained and wired as advisory scorer)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-004 (Continuation and State Relay), CRP-SPEC-005 (Decision Provenance Engine), CRP-SPEC-006 (Safety Policy Directive Language), CRP-SPEC-008 (Dispatch and Provider Adaptation), CRP-SPEC-011 (Audit Trail), CRP-SPEC-021 (Reasoning Orchestration and Synthesis), CRP-SPEC-026 (Semantic Quality Benchmark), CRP-SPEC-033 (Safety Control Plane / Inline HITL)

---

## Abstract

The Decision Provenance Engine (CRP-SPEC-005) verifies model output *against sources* — that is, grounding. It does not verify *inference against logic*. A model can cite every fact correctly and still draw an invalid conclusion. This specification defines the **Verification Relay (VR)**: a 14th stage of the DPE that scores each reasoning step for logical validity, together with a set of **symbolic verifier dispatch targets** invoked through an LLM-Modulo generate-critique-repair loop.

The relay unifies two verifier families:

1. **Symbolic verifiers** — an SMT solver for arithmetic/constraint claims, and a sandboxed executor for computational claims. These are *sound*: a `VALID` verdict is a proof and carries confidence `1.0`.
2. **Probabilistic verifiers** — a small Process Reward Model (PRM) that scores entailment for inference steps that are not formally checkable. The PRM is trained and wired as an **advisory scorer**, not as a sound verifier.

Verification results feed the quality tier (CRP-SPEC-026) and risk score, and the whole probabilistic stage is **depth-gated** (CRP-SPEC-006) so its cost is paid only where the policy or task depth demands it.

---

## 1. Terminology

**Claim**  
A single reasoning step or checkable assertion extracted from an agent trace. A claim carries a natural-language statement, a `kind` (inference, arithmetic, temporal, constraint, fact), the premises it depends on, and an optional formal representation.

**Verifier**  
Any component that accepts a `Claim` and returns a `VerificationResult`. Verifiers implement a common protocol so that the relay can dispatch to them uniformly.

**Verdict**  
The outcome of a verification attempt:

- `valid` — the verifier affirms the step or claim;
- `invalid` — the verifier refutes it, supplying a machine- or human-readable critique that can drive repair;
- `unknown` — the verifier cannot decide, usually because the claim is outside its decidable domain.

**Symbolic verifier**  
A deterministic, sound verifier that operates over formal representations. Examples defined in this specification are an SMT-based verifier (Z3) and a sandboxed executor. Symbolic verdicts carry confidence `1.0`.

**Process Reward Model (PRM)**  
A small classifier (typically 0.5–1.5 B parameters) trained to score whether a reasoning step is entailed by its premises. It is advisory and *not* sound; its confidence is strictly less than `1.0`.

**Verification Relay**  
The orchestrator that runs verifiers over a reasoning trace and, when a verifier returns `invalid`, feeds the critique back to the model to regenerate the claim. This generate-critique-repair loop is the CRP realisation of the LLM-Modulo pattern.

**Depth-gating**  
Policy-controlled activation of the probabilistic verifier based on task depth (for example, `thorough` or `exhaustive`). Symbolic verifiers are cheap enough to run unless explicitly disabled by policy.

**LLM-Modulo loop**  
An architecture in which an LLM generates candidate outputs and an external sound verifier critiques them until a valid result is produced or a repair budget is exhausted.

---

## 2. Specification

### 2.1 Common verifier interface

All verifiers — probabilistic and symbolic — implement a single interface. This lets the relay dispatch to them uniformly and lets new verifiers be added as CRP-SPEC-008 dispatch targets without modifying the relay.

```python
# crp/vr/interface.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Verdict(str, Enum):
    VALID = "valid"       # verifier affirms the step/claim
    INVALID = "invalid"   # verifier refutes it (with a reason)
    UNKNOWN = "unknown"   # verifier cannot decide (not in its domain)


@dataclass
class VerificationResult:
    verdict: Verdict
    confidence: float          # 1.0 for sound symbolic verifiers; <1 for PRM
    reason: str                # machine- or human-readable critique (drives repair)
    verifier: str              # which verifier produced this (audit)
    checkable: bool            # was this claim in the verifier's decidable domain?


class Verifier(Protocol):
    name: str

    def applies(self, claim: "Claim") -> bool:
        """Domain gate: is this claim within the verifier's decidable class?"""
        ...

    def verify(self, claim: "Claim", context: dict) -> VerificationResult:
        ...


@dataclass
class Claim:
    """A single reasoning step or checkable assertion extracted from the trace."""
    text: str
    kind: str                  # "inference" | "arithmetic" | "temporal" | "constraint" | "fact"
    premises: list[str]        # prior steps / facts this claim depends on
    formal: dict | None = None # optional pre-parsed formal representation
```

A conformant implementation MUST NOT bypass the interface when adding a new verifier. The interface is the protocol boundary between the relay and verifier dispatch targets.

### 2.2 Symbolic verifier — SMT for constraints and arithmetic

For claims reducible to logical or arithmetic constraints, the relay dispatches to an SMT solver. This verifier is *sound*: a `VALID` verdict constitutes a proof, and the returned confidence MUST be `1.0`.

```python
# crp/vr/z3_verifier.py — sound verification of arithmetic & logical constraints
import z3
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim


class Z3Verifier:
    name = "z3-smt"

    def applies(self, claim: Claim) -> bool:
        return claim.kind in ("arithmetic", "constraint") and claim.formal is not None

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        # claim.formal example:
        # {"vars": {"x": "Int"}, "assert": ["x > 0", "x < 5"], "claim": "x != 3"}
        s = z3.Solver()
        env = {}
        for name, ty in claim.formal["vars"].items():
            env[name] = z3.Int(name) if ty == "Int" else z3.Real(name)
        for a in claim.formal["assert"]:
            s.add(eval(a, {"__builtins__": {}}, env))          # premises
        # To prove `claim` follows, check that premises ∧ ¬claim is UNSAT
        s.add(z3.Not(eval(claim.formal["claim"], {"__builtins__": {}}, env)))
        r = s.check()
        if r == z3.unsat:      # ¬claim is impossible given premises => claim is entailed
            return VerificationResult(
                Verdict.VALID, 1.0, "entailed (proof)", self.name, True
            )
        elif r == z3.sat:      # a counter-model exists => claim does NOT follow
            return VerificationResult(
                Verdict.INVALID, 1.0, f"counterexample: {s.model()}", self.name, True
            )
        return VerificationResult(
            Verdict.UNKNOWN, 0.0, "solver undecided", self.name, True
        )
```

The SMT verifier MUST be invoked only when `claim.formal` is present and parseable. The formal expression MUST be produced from a constrained grammar (CRP-SPEC-054) and MUST NOT be constructed by direct interpolation of raw model text.

### 2.3 Symbolic verifier — sandboxed executor for computational claims

For claims that are pure computations (for example, "the scan covered 254 hosts" or "the total is $4,812"), the relay dispatches to a locked-down subprocess. The same sandbox discipline that governs tool execution applies: no network, no filesystem access beyond explicitly supplied inputs, and resource-capped execution.

```python
# crp/vr/exec_verifier.py — verify computational claims by deterministic execution
import json
import subprocess
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim


class ExecVerifier:
    name = "sandboxed-exec"

    def applies(self, claim: Claim) -> bool:
        return claim.kind == "arithmetic" and claim.formal and "expr" in claim.formal

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        # claim.formal: {"expr": "254 * 3", "expected": 762}
        code = f"import json;print(json.dumps({claim.formal['expr']}))"
        try:
            out = subprocess.run(
                ["python3", "-I", "-c", code],           # -I: isolated, no env/site
                capture_output=True, text=True, timeout=2,
                env={"PATH": "/usr/bin"},                 # minimal env; no network by sandbox policy
            )
            actual = json.loads(out.stdout.strip())
        except Exception as e:
            return VerificationResult(
                Verdict.UNKNOWN, 0.0, f"exec error: {e}", self.name, True
            )
        expected = claim.formal["expected"]
        if actual == expected:
            return VerificationResult(
                Verdict.VALID, 1.0, f"{actual}=={expected}", self.name, True
            )
        return VerificationResult(
            Verdict.INVALID, 1.0,
            f"computed {actual}, claim said {expected}", self.name, True
        )
```

The executor MUST run in an isolated interpreter, MUST NOT inherit the parent environment, and MUST be subject to a strict timeout and resource cap. Execution of agent-controlled strings MUST pass through the same trusted-gate discipline applied to tool argument construction.

### 2.4 Probabilistic verifier — Process Reward Model (DPE stage 14)

For inference steps that are *not* formally checkable, the relay scores logical entailment with a small fine-tuned classifier. This is the process-supervision stage. It is depth-gated because it costs a model call per step.

```python
# crp/vr/prm.py — step-level reasoning verification (DPE stage 14)
from transformers import pipeline
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim


class ProcessRewardVerifier:
    """A small (0.5-1.5B) classifier scoring: is this step entailed by its premises?
    Train on step-level labels harvested from VR's own symbolic verdicts (the flywheel)."""
    name = "prm"

    def __init__(self, model="autocyber/crp-prm-deberta-v1", threshold=0.5):
        self._clf = pipeline("text-classification", model=model, top_k=None)
        self._threshold = threshold

    def applies(self, claim: Claim) -> bool:
        return claim.kind == "inference"     # the non-formal steps

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        premises = " ".join(claim.premises)
        scores = {
            d["label"]: d["score"]
            for d in self._clf(f"premises: {premises} [SEP] step: {claim.text}")
        }
        p_valid = scores.get("VALID", 0.0)
        if p_valid >= self._threshold:
            return VerificationResult(
                Verdict.VALID, p_valid, "step-reward above threshold",
                self.name, checkable=False
            )
        return VerificationResult(
            Verdict.INVALID, 1.0 - p_valid,
            "step not entailed by prior steps", self.name, checkable=False
        )
```

The PRM is wired as an **advisory scorer**. Its confidence MUST be strictly less than `1.0`. A PRM verdict MUST NOT be treated as a proof. The PRM SHOULD be trained on labels harvested from symbolic verdicts so that the symbolic verifiers bootstrap the probabilistic verifier over time.

### 2.5 Verification Relay — generate-critique-repair

The Verification Relay orchestrates verifiers over a reasoning trace and feeds `INVALID` critiques back to the model to regenerate the claim. The loop reuses the continuation engine (CRP-SPEC-004) and is bounded by a configurable repair budget.

```python
# crp/vr/relay.py — the Verification Relay: dispatch verifiers, repair, feed quality/risk
from crp.vr.interface import Verdict, Claim, VerificationResult
from crp.vr.z3_verifier import Z3Verifier
from crp.vr.exec_verifier import ExecVerifier
from crp.vr.prm import ProcessRewardVerifier


class VerificationRelay:
    def __init__(self, max_repairs: int = 2):
        # symbolic verifiers first (sound, cheap, certain); PRM last (probabilistic)
        self.verifiers = [Z3Verifier(), ExecVerifier(), ProcessRewardVerifier()]
        self.max_repairs = max_repairs

    def _verify_claim(self, claim: Claim, ctx: dict) -> VerificationResult:
        for v in self.verifiers:
            if v.applies(claim):
                res = v.verify(claim, ctx)
                if res.verdict != Verdict.UNKNOWN:
                    return res
        return VerificationResult(
            Verdict.UNKNOWN, 0.0, "no verifier applies", "none", False
        )

    def verify_trace(
        self, claims: list[Claim], ctx: dict, repair_fn
    ) -> dict:
        """repair_fn(claim, critique) -> revised claim (an SLM call). Returns a report."""
        results, repairs = [], 0
        for claim in claims:
            res = self._verify_claim(claim, ctx)
            while res.verdict == Verdict.INVALID and repairs < self.max_repairs:
                claim = repair_fn(claim, res.reason)      # LLM-Modulo: critique -> regenerate
                res = self._verify_claim(claim, ctx)
                repairs += 1
            results.append((claim, res))
        return self._score(results, repairs)

    def _score(self, results, repairs) -> dict:
        checked = [r for _, r in results if r.verdict != Verdict.UNKNOWN]
        invalid = [r for _, r in results if r.verdict == Verdict.INVALID]
        # verification ratio drives a quality-tier CAP and a risk floor (SPEC-026)
        vr_ratio = 1.0 - (len(invalid) / max(1, len(checked)))
        return {
            "stage": "dpe_14_verification",
            "verification_ratio": round(vr_ratio, 3),
            "checked": len(checked),
            "invalid": len(invalid),
            "repairs": repairs,
            "tier_cap": "D" if invalid else None,       # unrepaired invalid step caps tier at D
            "risk_floor": "HIGH" if invalid else "LOW",
            "labels": [
                (c.text, r.verdict.value, r.verifier) for c, r in results
            ],  # PRM training data
        }
```

The relay MUST attempt symbolic verifiers before the PRM. Symbolic verifiers are sound and cheap; they SHOULD run unless the active policy explicitly disables them. The repair loop MUST respect the configured `max_repairs` and MUST report the final state of every claim, including the verifier that produced the final verdict.

### 2.6 Depth-gating in the Safety Policy Directive Language

The Verification Relay is expensive, so probabilistic verification is depth-gated through CRP-SPEC-006 policy directives. Symbolic verifiers are cheap enough to run by default.

```yaml
# safety-policy.yaml  (CRP-SPEC-006 extension)
verification_relay:
  enabled_at_depth: [thorough, exhaustive]   # quick/standard skip PRM; symbolic always runs
  symbolic_always: true                      # Z3/exec are cheap enough to always run
  max_repairs: 2
  on_unrepaired_invalid: cap_tier_D          # or: checkpoint (HITL via SPEC-033)
  emit_step_labels: true                     # feed SPEC-050 router + SPEC-055 calibration
```

A conformant gateway or runtime MUST honour `enabled_at_depth` for the PRM stage and MUST honour `symbolic_always` for the symbolic verifier family. When `on_unrepaired_invalid` is set to `checkpoint`, the Safety Control Plane (CRP-SPEC-033) MUST present a human-in-the-loop resolution before the response is forwarded.

---

## 3. Integration Points

- **CRP-SPEC-005 (Decision Provenance Engine):** The Verification Relay is DPE stage 14. It runs after grounding and entailment and contributes the `verification_ratio` signal to the existing DPE quality report.

- **CRP-SPEC-008 (Dispatch and Provider Adaptation):** Each verifier is a dispatch target. New verifiers — for example, a Datalog engine over the CKF or a units-of-measure checker — register through the dispatch layer without modifying the relay core.

- **CRP-SPEC-026 (Semantic Quality Benchmark / Quality Tiers):** An unrepaired `INVALID` step MUST cap the quality tier at `D` and MUST raise the risk floor to `HIGH`. A fully `VALID` trace MAY raise the tier. The `verification_ratio` is an explicit input to the quality-tier classifier.

- **CRP-SPEC-021 (Reasoning Orchestration and Synthesis):** Self-consistency divergence across sampled traces SHOULD be routed to the Verification Relay as an uncertainty signal. Disagreement between reasoning paths is a strong indicator that VR should be invoked.

- **CRP-SPEC-004 (Continuation and State Relay):** The generate-critique-repair loop reuses the continuation engine. A repair is a bounded continuation that preserves the Cognitive State Object and the audit chain.

- **CRP-SPEC-006 (Safety Policy Directive Language):** Depth-gating, maximum repair count, and the action taken on an unrepaired invalid step are policy directives, not hard-coded behaviour.

- **CRP-SPEC-011 (Audit Trail):** Step-level verdicts MUST be emitted to the audit chain. When `emit_step_labels` is enabled, the tuples `(step, verdict, verifier)` MUST be persisted for downstream training and calibration.

- **CRP-SPEC-033 (Safety Control Plane / Inline HITL):** When policy selects `on_unrepaired_invalid: checkpoint`, the Safety Control Plane MUST trigger a checkpoint rather than returning a raw error or silently accepting the invalid result.

- **CRP-SPEC-050 (Tool Capability Fabric) and CRP-SPEC-055 (Epistemic Profiles & Calibration):** Step labels and verification outcomes MAY be consumed by the quality-tier-supervised router and by epistemic calibration to refine model-specific confidence estimates.

---

## 4. Conformance Requirements

A conformant Verification Relay implementation MUST satisfy the following requirements:

1. **Uniform verifier interface.** Every verifier, symbolic or probabilistic, MUST implement the `Verifier` protocol defined in §2.1. The relay MUST dispatch through this protocol and MUST NOT special-case verifier classes internally.

2. **Symbolic verifiers run by default.** The SMT and sandboxed-executor verifiers MUST run whenever their `applies` predicate is true, unless the active safety policy explicitly disables them. Their soundness depends on this default.

3. **PRM depth-gating.** The Process Reward Model stage MUST run when the active depth is `thorough` or `exhaustive`. It MAY be skipped for `quick` or `standard` depths. It MUST NOT run unconditionally.

4. **Advisory confidence.** A symbolic `VALID` verdict MUST carry confidence `1.0`. A PRM verdict MUST NOT carry confidence `1.0`. No implementation may present a PRM score as a proof.

5. **Repair budget enforcement.** The generate-critique-repair loop MUST respect `max_repairs`. It MUST NOT attempt unbounded regeneration.

6. **No silent acceptance of invalid steps.** An unrepaired `INVALID` step MUST NOT be silently accepted. The policy action (`cap_tier_D` or `checkpoint`) MUST fire.

7. **Quality and risk feedback.** The relay MUST emit `verification_ratio`, `checked`, `invalid`, `repairs`, `tier_cap`, and `risk_floor` to the DPE quality report and risk surface.

8. **Audit emission.** Step-level verdicts MUST be written to the audit chain. When `emit_step_labels` is enabled, `(step, verdict, verifier)` tuples MUST be persisted for use as training data.

9. **Formal-expression provenance.** The SMT verifier MUST receive `claim.formal` only from a trusted parser or constrained-grammar emitter. It MUST NOT evaluate raw model text.

10. **Sandboxed execution.** The executor MUST run in an isolated, network-denied, filesystem-denied subprocess with a strict timeout and resource cap.

---

## 5. Security Considerations

The Verification Relay introduces new attack surfaces that MUST be mitigated:

- **Sandboxed executor.** The executor runs arbitrary-looking arithmetic expressions. It MUST be launched with an isolated interpreter, a minimal environment, no network access, no filesystem write access, and a strict CPU/time limit. Agent-controlled strings MUST pass through the same trusted-gate discipline that governs tool argument construction.

- **SMT expression injection.** The Z3 verifier evaluates `claim.formal` expressions with Python `eval` over a restricted environment (`{"__builtins__": {}}`). To prevent code injection, `claim.formal` MUST be parsed from a constrained grammar (CRP-SPEC-054) and MUST NOT be built by interpolating raw model text.

- **PRM training-data poisoning.** Labels harvested from symbolic verdicts MUST be provenance-tagged with the verifier name, claim hash, and policy context. A poisoned or adversarial label MUST be traceable to its source so it cannot silently corrupt the PRM.

- **Repair-loop resource exhaustion.** Without `max_repairs` and timeout enforcement, an adversarial model or prompt could force an unbounded number of regeneration attempts. The relay MUST cap repairs and MUST propagate resource exhaustion as a governed error.

- **Confidence laundering.** Implementations MUST NOT round a PRM score up to `1.0` or display it as a certainty. UI and downstream classifiers MUST distinguish symbolic proof from advisory scoring.

- **Audit leakage.** Step-level critiques can contain sensitive task content. They MUST be stored under the same classification, retention, and encryption rules as the rest of the audit trail (CRP-SPEC-011).

---

## 6. References

- CRP-SPEC-004: Continuation and State Relay
- CRP-SPEC-005: Decision Provenance Engine
- CRP-SPEC-006: Safety Policy Directive Language
- CRP-SPEC-008: Dispatch and Provider Adaptation
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-021: Reasoning Orchestration and Synthesis
- CRP-SPEC-026: Semantic Quality Benchmark
- CRP-SPEC-033: Safety Control Plane / Inline Human-in-the-Loop
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
- CRP-SPEC-054: Structured Decoding Enforcement
- CRP-SPEC-055: Epistemic Profiles and Calibration
- Lightman, R. et al. (2023). "Let's Verify Step by Step." *arXiv:2305.20050*.
- Kambhampati, S. et al. (2024). "LLMs Still Can't Plan; But Can Help Planning — The LLM-Modulo Approach."
