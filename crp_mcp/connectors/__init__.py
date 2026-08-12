# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Checkpoint review-channel connectors."""

from __future__ import annotations

import os

from crp_mcp.connectors.base import CheckpointConnector
from crp_mcp.connectors.comply import ComplyConnector
from crp_mcp.connectors.console import ConsoleConnector
from crp_mcp.connectors.email import EmailConnector
from crp_mcp.connectors.fcm import FCMConnector
from crp_mcp.connectors.gmail import GmailConnector
from crp_mcp.connectors.pagerduty import PagerDutyConnector
from crp_mcp.connectors.slack import SlackConnector
from crp_mcp.connectors.sms import SMSConnector
from crp_mcp.connectors.webhook import WebhookConnector

_CONNECTOR_CLASSES: dict[str, type[CheckpointConnector]] = {
    "console": ConsoleConnector,
    "comply": ComplyConnector,
    "webhook": WebhookConnector,
    "slack": SlackConnector,
    "email": EmailConnector,
    "gmail": GmailConnector,
    "fcm": FCMConnector,
    "pagerduty": PagerDutyConnector,
    "sms": SMSConnector,
}


def get_configured_connectors(
    names: str | None = None,
) -> list[CheckpointConnector]:
    """Return the configured checkpoint connectors.

    ``names`` is a comma-separated list of connector names.  When omitted it is
    read from ``CRP_MCP_CHECKPOINT_CONNECTORS``.  The ``console`` connector is
    always included as a safe default.
    """
    raw = (names or os.environ.get("CRP_MCP_CHECKPOINT_CONNECTORS", "console"))
    requested = {n.strip().lower() for n in raw.split(",") if n.strip()}
    requested.add("console")

    connectors: list[CheckpointConnector] = []
    for name in sorted(requested):
        cls = _CONNECTOR_CLASSES.get(name)
        if cls is None:
            continue
        connector = cls()
        if connector.is_configured() or name == "console":
            connectors.append(connector)
    return connectors


__all__ = [
    "CheckpointConnector",
    "ComplyConnector",
    "ConsoleConnector",
    "EmailConnector",
    "FCMConnector",
    "GmailConnector",
    "get_configured_connectors",
    "PagerDutyConnector",
    "SlackConnector",
    "SMSConnector",
    "WebhookConnector",
]
