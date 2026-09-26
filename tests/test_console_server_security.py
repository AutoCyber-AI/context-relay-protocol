# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Security tests for the local demo/console servers (SPEC-015).

Covers the hardening of the two user-run demo servers:

* ``examples/crp_demos/server.py`` — stdlib ``ThreadingHTTPServer`` (port 8770).
* ``examples/self_hosted_console.py`` — FastAPI console + OpenAI-compatible
  endpoint (port 8000).

Both must bind loopback by default, emit CORS headers only for allowlisted
origins (never ``*``), and support an optional bearer token with a loud
warning when bound beyond loopback without one.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from examples import self_hosted_console as console_mod
from examples.crp_demos import server as demo_server

# ── stdlib demo server (examples/crp_demos/server.py) ───────────────────────


@pytest.fixture()
def demo_httpd() -> Iterator[object]:
    server = demo_server.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(server: object, path: str, origin: str | None = None) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])  # type: ignore[attr-defined]
    headers = {"Origin": origin} if origin else {}
    conn.request("GET", path, headers=headers)
    return conn.getresponse()


def _post(server: object, path: str, payload: dict, origin: str | None = None,
          token: str | None = None) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])  # type: ignore[attr-defined]
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request("POST", path, body=json.dumps(payload), headers=headers)
    return conn.getresponse()


def test_demo_bind_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRP_HOST", raising=False)
    monkeypatch.delenv("CRP_DEMO_TOKEN", raising=False)
    args = demo_server.build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.token is None


def test_demo_host_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRP_HOST", "0.0.0.0")
    args = demo_server.build_parser().parse_args([])
    assert args.host == "0.0.0.0"


def test_demo_allowlisted_origin_gets_cors_headers(demo_httpd: object) -> None:
    port = demo_httpd.server_address[1]  # type: ignore[attr-defined]
    for origin in ("https://console.crprotocol.io", f"http://127.0.0.1:{port}"):
        resp = _get(demo_httpd, "/api/detect", origin=origin)
        body = resp.read()
        assert resp.status == 200, body
        assert resp.getheader("Access-Control-Allow-Origin") == origin
        resp.close()


def test_demo_non_allowlisted_origin_gets_no_cors_headers(demo_httpd: object) -> None:
    resp = _get(demo_httpd, "/api/detect", origin="https://evil.example")
    resp.read()
    assert resp.getheader("Access-Control-Allow-Origin") is None
    resp.close()


def test_demo_preflight_allowed_only_for_allowlist(demo_httpd: object) -> None:
    port = demo_httpd.server_address[1]  # type: ignore[attr-defined]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("OPTIONS", "/api/context/new",
                 headers={"Origin": "https://console.crprotocol.io",
                          "Access-Control-Request-Method": "POST"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 204
    assert resp.getheader("Access-Control-Allow-Origin") == "https://console.crprotocol.io"
    assert "POST" in (resp.getheader("Access-Control-Allow-Methods") or "")
    resp.close()

    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("OPTIONS", "/api/context/new", headers={"Origin": "https://evil.example"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 403
    assert resp.getheader("Access-Control-Allow-Origin") is None
    resp.close()


def test_demo_sse_never_sends_star_cors(demo_httpd: object) -> None:
    # The SSE endpoint is the one that historically emitted "*". It must now
    # send no CORS headers at all for non-allowlisted origins.
    resp = _get(demo_httpd, "/api/compare/stream?run_id=missing", origin="https://evil.example")
    resp.close()
    assert resp.getheader("Access-Control-Allow-Origin") is None


def test_demo_lan_bind_without_token_warns() -> None:
    warning = demo_server.exposure_warning("0.0.0.0", None)
    assert warning is not None
    assert "WARNING" in warning
    assert demo_server.exposure_warning("192.168.1.5", None) is not None
    # Loopback, or any bind with a token set, stays quiet.
    assert demo_server.exposure_warning("127.0.0.1", None) is None
    assert demo_server.exposure_warning("localhost", None) is None
    assert demo_server.exposure_warning("0.0.0.0", "secret") is None


def test_demo_bearer_token_enforced() -> None:
    server = demo_server.create_server("127.0.0.1", 0, token="secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        resp = _post(server, "/api/context/new", {})
        assert resp.status == 401
        resp.read()
        resp.close()

        resp = _post(server, "/api/context/new", {}, token="wrong")
        assert resp.status == 401
        resp.read()
        resp.close()

        resp = _post(server, "/api/context/new", {}, token="secret")
        body = resp.read()
        assert resp.status == 200, body
        assert json.loads(body)["session_id"]
        resp.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ── FastAPI self-hosted console (examples/self_hosted_console.py) ───────────


def test_console_bind_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRP_HOST", raising=False)
    monkeypatch.delenv("CRP_CONSOLE_TOKEN", raising=False)
    args = console_mod.build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.token is None


def test_console_allowlist_contains_cdn_and_own_origin() -> None:
    allowlist = console_mod._cors_allowlist("127.0.0.1", 8000)
    assert "https://console.crprotocol.io" in allowlist  # CDN console connect bar
    assert "http://localhost:8000" in allowlist
    assert "http://127.0.0.1:8000" in allowlist
    assert "http://127.0.0.1:8000" in allowlist  # server's own origin
    assert "*" not in allowlist


def test_console_cors_allowlisted_origin() -> None:
    client = TestClient(console_mod.build_app("127.0.0.1", 8000))
    resp = client.get("/health", headers={"Origin": "https://console.crprotocol.io"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://console.crprotocol.io"


def test_console_cors_non_allowlisted_origin_gets_no_headers() -> None:
    client = TestClient(console_mod.build_app("127.0.0.1", 8000))
    resp = client.get("/health", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_console_bearer_token_enforced_on_v1() -> None:
    client = TestClient(console_mod.build_app("127.0.0.1", 8000, token="secret"))
    # /v1/* requires the token...
    assert client.get("/v1/tel/stream").status_code == 401
    assert client.post("/v1/chat/completions", json={"messages": []}).status_code == 401
    # ...but /health and the console page stay open.
    assert client.get("/health").status_code == 200
    assert client.get("/crp/console").status_code == 200
    # A wrong token is rejected, a correct one passes the guard.
    assert client.get("/v1/tel/stream",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/tel/stream",
                      headers={"Authorization": "Bearer secret"}).status_code != 401


def test_console_lan_bind_without_token_warns() -> None:
    warning = console_mod._exposure_warning("0.0.0.0", None)
    assert warning is not None
    assert "WARNING" in warning
    assert console_mod._exposure_warning("192.168.1.5", None) is not None
    # Loopback, or any bind with a token set, stays quiet.
    assert console_mod._exposure_warning("127.0.0.1", None) is None
    assert console_mod._exposure_warning("localhost", None) is None
    assert console_mod._exposure_warning("0.0.0.0", "secret") is None


def test_console_is_loopback_helper() -> None:
    assert console_mod._is_loopback("127.0.0.1")
    assert console_mod._is_loopback("localhost")
    assert console_mod._is_loopback("::1")
    assert not console_mod._is_loopback("0.0.0.0")
    assert not console_mod._is_loopback("192.168.1.5")
