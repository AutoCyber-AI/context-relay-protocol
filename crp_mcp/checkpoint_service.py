# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Human-in-the-loop checkpoint creation, resolution, and escalation service.

Production persistence is delegated to the CRP Comply backend.  This local
implementation adds Phase-7 features: multi-approver support, escalation
policies, timeout auto-resolution, and HMAC-signed audit records.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from crp_mcp.auth import Identity, hosted_available
from crp_mcp.connectors import get_configured_connectors


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class EscalationRule:
    """A single escalation step: after ``after_seconds``, notify ``channels``."""

    after_seconds: int
    channels: list[str] = field(default_factory=list)
    on_timeout: str | None = None  # e.g. "reject"


@dataclass
class Approval:
    """One human approval or rejection."""

    decision: str
    reviewer: str
    note: str | None = None
    timestamp: str = field(default_factory=lambda: _utcnow())


@dataclass
class CheckpointRecord:
    """Tamper-evident checkpoint record."""

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger: str = "RISK_HIGH"
    message: str = "Human approval required before proceeding."
    org_id: str | None = None
    user_id: str = "local"
    status: str = "waiting_for_human"
    status_url: str = ""
    hosted: bool = False
    required_approvers: int = 1
    approvals: list[Approval] = field(default_factory=list)
    escalation: list[EscalationRule] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _utcnow())
    resolved_at: str | None = None
    reviewer: str | None = None
    reviewer_note: str | None = None
    signature: str | None = None


# In-memory store for local previews / integration tests.
_checkpoints: dict[str, CheckpointRecord] = {}
_active_tasks: set[asyncio.Task[Any]] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _public_origin() -> str:
    return os.environ.get("CRP_PUBLIC_ORIGIN", "https://crprotocol.io").rstrip("/")


def _checkpoint_status_url(checkpoint_id: str) -> str:
    return f"{_public_origin()}/checkpoints/{checkpoint_id}"


def _hmac_secret() -> bytes:
    raw = os.environ.get("CRP_MCP_AUDIT_HMAC_SECRET", "")
    return raw.encode("utf-8") if raw else b""


def _canonical(record: CheckpointRecord) -> bytes:
    """Return a canonical JSON representation for signing/verifying."""
    data = {
        "checkpoint_id": record.checkpoint_id,
        "trigger": record.trigger,
        "message": record.message,
        "org_id": record.org_id,
        "user_id": record.user_id,
        "status": record.status,
        "status_url": record.status_url,
        "hosted": record.hosted,
        "required_approvers": record.required_approvers,
        "approvals": [
            {
                "decision": a.decision,
                "reviewer": a.reviewer,
                "note": a.note,
                "timestamp": a.timestamp,
            }
            for a in record.approvals
        ],
        "escalation": [
            {"after_seconds": e.after_seconds, "channels": e.channels, "on_timeout": e.on_timeout}
            for e in record.escalation
        ],
        "created_at": record.created_at,
        "resolved_at": record.resolved_at,
        "reviewer": record.reviewer,
        "reviewer_note": record.reviewer_note,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_record(record: CheckpointRecord) -> None:
    secret = _hmac_secret()
    if not secret:
        record.signature = None
        return
    record.signature = hmac.new(secret, _canonical(record), hashlib.sha256).hexdigest()


def _verify_record(record: CheckpointRecord) -> bool:
    secret = _hmac_secret()
    if not secret or not record.signature:
        return True
    expected = hmac.new(secret, _canonical(record), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, record.signature)


def _record_to_dict(record: CheckpointRecord) -> dict[str, Any]:
    return {
        "checkpoint_id": record.checkpoint_id,
        "trigger": record.trigger,
        "message": record.message,
        "status": record.status,
        "org_id": record.org_id,
        "user_id": record.user_id,
        "status_url": record.status_url,
        "hosted": record.hosted,
        "required_approvers": record.required_approvers,
        "approvals": [
            {"decision": a.decision, "reviewer": a.reviewer, "note": a.note, "timestamp": a.timestamp}
            for a in record.approvals
        ],
        "escalation": [
            {"after_seconds": e.after_seconds, "channels": e.channels, "on_timeout": e.on_timeout}
            for e in record.escalation
        ],
        "created_at": record.created_at,
        "resolved_at": record.resolved_at,
        "reviewer": record.reviewer,
        "reviewer_note": record.reviewer_note,
        "signature": record.signature,
    }


def _normalise_escalation(
    rules: list[EscalationRule] | list[dict[str, Any]] | None,
) -> list[EscalationRule]:
    if not rules:
        return []
    normalised: list[EscalationRule] = []
    for rule in rules:
        if isinstance(rule, EscalationRule):
            normalised.append(rule)
        elif isinstance(rule, dict):
            normalised.append(
                EscalationRule(
                    after_seconds=int(rule.get("after_seconds", 0)),
                    channels=[c.strip() for c in rule.get("channels", []) if c.strip()],
                    on_timeout=rule.get("on_timeout"),
                )
            )
    return normalised


def _parse_escalation(raw: str | None) -> list[EscalationRule]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        return _normalise_escalation(parsed)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Persistence / audit
# ---------------------------------------------------------------------------
def _persist_local(checkpoint: dict[str, Any]) -> None:
    """Append a checkpoint record to the local JSONL log if configured."""
    path = os.environ.get("CRP_MCP_CHECKPOINT_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(checkpoint, default=str, sort_keys=True) + "\n")
    except Exception:
        # Persistence failure must not block checkpoint creation.
        pass


def _audit(event_type: str, record: CheckpointRecord) -> None:
    """Append a signed audit event to the main audit log if configured."""
    path = os.environ.get("CRP_MCP_AUDIT_LOG")
    if not path:
        return
    event = {
        "timestamp": _utcnow(),
        "event_type": event_type,
        "checkpoint_id": record.checkpoint_id,
        "org_id": record.org_id,
        "user_id": record.user_id,
        "status": record.status,
        "signature": record.signature,
    }
    secret = _hmac_secret()
    if secret:
        event["audit_sig"] = hmac.new(
            secret,
            json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, default=str, sort_keys=True) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------
async def _escalate(record: CheckpointRecord, rule: EscalationRule) -> None:
    """Wait, then escalate to additional channels or auto-resolve."""
    if rule.after_seconds > 0:
        await asyncio.sleep(rule.after_seconds)

    current = _checkpoints.get(record.checkpoint_id)
    if current is None or current.status != "waiting_for_human":
        return

    if rule.on_timeout:
        decision_map = {"reject": "rejected", "approve": "approved"}
        decision = decision_map.get(rule.on_timeout, rule.on_timeout)
        _resolve(current, decision, "system", f"escalation_timeout:{rule.after_seconds}s")
        _persist_local(_record_to_dict(current))
        _audit("checkpoint_timeout", current)
        return

    if rule.channels:
        connectors = get_configured_connectors(",".join(rule.channels))
        for connector in connectors:
            try:
                await connector.notify(_record_to_dict(current))
            except Exception:  # pragma: no cover
                pass


def _schedule_escalation(record: CheckpointRecord) -> None:
    """Schedule escalation tasks without blocking checkpoint creation."""
    for rule in record.escalation:
        if rule.after_seconds <= 0 and not rule.on_timeout and not rule.channels:
            continue
        task = asyncio.create_task(_escalate(record, rule))
        _active_tasks.add(task)
        task.add_done_callback(_active_tasks.discard)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def _resolve(
    record: CheckpointRecord,
    decision: str,
    reviewer: str,
    note: str | None = None,
) -> None:
    record.status = decision
    record.resolved_at = _utcnow()
    record.reviewer = reviewer
    record.reviewer_note = note
    _sign_record(record)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def create_checkpoint(
    trigger: str,
    message: str,
    identity: Identity | None = None,
    channels: list[str] | None = None,
    required_approvers: int = 1,
    escalation: list[EscalationRule] | None = None,
) -> dict[str, Any]:
    """Create a checkpoint, notify review channels, and return a status payload.

    The checkpoint is written to the local in-memory store and to the optional
    ``CRP_MCP_CHECKPOINT_LOG``.  When hosted mode is configured it is also
    forwarded to the CRP Comply backend and any enabled connectors.
    """
    org_id = getattr(identity, "org_id", None) if identity else None
    user_id = getattr(identity, "user_id", "local") if identity else "local"

    record = CheckpointRecord(
        trigger=trigger,
        message=message or "Human approval required before proceeding.",
        org_id=org_id,
        user_id=user_id,
        status_url=_checkpoint_status_url(str(uuid.uuid4())),
        hosted=hosted_available(),
        required_approvers=max(1, required_approvers),
        escalation=_normalise_escalation(
            escalation or _parse_escalation(os.environ.get("CRP_MCP_CHECKPOINT_ESCALATION"))
        ),
    )
    # Use the generated id for the status URL too.
    record.status_url = _checkpoint_status_url(record.checkpoint_id)

    _sign_record(record)
    _checkpoints[record.checkpoint_id] = record
    _persist_local(_record_to_dict(record))
    _audit("checkpoint_created", record)

    connectors = get_configured_connectors(
        ",".join(channels) if channels else None
    )
    notified: list[dict[str, Any]] = []
    for connector in connectors:
        try:
            result = await connector.notify(_record_to_dict(record))
            notified.append(result)
        except Exception as exc:  # pragma: no cover
            notified.append({
                "channel": getattr(connector, "name", "unknown"),
                "ok": False,
                "detail": str(exc),
            })

    _schedule_escalation(record)

    payload = _record_to_dict(record)
    payload["notified_channels"] = notified
    return payload


def approve_checkpoint(
    checkpoint_id: str,
    reviewer: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Record an approval for a checkpoint.

    If ``required_approvers`` is reached the checkpoint is resolved as approved.
    Any rejection immediately resolves the checkpoint as rejected.
    """
    record = _checkpoints.get(checkpoint_id)
    if record is None:
        return {"ok": False, "error": "checkpoint_not_found"}
    if record.status != "waiting_for_human":
        return {"ok": False, "error": f"checkpoint_already_{record.status}"}

    record.approvals.append(Approval(decision="approved", reviewer=reviewer, note=note))
    _audit("checkpoint_approval", record)

    approvals_count = sum(1 for a in record.approvals if a.decision == "approved")
    if approvals_count >= record.required_approvers:
        _resolve(record, "approved", reviewer, note)
        _persist_local(_record_to_dict(record))
        _audit("checkpoint_resolved", record)

    return {"ok": True, "checkpoint_id": checkpoint_id, "status": record.status}


def reject_checkpoint(
    checkpoint_id: str,
    reviewer: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Record a rejection and immediately resolve the checkpoint as rejected."""
    record = _checkpoints.get(checkpoint_id)
    if record is None:
        return {"ok": False, "error": "checkpoint_not_found"}
    if record.status != "waiting_for_human":
        return {"ok": False, "error": f"checkpoint_already_{record.status}"}

    record.approvals.append(Approval(decision="rejected", reviewer=reviewer, note=note))
    _resolve(record, "rejected", reviewer, note)
    _persist_local(_record_to_dict(record))
    _audit("checkpoint_resolved", record)

    return {"ok": True, "checkpoint_id": checkpoint_id, "status": record.status}


def resolve_checkpoint(
    checkpoint_id: str,
    decision: str,
    reviewer: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Resolve a checkpoint with ``approved`` or ``rejected``."""
    if decision == "approved":
        return approve_checkpoint(checkpoint_id, reviewer, note)
    if decision == "rejected":
        return reject_checkpoint(checkpoint_id, reviewer, note)
    return {"ok": False, "error": f"invalid_decision:{decision}"}


def get_checkpoint(checkpoint_id: str) -> dict[str, Any] | None:
    record = _checkpoints.get(checkpoint_id)
    if record is None:
        return None
    return _record_to_dict(record)


def verify_checkpoint_signature(checkpoint_id: str) -> bool:
    record = _checkpoints.get(checkpoint_id)
    if record is None:
        return False
    return _verify_record(record)
