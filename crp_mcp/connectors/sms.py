# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Twilio SMS checkpoint connector."""

from __future__ import annotations

import os
from typing import Any

import httpx

from crp_mcp.connectors.base import CheckpointConnector


class SMSConnector(CheckpointConnector):
    """Send a short checkpoint SMS via Twilio.

    Environment variables:
      * TWILIO_ACCOUNT_SID
      * TWILIO_AUTH_TOKEN
      * TWILIO_FROM
      * SMS_TO (comma-separated E.164 numbers)
    """

    name = "sms"

    def __init__(self) -> None:
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.from_number = os.environ.get("TWILIO_FROM")
        self.to_numbers = [
            n.strip()
            for n in (os.environ.get("SMS_TO", "").split(","))
            if n.strip()
        ]

    def is_configured(self) -> bool:
        return bool(
            self.account_sid and self.auth_token and self.from_number and self.to_numbers
        )

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "channel": self.name,
                "ok": False,
                "detail": "missing_twilio_configuration",
            }

        body = (
            f"CRP checkpoint {checkpoint.get('checkpoint_id')} "
            f"({checkpoint.get('trigger')}) needs approval. "
            f"{checkpoint.get('status_url', '')}"
        )[:320]

        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for number in self.to_numbers:
                url = (
                    f"https://api.twilio.com/2010-04-01/Accounts/"
                    f"{self.account_sid}/Messages.json"
                )
                try:
                    response = await client.post(
                        url,
                        auth=(self.account_sid, self.auth_token),
                        data={
                            "From": self.from_number,
                            "To": number,
                            "Body": body,
                        },
                    )
                    response.raise_for_status()
                    results.append({
                        "to": number,
                        "ok": True,
                        "status": response.status_code,
                    })
                except Exception as exc:  # pragma: no cover
                    results.append({
                        "to": number,
                        "ok": False,
                        "detail": str(exc),
                    })

        ok = all(r["ok"] for r in results)
        return {
            "channel": self.name,
            "ok": ok,
            "detail": results,
        }
