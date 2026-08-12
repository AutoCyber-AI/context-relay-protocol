# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Production hardening tests — circuit breaker, config validation,
retry logic, session cleanup, structured logging, key rotation (§audit H12).
"""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest


# ── H2: Key rotation ────────────────────────────────────────────────

class TestKeyRotation:
    def test_rotate_creates_new_key(self):
        from crp.security.binding import SessionBindingManager
        mgr = SessionBindingManager()
        binding1 = mgr.create_session("test-session")
        old_key = binding1.session_key

        binding2 = mgr.rotate_secret()
        assert binding2.session_key != old_key
        assert mgr.key_version == 1

    def test_old_signatures_valid_during_rollover(self):
        from crp.security.binding import SessionBindingManager
        mgr = SessionBindingManager()
        mgr.create_session("test-session")

        payload = b"important-data"
        old_sig = mgr.sign_request(payload)

        mgr.rotate_secret()
        # Old signature should still verify during rotation window
        assert mgr.verify_request_signature(payload, old_sig)

    def test_new_signatures_valid_after_rotation(self):
        from crp.security.binding import SessionBindingManager
        mgr = SessionBindingManager()
        mgr.create_session("test-session")
        mgr.rotate_secret()

        payload = b"new-data"
        new_sig = mgr.sign_request(payload)
        assert mgr.verify_request_signature(payload, new_sig)

    def test_rotation_window_limits_old_keys(self):
        from crp.security.binding import SessionBindingManager
        mgr = SessionBindingManager()
        mgr.create_session("test-session")
        mgr._rotation_window = 1  # only keep 1 previous key

        payload = b"data"
        sig_v0 = mgr.sign_request(payload)

        mgr.rotate_secret()  # v1
        mgr.rotate_secret()  # v2 — v0 should be evicted

        # v0 signature should no longer verify
        assert not mgr.verify_request_signature(payload, sig_v0)

    def test_rotate_without_session_raises(self):
        from crp.security.binding import SessionBindingManager
        mgr = SessionBindingManager()
        with pytest.raises(RuntimeError, match="No active session"):
            mgr.rotate_secret()


# ── H3: TelemetryWriter resource safety ──────────────────────────────

class TestTelemetryWriterLifecycle:
    def test_close_is_idempotent(self):
        from crp.observability.telemetry import TelemetryWriter
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        try:
            tw = TelemetryWriter(path)
            tw.close()
            tw.close()  # Should not raise
            assert tw._closed
        finally:
            os.unlink(path)

    def test_del_calls_close(self):
        from crp.observability.telemetry import TelemetryWriter
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        try:
            tw = TelemetryWriter(path)
            assert not tw._closed
            tw.__del__()
            assert tw._closed
        finally:
            os.unlink(path)


# ── H4: Circuit breaker ─────────────────────────────────────────────

class TestCircuitBreaker:
    def test_starts_closed(self):
        from crp.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.allow_request()

    def test_opens_after_threshold_failures(self):
        from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure()
        assert not cb.allow_request()

    def test_half_open_after_recovery_timeout(self):
        from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01))
        cb.record_failure()
        assert not cb.allow_request()

        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()

    def test_closes_after_success_threshold(self):
        from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.01,
            success_threshold=2,
        ))
        cb.record_failure()
        time.sleep(0.02)
        # Now HALF_OPEN
        _ = cb.state
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01))
        cb.record_failure()
        time.sleep(0.02)
        _ = cb.state  # transition to HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        from crp.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker()
        for _ in range(10):
            cb.record_failure()
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request()


# ── H6: Config validation ───────────────────────────────────────────

class TestConfigValidation:
    def test_defaults_pass(self):
        from crp.core.config import ConfigurationResolver
        cfg = ConfigurationResolver().resolve()
        assert cfg.enabled

    def test_rejects_negative_max_continuations(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError, match="max_continuations"):
            ConfigurationResolver().resolve(max_continuations=-1)

    def test_rejects_zero_max_threads(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError, match="max_threads"):
            ConfigurationResolver().resolve(max_threads=0)

    def test_rejects_invalid_process_priority(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError, match="process_priority"):
            ConfigurationResolver().resolve(process_priority="realtime")

    def test_rejects_invalid_default_role(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError, match="default_role"):
            ConfigurationResolver().resolve(default_role="SUPERADMIN")

    def test_accepts_valid_bounds(self):
        from crp.core.config import ConfigurationResolver
        cfg = ConfigurationResolver().resolve(
            max_continuations=100,
            max_threads=8,
            process_priority="normal",
            default_role="ADMIN",
        )
        assert cfg.max_continuations == 100

    def test_rejects_max_ram_mb_too_high(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError, match="max_ram_mb"):
            ConfigurationResolver().resolve(max_ram_mb=999_999)

    def test_multiple_errors_reported(self):
        from crp.core.config import ConfigurationResolver
        with pytest.raises(ValueError) as exc_info:
            ConfigurationResolver().resolve(
                max_continuations=-1,
                max_threads=0,
                process_priority="invalid",
            )
        msg = str(exc_info.value)
        assert "max_continuations" in msg
        assert "max_threads" in msg
        assert "process_priority" in msg


# ── H7: Continuation manager cleanup ────────────────────────────────

class TestContinuationManagerCleanup:
    def test_accumulated_facts_capped(self):
        from crp.continuation.manager import ContinuationConfig, ContinuationManager
        from crp.extraction.types import Fact

        config = ContinuationConfig(max_accumulated_facts=10)
        mgr = ContinuationManager(config=config)

        # Feed 20 facts over multiple windows
        for i in range(5):
            facts = [Fact(text=f"fact-{i}-{j}", confidence=0.5 + j * 0.01)
                     for j in range(5)]
            mgr.process_window(
                task_intent="test task",
                output=f"Window {i} output text. Some content here.",
                finish_reason="length",
                output_tokens=100,
                facts=facts,
                window_id=f"w-{i}",
            )

        # Should be capped at max_accumulated_facts
        assert len(mgr._accumulated_facts) <= 10


# ── H9: Structured logging ──────────────────────────────────────────

class TestStructuredLogging:
    def test_correlation_id_lifecycle(self):
        from crp.observability.structured_logging import (
            get_correlation_id,
            new_correlation_id,
        )
        cid = new_correlation_id()
        assert len(cid) == 12
        assert get_correlation_id() == cid

    def test_structured_formatter_output(self):
        import logging
        from crp.observability.structured_logging import StructuredFormatter

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="crp.test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "crp.test"


# ── H11: Session file cleanup ───────────────────────────────────────

class TestSessionCleanup:
    def test_removes_expired_files(self, tmp_path):
        from crp.state.session_cleanup import cleanup_expired_sessions

        # Create an "old" session file
        old_path = os.path.join(str(tmp_path), "old-session.json")
        with open(old_path, "w") as f:
            f.write("{}")
        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(old_path, (old_time, old_time))

        # Create a "new" session file
        new_path = os.path.join(str(tmp_path), "new-session.json")
        with open(new_path, "w") as f:
            f.write("{}")

        removed = cleanup_expired_sessions(str(tmp_path), ttl_seconds=7 * 24 * 3600)
        assert len(removed) == 1
        assert not os.path.exists(old_path)
        assert os.path.exists(new_path)

    def test_dry_run_does_not_delete(self, tmp_path):
        from crp.state.session_cleanup import cleanup_expired_sessions

        old_path = os.path.join(str(tmp_path), "session.json")
        with open(old_path, "w") as f:
            f.write("{}")
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(old_path, (old_time, old_time))

        removed = cleanup_expired_sessions(str(tmp_path), ttl_seconds=1, dry_run=True)
        assert len(removed) == 1
        assert os.path.exists(old_path)  # Not deleted

    def test_ignores_non_session_files(self, tmp_path):
        from crp.state.session_cleanup import cleanup_expired_sessions

        txt_path = os.path.join(str(tmp_path), "notes.txt")
        with open(txt_path, "w") as f:
            f.write("keep me")
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(txt_path, (old_time, old_time))

        removed = cleanup_expired_sessions(str(tmp_path), ttl_seconds=1)
        assert len(removed) == 0
        assert os.path.exists(txt_path)


# ═══════════════════════════════════════════════════════════════════
#  LOW-severity fix tests (§audit L1–L10)
# ═══════════════════════════════════════════════════════════════════


# ── L1 + L2: Convenience imports & error exports ────────────────────

class TestConvenienceImports:
    def test_error_types_importable(self):
        from crp import (
            BudgetExhaustedError,
            ErrorCode,
            ProviderError,
            ProviderTimeoutError,
            RateLimitExceededError,
            SecurityInvariantError,
            SessionClosedError,
            SessionExpiredError,
            SignatureInvalidError,
            StateCorruptedError,
            ValidationError,
        )
        assert issubclass(ProviderError, Exception)
        assert issubclass(BudgetExhaustedError, Exception)
        assert hasattr(ErrorCode, "PROVIDER_ERROR")

    def test_config_classes_importable(self):
        from crp import ConfigurationResolver, CRPConfig
        assert callable(ConfigurationResolver.resolve)
        assert CRPConfig is not None


# ── L3: Unknown kwargs warning ──────────────────────────────────────

class TestKwargsValidation:
    def test_unknown_kwargs_logged(self, caplog):
        import logging
        from crp.core.config import ConfigurationResolver

        resolver = ConfigurationResolver()
        with caplog.at_level(logging.WARNING, logger="crp.core.config"):
            cfg = resolver.resolve(bogus_key="value", another_bad=42)
        assert any("Unknown config" in r.message for r in caplog.records)


# ── L4: FactGraph edge indexing ─────────────────────────────────────

class TestFactGraphEdgeIndex:
    def test_edges_from_indexed(self):
        from crp.extraction.types import Fact, FactEdge, FactGraph

        g = FactGraph()
        g.add_fact(Fact(id="a", text="alpha"))
        g.add_fact(Fact(id="b", text="beta"))
        g.add_fact(Fact(id="c", text="gamma"))
        g.add_edge(FactEdge(source_id="a", target_id="b"))
        g.add_edge(FactEdge(source_id="a", target_id="c"))
        g.add_edge(FactEdge(source_id="b", target_id="c"))

        from_a = g.edges_from("a")
        assert len(from_a) == 2
        assert all(e.source_id == "a" for e in from_a)

        to_c = g.edges_to("c")
        assert len(to_c) == 2
        assert all(e.target_id == "c" for e in to_c)

    def test_empty_lookup_returns_empty(self):
        from crp.extraction.types import Fact, FactGraph

        g = FactGraph()
        g.add_fact(Fact(id="x", text="solo"))
        assert g.edges_from("x") == []
        assert g.edges_to("x") == []
        assert g.edges_from("nonexistent") == []

    def test_index_consistent_with_edge_list(self):
        from crp.extraction.types import Fact, FactEdge, FactGraph

        g = FactGraph()
        for fid in ["a", "b", "c", "d"]:
            g.add_fact(Fact(id=fid, text=fid))
        g.add_edge(FactEdge(source_id="a", target_id="b"))
        g.add_edge(FactEdge(source_id="b", target_id="c"))
        g.add_edge(FactEdge(source_id="c", target_id="d"))
        g.add_edge(FactEdge(source_id="a", target_id="d"))

        # Indices should match brute-force scan
        for fid in ["a", "b", "c", "d"]:
            brute_from = [e for e in g.edges if e.source_id == fid]
            brute_to = [e for e in g.edges if e.target_id == fid]
            assert len(g.edges_from(fid)) == len(brute_from)
            assert len(g.edges_to(fid)) == len(brute_to)


# ── L5: TypeAlias annotations ──────────────────────────────────────

class TestTypeAliases:
    def test_typing_module_has_aliases(self):
        from crp._typing import (
            EmbeddingFn,
            EmbeddingVector,
            FactID,
            JSON,
            SessionID,
            TokenCount,
            WindowID,
        )
        assert JSON is not None
        assert FactID is str
        assert WindowID is str
        assert SessionID is str
        assert TokenCount is int


# ── L6 + L7: Session file versioning & migration ───────────────────

class TestSessionVersioning:
    def test_to_dict_includes_schema_version(self):
        from crp.state.warm_store import SCHEMA_VERSION, WarmStateStore

        store = WarmStateStore()
        d = store.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION

    def test_load_v1_data_migrated(self):
        from crp.extraction.types import Fact
        from crp.state.warm_store import SCHEMA_VERSION, WarmStateStore

        store = WarmStateStore()
        # Simulate v1 data (no schema_version)
        v1_data = {
            "facts": {},
            "edges": [{"id": "e1", "source_id": "a", "target_id": "b",
                        "relation_type": "RELATED", "confidence": 0.5}],
            "critical_state": {},
            "structural_state": {},
            "window_count": 1,
            "current_window_id": "w0",
        }
        store.load_from_dict(v1_data)
        # Should succeed without error (migration fills source_stage)

    def test_future_version_rejected(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        future_data = {"schema_version": 999}
        with pytest.raises(ValueError, match="newer than supported"):
            store.load_from_dict(future_data)

    def test_roundtrip_preserves_version(self):
        from crp.extraction.types import Fact
        from crp.state.warm_store import SCHEMA_VERSION, WarmStateStore

        store1 = WarmStateStore()
        store1.add_facts([Fact(id="f1", text="test", confidence=0.8)])
        d = store1.to_dict()
        assert d["schema_version"] == SCHEMA_VERSION

        store2 = WarmStateStore()
        store2.load_from_dict(d)
        d2 = store2.to_dict()
        assert d2["schema_version"] == SCHEMA_VERSION


# ── L10: Changelog script exists ────────────────────────────────────

class TestChangelogAutomation:
    def test_script_exists_and_importable(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gen_changelog",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "scripts",
                "gen_changelog.py",
            ),
        )
        assert spec is not None

    def test_categorize_function(self):
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_changelog",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "scripts",
                "gen_changelog.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        groups = mod.categorize([
            "feat: add new endpoint",
            "fix: resolve crash on startup",
            "refactor: simplify config",
            "random commit message",
        ])
        assert "Added" in groups
        assert "Fixed" in groups
        assert "Changed" in groups
        assert "Other" in groups
