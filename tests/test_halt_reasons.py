# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the HTTP 451 halt-reason surface (SPEC-002 §13.2, v6.1.2).

Covers the human-readable layer added in 6.1.2: the extended ``HaltReason``
enum (original values unchanged — stable wire contract), the
``HALT_REASON_INFO`` mapping, and the ``crp_halt_explanation`` body field.
"""

from __future__ import annotations

from crp.headers.halt import (
    HALT_REASON_INFO,
    HaltReason,
    HaltResponse,
    build_halt_response,
    halt_reason_info,
)

# ── Enum stability (wire contract) ──────────────────────────────────────────


def test_original_reason_values_unchanged() -> None:
    assert HaltReason.CRITICAL_HALLUCINATION_RISK.value == "CRITICAL_HALLUCINATION_RISK"
    assert HaltReason.UNACCEPTABLE_EU_AI_ACT.value == "UNACCEPTABLE_EU_AI_ACT"
    assert HaltReason.SAFETY_BUDGET_DEPLETED.value == "SAFETY_BUDGET_DEPLETED"


def test_new_reason_values() -> None:
    assert HaltReason.GROUNDING_BELOW_THRESHOLD.value == "GROUNDING_BELOW_THRESHOLD"
    assert HaltReason.QUALITY_TIER_REJECTED.value == "QUALITY_TIER_REJECTED"
    assert HaltReason.UNTRUSTED_SOURCE.value == "UNTRUSTED_SOURCE"
    assert HaltReason.PROMPT_INJECTION_DETECTED.value == "PROMPT_INJECTION_DETECTED"
    assert HaltReason.SAFETY_POLICY_VIOLATION.value == "SAFETY_POLICY_VIOLATION"


# ── HALT_REASON_INFO mapping ────────────────────────────────────────────────


def test_every_reason_has_human_readable_entry() -> None:
    for reason in HaltReason:
        title, explanation = HALT_REASON_INFO[reason]
        assert title
        assert explanation
        assert reason.value not in title  # title is plain English, not the enum


def test_halt_reason_info_accepts_strings() -> None:
    title, explanation = halt_reason_info("GROUNDING_BELOW_THRESHOLD")
    assert title == HALT_REASON_INFO[HaltReason.GROUNDING_BELOW_THRESHOLD][0]
    assert explanation == HALT_REASON_INFO[HaltReason.GROUNDING_BELOW_THRESHOLD][1]


def test_halt_reason_info_unknown_string_falls_back() -> None:
    title, explanation = halt_reason_info("SOME_FUTURE_REASON")
    assert title
    assert explanation


# ── build_halt_response body ────────────────────────────────────────────────


def _build(reason: HaltReason | str) -> HaltResponse:
    return build_halt_response(
        reason=reason, session_id="s1", audit_trail_uri="/audit/s1",
    )


def test_body_carries_reason_and_explanation() -> None:
    resp = _build(HaltReason.GROUNDING_BELOW_THRESHOLD)
    assert resp.http_status == 451
    assert resp.body["crp_halt_reason"] == "GROUNDING_BELOW_THRESHOLD"
    assert resp.body["crp_halt_explanation"] == (
        HALT_REASON_INFO[HaltReason.GROUNDING_BELOW_THRESHOLD][1]
    )
    # Existing wire keys are untouched.
    assert resp.body["session_id"] == "s1"
    assert resp.body["audit_trail_uri"] == "/audit/s1"
    assert resp.body["oversight_required"] is False
    assert resp.body["retry_condition"] is None


def test_explanation_for_each_canonical_reason() -> None:
    for reason in HaltReason:
        resp = _build(reason)
        assert resp.body["crp_halt_explanation"] == HALT_REASON_INFO[reason][1]


def test_explanation_for_string_reason_and_default_retry_condition() -> None:
    resp = build_halt_response(
        reason="UNTRUSTED_SOURCE", session_id="s1", audit_trail_uri="/a",
        oversight_required=True,
    )
    assert resp.body["crp_halt_reason"] == "UNTRUSTED_SOURCE"
    assert resp.body["crp_halt_explanation"] == (
        HALT_REASON_INFO[HaltReason.UNTRUSTED_SOURCE][1]
    )
    assert resp.body["retry_condition"] == "oversight-required"


def test_headers_unchanged() -> None:
    resp = build_halt_response(
        reason=HaltReason.CRITICAL_HALLUCINATION_RISK, session_id="s1",
        audit_trail_uri="/audit/s1", hallucination_risk="CRITICAL", retry_after=30,
    )
    assert resp.headers["CRP-Compliance-Audit-Trail-URI"] == "/audit/s1"
    assert resp.headers["CRP-Safety-Hallucination-Risk"] == "CRITICAL"
    assert resp.headers["CRP-Safety-Retry-After"] == "30"
