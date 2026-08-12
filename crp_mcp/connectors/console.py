# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Console/audit-log checkpoint connector."""

from __future__ import annotations

import json
import sys
from typing import Any

from crp_mcp.connectors.base import CheckpointConnector


class ConsoleConnector(CheckpointConnector):
    """Write checkpoint notifications to stderr/audit log.

    This connector is always available and is the default review channel in
    local mode.  It never blocks or fails.
    """

    name = "console"

    def is_configured(self) -> bool:
        return True

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        record = {
            "channel": self.name,
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "trigger": checkpoint.get("trigger"),
            "message": checkpoint.get("message"),
            "org_id": checkpoint.get("org_id"),
            "user_id": checkpoint.get("user_id"),
            "status_url": checkpoint.get("status_url"),
        }
        print(
            f"[crp-checkpoint] {json.dumps(record, default=str)}",
            file=sys.stderr,
        )
        return {"channel": self.name, "ok": True, "detail": "logged"}
