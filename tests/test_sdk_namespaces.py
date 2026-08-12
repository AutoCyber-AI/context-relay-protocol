# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests for the CRP SDK namespace proxies (SPEC-032 §5)."""

from __future__ import annotations

import crp
from crp.agent.budget import AgentSafetyBudget
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
from crp.security.safety_manifest import SafetyManifest
from crp.state.cso import CognitiveStateObject

# Orchestrator initialisation is moderately expensive; reuse one client across
# the simple smoke tests. A fresh client is created only where mutation matters.
_client = crp.SDKClient()


def test_safety_proxy_type() -> None:
    assert isinstance(_client.safety, _SafetyProxy)


def test_ckf_proxy_type() -> None:
    assert isinstance(_client.ckf, _CKFProxy)


def test_cso_proxy_type() -> None:
    assert isinstance(_client.cso, _CSOProxy)


def test_provenance_proxy_type() -> None:
    assert isinstance(_client.provenance, _ProvenanceProxy)


def test_reasoning_proxy_type() -> None:
    assert isinstance(_client.reasoning, _ReasoningProxy)


def test_activation_proxy_type() -> None:
    assert isinstance(_client.activation, _ActivationProxy)


def test_agent_proxy_type() -> None:
    assert isinstance(_client.agent, _AgentProxy)


def test_events_proxy_type() -> None:
    assert isinstance(_client.events, _EventsProxy)


def test_providers_proxy_type() -> None:
    assert isinstance(_client.providers, _ProvidersProxy)


def test_extract_proxy_type() -> None:
    assert isinstance(_client.extract, _ExtractionProxy)


def test_safety_profile_is_string() -> None:
    profile = _client.safety.profile
    assert isinstance(profile, str)


def test_safety_manifest() -> None:
    manifest = _client.safety.manifest()
    assert isinstance(manifest, SafetyManifest)


def test_ckf_fact_count() -> None:
    count = _client.ckf.fact_count()
    assert isinstance(count, int)
    assert count >= 0


def test_ckf_health() -> None:
    health = _client.ckf.health()
    assert health is not None


def test_cso_get() -> None:
    cso = _client.cso.get()
    assert isinstance(cso, CognitiveStateObject)


def test_provenance_score() -> None:
    score = _client.provenance.score("hello")
    assert isinstance(score, dict)


def test_reasoning_scaffold() -> None:
    scaffold = _client.reasoning.scaffold("task")
    assert isinstance(scaffold, str)


def test_activation_mode() -> None:
    mode = _client.activation.mode()
    assert isinstance(mode, str)


def test_agent_budget() -> None:
    budget = _client.agent.budget()
    assert isinstance(budget, AgentSafetyBudget)


def test_events_subscribe() -> None:
    # Should silently succeed even when no event emitter is configured.
    _client.events.subscribe("test", lambda payload: None)


def test_providers_list_supported() -> None:
    providers = _client.providers.list_supported()
    assert isinstance(providers, list)
    assert all(isinstance(p, str) for p in providers)


def test_extract_facts() -> None:
    facts = _client.extract.facts("The sky is blue.")
    assert isinstance(facts, list)


def test_storage_proxy_type() -> None:
    assert isinstance(_client.storage, _StorageProxy)


def test_knowledge_proxy_type() -> None:
    assert isinstance(_client.knowledge, _KnowledgeProxy)


def test_audit_proxy_type() -> None:
    assert isinstance(_client.audit, _AuditProxy)


def test_compliance_proxy_type() -> None:
    assert isinstance(_client.compliance, _ComplianceProxy)


def test_storage_fact_count() -> None:
    count = _client.storage.fact_count()
    assert isinstance(count, int)
    assert count >= 0


def test_knowledge_location() -> None:
    location = _client.knowledge.location
    assert isinstance(location, str)


def test_audit_summary() -> None:
    summary = _client.audit.summary()
    assert isinstance(summary, dict)


def test_compliance_report() -> None:
    report = _client.compliance.report()
    assert isinstance(report, dict)


def test_safety_setter() -> None:
    # Create a fresh client so the profile is applied on first orchestrator init.
    fresh = crp.SDKClient()
    fresh.safety = "strict"
    # Accessing the property triggers orchestrator creation with the strict profile.
    assert isinstance(fresh.safety.profile, str)


def test_context_manager() -> None:
    with crp.SDKClient() as c:
        assert isinstance(c, crp.CRPClient)
        assert isinstance(c.safety, _SafetyProxy)


def test_safety_set_and_show() -> None:
    fresh = crp.SDKClient()
    fresh.safety.set(require_grounding=0.85)
    assert fresh.safety.manifest().get("require_grounding") == 0.85
    show = fresh.safety.show()
    assert "CRP SAFETY CONTROL PLANE" in show
    assert "grounding_verification" in show


def test_safety_set_profile() -> None:
    fresh = crp.SDKClient()
    fresh.safety.set_profile("strict")
    assert fresh.safety.profile == "strict"
    assert fresh.safety.manifest().get("pii_handling") == "block"


def test_safety_registry_and_explain() -> None:
    fresh = crp.SDKClient()
    registry = fresh.safety.registry()
    assert any(cap["name"] == "grounding_verification" for cap in registry)
    explanation = fresh.safety.explain("grounding_verification")
    assert "grounding" in explanation.lower()
    unknown = fresh.safety.explain("not_a_real_capability")
    assert "unknown" in unknown.lower()
