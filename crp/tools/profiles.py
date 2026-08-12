# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Capability execution profiles (CRP-SPEC-049 §3.1).

A leaf module (no CRP imports) so that low-level consumers like the Resource
Governor can reference the profile taxonomy without pulling in the full Tool
Capability Fabric — which would create an import cycle.
"""

from __future__ import annotations

from enum import Enum


class CapabilityProfile(str, Enum):
    """Model execution profile — bounds how many tools a frame may contain (CRP-SPEC-049 §3.1)."""

    FRONTIER = "frontier"
    CAPABLE_LOCAL = "capable-local"
    SMALL_LOCAL = "small-local"


# Max capabilities per Tool Positioning Frame, by profile (CRP-SPEC-050 §4.2).
_PROFILE_MAX_K: dict[CapabilityProfile, int] = {
    CapabilityProfile.FRONTIER: 7,
    CapabilityProfile.CAPABLE_LOCAL: 4,
    CapabilityProfile.SMALL_LOCAL: 2,
}


def max_capabilities(profile: CapabilityProfile) -> int:
    """Return the maximum number of capabilities a frame may offer for a profile."""
    return _PROFILE_MAX_K.get(profile, _PROFILE_MAX_K[CapabilityProfile.FRONTIER])
