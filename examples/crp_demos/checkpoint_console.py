# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live HITL Checkpoint Console — a REAL web UI for CRP's human-in-the-loop gate.

This is not a mockup. It runs the exact `security_analyst_agent.py` scenario
(CHEATSHEET.md §5.6) against a real LLM (LM Studio / OpenAI / Anthropic /
Ollama — auto-detected), streams the agent's live governance events (AG-UI +
`crp.*`) to a browser over Server-Sent Events, and when the model tries to
call the DESTRUCTIVE `quarantine_host` tool, the running agent thread
genuinely BLOCKS — waiting on a real `queue.Queue.get()` — until you click
Approve or Deny in the browser. There is no `input()`, no pre-recorded replay,
no simulated delay: the HTTP response that carries your click is what
unblocks the Python thread running the agent.

Run:
    python examples/crp_demos/checkpoint_console.py
    # then open http://127.0.0.1:8782 in a browser and click "Start Run"

Zero extra dependencies — stdlib `http.server` only, same pattern as
`examples/crp_demos/server.py`.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("CRP_GLINER_DISABLED", "1")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates"))

from _shared import resolve_provider  # noqa: E402
from security_analyst_agent import (  # noqa: E402
    check_threat_intel,
    lookup_cve,
    notify_security_team,
    quarantine_host_tool,
)

import crp  # noqa: E402
from crp.security.clarify import (  # noqa: E402
    ClarificationAction,
    ClarificationRequest,
    ClarificationResolution,
)
from crp.tools.descriptor import SafetyClass  # noqa: E402

logger = logging.getLogger("crp.demos.checkpoint_console")

_STATIC_DIR = Path(__file__).parent / "static"
# Two turns, mirroring the exact phrasing proven reliable in
# security_analyst_agent.py (STEP 2 + STEP 3): a dedicated "produce the
# remediation" turn is what actually gets an 8B local model to select the
# DESTRUCTIVE quarantine_host tool — a single combined/conditional prompt
# does not reliably trigger it.
_STEP_1_QUESTION = (
    "A scan found Apache 2.4.49 on host 10.0.0.15 (CVE-2021-41773, CRITICAL). "
    "Check the threat-intelligence reputation of that host."
)
_STEP_2_QUESTION = "Produce the remediation now: quarantine the host and notify the security team."

# ---------------------------------------------------------------------------
# Shared run state — one run at a time, deliberately simple for a demo.
# ---------------------------------------------------------------------------
_events: queue.Queue[tuple[str, dict]] = queue.Queue()
_decision_queue: queue.Queue[str] = queue.Queue()
_run_lock = threading.Lock()
_run_active = False
_APPROVAL_TIMEOUT_S = 300  # Invariant 10 — never leave the agent hanging forever


def _web_approval_handler(request: ClarificationRequest) -> ClarificationResolution:
    """The clarify_handler CRP calls synchronously when a DESTRUCTIVE tool is proposed.

    This function genuinely blocks the agent's execution thread — it is not a
    simulation. It resumes only when /api/decide is POSTed, or after a 5-minute
    safety timeout (which resolves to a denial, never a hang or a crash).
    """
    _events.put(("checkpoint_request", request.to_dict()))
    try:
        decision = _decision_queue.get(timeout=_APPROVAL_TIMEOUT_S)
    except queue.Empty:
        decision = "deny"
        _events.put(("checkpoint_timeout", {"request_id": request.request_id}))

    _events.put(("checkpoint_resolved", {"request_id": request.request_id, "decision": decision}))
    if decision == "approve":
        return ClarificationResolution(ClarificationAction.ANSWER, answer="approve", reviewer="web-user")
    return ClarificationResolution(ClarificationAction.ABORT, answer="denied", reviewer="web-user")


def _run_agent() -> None:
    """Run the real security-analyst agent (2 turns), forwarding every live event to the browser."""
    global _run_active
    try:
        provider = resolve_provider()
        agent = crp.Agent(
            provider=provider,
            tools=[lookup_cve, check_threat_intel, notify_security_team, quarantine_host_tool],
            system=(
                "You are a SOC security analyst assistant. Use the available tools to "
                "investigate findings before recommending or taking action. Never "
                "claim an action succeeded unless a tool actually reported it."
            ),
            profile="capable-local",
            depth="thorough",
            oversight_required={SafetyClass.DESTRUCTIVE},
            clarify_handler=_web_approval_handler,
        )
        _events.put(("provider", {"class": type(provider).__name__, "model": getattr(provider, "_model", "?")}))

        _events.put(("step_boundary", {"step": 1, "question": _STEP_1_QUESTION}))
        prior_cso = None
        for ev in agent.run_tel(_STEP_1_QUESTION, prior_cso=prior_cso):
            _events.put(("tel", ev.to_dict()))
        prior_cso = agent._last_cso  # carried forward automatically by run_tel too; explicit for clarity

        _events.put(("step_boundary", {"step": 2, "question": _STEP_2_QUESTION}))
        for ev in agent.run_tel(_STEP_2_QUESTION, prior_cso=prior_cso):
            _events.put(("tel", ev.to_dict()))
    except Exception as exc:  # noqa: BLE001 — surface to the browser, never crash silently
        logger.exception("Agent run failed")
        _events.put(("error", {"message": f"{type(exc).__name__}: {exc}"}))
    finally:
        _events.put(("done", {}))
        _run_active = False


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    server_version = "CRP-Checkpoint-Console/1.0"

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102 — quiet default access log
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return {}

    def do_GET(self) -> None:  # noqa: N802 — stdlib API
        global _run_active
        if self.path == "/" or self.path == "/index.html":
            self._serve_static("checkpoint.html")
        elif self.path.startswith("/api/start"):
            with _run_lock:
                if _run_active:
                    self._send_json({"ok": False, "error": "a run is already in progress"}, 409)
                    return
                _run_active = True
                # Drain any stale events/decisions from a previous run.
                while not _events.empty():
                    _events.get_nowait()
                while not _decision_queue.empty():
                    _decision_queue.get_nowait()
                threading.Thread(target=_run_agent, daemon=True).start()
            self._send_json({"ok": True, "question": _STEP_1_QUESTION})
        elif self.path.startswith("/api/stream"):
            self._sse_stream()
        else:
            self._serve_static(self.path.lstrip("/"))

    def do_POST(self) -> None:  # noqa: N802 — stdlib API
        if self.path.startswith("/api/decide"):
            body = self._read_json()
            decision = "approve" if body.get("decision") == "approve" else "deny"
            _decision_queue.put(decision)
            self._send_json({"ok": True, "decision": decision})
        else:
            self._send_json({"ok": False, "error": "unknown endpoint"}, 404)

    def _serve_static(self, name: str) -> None:
        target = (_STATIC_DIR / name).resolve()
        if not str(target).startswith(str(_STATIC_DIR.resolve())) or not target.is_file():
            self.send_response(404)
            self.end_headers()
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        deadline = time.time() + 900  # 15-minute hard cap on one SSE connection
        while time.time() < deadline:
            try:
                kind, payload = _events.get(timeout=15)
            except queue.Empty:
                try:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionAbortedError):
                    return
                continue
            data = json.dumps({"kind": kind, **payload}, default=str)
            try:
                self.wfile.write(f"event: {kind}\ndata: {data}\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError):
                return
            if kind in {"done", "error"}:
                return


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CRP live HITL checkpoint console")
    parser.add_argument("--port", type=int, default=8782)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    url = f"http://127.0.0.1:{args.port}"
    print("=" * 70)
    print("CRP Live Checkpoint Console")
    print("=" * 70)
    print(f"Open {url} in a browser, click 'Start Run', and approve/deny the")
    print("checkpoint live — this genuinely blocks the running agent thread.")
    print(f"Scenario: {_STEP_1_QUESTION} -> {_STEP_2_QUESTION}")
    print("=" * 70)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
