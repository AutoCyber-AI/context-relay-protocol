# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP orchestrator — full-featured dispatch with all subsystems (§2.5, §6.5).

Capabilities:
  - Envelope-based dispatch with 6-phase fact packing
  - Graduated 6-stage extraction pipeline on outputs + ingestion
  - WarmStateStore with CriticalState / StructuralState
  - CKF (Contextual Knowledge Fabric) 4-mode retrieval
  - Multi-window continuation with 3-way termination
  - Token measurement & budget validation
  - Message assembly per Axiom 4 (Model Ignorance)
  - QualityReport with real extraction & security stats
  - Session status & cost estimation
  - Budget cap enforcement
  - Streaming dispatch (§6.10.5)
  - Zero-LLM ingestion with graduated extraction (§2.5)
  - State export (§2.5)
  - Injection detection (advisory, §7.5)
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

# Deferred imports to avoid circular dependency chains.
# These modules import from crp.core.task_intent (which is in crp.core),
# creating a cycle via crp.core.__init__ → crp.core.orchestrator.
# We import them lazily at class init or first use instead.
from typing import TYPE_CHECKING, Any

from crp.core.app_profile import ApplicationProfile
from crp.core.config import ConfigurationResolver, CRPConfig
from crp.core.errors import (
    BudgetExhaustedError,
    RateLimitExceededError,
    SessionClosedError,
    SessionExpiredError,
    ValidationError,
)
from crp.core.session import (
    CostEstimate,
    EnvelopePreview,
    QualityReport,
    RemainingBudget,
    SessionHandle,
    SessionStatus,
)
from crp.core.window import (
    WindowDAG,
    resolve_generation_reserve,
)
from crp.providers.base import LLMProvider

if TYPE_CHECKING:
    from crp.ckf.fabric import ContextualKnowledgeFabric
    from crp.extraction.pipeline import ExtractionPipeline
    from crp.extraction.types import ExtractionResult as PipelineExtractionResult
    from crp.security.audit_trail import ComplianceAuditTrail
    from crp.security.compliance import ComplianceReporter, RiskClassifier
    from crp.security.consent import (
        ConsentManager,
        HumanOversightController,
        ProcessingRecordKeeper,
    )
    from crp.security.privacy import DataLineageTracker, PIIScanner, RetentionManager
    from crp.state.warm_store import WarmStateStore

from crp.core.dispatch_router import (
    DispatchMixin,
    StreamEvent,
    assemble_messages,  # noqa: F401  (re-exported for backwards compatibility)
)
from crp.core.extraction_facade import ExtractionMixin, ExtractionResult

logger = logging.getLogger("crp.orchestrator")


# ---------------------------------------------------------------------------
# Auto-detection: zero-config provider resolution
# ---------------------------------------------------------------------------

def _auto_detect_provider(model: str | None = None) -> LLMProvider:
    """Auto-detect the best available LLM provider.

    Resolution order:
      1. If ``model`` is given and matches a known provider pattern, use that.
      2. If ``OPENAI_API_KEY`` is set → OpenAIAdapter.
      3. If ``ANTHROPIC_API_KEY`` is set → AnthropicAdapter.
      4. If Ollama is running locally (``OLLAMA_HOST`` or localhost:11434) → OllamaAdapter.
      5. Raise a helpful error.
    """
    import os

    # Model-name heuristics
    if model:
        lower = model.lower()
        if any(lower.startswith(p) for p in ("gpt-", "o1", "o3", "o4")):
            from crp.providers.openai import OpenAIAdapter
            return OpenAIAdapter(model=model)
        if lower.startswith("claude"):
            from crp.providers.anthropic import AnthropicAdapter
            return AnthropicAdapter(model=model)
        # Any other model name → try Ollama
        from crp.providers.ollama import OllamaAdapter
        return OllamaAdapter(model=model)

    # Environment-based detection
    if os.environ.get("OPENAI_API_KEY"):
        from crp.providers.openai import OpenAIAdapter
        return OpenAIAdapter()

    if os.environ.get("ANTHROPIC_API_KEY"):
        from crp.providers.anthropic import AnthropicAdapter
        return AnthropicAdapter()

    # Try Ollama on localhost (fast-fail to keep init latency low)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        import urllib.request
        req = urllib.request.Request(f"{ollama_host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=0.5):
            from crp.providers.ollama import OllamaAdapter
            return OllamaAdapter()
    except Exception:
        pass

    raise ValueError(
        "No LLM provider detected. Either:\n"
        "  1. Pass provider=... explicitly:\n"
        "       from crp.providers import OpenAIAdapter\n"
        "       client = crp.Client(provider=OpenAIAdapter())\n"
        "  2. Pass model=... for auto-detection:\n"
        "       client = crp.Client(model='gpt-4o')\n"
        "  3. Set an API key environment variable:\n"
        "       OPENAI_API_KEY=sk-... or ANTHROPIC_API_KEY=...\n"
        "  4. Start Ollama locally:\n"
        "       ollama serve && ollama pull llama3.1"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(r"^[0-9a-fA-F\-]{36}$")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class CRPOrchestrator(DispatchMixin, ExtractionMixin):
    """Central dispatcher managing window lifecycle and protocol operations.

    Integrates ALL CRP subsystems:
    - ExtractionPipeline (graduated 6-stage extraction on outputs + ingestion)
    - WarmStateStore (persistent fact accumulation, ranking, aging)
    - CKF (ContextualKnowledgeFabric — 4-mode retrieval)
    - Envelope builder (6-phase budget-aware fact packing)
    - ContinuationManager (3-way termination, gap analysis, stitching)
    - SecurityManager (input validation, injection detection, RBAC, etc.)

    Args:
        provider: Primary LLM provider. ``llm`` is accepted as an alias.
        config: Optional ``CRPConfig`` instance.
        llm: Alias for ``provider`` (backwards compatibility).
        model: Model name for auto-detection when no provider is given.
        **init_kwargs: Extra configuration passed to ``ConfigurationResolver``.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        config: CRPConfig | None = None,
        *,
        llm: LLMProvider | None = None,
        model: str | None = None,
        app_profile: ApplicationProfile | None = None,
        **init_kwargs: Any,
    ) -> None:
        """Initialise the orchestrator and all subsystems."""
        # Deferred imports (avoid circular: orchestrator → ckf → extraction → core)
        from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
        from crp.continuation.manager import ContinuationConfig
        from crp.extraction.pipeline import ExtractionPipeline
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig

        # Accept 'llm' as alias for 'provider' (backwards compat with docs)
        resolved_provider = provider or llm
        if resolved_provider is None:
            resolved_provider = _auto_detect_provider(model=model)

        self._provider = resolved_provider
        self._app_profile = app_profile or ApplicationProfile()

        # Resolve configuration
        if config is not None:
            self._config = config
        else:
            self._config = ConfigurationResolver().resolve(**init_kwargs)

        # Session
        timeout = self._config.session_timeout
        now = time.time()
        self._session = SessionHandle(
            expires_at=now + timeout,
        )
        self._closed = False

        # Wire structured logging (§audit M2)
        from crp.observability.structured_logging import (
            configure_structured_logging,
            set_session_context,
        )
        configure_structured_logging()
        set_session_context(self._session.session_id)

        # Thread safety — RLock guards all mutable state (§audit C1)
        self._lock = threading.RLock()

        # Configurable thread pool for async dispatch (§audit C5)
        max_workers = self._config.get("max_threads", 2)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="crp-dispatch",
        )

        # Circuit breaker — prevent cascading failures on provider errors (§audit H4)
        from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        self._circuit_breaker = CircuitBreaker(CircuitBreakerConfig())

        # Counters
        self._windows_completed = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._continuation_windows_total = 0

        # DAG
        self._dag = WindowDAG()

        # ── Subsystems ─────────────────────────────────────────
        # Resource manager — centralized tracking (§audit R1)
        from crp.resources.resource_manager import MODEL_ESTIMATES, ResourceManager
        self._resource_manager = ResourceManager(
            budget_mb=self._config.get("memory_budget_mb", 512),
        )
        for model_name, est_mb in MODEL_ESTIMATES.items():
            self._resource_manager.register_model(model_name, est_mb)

        # Overhead manager — feature shedding cascade (§audit R2)
        from crp.resources.overhead_manager import OverheadBudgetManager
        self._overhead_manager = OverheadBudgetManager(
            max_overhead_pct=self._config.get("overhead_cap_pct", 15.0),
        )

        # Adaptive resource allocator — dynamic pipeline tuning (§resource-alloc)
        from crp.resources.adaptive_allocator import AdaptiveAllocator
        self._adaptive_allocator = AdaptiveAllocator(
            resource_manager=self._resource_manager,
            overhead_manager=self._overhead_manager,
            overhead_cap_pct=self._config.get("overhead_cap_pct", 15.0),
            idle_model_timeout_s=self._config.get("idle_model_timeout_s", 300.0),
        )

        # WarmStateStore — Tier 2 in-memory fact storage
        self._warm_store = WarmStateStore(WarmStoreConfig(
            max_facts=10_000,
        ))

        # Extraction pipeline — graduated 6-stage
        # Extraction pipeline — graduated 6-stage
        self._extraction = ExtractionPipeline(
            enable_stage_3=self._config.get("enable_stage_3", True),
            enable_stage_4=self._config.get("enable_stage_4", True),
            enable_stage_5=self._config.get("enable_stage_5", True),
            enable_stage_6=self._config.get("enable_stage_6", False),
        )

        # CKF — Contextual Knowledge Fabric (4-mode retrieval)
        self._ckf = ContextualKnowledgeFabric(CKFConfig(
            max_facts=10_000,
        ))

        # Cross-encoder model — lazy-loaded by default unless eager_load_models=True.
        # This keeps orchestrator init under ~1s instead of 15-30s.
        if self._config.get("eager_load_models", False):
            from crp.envelope.reranker import preload_cross_encoder
            preload_cross_encoder()

        # Injection detector (advisory, never blocks)
        # ── Security subsystems — delegated to SecurityManager (§audit4 CQ-C1) ──
        from crp.core.security_manager import SecurityManager
        self._security = SecurityManager(
            session_id=self._session.session_id,
            session_key=b"",  # session_binding creates its own key
            config=self._config,
        )
        # Backward-compatible attribute delegation
        self._injection_detector = self._security.injection_detector
        self._input_validator = self._security.input_validator
        self._session_binding = self._security.session_binding
        self._rbac = self._security.rbac
        self._integrity_chain = self._security.integrity_chain
        self._encryptor = self._security.encryptor
        self._quarantine = self._security.quarantine
        self._embedding_defense = self._security.embedding_defense
        self._pii_scanner = self._security.pii_scanner
        self._retention_manager = self._security.retention_manager
        self._erasure_manager = self._security.erasure_manager
        self._lineage_tracker = self._security.lineage_tracker
        self._consent_manager = self._security.consent_manager
        self._processing_records = self._security.processing_records
        self._human_oversight = self._security.human_oversight
        self._compliance_audit = self._security.compliance_audit
        self._risk_classifier = self._security.risk_classifier
        self._compliance_reporter = self._security.compliance_reporter

        # Source grounding — store original passages alongside facts (§17)
        from crp.advanced.source_grounding import SourceGroundingEngine
        self._source_grounding = SourceGroundingEngine()

        # Meta-learning scaffolds for small models (§19)
        from crp.advanced.meta_learning import MetaLearningConfig, MetaLearningEngine
        self._meta_learning = MetaLearningEngine(
            dispatch_fn=self._make_meta_dispatch_fn(),
            config=MetaLearningConfig(),
        )

        # Decision Provenance Engine — claim attribution & audit (§7.14.3)
        from crp.provenance import DecisionProvenanceEngine, ProvenanceConfig
        self._provenance_engine = DecisionProvenanceEngine(
            config=ProvenanceConfig(),
        )

        # LLM context curator — progressive understanding synthesis (§18)
        # V6 fix: Wire dispatch function at init time, not lazily during
        # dispatch. This avoids race conditions and stale provider references.
        from crp.advanced.curator import CurationConfig, LLMContextCurator

        def _curator_dispatch(sys_prompt: str, task: str, **kw):
            try:
                output, _ = self._provider.generate_chat(
                    [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": task},
                    ],
                    **kw,
                )
                return (output, {})
            except Exception as exc:
                logger.debug("Curator dispatch failed: %s", exc)
                return ("", {})

        self._curator = LLMContextCurator(
            dispatch_fn=_curator_dispatch,
            config=CurationConfig(),
        )

        # ── Wire embedding function globally (§5B.3, GAP A fix) ──
        # Lazy-loaded by default to keep init fast.  The model is loaded on
        # first actual semantic operation (CKF, gap analysis, etc.).
        if self._config.get("eager_load_models", False):
            from crp.envelope.decomposer import get_embedding_fn
            from crp.state.fact import set_embedding_function
            self._embedding_fn = get_embedding_fn()
            if self._embedding_fn is not None:
                set_embedding_function(self._embedding_fn)
                logger.info("Embedding function wired (all-MiniLM-L6-v2)")
        else:
            self._embedding_fn = None

        # Continuation manager — created per dispatch (stateful per task)
        self._continuation_config = ContinuationConfig(
            max_continuations=self._config.max_continuations,
            l3_extractor=self._make_l3_extractor(),
            embedding_fn=self._embedding_fn,
        )

        # Extraction history for quality gate anomaly detection (§audit4 REL-M1)
        self._extraction_history: deque[PipelineExtractionResult] = deque(maxlen=20)

        # ── Observability subsystems (§9) ─────────────────────
        # EventEmitter — protocol-wide event bus for all pipeline stages
        from crp.observability.events import EventEmitter
        self._emitter = EventEmitter()
        self._emitter.start()
        self._emitter.emit("session.created", {
            "session_id": self._session.session_id,
            "model": self._provider.model_name,
            "context_window": self._provider.context_window_size(),
        })

        # TelemetryWriter — per-window JSONL telemetry (optional file sink)
        from crp.observability.telemetry import TelemetryWriter
        telemetry_path = self._config.get("telemetry_path", "")
        self._telemetry_writer: TelemetryWriter | None = (
            TelemetryWriter(telemetry_path) if telemetry_path else None
        )

        # ── Advanced modules (previously disconnected) ────────
        # CQSDetector — detect context hunger in LLM output (§CQS)
        from crp.advanced.cqs import CQSDetector
        self._cqs_detector = CQSDetector()

        # CrossWindowValidator — consistency validation across windows (§cross-window)
        from crp.advanced.cross_window import CrossWindowValidator

        def _cross_window_dispatch(sys_prompt: str, task: str, **kw) -> tuple[str, Any]:
            try:
                output, _ = self._provider.generate_chat(
                    [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": task}],
                    **kw,
                )
                return output, {}
            except Exception:
                return "", {}

        self._cross_window_validator = CrossWindowValidator(
            dispatch_fn=_cross_window_dispatch,
            embedding_fn=self._embedding_fn,
        )

        # FeedbackLoop — fact confidence adjustment from user/system feedback (§feedback)
        from crp.advanced.feedback import FeedbackLoop
        self._feedback_loop = FeedbackLoop()

        # ParallelFanOut — parallel multi-task dispatch (§parallel)
        from crp.advanced.parallel import ParallelFanOut

        def _fanout_dispatch(sys_prompt: str, task: str, **kw) -> tuple[str, Any]:
            try:
                output, _ = self._provider.generate_chat(
                    [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": task}],
                    **kw,
                )
                return output, {}
            except Exception:
                return "", {}

        def _fanout_extract(text) -> list[dict[str, Any]]:
            result = self._extraction.extract(text, source_window_id="parallel-fanout")
            if not result.facts:
                return []
            return [{"id": f.id, "text": f.text, "confidence": f.confidence} for f in result.facts]

        self._parallel_fanout = ParallelFanOut(
            dispatch_fn=_fanout_dispatch,
            extract_fn=_fanout_extract,
            max_concurrent=self._config.get("parallel_max_concurrent", 4),
        )

        # ReviewCycleManager — periodic quality review during long generation (§review)
        from crp.advanced.review_cycle import ReviewCycleManager
        self._review_cycle = ReviewCycleManager(
            dispatch_fn=_cross_window_dispatch,
            model_review_capability=self._meta_learning.assess_model_capability()
            if hasattr(self._meta_learning, "assess_model_capability") else 1,
        )

        # ScaleModeSelector — processing mode selection based on task size (§scale)
        from crp.advanced.scale_mode import ScaleModeSelector
        self._scale_mode = ScaleModeSelector(
            context_window=self._provider.context_window_size(),
        )

        # ── Provider manager with fallback (§05, §F3 fix) ────
        from crp.providers.manager import LLMProviderManager
        self._provider_manager = LLMProviderManager(self._provider)

        # ---------- Compliance audit: session created (§7.14) ----------
        from crp.security.audit_trail import ComplianceEventType
        self._compliance_audit.record(
            ComplianceEventType.SESSION_CREATED,
            session_id=self._session.session_id,
            data={
                "protocol_version": self._session.protocol_version,
                "model": self._provider.model_name,
                "context_window": self._provider.context_window_size(),
            },
        )

        # Lock immutable fields after session creation
        self._config.lock()

        # Register atexit handler for graceful shutdown (§audit H6)
        atexit.register(self._atexit_close)

    # ------------------------------------------------------------------
    # Application-profile helpers (SPEC-008 extension)
    # ------------------------------------------------------------------

    def _app_context_manifest(self) -> Any | None:
        """Build a context manifest from the application profile if present."""
        if self._app_profile is None:
            return None
        try:
            manifest = self._app_profile.to_manifest()
            return manifest if manifest.sources else None
        except Exception as exc:
            logger.debug("Failed to build app-profile manifest: %s", exc)
            return None

    def _select_relay_strategy(self, has_registered_tools: bool = False) -> str:
        """Select a relay strategy based on the application capability contract.

        Strategy strings:
          - ``"push"``             — envelope-based dispatch (default)
          - ``"tools"``            — pull-based tool-mediated dispatch
          - ``"reflexive"``        — verify-then-refine
          - ``"progressive"``      — index → detail on demand
          - ``"stream_augmented"`` — real-time context injection
          - ``"agentic"``          — LLM-in-the-loop cognitive engine
        """
        profile = self._app_profile
        if profile is None:
            return "push"

        provider_supports_tools = self._provider.supports_tools()
        if has_registered_tools and provider_supports_tools:
            # Registered SDK tools run through the client's own tool loop.
            return "tools"
        if profile.supports_tools() and provider_supports_tools:
            return "tools"

        strategy = profile.context_strategy
        if strategy.value == "rag":
            return "push"
        if strategy.value == "summarization":
            return "reflexive"
        if strategy.value == "sliding_window":
            return "progressive"
        if strategy.value == "long_context":
            return "stream_augmented"
        if strategy.value == "hybrid":
            return "agentic"
        return "push"

    def dispatch_with_strategy(
        self,
        strategy: str,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Route a dispatch to the named relay strategy.

        Unknown strategies fall back to push-based dispatch with a warning.
        """
        _strategy_map: dict[str, Callable[..., tuple[str, QualityReport]]] = {
            "push": self.dispatch,
            "tools": self.dispatch_with_tools,
            "reflexive": self.dispatch_reflexive,
            "progressive": self.dispatch_progressive,
            "stream_augmented": self.dispatch_stream_augmented,
            "agentic": self.dispatch_agentic,
        }
        fn = _strategy_map.get(strategy)
        if fn is None:
            logger.warning("Unknown relay strategy '%s'; falling back to push", strategy)
            fn = self.dispatch
        return fn(system_prompt, task_input, **kwargs)

    # ------------------------------------------------------------------
    # L3 LLM-assisted requirement extraction (§5B.1)
    # ------------------------------------------------------------------

    def _make_l3_extractor(self):
        """Create L3 extractor callback that uses the LLM provider.

        Returns a callable that takes task_intent (str) and returns
        a list of Requirement objects. Used by ContinuationManager for
        LLM-assisted requirement discovery beyond L1 regex / L2 semantic.

        V4 fix: Budget-aware — caps input tokens, tracks overhead in
        telemetry, and limits max_tokens to avoid unbounded LLM cost.
        This is an analytical side-call (not content generation) so a
        full envelope pipeline is unnecessary, but we enforce the budget
        formula and log the interaction.
        """
        def _extract_via_llm(task_intent: str):
            from crp.continuation.gap import Requirement

            if self._provider is None:
                return []
            try:
                # Budget-aware: cap task intent to fit within a modest budget
                context_window = self._provider.context_window_size()
                # Reserve 512 for output, ~100 for system prompt overhead
                max_input_chars = min(2000, int(context_window * 3.3 * 0.5))
                truncated_intent = task_intent[:max_input_chars]

                prompt = (
                    "Analyze the following task and list the distinct requirements "
                    "that must be fulfilled. Return each requirement on its own line "
                    "prefixed with '- '. Be specific and concise.\n\n"
                    f"Task: {truncated_intent}"
                )
                messages = [
                    {"role": "system", "content": "You are a task analyst. Extract requirements."},
                    {"role": "user", "content": prompt},
                ]
                # Track token cost for telemetry
                input_tokens = self._provider.count_tokens(prompt) + self._provider.count_tokens(messages[0]["content"])
                logger.debug("L3 extractor: %d input tokens (analytical side-call)", input_tokens)

                output, _ = self._provider.generate_chat(messages, max_tokens=512)
                requirements: list[Requirement] = []
                for line in output.splitlines():
                    line = line.strip()
                    if line.startswith("- ") and len(line) > 4:
                        requirements.append(Requirement(
                            text=line[2:].strip(),
                            level=3,
                            category="llm_extracted",
                            weight=1.0,
                        ))
                logger.debug("L3 extractor: %d requirements extracted", len(requirements))
                return requirements
            except Exception as exc:
                logger.debug("L3 extractor failed (non-fatal): %s", exc)
                return []  # L3 failure is non-fatal (§5B.1)

        return _extract_via_llm

    # ------------------------------------------------------------------
    # Meta-learning dispatch function (§19 ORC support)
    # ------------------------------------------------------------------

    def _make_meta_dispatch_fn(self):
        """Create a dispatch callback for MetaLearningEngine.

        MetaLearningEngine.dispatch_fn signature: (system_prompt, user_prompt) -> (output, meta).
        Used for ORC (Orchestrated Reasoning Chains) LLM-assisted decomposition.

        V5 fix: Budget-aware — caps prompt to half context window, logs
        token cost, and stores extracted facts from meta-learning output
        back into the warm store so they're not ephemeral.
        """
        def _meta_dispatch(system_prompt: str, user_prompt: str):
            if self._provider is None:
                return ("", {})
            try:
                # Budget-aware: cap user prompt to fit within context window
                context_window = self._provider.context_window_size()
                sys_tokens = self._provider.count_tokens(system_prompt)
                max_user_tokens = context_window - sys_tokens - 1024  # reserve for output
                user_tokens = self._provider.count_tokens(user_prompt)
                if user_tokens > max_user_tokens > 0:
                    # Truncate proportionally
                    ratio = max_user_tokens / user_tokens
                    user_prompt = user_prompt[:int(len(user_prompt) * ratio)]

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                logger.debug(
                    "Meta-learning dispatch: %d+%d input tokens (ORC side-call)",
                    sys_tokens, self._provider.count_tokens(user_prompt),
                )
                output, finish_reason = self._provider.generate_chat(messages, max_tokens=1024)

                # Store extracted facts from meta-learning output so they're
                # not ephemeral (they feed back into CKF and warm store)
                if output and len(output) > 50:
                    try:
                        meta_result = self._extraction.extract(
                            output, source_window_id="meta-learning",
                        )
                        if meta_result.facts:
                            self._warm_store.add_facts(meta_result.facts)
                            self._ckf.store(meta_result.facts, window_id="meta-learning")
                            logger.debug(
                                "Meta-learning: %d facts extracted and stored",
                                len(meta_result.facts),
                            )
                    except Exception as exc:
                        logger.debug("Meta-learning extraction failed: %s", exc)

                return (output, {"finish_reason": finish_reason})
            except Exception as exc:
                logger.debug("Meta-learning dispatch failed: %s", exc)
                return ("", {})

        return _meta_dispatch

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _check_session(self) -> None:
        """Raise if session is closed or expired.

        Raises:
            SessionClosedError: If the session has been closed.
            SessionExpiredError: If the session has expired.
        """
        if self._closed:
            raise SessionClosedError()
        if self._session.is_expired:
            raise SessionExpiredError()

    def _check_budget(self, input_tokens: int) -> None:
        """Raise BudgetExhaustedError if caps would be exceeded.

        Args:
            input_tokens: Input tokens required for the next operation.

        Raises:
            BudgetExhaustedError: If a window or token cap would be exceeded.
        """
        max_w = self._config.max_windows_per_session
        if max_w and self._windows_completed >= max_w:
            raise BudgetExhaustedError(
                "Max windows per session exceeded",
                limit=max_w,
                used=self._windows_completed,
            )
        max_in = self._config.max_total_input_tokens
        if max_in and (self._total_input_tokens + input_tokens) > max_in:
            raise BudgetExhaustedError(
                "Max total input tokens exceeded",
                limit=max_in,
                used=self._total_input_tokens,
                requested=input_tokens,
            )

    # ------------------------------------------------------------------
    # Internal: extraction + fact storage
    def session_status(self) -> SessionStatus:
        """Get live session metrics.

        Returns:
            A ``SessionStatus`` with current counters and remaining budget.

        Raises:
            SessionClosedError: If the session is closed.
            SessionExpiredError: If the session has expired.
            RateLimitExceededError: If RBAC denies READ_STATE.
        """
        self._check_session()

        # RBAC permission check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.READ_STATE)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)

        remaining = None
        max_w = self._config.max_windows_per_session
        max_in = self._config.max_total_input_tokens
        max_out = self._config.max_total_output_tokens
        if max_w or max_in or max_out:
            remaining = RemainingBudget(
                windows_remaining=(max_w - self._windows_completed) if max_w else None,
                input_tokens_remaining=(max_in - self._total_input_tokens) if max_in else None,
                output_tokens_remaining=(max_out - self._total_output_tokens) if max_out else None,
            )

        # Overhead from continuation windows
        total = self._windows_completed
        overhead = self._continuation_windows_total / total if total > 0 else 0.0

        # USD cost — compute from provider pricing if available
        cost: float | None = None
        in_cost, out_cost = self._provider.cost_per_1k_tokens()
        if in_cost > 0 or out_cost > 0:
            cost = (
                (self._total_input_tokens / 1000 * in_cost)
                + (self._total_output_tokens / 1000 * out_cost)
            )

        return SessionStatus(
            session_id=self._session.session_id,
            windows_completed=self._windows_completed,
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            facts_in_warm_state=self._warm_store.fact_count,
            overhead_ratio=overhead,
            remaining_budget=remaining,
            total_cost=cost,
        )

    def estimate_session(
        self,
        system_prompt: str = "",
        task_input: str = "",
        *,
        planned_dispatches: int = 1,
        avg_output_tokens: int | None = None,
    ) -> CostEstimate:
        """Pre-flight cost estimation WITHOUT executing LLM calls.

        Args:
            system_prompt: Representative system prompt for token estimation.
            task_input: Representative task input for token estimation.
            planned_dispatches: Number of dispatches planned (default: 1).
            avg_output_tokens: Expected average output tokens per dispatch.
                If None, assumes model uses full generation reserve.

        Returns:
            CostEstimate with token estimates and USD cost (if pricing known).
        """
        self._check_session()

        # RBAC permission check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.READ_STATE)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)

        s_tokens = self._provider.count_tokens(system_prompt) if system_prompt else 0
        t_tokens = self._provider.count_tokens(task_input) if task_input else 0
        context_window = self._provider.context_window_size()
        g = resolve_generation_reserve(
            None, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        estimated_input_per = s_tokens + t_tokens
        estimated_output_per = avg_output_tokens or g
        total_input = estimated_input_per * planned_dispatches
        total_output = estimated_output_per * planned_dispatches

        # USD cost estimation via provider pricing
        cost_usd: float | None = None
        in_cost, out_cost = self._provider.cost_per_1k_tokens()
        if in_cost > 0 or out_cost > 0:
            cost_usd = (total_input / 1000 * in_cost) + (total_output / 1000 * out_cost)

        confidence = "medium"
        if planned_dispatches > 10:
            confidence = "low"
        elif planned_dispatches > 1 and system_prompt and task_input:
            confidence = "high"

        return CostEstimate(
            estimated_windows=planned_dispatches,
            estimated_input_tokens=total_input,
            estimated_output_tokens=total_output,
            estimated_cost_usd=cost_usd,
            confidence=confidence,
        )

    def preview_envelope(
        self, system_prompt: str, task_input: str
    ) -> EnvelopePreview:
        """Inspect envelope contents WITHOUT dispatching.

        Args:
            system_prompt: System prompt for the dispatch.
            task_input: User task input.

        Returns:
            An ``EnvelopePreview`` with token counts and included facts.

        Raises:
            SessionClosedError: If the session is closed.
            SessionExpiredError: If the session has expired.
            RateLimitExceededError: If RBAC denies READ_ENVELOPE.
        """
        self._check_session()

        # RBAC permission check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.READ_ENVELOPE)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)

        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()
        g = resolve_generation_reserve(
            None, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # Build a real envelope preview from accumulated facts
        envelope_result = self._build_envelope(system_prompt, task_input, g)

        return EnvelopePreview(
            total_tokens=s_tokens + t_tokens + envelope_result.envelope_tokens,
            envelope_tokens=envelope_result.envelope_tokens,
            generation_reserve=g,
            facts_included=envelope_result.facts_included,
            facts_available=self._warm_store.fact_count,
            saturation=envelope_result.saturation,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, **kwargs: Any) -> None:
        """Apply runtime configuration changes (mutable fields only).

        Args:
            **kwargs: Key-value pairs to update in the resolved config.

        Raises:
            SessionClosedError: If the session is closed.
            SessionExpiredError: If the session has expired.
            RateLimitExceededError: If RBAC denies CONFIGURE.
        """
        self._check_session()

        # RBAC permission check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.CONFIGURE)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)


        self._config.update(kwargs)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_session(self) -> None:
        """Clear warm state, CKF, event log, DAG. Keeps session open.

        Raises:
            SessionClosedError: If the session is closed.
            SessionExpiredError: If the session has expired.
            RateLimitExceededError: If RBAC denies MANAGE_SESSIONS.
        """
        self._check_session()

        # ---------- Compliance imports (§7.14) ----------
        from crp.security.audit_trail import ComplianceEventType

        # ---------- Compliance audit: session reset (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_DELETED,
            session_id=self._session.session_id,
            data={
                "operation": "reset_session",
                "facts_deleted": self._warm_store.fact_count,
                "windows_reset": self._windows_completed,
            },
        )

        # RBAC permission check (§7.10) — destructive, requires ADMIN
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.MANAGE_SESSIONS)
        if not perm_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RBAC_DENIED,
                session_id=self._session.session_id,
                data={"operation": "reset_session", "reason": perm_result.reason},
            )
            raise RateLimitExceededError(perm_result.reason)
        from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
        from crp.security.integrity import FactIntegrityChain
        from crp.security.quarantine import IngestQuarantine
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig

        self._windows_completed = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._continuation_windows_total = 0
        self._dag.clear()
        # Reset all subsystems
        self._warm_store = WarmStateStore(WarmStoreConfig(max_facts=10_000))
        self._ckf = ContextualKnowledgeFabric(CKFConfig(max_facts=10_000))
        self._extraction_history.clear()
        # Reset security subsystems
        self._integrity_chain = FactIntegrityChain(
            session_key=self._session_binding.session_key,
        )
        self._quarantine = IngestQuarantine()
        self._rbac.reset_limits()
        logger.info("Session %s reset (all subsystems)", self._session.session_id)

    # ------------------------------------------------------------------
    # Public API: Observability (§9 — EventEmitter access)
    # ------------------------------------------------------------------

    @property
    def emitter(self):
        """Protocol event bus for subscribing to events."""
        return self._emitter

    def on(self, event_type: str, listener) -> None:
        """Subscribe to a protocol event (convenience wrapper).

        Usage::

            def on_dispatch(event):
                print(f"Dispatch completed: {event.data}")

            orch.on("dispatch.completed", on_dispatch)
        """
        self._emitter.on(event_type, listener)

    # ------------------------------------------------------------------
    # Public API: Feedback Loop (§feedback — fact confidence adjustment)
    # ------------------------------------------------------------------

    @property
    def feedback(self):
        """Access the feedback loop for fact confidence adjustments."""
        return self._feedback_loop

    def boost_fact(self, fact_id: str, delta: float = 0.1, reason: str = "") -> None:
        """Boost a fact's confidence (positive feedback).

        Args:
            fact_id: Fact identifier.
            delta: Amount to increase confidence.
            reason: Optional reason for the feedback.
        """
        self._feedback_loop.boost_confidence(fact_id, delta, reason)
        self._emitter.emit("fact.boosted", {"fact_id": fact_id, "delta": delta})

    def penalize_fact(self, fact_id: str, delta: float = -0.2, reason: str = "") -> None:
        """Penalize a fact's confidence (negative feedback).

        Args:
            fact_id: Fact identifier.
            delta: Amount to decrease confidence.
            reason: Optional reason for the feedback.
        """
        self._feedback_loop.penalize_confidence(fact_id, delta, reason)
        self._emitter.emit("fact.penalized", {"fact_id": fact_id, "delta": delta})

    def reject_fact(self, fact_id: str, reason: str = "") -> None:
        """Reject a fact entirely (user override).

        Args:
            fact_id: Fact identifier.
            reason: Optional reason for rejection.
        """
        self._feedback_loop.reject_fact(fact_id, reason)
        self._emitter.emit("fact.rejected", {"fact_id": fact_id, "reason": reason})

    # ------------------------------------------------------------------
    # Public API: Provider manager (§05 — multi-provider routing)
    # ------------------------------------------------------------------

    def register_provider(self, provider: LLMProvider) -> None:
        """Register an additional LLM provider for fallback routing.

        Args:
            provider: Additional provider to register.
        """
        self._provider_manager.register(provider)
        self._emitter.emit("provider.connected", {
            "model": provider.model_name,
        })

    # ------------------------------------------------------------------
    # Public API: Parallel fan-out (§parallel)
    # ------------------------------------------------------------------

    @property
    def parallel(self):
        """Parallel fan-out engine for multi-task dispatch."""
        return self._parallel_fanout

    # ------------------------------------------------------------------
    # Session close
    # ------------------------------------------------------------------

    def _atexit_close(self) -> None:
        """Safety-net close called by atexit — never raises (§audit H6).

        This method swallows all exceptions to avoid crashes during Python
        interpreter shutdown.
        """
        try:
            # Suppress logging during shutdown to avoid I/O-on-closed-file errors
            logging.disable(logging.CRITICAL)
            # Use timeout to prevent deadlock if lock is held (§audit3 ORCH-C5)
            acquired = self._lock.acquire(timeout=5.0)
            if acquired:
                try:
                    self._close_locked()
                finally:
                    self._lock.release()
        except Exception:  # noqa: BLE001
            pass
        finally:
            logging.disable(logging.NOTSET)

    def close(self) -> None:
        """Close session — flush warm→cold, persist CKF, zero keys (§2.5).

        This method is thread-safe and idempotent.
        """
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        """Internal close implementation — called under ``self._lock``."""
        if self._closed:
            return

        # Shut down thread pool executor (§audit3: wait for in-flight tasks)
        self._executor.shutdown(wait=True)

        # ---------- Compliance imports (§7.14) ----------
        from crp.security.audit_trail import ComplianceEventType

        # ---------- Compliance audit: session closing (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.SESSION_CLOSED,
            session_id=self._session.session_id,
            data={
                "windows_completed": self._windows_completed,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "facts_in_warm_store": self._warm_store.fact_count,
                "audit_entries": self._compliance_audit.entry_count,
                "processing_records": self._processing_records.activity_count,
                "retention_tracked": self._retention_manager.tracked_count,
                "lineage_tracked": len(self._lineage_tracker.to_dict().get("entries", {})),
            },
        )

        # Flush warm state facts → CKF cold storage for cross-session retrieval
        try:
            # Validate session_id to prevent path traversal (§audit5 SEC-M1)
            sid = self._session.session_id
            if not _UUID_RE.fullmatch(sid):
                logger.error("Invalid session_id format in close: %r", sid[:40])
                raise ValueError(f"session_id is not a valid UUID: {sid!r:.40}")
            persist_dir = os.path.join(
                os.environ.get("CRP_DATA_DIR", "."),
                "crp_sessions",
            )
            os.makedirs(persist_dir, exist_ok=True)
            persist_path = os.path.join(
                persist_dir,
                f"{sid}.json",
            )
            self._ckf.persist(persist_path)
            logger.debug("CKF persisted to cold storage: %s", persist_path)
        except Exception as exc:
            logger.warning("CKF persistence failed: %s", exc)

        # Persist encrypted event log (§7.3)
        if self._config.get("encrypt_cold_state", True):
            try:
                event_data = json.dumps({
                    "session_id": self._session.session_id,
                    "windows_completed": self._windows_completed,
                    "integrity_chain": self._integrity_chain.to_dict(),
                }, separators=(",", ":")).encode("utf-8")
                persist_dir = os.path.join(
                    os.environ.get("CRP_DATA_DIR", "."),
                    "crp_sessions",
                )
                os.makedirs(persist_dir, exist_ok=True)
                event_blob = self._encryptor.encrypt_event_log(event_data)
                event_path = os.path.join(
                    persist_dir,
                    f"{self._session.session_id}.events.bin",
                )
                with open(event_path, "wb") as f:
                    f.write(event_blob.ciphertext)
                logger.debug("Encrypted event log persisted: %s", event_path)
            except Exception as exc:
                logger.debug("Event log persistence skipped: %s", exc)

        # ---------- Persist compliance audit trail (§7.14) ----------
        try:
            persist_dir = os.path.join(
                os.environ.get("CRP_DATA_DIR", "."),
                "crp_sessions",
            )
            os.makedirs(persist_dir, exist_ok=True)
            audit_path = os.path.join(
                persist_dir,
                f"{self._session.session_id}.audit.jsonl",
            )
            audit_jsonl = self._compliance_audit.export_jsonl()
            with open(audit_path, "w", encoding="utf-8") as f:
                f.write(audit_jsonl)
            logger.debug("Compliance audit trail persisted: %s (%d entries)",
                         audit_path, self._compliance_audit.entry_count)
        except Exception as exc:
            logger.error("Compliance audit trail persistence failed: %s", exc)

        # Zero out sensitive state from memory
        self._extraction_history.clear()

        # Final resource GC
        mgr = getattr(self, "_resource_manager", None)
        if mgr is not None:
            mgr.run_gc()

        self._closed = True
        logger.info(
            "Session %s closed — %d windows, %d input tokens, %d output tokens",
            self._session.session_id,
            self._windows_completed,
            self._total_input_tokens,
            self._total_output_tokens,
        )

        # Emit session.closed event and stop emitter (§9)
        self._emitter.emit("session.closed", {
            "session_id": self._session.session_id,
            "windows_completed": self._windows_completed,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        })
        self._emitter.stop()

        # Close telemetry writer if active (§9, D8 fix)
        if self._telemetry_writer is not None:
            self._telemetry_writer.close()
            self._telemetry_writer = None

        # Opportunistic session file cleanup (§audit H11)
        try:
            from crp.state.session_cleanup import cleanup_expired_sessions
            cleanup_expired_sessions()
        except Exception:  # noqa: BLE001
            pass  # best-effort, don't fail close

    # ------------------------------------------------------------------
    # Session resume — cross-session continuity (§2.5)
    # ------------------------------------------------------------------

    @classmethod
    def resume(
        cls,
        session_id: str,
        provider: LLMProvider | None = None,
        *,
        llm: LLMProvider | None = None,
        data_dir: str | None = None,
        **kwargs: Any,
    ) -> CRPOrchestrator:
        """Resume a previously closed session by restoring CKF state.

        Loads persisted facts from cold storage into a new orchestrator
        instance, providing cross-session knowledge continuity.

        Args:
            session_id: The session_id from the previous session.
            provider: LLM provider to use for the resumed session.
            llm: Alias for ``provider``.
            data_dir: Override for CRP_DATA_DIR (default: env or '.').
            **kwargs: Additional arguments forwarded to the orchestrator init.

        Returns:
            A new CRPOrchestrator with the previous session's facts loaded.

        Raises:
            ValidationError: If ``session_id`` is not a valid UUID.
        """
        base_dir = data_dir or os.environ.get("CRP_DATA_DIR", ".")
        # Validate session_id to prevent path traversal (§audit4 SEC-M2)
        if not _UUID_RE.fullmatch(session_id):
            raise ValidationError(
                f"Invalid session_id format: expected UUID, got {session_id!r:.40}"
            )
        persist_path = os.path.join(base_dir, "crp_sessions", f"{session_id}.json")

        # Create new orchestrator
        orch = cls(provider=provider, llm=llm, **kwargs)

        # Restore CKF state from cold storage
        if os.path.exists(persist_path):
            try:
                orch._ckf.restore(persist_path)
                logger.info(
                    "Resumed session: loaded CKF from %s (%d facts)",
                    persist_path,
                    len(orch._ckf._warm._facts),
                )
                # Pre-populate WarmStore with restored CKF facts for
                # immediate availability in first envelope
                restored_facts = [sf.fact for sf in orch._ckf._warm._facts.values()]
                if restored_facts:
                    orch._warm_store.add_facts(restored_facts)
                    logger.info("Restored %d facts into WarmStore", len(restored_facts))
            except Exception as exc:
                logger.warning("CKF restore failed for session %s: %s", session_id, exc)
        else:
            logger.warning("No persisted session found at %s", persist_path)

        return orch

    # ------------------------------------------------------------------
    # Streaming dispatch (§6.10.5)
    def export_state(self, fmt: str | None = None) -> bytes:
        """Export session state as encrypted bytes (§2.5).

        Includes warm store facts, critical state, structural state, and CKF health.
        Embeddings are NOT exported (§7.11) — recomputed on import.

        Args:
            fmt: Export format (reserved, currently only 'json' supported).

        Returns:
            Encrypted bytes (AES-256-GCM with session-bound key).

        Raises:
            SessionClosedError: If the session is closed.
            SessionExpiredError: If the session has expired.
            RateLimitExceededError: If RBAC denies EXPORT_STATE.
        """
        self._check_session()

        # ---------- Compliance imports (§7.14) ----------
        from crp.security.audit_trail import ComplianceEventType
        from crp.security.consent import ProcessingPurpose

        # ---------- Consent verification for export (§7.13) ----------
        self._consent_manager.check_required(ProcessingPurpose.EXPORT)

        # RBAC permission check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.EXPORT_STATE)
        if not perm_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RBAC_DENIED,
                session_id=self._session.session_id,
                data={"operation": "export_state", "reason": perm_result.reason},
            )
            raise RateLimitExceededError(perm_result.reason)

        # ---------- Compliance audit: export started (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_EXPORTED,
            session_id=self._session.session_id,
            data={
                "operation": "export_state",
                "phase": "started",
                "format": fmt or "json",
                "facts_count": self._warm_store.fact_count,
            },
        )

        # ---------- Processing record for export (§7.13 — GDPR Art. 30) ----------
        self._processing_records.record(
            purpose=ProcessingPurpose.EXPORT,
            data_categories=["session_state", "warm_store_facts", "ckf_state"],
            legal_basis="legitimate_interest",
            input_size_bytes=0,
            output_size_bytes=0,
            automated_decision=True,
            human_oversight=False,
            retention_period="external",
        )

        ckf_health = self._ckf.health()
        state = {
            "session_id": self._session.session_id,
            "protocol_version": self._session.protocol_version,
            "windows_completed": self._windows_completed,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "facts_in_warm_state": self._warm_store.fact_count,
            "ckf_facts": ckf_health.fact_count,
            "ckf_edges": ckf_health.edge_count,
            "ckf_communities": ckf_health.community_count,
            "warm_store": self._warm_store.to_dict(),
            "format": fmt or "json",
            "exported_at": time.time(),
        }

        # Strip embeddings from export (§7.11)
        from crp.security.embedding_defense import EmbeddingDefense
        state = EmbeddingDefense.strip_embeddings_for_export(state)

        # Include integrity chain signature for verification on import
        if self._integrity_chain.size > 0:
            try:
                state["integrity_chain_signature"] = self._integrity_chain.chain_signature()
            except ValueError:
                pass  # No session key — skip chain signature

        plaintext = json.dumps(state, separators=(",", ":")).encode("utf-8")

        # Encrypt with session-bound AES-256-GCM key (§7.3)
        blob = self._encryptor.encrypt_cold_state(plaintext)

        # ---------- Compliance audit: export completed (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_EXPORTED,
            session_id=self._session.session_id,
            data={
                "operation": "export_state",
                "phase": "completed",
                "format": fmt or "json",
                "ciphertext_bytes": len(blob.ciphertext),
                "facts_exported": self._warm_store.fact_count,
            },
        )

        return blob.ciphertext

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session(self) -> SessionHandle:
        """Return the session."""
        return self._session

    @property
    def dag(self) -> WindowDAG:
        """Return the dag."""
        return self._dag

    @property
    def config(self) -> CRPConfig:
        """Return the config."""
        return self._config

    @property
    def warm_store(self) -> WarmStateStore:
        """Access the WarmStateStore for direct fact operations."""
        return self._warm_store

    @property
    def ckf(self) -> ContextualKnowledgeFabric:
        """Access the CKF for 4-mode retrieval queries."""
        return self._ckf

    @property
    def compliance_audit(self) -> ComplianceAuditTrail:
        """Access the compliance audit trail for inspection (§7.14)."""
        return self._compliance_audit

    @property
    def pii_scanner(self) -> PIIScanner:
        """Access the PII scanner (§7.12)."""
        return self._pii_scanner

    @property
    def consent_manager(self) -> ConsentManager:
        """Access the consent manager (§7.13)."""
        return self._consent_manager

    @property
    def processing_records(self) -> ProcessingRecordKeeper:
        """Access the processing record keeper — GDPR Art. 30 (§7.13)."""
        return self._processing_records

    @property
    def retention_manager(self) -> RetentionManager:
        """Access the retention manager (§7.12)."""
        return self._retention_manager

    @property
    def lineage_tracker(self) -> DataLineageTracker:
        """Access the data lineage tracker (§7.12)."""
        return self._lineage_tracker

    @property
    def human_oversight(self) -> HumanOversightController:
        """Access the human oversight controller — EU AI Act Art. 14 (§7.13)."""
        return self._human_oversight

    @property
    def compliance_reporter(self) -> ComplianceReporter:
        """Access the compliance reporter (§7.15)."""
        return self._compliance_reporter

    @property
    def risk_classifier(self) -> RiskClassifier:
        """Access the risk classifier — EU AI Act Art. 6 (§7.15)."""
        return self._risk_classifier

    @property
    def extraction_pipeline(self) -> ExtractionPipeline:
        """Access the extraction pipeline for configuration."""
        return self._extraction

    # ------------------------------------------------------------------
    # Async API (§6.10) — asyncio.to_thread bridge
    # ------------------------------------------------------------------

    async def async_dispatch(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Async version of dispatch() — runs in a configurable thread pool.

        Uses the orchestrator's own ThreadPoolExecutor (sized via
        ``max_threads`` config) instead of the default asyncio executor,
        which prevents thread-pool saturation under concurrent load.

        Use from async code (FastAPI, asyncio, etc.)::

            output, report = await client.async_dispatch(
                "You are helpful.", "Explain CRP."
            )
        """
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, lambda: self.dispatch(system_prompt, task_input, **kwargs)
        )

    async def async_ingest(
        self,
        raw_text: str,
        *,
        source_label: str = "",
    ) -> ExtractionResult:
        """Async version of ingest() — runs in the orchestrator's thread pool."""
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, lambda: self.ingest(raw_text, source_label=source_label)
        )

    async def async_close(self) -> None:
        """Async version of close() — runs in the orchestrator's thread pool."""
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self.close)

    async def async_dispatch_stream(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ):
        """Async streaming dispatch — yields StreamEvent objects.

        Usage::

            async for event in client.async_dispatch_stream(
                "You are helpful.", "Explain CRP."
            ):
                if event.event_type == "token":
                    print(event.data, end="")
        """
        import asyncio
        import queue

        q: queue.Queue[StreamEvent | None] = queue.Queue(maxsize=1000)  # Bounded queue (§audit M12)

        def _produce():
            try:
                for event in self.dispatch_stream(
                    system_prompt, task_input, **kwargs
                ):
                    q.put(event)
            finally:
                q.put(None)  # Sentinel

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(self._executor, _produce)

        while True:
            event = await asyncio.to_thread(q.get)
            if event is None:
                break
            yield event

        await fut  # Propagate exceptions
