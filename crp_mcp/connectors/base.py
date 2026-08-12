# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Base class for checkpoint review-channel connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CheckpointConnector(ABC):
    """Notify a review channel that a human-in-the-loop checkpoint is waiting."""

    name: str = ""

    @abstractmethod
    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Send the checkpoint to the channel.  Return a status dict."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the connector has enough configuration to run."""
