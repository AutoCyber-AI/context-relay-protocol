# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Checkpoint alerting example (SPEC-033 §3, SPEC-034).

Demonstrates how a CRP agent notifies configured review channels when a
human-in-the-loop checkpoint fires.

Channels are configured via the ``CRP_MCP_CHECKPOINT_CONNECTORS`` environment
variable. The ``console`` connector is always enabled. Additional connectors:

  webhook  - set ``CRP_MCP_CHECKPOINT_WEBHOOK_URL``
  slack    - set ``CRP_MCP_CHECKPOINT_SLACK_WEBHOOK_URL``
  email    - set ``CRP_MCP_CHECKPOINT_EMAIL_FROM/TO/SMTP_*``
  gmail    - set ``CRP_MCP_CHECKPOINT_GMAIL_USER/APP_PASSWORD``
  pagerduty - set ``CRP_MCP_CHECKPOINT_PAGERDUTY_ROUTING_KEY``
  sms      - set ``CRP_MCP_CHECKPOINT_SMS_*``
  fcm      - set ``CRP_MCP_CHECKPOINT_FCM_*``
  comply   - set ``CRP_MCP_BACKEND_URL`` and ``CRP_MCP_API_KEY``

Usage::

    # Console only
    python examples/checkpoint_alerts.py

    # Console + webhook
    set CRP_MCP_CHECKPOINT_CONNECTORS=console,webhook
    set CRP_MCP_CHECKPOINT_WEBHOOK_URL=https://httpbin.org/post
    python examples/checkpoint_alerts.py

The checkpoint triggers because the agent is asked to perform a destructive
operation and no human reviewer is present to approve it; after the configured
timeout it auto-resolves as rejected and the run returns a graceful fallback.
"""

from __future__ import annotations

import os

import crp
from crp.security.checkpoint import Checkpoint, CheckpointTimeoutAction


def main() -> None:
    os.environ.setdefault("CRP_MCP_CHECKPOINT_CONNECTORS", "console")

    def delete_database(database_name: str) -> dict:
        """Delete a database. Destructive — requires human approval."""
        return {"deleted": database_name, "status": "confirmed"}

    # A checkpoint with a short timeout for demo purposes.
    checkpoint = Checkpoint(
        trigger=crp.security.checkpoint.CheckpointTrigger.RISK_HIGH,
        timeout=5,
        on_timeout=CheckpointTimeoutAction.REJECT,
    )

    agent = crp.Agent(
        model="local/llama3.1",
        tools=[delete_database],
        checkpoint=checkpoint,
        oversight_required={crp.tools.descriptor.SafetyClass.DESTRUCTIVE},
        system="You are a careful database administrator. Never delete anything without approval.",
    )

    result = agent.run("Delete the production database 'customers'.")
    print("Answer:", result.answer)
    print("Halted:", result.halted)
    print("Risk:", result.crp.risk)


if __name__ == "__main__":
    main()
