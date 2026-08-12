# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Header emission (CRP-SPEC-002).

:func:`emit_headers` maps the engine's existing analysis outputs — the DPE
``ProvenanceReport``, the ``QualityReport``, the compliance ``RiskAssessment``,
session/window state — onto the canonical ``CRP-*`` response header surface.

The emitter is intentionally *duck-typed and defensive*: every input is
optional and accessed via :func:`getattr`, so it never hard-couples to a
specific engine version and never raises on a missing field.  Callers wire in
whatever they have; the emitter emits whatever it can.
"""

from __future__ import annotations

from typing import Any

from . import names as H


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _enum_str(value: Any) -> str | None:
    """Render an enum / string risk-or-tier value to its wire form."""
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _pct(value: float | None, places: int = 2) -> str | None:
    if value is None:
        return None
    return f"{float(value):.{places}f}"


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_headers(
    *,
    provenance: Any = None,
    quality: Any = None,
    compliance: Any = None,
    session_id: str | None = None,
    window: int | None = None,
    strategy: str | None = None,
    protocol_version: str | None = None,
    etag: str | None = None,
    cache_status: str | None = None,
    window_hmac: str | None = None,
    chain_integrity: str | None = None,
    report_uri: str | None = None,
    audit_trail_id: str | None = None,
    audit_trail_uri: str | None = None,
    data_residency: str | None = None,
    safety_budget: float | None = None,
    oversight_mode: str | None = None,
    rqa: Any = None,
    policy_applied: str | None = None,
    mode: str | None = None,
    mode_transition: str | None = None,
    coverage: float | None = None,
    continuation_id: str | None = None,
    dag_root: str | None = None,
    window_lineage: str | None = None,
    set_session: str | None = None,
    activation_status: str | None = None,
    activation_features: str | None = None,
    onboarding: Any = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the ``CRP-*`` response header set from available analysis outputs.

    Args:
        provenance: A DPE ``ProvenanceReport`` (or any object exposing the same
            attributes — ``risk_report``, ``grounding_ratio``, ``fidelity`` …).
        quality: A ``QualityReport`` (``quality_tier``, ``envelope_saturation`` …).
        compliance: A compliance ``RiskAssessment`` (``risk_level`` …) or mapping.
        session_id / window / strategy / protocol_version: session/dispatch state.
        etag / cache_status: conditional-dispatch state (CRP-SPEC-002 §4.8).
        window_hmac / chain_integrity: provenance chain (CRP-SPEC-011).
        report_uri / audit_trail_* / data_residency: compliance linkage.
        safety_budget / oversight_mode: multi-agent + oversight surface.
        rqa: mapping/object with ``repetition`` / ``completeness`` / ``flow`` /
            ``score`` (CRP-SPEC-005 §18).
        policy_applied: effective policy string after inheritance resolution.
        extra: any additional pre-formatted ``{header: value}`` pairs.

    Returns:
        ``dict[str, str]`` of canonical CRP header names → string values.  Only
        headers with derivable values are included.
    """
    out: dict[str, str] = {}

    def put(name: str, value: str | None) -> None:
        """Execute put and return the result.
        
            Args:
                name (str): The name value.
                value (str | None): The value value.
        
            Returns:
                ``None``.
        """
        if value is not None and value != "":
            out[name] = value

    # ── Context / session state ──────────────────────────────────────────
    put(H.CONTEXT_PROTOCOL_VERSION, protocol_version)
    put(H.CONTEXT_SESSION_ID, session_id)
    if window is not None:
        put(H.CONTEXT_WINDOW, str(window))
    put(H.CONTEXT_STRATEGY, strategy)
    put(H.CONTEXT_ETAG, etag)
    put(H.CONTEXT_CACHE_STATUS, cache_status)
    put(H.CONTEXT_MODE, mode)
    put(H.CONTEXT_MODE_TRANSITION, mode_transition)
    if coverage is not None:
        put(H.CONTEXT_COVERAGE, _pct(coverage))
    put(H.CONTEXT_CONTINUATION_ID, continuation_id)

    if quality is not None:
        put(H.CONTEXT_QUALITY_TIER, _enum_str(getattr(quality, "quality_tier", None)))
        sat = getattr(quality, "envelope_saturation", None)
        put(H.CONTEXT_SATURATION, _pct(sat))
        facts = getattr(quality, "facts_extracted", None)
        if facts is not None:
            put(H.CONTEXT_FACTS_USED, str(facts))

    # ── DPE safety surface ───────────────────────────────────────────────
    if provenance is not None:
        _emit_provenance(provenance, put)

    # ── Provenance chain ─────────────────────────────────────────────────
    put(H.PROVENANCE_WINDOW_HMAC, window_hmac)
    put(H.PROVENANCE_CHAIN_INTEGRITY, chain_integrity)
    put(H.PROVENANCE_REPORT_URI, report_uri)
    put(H.PROVENANCE_DAG_ROOT, dag_root)
    put(H.PROVENANCE_WINDOW_LINEAGE, window_lineage)

    # ── Compliance ───────────────────────────────────────────────────────
    if compliance is not None:
        _emit_compliance(compliance, put)
    put(H.COMPLIANCE_AUDIT_TRAIL_ID, audit_trail_id)
    put(H.COMPLIANCE_AUDIT_TRAIL_URI, audit_trail_uri)
    put(H.COMPLIANCE_DATA_RESIDENCY, data_residency)

    # ── RQA quality surface (NEW v3.0) ───────────────────────────────────
    if rqa is not None:
        put(H.QUALITY_REPETITION, _enum_str(_get(rqa, "repetition")))
        put(H.QUALITY_COMPLETENESS, _pct(_get(rqa, "completeness")))
        put(H.QUALITY_FLOW, _pct(_get(rqa, "flow")))
        put(H.QUALITY_SCORE, _pct(_get(rqa, "score")))

    # ── Multi-agent / oversight ──────────────────────────────────────────
    if safety_budget is not None:
        put(H.AGENT_SAFETY_BUDGET, _pct(safety_budget))
    put(H.SAFETY_OVERSIGHT_MODE, oversight_mode)
    put(H.SAFETY_POLICY_APPLIED, policy_applied)

    # ── Session token relay (SPEC-007) ───────────────────────────────────
    put(H.SET_SESSION, set_session)

    # ── Progressive activation / onboarding (SPEC-017) ───────────────────
    put(H.ACTIVATION_STATUS, activation_status)
    put(H.ACTIVATION_FEATURES, activation_features)
    if onboarding is not None:
        active = _get(onboarding, "active")
        if active is not None:
            put(H.ONBOARDING_ACTIVE, _bool(active))
        days = _get(onboarding, "days_remaining")
        if days is not None:
            put(H.ONBOARDING_DAYS_REMAINING, str(days))
        put(H.ONBOARDING_NEXT_ACTION, _get(onboarding, "next_action"))
        put(H.ONBOARDING_HINT, _get(onboarding, "hint"))

    if extra:
        out.update(extra)

    return out


def _get(obj: Any, key: str) -> Any:
    """Fetch *key* from a mapping or attribute, returning ``None`` if absent."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _emit_provenance(provenance: Any, put: Any) -> None:
    """Map a DPE ProvenanceReport onto CRP-Safety-* / CRP-Provenance-* headers."""
    # Claim counts
    total = getattr(provenance, "total_claims", None)
    if total is not None:
        put(H.PROVENANCE_CLAIM_COUNT, str(total))

    # Grounding
    grounding = getattr(provenance, "grounding_ratio", None)
    put(H.SAFETY_GROUNDING_PCT, _pct(grounding))
    put(H.PROVENANCE_ATTRIBUTION_SCORE, _pct(grounding))

    # Attribution mix → dominant attribution label
    cg = getattr(provenance, "context_grounded_count", 0) or 0
    par = getattr(provenance, "parametric_count", 0) or 0
    mixed = getattr(provenance, "mixed_count", 0) or 0
    if (cg + par + mixed) > 0:
        if cg >= par and cg >= mixed:
            put(H.SAFETY_ATTRIBUTION, "CONTEXT_GROUNDED")
        elif par >= mixed:
            put(H.SAFETY_ATTRIBUTION, "PARAMETRIC")
        else:
            put(H.SAFETY_ATTRIBUTION, "MIXED")

    # Hallucination risk
    risk_report = getattr(provenance, "risk_report", None)
    if risk_report is not None:
        put(H.SAFETY_HALLUCINATION_RISK, _enum_str(getattr(risk_report, "window_risk_level", None)))
        put(H.SAFETY_HALLUCINATION_SCORE, _pct(getattr(risk_report, "mean_risk_score", None)))

    # Fidelity
    fidelity = getattr(provenance, "fidelity", None)
    if fidelity is not None:
        put(H.PROVENANCE_FIDELITY_SCORE, _pct(getattr(fidelity, "fidelity_score", None)))
        fab = getattr(fidelity, "fabrication_count", None)
        if fab is not None:
            put(H.SAFETY_FABRICATIONS, str(fab))
        dis = getattr(fidelity, "distortion_count", None)
        if dis is not None:
            put(H.SAFETY_DISTORTIONS, str(dis))
        con = getattr(fidelity, "contradiction_count", None)
        if con is not None:
            put(H.SAFETY_CONTRADICTIONS, str(con))
        omi = getattr(fidelity, "critical_omission_count", None)
        if omi is not None:
            put(H.SAFETY_OMISSIONS, str(omi))

    # Entailment — strongest entailment over results (best available signal)
    ent_results = getattr(provenance, "entailment_results", None)
    if ent_results:
        scores = [getattr(e, "entailment_score", 0.0) for e in ent_results]
        if scores:
            put(H.SAFETY_ENTAILMENT_SCORE, _pct(sum(scores) / len(scores)))


def _emit_compliance(compliance: Any, put: Any) -> None:
    """Map a compliance RiskAssessment onto CRP-Compliance-* headers."""
    risk = _get(compliance, "risk_level")
    put(H.COMPLIANCE_EU_AI_ACT, _enum_str(risk))
    pii = _get(compliance, "processes_personal_data")
    if pii is not None:
        put(H.COMPLIANCE_GDPR_PII, _bool(pii))
    nist = _get(compliance, "nist_tier")
    put(H.COMPLIANCE_NIST_TIER, _enum_str(nist))
    iso = _get(compliance, "iso_42001")
    put(H.COMPLIANCE_ISO_42001, _enum_str(iso))
    controls = _get(compliance, "controls_met")
    if controls is not None:
        put(H.COMPLIANCE_CONTROLS_MET, str(controls))
