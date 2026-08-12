# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Extraction pipeline orchestration — blackboard-reactive 6-stage pipeline.

Implements the graduated extraction decision tree, self-calibrating baselines,
and stage escalation logic per §3.2 and SPEC-024/SPEC-025.
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field

from crp.core.task_intent import TaskIntent
from crp.extraction.complexity import detect_content_complexity
from crp.extraction.stage1_regex import RegexExtractor
from crp.extraction.stage2_statistical import StatisticalExtractor
from crp.extraction.stage3_gliner import derive_labels_from_noun_phrases
from crp.extraction.stage3_ner import NERExtractor
from crp.extraction.stage4_uie import UIEExtractor
from crp.extraction.stage5_discourse import DiscourseExtractor, count_discourse_markers
from crp.extraction.stage6_llm import DispatchFn, LLMExtractor
from crp.extraction.types import (
    ContentType,
    ExtractionResult,
    Fact,
    FactEdge,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Self-calibrating baseline
# ---------------------------------------------------------------------------

_CALIBRATION_WINDOW_COUNT = 5   # Initial lock after N windows
_RECALIBRATION_INTERVAL = 10   # Recalibrate every N windows after lock
_ROLLING_WINDOW_SIZE = 10      # Rolling window for recalibration
_DEFAULT_STAGE2_BASELINE = 10  # Default facts before calibration
_DEFAULT_STAGE3_BASELINE = 5
_DEFAULT_CONFIDENCE_FLOOR = 0.6
_DRIFT_THRESHOLD = 0.30        # Recalibrate if yield drifts > 30% from baseline
# Gap G fix: Raised threshold so ML stages (GLiNER, UIE) fire more often.
# At 50, stages 1-2 would short-circuit on moderately rich text, preventing
# NER and relation extraction.  At 120, ML stages run for most content,
# producing richer fact graphs and CKF edges.
_SHORT_CIRCUIT_THRESHOLD = 120  # Skip later stages only with very rich extraction (§audit M6)


@dataclass
class CalibrationState:
    """Tracks self-calibrating baselines for stage escalation.

    Baselines are initially locked after ``_CALIBRATION_WINDOW_COUNT``
    windows.  After that, the system *periodically recalibrates* every
    ``_RECALIBRATION_INTERVAL`` windows using a rolling window of the
    most recent results.  This prevents stale baselines when extraction
    profiles change (e.g. when new content domains appear or stages
    come online).
    """

    baseline_stage_2: float = _DEFAULT_STAGE2_BASELINE
    baseline_stage_3: float = _DEFAULT_STAGE3_BASELINE
    baseline_confidence_floor: float = _DEFAULT_CONFIDENCE_FLOOR
    baseline_locked: bool = False
    calibration_epoch: int = 0  # How many times baselines have been calibrated
    _results: list[ExtractionResult] = field(default_factory=list)

    def record(self, result: ExtractionResult) -> None:
        """Record an extraction result. Calibrates/recalibrates as needed."""
        self._results.append(result)
        n = len(self._results)

        if not self.baseline_locked and n >= _CALIBRATION_WINDOW_COUNT:
            # Initial calibration
            self._calibrate(self._results[:_CALIBRATION_WINDOW_COUNT])
        elif self.baseline_locked and n % _RECALIBRATION_INTERVAL == 0:
            # Periodic recalibration with rolling window
            recent = self._results[-_ROLLING_WINDOW_SIZE:]
            if self._detect_drift(recent):
                logger.info("Baseline drift detected at window %d — recalibrating", n)
                self._calibrate(recent)

        # Cap stored results to prevent unbounded growth
        _MAX_RESULTS = _ROLLING_WINDOW_SIZE * 3
        if len(self._results) > _MAX_RESULTS:
            self._results = self._results[-_ROLLING_WINDOW_SIZE:]

    def _calibrate(self, results: list[ExtractionResult]) -> None:
        """Compute baselines from the given result set."""
        # Stage 2 yield mean
        s2 = [r.stage_yields.get(2, 0) for r in results]
        if s2:
            self.baseline_stage_2 = statistics.mean(s2)

        # Stage 3 yield mean (if ran)
        s3 = [r.stage_yields.get(3, 0) for r in results if 3 in r.stages_run]
        if s3:
            self.baseline_stage_3 = statistics.mean(s3)

        # Confidence 10th percentile
        all_conf = [f.confidence for r in results for f in r.facts]
        if len(all_conf) >= 10:
            self.baseline_confidence_floor = statistics.quantiles(all_conf, n=10)[0]

        self.baseline_locked = True
        self.calibration_epoch += 1
        logger.info(
            "Baselines calibrated (epoch %d) — stage2=%.1f, stage3=%.1f, conf_floor=%.2f",
            self.calibration_epoch,
            self.baseline_stage_2,
            self.baseline_stage_3,
            self.baseline_confidence_floor,
        )

    def _detect_drift(self, recent: list[ExtractionResult]) -> bool:
        """Return True if recent yields have drifted significantly from baselines."""
        if not recent:
            return False
        s2_recent = [r.stage_yields.get(2, 0) for r in recent]
        if s2_recent and self.baseline_stage_2 > 0:
            mean_s2 = statistics.mean(s2_recent)
            drift = abs(mean_s2 - self.baseline_stage_2) / max(self.baseline_stage_2, 1)
            if drift > _DRIFT_THRESHOLD:
                return True
        return False

    def should_escalate_stage_3(self, stage_1_2_yield: int) -> bool:
        """Return True if stages 1-2 yielded fewer facts than baseline."""
        return stage_1_2_yield < self.baseline_stage_2

    def should_escalate_stage_4(self, stage_3_relation_yield: float) -> bool:
        """Return True if Stage 3 relation yield per sentence is below 0.1."""
        return stage_3_relation_yield < 0.1

    @property
    def results_count(self) -> int:
        """Number of results recorded for calibration."""
        return len(self._results)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class ExtractionPipeline:
    """Blackboard-reactive 6-stage extraction pipeline.

    Usage::

        pipeline = ExtractionPipeline()
        result = pipeline.extract(text, task_intent)

    Stages 1-2 always run. Stages 3-6 run conditionally based on content
    complexity, yield thresholds, and availability.
    """

    def __init__(
        self,
        *,
        enable_stage_3: bool = True,
        enable_stage_4: bool = True,
        enable_stage_5: bool = True,
        enable_stage_6: bool = False,  # MAY — disabled by default
        dispatch_fn: DispatchFn | None = None,
        short_circuit_threshold: int = _SHORT_CIRCUIT_THRESHOLD,
    ) -> None:
        """Create a new extraction pipeline.

        Args:
            enable_stage_3: Enable NER stage (bert-base-NER by default;
                GLiNER via ``CRP_NER_MODEL=urchade/gliner_base``).
            enable_stage_4: Enable UIE relation stage.
            enable_stage_5: Enable discourse stage.
            enable_stage_6: Enable LLM-assisted stage (rare, expensive).
            dispatch_fn: Dispatch function for Stage 6.
            short_circuit_threshold: Stage 1-2 yield that skips later stages.
        """
        self._stage1 = RegexExtractor()
        self._stage2 = StatisticalExtractor()
        self._stage3 = NERExtractor()
        self._stage4 = UIEExtractor()
        self._stage5 = DiscourseExtractor()
        self._stage6 = LLMExtractor(dispatch_fn)

        self._enable_3 = enable_stage_3
        self._enable_4 = enable_stage_4
        self._enable_5 = enable_stage_5
        self._enable_6 = enable_stage_6
        self._short_circuit_threshold = short_circuit_threshold

        self._calibration = CalibrationState()

        # ML models (NER, UIE) are lazy-loaded on first extraction use.
        # This keeps orchestrator init under ~1s.  The _ensure_model() call
        # happens inside the is_available property when extract() first needs it.

    # -- Configuration ------------------------------------------------------

    @property
    def calibration(self) -> CalibrationState:
        """Current self-calibration state."""
        return self._calibration

    def set_dispatch_fn(self, fn: DispatchFn) -> None:
        """Set the dispatch function for Stage 6 (LLM-assisted extraction).

        Args:
            fn: Dispatch function conforming to ``DispatchFn``.
        """
        self._stage6.set_dispatch(fn)

    def register_regex_pattern(
        self, name: str, pattern: str, category: str, confidence: float = 0.90,
    ) -> None:
        """Register a custom regex pattern in Stage 1.

        Args:
            name: Pattern identifier.
            pattern: Regex string.
            category: Fact category to assign.
            confidence: Confidence for matched facts.
        """
        self._stage1.register_pattern(name, pattern, category, confidence)

    # -- Extraction ---------------------------------------------------------

    def extract(
        self,
        text: str,
        task_intent: TaskIntent | None = None,
        source_window_id: str = "",
    ) -> ExtractionResult:
        """Run the graduated extraction pipeline.

        Stages 1-2 always run. Stages 3-6 run conditionally based on
        content complexity, yield thresholds, and availability.

        Args:
            text: Source text to extract facts from.
            task_intent: Optional task intent for context-aware extraction.
            source_window_id: Window ID to stamp on extracted facts.

        Returns:
            An ``ExtractionResult`` with facts, edges, and pipeline metadata.
        """
        t0 = time.monotonic()
        result = ExtractionResult(source_window_id=source_window_id)
        all_facts: list[Fact] = []
        all_edges: list[FactEdge] = []
        stage_latency: dict[int, float] = {}

        # -- Content complexity detection -----------------------------------
        content_type = detect_content_complexity(text)
        result.content_type = content_type
        result.discourse_markers_found = count_discourse_markers(text)

        word_count = max(len(text.split()), 1)

        # ── STAGE 1: Regex (ALWAYS) ───────────────────────────────────────
        ts = time.monotonic()
        s1_facts = self._stage1.extract(text, source_window_id)
        stage_latency[1] = (time.monotonic() - ts) * 1000
        all_facts.extend(s1_facts)
        result.stages_run.append(1)
        result.stage_yields[1] = len(s1_facts)

        # ── STAGE 2: Statistical (ALWAYS) ─────────────────────────────────
        ts = time.monotonic()
        s2_facts = self._stage2.extract(text, source_window_id)
        stage_latency[2] = (time.monotonic() - ts) * 1000
        all_facts.extend(s2_facts)
        result.stages_run.append(2)
        result.stage_yields[2] = len(s2_facts)

        combined_s1_s2 = len(s1_facts) + len(s2_facts)

        # Short-circuit: skip expensive ML stages if early stages extracted enough (§audit M6)
        _short_circuited = (
            self._short_circuit_threshold > 0
            and combined_s1_s2 >= self._short_circuit_threshold
        )
        if _short_circuited:
            logger.info(
                "Short-circuit: %d facts from stages 1-2 >= threshold %d, skipping stages 3-6",
                combined_s1_s2, self._short_circuit_threshold,
            )
            result.stages_skipped.extend([s for s in (3, 4, 5, 6) if s not in result.stages_skipped])

        # ── STAGE 3: NER (conditional) ────────────────────────────────────
        if not _short_circuited and self._enable_3 and self._calibration.should_escalate_stage_3(combined_s1_s2):
            from crp.license_guard import is_feature_allowed
            if not is_feature_allowed("stage_3"):
                result.stages_skipped.append(3)
            elif self._stage3.is_available:
                ts = time.monotonic()
                # Derive labels from Stage 2 noun phrases
                noun_phrases = [f.text for f in s2_facts if f.category == "noun_phrase"]
                labels = derive_labels_from_noun_phrases(noun_phrases) if noun_phrases else None
                s3_facts = self._stage3.extract(
                    text, labels=labels, source_window_id=source_window_id,
                )
                stage_latency[3] = (time.monotonic() - ts) * 1000
                all_facts.extend(s3_facts)
                result.stages_run.append(3)
                result.stage_yields[3] = len(s3_facts)
                result.escalation_triggers.append(
                    f"stage_1_2_yield={combined_s1_s2} < baseline={self._calibration.baseline_stage_2:.0f}"
                )
            else:
                result.stages_skipped.append(3)
        else:
            result.stages_skipped.append(3)

        # ── STAGE 4: UIE (conditional) ────────────────────────────────────
        stage_3_ran = 3 in result.stages_run
        if not _short_circuited and self._enable_4 and stage_3_ran:
            # Relation yield from Stage 3 — approximate by counting facts / sentences
            _sent_count = max(len(text.split(".")), 1)
            s3_yield = result.stage_yields.get(3, 0)
            relation_per_sent = s3_yield / _sent_count
            if self._calibration.should_escalate_stage_4(relation_per_sent):
                if self._stage4.is_available:
                    ts = time.monotonic()
                    s4_facts, s4_edges = self._stage4.extract(text, source_window_id)
                    stage_latency[4] = (time.monotonic() - ts) * 1000
                    all_facts.extend(s4_facts)
                    all_edges.extend(s4_edges)
                    result.stages_run.append(4)
                    result.stage_yields[4] = len(s4_facts)
                    result.escalation_triggers.append(
                        f"stage_3_relation_yield={relation_per_sent:.2f} < 0.1"
                    )
                else:
                    result.stages_skipped.append(4)
            else:
                result.stages_skipped.append(4)
        else:
            result.stages_skipped.append(4)

        # ── STAGE 5: Discourse (conditional on content type) ──────────────
        if not _short_circuited and self._enable_5 and content_type in (ContentType.REASONING_DENSE, ContentType.NARRATIVE):
            ts = time.monotonic()
            s5_facts, s5_edges = self._stage5.extract(text, source_window_id)
            stage_latency[5] = (time.monotonic() - ts) * 1000
            all_facts.extend(s5_facts)
            all_edges.extend(s5_edges)
            result.stages_run.append(5)
            result.stage_yields[5] = len(s5_facts)
        else:
            result.stages_skipped.append(5)

        # ── STAGE 6: LLM (conditional — rare) ────────────────────────────
        if (
            not _short_circuited
            and self._enable_6
            and content_type == ContentType.REASONING_DENSE
            and self._stage6.is_available
        ):
            # Check Stage 5 edge yield
            _sent_count = max(len(text.split(".")), 1)
            s5_edge_yield = len([e for e in all_edges if e.source_stage == 5]) / _sent_count
            if s5_edge_yield < 0.1:
                ts = time.monotonic()
                s6_facts, s6_edges = self._stage6.extract(text, source_window_id)
                stage_latency[6] = (time.monotonic() - ts) * 1000
                all_facts.extend(s6_facts)
                all_edges.extend(s6_edges)
                result.stages_run.append(6)
                result.stage_yields[6] = len(s6_facts)
                result.escalation_triggers.append(
                    f"stage_5_edge_yield={s5_edge_yield:.2f} < 0.1"
                )
            else:
                result.stages_skipped.append(6)
        else:
            result.stages_skipped.append(6)

        # -- Tick Stage 3 idle counter --------------------------------------
        if 3 not in result.stages_run:
            self._stage3.tick_idle()

        # -- Assemble result ------------------------------------------------
        result.facts = all_facts
        result.edges = all_edges
        result.per_stage_latency = stage_latency
        result.entity_density = len(s1_facts) / max(word_count, 1)
        result.total_extraction_latency_ms = (time.monotonic() - t0) * 1000
        result.finalize()

        # -- Record for calibration -----------------------------------------
        self._calibration.record(result)

        return result
