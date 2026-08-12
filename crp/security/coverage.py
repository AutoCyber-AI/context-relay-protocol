# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Coverage Map — addable rules registry and explicit out-of-scope list (SPEC-034 §11).

The Coverage Map answers two questions honestly:
  1. What risks can CRP detect?  (the capabilities)
  2. What risks can CRP NOT detect?  (the out-of-scope list)

Honesty is a feature — the Control Plane shows both lists so users have
accurate expectations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.security.coverage")


# ── Addable rules (SPEC-034 §11) ───────────────────────────────────────────


class AddableRule:
    """Metadata for a safety rule that can be registered in the Coverage Map (SPEC-034).

    Attributes:
        name: Unique rule identifier.
        description: What the rule detects and why it matters.
        default: Default setting (e.g. "on", "warn").
        allowed_values: Valid settings for this rule.
        effect: Human-readable description of the rule's effect when triggered.
    """

    def __init__(
        self,
        name: str,
        description: str,
        default: str,
        allowed_values: list[str],
        effect: str,
    ) -> None:
        """Initialise an addable rule descriptor.

        Args:
            name: Unique rule identifier.
            description: Human-readable explanation.
            default: Default setting.
            allowed_values: List of valid setting strings.
            effect: Description of the rule's effect.
        """
        self.name = name
        self.description = description
        self.default = default
        self.allowed_values = allowed_values
        self.effect = effect


# Canonical addable rules defined by SPEC-034
DEFAULT_ADDABLE_RULES: list[AddableRule] = [
    AddableRule(
        name="jailbreak_detection",
        description="Override patterns in prompts attempting to bypass safety",
        default="on",
        allowed_values=["on", "off", "warn"],
        effect="Flag or block prompt-override attempts",
    ),
    AddableRule(
        name="toxicity_classification",
        description="Harmful content detection in inputs and outputs",
        default="warn",
        allowed_values=["on", "off", "warn", "block"],
        effect="Flag, warn, or block toxic content",
    ),
    AddableRule(
        name="secrets_detection",
        description="API keys, passwords, tokens in I/O",
        default="warn",
        allowed_values=["on", "off", "warn", "block"],
        effect="Flag or block leaked secrets",
    ),
    AddableRule(
        name="copyright_detection",
        description="Verbatim copyrighted text in output",
        default="warn",
        allowed_values=["on", "off", "warn", "block"],
        effect="Flag potential copyright violations",
    ),
    AddableRule(
        name="agency_boundary",
        description="Agent overreach detection — actions beyond authorised scope",
        default="warn",
        allowed_values=["on", "off", "warn", "block"],
        effect="Flag or block out-of-scope agent actions",
    ),
    AddableRule(
        name="semantic_drift",
        description="Topic drift across continuation windows",
        default="warn",
        allowed_values=["on", "off", "warn"],
        effect="Warn when output drifts from original task topic",
    ),
]


# ── Out-of-scope list (SPEC-034 §1.2) ──────────────────────────────────────

DEFAULT_OUT_OF_SCOPE: list[str] = [
    "model_alignment",      # CRP does not change model weights or values
    "training_data_bias",   # CRP does not audit the model's training set
    "emergent_capability",  # CRP governs observable I/O, not latent capability
    "semantic_subtlety",    # technically-true-but-misleading may pass automation
]


# ── SafetyCapability — unified capability descriptor ─────────────────────────


@dataclass
class SafetyCapability:
    """One entry in the Safety Registry / Coverage Map (SPEC-033, SPEC-034).

    Attributes:
        name: Unique capability identifier.
        description: What the capability evaluates.
        spec: Specification that defines the capability (e.g. "005", "033").
        default: Factory/default value.
        current: Active value after tuning.
        allowed_range: Optional list or range of permitted values.
        effect: Human-readable effect when the capability triggers.
        addable: True if the capability comes from SPEC-034 addable rules.
    """

    name: str
    description: str
    spec: str               # e.g. "005", "006", "015"
    default: Any
    current: Any
    allowed_range: list[Any] | None = None
    effect: str = ""
    addable: bool = False   # True if this is from SPEC-034 addable rules

    def to_dict(self) -> dict[str, Any]:
        """Serialise to dict for dashboard/export.

        Returns:
            JSON-safe dict representation of this capability.
        """
        return {
            "name": self.name,
            "description": self.description,
            "spec": self.spec,
            "default": self.default,
            "current": self.current,
            "allowed_range": self.allowed_range,
            "effect": self.effect,
            "addable": self.addable,
        }


@dataclass
class SafetyCoverageMap:
    """The complete map of detectable risks + explicit out-of-scope list (SPEC-034).

    The out-of-scope list is shown in the Control Plane too — honesty is a feature.
    """

    capabilities: dict[str, SafetyCapability] = field(default_factory=dict)
    out_of_scope: list[str] = field(default_factory=lambda: list(DEFAULT_OUT_OF_SCOPE))

    def register(self, capability: SafetyCapability) -> None:
        """Add or overwrite a capability in the map.

        Args:
            capability: Capability descriptor to register.

        Returns:
            None.
        """
        self.capabilities[capability.name] = capability
        logger.debug("Registered safety capability: %s", capability.name)

    def get(self, name: str) -> SafetyCapability | None:
        """Lookup a capability by name.

        Args:
            name: Capability identifier.

        Returns:
            The matching ``SafetyCapability`` or ``None``.
        """
        return self.capabilities.get(name)

    def list_addable(self) -> list[SafetyCapability]:
        """Return only the addable rules (SPEC-034).

        Returns:
            List of capabilities where ``addable`` is True.
        """
        return [c for c in self.capabilities.values() if c.addable]

    def to_dict(self) -> dict[str, Any]:
        """Serialise for dashboard rendering or config export.

        Returns:
            Dict with ``capabilities`` and ``out_of_scope`` keys.
        """
        return {
            "capabilities": {
                name: {
                    "description": cap.description,
                    "spec": cap.spec,
                    "default": cap.default,
                    "current": cap.current,
                    "allowed_range": cap.allowed_range,
                    "effect": cap.effect,
                    "addable": cap.addable,
                }
                for name, cap in self.capabilities.items()
            },
            "out_of_scope": self.out_of_scope,
        }
