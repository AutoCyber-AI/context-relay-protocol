# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Quality-Tier-Supervised Router (SPEC-050)."""

from __future__ import annotations

from crp.qsr.escalation import ESCALATION_LADDER, run_with_escalation
from crp.qsr.harvest import RoutingExample, harvest
from crp.qsr.profiles import FLEET, CapabilityProfile, register_profile
from crp.qsr.router import LearnedRouter, RoutingTask
from crp.qsr.schema_adapt import adapt_schema

__all__ = [
    "CapabilityProfile",
    "ESCALATION_LADDER",
    "FLEET",
    "LearnedRouter",
    "RoutingExample",
    "RoutingTask",
    "adapt_schema",
    "harvest",
    "register_profile",
    "run_with_escalation",
]
