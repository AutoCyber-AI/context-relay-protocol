# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests: LLM decision provenance audit entries (§7.14.2).

Verifies that the 5 new audit event types are recorded during dispatch():
  - ENVELOPE_CONTEXT_SELECTED: what facts/context were provided to the LLM
  - LLM_CALL_COMPLETED: LLM call inputs, outputs, timing, decision basis
  - FACTS_EXTRACTED: what facts were extracted, confidence, stages, provenance
  - CONTINUATION_DECIDED: gap analysis, trigger result, decision rationale
  - QUALITY_TIER_ASSIGNED: tier scoring, decision chain summary
"""

from __future__ import annotations

import pytest

from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider
from crp.security.audit_trail import ComplianceEventType


# ---------------------------------------------------------------------------
# Test providers
# ---------------------------------------------------------------------------


class _FakeProvider(LLMProvider):
    """Minimal provider for provenance tests."""

    def __init__(self, output: str = "fake output response"):
        self._output = output

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        return self._output, "length"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4 or 1

    def context_window_size(self) -> int:
        return 4096

    @property
    def max_output_tokens(self) -> int | None:
        return 1024

    @property
    def model_name(self) -> str:
        return "fake-provenance-v1"


def _make_orch(**kwargs) -> CRPOrchestrator:
    provider = kwargs.pop("provider", None) or _FakeProvider()
    if "max_continuations" not in kwargs:
        kwargs["max_continuations"] = 0
    return CRPOrchestrator(provider=provider, **kwargs)


def _get_entries(orch: CRPOrchestrator, event_type: ComplianceEventType) -> list[dict]:
    """Return all audit entries of a given type."""
    export = orch.compliance_audit.export()
    return [
        e for e in export["entries"]
        if e["event_type"] == event_type.value
    ]


def _event_types(orch: CRPOrchestrator) -> list[str]:
    export = orch.compliance_audit.export()
    return [e["event_type"] for e in export["entries"]]


# ---------------------------------------------------------------------------
# ENVELOPE_CONTEXT_SELECTED tests
# ---------------------------------------------------------------------------


class TestEnvelopeContextSelected:
    """Verify envelope/context selection is audited with provenance."""

    def test_envelope_audit_recorded_on_dispatch(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        assert len(entries) >= 1

    def test_envelope_audit_has_budget_info(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        data = entries[0]["data"]
        assert "budget_tokens" in data
        assert "envelope_tokens" in data
        assert "saturation" in data
        assert isinstance(data["budget_tokens"], int)

    def test_envelope_audit_has_fact_selection_details(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        data = entries[0]["data"]
        assert "facts_available" in data
        assert "facts_included" in data
        assert "facts_considered" in data

    def test_envelope_audit_has_source_of_truth(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        data = entries[0]["data"]
        assert "source_of_truth" in data
        assert isinstance(data["source_of_truth"], str)
        assert len(data["source_of_truth"]) > 10

    def test_envelope_audit_has_selection_rationale(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        data = entries[0]["data"]
        assert "selection_rationale" in data
        assert "ranked" in data["selection_rationale"].lower()

    def test_envelope_audit_has_packed_facts_list(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain quantum computing")
        entries = _get_entries(orch, ComplianceEventType.ENVELOPE_CONTEXT_SELECTED)
        data = entries[0]["data"]
        assert "packed_facts" in data
        assert isinstance(data["packed_facts"], list)


# ---------------------------------------------------------------------------
# LLM_CALL_COMPLETED tests
# ---------------------------------------------------------------------------


class TestLLMCallCompleted:
    """Verify LLM call details are audited with full provenance."""

    def test_llm_call_audit_recorded(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        assert len(entries) >= 1

    def test_llm_call_has_token_breakdown(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "input_tokens" in data
        assert "system_tokens" in data
        assert "task_tokens" in data
        assert "envelope_tokens" in data
        assert "output_tokens" in data
        assert "generation_reserve" in data

    def test_llm_call_has_finish_reason(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert data["finish_reason"] == "length"

    def test_llm_call_has_timing(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "wall_time_ms" in data
        assert data["wall_time_ms"] >= 0

    def test_llm_call_has_context_utilization(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "context_utilization" in data
        assert "context_window" in data
        assert 0 <= data["context_utilization"] <= 1

    def test_llm_call_has_decision_basis(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "decision_basis" in data
        assert "finish_reason" in data["decision_basis"]
        assert isinstance(data["decision_basis"], str)

    def test_llm_call_has_prompt_hashes(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "system_prompt_hash" in data
        assert "task_input_hash" in data
        assert len(data["system_prompt_hash"]) == 16  # truncated hash

    def test_llm_call_has_envelope_info(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "write about AI safety")
        entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        data = entries[0]["data"]
        assert "envelope_provided" in data
        assert "envelope_facts_count" in data
        assert "envelope_saturation" in data


# ---------------------------------------------------------------------------
# FACTS_EXTRACTED tests
# ---------------------------------------------------------------------------


class TestFactsExtracted:
    """Verify fact extraction is audited with provenance chain."""

    def test_facts_extracted_audit_recorded(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        assert len(entries) >= 1

    def test_facts_extracted_has_total_and_confidence(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "total_facts" in data
        assert "average_confidence" in data
        assert isinstance(data["total_facts"], int)

    def test_facts_extracted_has_quality_gate(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "quality_gate_passed" in data
        assert isinstance(data["quality_gate_passed"], bool)

    def test_facts_extracted_has_stages_info(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "stages_run" in data
        assert "per_stage_latency_ms" in data
        assert isinstance(data["stages_run"], list)

    def test_facts_extracted_has_individual_fact_details(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "facts" in data
        assert isinstance(data["facts"], list)
        # Each fact entry should have provenance fields
        if data["facts"]:
            fact = data["facts"][0]
            assert "fact_id" in fact
            assert "confidence" in fact
            assert "extraction_stage" in fact
            assert "text_preview" in fact

    def test_facts_extracted_has_source_of_truth(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "source_of_truth" in data
        assert "LLM output" in data["source_of_truth"]
        assert "envelope" in data["source_of_truth"]

    def test_facts_extracted_has_extraction_latency(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "describe machine learning")
        entries = _get_entries(orch, ComplianceEventType.FACTS_EXTRACTED)
        data = entries[0]["data"]
        assert "extraction_latency_ms" in data
        assert data["extraction_latency_ms"] >= 0


# ---------------------------------------------------------------------------
# CONTINUATION_DECIDED tests
# ---------------------------------------------------------------------------


class TestContinuationDecided:
    """Verify continuation decisions are audited with rationale."""

    def test_continuation_audit_recorded(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "short task")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        assert len(entries) >= 1  # At least the initial decision

    def test_continuation_has_gap_analysis(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "short task")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        data = entries[0]["data"]
        assert "gap_score" in data
        assert "gap_coverage" in data
        assert 0 <= data["gap_coverage"] <= 1

    def test_continuation_has_trigger_details(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "short task")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        data = entries[0]["data"]
        assert "trigger_details" in data
        assert isinstance(data["trigger_details"], dict)

    def test_continuation_has_decision_rationale(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "short task")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        data = entries[0]["data"]
        assert "decision_rationale" in data
        assert "gap score" in data["decision_rationale"].lower()

    def test_continuation_not_triggered_with_zero_max(self):
        """With max_continuations=0, continuation should not trigger."""
        orch = _make_orch(max_continuations=0)
        orch.dispatch("system prompt", "write a detailed essay")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        assert len(entries) >= 1
        # First entry should show no continuation
        data = entries[0]["data"]
        assert data["evaluation_point"] == "post_primary_window"

    def test_continuation_has_finish_reason(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "short task")
        entries = _get_entries(orch, ComplianceEventType.CONTINUATION_DECIDED)
        data = entries[0]["data"]
        assert "finish_reason" in data
        assert data["finish_reason"] in ("stop", "length", "error")


# ---------------------------------------------------------------------------
# QUALITY_TIER_ASSIGNED tests
# ---------------------------------------------------------------------------


class TestQualityTierAssigned:
    """Verify quality tier is audited with scoring rationale."""

    def test_quality_tier_audit_recorded(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        assert len(entries) == 1

    def test_quality_tier_has_tier_value(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "quality_tier" in data
        assert data["quality_tier"] in ("S", "A", "B", "C", "D")

    def test_quality_tier_has_scoring_rationale(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "scoring_rationale" in data
        assert "facts" in data["scoring_rationale"].lower()
        assert "saturation" in data["scoring_rationale"].lower()

    def test_quality_tier_has_decision_chain_summary(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "decision_chain_summary" in data
        assert "LLM call" in data["decision_chain_summary"]
        assert "facts selected" in data["decision_chain_summary"]

    def test_quality_tier_has_gap_coverage(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "final_gap_score" in data
        assert "gap_coverage" in data
        assert 0 <= data["gap_coverage"] <= 1

    def test_quality_tier_has_security_flags(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "pii_in_input" in data
        assert "pii_in_output" in data
        assert "injection_markers" in data

    def test_quality_tier_has_performance_metrics(self):
        orch = _make_orch()
        orch.dispatch("system prompt", "explain CRP")
        entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        data = entries[0]["data"]
        assert "total_dispatch_ms" in data
        assert "crp_overhead_pct" in data


# ---------------------------------------------------------------------------
# End-to-end decision provenance chain
# ---------------------------------------------------------------------------


class TestDecisionProvenanceChain:
    """Verify the full decision chain is traceable from audit trail."""

    def test_full_chain_present_after_dispatch(self):
        """All 5 provenance events appear after a single dispatch."""
        orch = _make_orch()
        orch.dispatch("system prompt", "explain the CRP protocol")
        events = _event_types(orch)
        assert ComplianceEventType.ENVELOPE_CONTEXT_SELECTED.value in events
        assert ComplianceEventType.LLM_CALL_COMPLETED.value in events
        assert ComplianceEventType.FACTS_EXTRACTED.value in events
        assert ComplianceEventType.CONTINUATION_DECIDED.value in events
        assert ComplianceEventType.QUALITY_TIER_ASSIGNED.value in events

    def test_chain_order_is_correct(self):
        """Provenance events appear in logical pipeline order."""
        orch = _make_orch()
        orch.dispatch("system prompt", "explain the CRP protocol")
        export = orch.compliance_audit.export()
        entries = export["entries"]
        event_types = [e["event_type"] for e in entries]

        idx_env = event_types.index(ComplianceEventType.ENVELOPE_CONTEXT_SELECTED.value)
        idx_llm = event_types.index(ComplianceEventType.LLM_CALL_COMPLETED.value)
        idx_ext = event_types.index(ComplianceEventType.FACTS_EXTRACTED.value)
        idx_cont = event_types.index(ComplianceEventType.CONTINUATION_DECIDED.value)
        idx_tier = event_types.index(ComplianceEventType.QUALITY_TIER_ASSIGNED.value)

        assert idx_env < idx_llm < idx_ext < idx_cont < idx_tier

    def test_chain_integrity_verified(self):
        """Audit chain remains tamper-evident after provenance entries."""
        orch = _make_orch()
        orch.dispatch("system prompt", "explain the CRP protocol")
        valid, broken_at = orch.compliance_audit.verify_chain()
        assert valid
        assert broken_at == -1

    def test_multiple_dispatches_produce_multiple_chains(self):
        """Each dispatch produces its own set of provenance entries."""
        orch = _make_orch()
        orch.dispatch("system prompt", "first task")
        orch.dispatch("system prompt", "second task")

        llm_entries = _get_entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        assert len(llm_entries) >= 2

        tier_entries = _get_entries(orch, ComplianceEventType.QUALITY_TIER_ASSIGNED)
        assert len(tier_entries) >= 2

    def test_provenance_entries_have_session_id(self):
        """All provenance entries reference the correct session."""
        orch = _make_orch()
        orch.dispatch("system prompt", "task")
        session_id = orch._session.session_id

        for event_type in [
            ComplianceEventType.ENVELOPE_CONTEXT_SELECTED,
            ComplianceEventType.LLM_CALL_COMPLETED,
            ComplianceEventType.FACTS_EXTRACTED,
            ComplianceEventType.CONTINUATION_DECIDED,
            ComplianceEventType.QUALITY_TIER_ASSIGNED,
        ]:
            entries = _get_entries(orch, event_type)
            assert len(entries) >= 1, f"No entries for {event_type.name}"
            assert entries[0]["session_id"] == session_id

    def test_total_audit_count_increased(self):
        """Dispatch now produces significantly more audit entries."""
        orch = _make_orch()
        pre_count = orch.compliance_audit.entry_count
        orch.dispatch("system prompt", "task")
        post_count = orch.compliance_audit.entry_count
        # At minimum: ENVELOPE + LLM + FACTS + CONTINUATION + QUALITY
        # plus existing DATA_PROCESSED (start/end) = 7+ new entries per dispatch
        assert post_count - pre_count >= 7
