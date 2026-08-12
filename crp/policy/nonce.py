# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Policy-nonce binding (CRP-SPEC-006 §7.1, CRP-SPEC-002 §5.16).

``CRP-Safety-Nonce`` binds a policy to a session nonce so that an attacker who
can inject a ``CRP-Safety-Policy`` header cannot relax enforcement without also
forging the nonce.  The gateway issues a nonce at session start and verifies it
on every subsequent policy-bearing request.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_nonce(num_bytes: int = 32) -> str:
    """Return a cryptographically-random URL-safe nonce."""
    return secrets.token_urlsafe(num_bytes)


def bind_policy(policy_value: str, nonce: str, secret: str | bytes) -> str:
    """Return an HMAC-SHA256 tag binding *policy_value* to *nonce*.

    The tag travels in ``CRP-Safety-Nonce`` (or a derived header) and is
    recomputed by the gateway from the trusted session secret.
    """
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    msg = f"{nonce}:{policy_value}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_policy(policy_value: str, nonce: str, secret: str | bytes, tag: str) -> bool:
    """Constant-time verification of a policy-nonce binding tag."""
    expected = bind_policy(policy_value, nonce, secret)
    return hmac.compare_digest(expected, tag)
