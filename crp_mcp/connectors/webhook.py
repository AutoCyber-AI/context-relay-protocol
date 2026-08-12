# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Generic webhook checkpoint connector."""

from __future__ import annotations

import os
from typing import Any

import httpx

from crp_mcp.connectors.base import CheckpointConnector


class WebhookConnector(CheckpointConnector):
    """POST checkpoint payloads to a configured HTTP(S) webhook URL."""

    name = "webhook"

    def __init__(
        self,
        url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url or os.environ.get("CRP_MCP_CHECKPOINT_WEBHOOK_URL")
        self.client = client

    def is_configured(self) -> bool:
        return bool(self.url)

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.url:
            return {"channel": self.name, "ok": False, "detail": "missing_url"}

        try:
            if self.client is not None:
                response = await self.client.post(self.url, json=checkpoint)
            else:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(self.url, json=checkpoint)
            response.raise_for_status()
            return {
                "channel": self.name,
                "ok": True,
                "detail": f"status:{response.status_code}",
            }
        except Exception as exc:  # pragma: no cover - network failures
            return {"channel": self.name, "ok": False, "detail": str(exc)}
