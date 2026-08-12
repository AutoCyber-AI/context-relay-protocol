# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SMTP email checkpoint connector."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from crp_mcp.connectors.base import CheckpointConnector


class EmailConnector(CheckpointConnector):
    """Send checkpoint notifications via SMTP.

    Environment variables:
      * EMAIL_SMTP_HOST (required)
      * EMAIL_SMTP_PORT (default 587)
      * EMAIL_SMTP_USER
      * EMAIL_SMTP_PASSWORD
      * EMAIL_FROM
      * EMAIL_TO (comma-separated)
    """

    name = "email"

    def __init__(self) -> None:
        self.host = os.environ.get("EMAIL_SMTP_HOST")
        self.port = int(os.environ.get("EMAIL_SMTP_PORT", "587") or "587")
        self.user = os.environ.get("EMAIL_SMTP_USER")
        self.password = os.environ.get("EMAIL_SMTP_PASSWORD")
        self.from_addr = os.environ.get("EMAIL_FROM")
        self.to_addrs = [
            a.strip()
            for a in (os.environ.get("EMAIL_TO", "").split(","))
            if a.strip()
        ]

    def is_configured(self) -> bool:
        return bool(self.host and self.from_addr and self.to_addrs)

    def _message(self, checkpoint: dict[str, Any]) -> MIMEMultipart:
        subject = f"CRP checkpoint {checkpoint.get('checkpoint_id')} requires approval"
        status_url = checkpoint.get("status_url", "")
        body_text = (
            f"A CRP safety checkpoint is waiting for human review.\n\n"
            f"Checkpoint ID: {checkpoint.get('checkpoint_id')}\n"
            f"Trigger:       {checkpoint.get('trigger')}\n"
            f"User:          {checkpoint.get('user_id')}\n"
            f"Org:           {checkpoint.get('org_id')}\n"
            f"Message:       {checkpoint.get('message') or 'No message'}\n"
        )
        if status_url:
            body_text += f"\nReview: {status_url}\n"

        body_html = f"""
        <html><body>
        <h2>CRP checkpoint requires approval</h2>
        <table>
          <tr><td><b>Checkpoint ID</b></td><td>{checkpoint.get('checkpoint_id')}</td></tr>
          <tr><td><b>Trigger</b></td><td>{checkpoint.get('trigger')}</td></tr>
          <tr><td><b>User</b></td><td>{checkpoint.get('user_id')}</td></tr>
          <tr><td><b>Org</b></td><td>{checkpoint.get('org_id')}</td></tr>
          <tr><td><b>Message</b></td><td>{checkpoint.get('message') or 'No message'}</td></tr>
        </table>
        {f'<p><a href="{status_url}">Review checkpoint</a></p>' if status_url else ''}
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
        return msg

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "channel": self.name,
                "ok": False,
                "detail": "missing_smtp_configuration",
            }

        try:
            msg = self._message(checkpoint)
            # smtplib is blocking; run in a thread to keep the MCP server async.
            import asyncio

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_sync, msg)
            return {
                "channel": self.name,
                "ok": True,
                "detail": f"sent_to:{len(self.to_addrs)}",
            }
        except Exception as exc:  # pragma: no cover
            return {"channel": self.name, "ok": False, "detail": str(exc)}

    def _send_sync(self, msg: MIMEMultipart) -> None:
        server = smtplib.SMTP(self.host, self.port)
        try:
            server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.sendmail(
                self.from_addr,
                self.to_addrs,
                msg.as_string(),
            )
        finally:
            server.quit()
