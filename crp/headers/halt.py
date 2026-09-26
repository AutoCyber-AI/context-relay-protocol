# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""HTTP 451 safety-halt response builder (SPEC-002 §13.2).

When the gateway refuses to relay a generation for legal/safety reasons it
returns HTTP 451 *Unavailable For Legal Reasons* with a structured JSON body
and a fixed set of CRP response headers.  :func:`build_halt_response` produces
both so any transport can serialise them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import names as H


class HaltReason(str, Enum):
    """Canonical ``crp_halt_reason`` values (SPEC-002 §13.2).

    The three original values are a stable wire contract; the additional
    values added in 6.1.2 let callers report the *dominant* violation instead
    of always claiming an umbrella prohibition.
    """

    CRITICAL_HALLUCINATION_RISK = "CRITICAL_HALLUCINATION_RISK"
    UNACCEPTABLE_EU_AI_ACT = "UNACCEPTABLE_EU_AI_ACT"
    SAFETY_BUDGET_DEPLETED = "SAFETY_BUDGET_DEPLETED"
    GROUNDING_BELOW_THRESHOLD = "GROUNDING_BELOW_THRESHOLD"
    QUALITY_TIER_REJECTED = "QUALITY_TIER_REJECTED"
    UNTRUSTED_SOURCE = "UNTRUSTED_SOURCE"
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    SAFETY_POLICY_VIOLATION = "SAFETY_POLICY_VIOLATION"


#: Human-readable rendering for each halt reason: ``(short title, explanation)``.
#: Used for the ``crp_halt_explanation`` body field and for UIs that want to
#: show operators a plain-English sentence instead of the raw enum value.
HALT_REASON_INFO: dict[HaltReason, tuple[str, str]] = {
    HaltReason.CRITICAL_HALLUCINATION_RISK: (
        "Critical hallucination risk",
        "CRP halted the response because its analysis indicates a critical "
        "risk that the model invented or distorted facts.",
    ),
    HaltReason.UNACCEPTABLE_EU_AI_ACT: (
        "Prohibited under the EU AI Act",
        "CRP halted the response because the request falls under a practice "
        "the EU AI Act prohibits, which cannot be served in any form.",
    ),
    HaltReason.SAFETY_BUDGET_DEPLETED: (
        "Safety budget depleted",
        "CRP halted the session because its multi-agent safety budget was "
        "consumed by repeated high-risk activity.",
    ),
    HaltReason.GROUNDING_BELOW_THRESHOLD: (
        "Answer not grounded in allowed sources",
        "CRP halted the response because too few of its claims trace back to "
        "your provided context, below the grounding threshold in your policy.",
    ),
    HaltReason.QUALITY_TIER_REJECTED: (
        "Answer below required quality tier",
        "CRP halted the response because its overall quality tier is lower "
        "than the minimum your policy accepts.",
    ),
    HaltReason.UNTRUSTED_SOURCE: (
        "Untrusted source used",
        "CRP halted the response because it relied on a source your policy "
        "does not trust.",
    ),
    HaltReason.PROMPT_INJECTION_DETECTED: (
        "Prompt injection detected",
        "CRP halted the response because its input shield detected an "
        "attempt to override the system's instructions.",
    ),
    HaltReason.SAFETY_POLICY_VIOLATION: (
        "Safety policy violated",
        "CRP halted the response because it violated one or more directives "
        "in your safety policy.",
    ),
}


def halt_reason_info(reason: HaltReason | str) -> tuple[str, str]:
    """Return ``(short title, explanation)`` for a halt reason.

    Unknown / free-text reasons fall back to a generic entry so the wire
    value is never rendered bare.
    """
    try:
        key = reason if isinstance(reason, HaltReason) else HaltReason(str(reason))
    except ValueError:
        return ("Safety policy violated",
                "CRP halted the response because it violated your safety policy.")
    return HALT_REASON_INFO[key]


@dataclass
class HaltResponse:
    """A fully-formed HTTP 451 safety halt (body + headers)."""

    http_status: int
    body: dict[str, object]
    headers: dict[str, str] = field(default_factory=dict)


def build_halt_response(
    *,
    reason: HaltReason | str,
    session_id: str,
    audit_trail_uri: str,
    oversight_required: bool = False,
    retry_condition: str | None = None,
    hallucination_risk: str | None = None,
    retry_after: int | str | None = None,
) -> HaltResponse:
    """Build the HTTP 451 safety-halt response (SPEC-002 §13.2).

    Args:
        reason: a :class:`HaltReason` (or its string value).
        session_id: the halted session id.
        audit_trail_uri: dereferenceable URI to the audit trail for this halt.
        oversight_required: whether human oversight must approve a retry.
        retry_condition: ``"oversight-required"`` or an ISO-8601 timestamp.  If
            omitted it defaults to ``"oversight-required"`` when
            *oversight_required* is set, else ``None``.
        hallucination_risk: optional risk tier for the
            ``CRP-Safety-Hallucination-Risk`` header (e.g. ``"CRITICAL"``).
        retry_after: optional ``CRP-Safety-Retry-After`` value (seconds or token).

    Returns:
        :class:`HaltResponse` with ``http_status=451``. The body always
        carries ``crp_halt_reason`` (wire contract, unchanged) plus the
        optional ``crp_halt_explanation`` plain-English sentence derived
        from the reason.
    """
    reason_value = reason.value if isinstance(reason, HaltReason) else str(reason)

    if retry_condition is None and oversight_required:
        retry_condition = "oversight-required"

    body: dict[str, object] = {
        "crp_halt_reason": reason_value,
        "crp_halt_explanation": halt_reason_info(reason_value)[1],
        "session_id": session_id,
        "audit_trail_uri": audit_trail_uri,
        "oversight_required": bool(oversight_required),
        "retry_condition": retry_condition,
    }

    headers: dict[str, str] = {H.COMPLIANCE_AUDIT_TRAIL_URI: audit_trail_uri}
    if hallucination_risk is not None:
        headers[H.SAFETY_HALLUCINATION_RISK] = str(hallucination_risk)
    if retry_after is not None:
        headers[H.SAFETY_RETRY_AFTER] = str(retry_after)

    return HaltResponse(http_status=451, body=body, headers=headers)
