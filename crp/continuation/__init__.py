# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Continuation engine — wall detection, gap analysis, stitch, completion."""

from crp.continuation.completion import (
    CompletionConfig,
    CompletionDetector,
    CompletionResult,
    CompletionSignal,
    SignalState,
)
from crp.continuation.degradation import (
    ChainDegradation,
    DegradationMetrics,
    RegroundingResult,
)
from crp.continuation.document_map import DocumentMap, HeadingEntry
from crp.continuation.flow import (
    FlowMetrics,
    InformationFlowMonitor,
    ResidualTaskAnchor,
    should_terminate,
)
# CSO relay — imported from state to avoid circular deps, re-exported here
# for convenience so callers can: from crp.continuation import relay_cso
from crp.state.cso import (
    CognitiveStateObject,
    EstablishedFact,
    Decision,
    GoalState,
    GoalMode,
    ProvenanceKind,
    relay_cso,
    extract_cso,
    preservation_report,
)
from crp.continuation.gap import (
    GapResult,
    Requirement,
    clear_requirement_cache,
    extract_task_requirements,
    gap_analysis,
)
from crp.continuation.manager import (
    ContinuationConfig,
    ContinuationManager,
    ContinuationState,
    DispatchResult,
)
from crp.continuation.quality_monitor import (
    GenerationQualityMonitor,
    QualityConfig,
    QualityScore,
)
from crp.continuation.stitch import (
    ContentBoundary,
    StitchConfig,
    StitchResult,
    detect_echo,
    stitch_many,
    stitch_outputs,
)
from crp.continuation.trigger import (
    TriggerConfig,
    TriggerResult,
    detect_wall_hit,
    evaluate_continuation,
)
from crp.continuation.voice import VoiceProfile, extract_voice_profile

__all__ = [
    # Trigger
    "TriggerConfig",
    "TriggerResult",
    "detect_wall_hit",
    "evaluate_continuation",
    # Gap
    "GapResult",
    "Requirement",
    "extract_task_requirements",
    "gap_analysis",
    "clear_requirement_cache",
    # Flow
    "InformationFlowMonitor",
    "FlowMetrics",
    "ResidualTaskAnchor",
    "should_terminate",
    # CSO relay (SPEC-030)
    "CognitiveStateObject",
    "EstablishedFact",
    "Decision",
    "GoalState",
    "GoalMode",
    "ProvenanceKind",
    "relay_cso",
    "extract_cso",
    "preservation_report",
    # Quality
    "GenerationQualityMonitor",
    "QualityConfig",
    "QualityScore",
    # Completion
    "CompletionDetector",
    "CompletionConfig",
    "CompletionResult",
    "CompletionSignal",
    "SignalState",
    # Stitch
    "StitchConfig",
    "StitchResult",
    "ContentBoundary",
    "detect_echo",
    "stitch_outputs",
    "stitch_many",
    # Voice
    "VoiceProfile",
    "extract_voice_profile",
    # Document Map
    "DocumentMap",
    "HeadingEntry",
    # Degradation
    "ChainDegradation",
    "DegradationMetrics",
    "RegroundingResult",
    # Manager
    "ContinuationManager",
    "ContinuationConfig",
    "ContinuationState",
    "DispatchResult",
]
