# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Metrics export and health monitoring (§8.9, §05).

MetricsExporter  — collects counters/gauges and exports as Prometheus,
                   OTLP-compatible JSON, or plain JSON.
HealthMonitor    — liveness + readiness probes for the CRP runtime.

Design goals:
  * Zero external dependencies (no prometheus_client, no opentelemetry).
  * Thread-safe counters via stdlib threading.Lock.
  * Easy to read: one class per concern, plain dicts for state.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# MetricsExporter (§9.2)
# ═══════════════════════════════════════════════════════════════════════════


class ExportFormat(Enum):
    """Supported output formats."""

    JSON = "json"
    PROMETHEUS = "prometheus"
    OTLP_JSON = "otlp_json"


class MetricsExporter:
    """Collects CRP metrics (counters, gauges, histograms) and exports them.

    Usage::

        mx = MetricsExporter()
        mx.incr("dispatch.count")
        mx.gauge("overhead.ratio", 0.12)
        mx.observe("dispatch.latency_ms", 42.3)
        print(mx.export(ExportFormat.JSON))
    """

    _MAX_HISTOGRAM_SIZE = 10_000  # Cap per-metric observations to prevent unbounded growth

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Counters: monotonically increasing integers.
        self._counters: dict[str, int] = {}
        # Gauges: point-in-time values that can go up or down.
        self._gauges: dict[str, float] = {}
        # Histograms: list of observed values (for percentiles).
        self._histograms: dict[str, list[float]] = {}

    # -- recording --------------------------------------------------------

    def incr(self, name: str, delta: int = 1) -> None:
        """Increment a counter by *delta* (default 1)."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + delta

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge to the current *value*."""
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        """Record an observation in a histogram bucket."""
        with self._lock:
            bucket = self._histograms.setdefault(name, [])
            bucket.append(value)
            if len(bucket) > self._MAX_HISTOGRAM_SIZE:
                # Keep the most recent half to avoid repeated trimming
                del bucket[: len(bucket) // 2]

    # -- querying ---------------------------------------------------------

    def get_counter(self, name: str) -> int:
        """Return the current value of a counter metric.

        Args:
            name: Metric name.

        Returns:
            Counter value, or ``0`` if the counter does not exist.
        """
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float | None:
        """Return the current value of a gauge metric.

        Args:
            name: Metric name.

        Returns:
            Gauge value, or ``None`` if the gauge does not exist.
        """
        with self._lock:
            return self._gauges.get(name)

    def get_histogram(self, name: str) -> list[float]:
        """Return all observations recorded for a histogram metric.

        Args:
            name: Metric name.

        Returns:
            List of observed values, or an empty list if none exist.
        """
        with self._lock:
            return list(self._histograms.get(name, []))

    # -- export -----------------------------------------------------------

    def export(self, fmt: ExportFormat = ExportFormat.JSON) -> str:
        """Export all metrics in the given format.

        Supported:
          * ``JSON``      — human-friendly nested dict.
          * ``PROMETHEUS`` — text/plain Prometheus exposition format.
          * ``OTLP_JSON``  — OpenTelemetry-compatible JSON envelope.
        """
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {k: list(v) for k, v in self._histograms.items()}

        if fmt == ExportFormat.JSON:
            return self._export_json(counters, gauges, histograms)
        if fmt == ExportFormat.PROMETHEUS:
            return self._export_prometheus(counters, gauges, histograms)
        if fmt == ExportFormat.OTLP_JSON:
            return self._export_otlp(counters, gauges, histograms)
        raise ValueError(f"Unknown export format: {fmt}")

    def reset(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    # -- private helpers --------------------------------------------------

    @staticmethod
    def _export_json(
        counters: dict[str, int],
        gauges: dict[str, float],
        histograms: dict[str, list[float]],
    ) -> str:
        return json.dumps(
            {"counters": counters, "gauges": gauges, "histograms": histograms},
            indent=2,
        )

    @staticmethod
    def _export_prometheus(
        counters: dict[str, int],
        gauges: dict[str, float],
        histograms: dict[str, list[float]],
    ) -> str:
        """Prometheus text exposition: each metric on its own line."""
        lines: list[str] = []
        for name, value in sorted(counters.items()):
            safe = name.replace(".", "_")
            lines.append(f"# TYPE crp_{safe} counter")
            lines.append(f"crp_{safe} {value}")
        for name, value in sorted(gauges.items()):  # type: ignore[assignment]
            safe = name.replace(".", "_")
            lines.append(f"# TYPE crp_{safe} gauge")
            lines.append(f"crp_{safe} {value}")
        for name, values in sorted(histograms.items()):
            safe = name.replace(".", "_")
            if values:
                lines.append(f"# TYPE crp_{safe} summary")
                lines.append(f"crp_{safe}_count {len(values)}")
                lines.append(f"crp_{safe}_sum {sum(values)}")
        return "\n".join(lines) + "\n" if lines else ""

    @staticmethod
    def _export_otlp(
        counters: dict[str, int],
        gauges: dict[str, float],
        histograms: dict[str, list[float]],
    ) -> str:
        """OTLP-compatible JSON envelope (simplified)."""
        metrics: list[dict[str, Any]] = []
        for name, value in counters.items():
            metrics.append({
                "name": f"crp.{name}",
                "type": "sum",
                "data_points": [{"value": value, "time_unix_nano": int(time.time() * 1e9)}],
            })
        for name, value in gauges.items():  # type: ignore[assignment]
            metrics.append({
                "name": f"crp.{name}",
                "type": "gauge",
                "data_points": [{"value": value, "time_unix_nano": int(time.time() * 1e9)}],
            })
        for name, values in histograms.items():
            metrics.append({
                "name": f"crp.{name}",
                "type": "histogram",
                "data_points": [{
                    "count": len(values),
                    "sum": sum(values),
                    "time_unix_nano": int(time.time() * 1e9),
                }],
            })
        envelope = {
            "resource_metrics": [{
                "scope_metrics": [{"metrics": metrics}],
            }],
        }
        return json.dumps(envelope, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# HealthMonitor (§9.7)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class HealthStatus:
    """Result of a health probe."""

    alive: bool = True
    ready: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the health status as a plain dict.

        Returns:
            Dict with ``alive``, ``ready``, and ``details`` fields.
        """
        return {"alive": self.alive, "ready": self.ready, "details": self.details}


class HealthMonitor:
    """Liveness and readiness probes for the CRP runtime.

    Register named checks with ``add_check(name, callable)``.  Each check
    returns ``True`` (healthy) or ``False`` (unhealthy).

    Usage::

        hm = HealthMonitor()
        hm.add_check("emitter", lambda: emitter.is_running)
        hm.add_check("warm_store", lambda: warm_store is not None)
        status = hm.probe()
        assert status.alive
    """

    def __init__(self) -> None:
        self._checks: dict[str, Any] = {}  # name → callable() → bool
        self._alive = True

    def add_check(self, name: str, check_fn: Any) -> None:
        """Register a readiness check."""
        self._checks[name] = check_fn

    def remove_check(self, name: str) -> bool:
        """Remove a check. Returns True if it existed."""
        return self._checks.pop(name, None) is not None

    def set_alive(self, alive: bool) -> None:
        """Manually mark the runtime as alive or dead (e.g. on shutdown)."""
        self._alive = alive

    def probe(self) -> HealthStatus:
        """Run all registered checks and return combined status.

        Liveness: ``True`` unless ``set_alive(False)`` was called.
        Readiness: ``True`` only if *all* registered checks pass.
        """
        details: dict[str, Any] = {}
        all_ready = True
        for name, fn in self._checks.items():
            try:
                ok = bool(fn())
            except Exception:
                ok = False
            details[name] = ok
            if not ok:
                all_ready = False
        return HealthStatus(alive=self._alive, ready=all_ready, details=details)
