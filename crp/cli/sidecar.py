# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP HTTP sidecar — lightweight REST API for inter-process context sharing (§9.3).

Architecture
~~~~~~~~~~~~
The sidecar exposes CRP sessions over HTTP, enabling:

1. **Inter-LLM fact sharing** — two applications using different LLMs can
   share extracted knowledge.  Application A (Claude) extracts facts,
   Application B (GPT-4) receives them via ``/facts/share`` — both benefit
   from the other's knowledge without direct LLM-to-LLM communication.

2. **Full protocol surface** — every CRP dispatch variant (basic, tools,
   reflexive, progressive, stream-augmented, agentic) is available over
   HTTP.  Feedback loops, cost estimation, and provider registration are
   also exposed.

3. **Language-agnostic integration** — any language/framework can interact
   with CRP via HTTP (TypeScript frontend, Rust service, Python backend).

4. **Dashboard & monitoring** — query session status, inspect facts,
   preview envelopes, and track event history.

Endpoints
~~~~~~~~~
Session lifecycle::

  POST /sessions                     Create a new CRP session
  GET  /sessions                     List active sessions
  GET  /sessions/:id/status          Session status / metrics
  POST /sessions/:id/close           Close session

Dispatch (all 6 variants)::

  POST /sessions/:id/dispatch                   Basic dispatch
  POST /sessions/:id/dispatch/tools             Tool-mediated dispatch
  POST /sessions/:id/dispatch/reflexive         Reflexive (verify) dispatch
  POST /sessions/:id/dispatch/progressive       Progressive dispatch
  POST /sessions/:id/dispatch/stream-augmented  Stream-augmented dispatch
  POST /sessions/:id/dispatch/agentic           Agentic dispatch

Knowledge::

  POST /sessions/:id/ingest          Ingest raw text
  GET  /sessions/:id/facts           Query extracted facts
  POST /sessions/:id/facts/share     Share facts TO another session
  POST /sessions/:id/facts/feedback  Boost / penalize / reject facts
  GET  /sessions/:id/envelope        Preview envelope

Provider::

  POST /sessions/:id/providers       Register fallback provider

Admin::

  GET  /health                       Health check
  POST /sessions/:id/estimate        Cost estimation

Security
~~~~~~~~
- **Off by default** — ``crp serve`` must be explicitly invoked; the sidecar
  is never started automatically by the library.
- Binds to ``127.0.0.1`` (loopback only) by default.
- Optional bearer-token authentication (``--auth-token``).
- Per-session RBAC enforced through the orchestrator's existing security layer.
- Request body size capped at 10 MB (configurable).
- Rate limiting: configurable per-IP burst window.
- Session ownership: sessions are bound to the token hash that created them.
- ``--bind-all`` requires explicit ``--auth-token`` or ``--allow-unauthenticated``.
- No HTTPS built-in — deploy behind a TLS-terminating reverse proxy for
  production use (nginx, Caddy, etc.).
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("crp.sidecar")


def _sanitize_error(exc: Exception) -> str:
    """Sanitize internal error details before sending to client (§audit M11).

    Strips stack traces, file paths, and internal module names.
    Returns a generic message for unexpected errors that might leak internals.
    """
    from crp.core.errors import CRPError
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        # Return generic message — str(exc) can leak internal paths/secrets
        return f"Invalid input: {type(exc).__name__}"
    if isinstance(exc, CRPError):
        # CRP errors have structured codes — truncate message to prevent leakage (§audit3 SEC-H3)
        msg = (exc.message or "")[:ERROR_MSG_MAX_LEN].replace("\n", " ")
        return f"CRP-{exc.code}: {msg}"
    # Generic error — don't leak internals
    return "Internal server error"

# ── Constants (§audit4 CQ-M1) ────────────────────────────────────────
MAX_BODY_BYTES_DEFAULT = 10 * 1024 * 1024   # 10 MB body limit
MAX_SESSIONS_DEFAULT = 64                   # Max concurrent sessions
RATE_WINDOW_DEFAULT = 60                    # Rate window in seconds
RATE_MAX_REQUESTS_DEFAULT = 120             # Max requests per IP per window
DISPATCH_RATE_WINDOW_DEFAULT = 60           # Dispatch rate window
DISPATCH_RATE_MAX_DEFAULT = 30              # Max dispatch requests per caller
RATE_COUNTER_MAX_KEYS = 10_000              # Max tracked IPs before eviction
RATE_COUNTER_EVICT_COUNT = 2_000            # Number of oldest IPs to evict
ERROR_MSG_MAX_LEN = 80                      # Error message truncation length

# ── Server state ─────────────────────────────────────────────────────
_active_sessions: dict[str, Any] = {}
_session_owners: dict[str, str] = {}       # session_id → token_hash that created it
_sessions_lock = threading.Lock()
_auth_token: str | None = None             # Optional bearer token (set via start_sidecar)
_max_body_bytes: int = MAX_BODY_BYTES_DEFAULT
_max_sessions: int = MAX_SESSIONS_DEFAULT

# ── Rate limiting state ──────────────────────────────────────────────
_rate_window_seconds: int = RATE_WINDOW_DEFAULT
_rate_max_requests: int = RATE_MAX_REQUESTS_DEFAULT
_rate_counters: dict[str, deque] = defaultdict(lambda: deque(maxlen=RATE_MAX_REQUESTS_DEFAULT))
_rate_lock = threading.Lock()

# Dispatch-specific rate limit (per API-key / per-IP, more expensive)
_dispatch_rate_window: int = DISPATCH_RATE_WINDOW_DEFAULT
_dispatch_rate_max: int = DISPATCH_RATE_MAX_DEFAULT
_dispatch_counters: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.monotonic()
    with _rate_lock:
        window = _rate_counters[client_ip]
        # Prune old entries (deque keeps bounded maxlen)
        cutoff = now - _rate_window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= _rate_max_requests:
            return False
        window.append(now)
        # Evict oldest IP keys to prevent unbounded growth (§audit2 SEC-H3, §audit3 SEC-C1)
        if len(_rate_counters) > RATE_COUNTER_MAX_KEYS:
            oldest = sorted(_rate_counters.items(),
                            key=lambda kv: max(kv[1]) if kv[1] else 0.0)
            for ip, _ in oldest[:RATE_COUNTER_EVICT_COUNT]:
                del _rate_counters[ip]
    return True


def _check_dispatch_rate(caller_key: str) -> bool:
    """Return True if dispatch request is allowed for this caller."""
    now = time.monotonic()
    with _rate_lock:
        window = _dispatch_counters[caller_key]
        cutoff = now - _dispatch_rate_window
        _dispatch_counters[caller_key] = [t for t in window if t > cutoff]
        if len(_dispatch_counters[caller_key]) >= _dispatch_rate_max:
            return False
        _dispatch_counters[caller_key].append(now)
        # Evict oldest keys to prevent unbounded growth (§audit3 SEC-H5)
        if len(_dispatch_counters) > RATE_COUNTER_MAX_KEYS:
            oldest = sorted(_dispatch_counters.items(),
                            key=lambda kv: max(kv[1]) if kv[1] else 0.0)
            for key, _ in oldest[:RATE_COUNTER_EVICT_COUNT]:
                del _dispatch_counters[key]
    return True


def _token_hash(token: str) -> str:
    """One-way hash of bearer token for ownership tracking."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: Any) -> None:
    """Write a JSON response with security headers."""
    body = json.dumps(data, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    """Read and parse JSON request body with size limit."""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        return {}
    if content_length > _max_body_bytes:
        raise ValueError(f"Request body too large ({content_length} bytes, max {_max_body_bytes})")
    raw = handler.rfile.read(content_length)
    return json.loads(raw.decode("utf-8"))


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Check bearer token if authentication is configured.

    When no auth_token is set, access is permitted only because
    start_sidecar() enforces auth for non-loopback binds (§audit3 SEC-H4).
    """
    if _auth_token is None:
        return True
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        _json_response(handler, 401, {"error": "Unauthorized", "detail": "Bearer token required"})
        return False
    provided = auth[7:]
    if secrets.compare_digest(provided, _auth_token):
        return True
    _json_response(handler, 401, {"error": "Unauthorized", "detail": "Invalid bearer token"})
    return False


def _get_caller_token(handler: BaseHTTPRequestHandler) -> str:
    """Extract and hash the caller's bearer token (for ownership tracking)."""
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _token_hash(auth[7:])
    return "anonymous"


def _check_session_access(handler: BaseHTTPRequestHandler, session_id: str) -> bool:
    """Verify caller owns (or has access to) the session."""
    if _auth_token is None:
        return True  # No auth = no ownership enforcement
    caller = _get_caller_token(handler)
    owner = _session_owners.get(session_id, caller)
    if caller == owner:
        return True
    _json_response(handler, 403, {"error": "Forbidden", "detail": "You do not own this session"})
    return False


class CRPSidecarHandler(BaseHTTPRequestHandler):
    """HTTP request handler for CRP sidecar endpoints.

    Security enforced at every layer:
    1. Rate limiting (per-IP)
    2. Bearer token authentication
    3. Session ownership verification
    4. Request body size limits
    5. Input validation on all endpoints
    """

    def log_message(self, format: str, *args: Any) -> None:
        """Route access logs through Python logging."""
        logger.info(format, *args)

    def setup(self) -> None:
        """Initialise the request handler (delegates to BaseHTTPRequestHandler)."""
        super().setup()

    def finish(self) -> None:
        """Complete the request, flushing the response stream."""
        super().finish()

    def flush_headers(self) -> None:
        """Send all buffered headers to the client."""
        super().flush_headers()

    # ── Pre-flight checks ────────────────────────────────────

    def _pre_flight(self) -> bool:
        """Run rate-limit + auth checks.  Return True if request may proceed."""
        client_ip = self.client_address[0]
        if not _check_rate_limit(client_ip):
            _json_response(self, 429, {"error": "Too Many Requests",
                                       "detail": f"Rate limit: {_rate_max_requests} req/{_rate_window_seconds}s"})
            return False
        if not _check_auth(self):
            return False
        return True

    def _get_session(self, session_id: str) -> Any | None:
        """Look up session with ownership check.  Returns orchestrator or None (after sending error)."""
        with _sessions_lock:
            orch = _active_sessions.get(session_id)
        if orch is None:
            # Generic 404 prevents session-ID enumeration (§audit5 SEC-L5)
            _json_response(self, 404, {"error": "Not found"})
            return None
        if not _check_session_access(self, session_id):
            return None
        return orch

    # ── GET routing ──────────────────────────────────────────

    def do_GET(self) -> None:
        """Route incoming GET requests to the appropriate handler."""
        if not self._pre_flight():
            return
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "status":
            self._handle_session_status(parts[1])
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "facts":
            self._handle_get_facts(parts[1], parse_qs(parsed.query))
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "envelope":
            self._handle_preview_envelope(parts[1], parse_qs(parsed.query))
        elif len(parts) == 1 and parts[0] == "health":
            self._handle_health()
        elif len(parts) == 1 and parts[0] == "ready":
            self._handle_ready()
        elif len(parts) == 1 and parts[0] == "metrics":
            self._handle_metrics()
        elif len(parts) == 1 and parts[0] == "sessions":
            self._handle_list_sessions()
        else:
            _json_response(self, 404, {"error": "Not found"})

    # ── POST routing ─────────────────────────────────────────

    def do_POST(self) -> None:
        """Route incoming POST requests to the appropriate handler."""
        if not self._pre_flight():
            return
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        # POST /sessions
        if len(parts) == 1 and parts[0] == "sessions":
            self._handle_create_session()

        # POST /sessions/:id/dispatch[/variant]
        elif len(parts) >= 3 and parts[0] == "sessions" and parts[2] == "dispatch":
            variant = parts[3] if len(parts) == 4 else "basic"
            self._handle_dispatch(parts[1], variant)

        # POST /sessions/:id/ingest
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "ingest":
            self._handle_ingest(parts[1])

        # POST /sessions/:id/facts/share
        elif len(parts) == 4 and parts[0] == "sessions" and parts[2] == "facts" and parts[3] == "share":
            self._handle_share_facts(parts[1])

        # POST /sessions/:id/facts/feedback
        elif len(parts) == 4 and parts[0] == "sessions" and parts[2] == "facts" and parts[3] == "feedback":
            self._handle_feedback(parts[1])

        # POST /sessions/:id/providers
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "providers":
            self._handle_register_provider(parts[1])

        # POST /sessions/:id/estimate
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "estimate":
            self._handle_estimate(parts[1])

        # POST /sessions/:id/close
        elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "close":
            self._handle_close(parts[1])

        else:
            _json_response(self, 404, {"error": "Not found"})

    # ── Health & list ────────────────────────────────────────

    def _handle_health(self) -> None:
        with _sessions_lock:
            count = len(_active_sessions)
        _json_response(self, 200, {
            "status": "ok",
            "active_sessions": count,
            "max_sessions": _max_sessions,
            "auth_required": _auth_token is not None,
            "rate_limit": f"{_rate_max_requests}/{_rate_window_seconds}s",
            "version": "2.0.0",
        })

    def _handle_ready(self) -> None:
        """Readiness probe for orchestration platforms (K8s, ECS) (§audit H8)."""
        with _sessions_lock:
            count = len(_active_sessions)
        can_accept = count < _max_sessions
        status = 200 if can_accept else 503
        _json_response(self, status, {
            "ready": can_accept,
            "active_sessions": count,
            "max_sessions": _max_sessions,
        })

    def _handle_metrics(self) -> None:
        """Expose Prometheus-compatible metrics (§audit M14)."""
        try:
            from crp.observability.metrics import MetricsExporter, ExportFormat
            exporter = MetricsExporter()
            # Collect live session metrics
            with _sessions_lock:
                exporter.gauge("sidecar.active_sessions", len(_active_sessions))
                for sid, orch in _active_sessions.items():
                    try:
                        st = orch.session_status()
                        exporter.gauge("sidecar.facts_in_warm_store", st.facts_in_warm_state)
                    except Exception:
                        pass
            text = exporter.export(ExportFormat.PROMETHEUS)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            encoded = text.encode("utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception:
            logger.exception("Metrics export failed")
            _json_response(self, 500, {"error": "Metrics export failed"})

    def _handle_list_sessions(self) -> None:
        caller = _get_caller_token(self)
        with _sessions_lock:
            snapshot = list(_active_sessions.items())
        sessions = []
        for sid, orch in snapshot:
            # Only show sessions the caller owns (or all if no auth)
            if _auth_token is not None and _session_owners.get(sid) != caller:
                continue
            try:
                st = orch.session_status()
                sessions.append({
                    "session_id": sid,
                    "windows_completed": st.windows_completed,
                    "facts_in_warm_state": st.facts_in_warm_state,
                })
            except Exception:
                sessions.append({"session_id": sid, "status": "error"})
        _json_response(self, 200, {"sessions": sessions})

    # ── Session lifecycle ────────────────────────────────────

    def _handle_create_session(self) -> None:
        with _sessions_lock:
            if len(_active_sessions) >= _max_sessions:
                _json_response(self, 503, {"error": "Max sessions reached",
                                           "detail": f"Limit: {_max_sessions}"})
                return
        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return
        try:
            from crp.providers.custom import CustomProvider
            from crp.core.orchestrator import CRPOrchestrator

            context_window = body.get("context_window", 128_000)
            model_name = body.get("model", "sidecar-custom")

            provider = CustomProvider(
                generate_fn=lambda msgs, **kw: ("", "stop"),
                count_tokens_fn=lambda t: max(1, len(t) // 4),
                context_size=context_window,
                name=model_name,
            )

            orch = CRPOrchestrator(provider=provider)
            session_id = orch._session.session_id
            caller = _get_caller_token(self)
            with _sessions_lock:
                _active_sessions[session_id] = orch
                _session_owners[session_id] = caller

            _json_response(self, 201, {
                "session_id": session_id,
                "model": model_name,
                "context_window": context_window,
            })
        except Exception as exc:
            logger.exception("Failed to create session")
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    def _handle_session_status(self, session_id: str) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            st = orch.session_status()
            _json_response(self, 200, {
                "session_id": st.session_id,
                "windows_completed": st.windows_completed,
                "total_input_tokens": st.total_input_tokens,
                "total_output_tokens": st.total_output_tokens,
                "facts_in_warm_state": st.facts_in_warm_state,
                "overhead_ratio": st.overhead_ratio,
            })
        except Exception as exc:
            logger.exception("Failed to get session status for %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    def _handle_close(self, session_id: str) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            orch.close()
            with _sessions_lock:
                _active_sessions.pop(session_id, None)
                _session_owners.pop(session_id, None)
            _json_response(self, 200, {"closed": True, "session_id": session_id})
        except Exception as exc:
            logger.exception("Failed to close session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Dispatch (all 6 variants) ────────────────────────────

    def _handle_dispatch(self, session_id: str, variant: str) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return

        # Per-caller dispatch rate limit (expensive operation)
        caller_key = _get_caller_token(self) + ":" + self.client_address[0]
        if not _check_dispatch_rate(caller_key):
            _json_response(self, 429, {
                "error": "Dispatch rate limit exceeded",
                "detail": f"Max {_dispatch_rate_max} dispatches/{_dispatch_rate_window}s per caller",
            })
            return

        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return

        system_prompt = body.get("system_prompt", "You are a helpful assistant.")
        task_input = body.get("task_input", "")
        if not task_input:
            _json_response(self, 400, {"error": "task_input is required"})
            return

        valid_variants = {"basic", "tools", "reflexive", "progressive",
                          "stream-augmented", "agentic"}
        if variant not in valid_variants:
            _json_response(self, 400, {"error": f"Unknown dispatch variant '{variant}'",
                                       "valid": sorted(valid_variants)})
            return

        try:
            if variant == "basic":
                output, report = orch.dispatch(system_prompt, task_input)
            elif variant == "tools":
                tools = body.get("tools", [])
                if not tools:
                    _json_response(self, 400, {"error": "tools list required for tools dispatch"})
                    return
                output, report = orch.dispatch_with_tools(
                    system_prompt, task_input, tools=tools,
                )
            elif variant == "reflexive":
                depth = body.get("depth", 1)
                output, report = orch.dispatch_reflexive(
                    system_prompt, task_input, depth=depth,
                )
            elif variant == "progressive":
                output, report = orch.dispatch_progressive(
                    system_prompt, task_input,
                )
            elif variant == "stream-augmented":
                # Collect streamed output into final string
                chunks = []
                for chunk in orch.dispatch_stream_augmented(system_prompt, task_input):
                    chunks.append(chunk.text if hasattr(chunk, "text") else str(chunk))
                output = "".join(chunks)
                report = orch.session_status()  # Best-effort report
                _json_response(self, 200, {
                    "output": output,
                    "variant": "stream-augmented",
                    "session_id": session_id,
                })
                return
            elif variant == "agentic":
                output, report = orch.dispatch_agentic(
                    system_prompt, task_input,
                )
            else:
                _json_response(self, 400, {"error": f"Unhandled variant: {variant}"})
                return

            _json_response(self, 200, {
                "output": output,
                "variant": variant,
                "quality_tier": report.quality_tier,
                "facts_extracted": report.facts_extracted,
                "continuation_windows": report.continuation_windows,
                "session_id": report.session_id,
                "window_id": report.window_id,
            })
        except Exception as exc:
            logger.exception("Dispatch error (variant=%s)", variant)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Ingest ───────────────────────────────────────────────

    def _handle_ingest(self, session_id: str) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return
        text = body.get("text", "")
        label = body.get("label", "sidecar-ingest")
        if not text:
            _json_response(self, 400, {"error": "text is required"})
            return
        try:
            result = orch.ingest(text, source_label=label)
            _json_response(self, 200, {
                "facts_extracted": result.facts_extracted,
                "source_label": result.source_label,
                "fact_ids": result.fact_ids,
            })
        except Exception as exc:
            logger.exception("Ingest failed for session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Facts: query, share, feedback ────────────────────────

    def _handle_get_facts(self, session_id: str, params: dict) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            limit = min(int(params.get("limit", ["50"])[0]), 500)
            ranked_facts = orch._warm_store.get_ranked_facts(limit=limit)
            facts = [
                {
                    "id": f.id,
                    "text": f.text,
                    "confidence": round(f.confidence, 3),
                    "source_window_id": f.source_window_id,
                    "extraction_stage": f.extraction_stage,
                }
                for f in ranked_facts
            ]
            _json_response(self, 200, {"facts": facts, "total": len(facts)})
        except Exception as exc:
            logger.exception("Failed to get facts for session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    def _handle_share_facts(self, source_session_id: str) -> None:
        """Share facts FROM source session TO target session.

        This is the **core inter-LLM context sharing** endpoint:
        - Session A (Claude) extracts facts about code architecture
        - Session B (GPT-4) receives those facts via this endpoint
        - Session B's next dispatch envelope automatically includes
          Session A's knowledge — no LLM-to-LLM communication needed

        Request body::

            {
                "target_session_id": "...",
                "limit": 50,
                "min_confidence": 0.5
            }
        """
        source_orch = self._get_session(source_session_id)
        if source_orch is None:
            return

        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return

        target_session_id = body.get("target_session_id", "")
        if not target_session_id:
            _json_response(self, 400, {"error": "target_session_id is required"})
            return

        # Verify caller also owns target session
        target_orch = self._get_session(target_session_id)
        if target_orch is None:
            return

        limit = min(int(body.get("limit", 50)), 500)
        min_confidence = max(0.0, min(1.0, float(body.get("min_confidence", 0.3))))

        try:
            source_facts = source_orch._warm_store.get_ranked_facts(limit=limit)
            shared_facts = [f for f in source_facts if f.confidence >= min_confidence]

            if shared_facts:
                target_orch._warm_store.add_facts(shared_facts)
                target_orch._ckf.store(
                    shared_facts,
                    window_id=f"shared-from-{source_session_id[:8]}",
                )

            shared_count = len(shared_facts)
            logger.info(
                "Shared %d facts from session %s → %s",
                shared_count, source_session_id[:8], target_session_id[:8],
            )

            source_orch._emitter.emit("fact.shared", {
                "target_session_id": target_session_id,
                "facts_shared": shared_count,
            })
            target_orch._emitter.emit("fact.received", {
                "source_session_id": source_session_id,
                "facts_received": shared_count,
            })

            _json_response(self, 200, {
                "facts_shared": shared_count,
                "source_session_id": source_session_id,
                "target_session_id": target_session_id,
            })
        except Exception as exc:
            logger.exception("Share facts failed from %s", source_session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    def _handle_feedback(self, session_id: str) -> None:
        """Adjust fact confidence or reject a fact.

        Request body::

            {
                "fact_id": "...",
                "action": "boost" | "penalize" | "reject",
                "delta": 0.1,
                "reason": "User confirmed this fact"
            }
        """
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return

        fact_id = body.get("fact_id", "")
        action = body.get("action", "")
        if not fact_id or action not in ("boost", "penalize", "reject"):
            _json_response(self, 400, {
                "error": "fact_id and action (boost|penalize|reject) required",
            })
            return

        delta = max(0.0, min(1.0, float(body.get("delta", 0.1))))
        reason = body.get("reason", "sidecar-feedback")

        try:
            if action == "boost":
                orch.boost_fact(fact_id, delta=delta, reason=reason)
            elif action == "penalize":
                orch.penalize_fact(fact_id, delta=delta, reason=reason)
            elif action == "reject":
                orch.reject_fact(fact_id, reason=reason)

            _json_response(self, 200, {
                "fact_id": fact_id,
                "action": action,
                "applied": True,
            })
        except Exception as exc:
            logger.exception("Feedback failed for fact %s in session %s", fact_id, session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Envelope preview ─────────────────────────────────────

    def _handle_preview_envelope(self, session_id: str, params: dict) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            task = params.get("task", ["Preview task"])[0]
            system = params.get("system", ["You are a helpful assistant."])[0]
            ep = orch.preview_envelope(system, task)
            _json_response(self, 200, {
                "total_tokens": ep.total_tokens,
                "envelope_tokens": ep.envelope_tokens,
                "generation_reserve": ep.generation_reserve,
                "facts_included": ep.facts_included,
                "facts_available": ep.facts_available,
                "saturation": round(ep.saturation, 4),
            })
        except Exception as exc:
            logger.exception("Envelope preview failed for session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Cost estimation ──────────────────────────────────────

    def _handle_estimate(self, session_id: str) -> None:
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return
        system_prompt = body.get("system_prompt", "You are a helpful assistant.")
        task_input = body.get("task_input", "")
        planned = body.get("planned_dispatches", 1)
        if not task_input:
            _json_response(self, 400, {"error": "task_input is required"})
            return
        try:
            est = orch.estimate_session(system_prompt, task_input,
                                        planned_dispatches=planned)
            _json_response(self, 200, {
                "estimated_input_tokens": est.estimated_input_tokens,
                "estimated_output_tokens": est.estimated_output_tokens,
                "estimated_windows": est.estimated_windows,
                "estimated_cost_usd": est.estimated_cost_usd
                if hasattr(est, "estimated_cost_usd") else None,
            })
        except Exception as exc:
            logger.exception("Cost estimation failed for session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})

    # ── Provider registration ────────────────────────────────

    def _handle_register_provider(self, session_id: str) -> None:
        """Register a fallback provider for this session.

        Request body::

            {
                "model": "gpt-4",
                "context_window": 128000
            }
        """
        orch = self._get_session(session_id)
        if orch is None:
            return
        try:
            body = _read_body(self)
        except ValueError as exc:
            _json_response(self, 413, {"error": _sanitize_error(exc)})
            return

        model_name = body.get("model", "")
        context_window = body.get("context_window", 128_000)
        if not model_name:
            _json_response(self, 400, {"error": "model name required"})
            return
        try:
            from crp.providers.custom import CustomProvider

            provider = CustomProvider(
                generate_fn=lambda msgs, **kw: ("", "stop"),
                count_tokens_fn=lambda t: max(1, len(t) // 4),
                context_size=context_window,
                name=model_name,
            )
            orch.register_provider(provider)
            _json_response(self, 200, {
                "registered": True,
                "model": model_name,
                "context_window": context_window,
            })
        except Exception as exc:
            logger.exception("Provider registration failed for session %s", session_id)
            _json_response(self, 500, {"error": _sanitize_error(exc)})


# ── Server factory ───────────────────────────────────────────────────


def start_sidecar(
    host: str = "127.0.0.1",
    port: int = 9470,
    auth_token: str | None = None,
    max_body_bytes: int = 10 * 1024 * 1024,
    max_sessions: int = 64,
    rate_limit: int = 120,
    rate_window: int = 60,
    dispatch_rate_limit: int = 30,
    dispatch_rate_window: int = 60,
) -> HTTPServer:
    """Start the CRP HTTP sidecar.

    The sidecar is **optional** — it is never started automatically by the
    library.  Users must explicitly invoke ``crp serve`` or call this
    function from their own code.

    Args:
        host: Bind address.  Default ``127.0.0.1`` (loopback only).
        port: Port number.  Default ``9470``.
        auth_token: Bearer token for authentication.  **Strongly
            recommended** when binding to non-loopback addresses.
        max_body_bytes: Maximum request body size (default 10 MB).
        max_sessions: Maximum concurrent sessions (default 64).
        rate_limit: Maximum requests per IP per rate window (default 120).
        rate_window: Rate-limit window in seconds (default 60).
        dispatch_rate_limit: Max dispatch requests per caller per window (default 30).
        dispatch_rate_window: Dispatch rate-limit window in seconds (default 60).

    Returns:
        HTTPServer instance (call ``.serve_forever()`` to start).
    """
    global _auth_token, _max_body_bytes, _max_sessions
    global _rate_max_requests, _rate_window_seconds
    global _dispatch_rate_max, _dispatch_rate_window

    # Enforce auth when binding to non-loopback addresses (§audit3 SEC-H4)
    if host not in ("127.0.0.1", "localhost", "::1") and auth_token is None:
        raise ValueError(
            f"Binding to '{host}' without auth_token is insecure. "
            "Pass auth_token or bind to 127.0.0.1 for local-only access."
        )

    if auth_token is None:
        logger.warning(
            "Sidecar starting without auth_token on %s:%d — "
            "unauthenticated access allowed (§audit4 SEC-H1)",
            host, port,
        )

    _auth_token = auth_token
    _max_body_bytes = max_body_bytes
    _max_sessions = max_sessions
    _rate_max_requests = rate_limit
    _rate_window_seconds = rate_window
    _dispatch_rate_max = dispatch_rate_limit
    _dispatch_rate_window = dispatch_rate_window

    server = HTTPServer((host, port), CRPSidecarHandler)
    logger.info("CRP sidecar started on %s:%d (auth=%s, max_sessions=%d)",
                host, port, "enabled" if auth_token else "disabled", max_sessions)
    return server
