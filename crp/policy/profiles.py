# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Industry-specific policy profiles (CRP-SPEC-006 §6).

Named profiles expand to full directive strings.  A policy value may be a bare
profile (``profile=medical``) or a profile plus additional directives
(``profile=medical; report-uri https://hospital.example/audit``).
"""

from __future__ import annotations

from .grammar import PolicySyntaxError, parse_policy
from .model import SafetyPolicy

# CRP-SPEC-006 §6.1 — canonical profile expansions.
PROFILES: dict[str, str] = {
    "medical": (
        "default-src context; halt-on HIGH; require-grounding 0.90; "
        "require-entailment 0.85; block-ungrounded; block-pii; block-fabrication; "
        "oversight human-review; require-flow 0.70; require-completeness 0.90; "
        "report-uri https://comply.crprotocol.io/reports"
    ),
    "financial": (
        "default-src context parametric; halt-on CRITICAL; warn-on HIGH; "
        "require-grounding 0.80; block-fabrication; upgrade-on-risk reflexive; "
        "require-completeness 0.80"
    ),
    "developer": (
        "default-src context parametric; warn-on CRITICAL; "
        "require-quality S A B; oversight auto"
    ),
    "public-facing": (
        "default-src context parametric; halt-on CRITICAL; warn-on HIGH; "
        "block-pii; require-flow 0.60; max-repetition MINOR; require-completeness 0.70"
    ),
}


def is_profile_policy(value: str) -> bool:
    """True if *value* begins with a ``profile=`` token."""
    return value.strip().lower().startswith("profile=")


def expand_profile(value: str) -> str:
    """Expand a ``profile=<name>[; extra-directives]`` value to a directive string.

    Raises:
        PolicySyntaxError: If the profile name is unknown.
    """
    directives = [d.strip() for d in value.split(";") if d.strip()]
    head = directives[0]
    _, _, name = head.partition("=")
    name = name.strip().lower()
    if name not in PROFILES:
        raise PolicySyntaxError(
            f"unknown profile {name!r} (expected one of: {', '.join(sorted(PROFILES))})"
        )
    extra = directives[1:]
    expanded = PROFILES[name]
    if extra:
        expanded = expanded + "; " + "; ".join(extra)
    return expanded


def resolve_policy(value: str, *, report_only: bool = False) -> SafetyPolicy:
    """Parse a policy value, transparently expanding ``profile=`` references."""
    value = value.strip()
    if is_profile_policy(value):
        # Capture the profile name for provenance before expanding.
        head = value.split(";", 1)[0]
        _, _, name = head.partition("=")
        expanded = expand_profile(value)
        policy = parse_policy(expanded, report_only=report_only)
        policy.profile = name.strip().lower()
        return policy
    return parse_policy(value, report_only=report_only)
