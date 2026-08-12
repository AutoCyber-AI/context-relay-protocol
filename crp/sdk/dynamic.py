# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Dynamic SDK accessors for full CRP coverage (SPEC-032 advanced surface).

The curated namespace proxies in :mod:`crp.sdk.proxies` cover the most common
subsystems. This module provides two escape hatches that expose the remaining
1,400+ classes and 700+ functions without hand-writing a proxy for each:

* :attr:`CRPClient.orchestrator` — direct access to the live
  :class:`~crp.core.orchestrator.CRPOrchestrator` instance.
* :attr:`CRPClient.modules` — a dynamic mirror of the entire ``crp`` package.

These accessors are lazy, read-only, and block private names so the SDK surface
remains safe and predictable.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any

logger = logging.getLogger("crp.sdk.dynamic")


def _is_public(name: str) -> bool:
    """Return True if ``name`` is a public Python identifier."""
    return not name.startswith("_")


class _OrchestratorProxy:
    """Lazy proxy around the live ``CRPOrchestrator`` instance.

    Every attribute access is forwarded to the underlying orchestrator, except
    for private names (those starting with ``_``). This lets advanced users call
    any orchestrator method or subsystem directly while still operating inside
    the configured SDK session.

    Example::

        client = crp.SDKClient()
        client.orchestrator.dispatch(system_prompt="...", task_input="...")
        client.orchestrator.ckf.retrieve(query_embedding=...)
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def __getattr__(self, name: str) -> Any:
        if not _is_public(name):
            raise AttributeError(
                f"Private attribute '{name}' is not exposed on the SDK orchestrator proxy."
            )
        try:
            return getattr(self._orchestrator, name)
        except AttributeError as exc:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'. "
                "Use client.modules.<module> for classes/functions outside the orchestrator."
            ) from exc

    def __dir__(self) -> list[str]:
        return sorted(
            name for name in dir(self._orchestrator) if _is_public(name)
        )

    def __repr__(self) -> str:
        orch = self._orchestrator
        sid = getattr(getattr(orch, "_session", None), "session_id", "?")
        return f"<_OrchestratorProxy session={sid}>"


class _ModulesProxy:
    """Dynamic mirror of the ``crp`` Python package.

    This proxy walks the public attributes of a module lazily. Submodules are
    returned as nested ``_ModulesProxy`` instances; classes and functions are
    returned directly. It gives SDK users access to every documented public
    symbol without importing modules manually.

    Example::

        client = crp.SDKClient()
        CRPOrchestrator = client.modules.core.orchestrator.CRPOrchestrator
        cdr_rank = client.modules.envelope.cdr.cdr_rank
        ConsentManager = client.modules.security.consent.ConsentManager
    """

    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: Any | None = None

    def _load(self) -> Any:
        if self._module is None:
            try:
                self._module = importlib.import_module(self._module_name)
            except Exception as exc:
                raise AttributeError(
                    f"Could not import module '{self._module_name}' through the SDK proxy."
                ) from exc
        return self._module

    def __getattr__(self, name: str) -> Any:
        if not _is_public(name):
            raise AttributeError(
                f"Private attribute '{name}' is not exposed on the SDK modules proxy."
            )
        module = self._load()
        try:
            obj = getattr(module, name)
        except AttributeError:
            # Parent package may not re-export the child submodule; try importing
            # it directly (e.g. crp.core.circuit_breaker).
            try:
                obj = importlib.import_module(f"{self._module_name}.{name}")
            except Exception as exc:
                raise AttributeError(
                    f"Module '{self._module_name}' has no public attribute '{name}'."
                ) from exc

        # Nested modules become nested proxies.
        if inspect.ismodule(obj) and getattr(obj, "__name__", "").startswith("crp."):
            return _ModulesProxy(obj.__name__)

        # Classes and functions are returned as-is.
        return obj

    def __dir__(self) -> list[str]:
        module = self._load()
        return sorted(
            name
            for name in dir(module)
            if _is_public(name)
        )

    def __repr__(self) -> str:
        return f"<_ModulesProxy {self._module_name}>"


def _root_modules_proxy() -> _ModulesProxy:
    """Return the root modules proxy for the ``crp`` package."""
    return _ModulesProxy("crp")
