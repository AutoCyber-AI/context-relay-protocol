# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Comply backend checkpoint connector."""

from __future__ import annotations

from typing import Any

from crp_mcp.backend_client import BackendError, BackendNotConfigured, ComplyClient
from crp_mcp.connectors.base import CheckpointConnector


class ComplyConnector(CheckpointConnector):
    """Persist a checkpoint to the CRP Comply dashboard via its HTTP API."""

    name = "comply"

    def __init__(self, client: ComplyClient | None = None) -> None:
        self.client = client or ComplyClient()

    def is_configured(self) -> bool:
        return bool(
            self.client.base_url and self.client.api_key
        )

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "channel": self.name,
                "ok": False,
                "detail": "comply_backend_not_configured",
            }

        try:
            result = await self.client.create_checkpoint(checkpoint)
            return {
                "channel": self.name,
                "ok": True,
                "detail": result.get("checkpoint_id", "created"),
            }
        except BackendNotConfigured:
            return {
                "channel": self.name,
                "ok": False,
                "detail": "comply_backend_not_configured",
            }
        except BackendError as exc:
            return {
                "channel": self.name,
                "ok": False,
                "detail": str(exc),
            }
        except Exception as exc:  # pragma: no cover
            return {"channel": self.name, "ok": False, "detail": str(exc)}
