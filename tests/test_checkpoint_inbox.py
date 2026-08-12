# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for checkpoint inbox (SPEC-034)."""

from __future__ import annotations

import pytest

from crp.comply.checkpoint_inbox import CheckpointInboxError, list_active_checkpoints, resolve_checkpoint
from crp.security.checkpoint import CheckpointResolutionAction
from crp.security.control_plane import get_default_control_plane


class TestCheckpointInbox:
    def test_resolve_checkpoint_approves(self) -> None:
        scp = get_default_control_plane()
        cp = scp.create_checkpoint(trigger="risk >= HIGH", context={"tenant_id": "org_1"})
        result = resolve_checkpoint(
            cp.checkpoint_id, action="approve", reviewer="user_1", note="looks good"
        )
        assert result["status"] == "resolved"
        assert result["action"] == "approve"
        assert "audit_ref" in result

    def test_resolve_checkpoint_rejects(self) -> None:
        scp = get_default_control_plane()
        cp = scp.create_checkpoint(trigger="risk >= HIGH", context={"tenant_id": "org_1"})
        result = resolve_checkpoint(
            cp.checkpoint_id, action="reject", reviewer="user_2"
        )
        assert result["action"] == "reject"

    def test_resolve_unknown_checkpoint_raises(self) -> None:
        with pytest.raises(CheckpointInboxError) as exc:
            resolve_checkpoint("nonexistent", action="approve", reviewer="user_1")
        assert exc.value.status_code == 404

    def test_resolve_invalid_action_raises(self) -> None:
        scp = get_default_control_plane()
        cp = scp.create_checkpoint()
        with pytest.raises(CheckpointInboxError):
            resolve_checkpoint(cp.checkpoint_id, action="banana", reviewer="user_1")

    def test_list_active_checkpoints(self) -> None:
        scp = get_default_control_plane()
        # Clear old checkpoints for clean test
        scp._checkpoints.clear()
        cp1 = scp.create_checkpoint(context={"tenant_id": "org_a"})
        cp2 = scp.create_checkpoint(context={"tenant_id": "org_a"})
        # Resolve one
        resolve_checkpoint(cp1.checkpoint_id, action="approve", reviewer="u1")

        active = list_active_checkpoints(tenant_id="org_a")
        ids = [a["checkpoint_id"] for a in active]
        assert cp2.checkpoint_id in ids
        assert cp1.checkpoint_id not in ids
