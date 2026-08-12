# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Derive context sources/manifests from raw message content (CRP 2.3).

Problem
-------
CRP 2.1/2.2 manifests are **declarative** — the integrator must author
them.  A malicious or lazy integrator who never calls
:meth:`ContextManifest.add` receives no enforcement benefit.  The
enforcer cannot distinguish "no manifest because this turn is
genuinely ephemeral" from "no manifest because the caller is hostile".

Solution
--------
Given any list of chat messages (``[{"role": ..., "content": ...}]``),
derive a :class:`ContextManifest` by hashing the content of each
message and emitting a :class:`ContextSource` with role-appropriate
defaults:

=====================  ==========================  ===============
``role``               :class:`SourceKind`         :class:`TrustLevel`
=====================  ==========================  ===============
``system``             ``SYSTEM_PROMPT``           ``TRUSTED``
``developer``          ``DEVELOPER_PROMPT``        ``TRUSTED``
``user``               ``USER_TURN``               ``UNKNOWN``
``assistant``          ``PARAMETRIC``              ``UNKNOWN``
``tool`` / ``function``  ``FUNCTION_CALL``         ``UNKNOWN``
other                  ``UNATTESTED``              ``UNKNOWN``
=====================  ==========================  ===============

The resulting manifest is *not signed by default* — signing it would
misrepresent the trust: derivation says "this is what came through the
wire", not "a human declared this is safe".  When the caller opts in
via ``sign_with=``, the signature covers exactly the content the
derivation saw.

The content hash lives in each source's ``metadata["content_sha256"]``
so downstream audit systems can correlate a manifest entry back to the
raw message it was produced from.

Every source derived here is stamped ``origin=OBSERVED`` so it is
distinguishable from ``DECLARED`` sources in a human-authored manifest.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .context_source import (
    ContextManifest,
    ContextSource,
    SourceKind,
    SourceOrigin,
    TrustLevel,
)

__all__ = [
    "content_hash",
    "derive_source_from_message",
    "derive_sources_from_messages",
    "derive_manifest_from_messages",
    "source_id_for_role",
]


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def content_hash(text: str, *, algo: str = "sha256") -> str:
    """Return ``"{algo}:{hex}"`` for *text*. Stable across processes."""
    if not isinstance(text, str):
        raise TypeError("content_hash expects str")
    h = hashlib.new(algo)
    h.update(text.encode("utf-8"))
    return f"{algo}:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# Role → (SourceKind, TrustLevel) mapping
# ---------------------------------------------------------------------------


_ROLE_MAP: dict[str, tuple[SourceKind, TrustLevel]] = {
    "system": (SourceKind.SYSTEM_PROMPT, TrustLevel.TRUSTED),
    "developer": (SourceKind.DEVELOPER_PROMPT, TrustLevel.TRUSTED),
    "user": (SourceKind.USER_TURN, TrustLevel.UNKNOWN),
    "assistant": (SourceKind.PARAMETRIC, TrustLevel.UNKNOWN),
    "tool": (SourceKind.FUNCTION_CALL, TrustLevel.UNKNOWN),
    "function": (SourceKind.FUNCTION_CALL, TrustLevel.UNKNOWN),
    "tool_result": (SourceKind.FUNCTION_CALL, TrustLevel.UNKNOWN),
}


def source_id_for_role(role: str, index: int, *, session_id: str | None = None) -> str:
    """Return a stable, human-readable source_id for a derived message source."""
    scope = session_id or "ad-hoc"
    return f"derived:{scope}:{role}:{index}"


def _flatten_content(content: Any) -> str:
    """Normalise message ``content`` to a string.

    OpenAI/Anthropic message contents may be ``str`` *or* a list of
    content blocks (``[{"type": "text", "text": "..."}]``). We stringify
    each block's ``text`` / ``content`` in order.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
                inner = block.get("content")
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, (list, tuple)):
                    parts.append(_flatten_content(inner))
        return "\n".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# Derivation API
# ---------------------------------------------------------------------------


def derive_source_from_message(
    message: Mapping[str, Any],
    *,
    index: int = 0,
    session_id: str | None = None,
    default_trust: TrustLevel | None = None,
) -> tuple[ContextSource, str]:
    """Return ``(source, content_text)`` for one chat message.

    Parameters
    ----------
    message
        A chat message dict with at least a ``role`` and ``content`` key.
        Follows OpenAI chat-completions convention; Anthropic messages
        (which omit ``role`` on the server's ``system`` parameter) should
        be normalised by the caller before invocation.
    index
        Position within the originating message list — used to build a
        stable ``source_id``.
    session_id
        Optional session scope; included in the ``source_id``.
    default_trust
        Overrides the role-default trust for all messages (useful when
        the caller already knows e.g. every user turn is untrusted).
    """
    role = str(message.get("role", "")).lower()
    kind, trust = _ROLE_MAP.get(role, (SourceKind.UNATTESTED, TrustLevel.UNKNOWN))
    if default_trust is not None:
        trust = default_trust
    text = _flatten_content(message.get("content"))
    chash = content_hash(text) if text else "sha256:"
    metadata: dict[str, Any] = {
        "content_sha256": chash,
        "content_len": len(text),
        "role": role,
    }
    # Carry tool_call_id / name when present — vital for function-calling traces.
    for extra in ("tool_call_id", "name", "tool_use_id"):
        val = message.get(extra)
        if isinstance(val, str) and val:
            metadata[extra] = val[:128]
    source = ContextSource(
        kind=kind,
        source_id=source_id_for_role(role or "unknown", index, session_id=session_id),
        origin=SourceOrigin.OBSERVED,
        trust_level=trust,
        retrieved_at=time.time(),
        metadata=metadata,
    )
    return source, text


def derive_sources_from_messages(
    messages: Sequence[Mapping[str, Any]],
    *,
    session_id: str | None = None,
    default_trust: TrustLevel | None = None,
) -> list[tuple[ContextSource, str]]:
    """Derive one ``(source, content)`` pair per message."""
    out: list[tuple[ContextSource, str]] = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, Mapping):
            continue
        out.append(
            derive_source_from_message(
                msg,
                index=i,
                session_id=session_id,
                default_trust=default_trust,
            )
        )
    return out


def derive_manifest_from_messages(
    messages: Sequence[Mapping[str, Any]],
    *,
    session_id: str | None = None,
    system_id: str = "",
    customer_id: str = "",
    default_trust: TrustLevel | None = None,
    sign_with: bytes | None = None,
) -> ContextManifest:
    """Build a :class:`ContextManifest` from raw chat messages.

    Each message becomes one declared source; the full content hash is
    captured in ``source.metadata["content_sha256"]`` so the manifest is
    replayable against the exact bytes that crossed the wire.

    Passing ``sign_with=`` yields a signed manifest — the signature
    attests only that these specific bytes passed through derivation,
    *not* that a human reviewed them.
    """
    manifest = ContextManifest(
        system_id=system_id,
        customer_id=customer_id,
    )
    for src, _content in derive_sources_from_messages(
        messages, session_id=session_id, default_trust=default_trust
    ):
        manifest.add(src)
    if sign_with is not None:
        manifest.sign(sign_with)
    return manifest
