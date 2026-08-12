# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Onboarding overlay + feature-activation cascade (CRP-SPEC-017 §4, §5).

Two independent UX layers on top of mode detection:

1. **Onboarding overlay** — a time-based (14-day) overlay that emits
   ``CRP-Onboarding-*`` headers and a constantly-updated "next action" signal.
2. **Feature cascade** — the set of feature groups that become active as the
   tenant's CKF fact count crosses milestones, emitted via
   ``CRP-Activation-Features`` and ``CRP-Activation-Status``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mode import ActivationMode

# CRP-SPEC-017 §4.1 — onboarding window.
ONBOARDING_DAYS = 14

# CRP-SPEC-017 §5.1 — feature-activation milestones (fact count → feature).
_FACT_FEATURES: tuple[tuple[int, str], ...] = (
    (1, "attribution"),
    (50, "fidelity"),
    (50, "community-routing"),
    (100, "quality-tier-b"),
    (500, "quality-tier-a"),
    (1000, "quality-tier-s"),
)

# Always-on feature groups (CRP-SPEC-017 §5.2).
_ALWAYS_ON: tuple[str, ...] = ("safety", "audit", "policy", "classification")


@dataclass
class TenantState:
    """Inputs used to compute onboarding + activation headers."""

    fact_count: int = 0
    community_count: int = 0
    days_since_signup: int = 0
    ai_system_registered: bool = False
    documents_ingested: bool = False
    safety_policy_configured: bool = False
    visited_comply: bool = False
    call_count: int = 0
    window_number: int = 1


def next_action(state: TenantState) -> str | None:
    """Determine the most useful onboarding next-action (CRP-SPEC-017 §4.3)."""
    if not state.ai_system_registered:
        return "register-ai-system"
    if not state.documents_ingested:
        return "ingest-documents"
    if not state.safety_policy_configured:
        return "configure-safety-policy"
    if state.call_count > 0 and not state.visited_comply:
        return "view-comply-dashboard"
    if state.call_count >= 100:
        return "consider-upgrade-pro"
    return None


def active_features(state: TenantState) -> list[str]:
    """Compute the active feature-group list (CRP-SPEC-017 §5.2)."""
    features = list(_ALWAYS_ON)
    for threshold, feature in _FACT_FEATURES:
        if state.fact_count >= threshold:
            # community-routing also requires community detection to have run.
            if feature == "community-routing" and state.community_count < 1:
                continue
            if feature not in features:
                features.append(feature)
    if state.window_number >= 2 and "cross-window-coherence" not in features:
        features.append("cross-window-coherence")
    return features


def onboarding_hint(mode: ActivationMode) -> str | None:
    """The mode-appropriate ``CRP-Onboarding-Hint`` value (CRP-SPEC-017 §2)."""
    if mode == ActivationMode.ZERO_CKF:
        return "ingest-documents-for-context-grounding"
    if mode == ActivationMode.PARTIAL_CKF:
        return "ingest-more-documents-for-quality-S-A"
    return None  # Full-CKF emits no hint.


def activation_status(mode: ActivationMode, fact_count: int) -> str:
    """The ``CRP-Activation-Status`` value for the mode (CRP-SPEC-017 §2)."""
    if mode == ActivationMode.ZERO_CKF:
        return "safety-active; context-inactive"
    if mode == ActivationMode.PARTIAL_CKF:
        return f"safety-active; context-emerging; facts={fact_count}"
    return "full-protocol-active"


@dataclass
class OnboardingHeaders:
    """Computed onboarding + activation header bundle."""

    headers: dict[str, str]


def build_activation_headers(state: TenantState, mode: ActivationMode) -> dict[str, str]:
    """Build the full ``CRP-Activation-*`` / ``CRP-Onboarding-*`` header set.

    Combines mode status, the feature cascade, the mode-appropriate hint, and
    the time-based onboarding overlay (only while within the 14-day window).
    """
    out: dict[str, str] = {
        "CRP-Activation-Status": activation_status(mode, state.fact_count),
        "CRP-Activation-Features": ",".join(active_features(state)),
    }

    hint = onboarding_hint(mode)
    if hint:
        out["CRP-Onboarding-Hint"] = hint

    # Time-based onboarding overlay (independent of CKF state).
    if state.days_since_signup < ONBOARDING_DAYS:
        out["CRP-Onboarding-Active"] = "true"
        out["CRP-Onboarding-Days-Remaining"] = str(ONBOARDING_DAYS - state.days_since_signup)
        action = next_action(state)
        if action:
            out["CRP-Onboarding-Next-Action"] = action

    return out
