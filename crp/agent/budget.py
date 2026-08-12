# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Budget + circuit breaker (CRP-SPEC-012 §2, §5; CRP-SPEC-015).

The Safety Budget is a session-scoped, header-observable risk-accumulation
signal.  Every session starts at ``1.0``; each *delivered* response decrements
it by an amount keyed to the DPE risk level.  When the budget crosses
thresholds, the gateway escalates oversight and ultimately halts the session —
the AI equivalent of a distributed-systems circuit breaker.

Relevant specifications:
  - CRP-SPEC-012: Multi-Agent Safety
  - CRP-SPEC-015: Security & Privacy

PRIVATE REFERENCE IMPLEMENTATION — SPEC-012 internals are not published.  This
module lives in the closed-source ``crp`` package only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from crp.policy.model import RiskLevel

INITIAL_BUDGET = 1.0

# CRP-SPEC-012 §2.2 — default decrements (within the spec's configurable ranges).
DEFAULT_DECREMENTS: dict[RiskLevel, float] = {
    RiskLevel.LOW: 0.00,
    RiskLevel.MEDIUM: 0.05,
    RiskLevel.HIGH: 0.15,
    RiskLevel.CRITICAL: 0.35,
}

# CRP-SPEC-012 §2.2 — interoperability bounds for configured decrements.
DECREMENT_RANGES: dict[RiskLevel, tuple[float, float]] = {
    RiskLevel.LOW: (0.00, 0.05),
    RiskLevel.MEDIUM: (0.02, 0.10),
    RiskLevel.HIGH: (0.10, 0.25),
    RiskLevel.CRITICAL: (0.25, 0.50),
}


class CircuitState(str, Enum):
    """Circuit-breaker state (CRP-SPEC-012 §5.1).

    Attributes:
        CLOSED: Normal operation; budget is above the half-open threshold.
        HALF_OPEN: Cautious operation; human review may be required.
        OPEN: Session halted; the gateway responds with HTTP 451.
    """

    CLOSED = "closed"        # budget > 0.50 — normal operation
    HALF_OPEN = "half-open"  # 0.10 < budget ≤ 0.50 — cautious / human-review
    OPEN = "open"            # budget ≤ 0.10 — session halted (HTTP 451)


class BudgetHealth(str, Enum):
    """Budget health band (CRP-SPEC-012 §2.3).

    Attributes:
        HEALTHY: Budget above 0.50.
        CAUTION: Budget between 0.25 and 0.50 inclusive.
        LOW: Budget between 0.10 and 0.24.
        DEPLETED: Budget at or below 0.10 but still positive.
        EXHAUSTED: Budget at or below 0.00.
    """

    HEALTHY = "healthy"      # > 0.50
    CAUTION = "caution"      # 0.25 – 0.50
    LOW = "low"              # 0.10 – 0.24
    DEPLETED = "depleted"    # ≤ 0.10
    EXHAUSTED = "exhausted"  # ≤ 0.00


@dataclass
class BudgetDecision:
    """Outcome of accounting a risk event against the budget.

    Attributes:
        budget: Remaining safety budget after the event.
        health: Human-readable health band for the remaining budget.
        circuit_state: Current circuit-breaker state.
        http_status: HTTP status to return when the session is halted, or None.
        force_oversight: Whether the gateway should force human review.
        warning: Short warning label for CRP-Safety-Budget-Warning header.
        retry_after: Retry guidance for halted sessions, or None.
    """

    budget: float
    health: BudgetHealth
    circuit_state: CircuitState
    http_status: int | None = None
    force_oversight: bool = False
    warning: str | None = None
    retry_after: str | None = None

    @property
    def halted(self) -> bool:
        """Return True if the session has been halted (HTTP 451)."""
        return self.http_status == 451

    @property
    def headers(self) -> dict[str, str]:
        """CRP headers describing the current budget state.

        Returns:
            Mapping of CRP header names to header values, including the
            remaining budget and any warning/oversight/retry directives.
        """
        out: dict[str, str] = {"CRP-Agent-Safety-Budget": f"{self.budget:.2f}"}
        if self.warning:
            out["CRP-Safety-Budget-Warning"] = self.warning
        if self.force_oversight:
            out["CRP-Safety-Oversight-Mode"] = "human-review"
        if self.retry_after:
            out["CRP-Safety-Retry-After"] = self.retry_after
        return out


def classify_budget(budget: float) -> tuple[BudgetHealth, CircuitState]:
    """Map a budget value to its health band and circuit state (§2.3, §5.1).

    Args:
        budget: Remaining safety budget, typically in the range [0.0, 1.0].

    Returns:
        A tuple of (``BudgetHealth``, ``CircuitState``) matching the budget
        threshold rules defined in CRP-SPEC-012.
    """
    if budget <= 0.0:
        return BudgetHealth.EXHAUSTED, CircuitState.OPEN
    if budget <= 0.10:
        return BudgetHealth.DEPLETED, CircuitState.OPEN
    if budget < 0.25:
        return BudgetHealth.LOW, CircuitState.HALF_OPEN
    if budget <= 0.50:
        return BudgetHealth.CAUTION, CircuitState.HALF_OPEN
    return BudgetHealth.HEALTHY, CircuitState.CLOSED


@dataclass
class AgentSafetyBudget:
    """Session-scoped safety budget (CRP-SPEC-012 §2).

    The authoritative budget value lives in the *signed* session token; this
    object is the gateway-side accountant.  Decrements are computed server-side
    only (anti-inflation, §10.1) and the budget never recovers within a session
    (§2.4).

    Attributes:
        budget: Current remaining safety budget, initialised to ``INITIAL_BUDGET``.
        decrements: Mapping from ``RiskLevel`` to the amount subtracted when a
            response at that risk level is delivered.  Values are clamped to
            the interoperability ranges in ``DECREMENT_RANGES``.
    """

    budget: float = INITIAL_BUDGET
    decrements: dict[RiskLevel, float] = field(
        default_factory=lambda: dict(DEFAULT_DECREMENTS)
    )

    def __post_init__(self) -> None:
        # Clamp configured decrements into the spec's interoperability ranges.
        for level, (lo, hi) in DECREMENT_RANGES.items():
            val = self.decrements.get(level, DEFAULT_DECREMENTS[level])
            self.decrements[level] = min(hi, max(lo, val))

    @property
    def health(self) -> BudgetHealth:
        """Return the current ``BudgetHealth`` band."""
        return classify_budget(self.budget)[0]

    @property
    def circuit_state(self) -> CircuitState:
        """Return the current ``CircuitState``."""
        return classify_budget(self.budget)[1]

    def peek(self) -> BudgetDecision:
        """Return the current decision without applying any decrement.

        Returns:
            A ``BudgetDecision`` reflecting the present budget state.
        """
        return self._decide()

    def account(
        self,
        risk_level: RiskLevel | None,
        *,
        is_redispatch: bool = False,
    ) -> BudgetDecision:
        """Decrement the budget for a *delivered* response's risk level (§2.2).

        Re-dispatches do not decrement (§2.5) — only the final delivered
        response counts.

        Args:
            risk_level: DPE risk level of the delivered response, or None if
                the response carries no risk classification.
            is_redispatch: When True, the event is a re-dispatch and must not
                decrement the budget.

        Returns:
            The resulting ``BudgetDecision`` after accounting for the event.
        """
        if not is_redispatch and risk_level is not None:
            self.budget = max(0.0, round(self.budget - self.decrements[risk_level], 4))
        return self._decide()

    def merge_downstream(self, sub_agent_budget: float) -> BudgetDecision:
        """Fan-in merge: orchestrator budget = ``min`` of self and sub-agent (§5.3).

        Args:
            sub_agent_budget: Remaining safety budget reported by a sub-agent.

        Returns:
            The resulting ``BudgetDecision`` after merging budgets.
        """
        self.budget = min(self.budget, sub_agent_budget)
        return self._decide()

    def _decide(self) -> BudgetDecision:
        """Build a ``BudgetDecision`` from the current budget value.

        Returns:
            A fully populated ``BudgetDecision``, including halt/warning
            directives when thresholds are crossed.
        """
        health, circuit = classify_budget(self.budget)
        decision = BudgetDecision(budget=self.budget, health=health, circuit_state=circuit)

        if health == BudgetHealth.EXHAUSTED:
            decision.http_status = 451
            decision.retry_after = "new-session-required"
            decision.warning = "exhausted"
        elif health == BudgetHealth.DEPLETED:
            decision.http_status = 451
            decision.retry_after = "new-session-required"
            decision.warning = "low"
            decision.force_oversight = True
        elif health == BudgetHealth.LOW:
            decision.warning = "low"
            decision.force_oversight = True
        elif health == BudgetHealth.CAUTION:
            decision.warning = "caution"

        return decision
