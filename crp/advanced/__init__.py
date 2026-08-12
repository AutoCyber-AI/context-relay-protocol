# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Advanced features — hierarchical, parallel, auto-ingest, CQS, meta-learning."""

from crp.advanced.auto_ingest import IngestFact, IngestResult, auto_ingest
from crp.advanced.cqs import ContextHungerSignal, CQSDetector, CQSResponse
from crp.advanced.cross_window import ConsistencyIssue, CrossWindowValidator, ValidationResult
from crp.advanced.curator import CurationConfig, LLMContextCurator, LLMSynthesis
from crp.advanced.feedback import FeedbackEntry, FeedbackLoop
from crp.advanced.hierarchical import HierarchicalPlan, HierarchicalProcessor
from crp.advanced.meta_learning import MetaLearningEngine, ORCResult, ReasoningTrace
from crp.advanced.parallel import FanOutResult, FanOutTask, ParallelFanOut
from crp.advanced.review_cycle import AssessmentResult, ReviewCycleManager, ReviewGuidance
from crp.advanced.scale_mode import QualityTier, ScaleModeSelector, SessionConfig
from crp.advanced.source_grounding import SourceGroundingEngine, SourcePassage

__all__ = [
    # auto_ingest
    "auto_ingest", "IngestResult", "IngestFact",
    # cqs
    "CQSDetector", "ContextHungerSignal", "CQSResponse",
    # cross_window
    "CrossWindowValidator", "ConsistencyIssue", "ValidationResult",
    # curator
    "LLMContextCurator", "LLMSynthesis", "CurationConfig",
    # feedback
    "FeedbackLoop", "FeedbackEntry",
    # hierarchical
    "HierarchicalProcessor", "HierarchicalPlan",
    # meta_learning
    "MetaLearningEngine", "ReasoningTrace", "ORCResult",
    # parallel
    "ParallelFanOut", "FanOutTask", "FanOutResult",
    # review_cycle
    "ReviewCycleManager", "ReviewGuidance", "AssessmentResult",
    # scale_mode
    "ScaleModeSelector", "QualityTier", "SessionConfig",
    # source_grounding
    "SourceGroundingEngine", "SourcePassage",
]
