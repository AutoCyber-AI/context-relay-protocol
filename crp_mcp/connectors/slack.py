# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Slack incoming-webhook checkpoint connector."""

from __future__ import annotations

import os
from typing import Any

import httpx

from crp_mcp.connectors.base import CheckpointConnector


class SlackConnector(CheckpointConnector):
    """Post a compact checkpoint message to a Slack incoming webhook."""

    name = "slack"

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _payload(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        status_url = checkpoint.get("status_url", "")
        text = (
            f"🛑 *CRP checkpoint* `{checkpoint.get('checkpoint_id')}`\n"
            f"*Trigger:* {checkpoint.get('trigger')}\n"
            f"*User:* {checkpoint.get('user_id')}  |  *Org:* {checkpoint.get('org_id')}\n"
            f"*Message:* {checkpoint.get('message') or 'No message'}"
        )
        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            }
        ]
        if status_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review checkpoint"},
                        "url": status_url,
                    }
                ],
            })
        return {"text": text, "blocks": blocks}

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.webhook_url:
            return {"channel": self.name, "ok": False, "detail": "missing_webhook_url"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=self._payload(checkpoint),
                )
                response.raise_for_status()
            return {
                "channel": self.name,
                "ok": True,
                "detail": f"status:{response.status_code}",
            }
        except Exception as exc:  # pragma: no cover
            return {"channel": self.name, "ok": False, "detail": str(exc)}
