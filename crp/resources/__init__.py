# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Resource management — allocation, monitoring, model registry, cost model."""

from crp.resources.adaptive_allocator import (
    AdaptiveAllocator,
    EnvelopeProfile,
    ExtractionProfile,
    PromptEfficiency,
    WindowOverheadRecord,
    detect_hardware,
)
from crp.resources.cost_model import (
    KNOWN_PRICING,
    BudgetWarning,
    BudgetWarningLevel,
    CostModel,
    OverheadBudget,
    OverheadDecision,
    ProviderPricing,
    WindowCost,
)
from crp.resources.overhead_manager import (
    PROTECTED_INTELLIGENCE,
    SHEDDING_CASCADE,
    OverheadBudgetManager,
)
from crp.resources.governor import (
    DeviceProfile,
    DeviceTier,
    ResourceGovernor,
    ResourcePlan,
)
from crp.resources.resource_manager import (
    MODEL_ESTIMATES,
    ResourceManager,
    ResourceSnapshot,
)

__all__ = [
    "AdaptiveAllocator",
    "DeviceProfile",
    "DeviceTier",
    "ResourceGovernor",
    "ResourcePlan",
    "CostModel",
    "EnvelopeProfile",
    "ExtractionProfile",
    "MODEL_ESTIMATES",
    "OverheadBudget",
    "OverheadDecision",
    "OverheadBudgetManager",
    "ProviderPricing",
    "ResourceManager",
    "ResourceSnapshot",
    "WindowCost",
    "WindowOverheadRecord",
    "BudgetWarning",
    "BudgetWarningLevel",
    "KNOWN_PRICING",
    "SHEDDING_CASCADE",
    "detect_hardware",
]
