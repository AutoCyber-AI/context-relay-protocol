# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Zero-CKF Safety Policy adjustments (CRP-SPEC-017 §6).

In Zero-CKF mode there are no facts to ground against, so certain Safety Policy
directives cannot be enforced as written.  Rather than block every response,
the gateway *auto-adjusts* the offending directives and emits
``CRP-Safety-Policy-Adjustment`` so the developer (and CRP-Scan / Comply) can
see what will be enforced once the CKF is populated.

Safety directives that still work without facts — ``halt-on``, ``block-pii``,
``upgrade-on-risk``, ``oversight``, ``report-uri`` — are left untouched.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from crp.policy.model import SafetyPolicy


@dataclass
class PolicyAdjustment:
    """A single auto-adjusted directive (CRP-SPEC-017 §6.2)."""

    directive: str
    adjusted_to: str
    reason: str = "zero-ckf-mode"

    def to_header_value(self) -> str:
        """Serialize this adjustment to a CRP-Safety-Policy-Adjustment header value."""
        return f"directive={self.directive}; adjusted-to={self.adjusted_to}; reason={self.reason}"


@dataclass
class AdjustedPolicy:
    """A Zero-CKF-adjusted policy plus the list of adjustments made."""

    policy: SafetyPolicy
    adjustments: list[PolicyAdjustment] = field(default_factory=list)

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        # One CRP-Safety-Policy-Adjustment per adjusted directive (joined).
        if not self.adjustments:
            return {}
        return {
            "CRP-Safety-Policy-Adjustment": ", ".join(
                a.to_header_value() for a in self.adjustments
            )
        }


def adjust_for_zero_ckf(policy: SafetyPolicy) -> AdjustedPolicy:
    """Return a Zero-CKF-adjusted copy of *policy* (CRP-SPEC-017 §6.1).

    Adjustments:
        - ``default-src context`` → add ``parametric`` (relax source trust)
        - ``block-ungrounded`` → downgrade to warn (cleared + flagged)
        - ``require-grounding`` → skipped (no facts to ground against)

    ``halt-on``, ``block-pii``, ``require-entailment`` (vs. query),
    ``upgrade-on-risk``, ``oversight`` and ``report-uri`` are preserved.
    """
    adjusted = copy.deepcopy(policy)
    changes: list[PolicyAdjustment] = []

    # default-src context (without parametric) → relax to allow parametric.
    if "context" in adjusted.default_src and "parametric" not in adjusted.default_src:
        if "'none'" not in adjusted.default_src:
            adjusted.default_src = adjusted.default_src + ["parametric"]
            changes.append(
                PolicyAdjustment("default-src context", "default-src context parametric")
            )

    # block-ungrounded → warn-ungrounded (clear the hard block).
    if adjusted.block_ungrounded:
        adjusted.block_ungrounded = False
        changes.append(PolicyAdjustment("block-ungrounded", "warn-ungrounded"))

    # require-grounding → skipped (no envelope to ground against).
    if adjusted.require_grounding is not None:
        skipped = f"require-grounding {adjusted.require_grounding:.2f}"
        adjusted.require_grounding = None
        changes.append(PolicyAdjustment(skipped, "skipped"))

    return AdjustedPolicy(policy=adjusted, adjustments=changes)
