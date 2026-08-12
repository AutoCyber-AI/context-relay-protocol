# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""First-class policy builder for ``crp.Agent`` (CRP-SPEC-059 §4).

``Policy`` is the ergonomic surface; it compiles into the TCF's
``PolicyContext`` and optional orchestrator safety overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.tools.capability_fabric import PolicyContext
from crp.tools.descriptor import SafetyClass


@dataclass
class Policy:
    """Declarative safety/policy constraints for an agent run."""

    blocked_safety_classes: set[SafetyClass] = field(default_factory=set)
    data_residency: str = ""
    policy_domains: set[str] = field(default_factory=set)
    allowlist: set[str] | None = None
    blocklist: set[str] = field(default_factory=set)
    authorised_scope: set[str] = field(default_factory=set)
    approved_sinks: set[str] = field(default_factory=set)
    require_grounding: float = 0.0
    halt_on_injection: bool = False
    halt_on_pii: bool = False
    profile_name: str = "balanced"
    clarification_threshold: float = 0.4

    @classmethod
    def balanced(cls) -> Policy:
        """Balanced policy: warn on HIGH, halt on CRITICAL."""
        return cls(profile_name="balanced")

    @classmethod
    def strict(cls) -> Policy:
        """Strict policy: halt on HIGH, block ungrounded output, block fabrications."""
        return cls(
            profile_name="strict",
            require_grounding=0.8,
            halt_on_injection=True,
            halt_on_pii=True,
        )

    @classmethod
    def permissive(cls) -> Policy:
        """Permissive policy: halt only on CRITICAL."""
        return cls(profile_name="permissive")

    @classmethod
    def grounded(cls, threshold: float = 0.6) -> Policy:
        """Policy requiring the given grounding confidence threshold."""
        return cls(require_grounding=threshold)

    def block(self, *capability_ids: str) -> Policy:
        """Add capability ids to the blocklist."""
        self.blocklist.update(capability_ids)
        return self

    def allow_only(self, *capability_ids: str) -> Policy:
        """Restrict selection to only these capability ids."""
        self.allowlist = set(capability_ids)
        return self

    def domain(self, *domains: str) -> Policy:
        """Require selected capabilities to declare at least one of these domains."""
        self.policy_domains.update(domains)
        return self

    def residency(self, region: str) -> Policy:
        """Require capabilities to match this data residency region."""
        self.data_residency = region
        return self

    def scope(self, *targets: str) -> Policy:
        """Restrict invocation targets to this authorised scope (SPEC-050 §3.4)."""
        self.authorised_scope.update(targets)
        return self

    def approve_sinks(self, *sinks: str) -> Policy:
        """Approve destinations that invocations carrying data labels may target."""
        self.approved_sinks.update(sinks)
        return self

    def safety(self, *classes: SafetyClass) -> Policy:
        """Block capabilities with these safety classes."""
        self.blocked_safety_classes.update(classes)
        return self

    def clarify(self, threshold: float) -> Policy:
        """Set the ambiguity threshold at which the agent asks rather than guesses."""
        self.clarification_threshold = threshold
        return self

    def to_policy_context(self) -> PolicyContext:
        """Compile this ergonomic policy into a TCF pre-filter."""
        return PolicyContext(
            blocked_safety_classes=set(self.blocked_safety_classes),
            data_residency=self.data_residency,
            policy_domains=set(self.policy_domains),
            allowlist=self.allowlist,
            blocklist=set(self.blocklist),
            authorised_scope=set(self.authorised_scope),
            approved_sinks=set(self.approved_sinks),
        )

    def to_safety_overrides(self) -> dict[str, Any]:
        """Return orchestrator/SDK safety overrides derived from this policy."""
        return {
            "safety.profile": self.profile_name,
            "safety.require_grounding": str(self.require_grounding),
            "safety.halt_on_injection": str(self.halt_on_injection),
            "safety.halt_on_pii": str(self.halt_on_pii),
        }
