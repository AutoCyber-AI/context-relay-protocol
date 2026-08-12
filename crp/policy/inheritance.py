# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Policy inheritance & tightening in multi-agent chains (CRP-SPEC-006 §5).

A child agent's Safety Policy MUST be equal to or *more restrictive* than its
parent's.  :func:`check_inheritance` detects any relaxation; the gateway rejects
relaxing child requests with HTTP 403 and ``CRP-Safety-Policy-Violation: inheritance``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .mode import merge_policies
from .model import RiskLevel, SafetyPolicy, _REP_RANK


@dataclass
class InheritanceResult:
    """Outcome of comparing a child policy against its parent."""

    valid: bool = True
    relaxations: list[str] = field(default_factory=list)
    applied_policy: SafetyPolicy | None = None

    @property
    def http_status(self) -> int | None:
        """Return the HTTP status."""
        return None if self.valid else 403

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        out: dict[str, str] = {}
        if not self.valid:
            out["CRP-Safety-Policy-Violation"] = "inheritance"
        if self.applied_policy is not None:
            out["CRP-Safety-Policy-Applied"] = self.applied_policy.to_policy_string()
        return out


def _risk_relaxed(parent: RiskLevel | None, child: RiskLevel | None) -> bool:
    """For halt/warn: child relaxes if it triggers at a *higher* risk than parent."""
    if parent is None:
        return False  # parent unset → child may add constraints freely
    if child is None:
        return True   # parent had a constraint, child dropped it → relaxed
    return child.rank > parent.rank


def _threshold_relaxed(parent: float | None, child: float | None) -> bool:
    if parent is None:
        return False
    if child is None:
        return True
    return child < parent


def check_inheritance(parent: SafetyPolicy, child: SafetyPolicy) -> InheritanceResult:
    """Validate that *child* is at least as restrictive as *parent* (§5.1).

    Returns an :class:`InheritanceResult` whose ``applied_policy`` is the
    most-restrictive merge of the two (used when the child is valid).
    """
    relaxations: list[str] = []

    if _risk_relaxed(parent.halt_on, child.halt_on):
        relaxations.append("halt-on")
    if _risk_relaxed(parent.warn_on, child.warn_on):
        relaxations.append("warn-on")
    if _threshold_relaxed(parent.require_grounding, child.require_grounding):
        relaxations.append("require-grounding")
    if _threshold_relaxed(parent.require_entailment, child.require_entailment):
        relaxations.append("require-entailment")
    if _threshold_relaxed(parent.require_flow, child.require_flow):
        relaxations.append("require-flow")
    if _threshold_relaxed(parent.require_completeness, child.require_completeness):
        relaxations.append("require-completeness")

    # Blocks: child must keep every block the parent set.
    for attr in (
        "block_ungrounded",
        "block_parametric",
        "block_pii",
        "block_fabrication",
        "block_repetition",
    ):
        if getattr(parent, attr) and not getattr(child, attr):
            relaxations.append(attr.replace("_", "-"))

    # default-src: child must not add sources the parent disallowed.
    if parent.default_src and "'none'" not in parent.default_src:
        added = [s for s in child.default_src if s not in parent.default_src]
        if added:
            relaxations.append("default-src")

    # require-quality: the child MUST NOT permit a tier the parent forbade
    # (tier-set intersection — a child may only narrow the allowed tiers).
    if parent.require_quality:
        widened = [t for t in child.require_quality if t not in parent.require_quality]
        if not child.require_quality or widened:
            relaxations.append("require-quality")

    # max-repetition: the child's ceiling MUST be at least as strict (≤) as the
    # parent's.  A higher ceiling (or dropping it) permits more repetition.
    if parent.max_repetition is not None:
        if child.max_repetition is None:
            relaxations.append("max-repetition")
        elif _REP_RANK[child.max_repetition] > _REP_RANK[parent.max_repetition]:
            relaxations.append("max-repetition")

    result = InheritanceResult(valid=not relaxations, relaxations=relaxations)
    if result.valid:
        result.applied_policy = merge_policies(parent, child)
    return result


def resolve_effective_policy(
    parent: SafetyPolicy | None, child: SafetyPolicy | None
) -> SafetyPolicy | None:
    """Resolve the effective child policy when the child may omit one (§5, C4d).

    SPEC-012 §5: a sub-agent that sends no ``CRP-Safety-Policy`` of its own
    inherits the parent's policy verbatim.  When both are present the result is
    the most-restrictive merge (delegated to :func:`check_inheritance`'s caller).

    Returns:
        * the parent's policy when *child* is ``None`` (full inheritance),
        * the child's policy when *parent* is ``None``,
        * otherwise the most-restrictive merge of the two.
    """
    if child is None:
        return parent
    if parent is None:
        return child
    return merge_policies(parent, child)
