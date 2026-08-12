# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Human-oversight token flow (CRP-SPEC-012 §6.2; CRP-SPEC-011).

When a response is halted (HTTP 451) and a human reviewer approves it, an
*oversight token* is issued.  The client retries with
``CRP-Oversight-Token: approved:sha256:<sig>``; the gateway validates it and
releases the halted response.  The safety budget is NOT replenished — the
human has merely accepted the logged risk.

Relevant specifications:
  - CRP-SPEC-011: Audit Trail
  - CRP-SPEC-012: Multi-Agent Safety

PRIVATE REFERENCE IMPLEMENTATION — SPEC-012 internals are not published.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

_TOKEN_PREFIX = "approved:sha256:"


@dataclass
class OversightApproval:
    """A human reviewer's approval of an oversighted response (§6.2).

    Attributes:
        session_id: Session that produced the halted response.
        window_id: Window identifier of the halted response.
        reviewer_id: Identifier of the human reviewer granting approval.
        approval_timestamp: ISO-8601 UTC timestamp of the approval.
    """

    session_id: str
    window_id: str
    reviewer_id: str
    approval_timestamp: str

    def signing_payload(self) -> bytes:
        """Build the HMAC signing payload bound to this approval.

        The payload binds the token to ``session_id + window_id`` so a token
        issued for one window cannot release another.

        Returns:
            UTF-8 encoded string of the joined approval fields.
        """
        return "\u241f".join(
            [self.session_id, self.window_id, self.reviewer_id, self.approval_timestamp]
        ).encode("utf-8")


def issue_oversight_token(approval: OversightApproval, secret: bytes) -> str:
    """Issue a ``CRP-Oversight-Token`` value for an approved response.

    Args:
        approval: Approval record identifying the session, window, reviewer,
            and timestamp.
        secret: HMAC secret shared by the oversight issuer and verifier.

    Returns:
        The full token string, including the ``approved:sha256:`` prefix.
    """
    sig = hmac.new(secret, approval.signing_payload(), hashlib.sha256).hexdigest()
    return f"{_TOKEN_PREFIX}{sig}"


def verify_oversight_token(token: str, approval: OversightApproval, secret: bytes) -> bool:
    """Constant-time validation that *token* approves *approval* (§6.2).

    The token's scope is bound to ``session_id + window_id`` via the signing
    payload, so a token issued for one window cannot release another.

    Args:
        token: Token presented by the client in ``CRP-Oversight-Token``.
        approval: Expected approval record against which to validate.
        secret: HMAC secret used to issue the token.

    Returns:
        True if the token is well-formed and its signature matches the expected
        value in constant time.
    """
    if not token.startswith(_TOKEN_PREFIX):
        return False
    presented = token[len(_TOKEN_PREFIX):]
    expected = hmac.new(secret, approval.signing_payload(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(presented, expected)


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601 (helper for building approvals).

    Returns:
        ISO-8601 formatted UTC timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()
