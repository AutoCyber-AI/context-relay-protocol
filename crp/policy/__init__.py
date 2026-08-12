# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Safety Policy engine (CRP-SPEC-006).

A CSP-inspired declarative policy language for AI safety enforcement at the
transport layer.  Clients declare ``CRP-Safety-Policy`` directives; the gateway
parses, merges, and enforces them against DPE output on every response.

Public API:
    parse_policy / resolve_policy   — string → SafetyPolicy (with profiles)
    mode_policy / merge_policies     — CRP-Safety-Mode shorthand + merging
    extract_signals / enforce_policy — evaluate a policy against DPE signals
    check_inheritance                — multi-agent tightening rule
    build_report / deliver_report    — violation reporting
    bind_policy / verify_policy      — policy-nonce binding
"""

from __future__ import annotations

from .enforce import SafetySignals, enforce_policy, extract_signals
from .grammar import PolicySyntaxError, parse_policy
from .inheritance import InheritanceResult, check_inheritance, resolve_effective_policy
from .mode import MODES, merge_policies, mode_policy
from .model import (
    EnforcementAction,
    OversightMode,
    PolicyDecision,
    RepetitionLevel,
    RiskLevel,
    SafetyPolicy,
    Strategy,
    Violation,
    ViolationType,
)
from .nonce import bind_policy, generate_nonce, verify_policy
from .profiles import PROFILES, expand_profile, is_profile_policy, resolve_policy
from .report import ViolationReport, build_report, deliver_report

__all__ = [
    # model
    "SafetyPolicy",
    "PolicyDecision",
    "Violation",
    "ViolationType",
    "EnforcementAction",
    "RiskLevel",
    "RepetitionLevel",
    "OversightMode",
    "Strategy",
    # parsing
    "parse_policy",
    "resolve_policy",
    "PolicySyntaxError",
    "PROFILES",
    "expand_profile",
    "is_profile_policy",
    # mode + merge
    "mode_policy",
    "merge_policies",
    "MODES",
    # enforcement
    "SafetySignals",
    "extract_signals",
    "enforce_policy",
    # inheritance
    "check_inheritance",
    "resolve_effective_policy",
    "InheritanceResult",
    # reporting
    "ViolationReport",
    "build_report",
    "deliver_report",
    # nonce
    "generate_nonce",
    "bind_policy",
    "verify_policy",
]
