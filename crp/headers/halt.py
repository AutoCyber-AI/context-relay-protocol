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
    """Canonical ``crp_halt_reason`` values (SPEC-002 §13.2)."""

    CRITICAL_HALLUCINATION_RISK = "CRITICAL_HALLUCINATION_RISK"
    UNACCEPTABLE_EU_AI_ACT = "UNACCEPTABLE_EU_AI_ACT"
    SAFETY_BUDGET_DEPLETED = "SAFETY_BUDGET_DEPLETED"


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
        :class:`HaltResponse` with ``http_status=451``.
    """
    reason_value = reason.value if isinstance(reason, HaltReason) else str(reason)

    if retry_condition is None and oversight_required:
        retry_condition = "oversight-required"

    body: dict[str, object] = {
        "crp_halt_reason": reason_value,
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
