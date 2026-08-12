# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Progressive SDK — the steering wheel for the CRP engine (SPEC-032).

Level 0: drop-in governance::

    import crp
    client = crp.SDKClient()
    r = client.complete("Summarise the EU AI Act")
    print(r.crp.risk)          # LOW | MEDIUM | HIGH | CRITICAL

Level 1: quality::

    client.ingest("./docs/")
    a = client.ask("Write a complete deployment guide")
    print(a.quality)           # S | A | B | C | D
    print(a.sources)           # [{title, doc_id, used_facts}]

Level 2: control::

    @client.tool
    def get_metrics(service: str) -> dict:
        return {"cpu": 0.5}

    r = client.ask("How is the api service doing?", depth="thorough")
    print(r.crp.safety_budget_remaining)
"""

from __future__ import annotations

import inspect
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from crp._version import __version__
from crp.config import CRPConfig as _UnifiedConfig
from crp.core.app_profile import (
    ApplicationProfile,
    ProviderKind,
    build_profile_from_messages,
)
from crp.core.config import _DEFAULTS as _CORE_DEFAULTS
from crp.core.config import CRPConfig as _CoreConfig
from crp.core.session import SessionHandle
from crp.providers.base import LLMProvider
from crp.sdk.dynamic import _ModulesProxy, _OrchestratorProxy, _root_modules_proxy
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
from crp.sdk.proxies_extra import (
    _ComplyProxy,
    _GatewayProxy,
    _HeadersProxy,
    _ObservabilityProxy,
    _PolicyProxy,
    _ScanProxy,
)
from crp.sdk.proxies_more import (
    _AdvancedProxy,
    _CLIProxy,
    _ContinuationProxy,
    _CoreProxy,
    _EnvelopeProxy,
    _ErrorsProxy,
    _ResourcesProxy,
    _SecurityProxy,
    _StateProxy,
)
from crp.sdk.response import (
    CRPAskResponse,
    CRPCompletionResponse,
    CRPResponseMeta,
    SourceAttribution,
)

logger = logging.getLogger("crp.sdk.client")

# ── Unified configuration adapter ──────────────────────────────────────────


class _UnifiedConfigAdapter(_CoreConfig):
    """Bridge a SPEC-037 unified config into the core orchestrator config."""

    # Mapping from unified dotted paths to core config keys.
    # Only keys with a meaningful core equivalent are wired; everything else
    # remains in the unified config and drives SDK-level behaviour.
    _MAP: dict[str, str | None] = {
        "context.windows.max": "max_windows_per_session",
        "context.windows.token_budget": "max_total_input_tokens",
        "context.continuation.input_mode": "input_continuation_mode",
        "context.retrieval.min_relevance": None,
        "context.retrieval.max_hops": None,
        "context.storage.hot_cache_size": None,
        "safety.profile": None,
        "safety.settings": None,
        "knowledge.embedding_model": None,
        "knowledge.auto_ingest": None,
        "audit.retention_days": None,
        "audit.enabled": None,
        "gateway.url": None,
        "gateway.api_key": None,
    }

    def __init__(self, unified: _UnifiedConfig) -> None:
        self._unified = unified
        super().__init__(_values=dict(_CORE_DEFAULTS))
        self._apply_unified_overrides()

    def _apply_unified_overrides(self) -> None:
        for dotted, core_key in self._MAP.items():
            if core_key is None:
                continue
            value = self._unified.get(dotted)
            if value is None:
                continue
            # Type coercion to match core expectations.
            if core_key in {
                "max_windows_per_session",
                "max_total_input_tokens",
                "max_total_output_tokens",
            }:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            self._values[core_key] = value

    @property
    def unified(self) -> _UnifiedConfig:
        """Return the unified."""
        return self._unified


# ── Continuation dispatcher adapter ─────────────────────────────────────────


class _ExhaustiveDispatcher:
    """Adapter that lets ContinuationManager drive the orchestrator."""

    def __init__(self, orchestrator: Any, system_prompt: str) -> None:
        self._orchestrator = orchestrator
        self._system_prompt = system_prompt

    def dispatch(self, prompt: str, **kwargs: Any) -> Any:
        """Dispatch the request and return the result.

            Args:
                prompt (str): The prompt value.
                **kwargs: Variable keyword arguments.

            Returns:
                ``Any``.
        """
        from crp.continuation.manager import DispatchResult

        output, _quality = self._orchestrator.dispatch(
            system_prompt=self._system_prompt,
            task_input=prompt,
            **kwargs,
        )
        return DispatchResult(
            output=output,
            finish_reason="stop",
            output_tokens=0,
            facts=[],
            window_id="",
        )


def _provider_from_profile(profile: ApplicationProfile) -> LLMProvider | None:
    """Create a provider adapter from an explicit application profile.

    Returns ``None`` when the profile does not contain enough information to
    instantiate a provider, letting the normal auto-detection path run.
    """
    if profile is None:
        return None
    import os

    model = profile.provider_model or ""
    metadata = profile.metadata or {}
    base_url = metadata.get("base_url")
    api_key = metadata.get("api_key")

    if profile.provider is ProviderKind.OPENAI and model:
        from crp.providers.openai import OpenAIAdapter
        return OpenAIAdapter(
            model=model,
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or "not-needed",
        )
    if profile.provider is ProviderKind.ANTHROPIC and model:
        from crp.providers.anthropic import AnthropicAdapter
        return AnthropicAdapter(
            model=model,
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY") or "not-needed",
        )
    if profile.provider is ProviderKind.OLLAMA and model:
        from crp.providers.ollama import OllamaAdapter
        return OllamaAdapter(model=model, base_url=base_url)
    if profile.provider is ProviderKind.LLAMA_CPP:
        from crp.providers.llamacpp import LlamaCppAdapter
        return LlamaCppAdapter(server_url=base_url or "http://localhost:8080")
    if profile.provider is ProviderKind.LM_STUDIO and model:
        from crp.providers.openai import OpenAIAdapter
        return OpenAIAdapter(
            model=model,
            base_url=base_url or "http://localhost:1234/v1",
            api_key="not-needed",
        )
    return None


# ── Tool decorator storage ─────────────────────────────────────────────────


@dataclass
class _ToolRegistry:
    """Internal storage for @client.tool decorated functions."""

    tools: dict[str, Callable] = field(default_factory=dict)

    def register(self, fn: Callable) -> None:
        """Execute register and return the result.

            Args:
                fn (Callable): The fn value.

            Returns:
                ``None``.
        """
        self.tools[fn.__name__] = fn


class _Conversation:
    """A multi-turn positioned conversation that relays CSO state automatically.

    Returned by :meth:`CRPClient.conversation`. Each :meth:`say` runs the positioned
    loop with the running CSO forwarded, so callers never thread ``prior_cso`` by hand.
    """

    def __init__(self, client: CRPClient, defaults: dict[str, Any]) -> None:
        self._client = client
        self._defaults = defaults
        self._cso: Any = None
        self.history: list[Any] = []

    def say(self, request: str, **kwargs: Any) -> Any:
        """Send one turn; returns the ``PositionedResult`` and advances the state."""
        params = {**self._defaults, **kwargs}
        params["prior_cso"] = self._cso
        result = self._client.dispatch_positioned(request, **params)
        self._cso = result.cso
        self.history.append(result)
        return result

    @property
    def cso(self) -> Any:
        """The current cognitive state object (accumulated across turns)."""
        return self._cso

    @property
    def turns(self) -> int:
        """Number of turns taken so far."""
        return len(self.history)

    def reset(self) -> None:
        """Clear the conversation state (start fresh)."""
        self._cso = None
        self.history.clear()


# ── CRPClient ──────────────────────────────────────────────────────────────


@dataclass(init=False)
class CRPClient:
    """Progressive-disclosure SDK client (SPEC-032).

    Args:
        provider: An LLMProvider instance (optional — can set later).
        config: A CRPConfig instance (optional — loads defaults or crp.config.yaml).
        safety: Safety profile name ("balanced", "strict", etc.) or dict.
        depth: Default query depth ("auto", "quick", "standard", "thorough",
               "exhaustive").
        app_profile: Optional application capability contract used to auto-select
            provider, relay strategy, and context behaviour.
    """

    provider: LLMProvider | None = field(default=None)
    config: _UnifiedConfig = field(default_factory=_UnifiedConfig)
    _safety_profile: str | dict[str, Any] = field(default="balanced", repr=False)
    depth: str = field(default="auto")  # Level 2: quick | standard | thorough | exhaustive
    model: str | None = field(default=None)  # model identifier for auto-detection
    api_key: str | None = field(default=None)  # optional gateway/provider API key
    app_profile: ApplicationProfile | None = field(default=None)
    _orchestrator: Any = field(default=None, repr=False)
    _session: SessionHandle | None = field(default=None, repr=False)
    _tools: _ToolRegistry = field(default_factory=_ToolRegistry, repr=False)
    _safety_overrides: dict[str, Any] = field(default_factory=dict, repr=False)

    def __init__(
        self,
        provider: LLMProvider | None = None,
        config: _UnifiedConfig | None = None,
        safety: str | dict[str, Any] = "balanced",
        depth: str = "auto",
        model: str | None = None,
        api_key: str | None = None,
        input_continuation_mode: str | None = None,
        app_profile: ApplicationProfile | None = None,
    ) -> None:
        """Manual __init__ to allow a ``safety`` property on a dataclass."""
        self.provider = provider
        self.config = config if config is not None else _UnifiedConfig()
        if input_continuation_mode is not None:
            self.config.set("context.continuation.input_mode", input_continuation_mode)
        self._safety_profile = safety
        self.depth = depth
        self.model = model
        self.api_key = api_key
        self.app_profile = app_profile
        self._orchestrator = None
        self._session = None
        self._tools = _ToolRegistry()
        self._safety_overrides = {}
        self._post_init()

    def _post_init(self) -> None:
        # Auto-load crp.config.yaml if present
        if not self.config._source_path and Path("crp.config.yaml").exists():
            self.config = _UnifiedConfig.load("crp.config.yaml")
        if self.api_key:
            self.config.set("gateway.api_key", self.api_key)
        # Lazy init orchestrator on first use to avoid heavy imports
        logger.debug("CRPClient initialised (v%s)", __version__)

    # ------------------------------------------------------------------
    # Internal: orchestrator access
    # ------------------------------------------------------------------

    def _ensure_orchestrator(self) -> Any:
        """Lazy initialisation of CRPOrchestrator."""
        if self._orchestrator is None:
            from crp.core.orchestrator import CRPOrchestrator, _auto_detect_provider
            from crp.providers.custom import CustomProvider

            core_config = _UnifiedConfigAdapter(self.config)
            if self.provider is not None:
                resolved_provider = self.provider
            else:
                # First try the explicit application profile; fall back to
                # orchestrator auto-detection; finally a silent provider so the
                # client remains instantiable even with no LLM configured.
                resolved_provider = _provider_from_profile(self.app_profile)
                if resolved_provider is None:
                    try:
                        resolved_provider = _auto_detect_provider(
                            model=self.model or (self.app_profile.provider_model if self.app_profile else None),
                        )
                    except ValueError:
                        resolved_provider = CustomProvider(
                            generate_fn=lambda msgs: ("", "stop"),
                            count_tokens_fn=lambda t: len(t.split()),
                            context_size=4096,
                            name="sdk-fallback",
                        )

            self._orchestrator = CRPOrchestrator(
                provider=resolved_provider,
                config=core_config,
                app_profile=self.app_profile,
            )
            self._apply_safety_profile()
        return self._orchestrator

    def _ensure_session(self) -> SessionHandle:
        """Lazy initialisation of session."""
        if self._session is None:
            orch = self._ensure_orchestrator()
            self._session = orch.session
        return self._session

    def _apply_safety_profile(self) -> None:
        """Map SDK safety profile to orchestrator human-oversight config."""
        from crp.security.consent import HumanOversightLevel, OversightConfig

        profile = self._safety_profile if isinstance(self._safety_profile, dict) else {}
        if isinstance(self._safety_profile, str):
            name = self._safety_profile
        else:
            name = profile.get("profile", "balanced")

        overrides = dict(self._safety_overrides)
        if name == "strict":
            level = HumanOversightLevel.APPROVAL
            cfg = OversightConfig(
                level=level,
                require_approval_for_dispatch=True,
                halt_on_injection_detection=True,
                halt_on_pii_detection=True,
                alert_on_quality_below=overrides.get("alert_on_quality_below", "B"),
            )
        elif name == "permissive":
            cfg = OversightConfig(
                level=HumanOversightLevel.NONE,
                halt_on_injection_detection=False,
                halt_on_pii_detection=False,
            )
        elif name == "research":
            cfg = OversightConfig(
                level=HumanOversightLevel.INFORMED,
                halt_on_injection_detection=False,
                halt_on_pii_detection=False,
            )
        else:  # balanced
            cfg = OversightConfig(
                level=HumanOversightLevel.INFORMED,
                halt_on_injection_detection=False,
                halt_on_pii_detection=False,
                alert_on_quality_below=overrides.get("alert_on_quality_below", "C"),
            )

        try:
            self._orchestrator._security._human_oversight._config = cfg
        except Exception as exc:
            logger.debug("Could not apply safety profile: %s", exc)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, **kwargs: Any) -> None:
        """Apply runtime configuration overrides (Layer 5).

        Unknown keys are stored in the unified config. Keys that map to core
        orchestrator settings are also forwarded when possible.
        """
        for key, value in kwargs.items():
            self.config.set(key, value)
        self._safety_overrides.update(
            {k: v for k, v in kwargs.items() if k.startswith("safety.")}
        )
        if self._orchestrator is not None:
            # Forward known core keys.
            core_map = {
                "context.windows.max": "max_windows_per_session",
                "context.windows.token_budget": "max_total_input_tokens",
            }
            core_overrides: dict[str, Any] = {}
            for key, value in kwargs.items():
                core_key = core_map.get(key)
                if core_key:
                    try:
                        core_overrides[core_key] = int(value)
                    except (TypeError, ValueError):
                        continue
            if core_overrides:
                try:
                    self._orchestrator._config.update(core_overrides)
                except ValueError as exc:
                    logger.warning("Immutable config override ignored: %s", exc)
            self._apply_safety_profile()

    # ------------------------------------------------------------------
    # Level 0 — Governance
    # ------------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        **kwargs: Any,
    ) -> CRPCompletionResponse:
        """Single-turn completion with automatic governance (Level 0).

        Returns:
            CRPCompletionResponse with ``.crp`` governance summary.
        """
        self._ensure_orchestrator()
        self._ensure_session()

        try:
            result = self._dispatch_with_depth(system, prompt, depth=None, **kwargs)
        except Exception as exc:
            logger.warning("Dispatch failed: %s", exc)
            return CRPCompletionResponse(
                text="",
                crp=CRPResponseMeta(
                    risk="CRITICAL",
                    grounded=False,
                    chain_valid=False,
                ),
                finish_reason="error",
            )

        result = self._normalise_result(result)
        meta = self._build_meta(result)
        return CRPCompletionResponse(
            text=result.output,
            crp=meta,
            finish_reason=result.finish_reason,
            usage=result.usage,
        )

    def stream(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        *,
        depth: str | None = None,
        **kwargs: Any,
    ):
        """Stream a single-turn completion as ``StreamEvent`` objects.

        Each event has ``event_type`` (``token``, ``extraction``,
        ``continuation``, ``window_complete``, ``done``, ``error``) and
        ``data``. Concatenating all ``token`` data values produces the same
        text as :meth:`complete`.

        Args:
            depth: Override depth (``quick`` / ``standard`` / ``thorough`` /
                ``exhaustive``).

        Example::

            for event in client.stream("Explain CRP."):
                if event.event_type == "token":
                    print(event.data, end="")
                elif event.event_type == "done":
                    print("\nDone")
        """
        orch = self._ensure_orchestrator()
        self._ensure_session()

        effective_depth = depth or self.depth
        dispatch_kwargs = self._depth_kwargs(effective_depth, kwargs)
        yield from orch.dispatch_stream(
            system_prompt=system,
            task_input=prompt,
            **dispatch_kwargs,
        )

    # ------------------------------------------------------------------
    # Level 1 — Quality
    # ------------------------------------------------------------------

    def ingest(self, path: str | list[str]) -> None:
        """Ingest documents into the Contextual Knowledge Fabric.

        Accepts a file path, directory path, or list of paths.
        """
        orch = self._ensure_orchestrator()
        self._ensure_session()

        paths = [path] if isinstance(path, str) else path
        for p in paths:
            p_obj = Path(p)
            if p_obj.is_dir():
                for f in p_obj.rglob("*"):
                    if f.is_file():
                        try:
                            orch.ingest(f.read_text(encoding="utf-8"), source_label=str(f))
                        except Exception as exc:
                            logger.warning("Ingest failed for %s: %s", f, exc)
            else:
                try:
                    orch.ingest(p_obj.read_text(encoding="utf-8"), source_label=p)
                except Exception as exc:
                    logger.warning("Ingest failed for %s: %s", p, exc)

    def ask(
        self,
        question: str,
        system: str = "You are a helpful assistant.",
        depth: str | None = None,
        **kwargs: Any,
    ) -> CRPAskResponse:
        """Multi-turn quality-aware query with source attribution (Level 1–2).

        Args:
            depth: Override depth for this query ("quick", "standard",
                   "thorough", "exhaustive"). Level 2 control.

        Returns:
            CRPAskResponse with quality tier, sources, completeness, and
            inspectable reasoning (Level 2).
        """
        orch = self._ensure_orchestrator()
        self._ensure_session()

        effective_depth = depth or self.depth
        how_built = self._build_how_it_was_built(question, effective_depth)

        try:
            if effective_depth == "exhaustive":
                result = self._ask_exhaustive(orch, system, question, kwargs)
            else:
                result = self._dispatch_with_depth(system, question, depth=effective_depth, **kwargs)
        except Exception as exc:
            logger.warning("Ask dispatch failed: %s", exc)
            return CRPAskResponse(
                text="",
                quality="D",
                complete=False,
                crp=CRPResponseMeta(
                    risk="CRITICAL",
                    grounded=False,
                    chain_valid=False,
                ),
                finish_reason="error",
                how_it_was_built=how_built,
            )

        result = self._normalise_result(result)
        meta = self._build_meta(result)
        quality = self._extract_quality(result)
        sources = self._extract_sources(result) or self._derive_sources(question, result.output)
        complete = getattr(result, "complete", False)
        open_qs = self._extract_open_questions(result)
        decisions = self._extract_decisions(result)

        return CRPAskResponse(
            text=result.output,
            quality=quality,
            sources=sources,
            complete=complete,
            crp=meta,
            finish_reason=result.finish_reason,
            usage=result.usage,
            decisions=decisions,
            how_it_was_built=how_built,
            open_questions=open_qs,
        )

    def _ask_exhaustive(
        self,
        orchestrator: Any,
        system: str,
        question: str,
        kwargs: dict[str, Any],
    ) -> Any:
        """Run the ContinuationManager loop for exhaustive depth."""
        from types import SimpleNamespace

        from crp.continuation.manager import ContinuationConfig, ContinuationManager

        initial_output, _quality = orchestrator.dispatch(
            system_prompt=system,
            task_input=question,
            **self._depth_kwargs("exhaustive", kwargs),
        )

        config = ContinuationConfig()
        manager = ContinuationManager(config)
        dispatcher = _ExhaustiveDispatcher(orchestrator, system)
        state = manager.run(
            task_intent=question,
            dispatcher=dispatcher,
            initial_output=initial_output,
            initial_finish_reason="stop",
            initial_output_tokens=0,
            initial_facts=[],
        )

        return SimpleNamespace(
            output=state.stitched_output or initial_output,
            finish_reason="stop" if state.finished else "length",
            complete=state.finished,
            quality_report=SimpleNamespace(
                risk_level="LOW",
                grounded=True,
                fabrication_count=0,
                tier="B",
            ),
            decisions=[d.__dict__ for d in getattr(state, "decisions", [])] if hasattr(state, "decisions") else [],
            open_questions=getattr(state, "open_questions", []),
        )

    # ------------------------------------------------------------------
    # Level 2 — Control
    # ------------------------------------------------------------------

    def tool(self, fn: Callable) -> Callable:
        """Decorator: register a tool for tool-mediated dispatch (Level 2).

        Usage::

            @client.tool
            def get_metrics(service: str) -> dict:
                return {"cpu": 0.5}
        """
        self._tools.register(fn)
        return fn

    def call_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a registered tool by name (Level 2)."""
        if name not in self._tools.tools:
            raise ValueError(f"Tool '{name}' not registered. Registered: {list(self._tools.tools.keys())}")
        return self._tools.tools[name](*args, **kwargs)

    def dispatch_positioned(
        self,
        user_request: str,
        *,
        fabric: Any = None,
        executor: Any = None,
        profile: Any = None,
        governor: Any = None,
        clarify_handler: Any = None,
        policy: Any = None,
        oversight_required: Any = None,
        context_facts: list[str] | None = None,
        max_operations: int = 12,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        prior_cso: Any = None,
        max_continuation_windows: int = 1,
    ) -> Any:
        """Run the positioned-tool-loop (CRP-SPEC-049/050) with this client's provider.

        Positioning, not injection: each operation positions the model on only the
        1–3 tools the protocol selected for it — never the full catalogue. Any
        ``@client.tool`` functions are auto-registered as capabilities when no
        explicit ``fabric`` is supplied.

        For multi-turn workflows, pass the previous result's ``.cso`` as
        ``prior_cso`` so the follow-up turn is positioned with everything the prior
        turn established (facts, tool observations, decisions).

        Returns a ``PositionedResult`` exposing ``.text``, ``.cso``,
        ``.event_stream``, ``.observation_count``, ``.headers``, and ``.halted``.
        """
        from crp.stl.positioned import provider_model_call, run_positioned
        from crp.tools.adapters import fabric_from_callables
        from crp.tools.capability_fabric import CapabilityProfile

        orch = self._ensure_orchestrator()
        provider = self.provider or getattr(orch, "_provider", None)
        if provider is None:
            raise RuntimeError("No LLM provider configured for dispatch_positioned()")
        model_call = provider_model_call(provider, temperature=temperature, max_tokens=max_tokens)

        if fabric is None and self._tools.tools:
            fabric, executor = fabric_from_callables(list(self._tools.tools.values()))

        return run_positioned(
            user_request,
            model_call,
            fabric=fabric,
            executor=executor,
            profile=profile or CapabilityProfile.FRONTIER,
            governor=governor,
            clarify_handler=clarify_handler,
            policy=policy,
            oversight_required=oversight_required,
            context_facts=context_facts,
            max_operations=max_operations,
            prior_cso=prior_cso,
            max_continuation_windows=max_continuation_windows,
        )

    def conversation(self, **defaults: Any) -> _Conversation:
        """Start a multi-turn positioned conversation that manages state for you.

        Each ``.say(request)`` runs the positioned loop with the running CSO relayed
        forward automatically — no manual ``prior_cso`` threading::

            convo = client.conversation()
            r1 = convo.say("Look up the service on port 443.")
            r2 = convo.say("Based on that, is it safe for a login page?")

        ``defaults`` are passed to every ``dispatch_positioned`` call (e.g.
        ``profile=``, ``max_continuation_windows=``, ``clarify_handler=``).
        """
        return _Conversation(self, defaults)

    def make_agent(
        self,
        tools: list[Any] | None = None,
        policy: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Return a ``crp.Agent`` pre-bound to this client's provider and config.

        This is the bridge from the progressive SDK client to the declarative
        Agent SDK introduced in CRPv6 (SPEC-059).
        """
        from crp.agent_sdk import Agent

        orch = self._ensure_orchestrator()
        provider = self.provider or getattr(orch, "_provider", None)
        merged_kwargs = {
            "provider": provider,
            "tools": tools,
            "policy": policy,
            "depth": self.depth,
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        merged_kwargs.update(kwargs)
        return Agent(**merged_kwargs)

    def derive_profile(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ApplicationProfile:
        """Derive an application capability contract from observed messages."""
        return build_profile_from_messages(messages, tools=tools)

    # ------------------------------------------------------------------
    # Session / visibility API (SPEC-038)
    # ------------------------------------------------------------------

    def session(self) -> Any:
        """Return a live view of the current CRP session."""
        orch = self._ensure_orchestrator()
        return SimpleNamespace(
            id=orch._session.session_id,
            fact_count=orch.warm_store.fact_count,
            window_count=orch.warm_store.window_count,
            status=orch.session_status,
        )

    @property
    def storage(self) -> Any:
        """Access storage visibility API."""
        return _StorageProxy(self._ensure_orchestrator())

    @property
    def knowledge(self) -> Any:
        """Access knowledge location."""
        return _KnowledgeProxy(self._ensure_orchestrator())

    @property
    def audit(self) -> Any:
        """Access the tamper-evident compliance audit trail."""
        return _AuditProxy(self._ensure_orchestrator())

    @property
    def compliance(self) -> Any:
        """Access EU AI Act / ISO 42001 compliance helpers."""
        return _ComplianceProxy(self._ensure_orchestrator())

    # ------------------------------------------------------------------
    # Namespace proxies (SPEC-032 advanced surface)
    # ------------------------------------------------------------------

    @property
    def safety(self) -> _SafetyProxy:  # type: ignore[override]
        """Access the Safety Control Plane (SPEC-033, SPEC-034)."""
        return _SafetyProxy(self._ensure_orchestrator())

    @safety.setter
    def safety(self, value: str | dict[str, Any]) -> None:
        """Store the SDK safety profile for later application."""
        self._safety_profile = value

    @property
    def ckf(self) -> _CKFProxy:
        """Access the Contextual Knowledge Fabric (SPEC-009, SPEC-025)."""
        return _CKFProxy(self._ensure_orchestrator())

    @property
    def cso(self) -> _CSOProxy:
        """Access the Cognitive State Object (SPEC-030)."""
        return _CSOProxy(self._ensure_orchestrator())

    @property
    def provenance(self) -> _ProvenanceProxy:
        """Access the Decision Provenance Engine (SPEC-005)."""
        return _ProvenanceProxy(self._ensure_orchestrator())

    @property
    def reasoning(self) -> _ReasoningProxy:
        """Access reasoning scaffolds, CQS, and cross-window validation."""
        return _ReasoningProxy(self._ensure_orchestrator())

    @property
    def activation(self) -> _ActivationProxy:
        """Access CRP activation-mode detection (SPEC-017)."""
        return _ActivationProxy(self._ensure_orchestrator())

    @property
    def agent(self) -> _AgentProxy:
        """Access multi-agent safety budget and chain tools (SPEC-012)."""
        return _AgentProxy(self._ensure_orchestrator())

    @property
    def events(self) -> _EventsProxy:
        """Access the protocol event bus (§9)."""
        return _EventsProxy(self._ensure_orchestrator())

    @property
    def providers(self) -> _ProvidersProxy:
        """Access LLM provider registration (SPEC-008)."""
        return _ProvidersProxy(self._ensure_orchestrator())

    @property
    def extract(self) -> _ExtractionProxy:
        """Access the graduated extraction pipeline (§2.5)."""
        return _ExtractionProxy(self._ensure_orchestrator())

    @property
    def gateway(self) -> _GatewayProxy:
        """Access CRP Gateway helpers (SPEC-016)."""
        return _GatewayProxy(self._ensure_orchestrator())

    @property
    def headers(self) -> _HeadersProxy:
        """Access the CRP HTTP header surface (SPEC-002)."""
        return _HeadersProxy(self._ensure_orchestrator())

    @property
    def observability(self) -> _ObservabilityProxy:
        """Access observability subsystems (audit, metrics, telemetry)."""
        return _ObservabilityProxy(self._ensure_orchestrator())

    @property
    def policy(self) -> _PolicyProxy:
        """Access the safety policy engine (SPEC-006)."""
        return _PolicyProxy(self._ensure_orchestrator())

    @property
    def scan(self) -> _ScanProxy:
        """Access CRP Scan helpers (SPEC-013, SPEC-036, SPEC-039)."""
        return _ScanProxy(self._ensure_orchestrator())

    @property
    def comply(self) -> _ComplyProxy:
        """Access CRP Comply helpers (SPEC-040, SPEC-042, SPEC-047, SPEC-048)."""
        return _ComplyProxy(self._ensure_orchestrator())

    @property
    def orchestrator(self) -> _OrchestratorProxy:
        """Access the live ``CRPOrchestrator`` instance directly.

        This exposes every public orchestrator method and subsystem (e.g.
        ``client.orchestrator.dispatch(...)``, ``client.orchestrator.ckf``).
        """
        return _OrchestratorProxy(self._ensure_orchestrator())

    @property
    def modules(self) -> _ModulesProxy:
        """Access any public class or function in the ``crp`` package.

        This dynamic mirror lets you reach the full CRP API without importing
        modules manually::

            client.modules.envelope.cdr.cdr_rank(...)
            client.modules.security.consent.ConsentManager(...)
        """
        return _root_modules_proxy()

    @property
    def core(self) -> _CoreProxy:
        """Access core orchestrator, session, DAG, ledger, and facilitator."""
        return _CoreProxy(self._ensure_orchestrator())

    @property
    def continuation(self) -> _ContinuationProxy:
        """Access continuation manager and helpers."""
        return _ContinuationProxy(self._ensure_orchestrator())

    @property
    def envelope(self) -> _EnvelopeProxy:
        """Access envelope builder, packer, reranker, CDR, and formatter."""
        return _EnvelopeProxy(self._ensure_orchestrator())

    @property
    def state(self) -> _StateProxy:
        """Access warm store, cold storage, snapshots, event log, and router."""
        return _StateProxy(self._ensure_orchestrator())

    @property
    def security(self) -> _SecurityProxy:
        """Access safety manifest, consent, RBAC, checkpoints, and audit trail."""
        return _SecurityProxy(self._ensure_orchestrator())

    @property
    def resources(self) -> _ResourcesProxy:
        """Access adaptive allocator, cost model, overhead, and resource manager."""
        return _ResourcesProxy(self._ensure_orchestrator())

    @property
    def advanced(self) -> _AdvancedProxy:
        """Access curator, feedback, meta-learning, source grounding, and validator."""
        return _AdvancedProxy(self._ensure_orchestrator())

    @property
    def cli(self) -> _CLIProxy:
        """Access CLI sidecar handler and startup result types."""
        return _CLIProxy(self._ensure_orchestrator())

    @property
    def errors(self) -> _ErrorsProxy:
        """Access public CRP exception classes."""
        return _ErrorsProxy(self._ensure_orchestrator())

    def save_config(self, path: str | Path) -> None:
        """Save the current unified config to ``path``.

        Args:
            path: Destination file path.
        """
        self.config.save(path)

    def config_hash(self) -> str:
        """Return a deterministic hash of the loaded unified config.

        Returns:
            Hex digest string, or empty string if hashing is unavailable.
        """
        try:
            return self.config.compute_hash()
        except Exception as exc:
            logger.debug("Config hash failed: %s", exc)
            return ""

    async def __aenter__(self) -> CRPClient:
        """Async context manager entry — not yet implemented."""
        raise NotImplementedError(
            "Async SDKClient context manager is not implemented in this version. "
            "Use `async with client` is not supported; use sync `with client` instead."
        )

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Async context manager exit — not yet implemented."""
        raise NotImplementedError(
            "Async SDKClient context manager is not implemented in this version."
        )

    # ------------------------------------------------------------------
    # Dispatch internals
    # ------------------------------------------------------------------

    def _depth_kwargs(self, depth: str, base_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Translate SDK depth setting into orchestrator/provider kwargs."""
        merged = dict(base_kwargs or {})
        depth_map = {
            "quick": {"max_output_tokens": 256},
            "standard": {"max_output_tokens": 512},
            "thorough": {"max_output_tokens": 1024},
            "exhaustive": {"max_output_tokens": 2048},
        }
        if depth in depth_map:
            for key, value in depth_map[depth].items():
                if key not in merged:
                    merged[key] = value
        return merged

    def _dispatch_with_depth(
        self,
        system: str,
        prompt: str,
        depth: str | None,
        **kwargs: Any,
    ) -> Any:
        """Route to orchestrator dispatch or tool-mediated loop."""
        orch = self._ensure_orchestrator()
        effective_depth = depth or self.depth

        # Level 2: tool-mediated dispatch when user tools are registered.
        if self._tools.tools and orch._provider.supports_tools():
            return self._dispatch_with_tools(system, prompt, effective_depth, **kwargs)

        # Profile-driven relay strategy selection (SPEC-008 extension).
        strategy = orch._select_relay_strategy(has_registered_tools=bool(self._tools.tools))
        dispatch_kwargs = self._depth_kwargs(effective_depth, kwargs)
        if strategy == "tools":
            # Tool-mediated dispatch uses its own output-budget logic; only
            # forward the explicit tool-round cap to avoid passing unknown
            # provider parameters through.
            return orch.dispatch_with_tools(
                system, prompt,
                max_tool_rounds=int(kwargs.get("max_tool_rounds", 10)),
            )
        if strategy != "push":
            return orch.dispatch_with_strategy(strategy, system, prompt, **dispatch_kwargs)

        return orch.dispatch(
            system_prompt=system,
            task_input=prompt,
            **dispatch_kwargs,
        )

    def _dispatch_with_tools(
        self,
        system: str,
        prompt: str,
        depth: str,
        **kwargs: Any,
    ) -> Any:
        """Run an OpenAI-compatible tool loop for registered functions."""
        orch = self._ensure_orchestrator()
        provider = orch._provider
        max_out = self._depth_kwargs(depth).get("max_output_tokens", 512)
        max_rounds = int(kwargs.pop("max_tool_rounds", 10))

        tools = [self._build_tool_schema(fn) for fn in self._tools.tools.values()]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        tool_log: list[dict[str, Any]] = []
        finish_reason = "stop"
        output = ""

        for _round in range(max_rounds):
            output, finish_reason, tool_calls, raw_msg = provider.generate_chat_with_tools(
                messages,
                tools=tools,
                max_tokens=max_out,
                **kwargs,
            )
            if finish_reason != "tool_calls" or not tool_calls:
                break
            messages.append(raw_msg)
            for tc in tool_calls:
                result = self._execute_tool_call(tc)
                tool_log.append({
                    "name": tc["function"]["name"],
                    "arguments": tc["function"].get("arguments"),
                    "result": result,
                })
                content = result if isinstance(result, str) else json.dumps(result, default=str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": content,
                })
        else:
            # Exhausted rounds without a natural stop.
            finish_reason = "length"

        return self._govern_output(system, prompt, output, finish_reason, tool_log)

    def _build_tool_schema(self, fn: Callable) -> dict[str, Any]:
        """Build an OpenAI-compatible tool definition from a Python function."""
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, param in sig.parameters.items():
            if param.default is inspect.Parameter.empty:
                required.append(name)
            properties[name] = self._python_type_to_json_schema(
                param.annotation if param.annotation is not inspect.Parameter.empty else str
            )

        description = (fn.__doc__ or f"Call {fn.__name__}").strip().split("\n")[0]
        return {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @staticmethod
    def _python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
        """Simple Python-type → JSON-schema mapping."""
        origin = getattr(annotation, "__origin__", None)
        if origin is list or annotation is list:
            return {"type": "array"}
        if origin is dict or annotation is dict:
            return {"type": "object"}
        if annotation is int:
            return {"type": "integer"}
        if annotation is float:
            return {"type": "number"}
        if annotation is bool:
            return {"type": "boolean"}
        return {"type": "string"}

    def _execute_tool_call(self, tc: dict[str, Any]) -> Any:
        """Invoke a registered tool from a provider tool_call dict."""
        name = tc["function"]["name"]
        args = tc["function"].get("arguments") or {}
        if name not in self._tools.tools:
            return {"error": f"Tool '{name}' not registered"}
        fn = self._tools.tools[name]
        if not isinstance(args, dict):
            args = {"input": args}
        try:
            return fn(**args)
        except Exception as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return {"error": str(exc)}

    def _govern_output(
        self,
        system: str,
        prompt: str,
        output: str,
        finish_reason: str,
        tool_log: list[dict[str, Any]],
    ) -> SimpleNamespace:
        """Apply CRP governance (extraction, scanning, quality tier) to tool output."""
        orch = self._ensure_orchestrator()
        from crp.core.dispatch_router import _classify_quality_tier
        from crp.core.session import QualityReport, SecurityFlags
        from crp.core.task_intent import TaskIntent

        window_id = f"sdk-tool-{uuid.uuid4().hex[:8]}"
        task_intent = TaskIntent(task_input=prompt, system_prompt=system)
        extraction = orch._extract_and_store(output, window_id, task_intent)

        input_flags = orch._scan_injection(prompt)
        output_flags = orch._scan_injection(output)
        flags = SecurityFlags(
            injection_markers_detected=(
                input_flags.injection_markers_detected + output_flags.injection_markers_detected
            ),
            control_chars_stripped=(
                input_flags.control_chars_stripped + output_flags.control_chars_stripped
            ),
            unicode_normalized=(input_flags.unicode_normalized or output_flags.unicode_normalized),
            output_injection_facts_penalized=sum(
                1
                for f in extraction.facts
                if f.flagged_confidence
                and "injection_in_fact" in getattr(f, "confidence_flag_reason", "")
            ),
        )

        output_tokens = orch._provider.count_tokens(output)
        tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=0,
            saturation=0.0,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        quality_report = QualityReport(
            session_id=orch._session.session_id,
            window_id=window_id,
            output=output,
            facts_extracted=extraction.total_facts,
            security_flags=flags,
            continuation_windows=0,
            envelope_saturation=0.0,
            quality_tier=tier,
            telemetry={"tool_calls": len(tool_log)},
        )

        return SimpleNamespace(
            output=output,
            finish_reason=finish_reason,
            quality_report=quality_report,
            usage={
                "input_tokens": orch._provider.count_tokens(system + prompt),
                "output_tokens": output_tokens,
            },
            complete=(finish_reason == "stop" and bool(output.strip())),
            sources=[],
            decisions=[],
            open_questions=[],
            tool_calls=tool_log,
        )

    # ------------------------------------------------------------------
    # Meta builders
    # ------------------------------------------------------------------

    def _normalise_result(self, result: Any) -> SimpleNamespace:
        """Normalise dispatch output to a standard namespace.

        Dispatch may return a tuple ``(output, quality_report)`` or a result
        object with ``output``, ``finish_reason``, ``quality_report`` etc.
        """
        if isinstance(result, tuple):
            output, quality = result
            return SimpleNamespace(
                output=output if output is not None else "",
                finish_reason="stop",
                quality_report=quality,
                usage={},
                complete=False,
                sources=[],
                decisions=[],
                open_questions=[],
                tool_calls=[],
            )
        return SimpleNamespace(
            output=getattr(result, "output", "") or "",
            finish_reason=getattr(result, "finish_reason", "stop"),
            quality_report=getattr(result, "quality_report", None),
            usage=getattr(result, "usage", {}) or {},
            complete=getattr(result, "complete", False),
            sources=getattr(result, "sources", []) or [],
            decisions=getattr(result, "decisions", []) or [],
            open_questions=getattr(result, "open_questions", []) or [],
            tool_calls=getattr(result, "tool_calls", []) or [],
        )

    def _build_meta(self, result: Any) -> CRPResponseMeta:
        """Build CRPResponseMeta from an orchestrator or governed result."""
        orch = self._orchestrator
        meta = CRPResponseMeta()

        meta.risk = self._derive_risk(result)
        meta.grounded = self._derive_grounded(result)
        meta.fabrications = self._derive_fabrications(result)
        meta.chain_valid = getattr(result, "chain_valid", True)

        # Injection detection from security flags
        security_flags = None
        if hasattr(result, "security_flags") and result.security_flags:
            security_flags = result.security_flags
        elif getattr(getattr(result, "quality_report", None), "security_flags", None):
            security_flags = result.quality_report.security_flags
        if security_flags:
            meta.injection_detected = getattr(security_flags, "injection_markers_detected", 0) > 0

        # PII detection via orchestrator scanner on output
        output = getattr(result, "output", "")
        if orch is not None:
            try:
                meta.pii_detected = orch._pii_scanner.scan(output).has_pii
            except Exception:
                meta.pii_detected = False

        meta.compliant = meta.risk != "CRITICAL"
        meta.safety_budget_remaining = 1.0 if meta.risk not in {"HIGH", "CRITICAL"} else 0.5
        if orch is not None:
            meta.session_id = orch._session.session_id
            qr = getattr(result, "quality_report", None)
            meta.window_id = getattr(qr, "window_id", "") if qr else ""
        return meta

    def _derive_risk(self, result: Any) -> str:
        """Derive a LOW/MEDIUM/HIGH/CRITICAL risk label."""
        finish_reason = getattr(result, "finish_reason", "stop")
        if finish_reason == "error":
            return "CRITICAL"

        qr = getattr(result, "quality_report", None)
        if qr is not None:
            if getattr(qr, "risk_level", None):
                return str(qr.risk_level)
            if getattr(qr, "quality_tier", None) == "D":
                return "HIGH"
            security_flags = getattr(qr, "security_flags", None)
            if security_flags:
                markers = getattr(security_flags, "injection_markers_detected", 0)
                if markers >= 3:
                    return "HIGH"
                if markers > 0:
                    return "MEDIUM"
        if getattr(result, "fabrications", 0) > 0:
            return "MEDIUM"
        return "LOW"

    def _derive_grounded(self, result: Any) -> bool:
        """Estimate whether the response is grounded in context."""
        if hasattr(result, "grounded"):
            return bool(result.grounded)
        qr = getattr(result, "quality_report", None)
        if qr is None:
            return True
        saturation = getattr(qr, "envelope_saturation", 0.0) or 0.0
        facts = getattr(qr, "facts_extracted", 0) or 0
        return saturation > 0.3 or facts > 0

    def _derive_fabrications(self, result: Any) -> int:
        """Return fabrication count if available."""
        if hasattr(result, "fabrications"):
            return int(result.fabrications or 0)
        qr = getattr(result, "quality_report", None)
        if qr is None:
            return 0
        return int(getattr(qr, "fabrication_count", 0) or 0)

    def _extract_quality(self, result: Any) -> str:
        """Extract quality tier from result."""
        if hasattr(result, "quality_report") and result.quality_report:
            tier = getattr(result.quality_report, "tier", None)
            if tier:
                return tier
            qt = getattr(result.quality_report, "quality_tier", None)
            if qt:
                return qt
        return "B"

    def _extract_sources(self, result: Any) -> list[SourceAttribution]:
        """Extract source attributions from result."""
        sources: list[SourceAttribution] = []
        if hasattr(result, "sources") and result.sources:
            for src in result.sources:
                if isinstance(src, dict):
                    sources.append(SourceAttribution(
                        title=src.get("title", ""),
                        doc_id=src.get("doc_id", ""),
                        used_facts=src.get("used_facts", 0),
                        relevance_score=src.get("relevance_score", 0.0),
                    ))
                elif isinstance(src, SourceAttribution):
                    sources.append(src)
        return sources

    def _derive_sources(self, question: str, output: str, top_k: int = 5) -> list[SourceAttribution]:
        """Derive source attributions from CKF and warm store facts."""
        orch = self._orchestrator
        if orch is None:
            return []

        facts_with_scores: list[tuple[Any, float]] = []
        try:
            from crp.provenance._embeddings import encode_texts
            embeddings = encode_texts([question]) or encode_texts([output])
            if embeddings and embeddings[0]:
                merged = orch.ckf.retrieve(
                    query_embedding=embeddings[0],
                    budget=top_k * 2,
                    modes=["semantic"],
                )
                facts_with_scores.extend((mf.fact, mf.score) for mf in merged.facts)
        except Exception:
            logger.debug("Semantic source retrieval unavailable")

        # Warm store fallback / supplement
        try:
            for wf in orch.warm_store.get_ranked_facts(limit=top_k * 2):
                facts_with_scores.append((wf.fact, 0.5))
        except Exception:
            pass

        # Group by source window / label
        groups: dict[str, dict[str, Any]] = {}
        for fact, score in facts_with_scores:
            if getattr(fact, "superseded_by", None):
                continue
            sid = fact.source_window_id or fact.metadata.get("source", "unknown")
            title = fact.metadata.get("title") or fact.metadata.get("source")
            if not title:
                text = fact.text.strip()
                title = text[:60] + "..." if len(text) > 60 else text
            if sid not in groups:
                groups[sid] = {"title": title, "score": score, "count": 0}
            groups[sid]["count"] += 1
            if score > groups[sid]["score"]:
                groups[sid]["score"] = score

        sorted_groups = sorted(groups.items(), key=lambda kv: kv[1]["score"], reverse=True)
        sources: list[SourceAttribution] = []
        for sid, g in sorted_groups[:top_k]:
            sources.append(SourceAttribution(
                title=g["title"],
                doc_id=sid,
                used_facts=g["count"],
                relevance_score=round(g["score"], 4),
            ))
        return sources

    # ------------------------------------------------------------------
    # Level 2 — Inspect reasoning
    # ------------------------------------------------------------------

    def _build_how_it_was_built(self, question: str, depth: str) -> str:
        """Human-readable description of how the response was constructed."""
        parts = [f"Query: {question[:80]}"]
        if depth != "auto":
            parts.append(f"Depth: {depth}")
        if self._tools.tools:
            parts.append(f"Tools available: {', '.join(self._tools.tools.keys())}")
        parts.append("Governance: CRP v4 safety + provenance active")
        return "; ".join(parts)

    def _extract_open_questions(self, result: Any) -> list[str]:
        """Extract unresolved questions flagged by CRP."""
        open_qs: list[str] = []
        if hasattr(result, "open_questions") and result.open_questions:
            open_qs = result.open_questions
        return open_qs

    def _extract_decisions(self, result: Any) -> list[dict[str, Any]]:
        """Extract CSO decisions if available."""
        decisions: list[dict[str, Any]] = []
        if hasattr(result, "decisions") and result.decisions:
            decisions = result.decisions
        return decisions

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear accumulated session facts (warm store + CKF)."""
        orch = self._ensure_orchestrator()
        try:
            orch.warm_store.clear()
            orch.ckf.clear()
        except Exception as exc:
            logger.warning("Reset failed: %s", exc)

    def close(self) -> None:
        """Release orchestrator resources."""
        if self._orchestrator is not None:
            try:
                self._orchestrator.close()
            except Exception as exc:
                logger.warning("Close failed: %s", exc)
            self._orchestrator = None
            self._session = None

    def __enter__(self) -> CRPClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


# Convenience alias for lazy-loading from crp.__getattr__
SDKClient = CRPClient
