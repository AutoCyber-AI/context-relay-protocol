# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Declarative Agent SDK surface (CRP-SPEC-059 §2).

``crp.Agent`` is the steering wheel: declare ``tools + policy + model`` once and
write zero loop code. The Agent builds the Tool Capability Fabric and executes
through the positioned loop, emitting a transparency event stream.
"""

from __future__ import annotations

import hashlib
import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from crp.agent_sdk.events import AgentEvent, AgentEventKind
from crp.agent_sdk.intent_compiler import compile_tools
from crp.agent_sdk.model_call import build_model_call
from crp.agent_sdk.policy import Policy
from crp.agent_sdk.tool_manifest import CompiledTool
from crp.clr import build_clarification, header_value, should_clarify
from crp.clr.response import Interpretation
from crp.isa import (
    CoreferenceResolver,
    IntentClassifier,
    ManagedIntentClassifier,
    build_intent_section,
)
from crp.sdk.response import CRPResponseMeta
from crp.state.cso import CognitiveStateObject
from crp.stl.classifier import classify_operations
from crp.stl.positioned import PositionedResult, run_positioned
from crp.tools.capability_fabric import CapabilityProfile, PolicyContext, ToolCapabilityFabric
from crp.tools.executor import CapabilityExecutor


@dataclass
class AgentResponse:
    """Result of one agent run."""

    text: str = ""
    cso: CognitiveStateObject = field(default_factory=CognitiveStateObject)
    operations: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    halted: bool = False
    observation_count: int = 0
    frame_tokens_total: int = 0
    continuation_windows: int = 0
    events: list[AgentEvent] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    crp: CRPResponseMeta = field(default_factory=CRPResponseMeta)
    verification: dict[str, Any] | None = None
    intent: dict[str, Any] = field(default_factory=dict)

    @property
    def answer(self) -> str:
        """Human-readable answer text."""
        return self.text

    @property
    def sources(self) -> list[dict[str, Any]]:
        """Tool observations surfaced as sources."""
        return [
            obs.to_dict() if hasattr(obs, "to_dict") else dict(obs)
            for obs in self.cso.tool_observations
        ]

    @property
    def decisions(self) -> list[Any]:
        """Decisions recorded in the CSO."""
        return list(self.cso.decisions)

    @property
    def how_it_was_built(self) -> str:
        """Short narrative of the operation sequence."""
        if not self.operations:
            return "direct-generation"
        return " → ".join(self.operations)

    @property
    def open_questions(self) -> list[str]:
        """Open questions carried forward in the CSO."""
        return list(self.cso.open_questions)

    @property
    def complete(self) -> bool:
        """True when the run finished without halting and the plan was integrated."""
        return not self.halted and self.cso.goal_state.completion >= 0.99


class Agent:
    """Declarative agent: ``tools + policy + model`` (SPEC-059 §2).

    Example::

        import crp

        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}

        agent = crp.Agent(model="local/llama3.1", tools=[get_weather])
        result = agent.run("What's the weather in Sydney?")
        print(result.answer)
    """

    def __init__(
        self,
        model: str | Any | None = None,
        provider: Any | None = None,
        tools: list[Any] | None = None,
        policy: Policy | PolicyContext | None = None,
        system: str = "You are a helpful agent.",
        profile: CapabilityProfile | str | None = None,
        depth: str = "auto",
        max_operations: int = 12,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        max_continuation_windows: int = 1,
        safety: str | dict[str, Any] | None = None,
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        """Create an Agent.

        Args:
            model: Model identifier string (e.g. ``"local/llama3.1"``) or ``None``
                if ``provider`` is supplied.
            provider: A CRP ``LLMProvider`` instance. If omitted, ``model`` is
                resolved lazily on first run.
            tools: List of callables, ``ToolSpec`` dicts, or ``CapabilityDescriptor``.
            policy: ``Policy`` or ``PolicyContext`` governing capability selection.
            system: Default system instruction.
            profile: Capability profile (``frontier``, ``capable-local``, ``small-local``).
            depth: Default query depth (``auto``, ``quick``, ``standard``, ``thorough``).
            max_operations: Hard cap on operations per run.
            temperature: Sampling temperature.
            max_tokens: Max tokens per model call.
            max_continuation_windows: Continuation windows for generative ops.
            safety: Safety profile name or override dict.
        """
        self.model = model
        self._provider = provider
        self._tools_sources = tools or []
        self.system = system
        self.depth = depth
        self.max_operations = max_operations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_continuation_windows = max_continuation_windows
        self.safety = safety or "balanced"

        if isinstance(profile, str):
            self.profile = CapabilityProfile(profile)
        elif profile is None:
            self.profile = CapabilityProfile.FRONTIER
        else:
            self.profile = profile

        if isinstance(policy, Policy):
            self.policy = policy.to_policy_context()
            self._policy_obj = policy
        else:
            self.policy = policy or PolicyContext()
            self._policy_obj = Policy()

        self._compiled_tools: list[CompiledTool] = []
        self._fabric: ToolCapabilityFabric | None = None
        self._executor: CapabilityExecutor | None = None
        self._last_cso: CognitiveStateObject | None = None
        self.intent_classifier = intent_classifier or ManagedIntentClassifier()
        self._session_entities: dict[str, str] = {}
        self._turn_history: list[str] = []
        self._turn_index: int = 0

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _ensure_compiled(self) -> list[CompiledTool]:
        """Compile tool sources on first use."""
        if not self._compiled_tools and self._tools_sources:
            self._compiled_tools = compile_tools(self._tools_sources)
        return self._compiled_tools

    def _ensure_fabric_and_executor(self) -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
        """Build the TCF and executor from compiled tools."""
        if self._fabric is None or self._executor is None:
            fabric = ToolCapabilityFabric()
            executor = CapabilityExecutor()
            for compiled in self._ensure_compiled():
                fabric.register(compiled.descriptor)
                if compiled.impl is not None:
                    fn = compiled.impl
                    executor.register_impl(
                        compiled.descriptor.capability_id,
                        lambda args, _fn=fn: _fn(**args),
                    )
            self._fabric = fabric
            self._executor = executor
        return self._fabric, self._executor

    def register_tool(self, tool: Any) -> Agent:
        """Register an additional tool and return ``self`` for chaining."""
        self._tools_sources.append(tool)
        self._compiled_tools = []
        self._fabric = None
        self._executor = None
        return self

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self) -> Any:
        """Return the LLM provider to use for this run."""
        if self._provider is not None:
            return self._provider
        if self.model is None:
            raise RuntimeError("Agent requires a provider or model identifier")
        # Lazy heavy import to keep ``import crp`` fast.
        try:
            from crp.core.orchestrator import _auto_detect_provider

            return _auto_detect_provider(model=self.model)
        except Exception:
            from crp.providers.custom import CustomProvider

            return CustomProvider(
                generate_fn=lambda _msgs: ("", "stop"),
                count_tokens_fn=lambda t: len(t.split()),
                context_size=4096,
                name="agent-fallback",
            )

    # ------------------------------------------------------------------
    # Run execution
    # ------------------------------------------------------------------

    def _build_response(self, result: PositionedResult, events: list[AgentEvent]) -> AgentResponse:
        """Build an ``AgentResponse`` from a positioned result."""
        cso = result.cso
        meta = CRPResponseMeta(
            risk="LOW" if not result.halted else "CRITICAL",
            grounded=not result.halted,
            fabrications=0,
            chain_valid=True,
            session_id=getattr(cso, "cso_id", ""),
        )
        return AgentResponse(
            text=result.text,
            cso=cso,
            operations=result.operations,
            headers=result.headers,
            halted=result.halted,
            observation_count=result.observation_count,
            frame_tokens_total=result.frame_tokens_total,
            continuation_windows=result.continuation_windows,
            events=events,
            crp=meta,
        )

    def _map_operation_event(self, op_event: dict[str, Any]) -> AgentEvent:
        """Map an OperationStateMachine event dict to an ``AgentEvent``."""
        state = op_event.get("state", "")
        kind_map = {
            "INTENT_CLASSIFIED": AgentEventKind.INTENT_CLASSIFIED,
            "OPERATION_POSITIONED": AgentEventKind.OPERATION_POSITIONED,
            "TOOL_SELECTED": AgentEventKind.TOOL_SELECTED,
            "TOOL_EXECUTED": AgentEventKind.TOOL_CALLED,
            "OPERATION_VERIFIED": AgentEventKind.OPERATION_VERIFIED,
            "INTEGRATED": AgentEventKind.INTEGRATED,
            "COMPLETE": AgentEventKind.FINAL,
            "HALTED": AgentEventKind.HALT,
        }
        kind = kind_map.get(state, AgentEventKind.FINAL)
        return AgentEvent(
            kind=kind,
            operation=op_event.get("operation"),
            operation_index=op_event.get("operation_index", 0),
            detail=op_event.get("detail", ""),
            data=op_event,
        )

    def _generate_clarification_candidates(
        self, resolved_turn: str, intent_section: dict[str, Any]
    ) -> list[Interpretation]:
        """Build candidate interpretations for the clarification protocol (SPEC-053)."""
        primary_ops = [op.value for op in classify_operations(resolved_turn)]
        speech_act = intent_section.get("speech_act", "request")
        primary = Interpretation(
            reading=f"As a {speech_act}: '{resolved_turn}'",
            operations=primary_ops or ["GENERATE"],
            probability=0.6,
        )
        # A contrasting reading: if the user was asking a question, frame as a request.
        if speech_act == "question":
            alt_ops = [op.value for op in classify_operations("Please answer: " + resolved_turn)]
            secondary = Interpretation(
                reading=f"As a request for action: '{resolved_turn}'",
                operations=alt_ops or ["RETRIEVE", "GENERATE"],
                probability=0.4,
            )
        else:
            secondary = Interpretation(
                reading=f"As a question seeking information: '{resolved_turn}'",
                operations=["RETRIEVE"],
                probability=0.4,
            )
        return [primary, secondary]

    def _maybe_clarify(
        self,
        raw_turn: str,
        resolved_turn: str,
        intent_section: dict[str, Any],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> AgentResponse | None:
        """Return a clarification response if ambiguity warrants asking (SPEC-053)."""
        confidence = float(intent_section.get("intent_confidence", 0.5))
        candidates = self._generate_clarification_candidates(resolved_turn, intent_section)
        probs = [c.probability for c in candidates]
        parse_divergence = 1.0 - max(probs) if len(probs) > 1 else 0.0
        risk = "HIGH" if self._policy_obj.profile_name == "strict" else "LOW"
        if not should_clarify(confidence, parse_divergence, risk, self._policy_obj):
            return None

        clarification = build_clarification(candidates, reason="ambiguous-target")
        meta = CRPResponseMeta(
            risk="MEDIUM",
            grounded=False,
            fabrications=0,
            chain_valid=True,
            session_id="",
        )
        response = AgentResponse(
            text=clarification.to_dict().__str__(),
            halted=True,
            crp=meta,
            intent=intent_section,
            headers={"X-CRP-Clarification": header_value(clarification)},
        )
        final_event = AgentEvent(
            kind=AgentEventKind.HALT,
            detail="CRP-Clarification-Required",
            data={
                "kind": "CRP-Clarification-Required",
                "reason": clarification.reason,
                "interpretations": [c.to_dict() for c in clarification.interpretations],
            },
        )
        response.events.append(final_event)
        if event_callback is not None:
            event_callback(final_event)
        return response

    def _run(
        self,
        user_request: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
        prior_cso: CognitiveStateObject | None = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """Internal synchronous run with optional event callback."""
        resolve_coref = kwargs.pop("resolve_coreferences", True)

        # SPEC-052 — intent + speech-act positioning, cross-session coreference.
        history = self._turn_history[-6:]
        tag = self.intent_classifier.classify(user_request, history)
        resolved = user_request
        if resolve_coref:
            resolver = CoreferenceResolver()
            resolved = resolver.resolve(user_request, self._session_entities)
        intent_section = build_intent_section(user_request, tag, resolved)

        self._turn_history.append(user_request)
        self._session_entities[f"turn_{self._turn_index}"] = resolved
        self._turn_index += 1

        # SPEC-053 — ask rather than guess when ambiguous.
        clarification_response = self._maybe_clarify(
            user_request, resolved, intent_section, event_callback
        )
        if clarification_response is not None:
            return clarification_response

        provider = self._resolve_provider()
        model_call = build_model_call(provider, temperature=self.temperature, max_tokens=self.max_tokens)
        fabric, executor = self._ensure_fabric_and_executor()

        events: list[AgentEvent] = []

        def _op_event_callback(op_event: dict[str, Any]) -> None:
            event = self._map_operation_event(op_event)
            events.append(event)
            if event_callback is not None:
                event_callback(event)

        result = run_positioned(
            resolved,
            model_call,
            fabric=fabric,
            executor=executor,
            profile=self.profile,
            policy=self.policy,
            context_facts=None,
            max_operations=self.max_operations,
            governor=None,
            clarify_handler=None,
            hmac_key=None,
            prior_cso=prior_cso,
            max_continuation_windows=self.max_continuation_windows,
            event_callback=_op_event_callback,
        )

        self._last_cso = result.cso
        response = self._build_response(result, events)
        response.intent = intent_section
        final_kind = AgentEventKind.HALT if result.halted else AgentEventKind.FINAL
        final_event = AgentEvent(
            kind=final_kind,
            detail="run_complete" if not result.halted else result.headers.get("CRP-Agent-Halt-Reason", "halted"),
            data={"halted": result.halted, "operations": result.operations},
        )
        events.append(final_event)
        if event_callback is not None:
            event_callback(final_event)
        return response

    def run(self, user_request: str, **kwargs: Any) -> AgentResponse:
        """Run the agent on ``user_request`` and return the full response."""
        prior_cso = kwargs.pop("prior_cso", self._last_cso)
        verify = kwargs.pop("verify", None)

        response = self._run(user_request, prior_cso=prior_cso, **kwargs)

        # SPEC-049 — Verification Relay (depth-gated; override with verify=...)
        run_vr = verify if verify is not None else self.depth in {"thorough", "exhaustive"}
        if run_vr and not response.halted:
            from crp.vr.extract import verify_text

            depth = self.depth if self.depth != "auto" else "standard"
            try:
                response.verification = verify_text(response.answer, depth=depth)
                if response.verification.get("invalid", 0) > 0:
                    response.crp.risk = "HIGH"
            except Exception as exc:  # pragma: no cover - defensive
                logging.getLogger(__name__).debug("Agent VR failed (non-blocking): %s", exc)

        return response

    def ask(self, question: str, **kwargs: Any) -> AgentResponse:
        """Alias for :meth:`run` optimized for question-answering."""
        return self.run(question, **kwargs)

    def run_stream(self, user_request: str, **kwargs: Any) -> Iterator[AgentEvent]:
        """Run the agent and yield each transparency event as it occurs.

        The model calls run in a background thread so events can be consumed
        incrementally.
        """
        prior_cso = kwargs.pop("prior_cso", self._last_cso)
        q: queue.SimpleQueue[Any] = queue.SimpleQueue()
        result_container: list[AgentResponse] = []

        def callback(event: AgentEvent) -> None:
            q.put(event)

        def target() -> None:
            try:
                response = self._run(
                    user_request,
                    event_callback=callback,
                    prior_cso=prior_cso,
                    **kwargs,
                )
                result_container.append(response)
            except Exception as exc:  # noqa: BLE001
                q.put(exc)
            finally:
                q.put(None)  # sentinel

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        while True:
            item = q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                thread.join()
                raise item
            yield item

        thread.join()
        if result_container:
            self._last_cso = result_container[0].cso

    def run_tel(self, user_request: str, **kwargs: Any) -> Iterator[Any]:
        """Run the agent and yield AG-UI-compatible transparency events.

        This is the public transparency stream consumed by frontends, CLIs, and
        audit consumers. It wraps :meth:`_run` in a background thread, maps
        internal :class:`AgentEvent` objects to AG-UI events, and adds CRP
        governance events (quality, provenance, state snapshot).
        """
        from crp.tel import CRPEmitter, Emitter, EventType, SessionBus, map_agent_event
        from crp.tel import events as tel_events

        prior_cso = kwargs.pop("prior_cso", self._last_cso)
        session_id = kwargs.pop("session_id", None) or f"agent-{uuid.uuid4().hex[:8]}"
        bus = SessionBus(session_id)
        emitter = Emitter(session_id, bus)
        crp_emitter = CRPEmitter(emitter)
        result_container: list[AgentResponse] = []
        error_container: list[BaseException] = []
        sentinel_q: queue.SimpleQueue[Any] = queue.SimpleQueue()

        def _agent_callback(agent_event: AgentEvent) -> None:
            for tel_event in map_agent_event(agent_event):
                emitter(tel_event)

        def target() -> None:
            try:
                crp_emitter.run_started(goal=user_request)
                response = self._run(
                    user_request,
                    event_callback=_agent_callback,
                    prior_cso=prior_cso,
                    **kwargs,
                )
                result_container.append(response)
                cso = response.cso
                emitter(tel_events.state_snapshot(snapshot=cso.to_dict()))
                crp_emitter.quality(
                    tier="A" if not response.halted else "D",
                    confidence=0.91 if not response.halted else 0.3,
                )
                # Provenance link into the real HMAC window chain (SPEC-011 §2.3).
                # The chain tip persists on the agent so consecutive runs form
                # a verifiable, tamper-evident sequence.
                from crp.provenance.window_chain import WindowHmacInput, build_window_hmac

                prev_tip = getattr(self, "_tel_chain_tip", "")
                response_hash = hashlib.sha256((response.text or "").encode("utf-8")).hexdigest()
                key = hashlib.sha256(session_id.encode("utf-8")).digest()
                chain_input = WindowHmacInput(
                    session_id=session_id,
                    window_number=len(bus._buffer),
                    timestamp=f"{time.time():.6f}",
                    response_hash=response_hash,
                    prev_window_hmac=prev_tip,
                )
                this_hash = build_window_hmac(chain_input, key)
                self._tel_chain_tip = this_hash
                self._tel_chain_input = chain_input  # retained for audit verification
                crp_emitter.provenance(
                    prev_hash=prev_tip or "genesis", this_hash=this_hash, op="agent_run"
                )
                crp_emitter.run_finished()
            except Exception as exc:  # noqa: BLE001
                error_container.append(exc)
                crp_emitter.run_error(error=str(exc))
            finally:
                sentinel_q.put(None)
                bus.close()

        # Start the subscription *before* the producer thread so the first
        # events (RUN_STARTED) are captured rather than raced.
        stream_iter = bus.subscribe()
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        try:
            for ev in stream_iter:
                yield ev
                if ev.type in {EventType.RUN_FINISHED, EventType.RUN_ERROR}:
                    break
        finally:
            bus.close()
            thread.join()
            if error_container:
                raise error_container[0]
            if result_container:
                self._last_cso = result_container[0].cso
