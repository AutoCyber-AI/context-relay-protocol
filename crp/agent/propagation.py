# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Multi-agent header propagation + delegation limits (CRP-SPEC-012 §3, §10.3).

Defines which CRP headers flow downstream (orchestrator → sub-agent) and
upstream (sub-agent → orchestrator), the fan-in budget merge, and the
loop-depth / delegation / DAG-node guards that prevent unbounded chains.

PRIVATE REFERENCE IMPLEMENTATION — SPEC-012 internals are not published.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from crp.headers import names as H

# CRP-SPEC-012 §3.1 — headers an orchestrator MUST/SHOULD send to a sub-agent.
DOWNSTREAM_HEADERS: tuple[str, ...] = (
    H.AGENT_SAFETY_BUDGET,
    H.SAFETY_POLICY,
    H.AGENT_SESSION_PARENT,
    H.AGENT_LOOP_DEPTH,
    H.SAFETY_MODE,
    H.COMPLIANCE_DATA_RESIDENCY,
)

# CRP-SPEC-012 §3.2 — headers a sub-agent MUST/SHOULD return to the orchestrator.
UPSTREAM_HEADERS: tuple[str, ...] = (
    H.AGENT_SAFETY_BUDGET,
    H.SAFETY_HALLUCINATION_RISK,
    H.PROVENANCE_HMAC,
    H.PROVENANCE_CHAIN_INTEGRITY,
    H.COMPLIANCE_AUDIT_TRAIL_URI,
    H.QUALITY_SCORE,
)

# CRP-SPEC-012 §3.3 — headers that MUST NOT propagate across the agent boundary.
NON_PROPAGATING_HEADERS: frozenset[str] = frozenset(
    {
        H.SESSION_TOKEN,
        H.SET_SESSION,
        H.CONTEXT_ETAG,
        H.CONTEXT_QUALITY_TIER,
    }
)

# CRP-SPEC-012 §10.3 — default chain-bounding limits.
DEFAULT_MAX_LOOP_DEPTH = 5
DEFAULT_MAX_DELEGATIONS = 5
DEFAULT_MAX_DAG_NODES = 50


@dataclass
class DelegationLimits:
    """Per-agent delegation controls (CRP-SPEC-012 §7.2)."""

    max_loop_depth: int = DEFAULT_MAX_LOOP_DEPTH
    max_delegations: int = DEFAULT_MAX_DELEGATIONS
    max_dag_nodes: int = DEFAULT_MAX_DAG_NODES
    allowed_strategies: frozenset[str] | None = None


@dataclass
class DelegationCheck:
    """Result of validating a delegation attempt against the limits."""

    allowed: bool = True
    reason: str | None = None

    @property
    def http_status(self) -> int | None:
        """Return the HTTP status."""
        return None if self.allowed else 403

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        return {} if self.allowed else {"CRP-Agent-Delegation-Rejected": self.reason or "limit-exceeded"}


def _ci_get(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return v
    return None


def build_downstream_headers(
    parent_headers: Mapping[str, str],
    *,
    parent_session_id: str,
    loop_depth: int,
) -> dict[str, str]:
    """Construct the header set an orchestrator forwards to a sub-agent (§3.1).

    Copies the propagating headers from the parent context, sets
    ``CRP-Agent-Session-Parent`` to the orchestrator session, and increments
    ``CRP-Agent-Loop-Depth``.
    """
    out: dict[str, str] = {}
    for name in DOWNSTREAM_HEADERS:
        if name in (H.AGENT_SESSION_PARENT, H.AGENT_LOOP_DEPTH):
            continue
        val = _ci_get(parent_headers, name)
        if val is not None:
            out[name] = val
    out[H.AGENT_SESSION_PARENT] = parent_session_id
    out[H.AGENT_LOOP_DEPTH] = str(loop_depth + 1)
    return out


def filter_upstream_headers(sub_agent_headers: Mapping[str, str]) -> dict[str, str]:
    """Select the headers a sub-agent surfaces back to the orchestrator (§3.2)."""
    out: dict[str, str] = {}
    for name in UPSTREAM_HEADERS:
        val = _ci_get(sub_agent_headers, name)
        if val is not None:
            out[name] = val
    return out


def check_delegation(
    limits: DelegationLimits,
    *,
    loop_depth: int,
    delegations_made: int,
    dag_nodes: int,
    strategy: str | None = None,
) -> DelegationCheck:
    """Validate a delegation against loop-depth / fan-out / DAG / strategy limits."""
    if loop_depth + 1 > limits.max_loop_depth:
        return DelegationCheck(False, f"max_loop_depth={limits.max_loop_depth} exceeded")
    if delegations_made + 1 > limits.max_delegations:
        return DelegationCheck(False, f"max_delegations={limits.max_delegations} exceeded")
    if dag_nodes + 1 > limits.max_dag_nodes:
        return DelegationCheck(False, f"max_dag_nodes={limits.max_dag_nodes} exceeded")
    if (
        strategy is not None
        and limits.allowed_strategies is not None
        and strategy not in limits.allowed_strategies
    ):
        return DelegationCheck(False, f"strategy '{strategy}' not permitted")
    return DelegationCheck(True)
