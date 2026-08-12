# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unit tests for CRP session tokens."""

from __future__ import annotations

import time

import pytest

from crp_shared.session_token import (
    CRP_SESSION_TOKEN_VERSION,
    SessionTokenManager,
    TokenError,
    encode_scope,
)


@pytest.fixture
def manager() -> SessionTokenManager:
    return SessionTokenManager(b"master-key-for-tests-32bytes!", default_ttl_seconds=60)


def test_issue_and_verify(manager: SessionTokenManager) -> None:
    token = manager.issue(
        session_id="sess-1",
        window_id="win-1",
        quality_hash="sha256:abc",
        soft_budget=1200,
        continuation_count=2,
        conversation_id="conv-1",
        dag_node_id="dag-1",
        strategy="balanced",
        policy_id="policy-1",
        ckf_etag="etag-1",
        scope=encode_scope("chat", "agent"),
    )
    assert isinstance(token, str)
    assert token.count(".") == 2

    decoded = manager.verify(token)
    assert decoded.v == CRP_SESSION_TOKEN_VERSION
    assert decoded.sid == "sess-1"
    assert decoded.win == "win-1"
    assert decoded.qh == "sha256:abc"
    assert decoded.sb == 1200
    assert decoded.ct == 2
    assert decoded.cid == "conv-1"
    assert decoded.dag == "dag-1"
    assert decoded.str_ == "balanced"
    assert decoded.pol == "policy-1"
    assert decoded.ckf == "etag-1"
    assert decoded.scope == encode_scope("chat", "agent")
    assert decoded.exp > decoded.iat


def test_tampered_payload_fails(manager: SessionTokenManager) -> None:
    token = manager.issue(session_id="sess-1")
    header, payload, sig = token.split(".")
    # Flip a character in the payload.
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = f"{header}.{tampered_payload}.{sig}"
    with pytest.raises(TokenError):
        manager.verify(tampered)


def test_expired_token_fails() -> None:
    short_manager = SessionTokenManager(b"master-key-for-tests-32bytes!", default_ttl_seconds=60)
    token = short_manager.issue(session_id="sess-1", ttl_seconds=-1)
    with pytest.raises(TokenError):
        short_manager.verify(token)


def test_invalid_format(manager: SessionTokenManager) -> None:
    with pytest.raises(TokenError):
        manager.verify("not-a-token")


def test_encode_scope() -> None:
    assert encode_scope("chat") == 1 << 0
    assert encode_scope("agent", "tool") == (1 << 5) | (1 << 6)
    assert encode_scope("unknown") == 0
