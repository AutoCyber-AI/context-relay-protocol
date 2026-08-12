# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Anthropic client wrapper with CRP context enforcement (CRP 2.3)."""

from __future__ import annotations

from typing import Any

from crp.core.context_enforcer import ContextEnforcer
from crp.core.context_source import ContextManifest

from ._common import enforce_messages, normalise_anthropic_messages

__all__ = ["wrap_anthropic"]


class _MessagesProxy:
    def __init__(
        self,
        inner: Any,
        enforcer: ContextEnforcer | None,
        manifest: ContextManifest | None,
        session_id: str | None,
    ) -> None:
        self._inner = inner
        self._enforcer = enforcer
        self._manifest = manifest
        self._session_id = session_id

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Execute create and return the result.
        
            Args:
                *args: Variable positional arguments.
                **kwargs: Variable keyword arguments.
        
            Returns:
                ``Any``.
        """
        system = kwargs.get("system")
        messages = kwargs.get("messages") or []
        enforce_messages(
            normalise_anthropic_messages(system, messages),
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
        return self._inner.create(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        """Execute stream and return the result.
        
            Args:
                *args: Variable positional arguments.
                **kwargs: Variable keyword arguments.
        
            Returns:
                ``Any``.
        """
        system = kwargs.get("system")
        messages = kwargs.get("messages") or []
        enforce_messages(
            normalise_anthropic_messages(system, messages),
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
        return self._inner.stream(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


class _AnthropicClientProxy:
    def __init__(
        self,
        inner: Any,
        enforcer: ContextEnforcer | None,
        manifest: ContextManifest | None,
        session_id: str | None,
    ) -> None:
        self.__dict__["_inner"] = inner
        self.__dict__["_messages"] = _MessagesProxy(
            inner.messages, enforcer, manifest, session_id
        )

    @property
    def messages(self) -> _MessagesProxy:
        """Return the messages."""
        return self.__dict__["_messages"]

    def __getattr__(self, item: str) -> Any:
        return getattr(self.__dict__["_inner"], item)


def wrap_anthropic(
    client: Any,
    *,
    enforcer: ContextEnforcer | None = None,
    manifest: ContextManifest | None = None,
    session_id: str | None = None,
) -> Any:
    """Return a proxy around an ``anthropic.Anthropic`` / ``anthropic.AsyncAnthropic`` client.

    Every call to ``client.messages.create(...)`` /
    ``client.messages.stream(...)`` is preceded by
    :meth:`ContextEnforcer.check_messages`. The ``system=`` parameter and
    the ``messages=`` list are unified into a single chat history for
    uniform derivation.
    """
    return _AnthropicClientProxy(client, enforcer, manifest, session_id)
