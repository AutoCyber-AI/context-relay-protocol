# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage tests for ``crp.cli.sidecar`` — the HTTP sidecar (§9.3).

The sidecar is a stdlib ``http.server.HTTPServer``; each test starts a real
server on an ephemeral port (port=0) in a daemon thread and talks to it over
loopback HTTP via ``urllib``.  No external network is touched.

Note: ``start_sidecar`` mutates module-level globals, and the rate-limit
counters are module-level dicts — the fixtures here snapshot and restore all
of that so tests stay independent.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from crp.cli import sidecar


def _request(
    port: int,
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    headers: dict | None = None,
) -> tuple[int, dict | str]:
    """Perform one HTTP request against the sidecar; return (status, parsed)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
    )
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        status = exc.code
    try:
        return status, json.loads(raw)
    except (ValueError, TypeError):
        return status, raw


def _reset_rate_counters() -> None:
    """Reset module-level session and rate-limit state between tests."""
    with sidecar._sessions_lock:
        for orch in sidecar._active_sessions.values():
            try:
                orch.close()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
        sidecar._active_sessions.clear()
        sidecar._session_owners.clear()
    sidecar._rate_counters.clear()
    sidecar._dispatch_counters.clear()


@pytest.fixture
def sidecar_server(monkeypatch):
    """Start an unauthenticated sidecar on an ephemeral port; yield its port."""
    _reset_rate_counters()
    server = sidecar.start_sidecar(host="127.0.0.1", port=0, auth_token=None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


@pytest.fixture
def sidecar_auth_server(monkeypatch):
    """Start an authenticated sidecar (token = 'secret-token')."""
    _reset_rate_counters()
    server = sidecar.start_sidecar(
        host="127.0.0.1", port=0, auth_token="secret-token",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def _create_session(port: int, body: dict | None = None) -> str:
    status, payload = _request(port, "POST", "/sessions", body or {})
    assert status == 201, payload
    return payload["session_id"]


# ── Health & misc ───────────────────────────────────────────────────────


def test_health(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "GET", "/health")
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["auth_required"] is False
    assert "version" in payload


def test_ready_probe(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "GET", "/ready")
    assert status == 200
    assert payload["ready"] is True


def test_ready_probe_full(sidecar_server, monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_max_sessions", 0)
    status, payload = _request(sidecar_server, "GET", "/ready")
    assert status == 503
    assert payload["ready"] is False


def test_metrics_endpoint(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "GET", "/metrics")
    assert status == 200
    assert "sidecar_active_sessions" in payload


def test_unknown_get_route(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "GET", "/nope")
    assert status == 404
    assert payload["error"] == "Not found"


def test_unknown_post_route(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "POST", "/nope", {})
    assert status == 404


def test_start_sidecar_rejects_remote_bind_without_auth() -> None:
    with pytest.raises(ValueError, match="without auth_token is insecure"):
        sidecar.start_sidecar(host="0.0.0.0", port=0)


# ── Sessions ────────────────────────────────────────────────────────────


def test_create_and_list_sessions(sidecar_server) -> None:
    sid = _create_session(sidecar_server, {"context_window": 4096, "model": "m1"})
    assert sid
    status, payload = _request(sidecar_server, "GET", "/sessions")
    assert status == 200
    ids = [s["session_id"] for s in payload["sessions"]]
    assert sid in ids


def test_create_session_default_body(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    assert sid


def test_session_status(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(sidecar_server, "GET", f"/sessions/{sid}/status")
    assert status == 200
    assert payload["session_id"]
    assert "windows_completed" in payload


def test_session_status_unknown_id(sidecar_server) -> None:
    status, payload = _request(sidecar_server, "GET", "/sessions/unknown-id/status")
    assert status == 404
    assert payload["error"] == "Not found"


def test_close_session(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(sidecar_server, "POST", f"/sessions/{sid}/close", {})
    assert status == 200
    assert payload["closed"] is True
    status, _ = _request(sidecar_server, "GET", f"/sessions/{sid}/status")
    assert status == 404


def test_max_sessions_limit(sidecar_server, monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_max_sessions", 1)
    _create_session(sidecar_server)
    status, payload = _request(sidecar_server, "POST", "/sessions", {})
    assert status == 503
    assert "Max sessions" in payload["error"]


# ── Ingest / facts ──────────────────────────────────────────────────────


def test_ingest_and_get_facts(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/ingest",
        {"text": "CRP provides unbounded context for agentic AI.", "label": "doc"},
    )
    assert status == 200, payload
    assert payload["source_label"] == "doc"
    assert isinstance(payload["fact_ids"], list)

    status, payload = _request(sidecar_server, "GET", f"/sessions/{sid}/facts?limit=10")
    assert status == 200
    assert isinstance(payload["facts"], list)
    assert "total" in payload


def test_ingest_requires_text(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(sidecar_server, "POST", f"/sessions/{sid}/ingest", {})
    assert status == 400
    assert "text is required" in payload["error"]


def test_share_facts_between_sessions(sidecar_server) -> None:
    source = _create_session(sidecar_server)
    target = _create_session(sidecar_server)
    _request(
        sidecar_server, "POST", f"/sessions/{source}/ingest",
        {"text": "Fact one. Fact two. Fact three about architecture."},
    )
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{source}/facts/share",
        {"target_session_id": target, "limit": 10, "min_confidence": 0.0},
    )
    assert status == 200, payload
    assert payload["target_session_id"] == target
    assert payload["facts_shared"] >= 1

    status, payload = _request(sidecar_server, "GET", f"/sessions/{target}/facts")
    assert status == 200
    assert payload["total"] >= 1


def test_share_facts_requires_target(sidecar_server) -> None:
    source = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{source}/facts/share", {},
    )
    assert status == 400
    assert "target_session_id is required" in payload["error"]


def test_share_facts_unknown_target(sidecar_server) -> None:
    source = _create_session(sidecar_server)
    status, _ = _request(
        sidecar_server, "POST", f"/sessions/{source}/facts/share",
        {"target_session_id": "missing"},
    )
    assert status == 404


def test_fact_feedback_validation(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    _request(
        sidecar_server, "POST", f"/sessions/{sid}/ingest",
        {"text": "Something extractable about databases."},
    )
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/facts/feedback", {},
    )
    assert status == 400

    status, payload = _request(sidecar_server, "GET", f"/sessions/{sid}/facts")
    fact_id = payload["facts"][0]["id"]
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/facts/feedback",
        {"fact_id": fact_id, "action": "boost", "delta": 0.2, "reason": "confirmed"},
    )
    assert status == 200
    assert payload["applied"] is True

    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/facts/feedback",
        {"fact_id": fact_id, "action": "reject"},
    )
    assert status == 200


def test_fact_feedback_unknown_fact_silently_succeeds(sidecar_server) -> None:
    # DOCUMENTED BEHAVIOR: boosting an unknown fact id does not raise — the
    # feedback loop no-ops and the endpoint still reports success.
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/facts/feedback",
        {"fact_id": "no-such-fact", "action": "boost"},
    )
    assert status == 200
    assert payload["applied"] is True


def test_fact_feedback_error_sanitized(sidecar_server, monkeypatch) -> None:
    from crp.core.orchestrator import CRPOrchestrator

    def _boom(self, fact_id, delta=0.1, reason=""):
        raise RuntimeError("internal details must not leak")

    monkeypatch.setattr(CRPOrchestrator, "boost_fact", _boom)
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/facts/feedback",
        {"fact_id": "f1", "action": "boost"},
    )
    assert status == 500
    # Internal error details must be sanitized (no leak of internals).
    assert payload["error"] == "Internal server error"


# ── Dispatch variants ───────────────────────────────────────────────────


def test_dispatch_requires_task_input(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch", {},
    )
    assert status == 400
    assert "task_input is required" in payload["error"]


def test_dispatch_unknown_variant(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/bogus",
        {"task_input": "hi"},
    )
    assert status == 400
    assert "Unknown dispatch variant" in payload["error"]


def test_dispatch_basic(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch",
        {"task_input": "Say hello.", "system_prompt": "Be brief."},
    )
    assert status == 200, payload
    assert payload["variant"] == "basic"
    assert "quality_tier" in payload
    assert payload["session_id"] == sid


def test_dispatch_tools_requires_tools(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/tools",
        {"task_input": "hi", "tools": []},
    )
    assert status == 400
    assert "tools list required" in payload["error"]


def test_dispatch_reflexive_and_progressive(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/reflexive",
        {"task_input": "hi", "depth": 1},
    )
    assert status == 200, payload

    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/progressive",
        {"task_input": "hi"},
    )
    assert status == 200, payload


def test_dispatch_stream_augmented(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/stream-augmented",
        {"task_input": "hi"},
    )
    assert status == 200, payload
    assert payload["variant"] == "stream-augmented"


def test_dispatch_agentic(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/dispatch/agentic",
        {"task_input": "hi"},
    )
    assert status == 200, payload


def test_envelope_preview(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "GET",
        f"/sessions/{sid}/envelope?task=What+is+CRP&system=Be+terse",
    )
    assert status == 200, payload
    assert "total_tokens" in payload
    assert "facts_available" in payload


def test_estimate(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/estimate",
        {"task_input": "Estimate me", "planned_dispatches": 2},
    )
    assert status == 200, payload
    assert "estimated_input_tokens" in payload


def test_register_provider(sidecar_server) -> None:
    sid = _create_session(sidecar_server)
    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/providers",
        {"model": "gpt-4", "context_window": 8192},
    )
    assert status == 200, payload
    assert payload["registered"] is True

    status, payload = _request(
        sidecar_server, "POST", f"/sessions/{sid}/providers", {},
    )
    assert status == 400
    assert "model name required" in payload["error"]


# ── Auth & rate limiting ────────────────────────────────────────────────


def test_auth_required_without_token(sidecar_auth_server) -> None:
    status, payload = _request(sidecar_auth_server, "GET", "/health")
    assert status == 401
    assert payload["detail"] == "Bearer token required"


def test_auth_rejects_wrong_token(sidecar_auth_server) -> None:
    status, payload = _request(
        sidecar_auth_server, "GET", "/health", token="wrong",
    )
    assert status == 401
    assert payload["detail"] == "Invalid bearer token"


def test_auth_allows_correct_token(sidecar_auth_server) -> None:
    status, payload = _request(
        sidecar_auth_server, "GET", "/health", token="secret-token",
    )
    assert status == 200
    assert payload["auth_required"] is True


def _create_authed_session(port: int, token: str) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/sessions", data=b"{}", method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["session_id"]


def test_check_session_access_unit(monkeypatch) -> None:
    """403 ownership branch: reachable only when owners differ.

    With a single shared auth token every authenticated caller hashes to the
    same owner, so the HTTP layer alone can never hit the 403 — exercise the
    helper directly with a fake handler.
    """
    import io

    class _FakeHandler:
        def __init__(self, token: str) -> None:
            self.headers = {"Authorization": f"Bearer {token}"}
            self.client_address = ("127.0.0.1", 0)
            self.wfile = io.BytesIO()
            self.status: int | None = None

        def send_response(self, status: int) -> None:
            self.status = status

        def send_header(self, *args) -> None:
            pass

        def end_headers(self) -> None:
            pass

    monkeypatch.setattr(sidecar, "_auth_token", "secret-token")
    try:
        owner_hash = sidecar._token_hash("secret-token")
        sidecar._session_owners["owned"] = owner_hash
        sidecar._session_owners["foreign"] = sidecar._token_hash("another")

        ok_handler = _FakeHandler("secret-token")
        assert sidecar._check_session_access(ok_handler, "owned") is True

        denied_handler = _FakeHandler("secret-token")
        assert sidecar._check_session_access(denied_handler, "foreign") is False
        assert denied_handler.status == 403
    finally:
        sidecar._session_owners.clear()
        monkeypatch.undo()


def test_list_sessions_filters_other_owned(sidecar_auth_server) -> None:
    sid = _create_authed_session(sidecar_auth_server, "secret-token")
    # Seed a session owned by a different caller; it must be filtered out.
    with sidecar._sessions_lock:
        sidecar._active_sessions["foreign-session"] = object()
        sidecar._session_owners["foreign-session"] = "foreign-owner"
    try:
        status, payload = _request(
            sidecar_auth_server, "GET", "/sessions", token="secret-token",
        )
        assert status == 200
        ids = [s["session_id"] for s in payload["sessions"]]
        assert sid in ids
        assert "foreign-session" not in ids
    finally:
        with sidecar._sessions_lock:
            sidecar._active_sessions.pop("foreign-session", None)
            sidecar._session_owners.pop("foreign-session", None)


def test_rate_limiting(sidecar_server, monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_rate_max_requests", 3)
    monkeypatch.setattr(sidecar, "_rate_window_seconds", 60)
    statuses = [
        _request(sidecar_server, "GET", "/health")[0] for _ in range(5)
    ]
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_dispatch_rate_limiting(sidecar_server, monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_dispatch_rate_max", 2)
    monkeypatch.setattr(sidecar, "_dispatch_rate_window", 60)
    sid = _create_session(sidecar_server)
    statuses = [
        _request(
            sidecar_server, "POST", f"/sessions/{sid}/dispatch",
            {"task_input": f"req {i}"},
        )[0]
        for i in range(4)
    ]
    assert statuses[:2] == [200, 200]
    assert 429 in statuses[2:]


def test_oversized_body_rejected(sidecar_server, monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_max_body_bytes", 64)
    status, payload = _request(
        sidecar_server, "POST", "/sessions",
        {"model": "x" * 200},
    )
    assert status == 413
    assert "Invalid input" in payload["error"]


# ── Unit-level helpers ──────────────────────────────────────────────────


def test_sanitize_error_variants() -> None:
    from crp.core.errors import CRPError

    assert sidecar._sanitize_error(ValueError("boom")) == "Invalid input: ValueError"
    err = CRPError(code=1001, message="something failed")
    sanitized = sidecar._sanitize_error(err)
    assert sanitized.startswith("CRP-1001")
    assert "something failed" in sanitized
    assert sidecar._sanitize_error(RuntimeError("secret internals")) == "Internal server error"


def test_token_hash_and_caller_helpers() -> None:
    assert sidecar._token_hash("abc") == sidecar._token_hash("abc")
    assert sidecar._token_hash("abc") != sidecar._token_hash("abd")
