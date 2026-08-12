# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unit tests for CRP audit trail and HMAC chain."""

from __future__ import annotations

import asyncio
import hmac

import pytest

from crp_shared.audit import (
    AuditEvent,
    AuditTrail,
    EventSeverity,
    EventType,
    WindowSummary,
)


@pytest.fixture
def master_key() -> bytes:
    return b"test-master-key-32-bytes-long!!!"


def test_audit_event_canonical_hash_is_stable() -> None:
    event = AuditEvent(
        event_type=EventType.SESSION_CREATED,
        severity=EventSeverity.INFO,
        session_id="s1",
        window_id="w1",
        data={"a": 1, "b": 2},
    )
    first = event.canonical_data_hash()
    second = event.canonical_data_hash()
    assert first == second
    assert first.startswith("sha256:")


def test_event_hmac_chain(master_key: bytes) -> None:
    session_key = AuditTrail.derive_session_hmac_key_static(master_key, "session-1")
    event1 = AuditEvent(
        event_type=EventType.SESSION_CREATED,
        severity=EventSeverity.INFO,
        session_id="session-1",
        window_id="w0",
        data={"msg": "start"},
    )
    hmac1 = AuditTrail.compute_event_hmac(event1, "", session_key)
    assert hmac1.startswith("sha256:")

    event2 = AuditEvent(
        event_type=EventType.DISPATCH_STARTED,
        severity=EventSeverity.INFO,
        session_id="session-1",
        window_id="w1",
        data={"model": "gpt-4"},
    )
    hmac2 = AuditTrail.compute_event_hmac(event2, hmac1, session_key)
    assert hmac2 != hmac1

    # Tampering with previous HMAC invalidates verification.
    hmac2_tampered = AuditTrail.compute_event_hmac(event2, hmac1 + "x", session_key)
    assert hmac2_tampered != hmac2


def test_window_hmac(master_key: bytes) -> None:
    session_key = AuditTrail.derive_session_hmac_key_static(master_key, "session-1")
    summary = WindowSummary(
        window_id="w1",
        window_number=1,
        session_id="session-1",
        timestamp="2026-06-05T00:00:00+00:00",
        response_content_hash="sha256:abc",
        dpe_report_hash="sha256:def",
        window_hmac="",
        previous_window_hmac="sha256:prev",
    )
    computed = AuditTrail.compute_window_hmac(summary, session_key)
    assert computed.startswith("sha256:")


def test_export_ndjson_format(master_key: bytes) -> None:
    trail = AuditTrail.__new__(AuditTrail)
    trail.gateway_master_key = master_key

    async def fake_get_events(session_id: str, limit: int = 1000, offset: int = 0):
        return [
            AuditEvent(
                event_type=EventType.SESSION_CREATED,
                severity=EventSeverity.INFO,
                session_id=session_id,
                window_id="w0",
                data={"msg": "start"},
                event_hmac="sha256:deadbeef",
                timestamp="2026-06-05T00:00:00+00:00",
            )
        ]

    trail.get_events = fake_get_events  # type: ignore[assignment]
    ndjson = asyncio.run(trail.export_ndjson("s1"))
    assert isinstance(ndjson, str)
    assert "SESSION_CREATED" in ndjson
    assert "sha256:deadbeef" in ndjson
    assert ndjson.endswith("\n")


def test_comply_signature_is_hmac() -> None:
    trail = AuditTrail.__new__(AuditTrail)
    trail.comply_api_key = "secret"
    sig = trail._sign_comply_payload("body", "12345")
    expected = hmac.new(
        b"secret",
        b"12345.body",
        "sha256",
    ).hexdigest()
    assert hmac.compare_digest(sig, expected)
