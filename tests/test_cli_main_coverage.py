# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage tests for ``crp.cli.main`` — the Click CLI entry point (§9.5).

``cli()`` is a plain function that builds the Click group lazily and invokes
it with ``standalone_mode=True``, so it cannot be passed to
``CliRunner.invoke`` directly.  These tests run it inside
``CliRunner.isolation()`` with ``sys.argv`` patched — exactly how the real
console script invokes it.  All LLM-facing paths use the built-in stub
``CustomProvider``; no network access occurs.
"""

from __future__ import annotations

import json
import sys
import uuid

import pytest

pytest.importorskip("click")

from click.testing import CliRunner

from crp.cli import main as cli_main

runner = CliRunner()


def _invoke(args: list[str], stdin_text: str = "") -> tuple[int, str, str]:
    """Run ``crp <args>`` and return (exit_code, stdout, stderr)."""
    with runner.isolation(input=stdin_text) as (out, err, _files):
        old_argv = sys.argv
        sys.argv = ["crp", *args]
        code = 0
        try:
            cli_main.cli()
        except SystemExit as exc:  # standalone_mode raises SystemExit
            code = exc.code if isinstance(exc.code, int) else 1
        finally:
            sys.argv = old_argv
        # Read the buffers before exiting isolation: the win32 UTF-8 wrapper
        # created inside cli() may be garbage-collected afterwards, and its
        # finalizer closes the underlying BytesIO.
        stdout_text = out.getvalue().decode("utf-8")
        stderr_text = err.getvalue().decode("utf-8")
    return code, stdout_text, stderr_text


def _init_session(args: list[str] | None = None) -> str:
    """Run ``crp init`` and return the new session ID."""
    code, out, err = _invoke(["init", *(args or [])])
    assert code == 0, err
    return out.strip()


def test_cli_version_currently_broken() -> None:
    # DOCUMENTED BUG (not fixed — source change forbidden): the CLI declares
    # ``click.version_option(package_name="crp")`` but the installed
    # distribution is named ``crprotocol``, so importlib.metadata lookup
    # raises RuntimeError("'crp' is not installed") at runtime.
    with pytest.raises(RuntimeError, match="'crp' is not installed"):
        _invoke(["--version"])


def test_cli_help() -> None:
    code, out, _ = _invoke(["--help"])
    assert code == 0
    for cmd in ("init", "dispatch", "ingest", "status", "preview", "serve", "scan"):
        assert cmd in out


def test_init_plain_outputs_uuid() -> None:
    session_id = _init_session()
    uuid.UUID(session_id)  # raises if not a valid UUID
    assert session_id in cli_main._sessions


def test_init_json_output() -> None:
    code, out, _ = _invoke([
        "init", "--model", "test-model", "--context-window", "8192",
        "--max-output", "1024", "--timeout", "3600", "--json",
    ])
    assert code == 0, out
    payload = json.loads(out)
    assert payload["model"] == "test-model"
    assert payload["context_window"] == 8192
    assert payload["startup_ok"] is True
    uuid.UUID(payload["session_id"])


def test_dispatch_unknown_session_errors() -> None:
    code, out, err = _invoke([
        "dispatch", "--session", "does-not-exist", "--task", "hello",
    ])
    assert code == 1
    # Click's CliRunner may merge stderr into the stdout buffer depending on
    # platform/version, so assert on the combined output.
    assert "unknown session" in (out + err).lower()


def test_dispatch_auto_session() -> None:
    code, out, err = _invoke(["dispatch", "--task", "Hello there"])
    assert code == 0, err
    assert out.strip() == ""


def test_dispatch_with_session_json() -> None:
    session_id = _init_session()
    code, out, err = _invoke([
        "dispatch", "--session", session_id, "--task", "Summarise CRP.",
        "--system", "Be terse.", "--json",
    ])
    assert code == 0, err
    payload = json.loads(out)
    # NOTE: the reported session_id is the orchestrator's internal session id
    # (freshly minted by CRPOrchestrator), not the CLI-level session key.
    uuid.UUID(payload["session_id"])
    assert "window_id" in payload
    assert "facts_extracted" in payload


def test_ingest_from_stdin() -> None:
    session_id = _init_session()
    code, out, err = _invoke(
        ["ingest", "--session", session_id, "--label", "notes"],
        stdin_text="CRP is a context orchestration protocol.",
    )
    assert code == 0, err
    assert "Ingested" in out
    assert "notes" in out


def test_ingest_from_file(tmp_path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("The quick brown fox jumps over the lazy dog.", encoding="utf-8")
    session_id = _init_session()
    code, out, err = _invoke([
        "ingest", "--session", session_id, str(doc), "--json",
    ])
    assert code == 0, err
    payload = json.loads(out)
    assert payload["source_label"] == "stdin"
    assert isinstance(payload["fact_ids"], list)


def test_ingest_unknown_session() -> None:
    code, _, _ = _invoke(
        ["ingest", "--session", "nope", "--label", "x"],
        stdin_text="text",
    )
    assert code == 1


def test_status_outputs_json() -> None:
    session_id = _init_session()
    code, out, err = _invoke(["status", "--session", session_id])
    assert code == 0, err
    payload = json.loads(out)
    # NOTE: reports the orchestrator's internal session id (see dispatch test).
    uuid.UUID(payload["session_id"])
    assert "windows_completed" in payload
    assert "overhead_ratio" in payload


def test_preview_envelope() -> None:
    session_id = _init_session()
    code, out, err = _invoke([
        "preview", "--session", session_id, "--task", "What is CRP?",
    ])
    assert code == 0, err
    payload = json.loads(out)
    assert "total_tokens" in payload
    assert "saturation" in payload


def test_serve_bind_all_requires_auth() -> None:
    code, _, err = _invoke(["serve", "--bind-all"])
    assert code == 1
    assert "--bind-all requires --auth-token" in err


def test_serve_start_and_shutdown(monkeypatch) -> None:
    from crp.cli import sidecar as sidecar_mod

    calls: dict[str, object] = {}

    class _FakeServer:
        def serve_forever(self) -> None:
            calls["served"] = True
            raise KeyboardInterrupt

        def shutdown(self) -> None:
            calls["shutdown"] = True

    monkeypatch.setattr(sidecar_mod, "start_sidecar", lambda **kw: _FakeServer())
    code, out, err = _invoke(["serve", "--port", "0"])
    assert code == 0, err
    assert "CRP sidecar starting on 127.0.0.1:0" in out
    assert "Auth: DISABLED" in out
    assert "POST /sessions/:id/facts/share" in out
    assert calls.get("served") is True
    assert calls.get("shutdown") is True


# ── crp scan ────────────────────────────────────────────────────────────

_VIOLATING_SOURCE = "from openai import OpenAI\nclient = OpenAI()\n"
_GOVERNED_SOURCE = "from crp import Client\nclient = Client()\n"


@pytest.fixture
def scan_dir(tmp_path):
    """Tmp directory containing one violating and one governed file."""
    (tmp_path / "bad.py").write_text(_VIOLATING_SOURCE, encoding="utf-8")
    (tmp_path / "good.py").write_text(_GOVERNED_SOURCE, encoding="utf-8")
    (tmp_path / "not_source.txt").write_text("OpenAI(", encoding="utf-8")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "bad.py").write_text(_VIOLATING_SOURCE, encoding="utf-8")
    return tmp_path


def _run_scan(scan_dir, *extra: str):
    return _invoke(["scan", "--paths", str(scan_dir), *extra])


def test_scan_json_format(scan_dir) -> None:
    code, out, err = _run_scan(scan_dir, "--report-only")
    assert code == 0, err
    findings = json.loads(out)
    assert isinstance(findings, list)
    # Only the ungoverned source file is flagged; governed/hidden/txt skipped.
    files = {f["file"] for f in findings}
    assert files == {str(scan_dir / "bad.py")}
    assert all(f["rule_id"] == "CRP001" for f in findings)
    assert all(f["severity"] == "HIGH" for f in findings)


def test_scan_fails_on_high_by_default(scan_dir) -> None:
    code, _, _ = _run_scan(scan_dir)
    assert code == 1


def test_scan_fail_on_critical_passes_with_only_high(scan_dir) -> None:
    code, _, err = _run_scan(scan_dir, "--fail-on", "CRITICAL", "--report-only")
    assert code == 0, err


def test_scan_text_format(scan_dir) -> None:
    code, out, err = _run_scan(scan_dir, "--format", "text", "--report-only")
    assert code == 0, err
    assert "CRP001: HIGH" in out
    assert "bad.py" in out


def test_scan_sarif_stdout_and_file(scan_dir, tmp_path) -> None:
    sarif_path = tmp_path / "out.sarif"
    code, out, err = _run_scan(
        scan_dir, "--format", "sarif", "--report-only",
        "--sarif", str(sarif_path), "--summary", str(tmp_path / "summary.md"),
    )
    assert code == 0, err
    doc = json.loads(out)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"][0]["ruleId"] == "CRP001"

    written = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert written["runs"][0]["results"]
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "# CRP Scan Summary" in summary
    assert "| HIGH | 1 |" in summary


def test_scan_min_version_finding(scan_dir) -> None:
    code, out, err = _run_scan(scan_dir, "--min-version", "999.0.0", "--report-only")
    assert code == 0, err
    findings = json.loads(out)
    assert findings[0]["rule_id"] == "CRP005"
    assert findings[0]["severity"] == "CRITICAL"


def test_scan_skips_missing_path() -> None:
    code, out, _ = _invoke([
        "scan", "--paths", "/nonexistent/path/xyz", "--report-only",
    ])
    assert code == 0
    assert json.loads(out) == []


def test_scan_min_grounding_advisory(scan_dir) -> None:
    code, _, err = _run_scan(scan_dir, "--min-grounding", "0.9", "--report-only")
    assert code == 0, err


def test_scan_remediate_prints_plan(scan_dir) -> None:
    code, out, err = _invoke(["scan-remediate", "--paths", str(scan_dir)])
    assert code == 0, err
    plan = json.loads(out)
    assert isinstance(plan["proposals"], list)
    assert len(plan["proposals"]) >= 1
    prop = plan["proposals"][0]
    for key in ("proposal_id", "rule_id", "file_path", "remediation_class",
                "title", "description", "diff", "config_snippet", "pr_branch"):
        assert key in prop


def test_scan_remediate_clean_repo_empty_plan(tmp_path) -> None:
    code, out, err = _invoke(["scan-remediate", "--paths", str(tmp_path)])
    assert code == 0, err
    plan = json.loads(out)
    assert plan["proposals"] == []


def test_scan_remediate_requires_gh_token_for_pr_mode(scan_dir, monkeypatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    code, _, err = _invoke([
        "scan-remediate", "--paths", str(scan_dir),
        "--repo", "owner/repo", "--branch", "crp-remediation",
    ])
    assert code == 1
    assert "--gh-token" in err


def test_build_remediation_pr_body() -> None:
    from crp.scan.remediation import RemediationEngine, ScanFinding

    engine = RemediationEngine()
    finding = ScanFinding(
        rule_id="CRP001",
        file_path="src/app.py",
        line=2,
        message="Direct OpenAI client instantiation without CRP governance",
        severity="error",
        provider="openai",
        call_expression="OpenAI()",
        code_context=["client = OpenAI()"],
        has_crp_import=False,
    )
    proposal = engine.propose_fix(finding)
    body = cli_main._build_remediation_pr_body([proposal])
    assert "## CRP Scan — Automated Remediation" in body
    assert "CRP001" in body
    assert "src/app.py:2" in body


# ── crp download-models ─────────────────────────────────────────────────


def test_download_models_single(monkeypatch) -> None:
    import crp.ml.downloader as downloader

    monkeypatch.setattr(
        downloader, "download_model", lambda key, model_dir=None: f"/models/{key}",
    )
    code, out, err = _invoke(["download-models", "--model", "intent"])
    assert code == 0, err
    assert "crp.isa.intent -> /models/crp.isa.intent" in out


def test_download_models_all(monkeypatch) -> None:
    import crp.ml.downloader as downloader

    monkeypatch.setattr(downloader, "download_all", lambda model_dir=None: {
        "crp.isa.intent": "/m/intent",
        "crp.security.safety": "/m/safety",
    })
    code, out, err = _invoke(["download-models", "--model-dir", "/tmp/models"])
    assert code == 0, err
    assert "crp.isa.intent -> /m/intent" in out
    assert "crp.security.safety -> /m/safety" in out


# ── Additional branch coverage ──────────────────────────────────────────


def test_cli_without_click_friendly_error(monkeypatch) -> None:
    # Force the lazy ``import click`` inside _require_click() to fail.
    # Isolation is required: cli() wraps sys.stdout/stderr on win32, and the
    # wrapper's finalizer would otherwise close pytest's capture streams.
    monkeypatch.setitem(sys.modules, "click", None)
    with runner.isolation() as (out, err, _f):
        with pytest.raises(SystemExit) as exc_info:
            cli_main.cli()
        message = str(exc_info.value)
        out.getvalue()
        err.getvalue()
    assert "pip install crprotocol[cli]" in message


def test_serve_bind_all_unauthenticated_warning(monkeypatch) -> None:
    from crp.cli import sidecar as sidecar_mod

    class _FakeServer:
        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(sidecar_mod, "start_sidecar", lambda **kw: _FakeServer())
    code, _, err = _invoke([
        "serve", "--port", "0", "--bind-all", "--allow-unauthenticated",
    ])
    assert code == 0
    assert "WITHOUT authentication" in err


def test_scan_single_file_path(tmp_path) -> None:
    target = tmp_path / "one.py"
    target.write_text(_VIOLATING_SOURCE, encoding="utf-8")
    code, out, err = _invoke([
        "scan", "--paths", str(target), "--report-only",
    ])
    assert code == 0, err
    findings = json.loads(out)
    assert len(findings) == 1
    assert findings[0]["file"] == str(target)


def test_scan_unreadable_file_skipped(tmp_path) -> None:
    # A directory named "*.py" is picked up by the walker but fails to open;
    # the scanner must skip it (continue) rather than raise.
    trap = tmp_path / "trap.py"
    trap.mkdir()
    good = tmp_path / "ok.py"
    good.write_text(_VIOLATING_SOURCE, encoding="utf-8")
    code, out, err = _invoke([
        "scan", "--paths", str(tmp_path), "--report-only",
    ])
    assert code == 0, err
    findings = json.loads(out)
    assert {f["file"] for f in findings} == {str(good)}


_ALL_RULES_SOURCE = """\
import os
import requests
headers = {"X-AI-Policy": "strict"}
resp = requests.post("https://api.openai.com/v1/chat", headers=headers)
key = os.environ.get("OPENAI_API_KEY")
hardcoded = "sk-abcdefghij0123456789abcdefghij0123456789"
client = anthropic.Anthropic()
model = google.generativeai.GenerativeModel("gemini")
"""


def test_scan_all_rule_variants(tmp_path) -> None:
    (tmp_path / "all.py").write_text(_ALL_RULES_SOURCE, encoding="utf-8")
    code, out, err = _invoke(["scan-remediate", "--paths", str(tmp_path)])
    assert code == 0, err
    plan = json.loads(out)
    providers = [p["proposal_id"] for p in plan["proposals"]]
    assert providers  # proposals exist for every rule variant
    # Scan output covers CRP002/CRP003/CRP004/CRP006 suggestion branches.
    code, out, err = _invoke(["scan", "--paths", str(tmp_path), "--report-only"])
    assert code == 0, err
    rules = {f["rule_id"] for f in json.loads(out)}
    assert {"CRP002", "CRP003", "CRP004", "CRP006"} <= rules


def test_scan_min_version_packaging_missing(scan_dir, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "packaging", None)
    code, out, err = _run_scan(scan_dir, "--min-version", "0.0.1", "--report-only")
    assert code == 0, err
    # ImportError branch swallows the version check — no CRP005 finding.
    assert all(f["rule_id"] != "CRP005" for f in json.loads(out))


def test_scan_remediate_code_context_read_failure(scan_dir, monkeypatch) -> None:
    from pathlib import Path

    real_read_text = Path.read_text

    def _boom(self: Path, *args, **kwargs):
        if self.name == "bad.py":
            raise OSError("simulated read failure")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)
    code, out, err = _invoke(["scan-remediate", "--paths", str(scan_dir)])
    assert code == 0, err
    plan = json.loads(out)
    assert plan["proposals"]
    # code_context falls back to [] on read failure.
    assert plan["proposals"][0]["diff"] is not None


def test_scan_remediate_pr_mode_faked_git(scan_dir, monkeypatch) -> None:
    """Drive the PR-mode git flow with a fully faked ``subprocess.run``.

    The gh CLI step is faked to fail so the command stops before writing
    ``/tmp/crp_remediation_pr_url`` (a POSIX-only path that would raise on
    Windows — see the note in the report).
    """
    import subprocess

    calls: list[list[str]] = []

    class _Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "gh":
            return _Result(1, stderr="simulated gh failure")
        # Everything else (git config/checkout/apply/add/commit/push) succeeds,
        # and ``git diff --cached --quiet`` must report "changes staged".
        if "diff" in cmd and "--quiet" in cmd:
            return _Result(1)
        return _Result(0)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.chdir(scan_dir)

    code, _, err = _invoke([
        "scan-remediate", "--paths", ".",
        "--repo", "owner/repo", "--branch", "crp-remediation",
        "--gh-token", "fake-token",
    ])
    assert code == 1
    assert "gh pr create failed" in err
    git_cmds = [c for c in calls if c[0] == "git"]
    flat = " ".join(" ".join(c) for c in git_cmds)
    for expected in ("config", "checkout -b crp-remediation", "apply", "add", "commit", "push"):
        assert expected in flat, f"missing git step: {expected}"


def test_download_models_import_error(monkeypatch) -> None:
    # The try/except wraps the download call itself (huggingface_hub may be
    # missing inside the downloader), not the module import.
    import crp.ml.downloader as downloader

    def _raise_import_error(key, model_dir=None):
        raise ImportError("No module named 'huggingface_hub'")

    monkeypatch.setattr(downloader, "download_model", _raise_import_error)
    code, _, err = _invoke(["download-models", "--model", "intent"])
    assert code == 1
    assert "huggingface_hub is required" in err
