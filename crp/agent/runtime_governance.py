# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Runtime governance bridge — wires Wave 2 modules into a single action path.

This module activates the previously inert SPEC-051/055/057 code at runtime by
exposing one ``GovernedAction`` helper.  A call to ``execute()`` runs:

  1. Autonomy tier check (ASR/pass^k → allowed action).
  2. Trust-monitor observation of the proposed action.
  3. Predictive-positioning simulation for HIGH-risk actions (SPEC-051).
  4. Epistemic adjustment from semantic entropy of sample outputs (SPEC-055).
  5. Bi-temporal CKF grounding lookup (SPEC-057).
  6. Memory write with authority-lattice enforcement (SPEC-045).

The bridge is opt-in: existing orchestrator paths keep working unchanged; callers
(such as the Agent SDK or Gateway) instantiate it when they want the full
Wave-2 governance stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crp.agent.autonomy import AutonomyAction, AutonomyGovernor, AutonomyMetrics
from crp.btf import BiTemporalFact, TemporalCKF
from crp.ep import epistemic_adjust
from crp.ep.calibration import CalibrationProfile
from crp.pp import WorldModel, guarded_dispatch
from crp.security.kill_switch import KillSwitch
from crp.security.trust_monitor import TrustMonitor
from crp.state.memory_authority import Authority, MemoryAuthorityLattice, MemoryTier

logger = logging.getLogger("crp.agent.runtime_governance")


@dataclass
class GovernedActionResult:
    """Result of a governed action execution."""

    executed: bool
    result: Any
    tier: str
    trust_action: str
    trust_score: float
    simulated: bool
    simulation_allowed: bool | None
    epistemic_adjustment: dict[str, Any] | None
    memory_entry_id: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a dict."""
        return {
            "executed": self.executed,
            "result": self.result,
            "tier": self.tier,
            "trust_action": self.trust_action,
            "trust_score": self.trust_score,
            "simulated": self.simulated,
            "simulation_allowed": self.simulation_allowed,
            "epistemic_adjustment": self.epistemic_adjustment,
            "memory_entry_id": self.memory_entry_id,
            "reason": self.reason,
        }


@dataclass
class RuntimeGovernorConfig:
    """Configuration for the runtime governance bridge."""

    autonomy_metrics: AutonomyMetrics = field(default_factory=AutonomyMetrics)
    calibration_profile: CalibrationProfile | None = None
    entropy_samples: list[str] | None = None
    base_tier: str = "B"
    base_risk: str = "MEDIUM"
    # Risk levels that trigger predictive-positioning simulation.
    simulate_risk_levels: set[str] = field(default_factory=lambda: {"HIGH"})
    sim_confidence_floor: float = 0.75
    # Memory write parameters.
    memory_actor: Authority = Authority.AGENT
    memory_tier: MemoryTier = MemoryTier.CONVERSATIONAL


class GovernedAction:
    """One-shot governed action executor.

    Usage::

        ga = GovernedAction(
            session_id="s-1",
            kill_switch=KillSwitch(),
            trust_monitor=TrustMonitor("s-1"),
            memory=MemoryAuthorityLattice(),
            temporal_ckf=TemporalCKF(),
            world_model=WorldModel([]),
            governor=AutonomyGovernor(),
        )
        result = ga.execute(
            state={"goal": "deploy"},
            action="deploy",
            risk="HIGH",
            execute_fn=lambda s, a, p: {"status": "deployed"},
            checkpoint_fn=lambda r, p, s: {"status": "checkpoint"},
            entropy_samples=["sample A", "sample B"],
        )
    """

    def __init__(
        self,
        session_id: str,
        *,
        kill_switch: KillSwitch,
        trust_monitor: TrustMonitor,
        memory: MemoryAuthorityLattice,
        temporal_ckf: TemporalCKF,
        world_model: WorldModel,
        governor: AutonomyGovernor,
        config: RuntimeGovernorConfig | None = None,
    ) -> None:
        self._session_id = session_id
        self._kill_switch = kill_switch
        self._trust = trust_monitor
        self._memory = memory
        self._temporal = temporal_ckf
        self._world = world_model
        self._governor = governor
        self._config = config or RuntimeGovernorConfig()

    def execute(
        self,
        state: dict[str, Any],
        action: str,
        risk: str,
        execute_fn: Any,
        checkpoint_fn: Any,
        *,
        action_kind: AutonomyAction | str = AutonomyAction.HIGH_RISK,
        entropy_samples: list[str] | None = None,
        btf_subject: str | None = None,
        btf_predicate: str | None = None,
        memory_key: str | None = None,
        memory_value: Any | None = None,
    ) -> GovernedActionResult:
        """Run the full Wave-2 governance pipeline for one action.

        Args:
            state: Current state features.
            action: Action name.
            risk: Risk level string (LOW/MEDIUM/HIGH/CRITICAL).
            execute_fn: ``fn(state, action, prediction) -> result``.
            checkpoint_fn: ``fn(reason, prediction, state) -> result``.
            action_kind: Autonomy classification of the action.
            entropy_samples: Optional list of outputs for semantic-entropy.
            btf_subject / btf_predicate: Optional bi-temporal CKF lookup.
            memory_key / memory_value: Optional memory entry to remember on success.

        Returns:
            ``GovernedActionResult`` with execution status and governance signals.
        """
        # 1. Autonomy tier check.
        autonomy_decision = self._governor.enforce(
            self._config.autonomy_metrics,
            action_kind,
            kill_switch=self._kill_switch,
        )
        if not autonomy_decision.allowed:
            return GovernedActionResult(
                executed=False,
                result=None,
                tier=autonomy_decision.tier.value,
                trust_action=self._trust._graduated_action(),
                trust_score=self._trust.trust_score,
                simulated=False,
                simulation_allowed=None,
                epistemic_adjustment=None,
                memory_entry_id=None,
                reason=autonomy_decision.reason,
            )

        # 2. Trust observation.
        trust_decision = self._trust.observe({
            "action": action,
            "risk": risk,
            "input": state.get("input", ""),
        })
        if trust_decision.action == "kill":
            if not self._kill_switch.is_fired:
                self._kill_switch.fire(
                    session_id=self._session_id,
                    reason="trust_threshold_crossed",
                    triggered_by="crp.agent.runtime_governance",
                    snapshot=trust_decision.to_dict(),
                )
            return GovernedActionResult(
                executed=False,
                result=None,
                tier=autonomy_decision.tier.value,
                trust_action=trust_decision.action,
                trust_score=trust_decision.trust_score,
                simulated=False,
                simulation_allowed=None,
                epistemic_adjustment=None,
                memory_entry_id=None,
                reason=f"trust kill: {trust_decision.reason}",
            )

        # 3. Predictive positioning for HIGH-risk actions.
        policy = _SimulationPolicy(
            simulate_risk_levels=self._config.simulate_risk_levels,
            sim_confidence_floor=self._config.sim_confidence_floor,
        )
        simulated = risk in self._config.simulate_risk_levels
        sim_result = guarded_dispatch(
            state=state,
            action=action,
            risk=risk,
            world=self._world,
            policy=policy,
            execute_fn=execute_fn,
            checkpoint_fn=checkpoint_fn,
        )
        simulation_allowed = None if not simulated else bool(sim_result.get("_simulation", {}).get("allowed"))

        if simulation_allowed is False:
            return GovernedActionResult(
                executed=False,
                result=sim_result,
                tier=autonomy_decision.tier.value,
                trust_action=trust_decision.action,
                trust_score=trust_decision.trust_score,
                simulated=True,
                simulation_allowed=False,
                epistemic_adjustment=None,
                memory_entry_id=None,
                reason="predictive positioning blocked the action",
            )

        # 4. Epistemic adjustment from semantic entropy.
        epistemic: dict[str, Any] | None = None
        if entropy_samples:
            try:
                from crp.ep import semantic_entropy

                entropy = semantic_entropy(entropy_samples, budget_ms=100.0)
                epistemic = epistemic_adjust(
                    base_tier=self._config.base_tier,
                    risk=risk,
                    entropy=entropy,
                    profile=self._config.calibration_profile,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Epistemic adjustment skipped: %s", exc)

        # 5. Bi-temporal CKF grounding.
        grounding: BiTemporalFact | None = None
        if btf_subject and btf_predicate:
            grounding = self._temporal.current(btf_subject, btf_predicate)

        # 6. Execute (or use sim_result if already produced by guarded_dispatch).
        if simulated:
            result = sim_result
            executed = True
        else:
            result = execute_fn(state, action, None)
            executed = True

        # 7. Memory write with authority lattice.
        memory_entry_id: str | None = None
        if memory_key is not None and memory_value is not None:
            entry = self._memory.remember(
                memory_key,
                memory_value,
                self._config.memory_actor,
                self._config.memory_tier,
                source=f"action:{action}",
            )
            if entry is not None:
                memory_entry_id = entry.entry_id

        reason = (
            f"executed tier={autonomy_decision.tier.value} "
            f"trust={trust_decision.action} simulated={simulated}"
        )
        if grounding is not None:
            reason += f" grounded={grounding.object}"

        return GovernedActionResult(
            executed=executed,
            result=result,
            tier=autonomy_decision.tier.value,
            trust_action=trust_decision.action,
            trust_score=trust_decision.trust_score,
            simulated=simulated,
            simulation_allowed=simulation_allowed,
            epistemic_adjustment=epistemic,
            memory_entry_id=memory_entry_id,
            reason=reason,
        )


class _SimulationPolicy:
    """Minimal policy object expected by ``guarded_dispatch``."""

    def __init__(self, simulate_risk_levels: set[str], sim_confidence_floor: float) -> None:
        self.simulate_risk_levels = simulate_risk_levels
        self.sim_confidence_floor = sim_confidence_floor

    def check_predicted_outcome(self, predicted: dict[str, Any]) -> str | None:
        """Flag predicted outcomes that indicate harm."""
        if predicted.get("harm"):
            return "predicted_harm"
        if predicted.get("irreversible"):
            return "irreversible_action"
        return None
