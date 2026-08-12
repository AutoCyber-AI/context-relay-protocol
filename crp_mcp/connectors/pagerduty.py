# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""PagerDuty Events API v2 checkpoint connector.

Triggers a PagerDuty incident when a checkpoint requires human attention.
Requires a PagerDuty Integration Key (routing key).

Environment variables:
  * PAGERDUTY_ROUTING_KEY - the 32-character integration/routing key.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from crp_mcp.connectors.base import CheckpointConnector


class PagerDutyConnector(CheckpointConnector):
    """Create PagerDuty incidents for critical checkpoints."""

    name = "pagerduty"

    def __init__(self, routing_key: str | None = None) -> None:
        self.routing_key = routing_key or os.environ.get("PAGERDUTY_ROUTING_KEY")

    def is_configured(self) -> bool:
        return bool(self.routing_key)

    def _payload(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        return {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": checkpoint.get("checkpoint_id"),
            "payload": {
                "summary": (
                    f"CRP checkpoint {checkpoint.get('checkpoint_id')} requires approval"
                ),
                "severity": "critical",
                "source": "crp-mcp-server",
                "custom_details": {
                    "trigger": checkpoint.get("trigger"),
                    "message": checkpoint.get("message"),
                    "org_id": checkpoint.get("org_id"),
                    "user_id": checkpoint.get("user_id"),
                    "status_url": checkpoint.get("status_url"),
                },
            },
            "links": [
                {
                    "href": checkpoint.get("status_url", "https://crprotocol.io"),
                    "text": "Review checkpoint",
                }
            ],
        }

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.routing_key:
            return {
                "channel": self.name,
                "ok": False,
                "detail": "missing_routing_key",
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=self._payload(checkpoint),
                )
                response.raise_for_status()
            data = response.json()
            return {
                "channel": self.name,
                "ok": True,
                "detail": data.get("dedup_key", "triggered"),
                "status": data.get("status"),
            }
        except Exception as exc:  # pragma: no cover
            return {"channel": self.name, "ok": False, "detail": str(exc)}
