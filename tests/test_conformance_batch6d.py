# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Batch 6D conformance tests — properties the audit (wasa_crp_production_audit,
Ch. 6) required but the suite did not cover:

  * idempotency key canonicalisation (U-L8) — mixed-type / nested-dict kwargs
    produce a stable, insertion-order-independent key;
  * audit ledger integrity incl. restart artefacts (U-C9 / A-PR-5 / U-L5) —
    ``ComplianceAuditTrail.verify_file`` detects a one-byte edit or a
    truncated tail, the external anchor round-trips, and a mixed-version
    (2.0.0 + 2.1.0 transcript) receipted chain verifies;
  * envelope determinism (U-C11) — dependency bonuses are input-order
    independent and ``rerank`` neither mutates callers' ScoredFacts nor
    changes its own answer on a second pass;
  * per-call continuation caps (U-C8 / A-PR-1) — the ``max_continuations``
    dispatch kwarg overrides the session config bound, and unknown dispatch
    kwargs warn (or raise under CRP_DISPATCH_STRICT_KWARGS=1);
  * sliding session expiry (U-C10) — ``SessionHandle.touch`` and the
    orchestrator's session check slide ``expires_at`` forward;
  * low-novelty continuation stop (A-PR-7) — repetitive stop-continuations
    terminate with ``low_novelty_stop`` instead of burning the window cap;
  * per-phase policy narrowing (A-PR-2) — multi-phase positioned runs narrow
    from the pristine caller policy, so late phases keep a non-empty
    allowlist for disjoint phase tool sets.

All tests are offline: providers are stubs, no live LLM is required.
"""

from __future__ import annotations

import math
import time
import warnings
from pathlib import Path
from typing import Any

import pytest

from crp.core.idempotency import RequestDeduplicator
from crp.core.orchestrator import CRPOrchestrator
from crp.core.session import SessionHandle
from crp.core.task_intent import TaskIntent
from crp.extraction.types import Fact, FactEdge, FactGraph, RelationType
from crp.providers.base import LLMProvider


# ---------------------------------------------------------------------------
# U-L8 — idempotency key canonicalisation
# ---------------------------------------------------------------------------


class TestIdempotencyKeyCanonicalisation:
    def test_mixed_type_kwargs_do_not_crash(self) -> None:
        dedup = RequestDeduplicator(ttl=300.0)
        key = dedup.compute_key(
            "sys",
            "task",
            limit=10,
            tags=["a", "b"],
            nested={"b": 2, "a": 1},
            flag=True,
            ratio=0.5,
        )
        assert isinstance(key, str) and len(key) == 32
        # Stable across repeated computation.
        assert key == dedup.compute_key(
            "sys", "task", limit=10, tags=["a", "b"],
            nested={"b": 2, "a": 1}, flag=True, ratio=0.5,
        )

    def test_nested_dict_insertion_order_independent(self) -> None:
        dedup = RequestDeduplicator(ttl=300.0)
        k1 = dedup.compute_key("s", "t", payload={"a": 1, "b": {"x": 1, "y": 2}})
        k2 = dedup.compute_key("s", "t", payload={"b": {"y": 2, "x": 1}, "a": 1})
        assert k1 == k2

    def test_type_tagging_separates_int_str_float(self) -> None:
        dedup = RequestDeduplicator(ttl=300.0)
        k_int = dedup.compute_key("s", "t", a=1)
        k_str = dedup.compute_key("s", "t", a="1")
        k_float = dedup.compute_key("s", "t", a=1.0)
        assert len({k_int, k_str, k_float}) == 3

    def test_tuple_and_list_equivalent(self) -> None:
        # JSON has no tuples: sequences canonicalise to lists.
        dedup = RequestDeduplicator(ttl=300.0)
        assert dedup.compute_key("s", "t", v=(1, 2)) == dedup.compute_key("s", "t", v=[1, 2])


# ---------------------------------------------------------------------------
# U-C9 / A-PR-5 / U-L5 — audit ledger integrity (incl. restart artefacts)
# ---------------------------------------------------------------------------


def _signed_trail() -> Any:
    pytest.importorskip("cryptography", reason="receipt tests need [security] extra")
    from crp.security.audit_trail import ActionSigner, ComplianceAuditTrail

    return ComplianceAuditTrail(session_id="s-conformance", action_signer=ActionSigner())


class TestAuditLedgerIntegrity:
    def test_verify_file_valid_export(self, tmp_path: Path) -> None:
        from crp.security.audit_trail import ComplianceAuditTrail

        trail = ComplianceAuditTrail(session_id="s1")
        for i in range(5):
            trail.record("compliance.data_processed", data={"i": i})
        path = tmp_path / "s1.audit.jsonl"
        path.write_text(trail.export_jsonl(), encoding="utf-8")
        ok, broken = ComplianceAuditTrail.verify_file(str(path))
        assert ok is True
        assert broken == -1

    def test_verify_file_detects_one_byte_edit(self, tmp_path: Path) -> None:
        from crp.security.audit_trail import ComplianceAuditTrail

        trail = ComplianceAuditTrail(session_id="s1")
        for i in range(5):
            trail.record("compliance.data_processed", data={"note": f"value-{i}"})
        path = tmp_path / "s1.audit.jsonl"
        text = trail.export_jsonl()
        path.write_text(text, encoding="utf-8")
        # Flip one character inside a data field WITHOUT recomputing anything:
        # a real editor-forger would have to rebuild the whole chain, which
        # is exactly what the keyless pre-6.2.2 chain could not detect.
        tampered = text.replace("value-3", "value-X", 1)
        assert tampered != text
        path.write_text(tampered, encoding="utf-8")
        ok, broken = ComplianceAuditTrail.verify_file(str(path))
        assert ok is False
        assert broken >= 0

    def test_verify_file_detects_middle_line_removal(self, tmp_path: Path) -> None:
        from crp.security.audit_trail import ComplianceAuditTrail

        trail = ComplianceAuditTrail(session_id="s1")
        for i in range(5):
            trail.record("compliance.data_processed", data={"i": i})
        path = tmp_path / "s1.audit.jsonl"
        lines = trail.export_jsonl().splitlines()
        # Remove a MIDDLE line: the next entry's previous_hash linkage then
        # points at a hash the file no longer contains.
        path.write_text("\n".join([lines[0], lines[1], *lines[3:]]) + "\n", encoding="utf-8")
        ok, broken = ComplianceAuditTrail.verify_file(str(path))
        assert ok is False
        assert broken == 2
        # TAIL truncation (the restart artefact) is caught by the external
        # anchor instead — covered by test_anchor_roundtrip_and_tamper_detection.

    def test_anchor_roundtrip_and_tamper_detection(self, tmp_path: Path) -> None:
        from crp.security.audit_anchor import anchor_to_file, verify_audit_file
        from crp.security.audit_trail import ComplianceAuditTrail

        trail = ComplianceAuditTrail(session_id="s1")
        for i in range(4):
            trail.record("compliance.data_processed", data={"i": i})
        audit_path = tmp_path / "s1.audit.jsonl"
        anchor_path = tmp_path / "s1.audit.jsonl.anchor.json"
        audit_path.write_text(trail.export_jsonl(), encoding="utf-8")
        anchor_to_file(trail, anchor_path)
        assert verify_audit_file(anchor_path, audit_path) is True
        # Truncate the audit file: the recomputed Merkle root must diverge.
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        audit_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        assert verify_audit_file(anchor_path, audit_path) is False

    def test_verify_file_strict_receipts(self, tmp_path: Path) -> None:
        pytest.importorskip("cryptography", reason="receipt tests need [security] extra")
        from crp.security.audit_trail import ActionSigner, ComplianceAuditTrail

        trail = _signed_trail()
        for i in range(3):
            trail.record("compliance.data_processed", data={"i": i})
        path = tmp_path / "s.audit.jsonl"
        path.write_text(trail.export_jsonl(), encoding="utf-8")
        pub = trail._action_signer.public_key_pem()
        ok, broken = ComplianceAuditTrail.verify_file(str(path), public_key_pem=pub)
        assert ok is True and broken == -1
        # Wrong key must fail closed under strict receipt verification.
        other = ActionSigner().public_key_pem()
        ok2, _ = ComplianceAuditTrail.verify_file(str(path), public_key_pem=other)
        assert ok2 is False

    def test_mixed_version_receipt_chain_verifies(self, tmp_path: Path) -> None:
        """U-L5: a signer-backed chain whose entries mix schema 2.0.0 with
        transcript-capable 2.1.0 entries must still pass
        ``verify_chain(verify_receipts=True)`` (receipts are computed over the
        entry hash, which is schema-version-agnostic)."""
        pytest.importorskip("cryptography", reason="receipt tests need [security] extra")

        trail = _signed_trail()
        trail.record("compliance.data_processed", data={"i": 0})
        trail.record("compliance.data_processed", data={"i": 1})
        trail.record("compliance.transcript_recorded", data={"window": 1})
        versions = {e.schema_version for e in trail._entries}
        assert versions == {"2.0.0", "2.1.0"}  # genuinely mixed
        ok, broken = trail.verify_chain(verify_receipts=True)
        assert ok is True
        assert broken == -1
        # The export envelope must expose the NEWEST schema version (U-C14b).
        exported = trail.export()
        assert exported["audit_trail_version"] == "2.1.0"


# ---------------------------------------------------------------------------
# U-C11 — envelope determinism
# ---------------------------------------------------------------------------


def _fact(fid: str, text: str) -> Fact:
    f = Fact(text=text, confidence=0.8, category="test")
    f.id = fid
    return f


def _graph(facts: list[Fact], edges: list[FactEdge]) -> FactGraph:
    g = FactGraph()
    for f in facts:
        g.add_fact(f)
    for e in edges:
        g.add_edge(e)
    return g


class TestEnvelopeDeterminism:
    def test_dependency_bonus_is_input_order_independent(self) -> None:
        from crp.envelope.decomposer import decompose_task_aspects
        from crp.envelope.scoring import score_facts

        ti = TaskIntent(system_prompt="sys", task_input="Analyse network security vulnerabilities")
        decomp = decompose_task_aspects(ti)

        facts = [
            _fact(f"f{i}", text)
            for i, text in enumerate(
                [
                    "CVE-2024-1111 is a critical network vulnerability",
                    "the firewall exposes admin ports",
                    "an exploit for CVE-2024-1111 is public",
                    "the weather is sunny today",
                ]
            )
        ]
        edges = [
            FactEdge(source_id="f2", target_id="f1", relation_type=RelationType.RELATED, confidence=0.9),
            FactEdge(source_id="f3", target_id="f2", relation_type=RelationType.RELATED, confidence=0.9),
        ]

        def scores(order: list[Fact]) -> dict[str, float]:
            scored = score_facts(order, decomp, _graph(facts, edges))
            return {s.fact.id: s.composite_score for s in scored}

        forward = scores(list(facts))
        reversed_ = scores(list(reversed(facts)))
        assert set(forward) == set(reversed_)
        for fid in forward:
            assert math.isclose(forward[fid], reversed_[fid], rel_tol=1e-9, abs_tol=1e-9), (
                f"composite_score for {fid} depends on input order: "
                f"{forward[fid]} vs {reversed_[fid]}"
            )

    def test_rerank_idempotent_and_non_mutating(self) -> None:
        from crp.envelope.reranker import MIN_FACTS_FOR_RERANK, rerank
        from crp.envelope.scoring import ScoredFact

        n = MIN_FACTS_FOR_RERANK + 3
        scored = [
            ScoredFact(fact=_fact(f"f{i}", f"fact number {i}"), composite_score=float(i % 5))
            for i in range(n)
        ]
        before = [s.composite_score for s in scored]
        ti = TaskIntent(system_prompt="sys", task_input="rank these facts")

        r1 = rerank(list(scored), ti)
        after = [s.composite_score for s in scored]
        assert after == before, "rerank mutated the caller's ScoredFact objects"

        r2 = rerank(list(r1), ti)
        assert [s.fact.id for s in r1] == [s.fact.id for s in r2]
        assert [s.composite_score for s in r1] == [s.composite_score for s in r2]


# ---------------------------------------------------------------------------
# U-C8 / A-PR-1 — per-call max_continuations and unknown-kwarg hygiene
# ---------------------------------------------------------------------------


class _LengthThenStopProvider(LLMProvider):
    """First calls hit the token wall; the final call stops."""

    def __init__(self, segments: int = 3) -> None:
        self.calls = 0
        self._segments = segments

    def generate_chat(self, messages, max_tokens=None, **kwargs):
        self.calls += 1
        if self.calls < self._segments:
            return (f"segment {self.calls} ", "length")
        return (f"segment {self.calls}", "stop")

    def count_tokens(self, text):
        return max(1, len(text) // 4)

    def context_window_size(self):
        return 8192


class TestPerCallContinuationCap:
    def test_per_call_cap_below_config(self) -> None:
        provider = _LengthThenStopProvider()
        orch = CRPOrchestrator(provider=provider, max_continuations=50)
        orch._continuation_config.l3_extractor = None
        try:
            # Protocol semantics: max_continuations bounds TOTAL windows
            # (continuation_count includes the first window — see
            # crp/continuation/trigger.py evaluate_continuation).
            events = list(orch.dispatch_stream("sys", "Write 5 sections", max_continuations=2))
            done = events[-1]
            assert done.event_type == "done"
            assert done.data.continuation_windows == 1
            assert provider.calls == 2
        finally:
            orch.close()

    def test_config_bound_applies_without_kwarg(self) -> None:
        provider = _LengthThenStopProvider()
        orch = CRPOrchestrator(provider=provider, max_continuations=50)
        orch._continuation_config.l3_extractor = None
        try:
            events = list(orch.dispatch_stream("sys", "Write 5 sections"))
            done = events[-1]
            # Provider stops after its 3rd segment → config cap 50 is not
            # binding; the loop ends on the provider's own stop.
            assert done.data.continuation_windows == 2
            assert provider.calls == 3
        finally:
            orch.close()

    def test_unknown_dispatch_kwarg_warns(self) -> None:
        orch = CRPOrchestrator(provider=_LengthThenStopProvider())
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                orch.dispatch("sys", "task", bogus_kwarg=1)
            assert any("bogus_kwarg" in str(w.message) for w in caught), (
                "unknown dispatch kwarg did not produce a UserWarning"
            )
        finally:
            orch.close()

    def test_unknown_dispatch_kwarg_strict_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("CRP_DISPATCH_STRICT_KWARGS", "1")
        orch = CRPOrchestrator(provider=_LengthThenStopProvider())
        try:
            with pytest.raises(TypeError):
                orch.dispatch("sys", "task", bogus_kwarg=1)
        finally:
            orch.close()


# ---------------------------------------------------------------------------
# U-C10 — sliding session expiry
# ---------------------------------------------------------------------------


class TestSlidingSessionExpiry:
    def test_touch_slides_expiry_forward(self) -> None:
        handle = SessionHandle(created_at=time.time() - 100_000, expires_at=time.time() - 1)
        assert handle.is_expired
        handle.touch(timeout_s=3600)
        assert not handle.is_expired
        assert handle.expires_at > time.time() + 3500

    def test_orchestrator_session_check_slides_expiry(self) -> None:
        orch = CRPOrchestrator(
            provider=_LengthThenStopProvider(),
            session_timeout=3600,
        )
        try:
            original_expiry = orch.session.expires_at
            time.sleep(0.01)
            orch._check_session()  # noqa: SLF001 — conformance seam
            orch._check_session()  # noqa: SLF001
            assert orch.session.expires_at > original_expiry
            # Slid to (roughly) now + session_timeout.
            assert orch.session.expires_at <= time.time() + 3600 + 60
        finally:
            orch.close()


# ---------------------------------------------------------------------------
# A-PR-7 — low-novelty stop
# ---------------------------------------------------------------------------


class TestLowNoveltyStop:
    def test_repetitive_stop_continuations_terminate(self, monkeypatch) -> None:
        from crp.continuation import manager as mgr
        from crp.continuation.manager import ContinuationConfig, ContinuationManager

        # Deterministic gram metric: treat each whitespace token as a "gram"
        # so novelty composition is exactly controllable in the test.
        monkeypatch.setattr(mgr, "_window_6grams", lambda t: {w for w in t.split() if w})

        cfg = ContinuationConfig(
            max_continuations=50,
            stop_novelty_threshold=0.5,
            max_low_novelty_stops=2,
        )
        cm = ContinuationManager(cfg)

        # Four priors with disjoint vocabularies (each >= 48 tokens).
        priors: list[str] = []
        for p in range(4):
            words = [f"w{p}_{i}" for i in range(25)]
            priors.append(" ".join(words * 3))  # 75 tokens each

        # Two "stuck" windows built from DISJOINT vocabulary slices of the
        # pure priors. m_a reuses words every prior contains; m_b reuses the
        # words NO prior-share with m_a (each pool w{p}_0..18 vs w{p}_19..24)
        # plus brand-new words. Because the near-duplicate guard compares the
        # current window against every single prior, a mixer that already
        # pooled all four vocabularies makes any later low-novelty window
        # >= 30% similar to it — repetition_detected fires first and the
        # decider guard is unreachable.  Slices keep every single-prior
        # overlap < 0.30 while the union novelty stays < 0.5.
        def mix_a(tag: str) -> str:
            words = [f"w{p}_{i}" for p in range(4) for i in range(19)]
            words.append(tag)
            return " ".join(words)

        def mix_b(tag: str) -> str:
            # The complementary slice: w{p}_19..24 (unused by m_a) + new words.
            words = [f"w{p}_{i}" for p in range(4) for i in range(19, 25)]
            words.extend([f"new_{i}" for i in range(20)])
            words.append(tag)
            return " ".join(words)

        task = (
            "Write a comprehensive multi-section security report covering "
            "reconnaissance enumeration exploitation and remediation in depth"
        )
        state = None
        for i, out in enumerate(priors):
            state = cm.process_window(task, out, "stop", 75, [], window_id=f"w{i}")
            assert not state.finished, f"prior {i} unexpectedly terminated ({state.termination_reason})"
        state = cm.process_window(task, mix_a("mA"), "stop", 77, [], window_id="mA")
        assert not state.finished, "first low-novelty stop must not terminate yet"
        state = cm.process_window(task, mix_b("mB"), "stop", 75, [], window_id="mB")
        assert state.finished
        assert state.termination_reason == "low_novelty_stop"

    def test_feature_disabled_allows_repetition(self, monkeypatch) -> None:
        from crp.continuation import manager as mgr
        from crp.continuation.manager import ContinuationConfig, ContinuationManager

        monkeypatch.setattr(mgr, "_window_6grams", lambda t: {w for w in t.split() if w})
        cfg = ContinuationConfig(
            max_continuations=50,
            stop_novelty_threshold=0.5,
            max_low_novelty_stops=0,  # disabled
        )
        cm = ContinuationManager(cfg)
        out = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima " * 4
        task = "Write a comprehensive multi-section report with many distinct requirements alpha"
        last = None
        for i in range(5):
            last = cm.process_window(task, out, "stop", 96, [], window_id=f"w{i}")
        assert last is not None
        # Identical verbatim windows trip the pre-existing verbatim-repeat
        # guard; the point is the NEW decider guard must not be the reason.
        assert last.termination_reason != "low_novelty_stop"


# ---------------------------------------------------------------------------
# A-PR-2 — per-phase policy narrowing from the pristine caller policy
# ---------------------------------------------------------------------------


class TestPhasePolicyNarrowing:
    def test_disjoint_phase_tool_sets_keep_non_empty_late_phase_allowlist(self) -> None:
        from crp.cognition.phase_machine import Phase, PhasePlan
        from crp.stl.classifier import STLOperation
        from crp.stl.positioned import run_positioned
        from crp.tools.capability_fabric import (
            CapabilityProfile,
            PolicyContext,
            ToolCapabilityFabric,
        )

        recorded: list[frozenset | None] = []

        class RecordingFabric(ToolCapabilityFabric):
            def select(  # type: ignore[override]
                self,
                operation,
                query_text: str = "",
                *,
                query_embedding=None,
                profile=CapabilityProfile.FRONTIER,
                policy=None,
                available_facts=None,
                k=None,
            ):
                recorded.append(None if policy is None else frozenset(policy.allowlist or ()))
                return super().select(
                    operation,
                    query_text=query_text,
                    query_embedding=query_embedding,
                    profile=profile,
                    policy=policy,
                    available_facts=available_facts,
                    k=k,
                )

        def cap(cid: str) -> dict[str, Any]:
            return {
                "capability_id": cid, "kind": "tool", "version": "1.0.0",
                "operation_types": ["retrieve"],
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"}, "produces_facts": True,
                "cost_profile": {"tokens": 50, "latency_ms": 100, "safety_class": "read-only"},
                "metadata": {"description": cid},
            }

        fabric = RecordingFabric()
        for i in range(4):
            fabric.register_dict(cap(f"t{i}"))

        phases = [
            Phase(name=f"p{i}", prompt="", operations=[STLOperation.RETRIEVE], tools=[f"t{i}"])
            for i in range(4)
        ]
        plan = PhasePlan(phases=phases)
        policy = PolicyContext(allowlist={"t0", "t1", "t2", "t3"})

        def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
            if schema is not None:
                return '{"capability_id": null, "answer": "ok"}'
            return "ok"

        result = run_positioned(
            "retrieve something",
            model_call,
            fabric=fabric,
            policy=policy,
            phase_plan=plan,
            final_synthesis=False,
        )
        del result
        assert len(recorded) == 4, f"expected 4 select calls, got {len(recorded)}"
        # Every phase must see caller_allowlist ∩ phase_tools — in particular
        # phase 4, which the pre-6.2.2 accumulated-narrowing bug emptied.
        for i, allowlist in enumerate(recorded):
            assert allowlist == {f"t{i}"}, f"phase {i} saw allowlist {allowlist!r}"
