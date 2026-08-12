# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Policy data model (CRP-SPEC-006).

Dataclasses and enums for the ``CRP-Safety-Policy`` directive language —
a CSP-inspired declarative syntax for AI safety enforcement at the transport
layer.  This module defines the structure; :mod:`crp.policy.grammar` parses
strings into it and :mod:`crp.policy.enforce` evaluates it against DPE output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    """DPE risk classification — ordered LOW < MEDIUM < HIGH < CRITICAL."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        """Return the rank."""
        return _RISK_RANK[self]

    def __ge__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        if isinstance(other, RiskLevel):
            return self.rank >= other.rank
        return NotImplemented

    def __gt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        if isinstance(other, RiskLevel):
            return self.rank > other.rank
        return NotImplemented

    def __le__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        if isinstance(other, RiskLevel):
            return self.rank <= other.rank
        return NotImplemented

    def __lt__(self, other: "RiskLevel") -> bool:  # type: ignore[override]
        if isinstance(other, RiskLevel):
            return self.rank < other.rank
        return NotImplemented


_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class RepetitionLevel(str, Enum):
    """DPE Stage 7 repetition classification — ordered NONE < … < SEVERE."""

    NONE = "NONE"
    MINOR = "MINOR"
    SIGNIFICANT = "SIGNIFICANT"
    SEVERE = "SEVERE"

    @property
    def rank(self) -> int:
        """Return the rank."""
        return _REP_RANK[self]


_REP_RANK: dict[RepetitionLevel, int] = {
    RepetitionLevel.NONE: 0,
    RepetitionLevel.MINOR: 1,
    RepetitionLevel.SIGNIFICANT: 2,
    RepetitionLevel.SEVERE: 3,
}


class OversightMode(str, Enum):
    """Human-oversight mode (CRP-SPEC-002 §5.10)."""

    AUTO = "auto"
    HUMAN_REVIEW = "human-review"
    HALT = "halt"
    LOG_ONLY = "log-only"


class Strategy(str, Enum):
    """Dispatch strategies allowed by ``upgrade-on-risk`` (CRP-SPEC-008)."""

    REFLEXIVE = "reflexive"
    HIERARCHICAL = "hierarchical"
    BATCH = "batch"


# Valid source-trust tokens for ``default-src``.
SOURCE_VALUES: frozenset[str] = frozenset(
    {"context", "parametric", "ckf", "cross-session", "'none'"}
)

# Valid quality tiers for ``require-quality``.
QUALITY_TIERS: frozenset[str] = frozenset({"S", "A", "B", "C", "D"})


@dataclass
class SafetyPolicy:
    """A parsed ``CRP-Safety-Policy`` value.

    Unset directives are ``None`` / ``False`` / empty.  ``report_only`` is set
    when the policy arrived via the ``CRP-Safety-Policy-Report-Only`` header.
    """

    # Source trust
    default_src: list[str] = field(default_factory=lambda: ["context", "parametric"])

    # Risk-level enforcement
    halt_on: RiskLevel | None = None
    warn_on: RiskLevel | None = None

    # Threshold requirements
    require_grounding: float | None = None
    require_entailment: float | None = None
    require_quality: list[str] = field(default_factory=list)
    require_flow: float | None = None
    require_completeness: float | None = None
    require_oversight: OversightMode | None = None

    # Blocking
    block_ungrounded: bool = False
    block_mixed: bool = False
    block_parametric: bool = False
    block_pii: bool = False
    block_fabrication: bool = False
    block_repetition: bool = False
    max_repetition: RepetitionLevel | None = None

    # Strategy / oversight / reporting
    upgrade_on_risk: Strategy | None = None
    oversight: OversightMode | None = None
    report_uri: str | None = None
    report_to: str | None = None

    # Meta
    report_only: bool = False
    profile: str | None = None
    raw: str = ""

    def to_policy_string(self) -> str:
        """Render the policy back to canonical ``CRP-Safety-Policy`` syntax."""
        parts: list[str] = []
        if self.default_src:
            parts.append("default-src " + " ".join(self.default_src))
        if self.halt_on:
            parts.append(f"halt-on {self.halt_on.value}")
        if self.warn_on:
            parts.append(f"warn-on {self.warn_on.value}")
        if self.require_grounding is not None:
            parts.append(f"require-grounding {self.require_grounding:.2f}")
        if self.require_entailment is not None:
            parts.append(f"require-entailment {self.require_entailment:.2f}")
        if self.require_quality:
            parts.append("require-quality " + " ".join(self.require_quality))
        if self.require_flow is not None:
            parts.append(f"require-flow {self.require_flow:.2f}")
        if self.require_completeness is not None:
            parts.append(f"require-completeness {self.require_completeness:.2f}")
        if self.require_oversight:
            parts.append(f"require-oversight {self.require_oversight.value}")
        if self.block_ungrounded:
            parts.append("block-ungrounded")
        if self.block_mixed:
            parts.append("block-mixed")
        if self.block_parametric:
            parts.append("block-parametric")
        if self.block_pii:
            parts.append("block-pii")
        if self.block_fabrication:
            parts.append("block-fabrication")
        if self.block_repetition:
            parts.append("block-repetition")
        if self.max_repetition:
            parts.append(f"max-repetition {self.max_repetition.value}")
        if self.upgrade_on_risk:
            parts.append(f"upgrade-on-risk {self.upgrade_on_risk.value}")
        if self.oversight:
            parts.append(f"oversight {self.oversight.value}")
        if self.report_uri:
            parts.append(f"report-uri {self.report_uri}")
        if self.report_to:
            parts.append(f"report-to {self.report_to}")
        return "; ".join(parts)


class EnforcementAction(str, Enum):
    """The action a policy decision recommends — ordered by severity."""

    PASS = "PASS"
    WARN = "WARN"
    CONTINUE = "CONTINUE"          # auto-dispatch a continuation window
    REDISPATCH = "REDISPATCH"      # re-run with an upgraded strategy/mode
    HALT = "HALT"                  # stop delivery, return HTTP 451/503

    @property
    def severity(self) -> int:
        """Return the severity."""
        return _ACTION_SEVERITY[self]


_ACTION_SEVERITY: dict[EnforcementAction, int] = {
    EnforcementAction.PASS: 0,
    EnforcementAction.WARN: 1,
    EnforcementAction.CONTINUE: 2,
    EnforcementAction.REDISPATCH: 3,
    EnforcementAction.HALT: 4,
}


class ViolationType(str, Enum):
    """Categorised policy-violation reasons (used in violation reports)."""

    HALT_ON_RISK = "HALT_ON_RISK"
    WARN_ON_RISK = "WARN_ON_RISK"
    GROUNDING_BELOW_THRESHOLD = "GROUNDING_BELOW_THRESHOLD"
    ENTAILMENT_BELOW_THRESHOLD = "ENTAILMENT_BELOW_THRESHOLD"
    QUALITY_TIER_REJECTED = "QUALITY_TIER_REJECTED"
    FLOW_BELOW_THRESHOLD = "FLOW_BELOW_THRESHOLD"
    COMPLETENESS_BELOW_THRESHOLD = "COMPLETENESS_BELOW_THRESHOLD"
    UNGROUNDED_CLAIM = "UNGROUNDED_CLAIM"
    PARAMETRIC_CONTENT = "PARAMETRIC_CONTENT"
    PII_DETECTED = "PII_DETECTED"
    FABRICATION_DETECTED = "FABRICATION_DETECTED"
    MIXED_CONTENT = "MIXED_CONTENT"
    REPETITION_EXCEEDED = "REPETITION_EXCEEDED"
    SOURCE_NOT_TRUSTED = "SOURCE_NOT_TRUSTED"


@dataclass
class Violation:
    """A single directive that was violated by the analysed response."""

    directive: str
    violation_type: ViolationType
    action: EnforcementAction
    detail: str = ""
    http_status: int | None = None


@dataclass
class PolicyDecision:
    """Result of evaluating a :class:`SafetyPolicy` against DPE signals."""

    action: EnforcementAction = EnforcementAction.PASS
    http_status: int | None = None
    violations: list[Violation] = field(default_factory=list)
    retry_after: str | None = None
    recommended_strategy: str | None = None
    recommended_grounding_mode: str | None = None
    report_only: bool = False

    @property
    def halted(self) -> bool:
        """Return whether the halted condition holds."""
        return self.action == EnforcementAction.HALT and not self.report_only

    @property
    def headers(self) -> dict[str, str]:
        """CRP headers describing this decision (violation + retry-after)."""
        out: dict[str, str] = {}
        if self.violations:
            out["CRP-Safety-Policy-Violation"] = ",".join(
                v.violation_type.value for v in self.violations
            )
        if self.retry_after:
            out["CRP-Safety-Retry-After"] = self.retry_after
        return out
