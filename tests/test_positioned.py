# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Tool Positioner and the live positioned-tool-loop (CRP-SPEC-049/050)."""

from __future__ import annotations

from typing import Any

from crp.stl import (
    STLOperation,
    build_operation_frame,
    build_tool_positioning_frame,
    guard_prompt_budget,
    parse_tool_call,
    run_positioned,
)
from crp.tools import (
    CapabilityExecutor,
    CapabilityProfile,
    PolicyContext,
    SafetyClass,
    ToolCapabilityFabric,
)


def _cap(cid: str, op: str, *, required: list[str] | None = None,
         safety: str = "read-only", desc: str = "") -> dict[str, Any]:
    props = {r: {"type": "string"} for r in (required or [])}
    return {
        "capability_id": cid, "kind": "tool", "version": "1.0.0",
        "operation_types": [op],
        "input_schema": {"type": "object", "properties": props, "required": required or []},
        "output_schema": {"type": "object"}, "produces_facts": True,
        "cost_profile": {"tokens": 50, "latency_ms": 100, "safety_class": safety},
        "metadata": {"description": desc},
    }


def _fabric(*caps: dict[str, Any]) -> ToolCapabilityFabric:
    tcf = ToolCapabilityFabric()
    for c in caps:
        tcf.register_dict(c)
    return tcf


# ── Tool Positioner ─────────────────────────────────────────────────────────


class TestToolPositioner:
    def _frame(self) -> Any:
        tcf = _fabric(_cap("lookup", "RETRIEVE", required=["q"], desc="look something up"))
        sel = tcf.select(STLOperation.RETRIEVE, profile=CapabilityProfile.SMALL_LOCAL)
        opframe = build_operation_frame(STLOperation.RETRIEVE, "find x", [])
        return build_tool_positioning_frame(opframe, sel, profile=CapabilityProfile.SMALL_LOCAL)

    def test_frame_lists_tools(self) -> None:
        tpf = self._frame()
        prompt = tpf.to_prompt()
        assert "lookup" in prompt
        assert "capability_id" in prompt  # the response contract
        assert tpf.max_calls == 1  # small-local

    def test_output_schema_enumerates_ids(self) -> None:
        tpf = self._frame()
        schema = tpf.output_schema()
        assert "lookup" in schema["properties"]["capability_id"]["enum"]

    def test_parse_valid_tool_call(self) -> None:
        tpf = self._frame()
        call = parse_tool_call('{"capability_id": "lookup", "arguments": {"q": "x"}}', tpf)
        assert call is not None and call.is_tool_call
        assert call.capability_id == "lookup"
        assert call.arguments == {"q": "x"}

    def test_parse_direct_answer(self) -> None:
        tpf = self._frame()
        call = parse_tool_call('{"capability_id": null, "answer": "42"}', tpf)
        assert call is not None and not call.is_tool_call
        assert call.answer == "42"

    def test_parse_code_fenced(self) -> None:
        tpf = self._frame()
        raw = '```json\n{"capability_id": "lookup", "arguments": {"q": "y"}}\n```'
        call = parse_tool_call(raw, tpf)
        assert call is not None and call.capability_id == "lookup"

    def test_parse_unknown_id_snaps_to_single(self) -> None:
        tpf = self._frame()
        call = parse_tool_call('{"capability_id": "ghost", "arguments": {"q": "z"}}', tpf)
        assert call is not None and call.capability_id == "lookup"

    def test_parse_unparseable_returns_answer(self) -> None:
        tpf = self._frame()
        call = parse_tool_call("just some prose, no json", tpf)
        assert call is not None and not call.is_tool_call
        assert "prose" in call.answer


# ── Positioned loop ─────────────────────────────────────────────────────────


def _tool_model(tool_json: str, text: str = "direct output"):
    def _call(prompt: str, schema: dict[str, Any] | None) -> str:
        return tool_json if schema is not None else text
    return _call


class TestPositionedLoop:
    def test_direct_generation_no_fabric(self) -> None:
        res = run_positioned("write a haiku about rain", _tool_model("", text="rain falls"))
        assert res.text == "rain falls"
        assert res.operations == ["generate"]
        assert not res.halted
        assert res.state_machine is not None and res.state_machine.is_complete
        assert res.observation_count == 0

    def test_multi_operation_assembly(self) -> None:
        res = run_positioned("compare and analyse the two designs", _tool_model("", text="section"))
        assert len(res.operations) >= 2
        assert "## COMPARE" in res.text and "## ANALYSE" in res.text

    def test_tool_execution_stores_observation(self) -> None:
        tcf = _fabric(_cap("lookup", "RETRIEVE", required=["q"], desc="look up records"))
        ex = CapabilityExecutor()
        ex.register_impl(
            "lookup",
            lambda args: {"hits": [args.get("q")]},
            extractor=lambda raw, args: {"found": raw["hits"]},
        )
        res = run_positioned(
            "find alpha records",
            _tool_model('{"capability_id": "lookup", "arguments": {"q": "alpha"}}'),
            fabric=tcf, executor=ex, profile=CapabilityProfile.SMALL_LOCAL,
        )
        assert res.observation_count == 1
        assert any("lookup" in f.statement for f in res.cso.established_facts)
        assert "TOOL_EXECUTED" in [e["state"] for e in res.event_stream]
        assert "alpha" in res.text
        assert not res.halted

    def test_multi_turn_state_relay(self) -> None:
        """A follow-up turn seeded with prior_cso carries forward established state."""
        tcf = _fabric(_cap("lookup", "RETRIEVE", required=["q"], desc="look up records"))
        ex = CapabilityExecutor()
        ex.register_impl("lookup", lambda args: {"service": "HTTPS"})
        turn1 = run_positioned(
            "look up the service on port 443",
            _tool_model('{"capability_id": "lookup", "arguments": {"q": "443"}}'),
            fabric=tcf, executor=ex, profile=CapabilityProfile.SMALL_LOCAL,
        )
        assert turn1.observation_count == 1

        # Turn 2 relays turn 1's CSO; no tool needed — state must carry forward.
        turn2 = run_positioned(
            "based on what we found, summarise it",
            _tool_model("", text="it is HTTPS"),
            prior_cso=turn1.cso,
        )
        # facts relayed, window advanced, prior context visible to the model
        assert any("HTTPS" in f.statement.upper() for f in turn2.cso.established_facts)
        assert turn2.cso.window_number == turn1.cso.window_number + 1
        assert "HTTPS" in turn2.cso.to_prompt_context().upper()
        assert not turn2.halted

    def test_selection_only_without_executor(self) -> None:
        tcf = _fabric(_cap("search", "RETRIEVE", required=["q"], desc="search"))
        res = run_positioned(
            "find something",
            _tool_model('{"capability_id": "search", "arguments": {"q": "x"}}'),
            fabric=tcf, profile=CapabilityProfile.SMALL_LOCAL,
        )
        assert res.observation_count == 0
        assert "search" in res.text
        assert res.state_machine is not None and res.state_machine.is_complete

    def test_preventive_oversight_halt(self) -> None:
        tcf = _fabric(_cap("delete_db", "TRANSFORM", safety="destructive", desc="delete the database"))
        ex = CapabilityExecutor()
        ex.register_impl("delete_db", lambda args: "deleted")
        res = run_positioned(
            "convert and wipe the data",
            _tool_model('{"capability_id": "delete_db", "arguments": {}}'),
            fabric=tcf, executor=ex,
            oversight_required={SafetyClass.DESTRUCTIVE},
        )
        assert res.halted
        assert len(res.cso.preventive_halt_history) == 1
        violation = res.cso.preventive_halt_history[0]["problematic_frame"]["violation"]
        assert "requires_oversight" in violation

    def test_policy_blocks_tool_at_selection(self) -> None:
        # A blocked tool is filtered at selection → operation falls back to direct generation.
        tcf = _fabric(_cap("danger", "RETRIEVE", safety="destructive", desc="dangerous"))
        res = run_positioned(
            "find the thing",
            _tool_model('{"capability_id": "danger", "arguments": {}}', text="answered directly"),
            fabric=tcf,
            policy=PolicyContext(blocked_safety_classes={SafetyClass.DESTRUCTIVE}),
        )
        assert not res.halted
        assert res.observation_count == 0

    def test_headers_emitted(self) -> None:
        res = run_positioned("summarise this", _tool_model("", text="summary"))
        assert res.headers["CRP-Agent-Operation-State"] == "COMPLETE"
        assert "CRP-Tool-Observation-Count" in res.headers
        assert res.headers["CRP-Agent-Capability-Profile"] == "frontier"


# ── Context-overflow guard (protocol-level, any provider/model) ─────────────


class TestGuardPromptBudget:
    def test_fits_within_budget_unchanged(self) -> None:
        prompt = "short prompt"
        safe_prompt, max_tokens = guard_prompt_budget(
            prompt, context_window=8192, requested_max_tokens=1024
        )
        assert safe_prompt == prompt
        assert max_tokens == 1024

    def test_caps_max_tokens_for_small_context_window(self) -> None:
        # A tiny context window must never let requested_max_tokens overflow it.
        _, max_tokens = guard_prompt_budget(
            "x" * 40, context_window=512, requested_max_tokens=1024
        )
        assert max_tokens < 1024
        assert max_tokens >= 128  # min_output_tokens floor

    def test_trims_oversized_prompt_preserving_tail(self) -> None:
        # Build a prompt whose EARLY lines are filler and whose LAST line is the
        # actual instruction — the guard must keep the tail and drop the front.
        filler = "\n".join(f"established fact number {i} repeated padding text" for i in range(400))
        prompt = f"{filler}\nACTUAL TASK: do the thing now"
        safe_prompt, max_tokens = guard_prompt_budget(
            prompt, context_window=512, requested_max_tokens=256
        )
        assert "ACTUAL TASK: do the thing now" in safe_prompt
        assert len(safe_prompt) < len(prompt)
        assert max_tokens >= 128

    def test_uses_provider_count_tokens_when_given(self) -> None:
        calls: list[str] = []

        def counter(text: str) -> int:
            calls.append(text)
            return len(text.split())  # word-count tokenizer, distinct from heuristic

        safe_prompt, max_tokens = guard_prompt_budget(
            "one two three four five",
            context_window=100,
            requested_max_tokens=50,
            count_tokens_fn=counter,
        )
        assert calls  # the custom tokenizer was actually invoked
        assert safe_prompt == "one two three four five"
