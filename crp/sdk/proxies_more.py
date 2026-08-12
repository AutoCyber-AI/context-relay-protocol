# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Additional curated namespace proxies for the progressive CRP SDK (SPEC-032).

These proxies expose the remaining top-level CRP subsystems through a stable,
discoverable SDK surface. Each proxy receives the orchestrator instance and uses
lazy imports to avoid heavy dependencies and circular imports.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger("crp.sdk.proxies_more")


# ── Core ────────────────────────────────────────────────────────────────────


class _CoreProxy:
    """Core orchestrator and session primitives proxy.

    Exposes the live orchestrator, its configuration, session handle, window
    DAG, manifest ledger, and LLM-in-the-loop facilitator.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def orchestrator(self) -> Any:
        """Return the live ``CRPOrchestrator`` instance.

        Returns:
            CRPOrchestrator instance.
        """
        return self._orchestrator

    def config(self) -> Any:
        """Return the orchestrator's core configuration object.

        Returns:
            CRPConfig instance.
        """
        return getattr(self._orchestrator, "_config", None)

    def session(self) -> Any:
        """Return the current ``SessionHandle``.

        Returns:
            SessionHandle instance.
        """
        return getattr(self._orchestrator, "_session", None)

    def dag(self) -> Any:
        """Return a fresh ``WindowDAG`` instance.

        Returns:
            WindowDAG instance.
        """
        from crp.core.window import WindowDAG

        return WindowDAG()

    def ledger(self) -> Any:
        """Return a ``ManifestLedger`` bound to the current session.

        Returns:
            ManifestLedger instance.
        """
        from crp.core.manifest_ledger import ManifestLedger

        session_id = ""
        session = getattr(self._orchestrator, "_session", None)
        if session is not None:
            session_id = getattr(session, "session_id", "") or session_id
        return ManifestLedger(session_id=session_id)

    def facilitator(self) -> Any:
        """Return a ``CRPFacilitator`` wired to the orchestrator's provider.

        Returns:
            CRPFacilitator instance.
        """
        from crp.core.facilitator import CRPFacilitator

        return CRPFacilitator(
            provider=getattr(self._orchestrator, "_provider", None),
            warm_store=getattr(self._orchestrator, "warm_store", None),
        )


# ── Continuation ────────────────────────────────────────────────────────────


class _ContinuationProxy:
    """Continuation manager and helper proxy (SPEC-004).

    Exposes the continuation manager, document map, chain degradation,
    information-flow monitor, quality monitor, voice profile, and residual-gap
    anchor.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def manager(self) -> Any:
        """Return a default ``ContinuationManager``.

        Returns:
            ContinuationManager instance.
        """
        from crp.continuation.manager import ContinuationConfig, ContinuationManager

        return ContinuationManager(ContinuationConfig())

    def document_map(self) -> Any:
        """Return a fresh ``DocumentMap``.

        Returns:
            DocumentMap instance.
        """
        from crp.continuation.document_map import DocumentMap

        return DocumentMap()

    def degradation(self) -> Any:
        """Return a fresh ``ChainDegradation`` tracker.

        Returns:
            ChainDegradation instance.
        """
        from crp.continuation.degradation import ChainDegradation

        return ChainDegradation()

    def flow_monitor(self) -> Any:
        """Return a fresh ``InformationFlowMonitor``.

        Returns:
            InformationFlowMonitor instance.
        """
        from crp.continuation.flow import InformationFlowMonitor

        return InformationFlowMonitor()

    def quality_monitor(self) -> Any:
        """Return a fresh ``GenerationQualityMonitor``.

        Returns:
            GenerationQualityMonitor instance.
        """
        from crp.continuation.quality_monitor import GenerationQualityMonitor

        return GenerationQualityMonitor()

    def voice_profile(self) -> Any:
        """Return a default ``VoiceProfile``.

        Returns:
            VoiceProfile instance.
        """
        from crp.continuation.voice import VoiceProfile

        return VoiceProfile.from_dict({})

    def residual_gap(self) -> Any:
        """Return a fresh ``ResidualTaskAnchor``.

        Returns:
            ResidualTaskAnchor instance.
        """
        from crp.continuation.flow import ResidualTaskAnchor

        return ResidualTaskAnchor()


# ── Envelope ────────────────────────────────────────────────────────────────


class _EnvelopeProxy:
    """Envelope construction proxy (SPEC-003, SPEC-024).

    Exposes the envelope builder, packer, reranker, CDR ranker, and formatter.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def builder(self) -> Any:
        """Return the envelope ``construct`` function and ``EnvelopeState``.

        Returns:
            SimpleNamespace with ``construct`` and ``EnvelopeState``.
        """
        from crp.envelope.builder import EnvelopeState, construct

        return SimpleNamespace(construct=construct, EnvelopeState=EnvelopeState)

    def packer(self) -> Any:
        """Return the graph-aware ``pack_facts`` function.

        Returns:
            pack_facts callable.
        """
        from crp.envelope.packer import pack_facts

        return pack_facts

    def reranker(self) -> Any:
        """Return the cross-encoder ``rerank`` function.

        Returns:
            rerank callable.
        """
        from crp.envelope.reranker import rerank

        return rerank

    def cdr(self) -> Any:
        """Return the Coverage-Differential Retrieval ``cdr_rank`` function.

        Returns:
            cdr_rank callable.
        """
        from crp.envelope.cdr import cdr_rank

        return cdr_rank

    def formatter(self) -> Any:
        """Return the envelope ``format_envelope`` function.

        Returns:
            format_envelope callable.
        """
        from crp.envelope.formatter import format_envelope

        return format_envelope


# ── State ───────────────────────────────────────────────────────────────────


class _StateProxy:
    """State-layer proxy (SPEC-035).

    Exposes warm store, cold storage helpers, snapshots, event log, state facts,
    and the storage router.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def warm_store(self) -> Any:
        """Return the orchestrator's ``WarmStateStore``.

        Returns:
            WarmStateStore instance.
        """
        return getattr(self._orchestrator, "warm_store", None)

    def cold_storage(self) -> Any:
        """Return cold-storage helpers.

        Returns:
            SimpleNamespace with ``persist_to_cold`` and ``restore_from_cold``.
        """
        from crp.state.cold_storage import persist_to_cold, restore_from_cold

        return SimpleNamespace(persist=persist_to_cold, restore=restore_from_cold)

    def snapshot(self) -> Any:
        """Return a fresh ``EventLogSnapshot``.

        Returns:
            EventLogSnapshot instance.
        """
        from crp.state.snapshot import EventLogSnapshot

        return EventLogSnapshot()

    def event_log(self) -> Any:
        """Return a fresh ``FactEventLog``.

        Returns:
            FactEventLog instance.
        """
        from crp.state.event_log import FactEventLog

        return FactEventLog()

    def fact(self) -> Any:
        """Return a sample ``StateFact`` wrapping a default ``Fact``.

        Returns:
            StateFact instance.
        """
        from crp.extraction.types import Fact
        from crp.state.fact import StateFact

        return StateFact(Fact(id="sdk_sample", text="Sample state fact."))

    def router(self) -> Any:
        """Return a fresh ``StorageRouter``.

        Returns:
            StorageRouter instance.
        """
        from crp.state.storage import StorageRouter

        return StorageRouter()


# ── Security ────────────────────────────────────────────────────────────────


class _SecurityProxy:
    """Security subsystem proxy (SPEC-015, SPEC-033, SPEC-034).

    Exposes the safety manifest, consent manager, RBAC enforcer, checkpoints,
    audit trail, encryption/decryption, injection detection, PII scanning, and
    ingest quarantine.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def manifest(self) -> Any:
        """Return a fresh ``SafetyManifest``.

        Returns:
            SafetyManifest instance.
        """
        from crp.security.safety_manifest import SafetyManifest

        return SafetyManifest()

    def consent(self) -> Any:
        """Return a fresh ``ConsentManager``.

        Returns:
            ConsentManager instance.
        """
        from crp.security.consent import ConsentManager

        return ConsentManager()

    def rbac(self) -> Any:
        """Return a fresh ``RBACEnforcer``.

        Returns:
            RBACEnforcer instance.
        """
        from crp.security.rbac import RBACEnforcer

        return RBACEnforcer()

    def checkpoint(self) -> Any:
        """Return a fresh ``Checkpoint``.

        Returns:
            Checkpoint instance.
        """
        from crp.security.checkpoint import Checkpoint

        return Checkpoint()

    def audit_trail(self) -> Any:
        """Return a ``ComplianceAuditTrail`` bound to the current session.

        Returns:
            ComplianceAuditTrail instance.
        """
        from crp.security.audit_trail import ComplianceAuditTrail

        session_id = ""
        session = getattr(self._orchestrator, "_session", None)
        if session is not None:
            session_id = getattr(session, "session_id", "") or session_id
        return ComplianceAuditTrail(session_id=session_id)

    def encrypt(self) -> Any:
        """Return a ``StateEncryptor`` for encryption operations.

        Returns:
            StateEncryptor instance.
        """
        from crp.security.encryption import StateEncryptor

        return StateEncryptor()

    def decrypt(self) -> Any:
        """Return a ``StateEncryptor`` for decryption operations.

        Returns:
            StateEncryptor instance.
        """
        from crp.security.encryption import StateEncryptor

        return StateEncryptor()

    def injection_report(self) -> Any:
        """Return a fresh ``InjectionDetector``.

        Returns:
            InjectionDetector instance.
        """
        from crp.security.injection import InjectionDetector

        return InjectionDetector()

    def pii_scan(self) -> Any:
        """Return a fresh ``PIIScanner``.

        Returns:
            PIIScanner instance.
        """
        from crp.security.privacy import PIIScanner

        return PIIScanner()

    def quarantine(self) -> Any:
        """Return a fresh ``IngestQuarantine``.

        Returns:
            IngestQuarantine instance.
        """
        from crp.security.quarantine import IngestQuarantine

        return IngestQuarantine()


# ── Resources ───────────────────────────────────────────────────────────────


class _ResourcesProxy:
    """Resource management proxy (§6.8, §6.12).

    Exposes the adaptive allocator, cost model, overhead manager, resource
    manager, and a cost-estimation helper.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def allocator(self) -> Any:
        """Return a fresh ``AdaptiveAllocator``.

        Returns:
            AdaptiveAllocator instance.
        """
        from crp.resources.adaptive_allocator import AdaptiveAllocator
        from crp.resources.overhead_manager import OverheadBudgetManager
        from crp.resources.resource_manager import ResourceManager

        return AdaptiveAllocator(
            resource_manager=ResourceManager(),
            overhead_manager=OverheadBudgetManager(),
        )

    def cost_model(self) -> Any:
        """Return a fresh ``CostModel``.

        Returns:
            CostModel instance.
        """
        from crp.resources.cost_model import CostModel

        return CostModel()

    def overhead_manager(self) -> Any:
        """Return a fresh ``OverheadBudgetManager``.

        Returns:
            OverheadBudgetManager instance.
        """
        from crp.resources.overhead_manager import OverheadBudgetManager

        return OverheadBudgetManager()

    def resource_manager(self) -> Any:
        """Return a fresh ``ResourceManager``.

        Returns:
            ResourceManager instance.
        """
        from crp.resources.resource_manager import ResourceManager

        return ResourceManager()

    def estimate_cost(self, input_tokens: int = 0, output_tokens: int = 0, model: str = "gpt-4o") -> Any:
        """Estimate cost for a given token budget and model.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model identifier used for pricing lookup.

        Returns:
            SimpleNamespace with ``total_usd`` and ``pricing``.
        """
        from crp.resources.cost_model import KNOWN_PRICING, ProviderPricing

        pricing = KNOWN_PRICING.get(model, ProviderPricing(provider_name=model))
        return SimpleNamespace(
            total_usd=pricing.total_cost(input_tokens, output_tokens),
            pricing=pricing,
        )


# ── Advanced ────────────────────────────────────────────────────────────────


class _AdvancedProxy:
    """Advanced reasoning and curation proxy (§13, §17–§19).

    Exposes the context curator, feedback loop, meta-learning engine, source
    grounding engine, and cross-window validator.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def curator(self) -> Any:
        """Return a fresh ``LLMContextCurator``.

        Returns:
            LLMContextCurator instance.
        """
        from crp.advanced.curator import LLMContextCurator

        return LLMContextCurator()

    def feedback(self) -> Any:
        """Return a fresh ``FeedbackLoop``.

        Returns:
            FeedbackLoop instance.
        """
        from crp.advanced.feedback import FeedbackLoop

        return FeedbackLoop()

    def meta_learning(self) -> Any:
        """Return a fresh ``MetaLearningEngine``.

        Returns:
            MetaLearningEngine instance.
        """
        from crp.advanced.meta_learning import MetaLearningEngine

        return MetaLearningEngine()

    def source_grounding(self) -> Any:
        """Return a fresh ``SourceGroundingEngine``.

        Returns:
            SourceGroundingEngine instance.
        """
        from crp.advanced.source_grounding import SourceGroundingEngine

        return SourceGroundingEngine()

    def cross_window_validator(self) -> Any:
        """Return a fresh ``CrossWindowValidator``.

        Returns:
            CrossWindowValidator instance.
        """
        from crp.advanced.cross_window import CrossWindowValidator

        return CrossWindowValidator()


# ── CLI ─────────────────────────────────────────────────────────────────────


class _CLIProxy:
    """CLI and sidecar proxy (§9.3, §9.5).

    Exposes the sidecar request handler and startup result types.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def sidecar_handler(self) -> Any:
        """Return the ``CRPSidecarHandler`` class.

        Returns:
            CRPSidecarHandler class.
        """
        from crp.cli.sidecar import CRPSidecarHandler

        return CRPSidecarHandler

    def startup_result(self) -> Any:
        """Return a fresh ``StartupResult``.

        Returns:
            StartupResult instance.
        """
        from crp.cli.startup import StartupResult

        return StartupResult()


# ── Errors ──────────────────────────────────────────────────────────────────


class _ErrorsProxy:
    """Public CRP exception taxonomy proxy (§6.8).

    Exposes common exception classes and a lookup helper.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def _module(self) -> Any:
        from crp.core import errors as errors_mod

        return errors_mod

    def exception(self, name: str) -> Any:
        """Return a CRP exception class by name.

        Args:
            name: Exception class name (e.g. ``"CRPError"``).

        Returns:
            Exception class, or ``CRPError`` if ``name`` is unknown.
        """
        mod = self._module()
        return getattr(mod, name, mod.CRPError)

    def all_exceptions(self) -> dict[str, Any]:
        """Return a mapping of all public CRP exception class names to classes.

        Returns:
            Dict of exception name to exception class.
        """
        mod = self._module()
        return {
            name: obj
            for name, obj in vars(mod).items()
            if isinstance(obj, type) and issubclass(obj, Exception) and not name.startswith("_")
        }

    @property
    def CRPError(self) -> Any:
        """Base CRP exception class."""
        return self._module().CRPError

    @property
    def ConfigError(self) -> Any:
        """Configuration-related error (mapped to ``ValidationError``)."""
        return self._module().ValidationError

    @property
    def SafetyViolation(self) -> Any:
        """Safety violation error (mapped to ``SecurityInvariantError``)."""
        return self._module().SecurityInvariantError

    @property
    def ValidationError(self) -> Any:
        """Validation error class."""
        return self._module().ValidationError

    @property
    def SecurityInvariantError(self) -> Any:
        """Security invariant error class."""
        return self._module().SecurityInvariantError

    @property
    def BudgetExhaustedError(self) -> Any:
        """Budget exhausted error class."""
        return self._module().BudgetExhaustedError

    @property
    def ProviderError(self) -> Any:
        """Provider error class."""
        return self._module().ProviderError
