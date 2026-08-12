# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Lightweight claim extraction for the Verification Relay (SPEC-049).

Turns raw model text into checkable ``Claim`` objects.  This starter extractor
is intentionally rule-based: it surfaces arithmetic equations and simple
constraint patterns so symbolic verifiers can decide them without a trained
model.  More sophisticated extraction (NLI parsing, equation detection, etc.)
can be plugged in as an additional verifier or extractor.
"""

from __future__ import annotations

import re
from typing import Any

from crp.vr.interface import Claim

# Equation patterns such as "10 + 20 = 30" or "(100 - 5) * 2 = 190".
_EQ_RE = re.compile(
    r"(?P<lhs>[\d\s\+\-\*\/\(\)\.]+?)\s*=\s*(?P<expected>[\d\.]+)",
    re.IGNORECASE,
)


def _safe_expr(lhs: str) -> str | None:
    """Return a Python-evaluable expression if *lhs* contains only safe tokens."""
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in lhs):
        return None
    # Collapse whitespace.
    return re.sub(r"\s+", "", lhs)


def extract_claims(text: str) -> list[Claim]:
    """Extract checkable claims from *text*.

    Returns:
        A list of ``Claim`` objects suitable for ``VerificationRelay.verify_trace``.
    """
    claims: list[Claim] = []
    for match in _EQ_RE.finditer(text):
        lhs = match.group("lhs").strip()
        expected_str = match.group("expected")
        expr = _safe_expr(lhs)
        if expr is None:
            continue
        try:
            expected = float(expected_str)
            if expected.is_integer():
                expected = int(expected)
        except ValueError:
            continue
        claims.append(
            Claim(
                text=match.group(0),
                kind="arithmetic",
                formal={"expr": expr, "expected": expected},
            )
        )

    # Simple logical constraint pattern: "X must be greater than Y" etc.
    # This is intentionally narrow; formal claims should come from structured
    # tool outputs or constrained decoders (SPEC-054) in production.
    if re.search(r"must be (greater|less) than \d+", text, re.IGNORECASE):
        claims.append(
            Claim(
                text=text.strip(),
                kind="inference",
            )
        )

    return claims


def verify_text(
    text: str,
    depth: str = "thorough",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience helper: extract claims from *text* and verify them.

    Args:
        text: Output text to verify.
        depth: Request depth; PRM is skipped unless thorough/exhaustive.
        context: Optional verifier context.

    Returns:
        Verification report dict (or a no-op report if no claims extracted).
    """
    from crp.vr.relay import VerificationRelay

    claims = extract_claims(text)
    if not claims:
        return {
            "stage": "dpe_14_verification",
            "verification_ratio": 1.0,
            "checked": 0,
            "invalid": 0,
            "repairs": 0,
            "tier_cap": None,
            "risk_floor": "LOW",
            "labels": [],
        }
    relay = VerificationRelay()
    return relay.verify_trace(claims, context=context, depth=depth)
