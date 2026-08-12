# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP demo server — a zero-dependency stdlib HTTP server for all demos.

Run::

    python -m examples.crp_demos.server          # serves on 127.0.0.1:8770
    python -m examples.crp_demos.server --port 9000

Then open http://127.0.0.1:8770 in a browser:

* ``/``               — landing page + live LLM detection
* ``/safety.html``    — App 1: AI Safety & Governance Console
* ``/context.html``   — App 2: Context Management & Provenance Explorer
* ``/comparison.html``— App 3: 4-Strategy Context Comparison

JSON API (all POST bodies are JSON):

* ``GET  /api/detect``            → discovered runtimes + capabilities
* ``POST /api/safety/analyze``    → run the governed-generation pipeline
* ``POST /api/context/new``       → start a context session
* ``POST /api/context/turn``      → send a message (multi-window)
* ``POST /api/context/tamper``    → corrupt a window → chain BROKEN
* ``POST /api/context/state``     → full session state
* ``POST /api/compare/start``     → start a 4-strategy benchmark run
* ``GET  /api/compare/stream``    → SSE stream for a run
* ``GET  /api/compare/status``    → current run state + partial results
* ``POST /api/compare/cancel``    → cancel an in-progress run
* ``POST /api/compare/poll``      → poll for pending events (non-SSE)
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from examples.crp_demos.pipeline import (
    DEFAULT_SAFETY_POLICY,
    ContextSessionStore,
    detect_runtime,
    run_safety_pipeline,
)
from examples.crp_demos import comparison_backend as _cmp

logger = logging.getLogger("crp.demos.server")

_STATIC_DIR = Path(__file__).parent / "static"
_SESSIONS = ContextSessionStore()

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


class _Handler(BaseHTTPRequestHandler):
    server_version = "CRP-Demo/3.0"

    # ── helpers ──────────────────────────────────────────────────────────
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Echo a couple of CRP headers at the transport layer too, when present.
        for name in ("CRP-Context-Protocol-Version", "CRP-Context-Session-Id",
                     "CRP-Provenance-Chain-Integrity", "CRP-Safety-Grounding-Pct"):
            val = payload.get("headers", {}).get(name) if isinstance(payload, dict) else None
            if val:
                self.send_header(name, str(val))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, OSError):
            return {}

    def _sse_stream(self, run_id: str) -> None:
        """Stream benchmark events as Server-Sent Events."""
        import time as _time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        deadline = _time.time() + 1800  # 30-minute max stream
        while _time.time() < deadline:
            events = _cmp.stream_events(run_id, timeout=2.0)
            for evt in events:
                data = json.dumps(evt, default=str)
                try:
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                except (OSError, BrokenPipeError):
                    return
                if evt.get("type") in ("run_done", "run_error"):
                    return
            run = _cmp.get_run(run_id)
            if run and run.status in ("done", "cancelled", "error"):
                break

        # Send terminal event
        try:
            self.wfile.write(b"data: {\"type\": \"stream_end\"}\n\n")
            self.wfile.flush()
        except OSError:
            pass

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        target = (_STATIC_DIR / rel).resolve()
        # Path-traversal guard.
        if not str(target).startswith(str(_STATIC_DIR.resolve())):
            self.send_error(403, "Forbidden")
            return
        if not target.is_file():
            self.send_error(404, "Not found")
            return
        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── routing ──────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/detect":
            try:
                self._send_json(detect_runtime())
            except Exception as exc:  # noqa: BLE001
                logger.exception("detect failed")
                self._send_json({"error": str(exc)}, status=500)
            return
        # Comparison SSE stream
        if path == "/api/compare/stream":
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
            run_id = params.get("run_id", "")
            self._sse_stream(run_id)
            return
        if path == "/api/compare/status":
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
            run_id = params.get("run_id", "")
            self._send_json(_cmp.get_status(run_id))
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        body = self._read_json()
        try:
            if path == "/api/safety/analyze":
                result = run_safety_pipeline(
                    system_prompt=str(body.get("system_prompt", "")),
                    question=str(body.get("question", "")),
                    context_facts=list(body.get("context_facts", []) or []),
                    policy_str=str(body.get("policy", "") or DEFAULT_SAFETY_POLICY),
                )
                self._send_json(result, status=200)
                return
            if path == "/api/context/new":
                self._send_json(_SESSIONS.new_session())
                return
            if path == "/api/context/turn":
                self._send_json(_SESSIONS.turn(
                    str(body.get("session_id", "")),
                    str(body.get("message", "")),
                ))
                return
            if path == "/api/context/tamper":
                self._send_json(_SESSIONS.tamper(
                    str(body.get("session_id", "")),
                    int(body.get("window_number", 1)),
                ))
                return
            if path == "/api/context/state":
                self._send_json(_SESSIONS.state(str(body.get("session_id", ""))))
                return
            # Context comparison API
            if path == "/api/compare/start":
                run_id = _cmp.start_benchmark(body)
                self._send_json({"run_id": run_id, "status": "started"})
                return
            if path == "/api/compare/cancel":
                ok = _cmp.cancel_run(str(body.get("run_id", "")))
                self._send_json({"cancelled": ok})
                return
            if path == "/api/compare/poll":
                events = _cmp.stream_events(
                    str(body.get("run_id", "")),
                    timeout=float(body.get("timeout", 10.0)),
                )
                self._send_json({"events": events})
                return
        except Exception as exc:  # noqa: BLE001
            logger.exception("request failed: %s", path)
            self._send_json({"error": str(exc)}, status=500)
            return
        self.send_error(404, "Not found")

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
        logger.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="CRP demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    url = f"http://{args.host}:{args.port}"
    print("\n  CRP demos running:")
    print(f"    Landing / detection     : {url}/")
    print(f"    Safety console          : {url}/safety.html")
    print(f"    Context explorer        : {url}/context.html")
    print(f"    Context comparison      : {url}/comparison.html")
    print("\n  Press Ctrl+C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping…")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
