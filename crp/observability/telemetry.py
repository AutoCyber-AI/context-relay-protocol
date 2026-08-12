# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Per-window telemetry writer — ``telemetry.jsonl`` output (§8.9).

TelemetryWriter appends one JSON object per line for every completed
window.  The JSONL file can be consumed by downstream analytics,
dashboards, or the AuditLog.

Design goals:
  * One line per window → easy to ``grep``, ``jq``, or stream-parse.
  * Flush after every write so no data is lost on crash.
  * Works with file paths or any writable file-like object.
"""

from __future__ import annotations

import atexit
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import IO, Any


@dataclass
class WindowTelemetry:
    """Telemetry record for a single completed window.

    Fields mirror the most useful per-window stats.  Extra fields can
    be added via ``extra``.
    """

    session_id: str
    window_id: str
    timestamp: float = field(default_factory=time.time)
    input_tokens: int = 0
    output_tokens: int = 0
    overhead_tokens: int = 0
    facts_included: int = 0
    facts_available: int = 0
    latency_ms: float = 0.0
    quality_tier: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the telemetry record as a plain dict.

        Returns:
            Dict representation with ``extra`` fields flattened into the top level.
        """
        d = asdict(self)
        # Flatten extra into the top level for ease of querying.
        extra = d.pop("extra", {})
        d.update(extra)
        return d


class TelemetryWriter:
    """Append-only JSONL writer for per-window telemetry.

    Usage::

        tw = TelemetryWriter("telemetry.jsonl")
        tw.write(WindowTelemetry(session_id="abc", window_id="w0", ...))
        tw.close()

    Also works as a context manager::

        with TelemetryWriter("telemetry.jsonl") as tw:
            tw.write(record)
    """

    def __init__(self, path_or_file: str | IO[str]) -> None:
        if isinstance(path_or_file, str):
            # Ensure parent directory exists.
            parent = os.path.dirname(path_or_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._file: IO[str] = open(path_or_file, "a", encoding="utf-8")  # noqa: SIM115
            self._owns_file = True
        else:
            self._file = path_or_file
            self._owns_file = False
        self._count = 0
        self._closed = False
        # Ensure close on interpreter shutdown (§audit H3)
        atexit.register(self.close)

    # -- writing ----------------------------------------------------------

    def write(self, record: WindowTelemetry) -> None:
        """Serialize *record* and append one JSON line. Flushes immediately."""
        line = json.dumps(record.to_dict(), separators=(",", ":"))
        self._file.write(line + "\n")
        self._file.flush()
        self._count += 1

    @property
    def records_written(self) -> int:
        """Return the records written."""
        return self._count

    # -- lifecycle --------------------------------------------------------

    def close(self) -> None:
        """Flush and close the underlying file if this writer owns it."""
        if self._closed:
            return
        self._closed = True
        if self._owns_file:
            self._file.close()

    def __del__(self) -> None:
        """Safety net: close file if not already closed (§audit H3)."""
        try:
            self.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> TelemetryWriter:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
