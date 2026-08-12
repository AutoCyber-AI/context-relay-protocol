# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Violation report payloads + delivery (CRP-SPEC-006 §3.16).

Builds the JSON violation-report payload and POSTs it to a policy's
``report-uri`` when configured.  Delivery is best-effort and dependency-light:
the standard-library ``urllib`` is used so the core package gains no new deps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enforce import SafetySignals
from .model import PolicyDecision, SafetyPolicy

CRP_VERSION = "3.0.0"


@dataclass
class ViolationReport:
    """A CRP-SPEC-006 §3.16 violation-report payload."""

    crp_version: str = CRP_VERSION
    session_id: str | None = None
    window_id: str | None = None
    timestamp: str = ""
    violation_type: str = ""
    directive_violated: str = ""
    risk_level: str | None = None
    hallucination_score: float | None = None
    grounding_pct: float | None = None
    fabrication_count: int = 0
    audit_trail_uri: str | None = None
    violations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the violation report as a plain dict.

        Returns:
            Dict with all non-None report fields.
        """
        d = {
            "crp_version": self.crp_version,
            "session_id": self.session_id,
            "window_id": self.window_id,
            "timestamp": self.timestamp,
            "violation_type": self.violation_type,
            "directive_violated": self.directive_violated,
            "risk_level": self.risk_level,
            "hallucination_score": self.hallucination_score,
            "grounding_pct": self.grounding_pct,
            "fabrication_count": self.fabrication_count,
            "audit_trail_uri": self.audit_trail_uri,
            "violations": self.violations,
        }
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        """Serialize the report to a JSON string.

        Returns:
            JSON-encoded violation report.
        """
        return json.dumps(self.to_dict())


def build_report(
    decision: PolicyDecision,
    signals: SafetySignals,
    *,
    session_id: str | None = None,
    window_id: str | None = None,
    audit_trail_uri: str | None = None,
) -> ViolationReport:
    """Construct a :class:`ViolationReport` from an enforcement decision."""
    primary = max(decision.violations, key=lambda v: v.action.severity) if decision.violations else None
    return ViolationReport(
        session_id=session_id,
        window_id=window_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        violation_type=primary.violation_type.value if primary else "",
        directive_violated=primary.directive if primary else "",
        risk_level=signals.risk_level.value if signals.risk_level else None,
        hallucination_score=signals.hallucination_score,
        grounding_pct=signals.grounding_pct,
        fabrication_count=signals.fabrication_count,
        audit_trail_uri=audit_trail_uri,
        violations=[
            {
                "directive": v.directive,
                "type": v.violation_type.value,
                "action": v.action.value,
                "detail": v.detail,
            }
            for v in decision.violations
        ],
    )


def deliver_report(policy: SafetyPolicy, report: ViolationReport, *, timeout: float = 5.0) -> bool:
    """Best-effort POST of *report* to ``policy.report_uri``.

    Returns ``True`` on a 2xx response, ``False`` otherwise (never raises).
    Does nothing (returns ``False``) when no ``report-uri`` is configured.
    """
    if not policy.report_uri:
        return False
    try:
        import urllib.request

        data = report.to_json().encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 - report-uri validated by gateway (§7.2)
            policy.report_uri,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except Exception:
        return False
