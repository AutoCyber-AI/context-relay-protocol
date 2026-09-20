# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Declarative Agent SDK surface (CRP-SPEC-059 §2).

``crp.Agent`` is the steering wheel: declare ``tools + policy + model`` once and
write zero loop code. The Agent builds the Tool Capability Fabric and executes
through the positioned loop, emitting a transparency event stream.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from crp.agent.autonomy import AutonomyGovernor, AutonomyMetrics
from crp.agent_sdk.events import AgentEvent, AgentEventKind
from crp.agent_sdk.intent_compiler import compile_tools
from crp.agent_sdk.model_call import build_model_call
from crp.agent_sdk.policy import Policy
from crp.agent_sdk.tool_manifest import CompiledTool
from crp.clr import build_clarification, header_value, should_clarify
from crp.clr.response import Interpretation
from crp.cognition import PresetCompiler
from crp.cognition.loader import resolve_preset_id
from crp.cognition.preset import CognitivePreset
from crp.isa import (
    CoreferenceResolver,
    IntentClassifier,
    ManagedIntentClassifier,
    build_intent_section,
)
from crp.sdk.response import CRPResponseMeta
from crp.security.checkpoint import Checkpoint, CheckpointResolutionAction
from crp.security.clarify import ClarificationHandler
from crp.security.control_plane import SafetyControlPlane, get_default_control_plane
from crp.security.kill_switch import KillSwitch
from crp.security.trust_monitor import TrustActions, TrustDecision, TrustMonitor
from crp.state.cso import CognitiveStateObject
from crp.stl.classifier import classify_operations
from crp.stl.positioned import PositionedResult, run_positioned
from crp.tools.capability_fabric import CapabilityProfile, PolicyContext, ToolCapabilityFabric
from crp.tools.descriptor import SafetyClass
from crp.tools.executor import CapabilityExecutor

logger = logging.getLogger(__name__)


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
        oversight_required: set[SafetyClass] | None = None,
        clarify_handler: ClarificationHandler | None = None,
        checkpoint: Checkpoint | None = None,
        trust_monitor: TrustMonitor | None = None,
        kill_switch: KillSwitch | None = None,
        control_plane: SafetyControlPlane | None = None,
        autonomy_metrics: AutonomyMetrics | None = None,
        preset: str | CognitivePreset | dict[str, Any] | None = None,
    ) -> None:
        """Create an Agent.

        Args:
            model: Model identifier string (e.g. ``"local/llama3.1"``) or ``None``
                if ``provider`` is supplied.
            provider: A CRP ``LLMProvider`` instance. If omitted, ``model`` is
                resolved lazily on first run.
            tools: List of callables, ``ToolSpec`` dicts, or ``CapabilityDescriptor``.
                A dict may include an ``"impl"`` callable alongside a
                ``cost_profile={"safety_class": "destructive"}`` entry to attach
                both a real implementation and a non-default safety class.
            policy: ``Policy`` or ``PolicyContext`` governing capability selection.
            system: Default system instruction.  If ``preset`` is provided, the
                preset's system prompt is appended to this value.
            profile: Capability profile (``frontier``, ``capable-local``, ``small-local``).
            depth: Default query depth (``auto``, ``quick``, ``standard``, ``thorough``).
            max_operations: Hard cap on operations per run.
            temperature: Sampling temperature.
            max_tokens: Max tokens per model call.
            max_continuation_windows: Continuation windows for generative ops.
            safety: Safety profile name or override dict.
            oversight_required: Safety classes (e.g. ``{SafetyClass.DESTRUCTIVE}``)
                that must be approved via ``clarify_handler`` before executing —
                gates the individual tool call at execution time, not just the
                plan (CRP-SPEC-033/034).
            clarify_handler: Resolves oversight/clarification requests. If a
                gated capability is selected and no handler (or a non-approving
                one) is supplied, the run halts rather than executing it —
                fail-safe default deny.
            checkpoint: Optional async human-in-the-loop checkpoint. If provided,
                DESTRUCTIVE tool selections wait for checkpoint resolution instead
                of the synchronous clarify_handler.
            trust_monitor: Optional runtime trust monitor. If omitted, one is
                created automatically and observes user input, tool calls, and output.
            kill_switch: Optional emergency kill switch. If omitted, one is created
                automatically and is fired when trust collapses.
            control_plane: Optional SafetyControlPlane. If omitted, a default plane
                is created and tuned by the ``safety`` profile.
            autonomy_metrics: Optional measured evidence for autonomy tier assignment.
            preset: A cognitive preset — a built-in id (e.g. ``"socratic_tutor"``),
                a path to a YAML/JSON file, a dict, or a :class:`CognitivePreset`.
                The preset defines the agent's persona, reasoning scaffold,
                safeguards, emotions, and output profile.
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
        self.oversight_required = oversight_required or set()
        self.clarify_handler = clarify_handler
        self.checkpoint = checkpoint
        self._preset: CognitivePreset | None = None
        self._compiled_preset: Any | None = None

        # Safety surface wiring (SPEC-033).
        self._session_id = f"agent-{uuid.uuid4().hex[:8]}"
        self._kill_switch = kill_switch or KillSwitch()
        self._trust_monitor = trust_monitor or TrustMonitor(
            session_id=self._session_id,
            kill_switch=self._kill_switch,
        )
        self._control_plane = control_plane or self._build_control_plane(self.safety)
        self._autonomy_governor = AutonomyGovernor()
        self._autonomy_metrics = autonomy_metrics or AutonomyMetrics()

        if preset is not None:
            loaded = self._resolve_preset(preset)
            self._apply_preset(loaded)

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
    # Preset handling (CRP-SPEC-046)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_preset(preset: str | CognitivePreset | dict[str, Any]) -> CognitivePreset:
        """Resolve a preset argument into a CognitivePreset."""
        if isinstance(preset, CognitivePreset):
            return preset
        if isinstance(preset, dict):
            return CognitivePreset.from_dict(preset)
        return resolve_preset_id(preset)

    def _apply_preset(self, preset: CognitivePreset) -> None:
        """Apply a compiled preset to this agent's configuration."""
        self._preset = preset
        compiled = PresetCompiler(preset).compile()
        self._compiled_preset = compiled

        # Enrich the system prompt with persona, reasoning, safeguards, output profile.
        if compiled.system:
            self.system = f"{self.system}\n\n{compiled.system}".strip()

        # Preset depth only overrides the default when the user did not supply one.
        if self.depth == "auto" and compiled.depth != "auto":
            self.depth = compiled.depth

        # Merge safeguard-driven oversight requirements.
        if compiled.safety_classes:
            self.oversight_required = set(self.oversight_required) | compiled.safety_classes

    @classmethod
    def presets(cls) -> list[dict[str, str]]:
        """Return metadata for all built-in cognitive presets."""
        from crp.cognition.loader import list_builtin_presets

        return list_builtin_presets()

    # ------------------------------------------------------------------
    # Safety surface helpers (SPEC-033)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_control_plane(safety: str | dict[str, Any] | None) -> SafetyControlPlane:
        """Create and tune a SafetyControlPlane from a safety profile name."""
        scp = get_default_control_plane()
        if isinstance(safety, str):
            profile = safety.lower()
            if profile == "strict":
                scp.tune("grounding_verification", 0.90)
                scp.tune("prompt_injection_shield", True)
                scp.tune("pii_detection", "block")
                scp.tune("human_oversight", "automatic")
            elif profile == "balanced":
                scp.tune("grounding_verification", 0.70)
                scp.tune("prompt_injection_shield", True)
                scp.tune("pii_detection", "flag")
                scp.tune("human_oversight", "manual")
            elif profile == "permissive":
                scp.tune("grounding_verification", 0.50)
                scp.tune("prompt_injection_shield", False)
                scp.tune("pii_detection", "flag")
                scp.tune("human_oversight", "manual")
        elif isinstance(safety, dict):
            for key, value in safety.items():
                scp.tune(key, value)
        return scp

    def _check_trust(
        self,
        observation: dict[str, Any],
        events: list[AgentEvent],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> TrustDecision | None:
        """Observe an event through the trust monitor and emit a trust event."""
        decision = self._trust_monitor.observe(observation)
        trust_event = AgentEvent(
            kind=AgentEventKind.TRUST_DECISION,
            detail=decision.action,
            data=decision.to_dict(),
        )
        events.append(trust_event)
        if event_callback is not None:
            event_callback(trust_event)
        return decision

    def _halt_for_trust(
        self,
        decision: Any,
        events: list[AgentEvent],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> AgentResponse:
        """Build a halted response because trust collapsed."""
        if not self._kill_switch.is_fired:
            self._kill_switch.fire(
                session_id=self._session_id,
                reason="trust_threshold_crossed",
                triggered_by="crp.agent_sdk.agent",
                snapshot=decision.to_dict(),
            )
        kill_event = AgentEvent(
            kind=AgentEventKind.KILL_SWITCH_FIRED,
            detail=decision.action,
            data={"trust_score": decision.trust_score, "reason": decision.reason},
        )
        events.append(kill_event)
        if event_callback is not None:
            event_callback(kill_event)
        meta = CRPResponseMeta(
            risk="CRITICAL",
            grounded=False,
            fabrications=0,
            chain_valid=True,
            session_id=self._session_id,
            trust_score=decision.trust_score,
            kill_switch_fired=True,
        )
        return AgentResponse(
            text=f"Run halted by safety surface ({decision.action}): {decision.reason}",
            halted=True,
            crp=meta,
            headers={"CRP-Agent-Halt-Reason": f"TRUST_{decision.action.upper()}"},
        )

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
                    sig = inspect.signature(fn)
                    boundable = {
                        p.name
                        for p in sig.parameters.values()
                        if p.kind
                        in (
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            inspect.Parameter.KEYWORD_ONLY,
                        )
                    }
                    has_var_kw = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD
                        for p in sig.parameters.values()
                    )

                    def _wrapped(
                        args: dict[str, Any],
                        _fn: Any = fn,
                        _boundable: set[str] = boundable,
                        _has_var_kw: bool = has_var_kw,
                    ) -> Any:
                        # Only pass arguments the function actually accepts.
                        # This prevents small models from hallucinating extra
                        # parameters for parameterless tools (e.g. get_time()).
                        if _has_var_kw:
                            return _fn(**args)
                        filtered = {k: v for k, v in args.items() if k in _boundable}
                        return _fn(**filtered)

                    executor.register_impl(
                        compiled.descriptor.capability_id,
                        _wrapped,
                    )

            # If a preset declares an explicit tool allowlist, restrict the fabric.
            if self._compiled_preset is not None and self._compiled_preset.tool_ids:
                allowed_ids = set(self._compiled_preset.tool_ids)
                filtered_fabric = ToolCapabilityFabric()
                filtered_executor = CapabilityExecutor()
                for desc in fabric.all():
                    if desc.capability_id in allowed_ids:
                        filtered_fabric.register(desc)
                        impl = executor.get_impl(desc.capability_id)
                        if impl is not None:
                            filtered_executor.register_impl(desc.capability_id, impl)
                fabric = filtered_fabric
                executor = filtered_executor

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
    # Safeguard helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _halt_message(results: list[Any], scope: str) -> str:
        """Build a graceful, human-readable halt message from safeguard results."""
        reasons = "; ".join(f"{r.rule} ({r.matched})" for r in results)
        return f"Request halted by preset safeguard ({scope}): {reasons}."

    @staticmethod
    def _ask_message(results: list[Any], scope: str, preset_name: str = "") -> str:
        """Build a graceful ask-back message from safeguard results.

        The message is phrased as a pause/request for clarification rather than
        a permanent refusal.  Invariant 10: checkpoints never leave the user with
        a raw error.
        """
        reasons = "; ".join(f"{r.rule}" for r in results)
        prefix = f"[{preset_name}] " if preset_name else ""
        return (
            f"{prefix}This request triggered a safeguard ({scope}): {reasons}. "
            "I want to make sure I help you the right way. Could you tell me more "
            "about what you need?"
        )

    def _emit_warning_event(
        self,
        results: list[Any],
        scope: str,
        events: list[AgentEvent],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> None:
        """Emit a warning event for triggered advisory safeguards and continue."""
        data = {
            "scope": scope,
            "rules": [r.to_dict() for r in results],
        }
        event = AgentEvent(
            kind=AgentEventKind.WARNING,
            detail=f"preset_safeguard_{scope}",
            data=data,
        )
        events.append(event)
        if event_callback is not None:
            event_callback(event)

    def _handle_preset_safeguards(
        self,
        results: list[Any],
        scope: str,
        user_request: str,
        events: list[AgentEvent],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> AgentResponse | None:
        """Handle triggered preset safeguards: halt, ask, or warn.

        Returns a response only when the action requires stopping/asking.
        Returns ``None`` for warnings so the caller can continue the run.
        """
        halt_results = [r for r in results if r.action == "halt"]
        if halt_results:
            halt_reason = "; ".join(f"{r.rule} ({r.matched})" for r in halt_results)
            meta = CRPResponseMeta(
                risk="CRITICAL",
                grounded=False,
                fabrications=0,
                chain_valid=True,
                session_id="",
            )
            response = AgentResponse(
                text=self._halt_message(halt_results, scope),
                halted=True,
                crp=meta,
                headers={"CRP-Agent-Halt-Reason": "PRESET_SAFEGUARD_VIOLATION"},
            )
            halt_event = AgentEvent(
                kind=AgentEventKind.HALT,
                detail="PRESET_SAFEGUARD_VIOLATION",
                data={"halted": True, "reason": halt_reason, "scope": scope},
            )
            response.events.append(halt_event)
            if event_callback is not None:
                event_callback(halt_event)
            return response

        ask_results = [r for r in results if r.action == "ask"]
        if ask_results:
            preset_name = self._preset.name if self._preset else ""
            ask_text = self._ask_message(ask_results, scope, preset_name)
            # If emotions are enabled, append the trigger instruction for the
            # matched affect so the response is compassionate/appropriate.
            emotion: dict[str, Any] | None = None
            if (
                self._compiled_preset is not None
                and self._compiled_preset.emotion_detector is not None
                and self._preset is not None
                and self._preset.emotions.enabled
            ):
                emotion = self._compiled_preset.emotion_detector(user_request)
                scores = emotion.get("scores", {}) if emotion else {}
                # Use the first detected affect that has a configured trigger.
                for affect in scores:
                    trigger = self._preset.emotions.triggers.get(affect, "")
                    if trigger:
                        ask_text = f"{ask_text}\n\n{trigger}"
                        break
            meta = CRPResponseMeta(
                risk="MEDIUM",
                grounded=False,
                fabrications=0,
                chain_valid=True,
                session_id="",
            )
            response = AgentResponse(
                text=ask_text,
                halted=True,
                crp=meta,
                headers={"CRP-Agent-Halt-Reason": "PRESET_SAFEGUARD_ASK", "X-CRP-Clarification": "required"},
            )
            ask_event = AgentEvent(
                kind=AgentEventKind.HALT,
                detail="PRESET_SAFEGUARD_ASK",
                data={
                    "halted": True,
                    "rules": [r.to_dict() for r in ask_results],
                    "scope": scope,
                    "emotion": emotion,
                },
            )
            response.events.append(ask_event)
            if event_callback is not None:
                event_callback(ask_event)
            return response

        warn_results = [r for r in results if r.action == "warn"]
        if warn_results:
            self._emit_warning_event(warn_results, scope, events, event_callback)

        return None

    def _resolve_clarify_handler(
        self,
        events: list[AgentEvent],
        event_callback: Callable[[AgentEvent], None] | None,
    ) -> ClarificationHandler | None:
        """Return the active clarification handler, bridging an async Checkpoint if provided.

        If the user supplied a ``Checkpoint`` instance, convert it into the
        synchronous ``ClarificationHandler`` interface that ``run_positioned``
        expects. The checkpoint is created externally, resolved by a reviewer or
        webhook, and applies graceful fallback on timeout/reject (Invariant 10).
        """
        if self.checkpoint is None:
            return self.clarify_handler
        if self.clarify_handler is not None:
            return self.clarify_handler

        checkpoint = self.checkpoint
        assert checkpoint is not None  # guarded by the outer condition

        def _notify_checkpoint_connectors(request: Any) -> None:
            """Fire-and-forget notification to configured review channels."""
            try:
                from crp_mcp.connectors import get_configured_connectors

                async def _notify() -> None:
                    connectors = get_configured_connectors()
                    payload = {
                        "checkpoint_id": request.request_id,
                        "trigger": "OVERSIGHT_REQUIRED",
                        "message": request.question,
                        "status": "waiting_for_human",
                        "context": request.to_dict(),
                    }
                    for connector in connectors:
                        try:
                            await connector.notify(payload)
                        except Exception as exc:  # noqa: BLE001
                            logger.debug(
                                "Checkpoint connector %s failed: %s",
                                getattr(connector, "name", "unknown"),
                                exc,
                            )

                # Run in a fresh event loop; checkpoints are rare so the overhead
                # is acceptable and it never blocks the agent loop.
                asyncio.run(_notify())
            except Exception as exc:  # noqa: BLE001
                logger.debug("Checkpoint connector notification failed: %s", exc)

        def _checkpoint_handler(request: Any) -> Any:
            from crp.security.clarify import (
                ClarificationAction,
                ClarificationResolution,
            )

            checkpoint_event = AgentEvent(
                kind=AgentEventKind.CHECKPOINT_REQUESTED,
                detail=request.request_id,
                data={"request": request.to_dict()},
            )
            events.append(checkpoint_event)
            _notify_checkpoint_connectors(request)
            if event_callback is not None:
                event_callback(checkpoint_event)
            resolution = asyncio.run(checkpoint.wait_for_resolution())
            resolved_event = AgentEvent(
                kind=AgentEventKind.CHECKPOINT_RESOLVED,
                detail=resolution.action.value,
                data={"request_id": request.request_id, "reviewer": resolution.reviewer},
            )
            events.append(resolved_event)
            if event_callback is not None:
                event_callback(resolved_event)
            if resolution.action == CheckpointResolutionAction.APPROVE:
                return ClarificationResolution(
                    ClarificationAction.ANSWER,
                    answer="approve",
                    reviewer=resolution.reviewer,
                )
            return ClarificationResolution(
                ClarificationAction.ABORT,
                answer="denied",
                reviewer=resolution.reviewer,
            )

        return _checkpoint_handler

    # ------------------------------------------------------------------
    # Run execution
    # ------------------------------------------------------------------

    def _build_response(self, result: PositionedResult, events: list[AgentEvent]) -> AgentResponse:
        """Build an ``AgentResponse`` from a positioned result."""
        cso = result.cso
        autonomy_decision = self._autonomy_governor.enforce(
            self._autonomy_metrics,
            "tool" if result.observation_count > 0 else "read",
            kill_switch=self._kill_switch,
        )
        meta = CRPResponseMeta(
            risk="LOW" if not result.halted else "CRITICAL",
            grounded=not result.halted,
            fabrications=0,
            chain_valid=True,
            session_id=self._session_id,
            trust_score=self._trust_monitor.trust_score,
            kill_switch_fired=self._kill_switch.is_fired,
            autonomy_tier=autonomy_decision.tier.value,
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
        """Map a positioned-loop event dict to an ``AgentEvent``.

        Two distinct shapes flow through this callback: ``OperationStateMachine``
        transitions (keyed by ``state``) and the tool-observation notification
        fired directly by ``run_positioned`` (keyed by ``event_type``). Routing
        both through the same ``state``-only lookup silently mis-mapped
        observations to a spurious extra ``FINAL``/``crp.run_complete`` event
        instead of a proper ``TOOL_CALL_RESULT`` — fixed by branching on shape.
        """
        if op_event.get("event_type") == "observation_received":
            return AgentEvent(
                kind=AgentEventKind.OBSERVATION_RECEIVED,
                operation=op_event.get("operation"),
                operation_index=op_event.get("operation_index", 0),
                detail=str(op_event.get("capability_id", "")),
                data=op_event,
            )
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
            "GOVERNANCE": AgentEventKind.GOVERNANCE,
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
        events: list[AgentEvent] = []

        # Preset input safeguard check (SPEC-046 §2.4).
        if (
            self._compiled_preset is not None
            and self._compiled_preset.safeguard_engine is not None
        ):
            input_results = self._compiled_preset.safeguard_engine.evaluate(
                user_input=user_request
            )
            if input_results:
                handled = self._handle_preset_safeguards(
                    input_results,
                    "input",
                    user_request,
                    events,
                    event_callback,
                )
                if handled is not None:
                    return handled

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

        # Observe user input through the trust monitor (SPEC-033 §3.5).
        input_trust = self._check_trust(
            {"input": resolved, "action": "user_request"},
            events,
            event_callback,
        )
        if input_trust and input_trust.action == TrustActions.KILL:
            return self._halt_for_trust(input_trust, events, event_callback)
        if input_trust and input_trust.action == TrustActions.GATE:
            if self.clarify_handler is None and self.checkpoint is None:
                return self._halt_for_trust(input_trust, events, event_callback)
            # Otherwise continue but mark as gated; destructive actions will still
            # hit clarify_handler/checkpoint below.

        provider = self._resolve_provider()
        model_call = build_model_call(provider, temperature=self.temperature, max_tokens=self.max_tokens)
        fabric, executor = self._ensure_fabric_and_executor()

        trust_kill_decision: Any | None = None

        def _op_event_callback(op_event: dict[str, Any]) -> None:
            nonlocal trust_kill_decision
            # The state machine's own COMPLETE event is superseded by the
            # explicit run-level final event appended below (which carries
            # the full operations list and the correct halted/halt-reason
            # detail) — skip it here so the stream doesn't show two
            # near-duplicate "run complete" events for a single run.
            if op_event.get("state") == "COMPLETE":
                return
            event = self._map_operation_event(op_event)
            events.append(event)
            if event_callback is not None:
                event_callback(event)
            # Observe tool calls through the trust monitor.
            if event.kind == AgentEventKind.TOOL_CALLED and not trust_kill_decision:
                decision = self._check_trust(
                    {
                        "tool": op_event.get("capability_id", ""),
                        "arguments": str(op_event.get("arguments", {})),
                        "action": "tool_call",
                    },
                    events,
                    event_callback,
                )
                if decision and decision.action == TrustActions.KILL:
                    trust_kill_decision = decision

        clarify_handler = self._resolve_clarify_handler(events, event_callback)
        result = run_positioned(
            resolved,
            model_call,
            fabric=fabric,
            executor=executor,
            profile=self.profile,
            policy=self.policy,
            context_facts=None,
            max_operations=self.max_operations,
            oversight_required=self.oversight_required or None,
            governor=None,
            clarify_handler=clarify_handler,
            hmac_key=None,
            prior_cso=prior_cso,
            max_continuation_windows=self.max_continuation_windows,
            event_callback=_op_event_callback,
            phase_plan=(
                self._compiled_preset.phase_plan.copy() if self._compiled_preset and self._compiled_preset.phase_plan else None
            ),
            final_synthesis=True,
            safeguard_engine=(
                self._compiled_preset.safeguard_engine if self._compiled_preset else None
            ),
        )

        # If trust monitor ordered a kill during the positioned loop, halt now.
        if trust_kill_decision and not result.halted:
            return self._halt_for_trust(trust_kill_decision, events, event_callback)

        # Preset safeguard check on the generated output.
        if (
            not result.halted
            and self._compiled_preset is not None
            and self._compiled_preset.safeguard_engine is not None
            and result.text
        ):
            output_results = self._compiled_preset.safeguard_engine.evaluate(
                user_input=user_request,
                output=result.text,
            )
            if output_results:
                handled = self._handle_preset_safeguards(
                    output_results,
                    "output",
                    user_request,
                    events,
                    event_callback,
                )
                if handled is not None:
                    return handled

        # Observe final output through the trust monitor.
        if not result.halted and result.text:
            output_trust = self._check_trust(
                {"output": result.text, "action": "generate"},
                events,
                event_callback,
            )
            if output_trust and output_trust.action == TrustActions.KILL:
                return self._halt_for_trust(output_trust, events, event_callback)

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

        # Emit a governance summary so transparency streams show the same
        # risk, grounding, provenance, and source count that the response object carries.
        autonomy_decision = self._autonomy_governor.enforce(
            self._autonomy_metrics,
            "tool" if result.observation_count > 0 else "read",
            kill_switch=self._kill_switch,
        )
        governance_event = AgentEvent(
            kind=AgentEventKind.GOVERNANCE,
            detail="governance_summary",
            data={
                "risk": response.crp.risk,
                "grounded": response.crp.grounded,
                "chain_valid": response.crp.chain_valid,
                "fabrications": response.crp.fabrications,
                "sources": len(response.sources),
                "tier": getattr(response.crp, "tier", ""),
                "confidence": getattr(response.crp, "confidence", 0.0),
                "semantic_entropy": getattr(response.crp, "semantic_entropy", None),
                "observation_count": response.observation_count,
                "halted": response.halted,
                "trust_score": self._trust_monitor.trust_score,
                "kill_switch_fired": self._kill_switch.is_fired,
                "autonomy_tier": autonomy_decision.tier.value,
                "control_plane_hash": self._control_plane.manifest.compute_hash(),
            },
        )
        events.append(governance_event)
        if event_callback is not None:
            event_callback(governance_event)
        return response

    def run(
        self,
        user_request: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """Run the agent on ``user_request`` and return the full response.

        Args:
            event_callback: Optional callback receiving each agent lifecycle
                event as it is emitted.  Useful for building a transparency
                stream while still getting the synchronous response.
        """
        prior_cso = kwargs.pop("prior_cso", self._last_cso)
        verify = kwargs.pop("verify", None)

        response = self._run(
            user_request, prior_cso=prior_cso, event_callback=event_callback, **kwargs
        )

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
                # Surface verification + retrieval results in the transparency stream.
                if response.verification:
                    crp_emitter.verification(
                        ratio=response.verification.get("verification_ratio", 0.0),
                        invalid=response.verification.get("invalid", 0),
                        repairs=response.verification.get("repairs", 0),
                    )
                if response.sources:
                    crp_emitter.retrieval(response.sources)
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
                # Surface the final answer in the transparency stream so consoles
                # and narratives render the response text, not just governance.
                if response.text:
                    emitter(tel_events.text_start(messageId="final"))
                    emitter(tel_events.text_delta(messageId="final", delta=response.text))
                    emitter(tel_events.text_end(messageId="final"))
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
