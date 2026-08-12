# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""LangChain callback for CRP context enforcement (CRP 2.3).

Usage::

    from langchain_openai import ChatOpenAI
    from crp.integrations import CRPContextCallback

    llm = ChatOpenAI(
        model="gpt-4o",
        callbacks=[CRPContextCallback()],
    )

The callback hooks ``on_chat_model_start`` and ``on_llm_start`` — both
fire before the outbound request is built.  If the default enforcer is
in REJECT mode and a violation is detected, the callback raises
:class:`crp.core.errors.CRPError`, which LangChain propagates as a
chain failure.

The implementation avoids any hard dependency on the langchain package.
When ``langchain_core.callbacks.BaseCallbackHandler`` is not importable,
:class:`CRPContextCallback` is defined as a plain object that still
exposes the hook methods — LangChain duck-types callbacks by attribute
name, so integrators on older versions still work.
"""

from __future__ import annotations

from typing import Any

from crp.core.context_enforcer import ContextEnforcer
from crp.core.context_source import ContextManifest

from ._common import enforce_messages

__all__ = ["CRPContextCallback"]


try:  # pragma: no cover - exercised only when langchain is installed
    from langchain_core.callbacks import BaseCallbackHandler as _Base  # type: ignore
except Exception:  # pragma: no cover - fallback path
    class _Base:  # type: ignore[no-redef]
        """Minimal shim when langchain_core is not installed."""


def _messages_from_lc_input(
    messages: Any,
    prompts: Any,
) -> list[dict[str, Any]]:
    """Normalise LangChain's callback payloads into an OpenAI-style list."""
    out: list[dict[str, Any]] = []
    if messages:
        # ``messages`` is a list-of-lists (one per request) of BaseMessage.
        try:
            batch = messages[0] if messages and isinstance(messages, list) else messages
        except Exception:
            batch = messages
        for m in batch or []:
            role = getattr(m, "type", None) or getattr(m, "role", None) or "user"
            content = getattr(m, "content", None)
            if content is None and hasattr(m, "__dict__"):
                content = m.__dict__.get("content")
            out.append({"role": str(role), "content": content if content is not None else ""})
        return out
    if prompts:
        for p in prompts:
            out.append({"role": "user", "content": str(p)})
    return out


class CRPContextCallback(_Base):
    """LangChain callback that runs the CRP enforcer before each LLM call."""

    raise_on_violation: bool = True

    def __init__(
        self,
        *,
        enforcer: ContextEnforcer | None = None,
        manifest: ContextManifest | None = None,
        session_id: str | None = None,
    ) -> None:
        try:
            super().__init__()  # type: ignore[misc]
        except Exception:
            pass
        self._enforcer = enforcer
        self._manifest = manifest
        self._session_id = session_id

    # ---- chat-model path ---------------------------------------------------
    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        """Run the CRP enforcer before a chat-model call starts.

        Args:
            serialized: LangChain serialized model info.
            messages: LangChain message payload (list of lists).
            **kwargs: Additional LangChain callback arguments.
        """
        enforce_messages(
            _messages_from_lc_input(messages, None),
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )

    # ---- completion-style path --------------------------------------------
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Run the CRP enforcer before a completion-style LLM call starts.

        Args:
            serialized: LangChain serialized model info.
            prompts: Raw prompt strings for the LLM call.
            **kwargs: Additional LangChain callback arguments.
        """
        enforce_messages(
            _messages_from_lc_input(None, prompts),
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
