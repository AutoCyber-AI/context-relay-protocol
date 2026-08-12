# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Firebase Cloud Messaging (FCM) push-notification checkpoint connector.

Sends push notifications to Android/iOS/Web devices using the FCM HTTP v1 API.
Requires a Firebase service account and one or more device registration tokens.

Environment variables:
  * FIREBASE_SERVICE_ACCOUNT_JSON - raw JSON of a Firebase service account key
    (contains project_id, client_email, private_key, token_uri).
    Alternatively set GOOGLE_APPLICATION_CREDENTIALS to a JSON file path.
  * FIREBASE_PROJECT_ID - optional override of the project_id in the service account.
  * FCM_DEVICE_TOKENS - comma-separated list of device registration tokens to notify.

Security note: the service account JSON is a secret. Store it in a secret manager
and never commit it to git.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from crp_mcp.connectors.base import CheckpointConnector

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
except Exception:  # pragma: no cover
    ServiceAccountCredentials = None  # type: ignore[assignment,misc]
    GoogleAuthRequest = None  # type: ignore[assignment,misc]


_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FCMConnector(CheckpointConnector):
    """Send checkpoint notifications as Firebase push messages."""

    name = "fcm"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client
        self.service_account_info = self._load_service_account_info()
        self.project_id = (
            os.environ.get("FIREBASE_PROJECT_ID")
            or (self.service_account_info or {}).get("project_id")
        )
        self.tokens = [
            t.strip()
            for t in os.environ.get("FCM_DEVICE_TOKENS", "").split(",")
            if t.strip()
        ]

    def is_configured(self) -> bool:
        return bool(
            ServiceAccountCredentials is not None
            and self.service_account_info
            and self.project_id
            and self.tokens
        )

    def _load_service_account_info(self) -> dict[str, Any] | None:
        raw_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if raw_json:
            try:
                return json.loads(raw_json)
            except json.JSONDecodeError:
                return None
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.isfile(creds_path):
            try:
                with open(creds_path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:  # pragma: no cover
                return None
        return None

    def _get_access_token(self) -> str | None:
        if ServiceAccountCredentials is None or self.service_account_info is None:
            return None
        try:
            credentials = ServiceAccountCredentials.from_service_account_info(
                self.service_account_info,
                scopes=[_FCM_SCOPE],
            )
            credentials.refresh(GoogleAuthRequest())
            return credentials.token
        except Exception:  # pragma: no cover
            return None

    def _message(self, token: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        title = f"CRP checkpoint {checkpoint.get('checkpoint_id', '')}"
        body = checkpoint.get("message") or "Human approval required."
        status_url = checkpoint.get("status_url", "")
        return {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": {
                    "checkpoint_id": str(checkpoint.get("checkpoint_id", "")),
                    "trigger": str(checkpoint.get("trigger", "")),
                    "status_url": status_url,
                    "org_id": str(checkpoint.get("org_id", "")),
                },
            }
        }

    async def notify(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "channel": self.name,
                "ok": False,
                "detail": "fcm_not_configured",
            }

        access_token = self._get_access_token()
        if not access_token:
            return {
                "channel": self.name,
                "ok": False,
                "detail": "fcm_auth_failed",
            }

        url = (
            f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        results: list[dict[str, Any]] = []
        http_client = self.client or httpx.AsyncClient(timeout=20.0)
        try:
            for token in self.tokens:
                try:
                    response = await http_client.post(
                        url,
                        headers=headers,
                        json=self._message(token, checkpoint),
                    )
                    response.raise_for_status()
                    results.append(
                        {
                            "token": token[:12] + "...",
                            "ok": True,
                            "name": response.json().get("name"),
                        }
                    )
                except Exception as exc:  # pragma: no cover
                    results.append(
                        {
                            "token": token[:12] + "...",
                            "ok": False,
                            "detail": str(exc),
                        }
                    )
        finally:
            if self.client is None:
                await http_client.aclose()

        ok = all(r["ok"] for r in results)
        return {
            "channel": self.name,
            "ok": ok,
            "detail": results,
        }
