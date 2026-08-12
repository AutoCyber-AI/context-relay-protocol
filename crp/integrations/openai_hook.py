# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""OpenAI client wrapper with CRP context enforcement (CRP 2.3).

Usage::

    from openai import OpenAI
    from crp.integrations import wrap_openai
    from crp.core.context_enforcer import ContextEnforcer, EnforcementPolicy, set_default_enforcer

    set_default_enforcer(ContextEnforcer(policy=EnforcementPolicy.REJECT))

    client = wrap_openai(OpenAI())
    # Every client.chat.completions.create(...) now runs the enforcer.
    resp = client.chat.completions.create(model="gpt-4o", messages=[...])

The wrapper is a shallow proxy — attribute access falls through to the
real client, so unsupported methods are unaffected. Only
``chat.completions.create`` and ``responses.create`` are intercepted.
"""

from __future__ import annotations

from typing import Any

from crp.core.context_enforcer import ContextEnforcer
from crp.core.context_source import ContextManifest

from ._common import enforce_messages

__all__ = ["wrap_openai"]


class _ChatCompletionsProxy:
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
        messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
        enforce_messages(
            messages,
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
        return self._inner.create(*args, **kwargs)

    async def acreate(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        """Execute acreate and return the result.
        
            Args:
                *args: Variable positional arguments.
                **kwargs: Variable keyword arguments.
        
            Returns:
                ``Any``.
        """
        messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
        enforce_messages(
            messages,
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
        return await self._inner.acreate(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


class _ChatProxy:
    def __init__(
        self,
        inner: Any,
        enforcer: ContextEnforcer | None,
        manifest: ContextManifest | None,
        session_id: str | None,
    ) -> None:
        self._inner = inner
        self._completions = _ChatCompletionsProxy(
            inner.completions, enforcer, manifest, session_id
        )

    @property
    def completions(self) -> _ChatCompletionsProxy:
        """Return the completions."""
        return self._completions

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


class _ResponsesProxy:
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
        # Responses API uses ``input=`` instead of ``messages=``; support both.
        msgs = kwargs.get("messages") or kwargs.get("input") or []
        # ``input`` may be a bare string — wrap it as a user message.
        if isinstance(msgs, str):
            msgs = [{"role": "user", "content": msgs}]
        enforce_messages(
            msgs,
            enforcer=self._enforcer,
            manifest=self._manifest,
            session_id=self._session_id,
        )
        return self._inner.create(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


class _OpenAIClientProxy:
    def __init__(
        self,
        inner: Any,
        enforcer: ContextEnforcer | None,
        manifest: ContextManifest | None,
        session_id: str | None,
    ) -> None:
        self.__dict__["_inner"] = inner
        self.__dict__["_chat"] = _ChatProxy(inner.chat, enforcer, manifest, session_id)
        # ``responses`` is optional (newer API) — build proxy only if present.
        if hasattr(inner, "responses"):
            self.__dict__["_responses"] = _ResponsesProxy(
                inner.responses, enforcer, manifest, session_id
            )

    @property
    def chat(self) -> _ChatProxy:
        """Return the chat."""
        return self.__dict__["_chat"]

    @property
    def responses(self) -> _ResponsesProxy:
        """Return the responses."""
        resp = self.__dict__.get("_responses")
        if resp is None:
            raise AttributeError("This OpenAI client does not expose 'responses'")
        return resp

    def __getattr__(self, item: str) -> Any:
        return getattr(self.__dict__["_inner"], item)

    def __setattr__(self, key: str, value: Any) -> None:
        setattr(self.__dict__["_inner"], key, value)


def wrap_openai(
    client: Any,
    *,
    enforcer: ContextEnforcer | None = None,
    manifest: ContextManifest | None = None,
    session_id: str | None = None,
) -> Any:
    """Return a proxy around an ``openai.OpenAI`` / ``openai.AsyncOpenAI`` client.

    Every call to ``client.chat.completions.create(...)`` (and
    ``client.responses.create(...)`` when available) is preceded by
    :meth:`ContextEnforcer.check_messages`. No enforcement happens when
    no enforcer is installed.
    """
    return _OpenAIClientProxy(client, enforcer, manifest, session_id)
