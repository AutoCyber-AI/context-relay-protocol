# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Ledger forwarding sinks (§7.14.5, CRP 2.3).

CRP 2.2's :class:`~crp.core.manifest_ledger.ManifestLedger` wrote JSONL
files to the local filesystem.  That is sufficient for a single node but
fails in two real operational settings:

* **Distributed workers** — multiple replicas need their ledger entries
  aggregated in a central store (SIEM, SQL, data-lake) so auditors see a
  single timeline.
* **Tamper-evidence in depth** — the CRP 2.3 hash-chain catches edits on
  the local JSONL file, but a root-level attacker could still delete the
  file.  Forwarding every record to an append-only external system closes
  that hole.

These sinks implement the existing
:class:`~crp.core.context_enforcer.AuditSink` protocol (``emit(event)``)
so the same wiring serves enforcement events *and* ledger writes. Pass
the sinks in via ``ManifestLedger(forward_to=[...])``.

All sinks here are pure-stdlib. Production deployments should use HTTPS
with rotating tokens and rely on the SIEM's native replay/retention.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

__all__ = [
    "JSONLinesFileSink",
    "HTTPForwardingSink",
    "AsyncBufferedSink",
    "NullSink",
]


_log = logging.getLogger("crp.ledger_backends")


class NullSink:
    """No-op sink. Useful when a configuration requires a sink object but
    nothing should be forwarded (e.g. in tests)."""

    def emit(self, event: dict[str, Any]) -> None:  # noqa: D401
        """Drop the event silently."""
        return


class JSONLinesFileSink:
    """Append every event as one JSON object per line to a local file.

    Thread-safe: all writes are serialised on an internal lock. Intended
    for replicating ledger records to a location monitored by Splunk
    Universal Forwarder, Vector, Fluentd, etc.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: dict[str, Any]) -> None:
        """Append *event* as one JSON line to the configured file.

        Args:
            event: Audit or ledger record to persist.
        """
        line = json.dumps(event, separators=(",", ":"), sort_keys=True, default=str)
        with self._lock, self._path.open("a", encoding="utf-8") as fp:
            fp.write(line)
            fp.write("\n")


class HTTPForwardingSink:
    """POST every event as JSON to an HTTPS endpoint.

    Intended for Splunk HEC, Elastic Common Schema ingest, Datadog Logs
    HTTP intake, Azure Monitor, AWS CloudWatch Logs (via signed gateway),
    or a bespoke SIEM collector.

    Failures are logged at WARNING; the sink never raises out to the
    caller. Callers that need guaranteed delivery should wrap this in
    :class:`AsyncBufferedSink` and pair it with a retry layer.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 3.0,
    ) -> None:
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError("HTTPForwardingSink: url must be http:// or https://")
        self._url = url
        self._headers = {
            "Content-Type": "application/json",
            "User-Agent": "crp-ledger-forwarder/1.0",
        }
        if headers:
            self._headers.update(headers)
        self._timeout = float(timeout)

    def emit(self, event: dict[str, Any]) -> None:
        """POST *event* as JSON to the configured HTTP endpoint.

        Args:
            event: Audit or ledger record to forward.
        """
        body = json.dumps(event, separators=(",", ":"), default=str).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=body, headers=self._headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    _log.warning(
                        "CRP ledger HTTP forward non-2xx: %d %s",
                        resp.status,
                        self._url,
                    )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            _log.warning("CRP ledger HTTP forward failed: %s (%s)", self._url, exc)


class AsyncBufferedSink:
    """Background-thread buffer wrapping a downstream sink.

    Enqueues events in memory (bounded; default 10k) and drains them on a
    single worker thread. Keeps ledger writes off the hot path when the
    downstream sink is slow or flaky.

    Call :meth:`close` on shutdown to flush. Events that cannot be
    enqueued (queue full) are dropped and logged — operators should size
    the queue for their write rate.
    """

    def __init__(
        self,
        target: Any,
        *,
        max_queue: int = 10_000,
        drain_on_close: bool = True,
    ) -> None:
        if not hasattr(target, "emit"):
            raise TypeError("AsyncBufferedSink target must implement .emit()")
        self._target = target
        self._q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max_queue)
        self._drain_on_close = drain_on_close
        self._stopped = threading.Event()
        self._worker = threading.Thread(
            target=self._run, name="crp-ledger-sink", daemon=True
        )
        self._worker.start()

    def emit(self, event: dict[str, Any]) -> None:
        """Enqueue *event* for background forwarding.

        Args:
            event: Audit or ledger record to enqueue.
        """
        if self._stopped.is_set():
            return
        try:
            self._q.put_nowait(dict(event))
        except queue.Full:
            _log.warning("CRP ledger async sink full; dropping event")

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            try:
                self._target.emit(item)
            except Exception as exc:  # pragma: no cover - defensive
                _log.warning("CRP ledger async target raised: %s", exc)
            finally:
                self._q.task_done()

    def close(self, timeout: float = 5.0) -> None:
        """Signal shutdown and (optionally) wait for the queue to drain."""
        if self._stopped.is_set():
            return
        self._stopped.set()
        if self._drain_on_close:
            deadline = time.monotonic() + timeout
            while not self._q.empty() and time.monotonic() < deadline:
                time.sleep(0.01)
        self._q.put(None)
        self._worker.join(timeout=timeout)
