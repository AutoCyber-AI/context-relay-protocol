# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""TEL transparency-stream endpoint for the Gateway (CRP-SPEC-056 §8.3).

Wires the Transparency Emission Layer onto a real HTTP surface. The Gateway
has no mandatory web framework, so the endpoint is exposed in two forms:

  - :func:`handle_tel_stream` — framework-agnostic, returns SSE headers plus a
    frame iterator (mirrors :func:`crp.gateway.api.handle_chat_completions`).
  - :func:`mount_fastapi` — mounts ``GET /v1/tel/stream`` on a FastAPI app
    (lazy import; FastAPI is optional).

The stream honours the SSE ``Last-Event-ID`` resume contract: event ids are
the per-session sequence numbers, so a reconnecting client replays everything
it missed from the session bus buffer. Comment heartbeats (``: ping``) are
emitted every ``heartbeat_interval`` seconds (default 15) to keep proxies
and browsers from closing idle connections.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from crp.tel.emitter import get_bus
from crp.tel.sse import stream_frames_sync

logger = logging.getLogger("crp.gateway.tel_stream")

#: Headers every SSE response must carry.
SSE_HEADERS: dict[str, str] = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable nginx proxy buffering
}

DEFAULT_STREAM_PATH = "/v1/tel/stream"


def tel_stream_frames(
    session_id: str,
    last_event_id: int | str | None = None,
    *,
    heartbeat_interval: float | None = 15.0,
) -> Iterator[str]:
    """Yield SSE frames for ``session_id`` from the TEL session bus.

    Args:
        session_id: TEL session whose events should be streamed.
        last_event_id: Value of the ``Last-Event-ID`` request header; buffered
            events with a higher sequence number are replayed first.
        heartbeat_interval: Seconds between ``: ping`` comment frames when the
            stream is idle. ``None`` disables heartbeats.
    """
    bus = get_bus(session_id)
    return stream_frames_sync(bus, last_event_id, heartbeat_interval=heartbeat_interval)


def handle_tel_stream(
    session_id: str,
    last_event_id: int | str | None = None,
    *,
    heartbeat_interval: float | None = 15.0,
) -> dict[str, Any]:
    """Framework-agnostic ``GET /v1/tel/stream`` handler.

    Returns a dict with ``status_code``, ``headers`` (SSE), and ``body`` — a
    sync iterator of SSE frames. ASGI/WSGI adapters can stream ``body``
    directly; tests can consume it with a mocked transport.
    """
    if not session_id:
        return {
            "status_code": 400,
            "headers": {"Content-Type": "application/json"},
            "body": iter(['{"error": {"code": "missing_session_id"}}']),
        }
    return {
        "status_code": 200,
        "headers": dict(SSE_HEADERS),
        "body": tel_stream_frames(
            session_id, last_event_id, heartbeat_interval=heartbeat_interval
        ),
    }


def mount_fastapi(
    app: Any,
    *,
    path: str = DEFAULT_STREAM_PATH,
    heartbeat_interval: float = 15.0,
) -> None:
    """Mount the TEL stream on a FastAPI app (lazy import — FastAPI optional).

    The mounted route serves ``GET {path}?session_id=...`` as
    ``text/event-stream`` and honours the ``Last-Event-ID`` header.
    """
    from crp.tel.emitter import get_bus as _get_bus
    from crp.tel.sse import stream_frames as _stream_frames

    async def _route(request: Any) -> Any:
        from fastapi.responses import StreamingResponse

        session_id = request.query_params.get("session_id", "")
        last_event_id = request.headers.get("last-event-id")
        bus = _get_bus(session_id)
        return StreamingResponse(
            _stream_frames(bus, last_event_id, heartbeat_interval=heartbeat_interval),
            media_type="text/event-stream",
            headers={k: v for k, v in SSE_HEADERS.items() if k.lower() != "content-type"},
        )

    app.get(path)(_route)
