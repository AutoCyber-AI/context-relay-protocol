# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP multi-agent safety (CRP-SPEC-012).

Session-scoped Safety Budget + circuit breaker, cross-agent header propagation
and delegation limits, cross-agent provenance linking, and the human-oversight
token flow.

PRIVATE REFERENCE IMPLEMENTATION — SPEC-012 internals are NOT published.  This
package is part of the closed-source ``crp`` reference engine only.

Public API:
    AgentSafetyBudget / BudgetDecision / classify_budget — budget + circuit breaker
    DelegationLimits / check_delegation                  — chain-bounding guards
    build_downstream_headers / filter_upstream_headers   — header propagation
    link_sub_agent_hmac / fan_in_hmac / SubAgentResult   — cross-agent provenance
    issue_oversight_token / verify_oversight_token        — oversight token flow
"""

from __future__ import annotations

from .budget import (
    DECREMENT_RANGES,
    DEFAULT_DECREMENTS,
    INITIAL_BUDGET,
    AgentSafetyBudget,
    BudgetDecision,
    BudgetHealth,
    CircuitState,
    classify_budget,
)
from .chain import (
    FanInQualityResult,
    SubAgentResult,
    aggregate_sub_agent_quality,
    fan_in_hmac,
    link_sub_agent_hmac,
    verify_sub_agent_link,
)
from .oversight import (
    OversightApproval,
    issue_oversight_token,
    now_iso,
    verify_oversight_token,
)
from .autonomy import (
    AutonomyAction,
    AutonomyDecision,
    AutonomyGovernor,
    AutonomyMetrics,
    AutonomyTier,
)
from .runtime_governance import (
    GovernedAction,
    GovernedActionResult,
    RuntimeGovernorConfig,
)
from .propagation import (
    DOWNSTREAM_HEADERS,
    NON_PROPAGATING_HEADERS,
    UPSTREAM_HEADERS,
    DelegationCheck,
    DelegationLimits,
    build_downstream_headers,
    check_delegation,
    filter_upstream_headers,
)

__all__ = [
    # budget + circuit breaker
    "AgentSafetyBudget",
    "BudgetDecision",
    "BudgetHealth",
    "CircuitState",
    "classify_budget",
    "INITIAL_BUDGET",
    "DEFAULT_DECREMENTS",
    "DECREMENT_RANGES",
    # propagation + limits
    "DOWNSTREAM_HEADERS",
    "UPSTREAM_HEADERS",
    "NON_PROPAGATING_HEADERS",
    "DelegationLimits",
    "DelegationCheck",
    "build_downstream_headers",
    "filter_upstream_headers",
    "check_delegation",
    # cross-agent provenance
    "SubAgentResult",
    "FanInQualityResult",
    "aggregate_sub_agent_quality",
    "link_sub_agent_hmac",
    "verify_sub_agent_link",
    "fan_in_hmac",
    # oversight
    "OversightApproval",
    "issue_oversight_token",
    "verify_oversight_token",
    "now_iso",
    # autonomy (SPEC-026)
    "AutonomyAction",
    "AutonomyDecision",
    "AutonomyGovernor",
    "AutonomyMetrics",
    "AutonomyTier",
    # runtime governance bridge (Wave 2)
    "GovernedAction",
    "GovernedActionResult",
    "RuntimeGovernorConfig",
]
