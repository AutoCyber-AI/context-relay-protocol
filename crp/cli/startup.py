# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP startup sequence — 6 steps per §09 §9.5.

Step 1: Resolve config     (5-layer, ~1 ms)
Step 2: Validate config    (type checks, ~5 ms)
Step 3: Authenticate app   (HMAC handshake, ~1 ms)
Step 4: Connect to LLM     (health check, ~200–500 ms cloud)
Step 5: Init session state  (warm store + event log, ~5–50 ms)
Step 6: Start event emitter (~1 ms)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.startup")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class StartupStep:
    """Result of one startup step."""

    step: int
    name: str
    ok: bool = True
    latency_ms: float = 0.0
    detail: str = ""


@dataclass
class StartupResult:
    """Aggregate result of the startup sequence."""

    steps: list[StartupStep] = field(default_factory=list)
    total_ms: float = 0.0

    @property
    def ok(self) -> bool:
        """Return whether the ok condition holds."""
        return all(s.ok for s in self.steps)

    @property
    def summary(self) -> dict[str, Any]:
        """Return the summary."""
        return {
            "ok": self.ok,
            "total_ms": round(self.total_ms, 2),
            "steps": [
                {"step": s.step, "name": s.name, "ok": s.ok,
                 "ms": round(s.latency_ms, 2)}
                for s in self.steps
            ],
        }


# ---------------------------------------------------------------------------
# Startup runner
# ---------------------------------------------------------------------------


def run_startup(
    *,
    provider: Any | None = None,
    config_overrides: dict[str, Any] | None = None,
    binding_secret: bytes | None = None,
    skip_auth: bool = False,
    skip_health: bool = False,
) -> tuple[StartupResult, dict[str, Any]]:
    """Execute the 6-step startup sequence.

    Returns ``(result, context)`` where *context* is a dict of resolved
    objects: ``config``, ``provider``, ``binding``, ``warm_store``,
    ``emitter``, ``session``.
    """
    ctx: dict[str, Any] = {}
    steps: list[StartupStep] = []
    t0 = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1 — Resolve config (5-layer hierarchy)
    # ------------------------------------------------------------------
    t = time.monotonic()
    try:
        from crp.core.config import ConfigurationResolver

        config = ConfigurationResolver().resolve(**(config_overrides or {}))
        ctx["config"] = config
        steps.append(StartupStep(
            step=1, name="resolve_config",
            latency_ms=_elapsed(t),
        ))
    except Exception as exc:
        steps.append(StartupStep(
            step=1, name="resolve_config", ok=False,
            latency_ms=_elapsed(t), detail=str(exc),
        ))
        return StartupResult(steps=steps, total_ms=_elapsed(t0)), ctx

    # ------------------------------------------------------------------
    # Step 2 — Validate config
    # ------------------------------------------------------------------
    t = time.monotonic()
    try:
        _validate_config(config)
        steps.append(StartupStep(
            step=2, name="validate_config",
            latency_ms=_elapsed(t),
        ))
    except Exception as exc:
        steps.append(StartupStep(
            step=2, name="validate_config", ok=False,
            latency_ms=_elapsed(t), detail=str(exc),
        ))
        return StartupResult(steps=steps, total_ms=_elapsed(t0)), ctx

    # ------------------------------------------------------------------
    # Step 3 — Authenticate (HMAC session binding)
    # ------------------------------------------------------------------
    t = time.monotonic()
    if skip_auth:
        steps.append(StartupStep(
            step=3, name="authenticate", latency_ms=_elapsed(t),
            detail="skipped",
        ))
    else:
        try:
            from crp.security.binding import SessionBindingManager

            secret = binding_secret or config.get("binding_secret", "").encode()
            mgr = SessionBindingManager(master_secret=secret or None)
            binding = mgr.create_session()
            ctx["binding"] = binding
            steps.append(StartupStep(
                step=3, name="authenticate",
                latency_ms=_elapsed(t),
            ))
        except Exception as exc:
            steps.append(StartupStep(
                step=3, name="authenticate", ok=False,
                latency_ms=_elapsed(t), detail=str(exc),
            ))

    # ------------------------------------------------------------------
    # Step 4 — Connect to LLM (health check)
    # ------------------------------------------------------------------
    t = time.monotonic()
    if provider is None or skip_health:
        ctx["provider"] = provider
        steps.append(StartupStep(
            step=4, name="connect_llm", latency_ms=_elapsed(t),
            detail="skipped" if skip_health else "no provider",
        ))
    else:
        try:
            from crp.providers.diagnostic import ProviderDiagnostic

            report = ProviderDiagnostic().diagnose(provider)
            ctx["provider"] = provider
            ctx["diagnostic"] = report
            steps.append(StartupStep(
                step=4, name="connect_llm",
                ok=report.all_passed,
                latency_ms=_elapsed(t),
                detail="" if report.all_passed else "health check failed",
            ))
        except Exception as exc:
            ctx["provider"] = provider
            steps.append(StartupStep(
                step=4, name="connect_llm", ok=False,
                latency_ms=_elapsed(t), detail=str(exc),
            ))

    # ------------------------------------------------------------------
    # Step 5 — Initialize session state (warm store + event log)
    # ------------------------------------------------------------------
    t = time.monotonic()
    try:
        from crp.state.event_log import FactEventLog
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        event_log = FactEventLog()
        ctx["warm_store"] = store
        ctx["event_log"] = event_log
        steps.append(StartupStep(
            step=5, name="init_session_state",
            latency_ms=_elapsed(t),
        ))
    except Exception as exc:
        steps.append(StartupStep(
            step=5, name="init_session_state", ok=False,
            latency_ms=_elapsed(t), detail=str(exc),
        ))

    # ------------------------------------------------------------------
    # Step 6 — Start event emitter
    # ------------------------------------------------------------------
    t = time.monotonic()
    try:
        from crp.observability.events import EventEmitter

        emitter = EventEmitter()
        emitter.start()
        ctx["emitter"] = emitter
        steps.append(StartupStep(
            step=6, name="start_event_emitter",
            latency_ms=_elapsed(t),
        ))
    except Exception as exc:
        steps.append(StartupStep(
            step=6, name="start_event_emitter", ok=False,
            latency_ms=_elapsed(t), detail=str(exc),
        ))

    result = StartupResult(steps=steps, total_ms=_elapsed(t0))
    logger.info(
        "Startup %s in %.1f ms (%d steps)",
        "OK" if result.ok else "FAILED",
        result.total_ms,
        len(steps),
    )
    return result, ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elapsed(start: float) -> float:
    return (time.monotonic() - start) * 1000


# JSON-Schema-style validation rules for CRP config.
_CONFIG_SCHEMA: list[dict] = [
    {"field": "session_timeout", "type": (int, float), "min_exclusive": 0,
     "error": "session_timeout must be positive"},
    {"field": "max_continuations", "type": (int,), "min": 0,
     "error": "max_continuations must be non-negative int"},
    {"field": "max_ram_mb", "type": (int, float), "min_exclusive": 0,
     "default": 512, "error": "max_ram_mb must be positive"},
]


def _validate_config(config: Any) -> None:
    """Schema-driven config validation (step 2).

    Each rule in ``_CONFIG_SCHEMA`` is checked in order.  This keeps
    validation declarative and easy to extend.
    """
    for rule in _CONFIG_SCHEMA:
        fname = rule["field"]
        value = config.get(fname, rule.get("default"))
        if value is None:
            continue  # optional field not provided

        # Type check
        if not isinstance(value, rule["type"]):
            raise ValueError(f"{rule['error']}: got {value!r}")

        # Range checks
        if "min_exclusive" in rule and value <= rule["min_exclusive"]:
            raise ValueError(f"{rule['error']}: got {value!r}")
        if "min" in rule and value < rule["min"]:
            raise ValueError(f"{rule['error']}: got {value!r}")
