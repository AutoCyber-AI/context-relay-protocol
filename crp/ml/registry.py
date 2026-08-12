# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Managed ML model registry — lazy, budgeted, with deterministic fallbacks.

CRP's ML-driven components are **default-on** when their optional dependencies
are installed, but they are never allowed to block the governance loop.  The
registry loads models on first use, caches them, enforces a per-call latency
budget, and degrades to a rule-based fallback if the model is missing, slow, or
raises.  This makes ML enhancement mandatory-in-presence without storming
resources.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from functools import wraps
from typing import Any

logger = logging.getLogger("crp.ml.registry")


@dataclass
class ModelSpec:
    """Specification for a lazily-loaded model."""

    key: str
    loader: Callable[[], Any]
    budget_ms: float = 50.0          # default inference budget
    load_timeout_ms: float = 30000.0  # how long initial load may take
    device: str = "auto"
    cache_dir: str = ""


class ModelLoadError(Exception):
    """Raised when a model cannot be loaded within budget."""


class ModelManager:
    """Central registry for ML models used by CRP subsystems."""

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = {}
        self._models: dict[str, Any] = {}
        self._load_errors: set[str] = set()
        self._default_device: str = os.getenv("CRP_ML_DEVICE", "auto")
        self._default_cache_dir: str = os.getenv("CRP_ML_CACHE_DIR", "")
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="crp_ml_")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        key: str,
        loader: Callable[[], Any],
        *,
        budget_ms: float = 50.0,
        load_timeout_ms: float = 30000.0,
        device: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        """Register a model loader without loading it."""
        self._specs[key] = ModelSpec(
            key=key,
            loader=loader,
            budget_ms=budget_ms,
            load_timeout_ms=load_timeout_ms,
            device=device or self._default_device,
            cache_dir=cache_dir or self._default_cache_dir,
        )
        # Clear any previous error so re-registration can be retried.
        self._load_errors.discard(key)

    def unregister(self, key: str) -> None:
        """Drop a model from the registry and release its instance."""
        self._specs.pop(key, None)
        self._models.pop(key, None)
        self._load_errors.discard(key)

    def is_registered(self, key: str) -> bool:
        return key in self._specs

    def is_available(self, key: str) -> bool:
        """True if the model is currently loaded and usable."""
        return key in self._models and key not in self._load_errors

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, key: str) -> Any | None:
        """Load (or return cached) the model for ``key``.

        Returns ``None`` if the model is not registered, already failed, or
        cannot be loaded within its load budget.  Never raises.
        """
        if key in self._models:
            return self._models[key]
        if key in self._load_errors:
            return None
        spec = self._specs.get(key)
        if spec is None:
            return None
        try:
            model = self._load_with_timeout(spec)
            if model is not None:
                self._models[key] = model
                logger.debug("Loaded model %s", key)
                return model
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load model %s: %s", key, exc)
        self._load_errors.add(key)
        return None

    def _load_with_timeout(self, spec: ModelSpec) -> Any:
        """Run the loader in a thread with a timeout."""
        timeout = max(1.0, spec.load_timeout_ms / 1000.0)
        future = self._executor.submit(spec.loader)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise ModelLoadError(f"loading {spec.key} exceeded {spec.load_timeout_ms}ms") from None

    # ------------------------------------------------------------------
    # Budgeted inference
    # ------------------------------------------------------------------

    def run(
        self,
        key: str,
        fn: Callable[[Any], Any],
        *,
        budget_ms: float | None = None,
        fallback: Any = None,
    ) -> Any:
        """Run ``fn(model)`` under a latency budget.

        Args:
            key: Registered model key.
            fn: Callable receiving the loaded model and returning a result.
            budget_ms: Per-call budget. Defaults to the registered spec budget.
            fallback: Value returned if model is unavailable or fn exceeds budget.

        Returns:
            ``fn(model)`` result, or ``fallback`` on any budget/availability issue.
        """
        model = self.load(key)
        if model is None:
            return fallback
        spec = self._specs.get(key)
        budget = budget_ms if budget_ms is not None else (spec.budget_ms if spec else 50.0)

        start = time.perf_counter()
        try:
            future = self._executor.submit(fn, model)
            result = future.result(timeout=max(0.001, budget / 1000.0))
            elapsed = (time.perf_counter() - start) * 1000.0
            if elapsed > budget:
                logger.debug("Model %s inference exceeded budget (%.1fms > %.1fms)", key, elapsed, budget)
            return result
        except TimeoutError:
            logger.debug("Model %s inference timed out after %.1fms", key, budget)
            return fallback
        except Exception as exc:  # noqa: BLE001
            logger.debug("Model %s inference raised: %s", key, exc)
            return fallback

    def clear(self) -> None:
        """Unload all models and reset error state."""
        self._models.clear()
        self._load_errors.clear()

    def reset(self, key: str) -> None:
        """Unload the model for ``key`` while keeping its registered spec.

        Useful for test isolation: the loader stays registered so the next
        call to :meth:`load` or :meth:`run` will re-load the model.
        """
        self._models.pop(key, None)
        self._load_errors.discard(key)

    def shutdown(self) -> None:
        """Release resources."""
        self.clear()
        self._executor.shutdown(wait=False)


# Module-level singleton.  Tests can replace or clear it.
MANAGER = ModelManager()


def managed_call(
    key: str,
    fn: Callable[[Any], Any],
    *,
    budget_ms: float | None = None,
    fallback: Any = None,
) -> Any:
    """Convenience wrapper around the global manager."""
    return MANAGER.run(key, fn, budget_ms=budget_ms, fallback=fallback)


def register_model(
    key: str,
    loader: Callable[[], Any],
    *,
    budget_ms: float = 50.0,
    load_timeout_ms: float = 30000.0,
) -> None:
    """Convenience wrapper to register a model on the global manager."""
    MANAGER.register(key, loader, budget_ms=budget_ms, load_timeout_ms=load_timeout_ms)


def timed_fallback(
    budget_ms: float, fallback: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that runs a function under ``budget_ms`` and returns ``fallback`` on timeout.

    The wrapped function receives the model as its first argument; the model is
    fetched from the registry using the argument name ``model_key`` if present.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            model_key = kwargs.pop("model_key", None)
            if model_key is None and args:
                model_key = args[0]
                args = args[1:]
            if model_key is None:
                return fallback
            return MANAGER.run(
                model_key,
                lambda model: fn(model, *args, **kwargs),
                budget_ms=budget_ms,
                fallback=fallback,
            )

        return wrapper

    return decorator
