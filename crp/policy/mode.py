# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP-Safety-Mode shorthand + policy merging (CRP-SPEC-006 §4.2).

``CRP-Safety-Mode`` is a shorthand for common policy combinations.  When both
``CRP-Safety-Mode`` and ``CRP-Safety-Policy`` are supplied, the two are merged
per-directive with *most-restrictive-wins* semantics.
"""

from __future__ import annotations

from .grammar import parse_policy
from .model import (
    EnforcementAction,
    OversightMode,
    RepetitionLevel,
    RiskLevel,
    SafetyPolicy,
)

# CRP-SPEC-006 §4.2 — mode → equivalent policy string.
MODES: dict[str, str] = {
    "strict": "halt-on CRITICAL; warn-on HIGH; block-ungrounded; require-grounding 0.75",
    "warn": "warn-on CRITICAL",
    "permissive": "default-src context parametric",
}


def mode_policy(mode: str) -> SafetyPolicy:
    """Return the :class:`SafetyPolicy` for a ``CRP-Safety-Mode`` shorthand."""
    key = mode.strip().lower()
    if key not in MODES:
        raise ValueError(f"unknown safety mode {mode!r} (expected one of: {', '.join(MODES)})")
    return parse_policy(MODES[key])


def _tighter_risk(a: RiskLevel | None, b: RiskLevel | None) -> RiskLevel | None:
    """For halt/warn: the *lower* risk level is more restrictive (halts sooner)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if a.rank <= b.rank else b


def _higher_threshold(a: float | None, b: float | None) -> float | None:
    """For require-*: the *higher* threshold is more restrictive."""
    vals = [v for v in (a, b) if v is not None]
    return max(vals) if vals else None


def _tighter_repetition(a: RepetitionLevel | None, b: RepetitionLevel | None) -> RepetitionLevel | None:
    """For max-repetition: the *lower* level is more restrictive."""
    if a is None:
        return b
    if b is None:
        return a
    return a if a.rank <= b.rank else b


# Oversight modes ordered least → most restrictive.
_OVERSIGHT_RANK: dict[OversightMode, int] = {
    OversightMode.LOG_ONLY: 0,
    OversightMode.AUTO: 1,
    OversightMode.HUMAN_REVIEW: 2,
    OversightMode.HALT: 3,
}


def _tighter_oversight(a: OversightMode | None, b: OversightMode | None) -> OversightMode | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if _OVERSIGHT_RANK[a] >= _OVERSIGHT_RANK[b] else b


def merge_policies(base: SafetyPolicy, override: SafetyPolicy) -> SafetyPolicy:
    """Merge two policies with *most-restrictive-wins* (CRP-SPEC-006 §4.1/§4.2).

    Used both for Mode+Policy combination and as the comparison primitive for
    inheritance.  The result is a new :class:`SafetyPolicy`; inputs are unchanged.
    """
    merged = SafetyPolicy(default_src=[])

    # default-src: intersection is the most restrictive (fewer trusted sources).
    if base.default_src and override.default_src:
        inter = [s for s in base.default_src if s in override.default_src]
        # An empty intersection collapses to 'none' (trust nothing).
        merged.default_src = inter or ["'none'"]
    else:
        merged.default_src = base.default_src or override.default_src

    merged.halt_on = _tighter_risk(base.halt_on, override.halt_on)
    merged.warn_on = _tighter_risk(base.warn_on, override.warn_on)

    merged.require_grounding = _higher_threshold(base.require_grounding, override.require_grounding)
    merged.require_entailment = _higher_threshold(base.require_entailment, override.require_entailment)
    merged.require_flow = _higher_threshold(base.require_flow, override.require_flow)
    merged.require_completeness = _higher_threshold(
        base.require_completeness, override.require_completeness
    )

    # require-quality: union of accepted tiers is more restrictive only by
    # intersection; the stricter list is the intersection of accepted tiers.
    if base.require_quality and override.require_quality:
        merged.require_quality = [t for t in base.require_quality if t in override.require_quality]
    else:
        merged.require_quality = base.require_quality or override.require_quality

    merged.require_oversight = _tighter_oversight(base.require_oversight, override.require_oversight)
    merged.oversight = _tighter_oversight(base.oversight, override.oversight)

    # Blocks: OR — if either blocks, the merged policy blocks.
    merged.block_ungrounded = base.block_ungrounded or override.block_ungrounded
    merged.block_parametric = base.block_parametric or override.block_parametric
    merged.block_pii = base.block_pii or override.block_pii
    merged.block_fabrication = base.block_fabrication or override.block_fabrication
    merged.block_repetition = base.block_repetition or override.block_repetition
    merged.max_repetition = _tighter_repetition(base.max_repetition, override.max_repetition)

    # Strategy / reporting: override wins if present, else base.
    merged.upgrade_on_risk = override.upgrade_on_risk or base.upgrade_on_risk
    merged.report_uri = override.report_uri or base.report_uri
    merged.report_to = override.report_to or base.report_to
    merged.report_only = base.report_only and override.report_only
    merged.profile = override.profile or base.profile

    return merged
