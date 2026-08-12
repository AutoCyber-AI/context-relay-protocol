# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Transparency Emission Layer (CRP-SPEC-056)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from crp.agent_sdk import Agent
from crp.agent_sdk.events import AgentEvent, AgentEventKind
from crp.providers.custom import CustomProvider
from crp.tel import (
    CRPEmitter,
    Emitter,
    Event,
    EventType,
    SessionBus,
    custom,
    map_agent_event,
    run_finished,
    run_started,
    state_delta,
    step_finished,
    step_started,
    text_delta,
    tool_result,
    tool_start,
)
from crp.tel.faithful import entailment_check, filter_faithful
from crp.tel.report import build_report
from crp.tel.sse import parse_sse, to_sse


class TestEventModel:
    def test_event_to_dict(self) -> None:
        ev = Event(type=EventType.RUN_STARTED, payload={"goal": "test"})
        d = ev.to_dict()
        assert d["type"] == "RUN_STARTED"
        assert d["goal"] == "test"
        assert "seq" in d
        assert "id" in d
        assert "ts" in d

    def test_event_to_sse_round_trip(self) -> None:
        ev = run_started(goal="demo")
        sse = ev.to_sse()
        assert sse.startswith(f"id: {ev.seq}\nevent: RUN_STARTED\ndata: ")
        parsed = parse_sse(sse)
        assert parsed[0]["goal"] == "demo"

    def test_helper_constructors(self) -> None:
        assert step_started(step="scan").type == EventType.STEP_STARTED
        assert text_delta(messageId="m1", delta="hi").payload == {"messageId": "m1", "delta": "hi"}
        ts = tool_start(call_id="c1", name="port_scan", reason="recon")
        assert ts.type == EventType.TOOL_CALL_START
        assert ts.payload["toolCallName"] == "port_scan"


class TestSessionBus:
    def test_sequence_numbers_are_monotonic(self) -> None:
        bus = SessionBus("s1")
        e1 = bus.emit(run_started())
        e2 = bus.emit(step_started(step="x"))
        assert e1.seq == 1
        assert e2.seq == 2

    def test_replay_after_last_event_id(self) -> None:
        bus = SessionBus("s1")
        bus.emit(run_started())
        bus.emit(step_started(step="a"))
        bus.emit(step_finished(step="a"))
        replayed = bus.replay_after(1)
        assert [e.type for e in replayed] == [EventType.STEP_STARTED, EventType.STEP_FINISHED]

    def test_buffer_size_drops_oldest(self) -> None:
        bus = SessionBus("s1", buffer_size=3)
        for _ in range(5):
            bus.emit(run_started())
        assert len(bus.replay_after(-1)) == 3
        assert bus.replay_after(-1)[0].seq == 3

    def test_subscribe_yields_live_events(self) -> None:
        bus = SessionBus("s1")
        emitter = Emitter("s1", bus)
        emitted: list[Event] = []

        def producer() -> None:
            emitter(run_started())
            emitter(step_started(step="p"))
            bus.close()

        import threading

        # Prime the subscription so the queue is registered before events fire.
        stream_iter = bus.subscribe()
        t = threading.Thread(target=producer)
        t.start()
        for ev in stream_iter:
            emitted.append(ev)
        t.join()
        assert EventType.RUN_STARTED in [e.type for e in emitted]
        assert EventType.STEP_STARTED in [e.type for e in emitted]


class TestCRPEmitter:
    def test_governance_events(self) -> None:
        bus = SessionBus("s2")
        emitter = CRPEmitter(Emitter("s2", bus))
        emitter.dpe_stage("scope_check", "LOW", 8, "pass")
        emitter.quality("A", 0.92)
        emitter.provenance("prev", "this", "scan")
        buf = bus.replay_after(-1)
        assert [e.payload.get("name") for e in buf] == ["crp.safety_scan", "crp.quality", "crp.provenance"]


class TestAgentEventMapping:
    def test_intent_classified_maps_to_custom(self) -> None:
        ae = AgentEvent(kind=AgentEventKind.INTENT_CLASSIFIED, operation="RETRIEVE", detail="plan=[RETRIEVE]")
        mapped = map_agent_event(ae)
        assert mapped[0].type == EventType.CUSTOM
        assert mapped[0].payload["name"] == "crp.intent"

    def test_tool_selected_maps_to_tool_start(self) -> None:
        ae = AgentEvent(
            kind=AgentEventKind.TOOL_SELECTED,
            operation="RETRIEVE",
            operation_index=0,
            detail="capability=get_weather",
        )
        mapped = map_agent_event(ae)
        assert any(e.type == EventType.TOOL_CALL_START for e in mapped)
        start = [e for e in mapped if e.type == EventType.TOOL_CALL_START][0]
        assert start.payload["toolCallName"] == "get_weather"

    def test_final_maps_to_run_complete_custom(self) -> None:
        ae = AgentEvent(kind=AgentEventKind.FINAL, detail="run_complete")
        mapped = map_agent_event(ae)
        assert mapped[0].type == EventType.CUSTOM
        assert mapped[0].payload["name"] == "crp.run_complete"

    def test_halt_maps_to_run_error(self) -> None:
        ae = AgentEvent(kind=AgentEventKind.HALT, detail="PREVENTIVE_SAFETY_VIOLATION")
        mapped = map_agent_event(ae)
        assert mapped[0].type == EventType.RUN_ERROR


class TestFaithfulNarration:
    def test_supported_claim_passes(self) -> None:
        trace = [tool_start("t1", "port_scan", "fingerprint"), tool_result("t1", {"open_ports": [22, 80]})]
        assert entailment_check("open ports 22 and 80", trace) is True

    def test_unsupported_claim_fails(self) -> None:
        trace = [tool_start("t1", "port_scan", "fingerprint"), tool_result("t1", {"open_ports": [22]})]
        assert entailment_check("The scan found port 443.", trace) is False

    def test_filter_faithful_withholds_unsupported(self) -> None:
        trace = [tool_result("t1", {"open_ports": [22]})]
        claims = ["open port 22", "open port 443"]
        assert filter_faithful(claims, trace) == ["open port 22"]


class TestReport:
    def test_casual_tier_summary(self) -> None:
        buf = [
            run_started(goal="scan host .20"),
            text_delta(messageId="m", delta="Scanning host .20"),
            tool_start("t1", "port_scan", "fingerprint"),
            custom("crp.safety_scan", {"stage": "scope_check", "risk": "LOW", "verdict": "pass"}),
            run_finished(),
        ]
        report = build_report(buf, tier="casual")
        assert report["tier"] == "casual"
        assert "completed" in report["summary"].lower()
        assert report["narrative"] == "Scanning host .20"
        assert "crp.safety_scan" in report["governance"]

    def test_power_tier_includes_tools_and_state(self) -> None:
        buf = [
            tool_start("t1", "port_scan", "recon"),
            tool_result("t1", {"open_ports": [22]}),
            state_delta([{"op": "add", "path": "/findings/-", "value": {"host": ".20"}}]),
        ]
        report = build_report(buf, tier="power")
        assert report["tools"][0]["name"] == "port_scan"
        assert report["state"]["findings"][0]["host"] == ".20"

    def test_auditor_tier_includes_audit_chain(self) -> None:
        buf = [
            custom("crp.provenance", {"op": "scan", "prev": "0" * 64, "hash": "abc"}),
            run_finished(),
        ]
        report = build_report(buf, tier="auditor")
        assert report["audit_chain"][0]["hash"] == "abc"


class TestAgentRunTel:
    def test_run_tel_emits_lifecycle_events(self) -> None:
        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}

        provider = CustomProvider(
            generate_fn=lambda _msgs: ("The weather in Sydney is sunny.", "stop"),
            count_tokens_fn=lambda t: len(t.split()),
            context_size=4096,
            name="mock",
        )
        agent = Agent(provider=provider, tools=[get_weather])
        events = list(agent.run_tel("What's the weather in Sydney?"))
        types = [e.type for e in events]
        assert EventType.RUN_STARTED in types
        assert EventType.RUN_FINISHED in types or EventType.RUN_ERROR in types
        # Sequence numbers must be monotonic and positive.
        seqs = [e.seq for e in events]
        assert seqs == sorted(seqs)
        assert all(s > 0 for s in seqs)

    def test_run_tel_includes_governance_events(self) -> None:
        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}

        provider = CustomProvider(
            generate_fn=lambda _msgs: ("The weather in Sydney is sunny.", "stop"),
            count_tokens_fn=lambda t: len(t.split()),
            context_size=4096,
            name="mock",
        )
        agent = Agent(provider=provider, tools=[get_weather])
        events = list(agent.run_tel("What's the weather in Sydney?"))
        names = [
            e.payload.get("name")
            for e in events
            if e.type == EventType.CUSTOM
        ]
        assert "crp.quality" in names
        assert "crp.provenance" in names
