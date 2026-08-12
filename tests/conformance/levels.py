# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP conformance levels and mandatory header sets (CRP-SPEC-014 §1).

Three conformance levels are defined:

* ``CRP-Basic``    — 7 mandatory headers, minimum viable governance.
* ``CRP-Standard`` — production-grade; all applicable headers + RQA + policy.
* ``CRP-Full``     — complete protocol incl. multi-agent, DAG, OCSF export.
"""

from __future__ import annotations

import enum

from crp.headers import names as H


class ConformanceLevel(str, enum.Enum):
    BASIC = "basic"
    STANDARD = "standard"
    FULL = "full"


# CRP-SPEC-014 §1.1 — the 7 mandatory CRP-Basic response headers.
BASIC_MANDATORY_HEADERS: tuple[str, ...] = (
    H.CONTEXT_SESSION_ID,
    H.SET_SESSION,
    H.SAFETY_HALLUCINATION_RISK,
    H.SAFETY_HALLUCINATION_SCORE,
    H.PROVENANCE_HMAC,
    H.PROVENANCE_CHAIN_INTEGRITY,
    H.CONTEXT_PROTOCOL_VERSION,
)

# CRP-SPEC-014 §1.2 — additional mandatory headers for CRP-Standard.
STANDARD_ADDITIONAL_HEADERS: tuple[str, ...] = (
    H.QUALITY_SCORE,
    H.QUALITY_REPETITION,
    H.QUALITY_COMPLETENESS,
    H.QUALITY_FLOW,
    H.CONTEXT_QUALITY_TIER,
    H.CONTEXT_SATURATION,
    H.CONTEXT_ETAG,
    H.COMPLIANCE_EU_AI_ACT,
    H.COMPLIANCE_AUDIT_TRAIL_ID,
    H.COMPLIANCE_AUDIT_TRAIL_URI,
    H.PROVENANCE_CLAIM_COUNT,
    H.PROVENANCE_ATTRIBUTION_SCORE,
    H.PROVENANCE_FIDELITY_SCORE,
    H.PROVENANCE_REPORT_URI,
    H.CONTEXT_WINDOW,
    H.CONTEXT_CONTINUATION_ID,
)

STANDARD_MANDATORY_HEADERS: tuple[str, ...] = (
    BASIC_MANDATORY_HEADERS + STANDARD_ADDITIONAL_HEADERS
)


def mandatory_headers(level: ConformanceLevel) -> tuple[str, ...]:
    """Return the mandatory header set for a conformance level."""
    if level is ConformanceLevel.BASIC:
        return BASIC_MANDATORY_HEADERS
    return STANDARD_MANDATORY_HEADERS


__all__ = [
    "ConformanceLevel",
    "BASIC_MANDATORY_HEADERS",
    "STANDARD_ADDITIONAL_HEADERS",
    "STANDARD_MANDATORY_HEADERS",
    "mandatory_headers",
]
