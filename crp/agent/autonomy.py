# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Autonomy-by-measurement — measured reliability → enforced autonomy tier (SPEC-026).

CRP assigns an agent an autonomy tier from measured evidence, not from a config
flag.  The inputs are:

  - ``asr`` (attack success rate): any consequential successful attack is a
    hard ceiling on autonomy.
  - ``pass_hat_k``: unbiased pass@k from verification / benchmark samples.
  - ``verification_rate``: fraction of produced claims that were verified.
  - ``n``: number of samples behind the pass@k estimate.

Tiers:
  ``T0`` — supervised: every action gated by human/ checkpoint.
  ``T1`` — constrained: deterministic tools only, grounding required.
  ``T2`` — conditional: tool use allowed, HIGH-risk actions simulated.
  ``T3`` — autonomous: routine operation without human-in-the-loop.

The governor is a small, deterministic function so it can be invoked in the
hot path of every agent dispatch without ML inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from crp.security.kill_switch import KillSwitch, KillSwitchReason


class AutonomyTier(str, Enum):
    """Autonomy tiers ordered from least to most autonomous."""

    T0_SUPERVISED = "T0_supervised"
    T1_CONSTRAINED = "T1_constrained"
    T2_CONDITIONAL = "T2_conditional"
    T3_AUTONOMOUS = "T3_autonomous"


class AutonomyAction(str, Enum):
    """Canonical actions an agent may attempt, from low to high risk."""

    READ = "read"
    TOOL = "tool"
    WRITE = "write"
    HIGH_RISK = "high_risk"
    DELEGATE = "delegate"


@dataclass
class AutonomyMetrics:
    """Measured evidence used to assign an autonomy tier."""

    asr: float = 0.0          # attack success rate [0, 1]
    pass_k: float = 0.0         # pass@k or pass^k [0, 1]
    verification_rate: float = 0.0  # verified claims / total claims [0, 1]
    n_samples: int = 0          # sample count behind pass_k
    n_attacks: int = 0          # number of attack trials behind asr

    def __post_init__(self) -> None:
        self.asr = max(0.0, min(1.0, float(self.asr)))
        self.pass_k = max(0.0, min(1.0, float(self.pass_k)))
        self.verification_rate = max(0.0, min(1.0, float(self.verification_rate)))
        self.n_samples = max(0, int(self.n_samples))
        self.n_attacks = max(0, int(self.n_attacks))


@dataclass
class AutonomyDecision:
    """Outcome of a tier assignment and action authorization."""

    tier: AutonomyTier
    action: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict."""
        return {
            "tier": self.tier.value,
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
        }


class AutonomyGovernor:
    """Assign autonomy tiers from measured reliability and enforce action policy.

    Usage::

        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.0, pass_k=0.92, verification_rate=0.91, n_samples=40)
        tier = gov.assign_tier(metrics)
        decision = gov.authorize(tier, AutonomyAction.HIGH_RISK)
    """

    # Minimum samples required before trusting a pass@k estimate enough for T3.
    MIN_SAMPLES_T3: int = 30
    MIN_SAMPLES_T2: int = 10

    def assign_tier(self, metrics: AutonomyMetrics) -> AutonomyTier:
        """Return the autonomy tier implied by *metrics*.

        Rules (most restrictive wins):
        1. ASR > 0.05 or < 10 samples → T0 supervised.
        2. ASR > 0 or pass@k < 0.90 or verification < 0.70 → T1 constrained.
        3. pass@k >= 0.90 and verification >= 0.90 and n >= 30 → T3 autonomous.
        4. Otherwise (pass@k >= 0.90, verification >= 0.70) → T2 conditional.
        """
        if metrics.asr > 0.05 or metrics.n_samples < self.MIN_SAMPLES_T2:
            return AutonomyTier.T0_SUPERVISED
        if metrics.asr > 0.0 or metrics.pass_k < 0.90 or metrics.verification_rate < 0.70:
            return AutonomyTier.T1_CONSTRAINED
        if metrics.pass_k >= 0.90 and metrics.verification_rate >= 0.90 and metrics.n_samples >= self.MIN_SAMPLES_T3:
            return AutonomyTier.T3_AUTONOMOUS
        return AutonomyTier.T2_CONDITIONAL

    def authorize(self, tier: AutonomyTier, action: AutonomyAction | str) -> AutonomyDecision:
        """Return whether *action* is permitted at *tier*.

        Policy matrix:
          T0: only READ allowed (everything else → checkpoint).
          T1: READ + TOOL with grounding.
          T2: READ + TOOL + WRITE; HIGH_RISK simulated/gated.
          T3: all actions allowed, including DELEGATE.
        """
        action = AutonomyAction(action) if isinstance(action, str) else action
        if tier == AutonomyTier.T0_SUPERVISED:
            allowed = action == AutonomyAction.READ
            reason = "T0: all non-read actions require human supervision" if not allowed else "T0: read allowed"
        elif tier == AutonomyTier.T1_CONSTRAINED:
            allowed = action in {AutonomyAction.READ, AutonomyAction.TOOL}
            reason = "T1: only read and deterministic tool actions allowed" if not allowed else "T1: allowed"
        elif tier == AutonomyTier.T2_CONDITIONAL:
            allowed = action in {AutonomyAction.READ, AutonomyAction.TOOL, AutonomyAction.WRITE}
            reason = "T2: high-risk/delegate actions require simulation or checkpoint" if not allowed else "T2: allowed"
        else:  # T3
            allowed = True
            reason = "T3: autonomous"

        return AutonomyDecision(tier=tier, action=action.value, allowed=allowed, reason=reason)

    def enforce(
        self,
        metrics: AutonomyMetrics,
        action: AutonomyAction | str,
        *,
        kill_switch: KillSwitch | None = None,
    ) -> AutonomyDecision:
        """Assign tier and authorize action in one call.

        If *kill_switch* is provided and the metrics show a severe trust
        collapse (ASR > 0.10), the kill-switch is fired.
        """
        tier = self.assign_tier(metrics)
        decision = self.authorize(tier, action)
        if metrics.asr > 0.10 and kill_switch is not None and not kill_switch.is_fired:
            kill_switch.fire(
                session_id="",
                reason=KillSwitchReason.RUNTIME_ANOMALY.value,
                triggered_by="crp.agent.autonomy",
                snapshot=metrics.__dict__,
            )
            return AutonomyDecision(
                tier=AutonomyTier.T0_SUPERVISED,
                action=str(action),
                allowed=False,
                reason="ASR exceeded 0.10 — kill-switch fired, session downgraded to supervised",
            )
        return decision
