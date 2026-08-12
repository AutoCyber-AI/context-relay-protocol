# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP MCP server — local stdio knowledge + hosted account-linked assistance."""

from __future__ import annotations

import os

__version__ = "4.0.0"

MODE_LOCAL = "local"
MODE_HOSTED = "hosted"


def get_mode() -> str:
    """Return the configured server mode (``local`` or ``hosted``)."""
    mode = os.getenv("CRP_MCP_MODE", MODE_LOCAL).lower().strip()
    return mode if mode in {MODE_LOCAL, MODE_HOSTED} else MODE_LOCAL
