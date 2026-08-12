# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Gmail SMTP checkpoint connector.

Uses an App Password (not your regular Gmail password) to send transactional
emails from a Gmail/Google Workspace account. If 2FA is enabled on the account,
generate an App Password at https://myaccount.google.com/apppasswords.

Environment variables:
  * GMAIL_USER - the Gmail / Google Workspace address (e.g. alerts@crprotocol.io)
  * GMAIL_APP_PASSWORD - the 16-character App Password
  * GMAIL_TO - comma-separated recipient addresses

If GMAIL_USER is not set, the connector falls back to the generic EmailConnector
env vars (EMAIL_SMTP_HOST=smtp.gmail.com, EMAIL_SMTP_USER, etc.).
"""

from __future__ import annotations

import os
from typing import Any

from crp_mcp.connectors.base import CheckpointConnector
from crp_mcp.connectors.email import EmailConnector


class GmailConnector(CheckpointConnector):
    """Send checkpoint notifications via Gmail SMTP + App Password."""

    name = "gmail"

    def __init__(self) -> None:
        self.user = os.environ.get("GMAIL_USER")
        self.password = os.environ.get("GMAIL_APP_PASSWORD")
        self.to = [a.strip() for a in os.environ.get("GMAIL_TO", "").split(",") if a.strip()]

        # Fallback to generic email env if Gmail-specific vars are absent.
        self._fallback = EmailConnector()
        self._fallback.host = self._fallback.host or "smtp.gmail.com"
        self._fallback.port = self._fallback.port or 587
        if not self.user:
            self.user = self._fallback.from_addr
        if not self.password:
            self.password = self._fallback.password
        if not self.to:
            self.to = self._fallback.to_addrs

    def is_configured(self) -> bool:
        return bool(self.user and self.password and self.to)

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "channel": self.name,
                "ok": False,
                "detail": "gmail_not_configured",
            }

        # Reuse the existing SMTP implementation, forcing Gmail defaults.
        self._fallback.host = "smtp.gmail.com"
        self._fallback.port = 587
        self._fallback.user = self.user
        self._fallback.password = self.password
        self._fallback.from_addr = self.user
        self._fallback.to_addrs = self.to

        return await self._fallback.notify(checkpoint)
