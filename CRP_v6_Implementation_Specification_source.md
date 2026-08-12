---
title: "CRP v6.0 — The Implementation Specification"
---

# CRP v6.0 — The Implementation Specification

### From Three Reports to Nine Shippable Specs: Exactly What to Build, How, and Where It Fits — With Real, Runnable Code — to Make the Context Relay Protocol the Default Governance Layer for SLM-First Agentic AI

**Prepared for Constantinos Vidiniotis, AutoCyber AI Pty Ltd**

**July 2026**

*Capstone to the series. The three prior volumes analysed the field — "The Architecture of Understanding" (reasoning), "The Architecture of Tool Use" (action), and "The Architecture of Transparency" (display). This volume converts that analysis, together with the CRP v5.1 gap assessment, into concrete, numbered, coded specification documents that slot directly into CRP's existing catalogue (CRP-SPEC-001 … CRP-SPEC-048) at CRP-SPEC-049 and above.*

---

# Part 0 — The Implementation Program: What to Build, How, and Where It Fits

## 0.0 Provenance of this specification

This document is a synthesis, not a fresh analysis. It draws on four inputs and converts them into buildable specs. The three companion reports supplied the field analysis: *The Architecture of Understanding* mapped the eight-layer model of machine cognition and where reasoning, world-modelling, and meta-cognition break down; *The Architecture of Tool Use* established the nine-stage tool loop, constrained decoding, and the trusted policy gate; *The Architecture of Transparency* defined the emission-and-display layer (AG-UI, faithful narration, the D1–D6 roadmap). The fourth input is the CRP v5.1 gap analysis, which ranked the three highest-leverage additions (verification relay, quality-tier-supervised routing, action-log world-model induction) and surveyed the surrounding solution landscape. The existing CRP specification catalogue (CRP-SPEC-001 through -048, published at crprotocol.io) supplied the integration points and the house style, so that every new spec here *extends* a real, numbered predecessor rather than floating free. Where those inputs identified something as genuinely unsolved, this document preserves that honesty rather than papering over it with a spec — because a specification that overpromises is worse than a gap named plainly.

## 0.1 The situation, stated plainly

CRP v5.1 already ships fifty specifications and three products, and it covers more of the "architecture of understanding" than any competing protocol: a 13-stage Decision Provenance Engine (SPEC-005), a Cognitive State Object relay across continuation windows (SPEC-030), reasoning orchestration with self-consistency (SPEC-021), a typed Contextual Knowledge Fabric (SPEC-009), two-sided provenance with an HMAC audit chain (SPEC-011), and the positioned tool loop (SPEC-031) that is the protocol's signature idea. The three reports and the gap analysis converge on a single finding: **CRP's remaining gaps are not capability gaps — they are verification, learning, prediction, and emission gaps, and every one of them attaches to plumbing CRP already has.**

Put concretely, CRP today *grounds* claims but does not *verify inference*; it *scaffolds* reasoning but does not *check* it; it *positions* agents but does not *learn* from how positioning turned out; it *records* actions but does not *predict* their outcomes; and it *generates* governance evidence but does not *stream* it. Each of those verbs is a spec away, because CRP already logs the data, runs the loop, and owns the control plane that the missing verb needs. This document specifies the nine specs that close the gaps, in the order they should be built, with the code to build them.

## 0.2 The nine specs, mapped to where they fit

Each new spec *extends* existing CRP specs rather than replacing them. The mapping is the "where it fits" answer:

| New spec | Name | Extends / requires | Closes gap from |
|---|---|---|---|
| **SPEC-049** | Verification Relay (VR) | 005 (DPE), 008 (Dispatch), 021 (ROS), 026 (SQB), 006 (SPDL) | Reasoning: verify inference, not just grounding |
| **SPEC-050** | Quality-Tier-Supervised Router (QSR) | 008 (Dispatch), 011 (Audit), 026 (SQB), 006 (SPDL) | Routing: static → learned, self-improving |
| **SPEC-051** | Predictive Positioning & World-Model Induction (PP) | 029 (Tier-E), 009 (CKF), 031 (STL), 033 (Control Plane) | Understanding: descriptive → predictive |
| **SPEC-052** | Intent & Speech-Act Positioning (ISA) | 003 (Envelope), 031 (STL), 028 (Multi-Horizon) | NLU: entities → meaning-in-context |
| **SPEC-053** | Clarification Protocol (CLR) | 001 (Core), 033 (Inline HITL), 002 (Headers) | NLU: guessing → negotiated grounding |
| **SPEC-054** | Structured Decoding Enforcement (SDE) | 016 (Gateway), 008 (Dispatch), 031 (STL) | Tool use: token-level tool-call validity |
| **SPEC-055** | Epistemic Profiles & Calibration (EP) | 009 (CKF), 026 (SQB), 021 (ROS) | Meta-cognition: measure self-knowledge |
| **SPEC-056** | Transparency Emission Layer (TEL) | 016 (Gateway), 005 (DPE), 011 (Audit), 030 (CSO) | Transparency: generate → stream (D1–D6) |
| **SPEC-057** | Bi-Temporal CKF (BTF) | 009 (CKF), 027 (Retrieval Integrity) | Structural: static facts → time-valid facts |

None of these is a rewrite. Each is a module that consumes data CRP already produces and writes into a control point CRP already owns.

## 0.3 The dependency graph and build sequence

The specs are not independent; some feed others. The build order below respects the dependencies and front-loads the highest-leverage work (the gap analysis's ranked recommendations: verification first, learned routing second, world-model induction third).

```
Wave 1 (foundations, highest leverage) ─────────────────────────────
  SPEC-049 Verification Relay ......... biggest single quality gain
  SPEC-054 Structured Decoding ........ kills a whole class of tool-call failures (cheap, standalone)
  SPEC-056 Transparency Emission ...... makes everything else legible; unblocks the demo story

Wave 2 (learning flywheels, depend on Wave 1 signals) ──────────────
  SPEC-050 Learned Router ............. trains on quality tiers + VR verdicts (needs 049)
  SPEC-055 Epistemic Profiles ......... trains on VR correctness + self-consistency (needs 049)
  SPEC-052 Intent & Speech-Act ........ positions the router better (feeds 050)

Wave 3 (frontier, research-credible, depend on the action log) ─────
  SPEC-051 Predictive Positioning ..... rule induction over the enriched action log
  SPEC-053 Clarification Protocol ..... needs 052's intent-confidence signal
  SPEC-057 Bi-Temporal CKF ............ deepens the substrate 049/051 read from
```

*Figure 0.1. Three waves. Wave 1 is buildable now from data CRP already logs; Wave 2 needs Wave 1's verdicts as training labels; Wave 3 is the frontier research story that turns the action log into a world model.*

The strategic logic: **Wave 1 delivers immediate, demonstrable quality and legibility; Wave 2 turns CRP's own audit data into self-improvement flywheels no competitor can replicate; Wave 3 is the research-paper-worthy frontier that makes CRP intellectually unassailable.** You can ship Wave 1 independently and see gains; Waves 2 and 3 compound on it.

## 0.4 The three flywheels — why this program compounds

The reason this is a *program* and not a feature list is that three of the specs create self-reinforcing loops from data CRP uniquely possesses:

1. **The verification flywheel (049 → 055).** Every verified reasoning step produces a correctness label. Those labels train the Process Reward Model *and* the per-model calibration curves, which make the next verification cheaper and better-targeted. CRP is the only protocol generating step-level correctness labels as a byproduct of governance.

2. **The routing flywheel (049/026 → 050).** Every dispatch produces a `(task, routing decision, quality tier, verification verdict)` tuple — a free, labelled training example for the router. The router improves with usage; the quality tiers supervise it; nobody else has quality-tier-labelled routing data because nobody else scores quality per call.

3. **The world-model flywheel (029 → 051).** Every tool action is an *intervention* on the environment, and its logged outcome is a natural experiment. Rule induction over the action log yields transition rules — a learned world model — that get more accurate with every action the fleet takes. This is the frontier-credible claim: *agent actions are interventions, so the action log is causal-discovery data*, which is genuinely research-paper-worthy.

Each flywheel is powered by evidence CRP *already logs and no competitor collects*. That is the deepest reason this program, not any single spec, is what makes CRP the default.

## 0.5 Effort, risk, and demo value — a planning matrix

For sequencing the real build, each spec carries a different effort/risk/payoff profile. This matrix is the founder's-eye view: what to build when, what it costs, what can go wrong, and what it *demonstrates* (because a spec you can demo is a spec you can sell).

| Spec | Effort | Technical risk | Demo value | Notes on the build |
|---|---|---|---|---|
| **049 VR** | High | Medium | **Very high** | PRM needs a trained classifier; symbolic verifiers are quick wins. Ship symbolic first, PRM second. |
| **054 SDE** | **Low** | **Low** | High | Mostly wiring XGrammar into the Gateway; the library does the hard part. Fastest credibility win. |
| **056 TEL** | Medium | Low | **Very high** | Adapter + event vocabulary; unblocks every demo. Build early even though it emits Wave-2/3 signals later. |
| **050 QSR** | Medium | Medium | High | Router training is standard ML; the moat is the data, which accrues automatically. |
| **055 EP** | Medium | Medium | Medium | Semantic entropy is cheap; calibration curves need volume to stabilise. |
| **052 ISA** | Low | Low | Medium | Two small local models; measurable positioning lift. Low-risk quick win. |
| **051 PP** | **High** | **High** | **Very high** | The frontier build and the frontier *risk* — start with shallow symbolic rules, gate hard, never overclaim causality. |
| **053 CLR** | Low | Low | High | Small code, big story ("asks instead of guessing"). Novel standards territory. |
| **057 BTF** | Medium | Low | Low | Substrate improvement; quiet but corrects a real grounding failure mode. |

The reading: **SDE, TEL, and CLR are cheap, low-risk, high-story** — build them early for fast, demonstrable wins even out of strict wave order. **VR and PP are the high-effort, high-payoff anchors** — VR is the quality anchor, PP the intellectual anchor. **The learning specs (050, 055) are medium everything** but compound over time. A pragmatic first sprint that maximises demonstrable progress: SDE + TEL + CLR + VR-symbolic, which together already tell the "valid tool calls, verified reasoning, faithful streamed governance, asks-when-unsure" story with modest effort.

## 0.6 What this specification deliberately excludes

Three honest scope boundaries, so the program is not oversold. It does **not** claim weight-level or continual on-device learning — every learning loop here is context-level or periodic-retrain (Part 11 says so). It does **not** claim verified causal discovery — SPEC-051 induces *predictive* rules and separates textual from interventional evidence, but causal *identification* remains open. And it does **not** claim comprehension or intentionality — the entire program delivers *functional* understanding (behaviour indistinguishable from understanding within scope), which is the honest and defensible claim. These exclusions are not weaknesses to hide; stated plainly, they are what make the *included* claims trustworthy, which for a governance protocol is the whole point.

## 0.7 How to read the spec documents

Parts 1–9 are the specifications themselves, written in CRP's house style: metadata header, status, abstract, motivation, normative specification with runnable code, integration points naming the exact existing specs touched, conformance requirements using RFC-2119 keywords (MUST / SHOULD / MAY), and security considerations. The code is real — built on the libraries the field actually uses in 2026 (Z3, XGrammar, DeBERTa-class verifiers, `jsonpatch`, the AG-UI event model) — and is close to production shape, not pseudocode. Part 10 is the strategic synthesis: what, taken together, makes CRP the go-to protocol. Part 11 is the forward research agenda — the agentic-AI areas worth investigating next, marked by how open each genuinely is.

A note on honesty, carried from every prior volume: where the code depends on a fast-moving library or a research result, it is named and dated so you can verify it against the current version before shipping; and where a capability is genuinely unsolved industry-wide (calibration, causal identification, embodied grounding), the spec says so rather than overclaiming. The specs are designed to be *submitted* — to your own catalogue first, and where appropriate to the IETF/IANA track CRP already engages — so they are written to survive scrutiny.

\newpage
# Part 1 — CRP-SPEC-049: The Verification Relay (VR)

```
Spec:        CRP-SPEC-049
Title:       The Verification Relay — Step-Level Reasoning Verification
             and Symbolic Verifier Dispatch
Status:      Proposed (Wave 1)
Version:     0.1
Requires:    CRP-SPEC-005 (DPE), CRP-SPEC-006 (SPDL), CRP-SPEC-008 (Dispatch),
             CRP-SPEC-021 (ROS), CRP-SPEC-026 (SQB)
Extends:     CRP-SPEC-005 (adds DPE stage 14), CRP-SPEC-008 (adds verifier dispatch targets)
Author:      AutoCyber AI Pty Ltd
```

## 1.1 Abstract

The DPE (SPEC-005) verifies output *against sources* — grounding. It does not verify *inference against logic*. A model can cite every fact correctly and still draw an invalid conclusion. This specification adds a **Verification Relay**: a 14th DPE stage that scores each reasoning step for logical validity using a Process Reward Model, plus a set of **symbolic verifier dispatch targets** (an SMT solver, a sandboxed executor, a datalog engine over the CKF) invoked through an LLM-Modulo generate-critique-repair loop. Verification results feed the quality tier (SPEC-026) and risk score, and are depth-gated (SPEC-006) so the cost is paid only where it matters.

## 1.2 Motivation

Grounding and validity are orthogonal. "All API keys are secrets; this value is an API key; therefore rotate all secrets weekly" is grounded (both premises citable) yet the conclusion does not follow. The single biggest reasoning-quality lever CRP lacks is *process supervision* — scoring the steps, not just the answer, a paradigm established by step-level verification research (Lightman et al., 2023) and extended by automatic process-reward labelling. For formally checkable claims (arithmetic, dates, unit conversions, constraint satisfaction), a probabilistic scorer is unnecessary and a *deterministic* verifier is both cheaper and certain; the LLM-Modulo framework (Kambhampati et al., 2024) — LLM generates, external sound verifier critiques, loop until valid — is the right architecture, and CRP already owns the loop machinery (the continuation engine, SPEC-004). The VR makes verification a first-class, dispatchable relay.

## 1.3 Specification

### 1.3.1 The verifier interface

All verifiers — probabilistic (PRM) and symbolic — implement one interface, so the relay can dispatch to them uniformly and so new verifiers are plug-ins (SPEC-008 dispatch targets).

```python
# crp/vr/interface.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

class Verdict(str, Enum):
    VALID    = "valid"       # verifier affirms the step/claim
    INVALID  = "invalid"     # verifier refutes it (with a reason)
    UNKNOWN  = "unknown"     # verifier cannot decide (not in its domain)

@dataclass
class VerificationResult:
    verdict: Verdict
    confidence: float          # 1.0 for sound symbolic verifiers; <1 for PRM
    reason: str                # machine- or human-readable critique (drives repair)
    verifier: str              # which verifier produced this (audit)
    checkable: bool            # was this claim in the verifier's decidable domain?

class Verifier(Protocol):
    name: str
    def applies(self, claim: "Claim") -> bool: ...          # domain gate
    def verify(self, claim: "Claim", context: dict) -> VerificationResult: ...

@dataclass
class Claim:
    """A single reasoning step or checkable assertion extracted from the trace."""
    text: str
    kind: str                  # "inference" | "arithmetic" | "temporal" | "constraint" | "fact"
    premises: list[str]        # prior steps / facts this claim depends on
    formal: dict | None = None # optional pre-parsed formal representation
```

### 1.3.2 Symbolic verifier — SMT (Z3) for constraints and arithmetic

For claims reducible to logical/arithmetic constraints, route to Z3. This is *sound*: a VALID verdict is a proof, confidence is 1.0.

```python
# crp/vr/z3_verifier.py — sound verification of arithmetic & logical constraints
import z3
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim

class Z3Verifier:
    name = "z3-smt"

    def applies(self, claim: Claim) -> bool:
        return claim.kind in ("arithmetic", "constraint") and claim.formal is not None

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        # claim.formal example: {"vars":{"x":"Int"},"assert":["x > 0","x < 5"],"claim":"x != 3"}
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
            return VerificationResult(Verdict.VALID, 1.0, "entailed (proof)", self.name, True)
        elif r == z3.sat:      # a counter-model exists => claim does NOT follow
            return VerificationResult(Verdict.INVALID, 1.0,
                                      f"counterexample: {s.model()}", self.name, True)
        return VerificationResult(Verdict.UNKNOWN, 0.0, "solver undecided", self.name, True)
```

### 1.3.3 Symbolic verifier — sandboxed executor for computational claims

For claims that are computations ("the scan covered 254 hosts", "the total is $4,812"), execute deterministically in a locked-down subprocess. This reuses the sandbox discipline from the tool-use volume (no network, no filesystem, resource-capped).

```python
# crp/vr/exec_verifier.py — verify computational claims by deterministic execution
import subprocess, json, tempfile, os
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim

class ExecVerifier:
    name = "sandboxed-exec"

    def applies(self, claim: Claim) -> bool:
        return claim.kind == "arithmetic" and claim.formal and "expr" in claim.formal

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        # claim.formal: {"expr":"254 * 3", "expected": 762}
        code = f"import json;print(json.dumps({claim.formal['expr']}))"
        try:
            out = subprocess.run(
                ["python3", "-I", "-c", code],           # -I: isolated, no env/site
                capture_output=True, text=True, timeout=2,
                env={"PATH": "/usr/bin"},                 # minimal env; no network by sandbox policy
            )
            actual = json.loads(out.stdout.strip())
        except Exception as e:
            return VerificationResult(Verdict.UNKNOWN, 0.0, f"exec error: {e}", self.name, True)
        expected = claim.formal["expected"]
        if actual == expected:
            return VerificationResult(Verdict.VALID, 1.0, f"{actual}=={expected}", self.name, True)
        return VerificationResult(Verdict.INVALID, 1.0,
                                  f"computed {actual}, claim said {expected}", self.name, True)
```

### 1.3.4 Probabilistic verifier — the Process Reward Model (DPE stage 14)

For inference steps that are *not* formally checkable, score logical entailment with a small fine-tuned classifier. This is the process-supervision stage; it is depth-gated because it costs a model call per step.

```python
# crp/vr/prm.py — step-level reasoning verification (DPE stage 14)
from transformers import pipeline
from crp.vr.interface import Verifier, VerificationResult, Verdict, Claim

class ProcessRewardVerifier:
    """A small (0.5-1.5B) classifier scoring: is this step entailed by its premises?
    Train on step-level labels harvested from VR's own symbolic verdicts (the flywheel)."""
    name = "prm"

    def __init__(self, model="AutoCyberAI/crp-prm-deberta-v1", threshold=0.5):
        self._clf = pipeline("text-classification", model=model, top_k=None)
        self._threshold = threshold

    def applies(self, claim: Claim) -> bool:
        return claim.kind == "inference"     # the non-formal steps

    def verify(self, claim: Claim, context: dict) -> VerificationResult:
        premises = " ".join(claim.premises)
        scores = {d["label"]: d["score"]
                  for d in self._clf(f"premises: {premises} [SEP] step: {claim.text}")}
        p_valid = scores.get("VALID", 0.0)
        if p_valid >= self._threshold:
            return VerificationResult(Verdict.VALID, p_valid, "step-reward above threshold",
                                      self.name, checkable=False)
        return VerificationResult(Verdict.INVALID, 1.0 - p_valid,
                                  "step not entailed by prior steps", self.name, checkable=False)
```

### 1.3.5 The relay — LLM-Modulo generate-critique-repair

The VR orchestrates verifiers over a reasoning trace, and — the LLM-Modulo core — feeds INVALID critiques back to the model to *repair*, looping until valid or budget-exhausted. It reuses the continuation loop (SPEC-004).

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
        return VerificationResult(Verdict.UNKNOWN, 0.0, "no verifier applies", "none", False)

    def verify_trace(self, claims: list[Claim], ctx: dict, repair_fn) -> dict:
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
            "checked": len(checked), "invalid": len(invalid), "repairs": repairs,
            "tier_cap": "D" if invalid else None,       # any unrepaired invalid step caps tier at D
            "risk_floor": "HIGH" if invalid else "LOW",
            "labels": [(c.text, r.verdict.value, r.verifier) for c, r in results],  # PRM training data
        }
```

### 1.3.6 Depth-gating in the Safety Policy Directive Language (SPEC-006)

The VR is expensive, so it is depth-gated. This is one directive in an existing spec.

```yaml
# safety-policy.yaml  (SPEC-006 extension)
verification_relay:
  enabled_at_depth: [thorough, exhaustive]   # quick/standard skip PRM; symbolic always runs
  symbolic_always: true                      # Z3/exec are cheap enough to always run
  max_repairs: 2
  on_unrepaired_invalid: cap_tier_D          # or: checkpoint (HITL via SPEC-033)
  emit_step_labels: true                     # feed SPEC-050 router + SPEC-055 calibration
```

## 1.4 Integration Points

- **SPEC-005 (DPE):** VR is DPE stage 14, running after grounding/entailment. Its `verification_ratio` joins the 13 existing signals.
- **SPEC-026 (SQB / Quality Tiers):** an unrepaired INVALID step **MUST** cap the quality tier at D and **MUST** raise the risk floor to HIGH. A fully-VALID trace **MAY** raise the tier.
- **SPEC-008 (Dispatch):** each verifier is a dispatch target; new verifiers (datalog over CKF, a units checker) register without touching the relay.
- **SPEC-021 (ROS):** self-consistency divergence across sampled traces **SHOULD** be routed to VR as an uncertainty signal (see SPEC-055).
- **SPEC-004 (Continuation):** the repair loop reuses the continuation engine; a repair is a bounded continuation.
- **SPEC-006 (SPDL):** depth-gating and the on-invalid action are policy directives.

## 1.5 Conformance Requirements

- A conforming VR implementation **MUST** run all *symbolic* verifiers regardless of depth, because they are sound and cheap.
- It **MUST** run the PRM stage when depth is `thorough` or `exhaustive`, and **MAY** skip it otherwise.
- It **MUST** emit step-level verdicts to the audit chain (SPEC-011) and **MUST**, when `emit_step_labels` is set, persist `(step, verdict, verifier)` tuples for downstream training (the verification flywheel).
- An unrepaired INVALID step **MUST NOT** be silently accepted; the policy action (`cap_tier_D` or `checkpoint`) **MUST** fire.
- A symbolic VALID verdict **MUST** carry confidence 1.0; a PRM verdict **MUST NOT** claim confidence 1.0.

## 1.6 Security Considerations

The sandboxed executor is an attack surface: it **MUST** run isolated (`-I`), network-denied, filesystem-denied, and resource-capped, and **MUST NOT** execute agent-controlled strings without the same trusted-gate discipline the tool-use layer applies to argument construction. The Z3 verifier uses `eval` over a *restricted* environment (`{"__builtins__": {}}`) with only pre-declared solver variables in scope; formal expressions **MUST** be parsed from a constrained grammar (SPEC-054), never from raw model text, to prevent code injection through the `formal` field. PRM training data harvested from symbolic verdicts **MUST** be provenance-tagged so a poisoned label cannot silently corrupt the model (the flywheel is only as trustworthy as its labels).

\newpage
# Part 2 — CRP-SPEC-050: The Quality-Tier-Supervised Router (QSR)

```
Spec:        CRP-SPEC-050
Title:       The Quality-Tier-Supervised Router — Learned, Capability-Aware
             Dispatch with an Escalation Ladder
Status:      Proposed (Wave 2)
Version:     0.1
Requires:    CRP-SPEC-008 (Dispatch), CRP-SPEC-011 (Audit), CRP-SPEC-026 (SQB),
             CRP-SPEC-049 (VR), CRP-SPEC-006 (SPDL)
Extends:     CRP-SPEC-008 (makes the router a trained, evaluated component)
Author:      AutoCyber AI Pty Ltd
```

## 2.1 Abstract

CRP's dispatch (SPEC-008) selects which operation, which tools, and which depth per call, but the routing decision itself is heuristic and unaudited. This specification turns the router into a **trained, self-improving component** supervised by the quality tiers CRP already produces. It logs `(task features, routing decision, quality tier, verification verdict)` tuples — which CRP alone collects — and fine-tunes a small classifier router on them; it adds **capability-aware routing** to heterogeneous local SLM fleets via per-model profiles; and it formalises an **escalation ladder** (try small, escalate on failure signals) as an SPDL primitive. The result is a routing flywheel: every dispatch is a free, labelled training example, so the router improves with use.

## 2.2 Motivation

The SLM-first thesis CRP is built on requires *heterogeneous specialist fleets* — Qwen-class models for code, Phi-class for math, Gemma-class for prose — because most agentic tasks are repetitive, scoped, and non-conversational, and a right-sized specialist beats a general giant on cost and often on quality. But specialist fleets only pay off with a *good router*, and routing is exactly where CRP currently leans on heuristics. The insight that makes CRP uniquely able to solve this: **the quality tier (SPEC-026) and the verification verdict (SPEC-049) are free training labels.** RouteLLM-style learned routing needs labelled `(task, model, outcome)` data that most builders must construct expensively; CRP generates it as governance exhaust. That is a self-improving flywheel no competitor can copy without first building CRP's scoring layer.

## 2.3 Specification

### 2.3.1 The training tuple, harvested from the audit chain

Every completed dispatch already writes an audit record (SPEC-011). The QSR reads those records into training tuples — no new logging, just a projection.

```python
# crp/qsr/harvest.py — build router training data from the audit chain (free labels)
from dataclasses import dataclass, asdict

@dataclass
class RoutingExample:
    # features (what the router sees BEFORE dispatch)
    task_kind: str            # from STL classification (SPEC-031): code/math/prose/extract...
    complexity: str           # ENTITY_RICH | REASONING_DENSE | NARRATIVE
    est_tokens: int
    tool_count: int
    depth: str
    # decision (what the router chose)
    model_id: str             # which SLM handled it
    # labels (how it turned out — the free supervision)
    quality_tier: str         # S/A/B/C/D  (SPEC-026)
    vr_ratio: float           # verification ratio (SPEC-049)
    escalated: bool           # did it need escalation?
    latency_ms: int
    cost: float

def harvest(audit_records) -> list[RoutingExample]:
    out = []
    for r in audit_records:
        if r.get("stage") != "dispatch_complete":
            continue
        out.append(RoutingExample(
            task_kind=r["task"]["kind"], complexity=r["task"]["complexity"],
            est_tokens=r["task"]["est_tokens"], tool_count=len(r["task"]["tools"]),
            depth=r["task"]["depth"], model_id=r["decision"]["model_id"],
            quality_tier=r["result"]["tier"], vr_ratio=r["result"].get("vr_ratio", 1.0),
            escalated=r["result"].get("escalated", False),
            latency_ms=r["result"]["latency_ms"], cost=r["result"]["cost"]))
    return out
```

### 2.3.2 Capability profiles per model

Each local model gets a benchmarkable profile (via the existing SQB, SPEC-026) recording its measured competence by task kind. Routing consults these before the learned model exists (cold start) and as features afterward.

```python
# crp/qsr/profiles.py — per-model capability profiles (benchmark-derived, SPEC-026)
from dataclasses import dataclass, field

@dataclass
class CapabilityProfile:
    model_id: str
    # measured mean quality (0-1) per task kind, from SQB benchmark runs
    competence: dict[str, float] = field(default_factory=dict)   # {"code":0.82,"math":0.61,...}
    ctx_window: int = 8192
    schema_complexity_ceiling: int = 3   # max JSON nesting depth this model handles reliably
    tokens_per_sec: float = 40.0
    cost_per_1k: float = 0.0             # 0 for local

    def score_for(self, task_kind: str) -> float:
        return self.competence.get(task_kind, 0.5)

# a fleet is a set of profiles; the router picks among them
FLEET = {
    "qwen3-coder-7b":  CapabilityProfile("qwen3-coder-7b",
                        {"code": 0.86, "math": 0.63, "prose": 0.55}, ctx_window=32768,
                        schema_complexity_ceiling=5),
    "phi4-math-4b":    CapabilityProfile("phi4-math-4b",
                        {"code": 0.58, "math": 0.84, "prose": 0.60},
                        schema_complexity_ceiling=3),
    "gemma3-4b":       CapabilityProfile("gemma3-4b",
                        {"code": 0.52, "math": 0.55, "prose": 0.81},
                        schema_complexity_ceiling=2),
}
```

### 2.3.3 The learned router

A small classifier maps task features to the model most likely to hit tier A+ at least cost. Before enough data accrues it falls back to the capability profiles; after, it uses the trained model. This is the RouteLLM pattern, supervised by CRP's quality tiers.

```python
# crp/qsr/router.py — learned, capability-aware router with cold-start fallback
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from crp.qsr.profiles import FLEET, CapabilityProfile

class LearnedRouter:
    def __init__(self):
        self._clf: GradientBoostingClassifier | None = None
        self._models = list(FLEET.keys())

    def _featurize(self, task) -> list[float]:
        kinds = ["code", "math", "prose", "extract"]
        complexity = {"ENTITY_RICH": 0, "REASONING_DENSE": 1, "NARRATIVE": 2}
        return [*[1.0 if task.kind == k else 0.0 for k in kinds],
                complexity.get(task.complexity, 0), task.est_tokens / 1000,
                task.tool_count, {"quick":0,"standard":1,"thorough":2,"exhaustive":3}[task.depth]]

    def train(self, examples):
        # label = the model that achieved the best (tier, then cost) for similar tasks
        good = [e for e in examples if e.quality_tier in ("S", "A")]
        if len(good) < 200:            # not enough signal yet -> stay in cold-start mode
            return False
        X = [self._featurize_ex(e) for e in good]
        y = [self._models.index(e.model_id) for e in good]
        self._clf = GradientBoostingClassifier(max_depth=3).fit(np.array(X), y)
        return True

    def route(self, task) -> str:
        # capability-aware pre-filter: exclude models whose schema ceiling is too low
        eligible = [m for m, p in FLEET.items()
                    if p.schema_complexity_ceiling >= task.schema_depth]
        if self._clf is not None:                    # learned path
            probs = self._clf.predict_proba([self._featurize(task)])[0]
            ranked = sorted(zip(self._models, probs), key=lambda t: -t[1])
            for model_id, _ in ranked:
                if model_id in eligible:
                    return model_id
        # cold-start / fallback: best capability profile for this task kind
        return max(eligible, key=lambda m: FLEET[m].score_for(task.kind))
```

### 2.3.4 The escalation ladder as an SPDL primitive

"Try small locally; escalate on failure signals" becomes one policy directive, using signals CRP already has (quality tier, grounding score, verification ratio, self-consistency divergence).

```python
# crp/qsr/escalation.py — escalate-on-failure ladder driven by SPDL
from crp.qsr.router import LearnedRouter

ESCALATION_LADDER = ["gemma3-4b", "qwen3-coder-7b", "cloud-large"]  # small -> large

def run_with_escalation(task, execute_fn, policy) -> dict:
    """policy: {'escalate_on': {'tier_below':'B','vr_ratio_below':0.9}, 'max_rungs':2}"""
    router = LearnedRouter()
    first = router.route(task)
    ladder = [first] + [m for m in ESCALATION_LADDER if m != first]
    rungs = 0
    for model_id in ladder:
        result = execute_fn(task, model_id)
        below_tier = _tier_rank(result["tier"]) < _tier_rank(policy["escalate_on"]["tier_below"])
        below_vr = result.get("vr_ratio", 1.0) < policy["escalate_on"]["vr_ratio_below"]
        if not (below_tier or below_vr) or rungs >= policy["max_rungs"]:
            result["escalated"] = rungs > 0
            return result
        rungs += 1        # failure signal -> climb the ladder
    result["escalated"] = True
    return result

def _tier_rank(t): return {"S":5,"A":4,"B":3,"C":2,"D":1}[t]
```

```yaml
# safety-policy.yaml (SPEC-006 extension)
escalation:
  escalate_on: { tier_below: B, vr_ratio_below: 0.9 }
  max_rungs: 2
  ladder: [local-small, local-specialist, cloud-large]
```

### 2.3.5 Schema adaptation for small models

Recent evidence favours *adapting tool schemas to small models* over the reverse: SLMs fail on deep nested JSON that large models handle. When routing to a model whose `schema_complexity_ceiling` is below the tool's schema depth, transform the schema — flatten, rename keys to natural language, constrain enums — before positioning (SPEC-031).

```python
# crp/qsr/schema_adapt.py — flatten/simplify tool schemas per model capability
def adapt_schema(schema: dict, ceiling: int) -> dict:
    """Flatten nested objects beyond `ceiling` levels into dotted, NL-named fields."""
    def flatten(obj, prefix="", depth=0):
        out = {}
        for k, v in obj.get("properties", {}).items():
            name = f"{prefix}{k}"
            if v.get("type") == "object" and depth >= ceiling:
                # collapse: represent the subtree as a single natural-language string field
                out[name.replace('_', ' ')] = {"type": "string",
                    "description": f"describe {name.replace('_',' ')} in plain words"}
            elif v.get("type") == "object":
                out.update(flatten(v, prefix=f"{name}.", depth=depth + 1))
            else:
                out[name.replace('_', ' ')] = v
        return out
    return {"type": "object", "properties": flatten(schema)}
```

## 2.4 Integration Points

- **SPEC-008 (Dispatch):** the QSR replaces the heuristic router; dispatch calls `LearnedRouter.route`.
- **SPEC-011 (Audit) + SPEC-026 (SQB):** the audit chain is the training corpus; quality tiers are the labels. The router **MUST NOT** require any logging CRP does not already do.
- **SPEC-049 (VR):** the verification ratio is both a routing feature and an escalation trigger.
- **SPEC-031 (STL):** schema adaptation runs inside the positioned tool loop, before schema enters the tool-selection window.
- **SPEC-006 (SPDL):** the escalation ladder and its triggers are policy directives.

## 2.5 Conformance Requirements

- The router **MUST** operate in cold-start mode (capability profiles only) until at least 200 tier-A/S examples exist, then **MAY** switch to the learned model.
- It **MUST** exclude models whose `schema_complexity_ceiling` is below the task's schema depth *unless* schema adaptation is applied.
- Escalation **MUST** be driven only by observed failure signals (tier, grounding, VR ratio, divergence), never by a fixed retry count alone, and **MUST** respect `max_rungs`.
- Every routing decision and its outcome **MUST** be written back to the audit chain so the flywheel is continuous.

## 2.6 Security Considerations

The router is trained on audit data; if an adversary can influence outcomes (e.g. induce spuriously high tiers), they can poison routing. Training **MUST** use only provenance-verified audit records (SPEC-011 HMAC chain), and the training job **SHOULD** hold out a trusted evaluation set to detect distribution shift or poisoning before promoting a new router. Capability profiles **MUST** be derived from sealed benchmark runs (SQB), not from self-reported model claims. Escalation to a *cloud* rung **MUST** re-apply the full DPE and policy envelope, since leaving the local trust boundary changes the data-governance posture (a compliance-relevant event that **MUST** be surfaced via SPEC-056).

\newpage
# Part 3 — CRP-SPEC-051: Predictive Positioning & World-Model Induction (PP)

```
Spec:        CRP-SPEC-051
Title:       Predictive Positioning — World-Model Rule Induction over the
             Action Log, Causal CKF Edges, and Simulation-Before-Action
Status:      Proposed (Wave 3, frontier)
Version:     0.1
Requires:    CRP-SPEC-009 (CKF), CRP-SPEC-029 (Tier-E Action Log),
             CRP-SPEC-031 (STL), CRP-SPEC-033 (Safety Control Plane), CRP-SPEC-006 (SPDL)
Extends:     CRP-SPEC-031 (positions the agent with what WILL happen, not just what is true)
Author:      AutoCyber AI Pty Ltd
```

## 3.1 Abstract

A knowledge graph of extracted facts (CKF, SPEC-009) is a *descriptive* model; strong understanding requires a *predictive* one — anticipating the consequences of an action before taking it. This specification induces a lightweight **world model** from CRP's event-sourced action log (Tier-E, SPEC-029): transition rules of the form `(state_pattern, action) → outcome_pattern`, learned from the actions the fleet has already taken. It adds **causal edge types** (`causes`, `enables`, `prevents`) to the CKF for counterfactual retrieval, and a **simulation-before-action** check for HIGH-risk operations that predicts the outcome against the rule set and causal graph before dispatch, turning EU AI Act Article 14 human oversight from reactive into *anticipatory*. The frontier-credible claim underpinning it: **agent actions are interventions on the environment, so the action log is causal-discovery data** — a research-paper-worthy observation, because it sidesteps the usual barrier that causal identification needs interventional data by noting that CRP already logs interventions.

## 3.2 Motivation

The world-model gap is the deepest gap in the report *and in the industry* — no production system predicts action consequences robustly. But the research frontier is exactly here: neurosymbolic world-model alignment (the WALL-E line of work) shows that LLMs can serve as world models when aligned to environment dynamics via learned symbolic rules — code-based, gradient-free integration of action rules with knowledge and scene graphs — reaching high task success after only a few iterations, and later work improves prediction in structured-dynamics domains by treating symbolic scores as an energy term over the neural model's distribution. CRP is unusually well placed to adopt this because it *already captures every tool call and its result* (Tier-E) and *already owns the loop and the control plane*. The world model is not a new subsystem; it is an induction pass over data CRP already has, plus a check on a control point CRP already owns.

## 3.3 Specification

### 3.3.1 Transition rules from the action log

Each Tier-E record is `(pre_state, action, post_state)`. Rule induction abstracts these into patterns: which state features, under which action, predict which outcome. Start rule-based and gradient-free (WALL-E's insight: symbolic rules are sample-efficient and inspectable).

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

### 3.3.2 Prediction — the learned world model

Given a proposed action and current state, predict the outcome by matching against induced rules. This is what "predictive positioning" adds: the agent is positioned not only with what is true, but with what the model expects to happen.

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
        return None      # caller MAY fall back to a neural predictor (see 3.3.4)
```

### 3.3.3 Causal edges in the CKF

Add `causes`/`enables`/`prevents` edge types to the CKF (SPEC-009), populated by the LLM-assisted extraction stage prompted for causal language, and *strengthened* by action-log evidence (an action reliably followed by an outcome is interventional support for a causal edge — stronger than mere textual "because").

```python
# crp/pp/causal_ckf.py — causal edges + counterfactual (causal-upstream) retrieval
from enum import Enum

class CausalEdge(str, Enum):
    CAUSES = "causes"; ENABLES = "enables"; PREVENTS = "prevents"

def add_causal_edge(ckf, src: str, dst: str, kind: CausalEdge,
                    textual_conf: float, interventional_support: int = 0):
    # interventional support = # of action-log transitions where doing src changed dst
    # this is the key move: agent actions are interventions, so this is causal evidence
    conf = min(1.0, textual_conf + 0.1 * interventional_support)   # interventions boost confidence
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

### 3.3.4 Simulation-before-action for HIGH-risk operations

For operations the safety policy tags HIGH, predict the outcome *before* executing; if the prediction violates policy, checkpoint (HITL) instead of acting. This unifies the world model with the existing Safety Control Plane (SPEC-033) and makes oversight anticipatory.

```python
# crp/pp/simulate.py — predict-then-gate for HIGH-risk actions (anticipatory oversight)
from crp.pp.world_model import WorldModel

def guarded_dispatch(state: dict, action: str, risk: str,
                     world: WorldModel, policy, execute_fn, checkpoint_fn):
    if risk == "HIGH":
        pred = world.predict(state, action)
        if pred:
            violation = policy.check_predicted_outcome(pred["predicted"])   # SPEC-006 eval
            if violation and pred["confidence"] >= policy.sim_confidence_floor:
                # the world model predicts a policy-violating outcome -> don't act; ask a human
                return checkpoint_fn(reason=f"predicted {violation} "
                                     f"(conf {pred['confidence']}, n={pred['support']})",
                                     prediction=pred)
        # no confident prediction of harm -> proceed, but record the prediction for audit
    return execute_fn(state, action, prediction=pred if risk == "HIGH" else None)
```

```yaml
# safety-policy.yaml (SPEC-006 extension)
predictive_positioning:
  simulate_risk_levels: [HIGH]        # which risk tiers get simulation-before-action
  sim_confidence_floor: 0.75          # only block on predictions at/above this confidence
  neural_fallback: true               # if no symbolic rule matches, query neural predictor
  induction_schedule: nightly         # re-induce rules from the growing action log
```

### 3.3.5 The neural fallback (optional, WALL-E-style hybrid)

When no symbolic rule matches, an aligned neural predictor fills the gap, with the symbolic rules acting as an energy term that corrects the neural distribution in structured domains — the hybrid the 2026 literature favours. This is optional and depth/risk-gated; the symbolic layer alone already delivers the compliance and safety value.

## 3.4 Integration Points

- **SPEC-029 (Tier-E):** the action log is the training data; induction is a scheduled pass over it. No new logging.
- **SPEC-009 (CKF):** causal edges are new CKF edge types; counterfactual retrieval is a CDGR walk variant.
- **SPEC-031 (STL):** predictions enrich the positioning envelope ("what will happen") alongside facts ("what is true").
- **SPEC-033 (Safety Control Plane):** simulation-before-action hooks the existing HIGH-risk checkpoint path; it adds a *predicted-outcome* trigger to the existing *observed-outcome* triggers.
- **SPEC-006 (SPDL):** which risk levels simulate, the confidence floor, and the induction schedule are policy.
- **SPEC-056 (TEL):** a predicted outcome and any anticipatory checkpoint **MUST** be streamable as governance events (this is a strong demo: "the agent predicted this would breach scope, so it paused").

## 3.5 Conformance Requirements

- Induced rules **MUST** record support count and confidence; a rule with support below the configured minimum **MUST NOT** be used to block an action.
- Simulation-before-action **MUST** run for every operation at a configured HIGH-risk level and **MUST** fail *open to a checkpoint* (ask a human), never fail *closed to silent execution* and never fail *open to silent skipping*.
- Causal edges **MUST** distinguish textual from interventional evidence; a purely textual causal edge **MUST NOT** be presented as verified causality (see honesty note).
- Predictions used to gate actions **MUST** be written to the audit chain with their supporting rule, so an anticipatory block is itself auditable.

## 3.6 Security & Honesty Considerations

Two cautions the spec states plainly, because overclaiming here is both a technical and a reputational risk. First, **causal edges extracted from text are reported causality, not verified causality**; only the interventional support from the action log is genuine causal evidence, and even that assumes the logged action was the operative intervention. The spec therefore separates the two evidence types and forbids presenting textual causality as verified. Second, a **poisoned action log poisons the world model**: an adversary who can inject misleading transitions could teach the model that a harmful action is safe. Induction **MUST** run only over provenance-verified Tier-E records (SPEC-011), **SHOULD** weight by identity trust, and **SHOULD** flag rules whose support comes from a narrow set of sessions (a poisoning signature). The world model is a *safety aid that can be attacked*, so its predictions inform oversight — they do not replace it.

\newpage
# Part 4 — CRP-SPEC-052: Intent & Speech-Act Positioning (ISA)

```
Spec:        CRP-SPEC-052
Title:       Intent & Speech-Act Positioning — Pragmatic Interpretation and
             Cross-Session Coreference Before Envelope Packing
Status:      Proposed (Wave 2)
Version:     0.1
Requires:    CRP-SPEC-003 (Envelope), CRP-SPEC-031 (STL), CRP-SPEC-028 (Multi-Horizon Context),
             CRP-SPEC-009 (CKF)
Extends:     CRP-SPEC-003 (adds an interpreted-intent envelope section)
Author:      AutoCyber AI Pty Ltd
```

## 4.1 Abstract

CRP classifies content *complexity* (ENTITY_RICH / REASONING_DENSE / NARRATIVE) but not communicative *intent*. "Can you check the contract?", "Check the contract", and "I wonder if the contract covers this" are three different speech acts requiring different operations. This specification adds a tiny, fast intent-and-speech-act classifier at the front of the positioned tool loop, and an explicit cross-session **coreference resolution** pass so that "it", "that approach", and "the second option" are resolved to their referents before the envelope is packed. The SLM is then positioned with *interpreted intent*, not raw text — the difference between information extraction and natural-language *understanding*.

## 4.2 Motivation

Information extraction (CRP's strong 6-stage pipeline) is not the same as understanding meaning-in-context. Two pragmatic layers are missing. First, **speech acts and implied constraints**: the same propositional content can be a request, a question, an assertion, or an expressive, and the directness and emotional valence change what operation is appropriate. Second, **reference resolution across turns**, which is where SLMs fail hardest — retrieval-by-similarity (SPEC-028) surfaces relevant history but does not *resolve* "it" to a specific entity. Both are cheap to add with small local models (sub-10 ms), and both materially improve positioning, which improves everything downstream (routing, tool selection, quality).

## 4.3 Specification

### 4.3.1 The intent / speech-act classifier

A distilled classifier (SetFit or a small DeBERTa) tags each user turn. It runs before dispatch and its output becomes an envelope section (SPEC-003).

```python
# crp/isa/intent.py — fast speech-act + intent tagging (sub-10ms, local)
from dataclasses import dataclass
from setfit import SetFitModel      # few-shot, tiny, CPU-fast

@dataclass
class IntentTag:
    speech_act: str        # request | question | assertion | expressive
    directness: float      # 0 (hinted) .. 1 (explicit imperative)
    implied_constraints: list[str]
    valence: float         # -1 (frustrated) .. +1 (positive); informs tone, not logic

class IntentClassifier:
    def __init__(self, model="AutoCyberAI/crp-intent-setfit"):
        self._act = SetFitModel.from_pretrained(model)          # speech-act head

    def classify(self, turn: str, history: list[str]) -> IntentTag:
        act = self._act.predict([turn])[0]
        directness = self._directness(turn)
        return IntentTag(speech_act=act, directness=directness,
                         implied_constraints=self._constraints(turn),
                         valence=self._valence(turn))

    @staticmethod
    def _directness(turn: str) -> float:
        t = turn.strip().lower()
        if t.endswith("?") or t.startswith(("can you", "could you", "would you", "i wonder")):
            return 0.4                       # softened / indirect
        if t.startswith(("please ",)) or t.split()[0].endswith("s") is False:
            return 0.9                       # imperative
        return 0.7

    @staticmethod
    def _constraints(turn: str) -> list[str]:
        cons = []
        for kw, c in (("only", "restrict-scope"), ("without", "exclusion"),
                      ("before", "temporal-order"), ("must", "hard-constraint")):
            if kw in turn.lower():
                cons.append(c)
        return cons

    @staticmethod
    def _valence(turn: str) -> float:
        neg = sum(w in turn.lower() for w in ("still", "again", "broken", "wrong", "not working"))
        return -0.5 if neg else 0.0
```

### 4.3.2 Cross-session coreference resolution

Maintain a session-scoped entity registry (extend the CKF with discourse mentions) and rewrite ambiguous references before packing. Use a local neural coreference model (`fastcoref`/Maverick-class).

```python
# crp/isa/coref.py — resolve "it"/"that approach"/"the second option" before envelope packing
from fastcoref import FCoref

class CoreferenceResolver:
    def __init__(self):
        self._model = FCoref()          # local, fast neural coref

    def resolve(self, turn: str, session_entities: dict[str, str]) -> str:
        """Rewrite pronouns/deixis in `turn` using clusters + the session entity registry."""
        # 1) intra-turn + recent-window coref via the neural model
        text = " ".join(list(session_entities.values())[-6:] + [turn])
        preds = self._model.predict(texts=[text])
        clusters = preds[0].get_clusters()
        rewritten = turn
        for cluster in clusters:
            # canonical mention = the longest non-pronominal span in the cluster
            canonical = max((m for m in cluster if not _is_pronoun(m)),
                            key=len, default=None)
            if canonical:
                for mention in cluster:
                    if _is_pronoun(mention) and mention in rewritten:
                        rewritten = rewritten.replace(mention, canonical, 1)
        # 2) ordinal deixis ("the second option") against the registry
        rewritten = _resolve_ordinals(rewritten, session_entities)
        return rewritten

def _is_pronoun(m: str) -> bool:
    return m.lower() in {"it", "that", "this", "they", "them", "he", "she", "those", "these"}
```

### 4.3.3 Positioning with interpreted intent

The envelope gains an `interpreted_intent` section, so the SLM sees the resolved, pragmatically-tagged request.

```python
# crp/isa/position.py — assemble the interpreted-intent envelope section (SPEC-003)
def build_intent_section(raw_turn, intent_tag, resolved_turn) -> dict:
    return {
        "raw": raw_turn,
        "resolved": resolved_turn,                    # references rewritten
        "speech_act": intent_tag.speech_act,
        "directness": intent_tag.directness,
        "constraints": intent_tag.implied_constraints,
        "tone_hint": "acknowledge_friction" if intent_tag.valence < 0 else "neutral",
        "intent_confidence": _confidence(intent_tag),  # feeds SPEC-053 clarification gate
    }
```

## 4.4 Integration & Conformance (brief)

Extends the envelope (SPEC-003) with `interpreted_intent`; the registry extends CKF typed nodes (SPEC-009) with discourse mentions; retrieval remains SPEC-028's job (ISA *resolves* what retrieval *surfaces*). A conforming implementation **MUST** run coreference before envelope packing when the turn contains unresolved pronouns/deixis, **MUST** attach `intent_confidence` (consumed by SPEC-053), and **MUST** keep the classifier within a latency budget that does not regress the positioned tool loop (target sub-10 ms). It **MUST NOT** let valence/tone influence *logical* operation selection — tone informs phrasing, not what the agent does.

\newpage

# Part 5 — CRP-SPEC-053: The Clarification Protocol (CLR)

```
Spec:        CRP-SPEC-053
Title:       The Clarification Protocol — Ambiguity as a First-Class
             Protocol Primitive
Status:      Proposed (Wave 3)
Version:     0.1
Requires:    CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-033 (Inline HITL),
             CRP-SPEC-052 (ISA)
Extends:     CRP-SPEC-001 (adds a Clarification-Required response type)
Author:      AutoCyber AI Pty Ltd
```

## 5.1 Abstract

CRP has HITL checkpoints for *risk* (SPEC-033) but none for *ambiguity*. When intent is genuinely uncertain — the intent classifier's confidence is low, or two parses are near-equiprobable — the protocol should emit a structured **`CRP-Clarification-Required`** response instead of guessing. This makes interactive grounding a protocol primitive. No protocol in the MCP/A2A/CRP ecosystem has this today, so it is genuinely novel spec territory and arguably CRP's to claim.

## 5.2 Motivation

Guessing under ambiguity is the source of a large fraction of agent failures: the agent commits confidently to one reading of an ambiguous request and does the wrong thing efficiently. Humans resolve this by asking. Formalising "ask when uncertain" as a typed protocol response — rather than an ad-hoc model behaviour — makes it governable (you can *require* clarification above a risk×ambiguity threshold), auditable, and interoperable. It is active learning / interactive grounding lifted into the protocol layer.

## 5.3 Specification

### 5.3.1 The clarification trigger

Fire when ambiguity is high *and* the cost of a wrong guess is non-trivial. Ambiguity comes from SPEC-052's `intent_confidence` and from parse divergence; cost comes from the risk tier.

```python
# crp/clr/trigger.py — decide whether to clarify rather than guess
def should_clarify(intent_confidence: float, parse_divergence: float,
                   risk: str, policy) -> bool:
    ambiguity = (1 - intent_confidence) * 0.5 + parse_divergence * 0.5
    # clarify when ambiguity is high, scaled DOWN the more reversible the action is
    risk_weight = {"LOW": 0.3, "MEDIUM": 0.7, "HIGH": 1.0}[risk]
    return ambiguity * risk_weight >= policy.clarification_threshold   # e.g. 0.4
```

### 5.3.2 The structured response

Instead of an answer, the agent returns a typed clarification with the candidate interpretations, so the client can render a choice (and, via SPEC-056, stream it as an interrupt).

```python
# crp/clr/response.py — the CRP-Clarification-Required structured response
from dataclasses import dataclass, field

@dataclass
class Interpretation:
    reading: str            # a plain-language paraphrase of one candidate intent
    operations: list[str]   # what the agent would do under this reading
    probability: float

@dataclass
class ClarificationRequired:
    kind: str = "CRP-Clarification-Required"
    reason: str = ""
    interpretations: list[Interpretation] = field(default_factory=list)
    default: int | None = None      # index the agent would pick if forced (with consent)

def build_clarification(candidates: list[Interpretation], reason: str) -> dict:
    candidates.sort(key=lambda c: -c.probability)
    return {
        "kind": "CRP-Clarification-Required",
        "reason": reason,
        "interpretations": [c.__dict__ for c in candidates],
        "default": 0 if candidates[0].probability - candidates[1].probability > 0.25 else None,
    }
```

### 5.3.3 The header and lifecycle

A response header signals the clarification so intermediaries and clients handle it without parsing the body.

```
X-CRP-Clarification: required; candidates=2; reason="ambiguous-target"
```

The lifecycle: agent emits `CRP-Clarification-Required` → client presents interpretations (rendered as an AG-UI `INTERRUPT`, SPEC-056) → user selects → selection re-enters as a resolved turn (with the ISA envelope now unambiguous) → agent proceeds. The exchange is written to the audit chain, so "the agent asked rather than guessed" is provable — a genuine governance and safety property.

## 5.4 Integration & Conformance (brief)

Consumes SPEC-052's `intent_confidence`; renders via SPEC-033/SPEC-056 (interrupt); logs to SPEC-011. A conforming implementation **MUST** emit `CRP-Clarification-Required` rather than guess when `should_clarify` fires, **MUST** include at least two distinct interpretations with their operations, **MUST NOT** proceed on a defaulted interpretation for HIGH-risk actions without explicit consent, and **MUST** record both the clarification and the resolution. Policy (SPEC-006) **MAY** set the threshold and **MAY** require clarification unconditionally for specified operation classes.

\newpage
# Part 6 — CRP-SPEC-054: Structured Decoding Enforcement (SDE)

```
Spec:        CRP-SPEC-054
Title:       Structured Decoding Enforcement — Token-Level Grammar Constraints
             for Guaranteed-Valid Tool Calls
Status:      Proposed (Wave 1)
Version:     0.1
Requires:    CRP-SPEC-016 (Gateway), CRP-SPEC-008 (Dispatch), CRP-SPEC-031 (STL)
Extends:     CRP-SPEC-016 (enforces grammar at generation time in the runtime proxy)
Author:      AutoCyber AI Pty Ltd
```

## 6.1 Abstract

SLMs fail on tool calls not because they choose the wrong tool but because they emit *malformed* arguments — invalid JSON, wrong types, hallucinated fields. This specification enforces validity at the *token level* using grammar-constrained decoding in the CRP Gateway (SPEC-016): the model is *mechanically prevented* from emitting a token that would break the tool-call schema, eliminating the generate-validate-retry loop for structural validity entirely. It uses XGrammar — the default structured-generation backend for vLLM, SGLang, and TensorRT-LLM as of early 2026 — with a fallback to llguidance/Outlines depending on constraint shape.

## 6.2 Motivation

Structural tool-call failures are a whole *class* of SLM error that constrained decoding eliminates by construction: if the grammar forbids it, the model cannot generate it. Modern engines have removed the historical objection (early constrained decoding added 50–200% latency); XGrammar precomputes validity for the ~99% of vocabulary tokens whose validity is context-independent, reaching under ~40 microseconds per token with near-zero overhead, and grammar-constrained generation can even run *faster* than unconstrained because the search space is smaller. Adapting schemas to small models (SPEC-050) plus enforcing them at decode time (this spec) together close the SLM tool-call reliability gap — the two highest-leverage moves for the SLM-first fleet.

## 6.3 Specification

### 6.3.1 Compiling the tool schema to a grammar

The positioned tool loop (SPEC-031) already isolates the schema of the selected tool. SDE compiles that schema to an XGrammar constraint at selection time.

```python
# crp/sde/compile.py — compile the selected tool's JSON schema to an XGrammar grammar
import xgrammar as xgr
from functools import lru_cache
import json

@lru_cache(maxsize=512)
def compile_tool_grammar(tool_schema_json: str, tokenizer_info_key: str):
    """Compile once per (schema, tokenizer); cache — compilation is the only real cost."""
    schema = json.loads(tool_schema_json)
    tokenizer_info = _TOKENIZER_INFO[tokenizer_info_key]     # xgr.TokenizerInfo, prebuilt
    compiler = xgr.GrammarCompiler(tokenizer_info)
    # a tool call must be JSON matching the tool's argument schema
    return compiler.compile_json_schema(schema)
```

### 6.3.2 Enforcing the grammar during generation

At decode time the grammar produces a per-step bitmask over the vocabulary; invalid tokens are masked to `-inf` before sampling. This is the enforcement — the model physically cannot pick an invalid token.

```python
# crp/sde/enforce.py — apply the grammar as a logit mask each decode step (Gateway hook)
import xgrammar as xgr
import torch

class GrammarEnforcer:
    def __init__(self, compiled_grammar, vocab_size: int):
        self._matcher = xgr.GrammarMatcher(compiled_grammar)
        self._mask = xgr.allocate_token_bitmask(1, vocab_size)

    def mask_logits(self, logits: torch.Tensor) -> torch.Tensor:
        # fill the bitmask with the tokens VALID at this position, then apply it
        self._matcher.fill_next_token_bitmask(self._mask)
        xgr.apply_token_bitmask_inplace(logits, self._mask.to(logits.device))
        return logits                       # invalid tokens now -inf; sampling is safe

    def accept(self, token_id: int) -> bool:
        return self._matcher.accept_token(token_id)   # advance the grammar state

    def is_complete(self) -> bool:
        return self._matcher.is_terminated()
```

For a hosted runtime (vLLM/SGLang) the same is one request parameter — CRP sets it in the Gateway rather than hand-rolling the loop:

```python
# crp/sde/vllm_path.py — the hosted-runtime path: guided decoding as a request param
def build_vllm_request(prompt: str, tool_schema: dict) -> dict:
    return {
        "prompt": prompt,
        "guided_json": tool_schema,          # vLLM auto-selects XGrammar/Outlines by shape
        "guided_decoding_backend": "xgrammar",
        "temperature": 0.2,
    }
```

### 6.3.3 Choosing the engine by constraint shape

XGrammar (pushdown-automaton, CFG-capable) handles *recursive/nested* schemas; FSM-based Outlines flattens recursion and should be avoided for deep trees; llguidance is strong for dynamic per-request schemas. SDE selects per schema.

```python
# crp/sde/select_engine.py — pick the grammar engine by schema shape
def select_engine(schema: dict) -> str:
    if _has_recursion(schema) or _max_depth(schema) > 3:
        return "xgrammar"        # CFG engine for nested/recursive
    if _is_per_request_dynamic(schema):
        return "llguidance"      # fast TTFT on changing schemas
    return "xgrammar"            # default; it is the vLLM/SGLang default backend anyway
```

## 6.4 Integration & Conformance (brief)

Runs in the Gateway (SPEC-016) on the generation path; consumes the isolated schema from the positioned tool loop (SPEC-031); composes with schema adaptation (SPEC-050) — adapt first, then enforce the adapted schema. A conforming implementation **MUST** enforce the selected tool's argument grammar at decode time for all tool-calling generations, **MUST** cache compiled grammars per `(schema, tokenizer)`, **MUST** select a CFG-capable engine for recursive schemas, and **MUST NOT** rely on post-hoc validation as the *primary* guarantee (enforcement is primary; validation is a defence-in-depth check). Because enforcement guarantees *structural* validity only, semantic validity (SPEC-005 grounding, SPEC-049 verification) **MUST** still run.

## 6.5 Security Considerations

Grammar enforcement is itself a safety control: it makes prompt-injection-induced malformed calls impossible and constrains an attacker to the *shape* the schema allows. But it does not constrain *values* within the shape — a grammatically-valid call can still be semantically dangerous — so the trusted policy gate (tool-use volume) and predictive simulation (SPEC-051) remain necessary. Formal expressions consumed by the Verification Relay (SPEC-049) **MUST** be generated under SDE, closing the injection vector noted in SPEC-049 §1.6.

\newpage

# Part 7 — CRP-SPEC-055: Epistemic Profiles & Calibration (EP)

```
Spec:        CRP-SPEC-055
Title:       Epistemic Profiles — Per-Model, Per-Task Calibration Tracking
             and Semantic-Entropy Uncertainty
Status:      Proposed (Wave 2)
Version:     0.1
Requires:    CRP-SPEC-009 (CKF), CRP-SPEC-026 (SQB), CRP-SPEC-021 (ROS), CRP-SPEC-049 (VR)
Extends:     CRP-SPEC-031 (positions with the model's known blind spots)
Author:      AutoCyber AI Pty Ltd
```

## 7.1 Abstract

Quality tiers measure the *output*; nothing measures the *model's self-knowledge*. This specification tracks, per model and per task type, the gap between the model's implicit confidence (logprobs, self-consistency, self-rating) and its DPE/VR-verified correctness, storing a **calibration curve** in the CKF. Positioning can then include the model's known blind spots ("this model is overconfident on legal reasoning — apply stricter grounding"). It also wires **semantic entropy** — divergence across sampled reasoning paths — directly into the quality tier and risk score as a cheap, principled uncertainty signal.

## 7.2 Motivation

Models still do not reliably know what they do not know; this is an unsolved industry-wide problem, and honesty requires saying so. But two *partial* signals are cheap and CRP already produces their inputs. First, **calibration drift**: over many verified outcomes, a model's confidence-vs-correctness curve is measurable, and a model that is systematically overconfident on a task type is a known, correctable risk. Second, **semantic entropy** (clustering sampled answers by meaning and measuring the spread) is the best cheap uncertainty estimator available, and CRP's ROS (SPEC-021) already samples multiple reasoning paths — the divergence is currently under-used. Both turn latent uncertainty into an explicit, governable signal.

## 7.3 Specification

### 7.3.1 Semantic entropy from self-consistency samples

Cluster the N sampled answers by semantic equivalence (bidirectional entailment) and compute entropy over the clusters. Low clusters + high agreement = confident; many clusters = uncertain.

```python
# crp/ep/semantic_entropy.py — uncertainty from meaning-level divergence across samples
import math
from transformers import pipeline

_nli = pipeline("text-classification", model="microsoft/deberta-large-mnli", top_k=None)

def _equivalent(a: str, b: str) -> bool:
    ab = max(_nli(f"{a} [SEP] {b}"), key=lambda d: d["score"])["label"]
    ba = max(_nli(f"{b} [SEP] {a}"), key=lambda d: d["score"])["label"]
    return ab == "ENTAILMENT" and ba == "ENTAILMENT"     # bidirectional => same meaning

def semantic_entropy(samples: list[str]) -> float:
    clusters: list[list[str]] = []
    for s in samples:
        for c in clusters:
            if _equivalent(s, c[0]):
                c.append(s); break
        else:
            clusters.append([s])
    n = len(samples)
    probs = [len(c) / n for c in clusters]
    h = -sum(p * math.log(p) for p in probs)             # entropy over meaning-clusters
    return round(h / math.log(n) if n > 1 else 0.0, 3)   # normalised 0..1
```

### 7.3.2 The calibration curve, stored in the CKF

Bin verified outcomes by the model's stated/implicit confidence; the reliability curve (confidence vs empirical correctness) is the epistemic profile.

```python
# crp/ep/calibration.py — per-model, per-task calibration curves in the CKF
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class CalibrationProfile:
    model_id: str
    task_kind: str
    bins: dict = field(default_factory=lambda: defaultdict(lambda: [0, 0]))  # conf_bin -> [correct, total]

    def observe(self, confidence: float, correct: bool):
        b = round(confidence, 1)                 # 0.0..1.0 in 0.1 bins
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
                ece += (n / total) * abs(acc - conf)     # gap between confidence and accuracy
        return round(ece, 3)

    def overconfident_on(self, threshold=0.15) -> bool:
        # is empirical accuracy consistently below stated confidence?
        return self.expected_calibration_error() >= threshold
```

### 7.3.3 Feeding tier/risk and positioning

Semantic entropy and calibration both adjust the quality tier and risk, and inject a positioning hint.

```python
# crp/ep/apply.py — wire calibration + entropy into tier, risk, and positioning
def epistemic_adjust(base_tier: str, risk: str, entropy: float,
                     profile) -> dict:
    out = {"tier": base_tier, "risk": risk, "positioning_hint": None}
    if entropy > 0.6:                              # samples disagree in meaning
        out["risk"] = _raise(risk)                 # high semantic entropy => raise risk
        out["tier"] = _cap(base_tier, "B")         # and cap the tier
    if profile and profile.overconfident_on():
        out["positioning_hint"] = (f"{profile.model_id} is overconfident on "
                                   f"{profile.task_kind}; apply stricter grounding thresholds")
        out["risk"] = _raise(out["risk"])
    return out
```

## 7.4 Integration & Conformance (brief)

Calibration profiles are CKF nodes (SPEC-009); entropy consumes ROS samples (SPEC-021); correctness labels come from DPE/VR (SPEC-005/049); adjustments flow to SQB tiering (SPEC-026) and STL positioning (SPEC-031). A conforming implementation **MUST** compute semantic entropy over meaning-clusters (bidirectional entailment), not surface-string equality; **MUST** update calibration only from verified outcomes; **MUST** surface an overconfidence hint into positioning when ECE exceeds the configured threshold; and **MUST NOT** present any of these as a solution to the calibration problem — they are signals that *narrow* the gap, and the spec says so, per the frontier-honesty rule.

\newpage
# Part 8 — CRP-SPEC-056: The Transparency Emission Layer (TEL)

```
Spec:        CRP-SPEC-056
Title:       The Transparency Emission Layer — Streaming CRP's Governance
             Evidence as Standard, Faithful, Verifiable Events
Status:      Proposed (Wave 1)
Version:     0.1
Requires:    CRP-SPEC-016 (Gateway), CRP-SPEC-005 (DPE), CRP-SPEC-011 (Audit),
             CRP-SPEC-030 (CSO), CRP-SPEC-049 (VR)
Extends:     the CRP Streaming guide; makes governance legible on the wire
Author:      AutoCyber AI Pty Ltd
```

## 8.1 Abstract

CRP *generates* more governance evidence than any competitor but has no standard layer to *emit and display* it. This specification defines the Transparency Emission Layer: it maps CRP's internal events onto the **AG-UI** event standard (so any AG-UI frontend renders a CRP agent), adds a **namespaced governance-event vocabulary** (`crp.safety_scan`, `crp.policy`, `crp.quality`, `crp.provenance`, …), enforces a **faithful-narration contract** (every narrated claim entailment-checked against the trace), and streams the **audit chain** as a client-verifiable provenance layer. This is the concrete realisation of the D1–D6 roadmap from *The Architecture of Transparency*.

## 8.2 Motivation

The transparency volume's finding: the industry streams *what the agent does* (tokens, tools, state) but not *whether what it says is true, whether what it did was allowed, and whether any of it can be proven*. CRP is uniquely able to stream those three because it alone generates the evidence. TEL is therefore not a UI feature — it is the emission layer that converts CRP's invisible governance into its most visible differentiator. Adopting AG-UI (the cross-framework event standard now emitted by LangGraph, CrewAI, Mastra, Microsoft, and AWS runtimes) means CRP inherits an entire frontend ecosystem for free while extending it where governance requires.

## 8.3 Specification (the six extensions, condensed to normative form)

### 8.3.1 D1 — CRP → AG-UI event mapping

Emit standard AG-UI lifecycle/text/reasoning/tool/state events from the runtime, plus namespaced `CUSTOM` governance events. (Full event model and SSE server are given in *The Architecture of Transparency*, Templates 1–3; the adapter is Template 12.)

```python
# crp/tel/adapter.py — map CRP runtime hooks to AG-UI-compatible events (D1 + D2)
from crp.tel.events import Event, custom, tool_start, tool_result   # AG-UI-compatible model

class CRPEmitter:
    def __init__(self, emit): self.emit = emit
    # D2 governance vocabulary — the events NO competitor streams:
    def dpe_stage(self, stage, risk, ms, verdict):
        self.emit(custom("crp.safety_scan", {"stage": stage, "risk": risk,
                                             "ms": ms, "verdict": verdict}))
    def verification(self, ratio, invalid, repairs):        # SPEC-049 on the wire
        self.emit(custom("crp.verification", {"ratio": ratio, "invalid": invalid,
                                             "repairs": repairs}))
    def quality(self, tier, confidence, entropy):           # SPEC-026 + SPEC-055
        self.emit(custom("crp.quality", {"tier": tier, "confidence": confidence,
                                        "semantic_entropy": entropy}))
    def prediction(self, action, predicted, conf):          # SPEC-051 anticipatory oversight
        self.emit(custom("crp.prediction", {"action": action, "predicted": predicted,
                                           "confidence": conf}))
    def provenance(self, prev_hash, this_hash, op):         # D4 live audit chain
        self.emit(custom("crp.provenance", {"op": op, "prev": prev_hash, "hash": this_hash}))
```

### 8.3.2 D3 — the faithful-narration contract

Every `TEXT_MESSAGE_CONTENT` summary sentence **MUST** be entailment-checked against the event trace before it is streamed; unsupported sentences are withheld. This reuses CRP's existing verification (DPE/VR) pointed at *narration*, and is the guarantee no competitor offers. (Implementation: *Transparency* Template 7.)

### 8.3.3 D4 — live verifiable provenance

Stream the HMAC audit chain link-by-link (`crp.provenance`) so an auditor-tier client recomputes and verifies tamper-evidence in the browser, in real time. Turns "trust us" into "check for yourself."

### 8.3.4 D5 — quality & confidence streaming

Emit `crp.quality` (tier + calibrated confidence + semantic entropy) as an always-visible badge, countering over-trust by making epistemic humility legible (SPEC-055).

### 8.3.5 D6 — resumable transparency across windows

Back the event stream with the CSO relay (SPEC-030) and `Last-Event-ID` replay so a long, continuation-relayed engagement can be left and resumed with full transparency intact — a capability token-streamers lack because they have no persistent governed session state.

## 8.4 Integration & Conformance (brief)

Runs in the Gateway (SPEC-016); consumes DPE (005), VR (049), SQB (026), EP (055), PP (051) outputs; streams over the CRP Streaming transport (SSE default). A conforming implementation **MUST** emit standard AG-UI events for lifecycle/text/tool/state so generic frontends render CRP agents; **MUST** emit governance as namespaced `CUSTOM` events so they degrade gracefully; **MUST** entailment-check narration before display (D3); **MUST** make the audit chain client-verifiable (D4); and **MUST** support `Last-Event-ID` replay for resumability (D6). It **MUST NOT** stream a narrated claim the trace does not support, under any engagement pressure.

## 8.5 Security Considerations

The stream carries partly-adversarial content (tool output from untrusted targets); rendered content **MUST** be inert/declarative (A2UI), never executable, and every value **MUST** carry a provenance taint (see *Transparency* §32). Stream endpoints **MUST** be authenticated and tenant-isolated (Clerk SSO); `STATE_DELTA` patches **MUST** be hardened against prototype pollution. Because TEL exposes governance internals, the *disclosure tier* (SPEC-006 policy) governs which events reach which identities — an external user **MUST NOT** receive auditor-tier provenance unless authorised.

\newpage

# Part 9 — CRP-SPEC-057: Bi-Temporal CKF (BTF)

```
Spec:        CRP-SPEC-057
Title:       Bi-Temporal Contextual Knowledge Fabric — Event-Time vs
             Ingestion-Time Fact Validity
Status:      Proposed (Wave 3)
Version:     0.1
Requires:    CRP-SPEC-009 (CKF), CRP-SPEC-027 (Retrieval Integrity)
Extends:     CRP-SPEC-009 (adds validity intervals to facts and edges)
Author:      AutoCyber AI Pty Ltd
```

## 9.1 Abstract

CKF facts are currently point-in-time assertions. This specification adds **bi-temporal** validity — tracking both *event time* (when a fact was true in the world) and *ingestion time* (when CRP learned it) — so the fabric can answer "what did we believe on date X?" and "what was actually true during period Y?" separately. This is the one idea worth borrowing from temporal knowledge-graph systems (the Graphiti bi-temporal model), and it materially improves retrieval correctness for facts that change over time.

## 9.2 Motivation

Facts expire and supersede. "The production database is on host .40" was true until the migration; a retrieval that returns it *after* the migration is grounded in a stale fact and produces a confidently wrong answer. Similarity retrieval (SPEC-028) has no notion of temporal validity, so it cannot distinguish current from superseded facts. Bi-temporality fixes this at the substrate: every fact carries `[valid_from, valid_to]` (event time) and `[ingested_at, invalidated_at]` (ingestion time), and retrieval filters by the query's temporal context. It also enables honest audit ("we acted correctly on what we knew *then*, even though the fact later changed").

## 9.3 Specification

```python
# crp/btf/temporal.py — bi-temporal facts + as-of retrieval in the CKF
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BiTemporalFact:
    subject: str; predicate: str; object: str
    valid_from: datetime                 # event time: when true in the world
    valid_to: datetime | None = None     # None = still valid
    ingested_at: datetime = None         # ingestion time: when CRP learned it
    invalidated_at: datetime | None = None   # when CRP stopped believing it

    def true_in_world_at(self, t: datetime) -> bool:
        return self.valid_from <= t and (self.valid_to is None or t < self.valid_to)

    def believed_by_system_at(self, t: datetime) -> bool:
        return self.ingested_at <= t and (self.invalidated_at is None or t < self.invalidated_at)

def supersede(ckf, fact: BiTemporalFact, new_object: str, at: datetime):
    """A new value arrives: close the old fact's validity and insert the new one."""
    fact.valid_to = at
    fact.invalidated_at = datetime.utcnow()
    ckf.update(fact)
    ckf.insert(BiTemporalFact(fact.subject, fact.predicate, new_object,
                              valid_from=at, ingested_at=datetime.utcnow()))

def retrieve_as_of(ckf, subject: str, predicate: str, world_time: datetime) -> BiTemporalFact | None:
    """Return the fact that was TRUE IN THE WORLD at world_time (not the latest)."""
    candidates = ckf.facts(subject=subject, predicate=predicate)
    return next((f for f in candidates if f.true_in_world_at(world_time)), None)
```

## 9.4 Integration & Conformance (brief)

Extends CKF facts/edges (SPEC-009) with the four timestamps; retrieval (SPEC-028) gains an `as_of` temporal filter; retrieval integrity (SPEC-027) verifies temporal consistency. A conforming implementation **MUST** record both event time and ingestion time for time-sensitive facts, **MUST** supersede rather than overwrite when a fact changes (preserving history), and **MUST** support as-of retrieval by world time. Retrieval for a current query **SHOULD** default to `valid_to is None` (currently-true) facts unless the query specifies a historical context.

\newpage
# Appendix A — Reference Integration: One Request Through All Nine Specs

The fastest way to see "exactly how it fits" is to trace a single request through the whole enhanced stack. Here is one pentest instruction — *"can you check if .40 is still exposed?"* — flowing through all nine specs in order, showing which spec owns which decision and what it emits. This is the composition, made concrete.

```python
# reference_integration.py — one request, all nine specs, in dispatch order
from crp.isa import IntentClassifier, CoreferenceResolver, build_intent_section
from crp.clr import should_clarify, build_clarification
from crp.qsr import LearnedRouter, run_with_escalation, adapt_schema
from crp.sde import compile_tool_grammar, GrammarEnforcer
from crp.vr import VerificationRelay, Claim
from crp.pp import WorldModel, guarded_dispatch
from crp.ep import semantic_entropy, epistemic_adjust
from crp.tel import CRPEmitter
from crp.btf import retrieve_as_of

def handle(turn: str, session, emit, world: WorldModel, policy):
    crp = CRPEmitter(emit)                                   # SPEC-056: start streaming
    crp.emit(...)  # RUN_STARTED

    # 1) SPEC-052 ISA — interpret intent + resolve "it"/".40"/"still"
    intent = IntentClassifier().classify(turn, session.history)
    resolved = CoreferenceResolver().resolve(turn, session.entities)   # "check if .40 is exposed"
    intent_section = build_intent_section(turn, intent, resolved)
    crp.dpe_stage("intent_positioning", "LOW", 6, "pass")

    # 2) SPEC-053 CLR — is intent ambiguous enough to ask rather than guess?
    if should_clarify(intent_section["intent_confidence"], parse_divergence=0.1,
                      risk="MEDIUM", policy=policy):
        return build_clarification(...)                      # emit CRP-Clarification-Required, stop

    # 3) SPEC-057 BTF — retrieve the CURRENT fact, not a stale one
    fact = retrieve_as_of(session.ckf, ".40", "exposure_state", world_time=now())
    # (avoids grounding on a pre-remediation "exposed" fact that was later fixed)

    # 4) SPEC-050 QSR — route to the right local model; adapt schema if needed
    task = build_task(resolved, intent_section, fact)
    model_id = LearnedRouter().route(task)                   # e.g. qwen3-coder-7b
    tool_schema = adapt_schema(PORT_SCAN_SCHEMA, ceiling=FLEET[model_id].schema_complexity_ceiling)
    crp.emit(...)  # tool_start(port_scan, reason="verify .40 exposure")

    # 5) SPEC-054 SDE — compile + enforce the tool-call grammar (valid args guaranteed)
    grammar = compile_tool_grammar(json.dumps(tool_schema), model_id)
    enforcer = GrammarEnforcer(grammar, vocab_size=VOCAB)    # masks invalid tokens at decode

    # 6) SPEC-051 PP — HIGH-risk? predict outcome BEFORE acting; checkpoint if it predicts harm
    state = current_state(session, fact)
    def do_scan(state, action, prediction=None):
        return execute_scan(".40", enforcer=enforcer)        # runs under grammar enforcement
    result = guarded_dispatch(state, "port_scan:aggressive", risk="HIGH",
                              world=world, policy=policy, execute_fn=do_scan,
                              checkpoint_fn=lambda **k: crp.prediction(**k) or ask_human(**k))

    # 7) SPEC-049 VR — verify the reasoning that turns raw ports into a "still exposed" claim
    claims = extract_claims(result)   # e.g. inference: "port 443 open => service reachable => exposed"
    vr = VerificationRelay().verify_trace(claims, ctx={"fact": fact}, repair_fn=repair_with_slm)
    crp.verification(vr["verification_ratio"], vr["invalid"], vr["repairs"])

    # 8) SPEC-055 EP — uncertainty from sample divergence + this model's calibration
    entropy = semantic_entropy(sample_conclusions(result, n=5))
    adjusted = epistemic_adjust(base_tier=vr_tier(vr), risk=result["risk"],
                                entropy=entropy, profile=session.calibration(model_id, task.kind))
    crp.quality(adjusted["tier"], confidence=1 - entropy, entropy=entropy)

    # 9) SPEC-056 TEL — faithful, entailment-checked narration + provenance, then finish
    narrate_final_faithful(crp, session, trace=vr["labels"])  # withholds unsupported claims
    crp.provenance(prev_hash=session.audit.prev, this_hash=session.audit.commit(), op="scan")
    crp.emit(...)  # RUN_FINISHED
    return result
```

Read top to bottom, the ownership is unambiguous — which is the "where it fits" answer in executable form:

- **ISA (052)** turns *"check if .40 is still exposed"* from raw text into resolved, intent-tagged input, so everything downstream reasons over meaning, not surface string.
- **CLR (053)** decides whether the request is clear enough to proceed or must be negotiated — the guess-vs-ask gate.
- **BTF (057)** ensures the grounding fact is *current*, not a superseded "exposed" from before a fix.
- **QSR (050)** picks the right local specialist and right-sizes the schema for it.
- **SDE (054)** guarantees the tool call is structurally valid by construction — no malformed-args failure is possible.
- **PP (051)** predicts the consequence of an aggressive scan and checkpoints *before* acting if it foresees a scope breach — anticipatory oversight.
- **VR (049)** verifies the inference from open ports to "still exposed" is logically valid, repairing it if not.
- **EP (055)** attaches honest uncertainty from sample divergence and this model's known calibration.
- **TEL (056)** streams the whole thing as faithful, governed, provable events from start to finish.

Every arrow between these is data CRP already produces flowing into a control point CRP already owns. That is why the program is *additive*, not a rewrite: nine modules on the existing spine.

\newpage

# Appendix B — Consolidated Build Checklist

The normative `MUST` requirements across all nine specs, organised as a wave-by-wave build checklist. Ship a wave, verify its checklist, move on.

**Wave 1 — Foundations (build now; data already exists)**

- [ ] **SPEC-049 VR:** symbolic verifiers (Z3 + sandboxed exec) run at every depth; PRM runs at thorough/exhaustive; unrepaired INVALID caps tier at D and raises risk to HIGH; step verdicts written to audit; sandbox isolated/network-denied; formal exprs generated under SDE.
- [ ] **SPEC-054 SDE:** tool-call grammar enforced at decode time for all tool calls; grammars cached per `(schema, tokenizer)`; CFG engine (XGrammar) for recursive schemas; enforcement is primary, validation defence-in-depth; semantic checks (VR/DPE) still run.
- [ ] **SPEC-056 TEL:** standard AG-UI events for lifecycle/text/tool/state; governance as namespaced `CUSTOM` events; narration entailment-checked before display; audit chain client-verifiable; `Last-Event-ID` replay; rendered tool output inert/declarative; endpoints authenticated + tenant-isolated.

**Wave 2 — Learning flywheels (need Wave 1 verdicts as labels)**

- [ ] **SPEC-050 QSR:** cold-start on capability profiles until ≥200 tier-A/S examples; exclude models below schema ceiling unless adapted; escalation driven by failure signals + `max_rungs`; decisions written back to audit; train only on provenance-verified records; cloud escalation re-applies full DPE.
- [ ] **SPEC-055 EP:** semantic entropy over meaning-clusters (bidirectional entailment), not string equality; calibration updated only from verified outcomes; overconfidence hint injected into positioning above ECE threshold; never presented as solving calibration.
- [ ] **SPEC-052 ISA:** coreference before envelope packing when pronouns/deixis present; `intent_confidence` attached (feeds CLR); sub-10 ms budget; tone influences phrasing only, never operation selection.

**Wave 3 — Frontier (turn the action log into a world model)**

- [ ] **SPEC-051 PP:** rules record support + confidence; below-min-support rules never block; simulation runs for configured HIGH-risk ops and fails to a *checkpoint*; textual vs interventional causal evidence distinguished; predictions written to audit; induction only over provenance-verified Tier-E.
- [ ] **SPEC-053 CLR:** emit `CRP-Clarification-Required` rather than guess when triggered; ≥2 distinct interpretations with operations; no defaulted HIGH-risk proceed without consent; clarification + resolution logged.
- [ ] **SPEC-057 BTF:** record event time + ingestion time for time-sensitive facts; supersede rather than overwrite; support as-of retrieval; default to currently-valid facts unless historical context requested.

**Cross-cutting (every wave)**

- [ ] All new signals stream via TEL as governance events (so each build is immediately demonstrable).
- [ ] All training/induction reads only HMAC-verified audit/action records (SPEC-011) — the flywheels are only as trustworthy as their labels.
- [ ] No frontier capability (calibration, causality, comprehension) is overclaimed in docs, specs, or pitches — the honesty rule is itself a conformance requirement, because it is what makes the credible claims credible.

\newpage
# Part 10 — What Would Make CRP the Go-To Protocol

Having specified the nine builds, step back to the strategic question: with these shipped, why would a serious team *choose CRP* over assembling MCP + a framework + an observability vendor themselves? The answer is not any single spec. It is four properties that only emerge when the specs are taken together, and that no competitor can replicate without first rebuilding CRP's foundation.

## 10.1 CRP's honest identity: understanding is a systems property, and CRP is the system

The deepest insight from the whole series is that **"understanding" in SLM-first systems is not a property of the model — it is a property of the system around the model.** A 4B model does not understand a compliance requirement; a 4B model *positioned* with the right facts, *constrained* to valid tool calls, *verified* against logic, *routed* to its competence, *aware* of its own miscalibration, *predicting* the consequences of its actions, and *narrating* faithfully — that composite *behaves* as though it understands, within scope. CRP is the composite. This reframes CRP's category: it is not "another agent framework" and not "MCP with more headers." It is the **governance and cognition substrate that makes small models trustworthy** — the layer that converts cheap, private, local inference into governed, auditable, reliable agentic work. That identity is defensible because it is *true*, and because every one of the nine specs is a load-bearing piece of it.

## 10.2 The three flywheels are an unreplicable data moat

Competitors can copy a spec. They cannot copy the data. The three flywheels (Part 0.4) all run on evidence CRP generates as a byproduct of governance and *no one else collects*:

- **Step-level correctness labels** (from the Verification Relay) train reward models and calibration curves. Nobody else verifies inference, so nobody else has these labels.
- **Quality-tier-labelled routing outcomes** train the learned router. Nobody else scores quality per call, so nobody else can supervise routing this way.
- **Logged interventions** (the action log) induce a world model. Nobody else records governed action-outcome pairs at fleet scale, so nobody else has causal-discovery data.

Each flywheel improves with usage, and each is fed by a proprietary data stream that only exists *because* CRP does governance. This is the classic data-network-effect moat, and it is unusually strong here because the data is not scraped or bought — it is *generated by the product's core function*. A competitor starting today would need to build CRP's entire scoring, verification, and audit layer *first*, and then wait for usage to accumulate the data, before they could begin to compete on the flywheels. That is a multi-year moat that widens with every CRP deployment.

## 10.3 The standards plays no one else is positioned to make

Two of the specs are *open protocol territory* that CRP can define and own, because they sit exactly at CRP's governance focus and are absent from every peer protocol:

- **The governance-event vocabulary (SPEC-056).** AG-UI standardised *execution* events (lifecycle, tool, state). There is **no** cross-vendor standard for *governance* events — safety stage, risk, policy verdict, verification ratio, provenance link. CRP can publish this vocabulary as the extension every governed agent emits, the way AG-UI became the execution standard. First mover in an empty, high-value slot.
- **The clarification primitive (SPEC-053).** MCP has no ambiguity-negotiation primitive; A2A has none; no agent protocol does. "Ask when genuinely uncertain, as a typed, governable, auditable protocol response" is genuinely novel and squarely in CRP's interactive-grounding wheelhouse. Owning it makes CRP the protocol that *negotiates* rather than *guesses* — a safety story and a differentiation story at once.

CRP already engages the IETF/IANA track. These two specs are the ones worth pushing there, because standardising them makes CRP the *reference* — and a protocol that defines the standard is, by definition, the go-to.

## 10.4 The compliance story becomes anticipatory, not just documentary

Most "AI governance" tooling is *documentary* — it records what happened for an audit after the fact. CRP's nine specs make governance *anticipatory*: predictive simulation (SPEC-051) turns EU AI Act Article 14 human oversight into a *pre-action* checkpoint ("the agent predicted this would breach scope, so it paused and asked"); the clarification protocol (SPEC-053) prevents wrong actions rather than logging them; the verification relay (SPEC-049) catches invalid reasoning before it becomes a decision; faithful narration (SPEC-056) guarantees the record is true. For a buyer in a regulated domain, "our agent *prevents* violations and *proves* it did" is a categorically stronger proposition than "our agent *logs* violations for review." This is the enterprise closer, and it falls directly out of the architecture.

## 10.5 The one-sentence version

Put everything in a sentence a buyer remembers: **CRP is the only protocol that makes small, private, local models behave as trustworthy agents — verifying their reasoning, learning from their outcomes, predicting their actions' consequences, and streaming faithful, provable evidence of all of it — and it improves itself with every deployment.** The nine specs are what make that sentence true. Ship Wave 1 and it is demonstrably true; ship Waves 2 and 3 and it becomes unassailable.

\newpage

# Part 11 — The Forward Research Agenda for Agentic AI

You asked what else is worth researching. Here is the agenda, framed by how genuinely open each area is, and — where relevant — how it connects to CRP. These are the areas where the next reports in this series could go, and where research-credible contributions are still available.

## 11.1 Near-term, high-leverage (buildable, with real gaps to close)

**Multi-agent trust, delegation, and coordination protocols.** The single-agent story is maturing; the multi-agent story is wide open. When agent A delegates to agent B, what governance travels with the delegation? How is trust established, scoped, and revoked? How do CRP's identity headers and policy envelopes compose across an agent-to-agent boundary? A2A moves *messages*; it does not move *governance*. A "governed delegation" spec — CRP's policy envelope and audit chain crossing the A2A boundary — is a natural tenth spec and a genuinely open area.

**Evaluation science for agents.** We still lack good ways to measure whether an agent is *good* — not on benchmarks, but on real, long-horizon, tool-using, multi-step tasks with partial credit and safety constraints. CRP's quality tiers and verification verdicts are a start, but a rigorous *agent evaluation methodology* (with reproducibility, partial credit, safety-weighted scoring) is unbuilt industry-wide and would be a strong research contribution — and CRP's logged outcomes are the ideal dataset.

**Adversarial robustness and agent security.** The tool-use volume flagged indirect prompt injection through tool output as unsolved; it is the tip of an iceberg. Agent-specific attack surfaces — poisoned retrieval, malicious tool results, confused-deputy escalation, world-model poisoning (SPEC-051 §3.6), flywheel poisoning (SPEC-050 §2.6) — are under-studied and directly relevant to AutoCyber's security identity. A systematic *agent threat model and defence catalogue* is both a research paper and a product.

**Memory consolidation and forgetting.** CRP has strong session/persistent memory (SPEC-045) and now bi-temporal facts (SPEC-057), but *what to forget, when, and how to consolidate* — the analogue of sleep-time memory replay — is an active, tractable frontier. Bi-temporality is the substrate; a principled consolidation policy is the open work.

## 11.2 Medium-term, harder (partial solutions exist; robustness is open)

**Ontology-grounded reasoning.** Layering domain ontologies onto the CKF (ontology-constrained retrieval has shown large fact-recall gains) ties into CRP's Authoritative Domain Agent (SPEC-044) and could sharply improve grounding in regulated verticals. The research question is *automatic* ontology alignment, which is not solved.

**Calibration and selective prediction.** SPEC-055 narrows the gap with semantic entropy and calibration curves, but reliable "the model knows what it doesn't know" is unsolved. Conformal prediction (distribution-free uncertainty with coverage guarantees) is the most promising rigorous direction and is worth a dedicated investigation — a conformal wrapper over CRP's tiers would be a strong, novel contribution.

**Neurosymbolic world models at depth.** SPEC-051 induces shallow transition rules; deep, compositional, transferable world models for open-ended environments (the WALL-E frontier and its energy-based successors) are genuinely open. CRP's action log is the data; the modelling is the research.

## 11.3 Frontier, largely unsolved (name the openness honestly)

These are the areas to *understand* and *not overclaim*, because being straight about them is part of CRP's credibility:

- **Genuine causal discovery from agent behaviour.** SPEC-051's "actions are interventions" observation is the closest practical handle, but true causal identification (do-calculus, confounding control) from observational-plus-interventional logs is unsolved. This is the most research-paper-worthy open thread in the whole program — worth a focused study, not a product claim.
- **Theory of mind / user belief modelling.** Production-grade tracking of *the user's* evolving beliefs and intentions barely exists; CRP's identity headers are a coarse proxy. A "collaborative belief-state" layer is deep, valuable, and open.
- **Weight-level continual learning without catastrophic forgetting, on-device.** Every learning mechanism in this program (VR training, router flywheel, world-model induction) is *context-* or *periodic-retrain* level. True on-device lifelong learning at the weights remains open, and honestly acknowledging that is better than implying CRP learns continuously at the weight level.
- **Embodied / sensorimotor grounding for local SLMs.** Multimodal SLMs exist; meaningful sensorimotor grounding on consumer hardware does not. Relevant only if CRP moves toward robotics/IoT, but worth watching.
- **The symbol-grounding and comprehension question.** No system — CRP included, frontier labs included — has genuine intentionality or comprehension; everything is *functional* understanding, behaviour indistinguishable from understanding within scope. Protocol scaffolding narrows the behavioural gap; it does not close the ontological one. This is the claim to *never* make in an IETF thread or a pitch, and saying so plainly is what makes the rest of CRP's claims credible.

## 11.4 A concrete next spec: CRP-SPEC-058 Governed Delegation (preview)

To make the "multi-agent governance" recommendation actionable rather than aspirational, here is the shape of the tenth spec — the natural Wave 4 — sketched to the same standard.

```
Spec:     CRP-SPEC-058 (preview)
Title:    Governed Delegation — Carrying the Policy Envelope, Audit Chain,
          and Verification Guarantees Across an Agent-to-Agent Boundary
Requires: CRP-SPEC-002 (Headers), 006 (SPDL), 011 (Audit), 033 (Control Plane),
          049 (VR), 056 (TEL); interoperates with A2A
```

The problem: when agent A delegates a sub-task to agent B, A2A moves the *message* but nothing moves the *governance* — B runs under its own (or no) policy, its reasoning is unverified from A's perspective, and the audit chain forks. Governed delegation closes this with three mechanisms. A **delegation envelope** propagates A's policy envelope, identity, depth, and safety budget to B as signed headers, so B inherits A's constraints (a sub-agent cannot exceed the scope its delegator was granted — the least-privilege principle across the agent boundary). A **cross-agent audit link** binds B's audit sub-chain into A's via the HMAC chain (SPEC-011), so the whole delegated computation is one verifiable provenance graph. And a **verification handshake**: A **MUST** be able to require that B's returned result carry a VR verdict (SPEC-049) and a faithful-narration attestation (SPEC-056), so A can trust B's output at the same standard A holds itself to — or reject it.

```python
# crp/delegation/envelope.py (preview) — sign and propagate governance on delegation
def delegate(sub_task, target_agent, parent_ctx) -> dict:
    envelope = {
        "policy": parent_ctx.policy_envelope,              # inherited constraints (SPEC-006)
        "identity": parent_ctx.identity,                    # who is ultimately responsible
        "scope": intersect(parent_ctx.scope, sub_task.scope),  # sub-agent scope <= parent scope
        "budget": parent_ctx.remaining_budget(),            # shared safety budget
        "require": {"vr_verdict": True, "faithful_narration": True},  # trust bar for the result
        "audit_parent": parent_ctx.audit.current_hash,      # link B's chain into A's
    }
    signed = hmac_sign(envelope, parent_ctx.key)            # tamper-evident (SPEC-011)
    result = a2a_call(target_agent, sub_task, headers={"X-CRP-Delegation": signed})
    verify_delegation_result(result, envelope["require"])   # reject if trust bar unmet
    return result
```

This single spec would make CRP the first protocol to carry *governance* — not just messages — across the multi-agent boundary, extending every guarantee in this document from one agent to a society of them. It is the clearest open lead in the field and the natural culmination of the program.

## 11.5 The next report in the series

If the series continues, the highest-value fourth theme is **multi-agent governance** — how CRP's single-agent guarantees (verification, prediction, faithful transparency, provenance) compose across delegation boundaries into a *governed multi-agent system*. It is the natural sequel to Understanding, Tool Use, and Transparency: those three govern one agent's mind, hands, and face; the fourth would govern a *society* of agents. It is where the field is heading, where the protocols are weakest, and where CRP's governance-first identity has the clearest edge.

\newpage

# References

*APA 7th edition. This program cites fast-moving software and preprints alongside established work; where an entry describes a living library or a recent preprint, verify the current version, identifier, and URL before formal citation. CRP-SPEC references denote AutoCyber AI internal specifications available at crprotocol.io.*

Bryan, P. C., & Nottingham, M. (2013). *JavaScript Object Notation (JSON) Patch* (RFC 6902). Internet Engineering Task Force. https://doi.org/10.17487/RFC6902

Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., … Schulman, J. (2021). *Training verifiers to solve math word problems* (arXiv:2110.14168). arXiv. https://doi.org/10.48550/arXiv.2110.14168

CopilotKit. (2025). *AG-UI: The Agent-User Interaction Protocol* [Specification]. https://docs.ag-ui.com

Dong, Y., Ruan, C. F., Cai, Y., Xu, Z., Zhao, Y., Lai, R., & Chen, T. (2025). XGrammar: Flexible and efficient structured generation engine for large language models. *Proceedings of Machine Learning and Systems, 7*. (arXiv:2411.15065)

Farquhar, S., Kossen, J., Kuhn, L., & Gal, Y. (2024). Detecting hallucinations in large language models using semantic entropy. *Nature, 630*(8017), 625–630. https://doi.org/10.1038/s41586-024-07421-0

Kambhampati, S., Valmeekam, K., Guan, L., Stechly, K., Verma, M., Bhambri, S., … Murthy, A. (2024). LLMs can't plan, but can help planning in LLM-Modulo frameworks. In *Proceedings of the 41st International Conference on Machine Learning (ICML 2024)*. (arXiv:2402.01817)

Lightman, H., Kosaraju, V., Burda, Y., Edwards, H., Baker, B., Lee, T., … Cobbe, K. (2023). *Let's verify step by step* (arXiv:2305.20050). arXiv. https://doi.org/10.48550/arXiv.2305.20050

MLC Community. (2026). *XGrammar-2: Efficient dynamic structured generation engine for agentic LLMs* (arXiv:2601.04426). arXiv.

Ong, I., Almahairi, A., Wu, V., Zhang, H., Lin, Z., Chiang, W.-L., … Stoica, I. (2024). *RouteLLM: Learning to route LLMs with preference data* (arXiv:2406.18665). arXiv.

Willard, B. T., & Louf, R. (2023). *Efficient guided generation for large language models* (arXiv:2307.09702). arXiv. (Outlines.)

Zep / Graphiti. (2025). *Graphiti: Temporal knowledge graphs for agent memory* [Computer software]. https://github.com/getzep/graphiti

Zhou, S., et al. (2024). *WALL-E: World alignment by rule learning improves world-model-based LLM agents* (arXiv:2410.07484). arXiv.

*Companion volumes (this series):* Vidiniotis, C. (2026). *The Architecture of Understanding in Agentic AI Systems*; *The Architecture of Tool Use in Agentic AI Systems*; *The Architecture of Transparency in Agentic AI Systems*. AutoCyber AI.

*CRP specifications referenced:* CRP-SPEC-001 (Core), -002 (Headers), -003 (Envelope), -004 (Continuation), -005 (DPE), -006 (SPDL), -008 (Dispatch), -009 (CKF), -011 (Audit/HMAC), -016 (Gateway), -021 (ROS), -026 (SQB), -027 (Retrieval Integrity), -028 (Multi-Horizon Context), -029 (Tier-E Action Log), -030 (CSO), -031 (STL), -033 (Safety Control Plane), -044 (Authoritative Domain Agent), -045 (Session/Persistent Learning). AutoCyber AI. https://crprotocol.io

*End of specification.*
