# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Policy grammar parser (CRP-SPEC-006 §2).

Parses ``CRP-Safety-Policy`` directive strings into a :class:`SafetyPolicy`,
enforcing the ABNF grammar.  Malformed policies raise :class:`PolicySyntaxError`
(the gateway returns HTTP 400 for these — see CRP-SPEC-006 §7.1).
"""

from __future__ import annotations

from .model import (
    QUALITY_TIERS,
    SOURCE_VALUES,
    OversightMode,
    RepetitionLevel,
    RiskLevel,
    SafetyPolicy,
    Strategy,
)


class PolicySyntaxError(ValueError):
    """Raised when a ``CRP-Safety-Policy`` value violates the grammar."""


# Directives that take no argument (block-*).
_FLAG_DIRECTIVES: frozenset[str] = frozenset(
    {
        "block-ungrounded",
        "block-mixed",
        "block-parametric",
        "block-pii",
        "block-fabrication",
        "block-repetition",
    }
)


def _parse_threshold(directive: str, value: str) -> float:
    try:
        f = float(value)
    except ValueError as exc:
        raise PolicySyntaxError(f"{directive}: invalid threshold {value!r}") from exc
    if not (0.0 <= f <= 1.0):
        raise PolicySyntaxError(f"{directive}: threshold {f} out of range [0.0, 1.0]")
    return f


def _parse_enum(directive: str, value: str, enum_cls, label: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = ", ".join(m.value for m in enum_cls)
        raise PolicySyntaxError(
            f"{directive}: invalid {label} {value!r} (expected one of: {valid})"
        ) from exc


def parse_policy(value: str, *, report_only: bool = False) -> SafetyPolicy:
    """Parse a ``CRP-Safety-Policy`` directive string into a :class:`SafetyPolicy`.

    Args:
        value: The raw header value (e.g. ``"default-src context; halt-on CRITICAL"``).
        report_only: Set when parsed from ``CRP-Safety-Policy-Report-Only``.

    Raises:
        PolicySyntaxError: If any directive is malformed or unknown.
    """
    policy = SafetyPolicy(default_src=[], raw=value.strip())
    policy.report_only = report_only
    saw_default_src = False

    raw_directives = [d.strip() for d in value.split(";") if d.strip()]
    if not raw_directives:
        raise PolicySyntaxError("empty policy")

    for raw in raw_directives:
        tokens = raw.split()
        name = tokens[0].lower()
        args = tokens[1:]

        if name in _FLAG_DIRECTIVES:
            if args:
                raise PolicySyntaxError(f"{name}: takes no arguments")
            setattr(policy, name.replace("-", "_"), True)
            continue

        if not args:
            raise PolicySyntaxError(f"{name}: missing argument")

        if name == "default-src":
            for s in args:
                if s not in SOURCE_VALUES:
                    raise PolicySyntaxError(
                        f"default-src: invalid source {s!r} "
                        f"(expected one of: {', '.join(sorted(SOURCE_VALUES))})"
                    )
            policy.default_src = list(args)
            saw_default_src = True

        elif name == "halt-on":
            policy.halt_on = _parse_enum(name, args[0], RiskLevel, "risk-level")
            if policy.halt_on == RiskLevel.LOW:
                raise PolicySyntaxError("halt-on: LOW is not a valid halt level")

        elif name == "warn-on":
            policy.warn_on = _parse_enum(name, args[0], RiskLevel, "risk-level")

        elif name == "require-grounding":
            policy.require_grounding = _parse_threshold(name, args[0])

        elif name == "require-entailment":
            policy.require_entailment = _parse_threshold(name, args[0])

        elif name == "require-quality":
            for tier in args:
                if tier not in QUALITY_TIERS:
                    raise PolicySyntaxError(
                        f"require-quality: invalid tier {tier!r} "
                        f"(expected one of: {', '.join(sorted(QUALITY_TIERS))})"
                    )
            policy.require_quality = list(args)

        elif name == "require-flow":
            policy.require_flow = _parse_threshold(name, args[0])

        elif name == "require-completeness":
            policy.require_completeness = _parse_threshold(name, args[0])

        elif name == "require-oversight":
            policy.require_oversight = _parse_enum(name, args[0], OversightMode, "oversight-mode")

        elif name == "max-repetition":
            policy.max_repetition = _parse_enum(name, args[0], RepetitionLevel, "repetition-level")
            if policy.max_repetition == RepetitionLevel.SEVERE:
                raise PolicySyntaxError("max-repetition: SEVERE is not a valid limit")

        elif name == "upgrade-on-risk":
            policy.upgrade_on_risk = _parse_enum(name, args[0], Strategy, "strategy-name")

        elif name == "oversight":
            policy.oversight = _parse_enum(name, args[0], OversightMode, "oversight-mode")

        elif name == "report-uri":
            policy.report_uri = args[0]

        elif name == "report-to":
            policy.report_to = args[0]

        else:
            raise PolicySyntaxError(f"unknown directive {name!r}")

    # default-src default (CRP-SPEC-006 §3.1).
    if not saw_default_src:
        policy.default_src = ["context", "parametric"]

    return policy
