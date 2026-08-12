# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 8 tests — CLI, deployment, startup sequence, event emitter."""

from __future__ import annotations

import json

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# 8B.1 — Embedded library: ``import crp``
# ═══════════════════════════════════════════════════════════════════════════


class TestEmbeddedLibrary:
    """Verify that ``import crp`` exposes the public API (§9.1)."""

    def test_version_available(self):
        import crp

        assert isinstance(crp.__version__, str)
        assert crp.__version__

    def test_client_alias(self):
        import crp

        assert crp.Client is crp.CRPOrchestrator

    def test_core_types_importable(self):
        from crp import (
            Client,
            CostEstimate,
            CRPError,
            CRPOrchestrator,
            EnvelopePreview,
            ExtractionResult,
            QualityReport,
            SessionHandle,
            SessionStatus,
            StreamEvent,
            TaskIntent,
        )

        assert Client is CRPOrchestrator

    def test_core_subpackage_exports(self):
        from crp.core import (
            BatchResult,
            BudgetExhaustedError,
            ConfigurationResolver,
            CRPConfig,
            CRPOrchestrator,
            ExtractionResult,
            ProviderError,
            RequestDeduplicator,
            SessionClosedError,
            SessionExpiredError,
            SessionHandle,
            SessionLock,
            StreamEvent,
            TaskIntent,
            WindowDAG,
            WindowMetrics,
            WindowNode,
            WindowState,
        )

        assert CRPOrchestrator is not None

    def test_advanced_subpackage_exports(self):
        from crp.advanced import (
            CQSDetector,
            CrossWindowValidator,
            FeedbackLoop,
            HierarchicalProcessor,
            LLMContextCurator,
            MetaLearningEngine,
            ParallelFanOut,
            ReviewCycleManager,
            ScaleModeSelector,
            SourceGroundingEngine,
            auto_ingest,
        )

        assert auto_ingest is not None

    def test_resources_subpackage_exports(self):
        from crp.resources import (
            KNOWN_PRICING,
            BudgetWarning,
            BudgetWarningLevel,
            CostModel,
            OverheadBudget,
            OverheadDecision,
            ProviderPricing,
            WindowCost,
        )

        assert len(KNOWN_PRICING) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 8C — Startup sequence (6 steps)
# ═══════════════════════════════════════════════════════════════════════════

from crp.cli.startup import StartupResult, StartupStep, run_startup


class TestStartupSequence:
    """Verify the 6-step startup (§9.5)."""

    def test_full_startup_no_provider(self):
        result, ctx = run_startup(skip_auth=True, skip_health=True)
        assert result.ok
        assert len(result.steps) == 6
        assert result.total_ms >= 0

    def test_step_names(self):
        result, _ = run_startup(skip_auth=True, skip_health=True)
        names = [s.name for s in result.steps]
        assert names == [
            "resolve_config",
            "validate_config",
            "authenticate",
            "connect_llm",
            "init_session_state",
            "start_event_emitter",
        ]

    def test_config_resolved(self):
        _, ctx = run_startup(skip_auth=True, skip_health=True)
        assert "config" in ctx

    def test_warm_store_initialized(self):
        _, ctx = run_startup(skip_auth=True, skip_health=True)
        assert "warm_store" in ctx

    def test_event_log_initialized(self):
        _, ctx = run_startup(skip_auth=True, skip_health=True)
        assert "event_log" in ctx
        from crp.state.event_log import FactEventLog
        assert isinstance(ctx["event_log"], FactEventLog)

    def test_emitter_started(self):
        _, ctx = run_startup(skip_auth=True, skip_health=True)
        emitter = ctx.get("emitter")
        assert emitter is not None
        assert emitter.is_running

    def test_config_overrides(self):
        _, ctx = run_startup(
            config_overrides={"session_timeout": 3600},
            skip_auth=True,
            skip_health=True,
        )
        assert ctx["config"].session_timeout == 3600

    def test_startup_with_provider(self):
        from crp.providers.custom import CustomProvider

        prov = CustomProvider(
            generate_fn=lambda msgs, **kw: ("hello", "stop"),
            count_tokens_fn=lambda t: max(1, len(t) // 4),
            context_size=8192,
        )
        result, ctx = run_startup(
            provider=prov, skip_auth=True, skip_health=True,
        )
        assert result.ok
        assert ctx["provider"] is prov

    def test_startup_with_auth(self):
        result, ctx = run_startup(
            binding_secret=b"test-secret",
            skip_health=True,
        )
        assert result.ok
        assert "binding" in ctx

    def test_startup_result_summary(self):
        result, _ = run_startup(skip_auth=True, skip_health=True)
        summary = result.summary
        assert summary["ok"] is True
        assert "total_ms" in summary
        assert len(summary["steps"]) == 6

    def test_startup_step_dataclass(self):
        step = StartupStep(step=1, name="test", ok=True, latency_ms=1.5)
        assert step.step == 1
        assert step.name == "test"
        assert step.ok
        assert step.latency_ms == 1.5

    def test_schema_validation_rejects_bad_timeout(self):
        result, _ = run_startup(
            config_overrides={"session_timeout": -1},
            skip_auth=True,
            skip_health=True,
        )
        # Validation now fires during config resolution (step 1)
        validate_step = result.steps[0]
        assert not validate_step.ok
        assert "session_timeout" in validate_step.detail

    def test_schema_validation_rejects_bad_continuations(self):
        result, _ = run_startup(
            config_overrides={"max_continuations": -5},
            skip_auth=True,
            skip_health=True,
        )
        # Validation now fires during config resolution (step 1)
        validate_step = result.steps[0]
        assert not validate_step.ok
        assert "max_continuations" in validate_step.detail


# ═══════════════════════════════════════════════════════════════════════════
# 8C.6 — Event emitter
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.events import CRPEvent, EventEmitter


class TestEventEmitter:
    """Verify the event bus (§9.5 step 6)."""

    def test_start_stop(self):
        em = EventEmitter()
        assert not em.is_running
        em.start()
        assert em.is_running
        em.stop()
        assert not em.is_running

    def test_emit_and_receive(self):
        em = EventEmitter()
        em.start()
        received = []
        em.on("test.event", lambda e: received.append(e))
        em.emit("test.event", {"key": "value"})
        assert len(received) == 1
        assert received[0].event_type == "test.event"
        assert received[0].data == {"key": "value"}

    def test_events_dropped_when_stopped(self):
        em = EventEmitter()
        received = []
        em.on("x", lambda e: received.append(e))
        em.emit("x")
        assert len(received) == 0  # not started

    def test_global_listener(self):
        em = EventEmitter()
        em.start()
        received = []
        em.on_all(lambda e: received.append(e))
        em.emit("a")
        em.emit("b")
        assert len(received) == 2

    def test_off_removes_listener(self):
        em = EventEmitter()
        em.start()
        received = []
        fn = lambda e: received.append(e)
        em.on("x", fn)
        assert em.off("x", fn)
        em.emit("x")
        assert len(received) == 0

    def test_off_returns_false_for_unknown(self):
        em = EventEmitter()
        assert not em.off("x", lambda e: None)

    def test_listener_count(self):
        em = EventEmitter()
        em.on("a", lambda e: None)
        em.on("a", lambda e: None)
        em.on_all(lambda e: None)
        assert em.listener_count == 3

    def test_crp_event_to_dict(self):
        e = CRPEvent(event_type="test", data={"k": 1})
        d = e.to_dict()
        assert d["event_type"] == "test"
        assert d["data"] == {"k": 1}
        assert "timestamp" in d

    def test_listener_exception_does_not_propagate(self):
        em = EventEmitter()
        em.start()
        received = []

        def bad(e):
            raise RuntimeError("boom")

        em.on("x", bad)
        em.on("x", lambda e: received.append(e))
        em.emit("x")  # should not raise
        assert len(received) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 8A — CLI commands (unit-level: test Click invocations)
# ═══════════════════════════════════════════════════════════════════════════


class TestCLICommands:
    """Test CLI commands via programmatic invocation (no subprocess)."""

    @pytest.fixture(autouse=True)
    def _reset_sessions(self):
        """Clear CLI session store between tests."""
        from crp.cli import main as cli_mod

        cli_mod._sessions.clear()
        yield
        cli_mod._sessions.clear()

    def _invoke_cli(self, args: list[str]):
        """Invoke the CLI group programmatically via click's test runner."""
        click = pytest.importorskip("click")
        from click.testing import CliRunner

        # We need to build the click group to invoke it
        # The cli() function builds and runs the group in standalone mode.
        # We replicate the group construction for testing:
        from crp.cli import main as cli_mod

        # Remove stale stream handlers left by prior CliRunner invocations
        # (e.g. after dispatch loads GLiNER and attaches structured loggers).
        import logging as _logging
        for _name in (None, "crp", "crp.startup"):
            _lg = _logging.getLogger(_name)
            for _h in _lg.handlers[:]:
                if isinstance(_h, _logging.StreamHandler):
                    _lg.removeHandler(_h)

        runner = CliRunner()

        # Build the click group inline (same as cli() but without standalone_mode)
        @click.group(context_settings={"help_option_names": ["-h", "--help"]})
        @click.version_option(package_name="crp")
        def _cli():
            pass

        @_cli.command()
        @click.option("--model", default="custom")
        @click.option("--context-window", default=128_000, type=int)
        @click.option("--max-output", default=4096, type=int)
        @click.option("--timeout", default=86400, type=int)
        @click.option("--json", "as_json", is_flag=True)
        def init(model, context_window, max_output, timeout, as_json):
            import uuid

            from crp.cli.startup import run_startup
            from crp.providers.custom import CustomProvider

            provider = CustomProvider(
                generate_fn=lambda msgs, **kw: ("", "stop"),
                count_tokens_fn=lambda t: max(1, len(t) // 4),
                context_size=context_window,
                name=model,
                max_output=max_output,
            )
            result, ctx = run_startup(
                provider=provider,
                config_overrides={"session_timeout": timeout},
                skip_health=True,
            )
            session_id = str(uuid.uuid4())
            cli_mod._sessions[session_id] = {
                "id": session_id,
                "provider": provider,
                "config": ctx.get("config"),
                "emitter": ctx.get("emitter"),
                "orchestrator": None,
            }
            if as_json:
                click.echo(json.dumps({
                    "session_id": session_id,
                    "model": model,
                    "context_window": context_window,
                    "startup_ok": result.ok,
                }))
            else:
                click.echo(session_id)

        @_cli.command()
        @click.option("--session", "session_id", default=None)
        @click.option("--task", required=True)
        @click.option("--system", default="You are a helpful assistant.")
        @click.option("--json", "as_json", is_flag=True)
        def dispatch(session_id, task, system, as_json):
            if session_id is None:
                import uuid as _uuid

                from crp.cli.startup import run_startup
                from crp.providers.custom import CustomProvider

                _prov = CustomProvider(
                    generate_fn=lambda msgs, **kw: ("", "stop"),
                    count_tokens_fn=lambda t: max(1, len(t) // 4),
                    context_size=128_000,
                )
                _res, _ctx = run_startup(provider=_prov, skip_health=True)
                session_id = str(_uuid.uuid4())
                cli_mod._sessions[session_id] = {
                    "id": session_id,
                    "provider": _prov,
                    "config": _ctx.get("config"),
                    "emitter": _ctx.get("emitter"),
                    "orchestrator": None,
                }
            sess = cli_mod._get_session(session_id)
            orch = cli_mod._ensure_orchestrator(sess)
            output, report = orch.dispatch(system, task)
            if as_json:
                click.echo(json.dumps({"output": output}))
            else:
                click.echo(output)

        @_cli.command()
        @click.option("--session", "session_id", required=True)
        def status(session_id):
            sess = cli_mod._get_session(session_id)
            orch = cli_mod._ensure_orchestrator(sess)
            st = orch.session_status()
            click.echo(json.dumps({
                "session_id": st.session_id,
                "windows_completed": st.windows_completed,
            }))

        @_cli.command()
        @click.option("--session", "session_id", required=True)
        @click.option("--task", required=True)
        @click.option("--system", default="You are a helpful assistant.")
        def preview(session_id, task, system):
            sess = cli_mod._get_session(session_id)
            orch = cli_mod._ensure_orchestrator(sess)
            ep = orch.preview_envelope(system, task)
            click.echo(json.dumps({"total_tokens": ep.total_tokens}))

        @_cli.command()
        @click.option("--port", default=9470, type=int)
        @click.option("--bind-all", is_flag=True, default=False)
        def serve(port, bind_all):
            host = "0.0.0.0" if bind_all else "127.0.0.1"
            click.echo(f"CRP sidecar starting on {host}:{port}")

        try:
            result = runner.invoke(_cli, args, catch_exceptions=False)
        finally:
            # Clean any handlers added during invocation to avoid
            # contaminating subsequent CliRunner stdout capture.
            for _name in (None, "crp", "crp.startup"):
                _lg = _logging.getLogger(_name)
                for _h in _lg.handlers[:]:
                    if isinstance(_h, _logging.StreamHandler):
                        _lg.removeHandler(_h)
        return result

    @staticmethod
    def _parse_cli_json(output: str) -> dict:
        """Parse the command's JSON from CLI output, ignoring structured log lines.

        CRP's structured logger may prepend JSON log lines to stdout before
        the command's click.echo() output.  The actual command JSON is the
        last valid JSON line that does NOT contain a ``"logger"`` key.
        """
        for line in reversed(output.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "logger" not in data:
                    return data
            except json.JSONDecodeError:
                continue
        # Fallback: first line
        return json.loads(output.strip().splitlines()[0])

    # ── 8A.1: crp init ──────────────────────────────────────────────

    def test_init_prints_session_id(self):
        result = self._invoke_cli(["init"])
        assert result.exit_code == 0
        session_id = result.output.strip()
        assert len(session_id) == 36  # UUID

    def test_init_json_output(self):
        result = self._invoke_cli(["init", "--json"])
        assert result.exit_code == 0
        data = self._parse_cli_json(result.output)
        assert "session_id" in data
        assert data["startup_ok"] is True

    # ── 8A.2: crp dispatch ──────────────────────────────────────────

    def test_dispatch_with_session(self):
        # First init
        init_result = self._invoke_cli(["init", "--json"])
        data = self._parse_cli_json(init_result.output)
        sid = data["session_id"]

        result = self._invoke_cli([
            "dispatch", "--session", sid, "--task", "Hello CRP",
        ])
        assert result.exit_code == 0

    def test_dispatch_auto_init_without_session(self):
        """``crp dispatch --task "Hello"`` works without --session (auto-init)."""
        result = self._invoke_cli(["dispatch", "--task", "Hello CRP"])
        assert result.exit_code == 0

    # ── 8A.4: crp status ────────────────────────────────────────────

    def test_status_json(self):
        init_result = self._invoke_cli(["init", "--json"])
        sid = self._parse_cli_json(init_result.output)["session_id"]

        result = self._invoke_cli(["status", "--session", sid])
        assert result.exit_code == 0
        data = self._parse_cli_json(result.output)
        assert "session_id" in data
        assert "windows_completed" in data

    # ── 8A.5: crp preview ───────────────────────────────────────────

    def test_preview_json(self):
        init_result = self._invoke_cli(["init", "--json"])
        sid = self._parse_cli_json(init_result.output)["session_id"]

        result = self._invoke_cli([
            "preview", "--session", sid, "--task", "Test task",
        ])
        assert result.exit_code == 0
        data = self._parse_cli_json(result.output)
        assert "total_tokens" in data

    # ── 8B.3/8B.4: crp serve ────────────────────────────────────────

    def test_serve_default_localhost(self):
        result = self._invoke_cli(["serve"])
        assert result.exit_code == 0
        assert "127.0.0.1:9470" in result.output

    def test_serve_bind_all_requires_flag(self):
        result = self._invoke_cli(["serve", "--bind-all"])
        assert result.exit_code == 0
        assert "0.0.0.0:9470" in result.output

    def test_serve_custom_port(self):
        result = self._invoke_cli(["serve", "--port", "8080"])
        assert result.exit_code == 0
        assert "127.0.0.1:8080" in result.output

    # ── 8A.6: UNIX-friendly ─────────────────────────────────────────

    def test_json_output_is_valid_json(self):
        result = self._invoke_cli(["init", "--json"])
        assert result.exit_code == 0
        # Must be valid JSON (first line; ignore trailing log noise)
        data = self._parse_cli_json(result.output)
        assert isinstance(data, dict)
