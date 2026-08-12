# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared helpers for the CRP integration wrappers (CRP 2.3)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from crp.core.context_enforcer import ContextEnforcer, default_enforcer
from crp.core.context_source import ContextManifest

_log = logging.getLogger("crp.integrations")


def resolve_enforcer(enforcer: ContextEnforcer | None) -> ContextEnforcer | None:
    """Return the effective enforcer: explicit > process default > None."""
    return enforcer if enforcer is not None else default_enforcer()


def enforce_messages(
    messages: Sequence[dict[str, Any]],
    *,
    enforcer: ContextEnforcer | None = None,
    manifest: ContextManifest | None = None,
    session_id: str | None = None,
    derive: bool = True,
) -> None:
    """Run the enforcer over an outgoing chat-completions payload.

    No-op when no enforcer is installed. Raises
    :class:`crp.core.errors.CRPError` if the active enforcer is in
    REJECT mode and a violation occurs — by design, this stops the
    outbound HTTP call before secrets leave the process.
    """
    active = resolve_enforcer(enforcer)
    if active is None:
        return
    if not messages:
        return
    active.check_messages(
        list(messages),
        manifest=manifest,
        session_id=session_id,
        derive_manifest=derive and manifest is None,
    )


def normalise_anthropic_messages(
    system: Any,
    messages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Re-shape Anthropic's (``system=``, ``messages=``) into OpenAI-style
    ``[{"role": "system"...}, ...]`` for uniform derivation."""
    out: list[dict[str, Any]] = []
    if system:
        if isinstance(system, str):
            out.append({"role": "system", "content": system})
        elif isinstance(system, list):
            # Anthropic supports list-of-blocks for system too
            out.append({"role": "system", "content": system})
    for m in messages:
        if isinstance(m, dict):
            out.append(dict(m))
    return out
