# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Verification Relay interface (SPEC-049 §1.3.1).

All symbolic and probabilistic verifiers implement the same ``Verifier`` protocol
so the relay can dispatch uniformly.  A ``Claim`` is a single reasoning step or
checkable assertion extracted from a trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Verdict(str, Enum):
    """Possible outcomes of a verification attempt."""

    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass
class VerificationResult:
    """Result returned by every verifier."""

    verdict: Verdict
    confidence: float
    reason: str
    verifier: str
    checkable: bool


@dataclass
class Claim:
    """A single reasoning step or assertion to be verified."""

    text: str
    kind: str = "inference"  # inference | arithmetic | temporal | constraint | fact
    premises: list[str] = field(default_factory=list)
    formal: dict[str, Any] | None = None


@runtime_checkable
class Verifier(Protocol):
    """Protocol implemented by every verifier plugged into the relay."""

    name: str

    def applies(self, claim: Claim) -> bool:
        """Return True if this verifier can decide *claim*."""
        ...

    def verify(self, claim: Claim, context: dict[str, Any]) -> VerificationResult:
        """Verify *claim* and return a ``VerificationResult``."""
        ...
