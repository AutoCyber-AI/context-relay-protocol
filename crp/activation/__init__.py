# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP progressive activation & Zero-CKF mode (CRP-SPEC-017).

Graceful degradation for an empty or sparse Contextual Knowledge Fabric:
operating-mode detection (Zero/Partial/Full-CKF) with sticky transitions,
per-call coverage adaptation, the time-based onboarding overlay + feature
cascade, Zero-CKF Safety Policy auto-adjustment, and the DPE stage plan.

Public API:
    ActivationMode / detect_mode / ModeState        — mode detection + stickiness
    assess_coverage / apply_tier_cap                — per-call coverage
    TenantState / build_activation_headers          — onboarding + activation headers
    adjust_for_zero_ckf / AdjustedPolicy            — Zero-CKF policy adjustment
    stage_plan_for / StagePlan                      — DPE stage selection
"""

from __future__ import annotations

from .mode import (
    COVERAGE_RELEVANCE_FLOOR,
    FULL_MIN_FACTS,
    PARTIAL_MIN_FACTS,
    ActivationMode,
    CoverageResult,
    ModeState,
    ModeTransition,
    apply_tier_cap,
    assess_coverage,
    detect_mode,
)
from .onboarding import (
    ONBOARDING_DAYS,
    TenantState,
    activation_status,
    active_features,
    build_activation_headers,
    next_action,
    onboarding_hint,
)
from .policy_adjust import AdjustedPolicy, PolicyAdjustment, adjust_for_zero_ckf
from .stages import StageMode, StagePlan, stage_plan_for, zero_ckf_stage_plan

__all__ = [
    # mode
    "ActivationMode",
    "detect_mode",
    "ModeState",
    "ModeTransition",
    "CoverageResult",
    "assess_coverage",
    "apply_tier_cap",
    "COVERAGE_RELEVANCE_FLOOR",
    "PARTIAL_MIN_FACTS",
    "FULL_MIN_FACTS",
    # onboarding + activation
    "TenantState",
    "build_activation_headers",
    "next_action",
    "active_features",
    "onboarding_hint",
    "activation_status",
    "ONBOARDING_DAYS",
    # policy adjustment
    "adjust_for_zero_ckf",
    "AdjustedPolicy",
    "PolicyAdjustment",
    # stages
    "stage_plan_for",
    "zero_ckf_stage_plan",
    "StagePlan",
    "StageMode",
]
