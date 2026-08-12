# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Policy enforcement engine (CRP-SPEC-006 §3-4).

:func:`enforce_policy` evaluates a parsed :class:`SafetyPolicy` against the DPE
analysis signals and returns a :class:`PolicyDecision`.  Directive interactions
follow *most-restrictive-wins* (CRP-SPEC-006 §4.1): the decision's final action
is the most severe action recommended by any violated directive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import (
    EnforcementAction,
    OversightMode,
    PolicyDecision,
    RepetitionLevel,
    RiskLevel,
    SafetyPolicy,
    Violation,
    ViolationType,
)

# Per-claim source-trust mapping: which default-src token authorises which
# DPE attribution type.
_ATTRIBUTION_SOURCE = {
    "CONTEXT_GROUNDED": "context",
    "PARAMETRIC": "parametric",
    "MIXED": "context",  # mixed claims require context trust at minimum
    "UNCERTAIN": None,    # never trusted by any source token
}


@dataclass
class SafetySignals:
    """Normalised DPE signals consumed by the enforcer."""

    risk_level: RiskLevel | None = None
    hallucination_score: float | None = None
    grounding_pct: float | None = None
    entailment_score: float | None = None
    quality_tier: str | None = None
    flow: float | None = None
    completeness: float | None = None
    repetition: RepetitionLevel | None = None
    fabrication_count: int = 0
    pii_detected: bool = False
    ungrounded_count: int = 0
    parametric_count: int = 0
    mixed_count: int = 0
    sources_used: set[str] = field(default_factory=set)


def _coerce_risk(value: Any) -> RiskLevel | None:
    if value is None:
        return None
    raw = str(getattr(value, "value", value)).upper()
    try:
        return RiskLevel(raw)
    except ValueError:
        return None


def _coerce_repetition(value: Any) -> RepetitionLevel | None:
    if value is None:
        return None
    raw = str(getattr(value, "value", value)).upper()
    try:
        return RepetitionLevel(raw)
    except ValueError:
        return None


def extract_signals(
    *,
    provenance: Any = None,
    quality: Any = None,
    compliance: Any = None,
    rqa: Any = None,
) -> SafetySignals:
    """Build :class:`SafetySignals` from engine outputs (all duck-typed/optional)."""
    sig = SafetySignals()

    if provenance is not None:
        risk_report = getattr(provenance, "risk_report", None)
        if risk_report is not None:
            sig.risk_level = _coerce_risk(getattr(risk_report, "window_risk_level", None))
            sig.hallucination_score = getattr(risk_report, "mean_risk_score", None)
        sig.grounding_pct = getattr(provenance, "grounding_ratio", None)

        fidelity = getattr(provenance, "fidelity", None)
        if fidelity is not None:
            sig.fabrication_count = getattr(fidelity, "fabrication_count", 0) or 0

        ent = getattr(provenance, "entailment_results", None)
        if ent:
            scores = [getattr(e, "entailment_score", 0.0) for e in ent]
            if scores:
                sig.entailment_score = sum(scores) / len(scores)

        # Attribution mix → ungrounded / parametric counts + sources used.
        cg = getattr(provenance, "context_grounded_count", 0) or 0
        par = getattr(provenance, "parametric_count", 0) or 0
        mixed = getattr(provenance, "mixed_count", 0) or 0
        uncertain = getattr(provenance, "uncertain_count", 0) or 0
        sig.parametric_count = par
        sig.mixed_count = mixed
        # PARAMETRIC and UNCERTAIN claims are fully ungrounded. MIXED claims are
        # partially grounded and are handled separately (block-mixed directive)
        # so that block-ungrounded does not over-reach against partial matches.
        sig.ungrounded_count = par + uncertain
        if cg:
            sig.sources_used.add("context")
        if mixed:
            sig.sources_used.add("context")
        if par:
            sig.sources_used.add("parametric")
        if uncertain:
            sig.sources_used.add("uncertain")

    if quality is not None:
        sig.quality_tier = str(getattr(quality, "quality_tier", "") or "") or None

    if compliance is not None:
        pii = getattr(compliance, "processes_personal_data", None)
        if pii is None and isinstance(compliance, dict):
            pii = compliance.get("processes_personal_data")
        sig.pii_detected = bool(pii)

    if rqa is not None:
        get = (lambda k: rqa.get(k)) if isinstance(rqa, dict) else (lambda k: getattr(rqa, k, None))
        if sig.flow is None:
            sig.flow = get("flow")
        if sig.completeness is None:
            sig.completeness = get("completeness")
        sig.repetition = _coerce_repetition(get("repetition"))

    return sig


def enforce_policy(policy: SafetyPolicy, signals: SafetySignals) -> PolicyDecision:
    """Evaluate *policy* against *signals* → a :class:`PolicyDecision`."""
    decision = PolicyDecision(report_only=policy.report_only)
    violations: list[Violation] = decision.violations

    def add(directive: str, vtype: ViolationType, action: EnforcementAction, detail: str = "", status: int | None = None) -> None:
        """Execute add and return the result.
        
            Args:
                directive (str): The directive value.
                vtype (ViolationType): The vtype value.
                action (EnforcementAction): The action value.
                detail (str): The detail value.
                status (int | None): The status value.
        
            Returns:
                ``None``.
        """
        violations.append(Violation(directive, vtype, action, detail, status))

    # ── default-src (source trust) ───────────────────────────────────────
    if policy.default_src:
        if "'none'" in policy.default_src:
            add("default-src 'none'", ViolationType.SOURCE_NOT_TRUSTED,
                EnforcementAction.HALT, "all sources blocked", 451)
        else:
            for src in signals.sources_used:
                if src == "uncertain" or src not in policy.default_src:
                    add(f"default-src {' '.join(policy.default_src)}",
                        ViolationType.SOURCE_NOT_TRUSTED, EnforcementAction.HALT,
                        f"untrusted source: {src}", 451)
                    break

    # ── halt-on / warn-on (risk levels) ──────────────────────────────────
    if signals.risk_level is not None:
        if policy.halt_on is not None and signals.risk_level.rank >= policy.halt_on.rank:
            add(f"halt-on {policy.halt_on.value}", ViolationType.HALT_ON_RISK,
                EnforcementAction.HALT, f"risk {signals.risk_level.value}", 451)
        elif policy.warn_on is not None and signals.risk_level.rank >= policy.warn_on.rank:
            add(f"warn-on {policy.warn_on.value}", ViolationType.WARN_ON_RISK,
                EnforcementAction.WARN, f"risk {signals.risk_level.value}")

    # ── require-grounding / require-entailment ───────────────────────────
    redispatch_or_halt = EnforcementAction.REDISPATCH if policy.upgrade_on_risk else EnforcementAction.HALT
    if policy.require_grounding is not None and signals.grounding_pct is not None:
        if signals.grounding_pct < policy.require_grounding:
            add(f"require-grounding {policy.require_grounding:.2f}",
                ViolationType.GROUNDING_BELOW_THRESHOLD, redispatch_or_halt,
                f"grounding {signals.grounding_pct:.2f}", None if policy.upgrade_on_risk else 451)
            decision.recommended_grounding_mode = "context-strict"

    if policy.require_entailment is not None and signals.entailment_score is not None:
        if signals.entailment_score < policy.require_entailment:
            add(f"require-entailment {policy.require_entailment:.2f}",
                ViolationType.ENTAILMENT_BELOW_THRESHOLD, redispatch_or_halt,
                f"entailment {signals.entailment_score:.2f}", None if policy.upgrade_on_risk else 451)
            decision.recommended_grounding_mode = "context-strict"

    # ── require-quality ──────────────────────────────────────────────────
    if policy.require_quality and signals.quality_tier is not None:
        if signals.quality_tier not in policy.require_quality:
            add(f"require-quality {' '.join(policy.require_quality)}",
                ViolationType.QUALITY_TIER_REJECTED, EnforcementAction.HALT,
                f"tier {signals.quality_tier}", 503)

    # ── require-flow → re-dispatch with flow augmentation ────────────────
    if policy.require_flow is not None and signals.flow is not None:
        if signals.flow < policy.require_flow:
            add(f"require-flow {policy.require_flow:.2f}",
                ViolationType.FLOW_BELOW_THRESHOLD, EnforcementAction.REDISPATCH,
                f"flow {signals.flow:.2f}")

    # ── require-completeness → auto-continuation window ──────────────────
    if policy.require_completeness is not None and signals.completeness is not None:
        if signals.completeness < policy.require_completeness:
            add(f"require-completeness {policy.require_completeness:.2f}",
                ViolationType.COMPLETENESS_BELOW_THRESHOLD, EnforcementAction.CONTINUE,
                f"completeness {signals.completeness:.2f}")

    # ── block-* directives ───────────────────────────────────────────────
    if policy.block_ungrounded and signals.ungrounded_count > 0:
        add("block-ungrounded", ViolationType.UNGROUNDED_CLAIM, EnforcementAction.HALT,
            f"{signals.ungrounded_count} ungrounded claims", 451)
    if policy.block_mixed and signals.mixed_count > 0:
        add("block-mixed", ViolationType.MIXED_CONTENT, EnforcementAction.HALT,
            f"{signals.mixed_count} mixed claims", 451)
    if policy.block_parametric and signals.parametric_count > 0:
        add("block-parametric", ViolationType.PARAMETRIC_CONTENT, EnforcementAction.HALT,
            f"{signals.parametric_count} parametric claims", 451)
    if policy.block_pii and signals.pii_detected:
        add("block-pii", ViolationType.PII_DETECTED, EnforcementAction.HALT, "PII detected", 451)
    if policy.block_fabrication and signals.fabrication_count > 0:
        add("block-fabrication", ViolationType.FABRICATION_DETECTED, EnforcementAction.HALT,
            f"{signals.fabrication_count} fabrications", 451)
    if policy.block_repetition and signals.repetition == RepetitionLevel.SEVERE:
        add("block-repetition", ViolationType.REPETITION_EXCEEDED, EnforcementAction.REDISPATCH,
            "SEVERE repetition")

    # ── max-repetition ───────────────────────────────────────────────────
    if policy.max_repetition is not None and signals.repetition is not None:
        if signals.repetition.rank > policy.max_repetition.rank:
            add(f"max-repetition {policy.max_repetition.value}",
                ViolationType.REPETITION_EXCEEDED, EnforcementAction.REDISPATCH,
                f"repetition {signals.repetition.value}")

    # ── Resolve final action (most-restrictive-wins) ─────────────────────
    if violations:
        worst = max(violations, key=lambda v: v.action.severity)
        decision.action = worst.action
        # HTTP status from the most-severe halting violation.
        halting = [v for v in violations if v.action == EnforcementAction.HALT and v.http_status]
        if halting:
            decision.http_status = max(v.http_status for v in halting if v.http_status)
            decision.retry_after = "oversight-required"

    if policy.upgrade_on_risk and decision.action in (
        EnforcementAction.REDISPATCH, EnforcementAction.WARN
    ):
        decision.recommended_strategy = policy.upgrade_on_risk.value

    # Oversight HALT mode forces a halt regardless.
    if policy.oversight == OversightMode.HALT and decision.action == EnforcementAction.WARN:
        decision.action = EnforcementAction.HALT
        decision.http_status = decision.http_status or 451
        decision.retry_after = "oversight-required"

    return decision
