# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Manifest — the single config that drives code + dashboard (SPEC-033 §2).

The Manifest is the one source of truth that both the Safety Control Plane
and any dashboard UI read and write. Change it in code and the dashboard
reflects it; change it in the dashboard and the file updates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.security.safety_manifest")


# ── Default safety profiles (SPEC-033 §2.3) ────────────────────────────────


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "balanced": {
        "hallucination_halt": "CRITICAL",
        "hallucination_warn": "HIGH",
        "require_grounding": 0.70,
        "block_fabrication": True,
        "block_distortion": True,
        "pii_handling": "flag",
        "injection_shield": True,
        "safety_budget_start": 1.0,
    },
    "strict": {
        "hallucination_halt": "HIGH",
        "hallucination_warn": "MEDIUM",
        "require_grounding": 0.85,
        "block_fabrication": True,
        "block_distortion": True,
        "pii_handling": "block",
        "injection_shield": True,
        "safety_budget_start": 1.0,
    },
    "medical": {
        "hallucination_halt": "MEDIUM",
        "hallucination_warn": "LOW",
        "require_grounding": 0.90,
        "block_fabrication": True,
        "block_distortion": True,
        "pii_handling": "block",
        "injection_shield": True,
        "safety_budget_start": 0.8,
    },
    "financial": {
        "hallucination_halt": "HIGH",
        "hallucination_warn": "MEDIUM",
        "require_grounding": 0.85,
        "block_fabrication": True,
        "block_distortion": True,
        "pii_handling": "redact",
        "injection_shield": True,
        "safety_budget_start": 0.9,
    },
}


# ── SafetyManifest dataclass ───────────────────────────────────────────────


@dataclass
class SafetyManifest:
    """The one config that drives all CRP safety — code and dashboard (SPEC-033 §2).

    Attributes:
        profile: Named profile ("balanced", "strict", "medical", "financial")
                 or "custom" when any field deviates from a named profile.
        settings: Dict of capability-name → current value.
        checkpoints: List of checkpoint declarations (inline HITL rules).
        custom_rules: List of paths to custom rule modules.
    """

    profile: str = "balanced"
    settings: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    custom_rules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Merge profile defaults with any explicitly provided settings
        base = DEFAULT_PROFILES.get(self.profile, DEFAULT_PROFILES["balanced"]).copy()
        base.update(self.settings)
        self.settings = base
        # Detect if we have deviated from the named profile
        if self.profile in DEFAULT_PROFILES and self.settings != DEFAULT_PROFILES[self.profile]:
            # Only mark custom if the user explicitly set something different
            pass  # Keep named profile unless explicitly changed

    # ------------------------------------------------------------------
    # Get / set
    # ------------------------------------------------------------------

    def get(self, name: str, default: Any = None) -> Any:
        """Read a setting by name.

        Args:
            name: Setting key.
            default: Value returned if the setting is absent.

        Returns:
            Current setting value or ``default``.
        """
        return self.settings.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Write a setting — marks profile as custom if it deviates.

        Args:
            name: Setting key.
            value: New value to store.

        Returns:
            None. Updates ``profile`` to ``"custom"`` when the value differs
            from the named profile defaults.
        """
        self.settings[name] = value
        if self.profile in DEFAULT_PROFILES:
            if self.settings != DEFAULT_PROFILES[self.profile]:
                self.profile = "custom"
        logger.debug("SafetyManifest setting %s = %s (profile=%s)", name, value, self.profile)

    # ------------------------------------------------------------------
    # Hash for header emission (SPEC-037)
    # ------------------------------------------------------------------

    def compute_hash(self) -> str:
        """Return a deterministic hash of this manifest for CRP-Config-Hash.

        Returns:
            Hex-encoded BLAKE2b digest of the canonical settings JSON.

        Raises:
            ValueError: If the settings cannot be serialised (rare).
        """
        canonical = json.dumps(self.settings, sort_keys=True, separators=(",", ":"))
        return hashlib.blake2b(canonical.encode(), digest_size=16).hexdigest()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the manifest to a JSON-safe dict.

        Returns:
            Dict with ``profile``, ``settings``, ``checkpoints``, and ``custom_rules``.
        """
        return {
            "profile": self.profile,
            "settings": self.settings,
            "checkpoints": self.checkpoints,
            "custom_rules": self.custom_rules,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyManifest:
        """Restore a ``SafetyManifest`` from a serialised dict.

        Args:
            data: Dict produced by ``to_dict``.

        Returns:
            Reconstructed ``SafetyManifest`` instance.
        """
        return cls(
            profile=data.get("profile", "balanced"),
            settings=data.get("settings", {}),
            checkpoints=data.get("checkpoints", []),
            custom_rules=data.get("custom_rules", []),
        )
