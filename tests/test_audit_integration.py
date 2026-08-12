# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Integration tests for CRP audit trail against PostgreSQL."""

from __future__ import annotations

import os

import asyncpg
import pytest

from crp_shared.audit import AuditEvent, AuditTrail, ChainIntegrity, EventSeverity, EventType
from crp_shared.schema import ensure_gateway_schema

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def pool():
    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    await ensure_gateway_schema(pool)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
def master_key() -> bytes:
    return b"integration-test-master-key-32!"


async def test_record_and_verify_chain(pool: asyncpg.Pool, master_key: bytes) -> None:
    trail = AuditTrail(pool=pool, gateway_master_key=master_key)
    session_id = "test-session-chain"

    # Clean up from prior runs.
    await pool.execute("DELETE FROM gateway_audit_events WHERE session_id = $1", session_id)

    event1 = AuditEvent(
        event_type=EventType.SESSION_CREATED,
        severity=EventSeverity.INFO,
        session_id=session_id,
        window_id="w0",
        data={"msg": "hello"},
    )
    await trail.record_event(event1)
    assert event1.event_hmac

    event2 = AuditEvent(
        event_type=EventType.DISPATCH_STARTED,
        severity=EventSeverity.INFO,
        session_id=session_id,
        window_id="w1",
        data={"model": "gpt-4"},
    )
    await trail.record_event(event2)
    assert event2.event_index == 1

    events = await trail.get_events(session_id)
    assert len(events) == 2
    assert events[1].event_index == 1

    integrity, broken_at = await trail.verify_chain(session_id)
    assert integrity == ChainIntegrity.VALID
    assert broken_at is None

    # Tamper with the DB and verify breakage is detected.
    await pool.execute(
        "UPDATE gateway_audit_events SET data = $1 WHERE session_id = $2 AND event_index = 0",
        '{"tampered": true}',
        session_id,
    )
    integrity, broken_at = await trail.verify_chain(session_id)
    assert integrity == ChainIntegrity.BROKEN
    assert broken_at == 0

    # Cleanup.
    await pool.execute("DELETE FROM gateway_audit_events WHERE session_id = $1", session_id)
