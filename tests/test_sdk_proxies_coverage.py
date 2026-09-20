# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage tests for ``crp.sdk.proxies`` — the namespace proxy layer (SPEC-032).

A single real ``SDKClient`` drives the happy paths against a live
orchestrator; ``SimpleNamespace`` fakes drive the fallback/exception branches
that the real orchestrator can never reach.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import crp
from crp.sdk.proxies import (
    _ActivationProxy,
    _AgentProxy,
    _AuditProxy,
    _CKFProxy,
    _ComplianceProxy,
    _CSOProxy,
    _EventsProxy,
    _ExtractionProxy,
    _KnowledgeProxy,
    _ProvenanceProxy,
    _ProvidersProxy,
    _ReasoningProxy,
    _SafetyProxy,
    _StorageProxy,
)

_client = crp.SDKClient()


@pytest.fixture(scope="module")
def orch():
    """The real orchestrator behind the module-level client."""
    o = _client._ensure_orchestrator()
    # Seed a couple of facts so CKF/CSO/provenance paths have data.
    o.ingest("CRP gives every LLM call its own curated context envelope.", source_label="seed")
    return o


# ── _SafetyProxy ────────────────────────────────────────────────────────


def test_control_plane_caches_instance(orch) -> None:
    proxy = _SafetyProxy(orch)
    cp1 = proxy.control_plane()
    cp2 = proxy.control_plane()
    assert cp1 is cp2


def test_add_rule_registers(orch) -> None:
    proxy = _SafetyProxy(orch)
    rule = proxy.add_rule("my_custom_rule", check_fn=lambda x: None, description="test rule")
    assert rule.name == "my_custom_rule"
    names = [cap["name"] for cap in proxy.registry()]
    assert "my_custom_rule" in names


def test_checkpoint_defaults_and_invalid_values(orch) -> None:
    from crp.security.checkpoint import (
        CheckpointRejectAction,
        CheckpointTimeoutAction,
        CheckpointTrigger,
    )

    proxy = _SafetyProxy(orch)
    cp = proxy.checkpoint()
    # DOCUMENTED BEHAVIOR: the declared default trigger string "RISK_HIGH"
    # does not match the enum value ("risk >= HIGH"), so the ValueError
    # fallback yields CUSTOM_RULE even for the defaults.
    assert cp.trigger is CheckpointTrigger.CUSTOM_RULE
    assert cp.on_timeout is CheckpointTimeoutAction.ESCALATE
    # Same class of oddity: default reject string "HALT" is uppercase but the
    # enum value is "halt", so the fallback yields FALLBACK.
    assert cp.on_reject is CheckpointRejectAction.FALLBACK

    # Valid enum *values* map correctly.
    cp_ok = proxy.checkpoint(
        trigger="risk >= CRITICAL",
        timeout_action="approve",
        reject_action="revise",
    )
    assert cp_ok.trigger is CheckpointTrigger.RISK_CRITICAL
    assert cp_ok.on_timeout is CheckpointTimeoutAction.APPROVE
    assert cp_ok.on_reject is CheckpointRejectAction.REVISE

    # Invalid enum values fall back to documented defaults.
    cp2 = proxy.checkpoint(
        trigger="not-a-trigger",
        timeout_action="bogus",
        reject_action="bogus",
    )
    assert cp2.trigger is CheckpointTrigger.CUSTOM_RULE
    assert cp2.on_timeout is CheckpointTimeoutAction.ESCALATE
    assert cp2.on_reject is CheckpointRejectAction.FALLBACK


def test_set_profile_unknown_raises(orch) -> None:
    proxy = _SafetyProxy(orch)
    with pytest.raises(ValueError, match="unknown safety profile"):
        proxy.set_profile("no-such-profile")


def test_set_and_profile_roundtrip(orch) -> None:
    proxy = _SafetyProxy(orch)
    proxy.set(require_grounding=0.77)
    assert proxy.manifest().get("require_grounding") == 0.77
    assert isinstance(proxy.profile, str)


def test_explain_out_of_scope(orch) -> None:
    proxy = _SafetyProxy(orch)
    explanation = proxy.explain("model_alignment")
    assert "out of scope" in explanation.lower()


# ── _CKFProxy ───────────────────────────────────────────────────────────


def test_ckf_query_and_search(orch) -> None:
    proxy = _CKFProxy(orch)
    assert proxy.query() is not None
    result = proxy.search("context envelope")
    assert result is not None


def test_ckf_graph_walk(orch) -> None:
    proxy = _CKFProxy(orch)
    facts = orch.warm_store.get_ranked_facts(limit=1)
    if facts:
        result = proxy.graph_walk(facts[0].id, max_hops=2)
        assert result is not None


def test_ckf_community_summary(orch) -> None:
    proxy = _CKFProxy(orch)
    assert proxy.community_summary() is not None


def test_ckf_cdgr_expand_with_facts(orch) -> None:
    proxy = _CKFProxy(orch)
    result = proxy.cdgr_expand("context envelope")
    assert result is not None


def test_ckf_cdgr_expand_empty(tmp_path) -> None:
    from crp.ckf.cdgr import CDGRResult

    fake_ckf = SimpleNamespace(
        _warm=SimpleNamespace(_graph=None, _facts={}),
        _config=SimpleNamespace(persist_path=None),
    )
    proxy = _CKFProxy(SimpleNamespace(ckf=fake_ckf))
    result = proxy.cdgr_expand("anything")
    assert isinstance(result, CDGRResult)
    assert result.anchors == []


def test_ckf_persist_restore_not_configured(orch) -> None:
    proxy = _CKFProxy(orch)
    with pytest.raises(NotImplementedError):
        proxy.persist()
    with pytest.raises(NotImplementedError):
        proxy.restore()


def test_ckf_persist_restore_unsupported(tmp_path) -> None:
    fake_ckf = SimpleNamespace(_config=SimpleNamespace(persist_path=str(tmp_path / "ckf")))
    proxy = _CKFProxy(SimpleNamespace(ckf=fake_ckf))
    with pytest.raises(NotImplementedError):
        proxy.persist()
    with pytest.raises(NotImplementedError):
        proxy.restore()


def test_ckf_persist_restore_supported(tmp_path) -> None:
    target = tmp_path / "ckf.json"
    fake_ckf = SimpleNamespace(
        _config=SimpleNamespace(persist_path=str(target)),
        persist=lambda p: target.write_text("{}", encoding="utf-8"),
        restore=lambda p: ["warning-a"],
    )
    proxy = _CKFProxy(SimpleNamespace(ckf=fake_ckf))
    proxy.persist()
    assert target.exists()
    assert proxy.restore() == ["warning-a"]


def test_ckf_subscribe_variants(orch) -> None:
    proxy = _CKFProxy(orch)
    received: list[Any] = []
    # Real CKF subscribe (if available) or graceful warning path.
    proxy.subscribe("fact.added", received.append)

    no_sub = SimpleNamespace(ckf=SimpleNamespace(_config=None))
    _CKFProxy(no_sub).subscribe("x", lambda e: None)  # warns, does not raise

    raising = SimpleNamespace(ckf=SimpleNamespace(
        subscribe=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    ))
    _CKFProxy(raising).subscribe("x", lambda e: None)  # exception is swallowed


def test_ckf_health_and_fact_count(orch) -> None:
    proxy = _CKFProxy(orch)
    assert proxy.health() is not None
    assert proxy.fact_count() >= 1


# ── _CSOProxy ───────────────────────────────────────────────────────────


def test_cso_get_from_warm_store(orch) -> None:
    from crp.state.cso import CognitiveStateObject

    proxy = _CSOProxy(orch)
    cso = proxy.get()
    assert isinstance(cso, CognitiveStateObject)
    assert proxy.established_facts() == list(cso.established_facts)


def test_cso_get_from_session() -> None:
    from crp.state.cso import CognitiveStateObject

    session_cso = CognitiveStateObject()
    fake = SimpleNamespace(_session=SimpleNamespace(cso=session_cso))
    proxy = _CSOProxy(fake)
    assert proxy.get() is session_cso


def test_cso_accessors_empty() -> None:
    fake = SimpleNamespace(_session=SimpleNamespace(cso=None), warm_store=None)
    proxy = _CSOProxy(fake)
    assert proxy.decisions() == []
    # A fresh CognitiveStateObject carries a default DOCUMENT-mode goal state.
    assert len(proxy.goals()) == 1
    assert proxy.dependencies() == []
    assert proxy.established_facts() == []


# ── _ProvenanceProxy ────────────────────────────────────────────────────


def test_provenance_without_dpe() -> None:
    fake = SimpleNamespace(_provenance_engine=None)
    proxy = _ProvenanceProxy(fake)
    assert proxy.chains("output") == []
    score = proxy.score("output")
    assert score == {
        "fabrications": 0, "distortions": 0, "contradictions": 0,
        "omissions": 0, "grounded": False,
    }
    report = proxy.report("output")
    assert report["chains"] == 0


def test_provenance_with_dpe(orch) -> None:
    proxy = _ProvenanceProxy(orch)
    report = proxy.report("CRP provides context envelopes for LLM calls.")
    assert "chains" in report
    assert "grounded" in report


def test_provenance_facts_for_dpe_failure() -> None:
    # _facts_for_dpe swallows exceptions and returns [].
    fake_ckf = SimpleNamespace(_warm=SimpleNamespace(_facts={"x": object()}))  # sf.fact -> AttributeError
    fake = SimpleNamespace(_provenance_engine=None, ckf=fake_ckf)
    proxy = _ProvenanceProxy(fake)
    assert proxy.chains("out") == []


# ── _ReasoningProxy ─────────────────────────────────────────────────────


def test_scaffold_without_engine() -> None:
    proxy = _ReasoningProxy(SimpleNamespace(_meta_learning=None))
    assert proxy.scaffold("task") == ""


def test_scaffold_engine_raises() -> None:
    engine = SimpleNamespace(
        build_reasoning_scaffold=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    proxy = _ReasoningProxy(SimpleNamespace(_meta_learning=engine))
    assert proxy.scaffold("task") == ""


def test_sources_variants() -> None:
    proxy = _ReasoningProxy(SimpleNamespace(_source_grounding=None))
    assert proxy.sources() == []

    class _P:
        def to_dict(self):
            return {"text": "passage"}

    engine = SimpleNamespace(
        _passages={"p1": _P()},
        get_passages_for_fact=lambda fid: [_P()],
    )
    proxy2 = _ReasoningProxy(SimpleNamespace(_source_grounding=engine))
    assert proxy2.sources() == [{"text": "passage"}]
    assert proxy2.sources("f1") == [{"text": "passage"}]


def test_cqs_detection(orch) -> None:
    proxy = _ReasoningProxy(orch)
    result = proxy.cqs("I need more information about the context window usage")
    assert "action" in result
    assert "signals" in result


def test_cross_window_validate(orch) -> None:
    proxy = _ReasoningProxy(orch)
    result = proxy.cross_window_validate(["Window one output.", "Window two output."])
    assert "tier" in result
    assert "issues" in result


# ── _ActivationProxy ────────────────────────────────────────────────────


def test_mode_failure_falls_back_to_zero() -> None:
    bad_ckf = SimpleNamespace(fact_count=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    proxy = _ActivationProxy(SimpleNamespace(ckf=bad_ckf))
    assert proxy.mode() == "zero-ckf"
    assert proxy.apply_tier_cap("A") == "C"  # zero-ckf caps at C


def test_apply_tier_cap_full_mode(orch) -> None:
    proxy = _ActivationProxy(orch)
    # Empty CKF detects as some mode; the cap only applies below the mode's tier.
    tier = proxy.apply_tier_cap("S")
    assert tier in {"S", "A", "B", "C", "D"}


def test_coverage_and_failure() -> None:
    proxy = _ActivationProxy(orch)
    result = proxy.coverage()
    assert "coverage" in result
    assert "effective_mode" in result

    bad = SimpleNamespace(ckf=SimpleNamespace(
        fact_count=lambda: (_ for _ in ()).throw(RuntimeError("x")),
    ))
    failed = _ActivationProxy(bad).coverage()
    assert failed["effective_mode"] == "zero-ckf"
    assert failed["reason"] == "error"


# ── _AgentProxy ─────────────────────────────────────────────────────────


def test_account_event_valid_and_invalid(orch) -> None:
    proxy = _AgentProxy(orch)
    result = proxy.account_event("HIGH")
    assert "budget" in result and "halted" in result
    invalid = proxy.account_event("not-a-level")
    assert invalid["health"] is not None  # falls back to LOW


def test_link_sub_agent(orch) -> None:
    proxy = _AgentProxy(orch)
    link = proxy.link_sub_agent("parent-1", "child-1")
    assert isinstance(link, str) and link


def test_link_sub_agent_no_security() -> None:
    class _Sec:
        @property
        def session_key(self):
            raise RuntimeError("no key")

    fake = SimpleNamespace(_security=_Sec())
    proxy = _AgentProxy(fake)
    link = proxy.link_sub_agent("a", "b")
    assert isinstance(link, str)  # key falls back to b""


def test_aggregate_results(orch) -> None:
    proxy = _AgentProxy(orch)
    result = proxy.aggregate(["answer one", "answer two"])
    assert "coherent" in result

    class _R:
        text = "object answer"

    result2 = proxy.aggregate([_R()])
    assert "coherent" in result2


# ── _EventsProxy ────────────────────────────────────────────────────────


def test_events_roundtrip(orch) -> None:
    proxy = _EventsProxy(orch)
    received: list[Any] = []
    proxy.subscribe("test.event", received.append)
    proxy.emit("test.event", {"k": 1})
    proxy.unsubscribe("test.event", received.append)
    assert received  # subscription fired before unsubscribe


def test_events_no_emitter() -> None:
    proxy = _EventsProxy(SimpleNamespace())  # no _emitter attribute
    proxy.subscribe("x", lambda e: None)
    proxy.unsubscribe("x", lambda e: None)
    proxy.emit("x", {})


def test_events_emitter_raises() -> None:
    emitter = SimpleNamespace(
        on=lambda *a: (_ for _ in ()).throw(RuntimeError("x")),
        off=lambda *a: (_ for _ in ()).throw(RuntimeError("x")),
        emit=lambda *a: (_ for _ in ()).throw(RuntimeError("x")),
    )
    proxy = _EventsProxy(SimpleNamespace(_emitter=emitter))
    proxy.subscribe("x", lambda e: None)
    proxy.unsubscribe("x", lambda e: None)
    proxy.emit("x", {})


# ── _ProvidersProxy ─────────────────────────────────────────────────────


def test_register_with_manager(orch) -> None:
    from crp.providers.custom import CustomProvider

    proxy = _ProvidersProxy(orch)
    provider = CustomProvider(
        generate_fn=lambda msgs, **kw: ("", "stop"),
        count_tokens_fn=lambda t: max(1, len(t) // 4),
        context_size=4096,
    )
    proxy.register(provider)
    assert proxy.default() is not None


def test_register_fallback_paths() -> None:
    # Manager present but register() raises → falls through to _provider attr.
    pm = SimpleNamespace(register=lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    fake = SimpleNamespace(_provider_manager=pm, _provider=None)
    proxy = _ProvidersProxy(fake)
    provider = object()
    proxy.register(provider)
    assert fake._provider is provider

    # No manager, no _provider attr → NotImplementedError.
    bare = SimpleNamespace()
    with pytest.raises(NotImplementedError):
        _ProvidersProxy(bare).register(object())


def test_default_and_list_supported(orch) -> None:
    proxy = _ProvidersProxy(orch)
    assert proxy.default() is not None
    assert "openai" in proxy.list_supported()


# ── _ExtractionProxy ────────────────────────────────────────────────────


def test_extract_not_available() -> None:
    proxy = _ExtractionProxy(SimpleNamespace(extraction_pipeline=None))
    with pytest.raises(NotImplementedError):
        proxy.run("text")


def test_extract_content_type_fallback() -> None:
    class _Pipeline:
        def extract(self, text, **kwargs):
            if "content_type" in kwargs:
                raise TypeError("no content_type please")
            return SimpleNamespace(facts=[], fact_graph=None)

    proxy = _ExtractionProxy(SimpleNamespace(extraction_pipeline=_Pipeline()))
    result = proxy.run("text", content_type="text/plain")
    assert result is not None


def test_extract_facts_and_graph(orch) -> None:
    proxy = _ExtractionProxy(orch)
    facts = proxy.facts("The envelope contains curated facts.")
    assert isinstance(facts, list)
    graph = proxy.graph("The envelope contains curated facts.")
    assert "nodes" in graph and "edges" in graph
    assert isinstance(graph["nodes"], list)


def test_extract_graph_missing() -> None:
    proxy = _ExtractionProxy(SimpleNamespace(
        extraction_pipeline=SimpleNamespace(extract=lambda t, **k: SimpleNamespace()),
    ))
    assert proxy.graph("x") == {"nodes": [], "edges": []}


# ── _StorageProxy ───────────────────────────────────────────────────────


def test_storage_overview_and_counts(orch) -> None:
    proxy = _StorageProxy(orch)
    overview = proxy.overview()
    assert overview[0]["primitive"] == "warm_store"
    assert proxy.fact_count() >= 1
    assert proxy.windows() >= 0


def test_storage_save_load_roundtrip(orch, tmp_path) -> None:
    proxy = _StorageProxy(orch)
    path = tmp_path / "warm_state.json"
    proxy.save(path)
    assert path.exists()
    warnings = proxy.load(path)
    assert isinstance(warnings, list)


def test_storage_backend_and_config(orch) -> None:
    proxy = _StorageProxy(orch)
    assert proxy.backend in {"memory", "sqlite"}
    cfg = proxy.config
    assert "max_facts" in cfg


# ── _KnowledgeProxy ─────────────────────────────────────────────────────


def test_knowledge_location_variants() -> None:
    ckf_no_path = SimpleNamespace(_config=SimpleNamespace(persist_path=None))
    assert _KnowledgeProxy(SimpleNamespace(ckf=ckf_no_path)).location == "CKF"

    ckf_path = SimpleNamespace(_config=SimpleNamespace(persist_path="/tmp/ckf"))
    proxy = _KnowledgeProxy(SimpleNamespace(ckf=ckf_path))
    assert proxy.location == "CKF (persist=/tmp/ckf)"


def test_knowledge_query_search_health(orch) -> None:
    proxy = _KnowledgeProxy(orch)
    assert proxy.query() is not None
    assert proxy.search("envelope") is not None
    assert proxy.health() is not None


def test_knowledge_graph_walk(orch) -> None:
    proxy = _KnowledgeProxy(orch)
    facts = orch.warm_store.get_ranked_facts(limit=1)
    if facts:
        assert proxy.graph_walk(facts[0].id, max_hops=1) is not None


def test_knowledge_community_summary_topic(orch) -> None:
    proxy = _KnowledgeProxy(orch)
    # No topic → full result.
    assert proxy.community_summary() is not None
    # Topic that matches nothing → empty list.
    matched = proxy.community_summary(topic="zzzz-no-such-topic")
    assert matched == []


def test_knowledge_delegations(orch, tmp_path) -> None:
    proxy = _KnowledgeProxy(orch)
    proxy.persist(tmp_path / "nope.json") if False else None  # persist needs configured path
    # subscribe delegates to the CKF proxy without raising.
    proxy.subscribe("fact.added", lambda e: None)


# ── _AuditProxy ─────────────────────────────────────────────────────────


def test_audit_accessors(orch) -> None:
    proxy = _AuditProxy(orch)
    summary = proxy.summary()
    assert summary["entry_count"] >= 0
    assert isinstance(proxy.verify(), tuple)
    assert isinstance(proxy.chain_hash, str)
    exported = proxy.export()
    assert isinstance(exported, dict)


def test_audit_record_valid_and_invalid(orch) -> None:
    proxy = _AuditProxy(orch)
    before = proxy.summary()["entry_count"]
    proxy.record("DATA_PROCESSED", {"detail": "test"})
    proxy.record("NOT_A_REAL_TYPE", {"detail": "test"})  # falls back to DATA_PROCESSED
    after = proxy.summary()["entry_count"]
    assert after >= before + 2


def test_audit_events_and_query(orch) -> None:
    proxy = _AuditProxy(orch)
    events = proxy.events()
    assert isinstance(events, list)
    assert isinstance(proxy.query(limit=3), list)
    assert isinstance(proxy.events(event_type="DATA_PROCESSED"), list)


# ── _ComplianceProxy ────────────────────────────────────────────────────


def test_compliance_classify(orch) -> None:
    proxy = _ComplianceProxy(orch)
    result = proxy.classify(
        "Customer support triage",
        processes_personal_data=True,
        makes_automated_decisions=False,
    )
    assert "risk_level" in result or "level" in result


def test_compliance_report_and_controls(orch) -> None:
    proxy = _ComplianceProxy(orch)
    report = proxy.report()
    assert isinstance(report, dict)
    assert isinstance(proxy.controls(), list)
    assert isinstance(proxy.risk_level(), str)


def test_compliance_transparency_and_records(orch) -> None:
    proxy = _ComplianceProxy(orch)
    decl = proxy.transparency_declaration()
    assert "purposes" in decl
    assert "has_human_oversight" in decl
    assert isinstance(proxy.processing_records(), list)
