# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Resource Governor — protocol-layer "slow and steady over fast and failing" (CRP v5).

The Governor is CRP's orchestration-layer answer to local-LLM resource pressure. It
does NOT do quantization / KV compression / model offloading — those belong to the
inference engine (llama.cpp / vLLM / llama-swap). It governs the *protocol* levers that
keep utilisation under a target on a constrained device:

  - **capability profile** (frame size: small-local 1–2 tools … frontier 5–7),
  - **operation cap** (loop guard),
  - **tool concurrency** (serialised on constrained devices — the steadiness lever).

Prime directive: on a constrained device, run **slow and steady** — never exceed the
target utilisation, accepting slower wall-clock time rather than risking OOM/overheat.
When the device is unknown, the Governor defaults to the *safe* (constrained) plan.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum

from crp.tools.profiles import CapabilityProfile

logger = logging.getLogger("crp.resources.governor")


class DeviceTier(str, Enum):
    """Coarse device class used to pick a resource plan."""

    CONSTRAINED = "constrained"
    STANDARD = "standard"
    GENEROUS = "generous"


# Profile ordering, smallest → largest, so the Governor can CAP without upsizing.
_PROFILE_ORDER: list[CapabilityProfile] = [
    CapabilityProfile.SMALL_LOCAL,
    CapabilityProfile.CAPABLE_LOCAL,
    CapabilityProfile.FRONTIER,
]


def _smaller_of(a: CapabilityProfile, b: CapabilityProfile) -> CapabilityProfile:
    return a if _PROFILE_ORDER.index(a) <= _PROFILE_ORDER.index(b) else b


def _detect_ram_gb() -> float:
    """Best-effort total RAM in GB. Returns 0.0 (unknown) if psutil is unavailable."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return 0.0
    try:
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:  # noqa: BLE001
        return 0.0


@dataclass
class DeviceProfile:
    """The detected (or supplied) device characteristics."""

    tier: DeviceTier
    cpu_count: int
    ram_gb: float
    target_utilisation: float = 0.40
    detected: bool = True


@dataclass
class ResourcePlan:
    """The Governor's plan for a run — the protocol levers, not engine settings."""

    profile: CapabilityProfile
    max_operations: int
    tool_concurrency: int  # 1 = serialised (slow & steady)
    bounded_window: bool = True  # always true — the core CRP invariant
    reason: str = ""


def _classify(cpu_count: int, ram_gb: float) -> DeviceTier:
    # Unknown RAM → treat as constrained (safe default: slow and steady).
    if ram_gb <= 0.0:
        return DeviceTier.CONSTRAINED
    if ram_gb < 8 or cpu_count < 4:
        return DeviceTier.CONSTRAINED
    if ram_gb < 16 or cpu_count < 8:
        return DeviceTier.STANDARD
    return DeviceTier.GENEROUS


# Tier → (profile ceiling, op cap, concurrency).
_TIER_PLAN: dict[DeviceTier, tuple[CapabilityProfile, int, int]] = {
    DeviceTier.CONSTRAINED: (CapabilityProfile.SMALL_LOCAL, 6, 1),
    DeviceTier.STANDARD: (CapabilityProfile.CAPABLE_LOCAL, 10, 1),
    DeviceTier.GENEROUS: (CapabilityProfile.FRONTIER, 12, 2),
}


class ResourceGovernor:
    """Picks a resource plan that holds utilisation under the target."""

    def __init__(self, target_utilisation: float = 0.40, device: DeviceProfile | None = None) -> None:
        self.target_utilisation = target_utilisation
        self.device = device or self.detect_device(target_utilisation)

    @staticmethod
    def detect_device(target_utilisation: float = 0.40) -> DeviceProfile:
        """Detect the device tier from CPU/RAM (psutil optional; safe default constrained)."""
        cpu = os.cpu_count() or 2
        ram = _detect_ram_gb()
        tier = _classify(cpu, ram)
        return DeviceProfile(
            tier=tier, cpu_count=cpu, ram_gb=ram,
            target_utilisation=target_utilisation, detected=(ram > 0.0),
        )

    def plan(self, requested_profile: CapabilityProfile | None = None) -> ResourcePlan:
        """Return a plan for the current device, capping any requested profile.

        The Governor never *upsizes* beyond the device tier's ceiling. If the caller
        requests a smaller (more frugal) profile, that is honoured — frugality is always
        allowed; exceeding the tier ceiling is not.
        """
        ceiling, op_cap, concurrency = _TIER_PLAN[self.device.tier]
        profile = ceiling if requested_profile is None else _smaller_of(requested_profile, ceiling)
        capped = profile is not requested_profile and requested_profile is not None
        detail = "detected" if self.device.detected else "assumed (psutil unavailable)"
        reason = (
            f"slow-and-steady: tier={self.device.tier.value} ({detail}, "
            f"cpu={self.device.cpu_count}, ram={self.device.ram_gb:.0f}GB, "
            f"target<={self.target_utilisation:.0%}) → profile={profile.value}, "
            f"ops<={op_cap}, concurrency={concurrency}"
            + (f"; capped from {requested_profile.value}" if capped else "")
        )
        logger.debug("ResourceGovernor plan: %s", reason)
        return ResourcePlan(
            profile=profile,
            max_operations=op_cap,
            tool_concurrency=concurrency,
            bounded_window=True,
            reason=reason,
        )
