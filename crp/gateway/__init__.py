# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Gateway service — SPEC-016.

The Gateway is the hosted reverse proxy that turns a single base-URL
change into full CRP governance on every AI call.  This package contains
the local implementation used for development and the self-hosted deployment
path (Railway / Docker).  The hosted managed service at
``gateway.crprotocol.io`` runs the same code.

Exports (lazy — heavy deps imported on first use):
    GatewayRequestLifecycle — 22-step request pipeline
    ProviderRouter           — routes to OpenAI / Anthropic / local
    KeyVault                 — per-tenant encrypted key storage
"""

from __future__ import annotations

from .api import GatewayRequestLifecycle, HaltResponse, handle_chat_completions
from .key_vault import KeyVault
from .router import ProviderRouter

__all__ = [
    "GatewayRequestLifecycle",
    "HaltResponse",
    "handle_chat_completions",
    "KeyVault",
    "ProviderRouter",
]
