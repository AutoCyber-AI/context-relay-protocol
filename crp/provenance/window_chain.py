# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Window-level HMAC provenance chain (CRP-SPEC-004 §9, CRP-SPEC-011 §2-3).

Each window in a session carries a summary HMAC that chains from its parent
window(s). The chain is tamper-evident: modifying or removing any ancestor
invalidates every descendant. This module computes window HMACs (linear and
fan-in) and verifies the chain, emitting the ``CRP-Provenance-Chain-Integrity``
status defined in CRP-SPEC-011 §3.3.

PRIVATE REFERENCE IMPLEMENTATION — SPEC internals are not published.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass, field

# Unit separator joins fields unambiguously (matches crp.agent.chain).
_SEP = "\u241f"


# ---------------------------------------------------------------------------
# Chain integrity status (CRP-SPEC-011 §3.3)
# ---------------------------------------------------------------------------

class ChainIntegrity(str, enum.Enum):
    """Result of verifying a window provenance chain."""

    VALID = "VALID"            # Full chain verified root → current window
    BROKEN = "BROKEN"          # Verification failed — possible tampering
    PARTIAL = "PARTIAL"        # Window-level verified; full chain not checked
    UNVERIFIED = "UNVERIFIED"  # First window of session (no previous to chain)


# ---------------------------------------------------------------------------
# Window HMAC computation (CRP-SPEC-011 §2.3, CRP-SPEC-004 §9.1)
# ---------------------------------------------------------------------------

@dataclass
class WindowHmacInput:
    """Inputs to a window's summary HMAC.

    ``HMAC-SHA256(session_id ‖ window_number ‖ timestamp ‖ response_hash ‖
    dpe_report_hash ‖ prev_window_hmac, key)`` — CRP-SPEC-011 §2.3.
    """

    session_id: str
    window_number: int
    timestamp: str
    response_hash: str
    dpe_report_hash: str = ""
    prev_window_hmac: str = ""  # empty for the root window

    def message(self) -> bytes:
        """Return the canonical message bytes used for window HMAC computation."""
        return _SEP.join(
            [
                self.session_id,
                str(self.window_number),
                self.timestamp,
                self.response_hash,
                self.dpe_report_hash,
                self.prev_window_hmac,
            ]
        ).encode("utf-8")


def build_window_hmac(inp: WindowHmacInput, key: bytes) -> str:
    """Compute a window summary HMAC (linear chain extension, §9.1)."""
    digest = hmac.new(key, inp.message(), hashlib.sha256).hexdigest()
    return f"sha256:{digest}"


def build_fan_in_window_hmac(
    *,
    session_id: str,
    window_number: int,
    timestamp: str,
    response_hash: str,
    dpe_report_hash: str,
    parent_hmacs: Sequence[str],
    key: bytes,
) -> str:
    """Compute a fan-in window HMAC merging multiple parents (§9.3).

    Parent HMACs are sorted lexicographically and joined with ``|`` so the
    result is deterministic regardless of child completion order.
    """
    merged_parent_input = "|".join(sorted(parent_hmacs))
    msg = _SEP.join(
        [
            session_id,
            str(window_number),
            timestamp,
            response_hash,
            dpe_report_hash,
            merged_parent_input,
        ]
    ).encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Chain records & verification (CRP-SPEC-011 §3)
# ---------------------------------------------------------------------------

@dataclass
class WindowChainRecord:
    """A window's stored HMAC plus the inputs needed to recompute it."""

    session_id: str
    window_number: int
    timestamp: str
    response_hash: str
    dpe_report_hash: str = ""
    hmac: str = ""
    parent_hmacs: list[str] = field(default_factory=list)
    is_fan_in: bool = False

    def recompute(self, key: bytes, prev_window_hmac: str) -> str:
        """Recompute this window's expected HMAC.

        Args:
            key: HMAC key bytes.
            prev_window_hmac: Parent window HMAC (ignored for fan-in windows).

        Returns:
            The recomputed HMAC string.
        """
        if self.is_fan_in:
            return build_fan_in_window_hmac(
                session_id=self.session_id,
                window_number=self.window_number,
                timestamp=self.timestamp,
                response_hash=self.response_hash,
                dpe_report_hash=self.dpe_report_hash,
                parent_hmacs=self.parent_hmacs,
                key=key,
            )
        return build_window_hmac(
            WindowHmacInput(
                session_id=self.session_id,
                window_number=self.window_number,
                timestamp=self.timestamp,
                response_hash=self.response_hash,
                dpe_report_hash=self.dpe_report_hash,
                prev_window_hmac=prev_window_hmac,
            ),
            key,
        )


@dataclass
class ChainVerification:
    """Outcome of a chain verification (CRP-SPEC-011 §3.3)."""

    status: ChainIntegrity = ChainIntegrity.UNVERIFIED
    broken_at_window: int = -1
    verified_count: int = 0

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        return {"CRP-Provenance-Chain-Integrity": self.status.value}


def verify_window_chain(
    records: Sequence[WindowChainRecord], key: bytes
) -> ChainVerification:
    """Verify a session's complete window chain from root to leaf (§3.1).

    Returns ``UNVERIFIED`` for an empty/single-root chain that has nothing to
    chain from, ``BROKEN`` (with ``broken_at_window``) on the first mismatch,
    and ``VALID`` when every link verifies.
    """
    if not records:
        return ChainVerification(status=ChainIntegrity.UNVERIFIED)

    prev_hmac = ""
    verified = 0
    for rec in records:
        expected = rec.recompute(key, prev_hmac)
        if not hmac.compare_digest(expected, rec.hmac):
            return ChainVerification(
                status=ChainIntegrity.BROKEN,
                broken_at_window=rec.window_number,
                verified_count=verified,
            )
        verified += 1
        prev_hmac = rec.hmac

    # A lone root window has nothing prior to chain from.
    if len(records) == 1 and not records[0].parent_hmacs:
        return ChainVerification(
            status=ChainIntegrity.UNVERIFIED, verified_count=verified
        )

    return ChainVerification(status=ChainIntegrity.VALID, verified_count=verified)


def verify_window_partial(
    record: WindowChainRecord, parent_window_hmac: str, key: bytes
) -> ChainVerification:
    """Verify a single window against its parent's HMAC (§3.2).

    Auditors holding only one window and its parent tip get ``PARTIAL`` on
    success (the full chain was not checked) or ``BROKEN`` on mismatch.
    """
    expected = record.recompute(key, parent_window_hmac)
    if not hmac.compare_digest(expected, record.hmac):
        return ChainVerification(
            status=ChainIntegrity.BROKEN, broken_at_window=record.window_number
        )
    return ChainVerification(status=ChainIntegrity.PARTIAL, verified_count=1)


__all__ = [
    "ChainIntegrity",
    "WindowHmacInput",
    "build_window_hmac",
    "build_fan_in_window_hmac",
    "WindowChainRecord",
    "ChainVerification",
    "verify_window_chain",
    "verify_window_partial",
]
