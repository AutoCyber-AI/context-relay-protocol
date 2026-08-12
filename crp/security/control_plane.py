# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Control Plane (SCP) — single place for all CRP safety (SPEC-033).

The SCP unifies existing scattered safety mechanisms under one catalogue:
  - Registry: every capability, its default, its current setting, its effect
  - Manifest: the one config that drives code + dashboard
  - Checkpoints: inline human-in-the-loop declarations
  - Coverage Map: what CRP detects AND what it explicitly does not detect

Usage::

    from crp.security.control_plane import SafetyControlPlane

    scp = SafetyControlPlane()
    scp.show()                       # human-readable printout
    capability = scp.get_capability("require_grounding")
    scp.tune("require_grounding", 0.85)
    scp.register_rule(my_custom_rule)
    surface = scp.get_surface_map()  # for dashboard UI rendering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crp.security.checkpoint import Checkpoint, CheckpointResolution
from crp.security.coverage import (
    DEFAULT_ADDABLE_RULES,
    SafetyCapability,
    SafetyCoverageMap,
)
from crp.security.safety_manifest import SafetyManifest

logger = logging.getLogger("crp.security.control_plane")


# ── Built-in registry entries (SPEC-033 §1.1) ──────────────────────────────


_DEFAULT_REGISTRY_ENTRIES: list[SafetyCapability] = [
    SafetyCapability(
        name="hallucination_risk_scoring",
        description="Flags unsupported/invented output, 4 levels",
        spec="005",
        default="warn HIGH, halt CRITICAL",
        current="warn HIGH, halt CRITICAL",
        effect="Risk-score output and halt on CRITICAL",
    ),
    SafetyCapability(
        name="fabrication_detection",
        description="Invented entities, fake citations, false specifics",
        spec="005 §3a",
        default=True,
        current=True,
        effect="Block invented specifics",
    ),
    SafetyCapability(
        name="distortion_detection",
        description="Changed numbers, flipped negations, altered facts",
        spec="005 §3b",
        default=True,
        current=True,
        effect="Block altered source facts",
    ),
    SafetyCapability(
        name="grounding_verification",
        description="% of output supported by provided context",
        spec="005",
        default=0.70,
        current=0.70,
        allowed_range=[0.0, 1.0],
        effect="Require minimum grounding score",
    ),
    SafetyCapability(
        name="contradiction_detection",
        description="Self-contradiction within & across windows",
        spec="005 §6",
        default=True,
        current=True,
        effect="Flag contradictions",
    ),
    SafetyCapability(
        name="repetition_detection",
        description="Looping, recycled content",
        spec="005 §7",
        default="warn",
        current="warn",
        effect="Warn on repetitive output",
    ),
    SafetyCapability(
        name="pii_detection",
        description="GDPR personal data in inputs/outputs",
        spec="005 §11",
        default="flag",
        current="flag",
        allowed_range=["flag", "redact", "block"],
        effect="Handle PII per policy",
    ),
    SafetyCapability(
        name="prompt_injection_shield",
        description="Override/exfiltration patterns in inputs",
        spec="015",
        default=True,
        current=True,
        effect="Block prompt-injection patterns",
    ),
    SafetyCapability(
        name="safety_budget_multiagent",
        description="Cumulative risk across agent chains → circuit breaker",
        spec="012",
        default=1.0,
        current=1.0,
        allowed_range=[0.0, 1.0],
        effect="Circuit-break on budget exhaustion",
    ),
    SafetyCapability(
        name="compliance_classification",
        description="EU AI Act / GDPR / ISO / NIST per call",
        spec="010",
        default="classify",
        current="classify",
        effect="Classify compliance domain",
    ),
    SafetyCapability(
        name="tamper_evident_audit",
        description="HMAC chain — proves what happened, detects edits",
        spec="011",
        default=True,
        current=True,
        effect="Sign every window/operation",
    ),
    SafetyCapability(
        name="http_451_halt",
        description="Hard stop — unsafe output never reaches caller",
        spec="002",
        default="on CRITICAL",
        current="on CRITICAL",
        effect="Return HTTP 451 on CRITICAL risk",
    ),
    SafetyCapability(
        name="human_oversight",
        description="Route risky output to a human",
        spec="006",
        default="manual",
        current="manual",
        effect="Require human approval",
    ),
]


# ── Custom rule wrapper ────────────────────────────────────────────────────


@dataclass
class CustomSafetyRule:
    """A user-defined safety rule registered as a first-class citizen (SPEC-033).

    Attributes:
        name: Unique rule identifier.
        check_fn: Callable that performs the safety check. Type is kept as ``Any``
            to avoid heavy import dependencies in the control plane module.
        description: Human-readable explanation of what the rule detects.
        default: Default value for the rule when registered.
    """

    name: str
    check_fn: Any  # Callable[[Any], Any] — deferred typing to avoid heavy imports
    description: str = ""
    default: Any = None


# ── SafetyControlPlane ─────────────────────────────────────────────────────


@dataclass
class SafetyControlPlane:
    """Single place from which all CRP safety is seen, tuned, and extended (SPEC-033).

    Attributes:
        registry: Dict of capability-name → SafetyCapability.
        manifest: The SafetyManifest that drives settings.
        coverage: The SafetyCoverageMap (capabilities + out-of-scope).
        checkpoints: Active checkpoint instances awaiting resolution.
    """

    registry: dict[str, SafetyCapability] = field(default_factory=dict)
    manifest: SafetyManifest = field(default_factory=SafetyManifest)
    coverage: SafetyCoverageMap = field(default_factory=SafetyCoverageMap)
    _checkpoints: dict[str, Checkpoint] = field(default_factory=dict, repr=False)
    _custom_rules: list[CustomSafetyRule] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        # Populate registry with built-in capabilities
        for cap in _DEFAULT_REGISTRY_ENTRIES:
            self.registry[cap.name] = cap
        # Populate coverage map with addable rules
        for rule in DEFAULT_ADDABLE_RULES:
            cap = SafetyCapability(
                name=rule.name,
                description=rule.description,
                spec="034",
                default=rule.default,
                current=rule.default,
                allowed_range=rule.allowed_values,
                effect=rule.effect,
                addable=True,
            )
            self.coverage.register(cap)
            # Also mirror addable rules into the main registry
            self.registry[cap.name] = cap
        logger.debug("SafetyControlPlane initialised with %d capabilities", len(self.registry))

    # ------------------------------------------------------------------
    # Registry operations
    # ------------------------------------------------------------------

    def get_capability(self, name: str) -> SafetyCapability | None:
        """Retrieve a capability from the registry.

        Args:
            name: Capability identifier.

        Returns:
            The matching ``SafetyCapability`` or ``None`` if not registered.
        """
        return self.registry.get(name)

    def list_capabilities(self) -> list[SafetyCapability]:
        """Return all registered capabilities.

        Returns:
            List of every built-in, addable, and custom capability in the registry.
        """
        return list(self.registry.values())

    def tune(self, name: str, value: Any) -> None:
        """Change the current value of a capability and sync to Manifest.

        Args:
            name: Capability identifier.
            value: New current value. Should normally be within ``allowed_range``.

        Returns:
            None. Logs a warning if the capability is unknown.
        """
        cap = self.registry.get(name)
        if cap is None:
            logger.warning("Tune requested for unknown capability: %s", name)
            return
        cap.current = value
        self.manifest.set(name, value)
        logger.info("Tuned %s → %s", name, value)

    def register_rule(self, rule: CustomSafetyRule) -> None:
        """Register a custom safety rule as a first-class citizen.

        Args:
            rule: Custom rule definition including name, check function, and default.

        Returns:
            None. The rule is mirrored into the registry and coverage map.
        """
        self._custom_rules.append(rule)
        cap = SafetyCapability(
            name=rule.name,
            description=rule.description,
            spec="033-custom",
            default=rule.default,
            current=rule.default,
            effect="Custom user-defined rule",
        )
        self.registry[cap.name] = cap
        logger.info("Registered custom safety rule: %s", rule.name)

    # ------------------------------------------------------------------
    # Checkpoint operations
    # ------------------------------------------------------------------

    def create_checkpoint(
        self,
        trigger: str = "always",
        timeout: int = 300,
        on_timeout: str = "escalate",
        on_reject: str = "fallback",
        context: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create and track a new human-in-the-loop checkpoint.

        Args:
            trigger: Condition that fires the checkpoint. One of the
                ``CheckpointTrigger`` values or a custom string.
            timeout: Seconds to wait for human review before auto-resolution.
            on_timeout: Action taken when the checkpoint times out.
            on_reject: Action taken when the human reviewer rejects.
            context: Arbitrary dict passed to the reviewer UI/webhook.

        Returns:
            The created ``Checkpoint`` instance, tracked by ID internally.
        """
        from crp.security.checkpoint import (
            CheckpointRejectAction,
            CheckpointTimeoutAction,
            CheckpointTrigger,
        )

        _trigger = (
            CheckpointTrigger(trigger)
            if trigger in {t.value for t in CheckpointTrigger}
            else CheckpointTrigger.CUSTOM_RULE
        )
        cp = Checkpoint(
            trigger=_trigger,
            timeout=timeout,
            on_timeout=CheckpointTimeoutAction(on_timeout),
            on_reject=CheckpointRejectAction(on_reject),
            context=context or {},
        )
        self._checkpoints[cp.checkpoint_id] = cp
        logger.info("Checkpoint created: %s (trigger=%s)", cp.checkpoint_id, trigger)
        return cp

    def resolve_checkpoint(self, checkpoint_id: str, resolution: CheckpointResolution) -> None:
        """Resolve a checkpoint by ID (called by reviewer or webhook).

        Args:
            checkpoint_id: UUID of the checkpoint returned by ``create_checkpoint``.
            resolution: Human reviewer's decision and optional edited output.

        Returns:
            None. Logs an error if the checkpoint ID is unknown.
        """
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            logger.error("Resolve requested for unknown checkpoint: %s", checkpoint_id)
            return
        cp.resolve(resolution)

    # ------------------------------------------------------------------
    # Surface map (for dashboard UI rendering)
    # ------------------------------------------------------------------

    def get_surface_map(self) -> dict[str, Any]:
        """Return the complete safety surface as a dict — for UI dashboards.

        Returns:
            Dict with ``registry``, ``manifest``, ``coverage``, and
            ``active_checkpoints`` keys.
        """
        return {
            "registry": {name: cap.to_dict() for name, cap in self.registry.items()},
            "manifest": self.manifest.to_dict(),
            "coverage": self.coverage.to_dict(),
            "active_checkpoints": len(self._checkpoints),
        }

    # ------------------------------------------------------------------
    # Human-readable output
    # ------------------------------------------------------------------

    def show(self) -> str:
        """Return a human-readable printout of the entire safety surface.

        Returns:
            Multi-line string listing every capability's current/default values,
            allowed ranges, effects, and the explicit out-of-scope list.
        """
        lines = [
            "CRP SAFETY CONTROL PLANE — current settings",
            "════════════════════════════════════════════════════════════",
        ]
        for name, cap in sorted(self.registry.items()):
            allowed = f" [range {cap.allowed_range}]" if cap.allowed_range else ""
            lines.append(
                f"  {name:24s} {str(cap.current):12s} [default: {cap.default}]{allowed}"
                f"  what: {cap.effect}"
            )
        lines.append("")
        lines.append("OUT OF SCOPE (honest capability boundary)")
        lines.append("────────────────────────────────────────────────────────────")
        for item in self.coverage.out_of_scope:
            lines.append(f"  • {item}")
        return "\n".join(lines)


# Convenience alias for the module-level registry
default_control_plane: SafetyControlPlane | None = None


def get_default_control_plane() -> SafetyControlPlane:
    """Return the singleton default control plane (lazy initialised).

    Returns:
        The module-level default ``SafetyControlPlane`` instance, creating it
        on first call.
    """
    global default_control_plane
    if default_control_plane is None:
        default_control_plane = SafetyControlPlane()
    return default_control_plane
