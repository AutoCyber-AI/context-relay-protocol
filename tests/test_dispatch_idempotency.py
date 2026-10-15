# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Regression tests for U-C6 — dispatch idempotency is wired into the
dispatch path (§23: same key within TTL returns cached result, no
re-dispatch), plus the RequestDeduplicator/SessionLock race fixes.

Before this batch, ``RequestDeduplicator`` had zero call sites outside
tests, so a retried dispatch always double-dispatched (double cost,
double facts) despite the advertised guarantee.
"""

from __future__ import annotations

import threading
import time

import pytest

from crp.core.idempotency import RequestDeduplicator, SessionLock
from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider


class CountingProvider(LLMProvider):
    """Provider that counts generate_chat calls and can sleep."""

    def __init__(self, delay_s: float = 0.0):
        self.calls = 0
        self.lock = threading.Lock()
        self.delay_s = delay_s

    def generate_chat(self, messages, max_tokens=None, **kwargs):
        with self.lock:
            self.calls += 1
        if self.delay_s:
            time.sleep(self.delay_s)
        return ("counted output", "stop")

    def count_tokens(self, text):
        return max(1, len(text) // 4)

    def context_window_size(self):
        return 128000


def _orch(provider, **config_overrides) -> CRPOrchestrator:
    # The orchestrator's config is crp.core.config.CRPConfig — pass kwargs
    # straight through the constructor (ConfigurationResolver).
    return CRPOrchestrator(provider=provider, **config_overrides)


# ---------------------------------------------------------------------------
# Wired into dispatch()
# ---------------------------------------------------------------------------


class TestDispatchIdempotencyWired:
    def test_retry_within_ttl_single_provider_call(self) -> None:
        """Identical dispatch retried within TTL → the retry adds zero new
        provider calls (the first dispatch may make internal side-calls,
        e.g. the L3 extractor — the §23 guarantee is about the retried call)."""
        provider = CountingProvider()
        orch = _orch(provider)
        try:
            out1, _ = orch.dispatch("sys", "task")
            calls_after_first = provider.calls
            assert calls_after_first >= 1
            out2, _ = orch.dispatch("sys", "task")
            assert out1 == out2
            assert provider.calls == calls_after_first, (
                f"retry double-dispatched: {provider.calls - calls_after_first} "
                "extra provider calls"
            )
        finally:
            orch.close()

    def test_different_inputs_dispatch_separately(self) -> None:
        provider = CountingProvider()
        orch = _orch(provider)
        try:
            orch.dispatch("sys", "task-a")
            calls_after_first = provider.calls
            orch.dispatch("sys", "task-b")
            assert provider.calls > calls_after_first
        finally:
            orch.close()

    def test_different_kwargs_dispatch_separately(self) -> None:
        provider = CountingProvider()
        orch = _orch(provider)
        try:
            orch.dispatch("sys", "task", max_continuations=1)
            calls_after_first = provider.calls
            orch.dispatch("sys", "task", max_continuations=2)
            assert provider.calls > calls_after_first
        finally:
            orch.close()

    def test_ttl_expiry_redispatches(self) -> None:
        provider = CountingProvider()
        orch = _orch(provider, **{"dispatch_idempotency_ttl_s": 0.05})
        try:
            orch.dispatch("sys", "task")
            calls_after_first = provider.calls
            time.sleep(0.1)  # let the TTL lapse
            orch.dispatch("sys", "task")
            assert provider.calls > calls_after_first, (
                "expired TTL must re-dispatch"
            )
        finally:
            orch.close()

    def test_opt_out_via_config(self) -> None:
        """dispatch_idempotency=False restores legacy double-dispatch."""
        provider = CountingProvider()
        orch = _orch(provider, **{"dispatch_idempotency": False})
        try:
            orch.dispatch("sys", "task")
            calls_after_first = provider.calls
            orch.dispatch("sys", "task")
            assert provider.calls > calls_after_first, (
                "opt-out must restore legacy double-dispatch"
            )
        finally:
            orch.close()

    def test_concurrent_identical_dispatches_single_flight(self) -> None:
        """8 threads fire the same dispatch concurrently → exactly one
        provider call; followers serve the cached result."""
        provider = CountingProvider(delay_s=0.15)
        orch = _orch(
            provider,
            **{"dispatch_idempotency_inflight_wait_s": 180.0},
        )
        # Calibrate how many provider calls one dispatch makes (main window
        # + internal side-calls) so the single-flight assertion is exact.
        orch.dispatch("sys", "warmup-task")
        calls_per_dispatch = provider.calls
        assert calls_per_dispatch >= 1
        results: list = []
        errors: list = []

        def fire():
            try:
                results.append(orch.dispatch("sys", "shared-task"))
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=fire) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        try:
            assert not errors, f"dispatch errors: {errors!r}"
            assert len(results) == 8
            # Warmup (1 dispatch) + 8 concurrent identical requests coalesced
            # into exactly one more dispatch.
            assert provider.calls == 2 * calls_per_dispatch, (
                f"single-flight broken: {provider.calls} provider calls for "
                "warmup + 8 concurrent identical dispatches"
            )
            outputs = {out for out, _ in results}
            assert outputs == {"counted output"}
        finally:
            orch.close()

    def test_cache_hit_returns_same_report_object(self) -> None:
        provider = CountingProvider()
        orch = _orch(provider)
        try:
            _, report1 = orch.dispatch("sys", "task")
            _, report2 = orch.dispatch("sys", "task")
            assert report1 is report2
        finally:
            orch.close()


# ---------------------------------------------------------------------------
# RequestDeduplicator race fixes
# ---------------------------------------------------------------------------


class TestDeduplicatorRaces:
    def test_check_store_8_threads_no_exception(self) -> None:
        """Fuzz check/store from 8 threads — must never raise
        'dictionary changed size during iteration' (the U-C6 latent race)."""
        dedup = RequestDeduplicator(ttl=0.05, max_cache_size=64)
        stop = time.time() + 3.0
        errors: list = []

        def worker(wid: int):
            i = 0
            while time.time() < stop and not errors:
                try:
                    key = f"w{wid}-k{i % 40}"
                    dedup.check(key)
                    dedup.store(key, f"out-{i}")
                    i += 1
                except Exception as exc:  # pragma: no cover - diagnostic
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"race raised: {errors!r}"

    def test_single_flight_claim_and_release(self) -> None:
        dedup = RequestDeduplicator()
        owner, ev = dedup.acquire_inflight("k")
        assert owner
        # Second claim while in flight → follower with the SAME event.
        owner2, ev2 = dedup.acquire_inflight("k")
        assert not owner2
        assert ev2 is ev
        # Release wakes followers and allows a new owner.
        dedup.release_inflight("k", ev)
        assert ev2.is_set()
        owner3, ev3 = dedup.acquire_inflight("k")
        assert owner3
        dedup.release_inflight("k", ev3)

    def test_concurrent_store_same_key_last_write_wins_no_raise(self) -> None:
        dedup = RequestDeduplicator()
        errors: list = []

        def store(wid: int):
            try:
                for i in range(500):
                    dedup.store("same-key", f"out-{wid}-{i}")
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=store, args=(w,)) for w in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        hit = dedup.check("same-key")
        assert hit is not None


# ---------------------------------------------------------------------------
# SessionLock — real read lock
# ---------------------------------------------------------------------------


class TestSessionLock:
    def test_concurrent_reads_proceed(self) -> None:
        lock = SessionLock()
        assert lock.acquire_read()
        assert lock.acquire_read()  # second reader not blocked
        lock.release_read()
        lock.release_read()

    def test_writer_waits_for_reader(self) -> None:
        lock = SessionLock(timeout=5.0)
        assert lock.acquire_read()
        acquired: list = []

        def write():
            acquired.append(lock.acquire_write())

        t = threading.Thread(target=write)
        t.start()
        time.sleep(0.1)
        assert acquired == []  # writer must wait while a reader holds
        lock.release_read()
        t.join(timeout=5)
        assert acquired == [True]
        lock.release_write()

    def test_reader_waits_for_writer(self) -> None:
        lock = SessionLock(timeout=5.0)
        assert lock.acquire_write()
        acquired: list = []

        def read():
            acquired.append(lock.acquire_read())

        t = threading.Thread(target=read)
        t.start()
        time.sleep(0.1)
        assert acquired == []  # read lock is no longer a no-op
        lock.release_write()
        t.join(timeout=5)
        assert acquired == [True]
        lock.release_read()

    def test_write_timeout_returns_false(self) -> None:
        lock = SessionLock(timeout=0.2)
        assert lock.acquire_write()
        try:
            assert not lock.acquire_write()  # would block → False on timeout
        finally:
            lock.release_write()
