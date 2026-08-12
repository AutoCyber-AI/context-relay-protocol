# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Ingest quarantine — anti-poisoning with 1-window quarantine (§7.8).

Facts from untrusted sources are quarantined for 1 window with a 0.7×
confidence penalty. Cross-reference validation promotes or rejects them.
Batch poisoning detection: >30% failures → quarantine entire batch.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class QuarantineEntry:
    """A fact held in quarantine."""

    fact_id: str
    original_confidence: float
    penalized_confidence: float  # 0.7× original
    quarantine_window_id: str
    ingested_at: float = field(default_factory=time.time)
    source_label: str = ""
    promoted: bool = False
    rejected: bool = False
    rejection_reason: str = ""


@dataclass
class QuarantineReport:
    """Result of cross-reference validation pass."""

    total_quarantined: int = 0
    promoted: int = 0
    rejected: int = 0
    batch_poisoned: bool = False
    details: list[str] = field(default_factory=list)


# Confidence penalty factor for quarantined facts (§6F.1)
QUARANTINE_CONFIDENCE_FACTOR = 0.7
# Batch poisoning threshold: >30% failures → quarantine entire batch (§6F.3)
BATCH_POISON_THRESHOLD = 0.30


class IngestQuarantine:
    """1-window quarantine with confidence penalty and batch poisoning detection (§7.8).

    Workflow:
    1. Incoming facts go into quarantine with 0.7× confidence
    2. After 1 window, cross-reference against extraction-derived facts
    3. Matching facts are promoted (confidence restored)
    4. Non-matching facts are rejected
    5. If >30% of a batch fails, quarantine entire batch

    Usage:
        q = IngestQuarantine()
        q.quarantine_facts([...], "w-1", source="user_input")
        # ... next window processes ...
        report = q.validate_and_promote("w-2", extraction_fact_texts)
    """

    def __init__(
        self,
        confidence_factor: float = QUARANTINE_CONFIDENCE_FACTOR,
        batch_poison_threshold: float = BATCH_POISON_THRESHOLD,
    ) -> None:
        self._factor = confidence_factor
        self._batch_threshold = batch_poison_threshold
        self._quarantined: dict[str, QuarantineEntry] = {}
        self._window_batches: dict[str, list[str]] = {}  # window_id → [fact_ids]
        self._fact_texts: dict[str, str] = {}  # fact_id → original text for similarity
        self._promotion_history: list[QuarantineReport] = []

    @property
    def quarantine_count(self) -> int:
        """Number of facts currently in quarantine (not promoted or rejected)."""
        return sum(
            1 for e in self._quarantined.values()
            if not e.promoted and not e.rejected
        )

    @property
    def history(self) -> list[QuarantineReport]:
        """Return the history."""
        return list(self._promotion_history)

    def quarantine_fact(
        self,
        fact_id: str,
        original_confidence: float,
        window_id: str,
        source_label: str = "",
        fact_text: str = "",
    ) -> QuarantineEntry:
        """Place a single fact into quarantine with 0.7× confidence penalty (§6F.1)."""
        entry = QuarantineEntry(
            fact_id=fact_id,
            original_confidence=original_confidence,
            penalized_confidence=original_confidence * self._factor,
            quarantine_window_id=window_id,
            source_label=source_label,
        )
        self._quarantined[fact_id] = entry
        if fact_text:
            self._fact_texts[fact_id] = fact_text
        self._window_batches.setdefault(window_id, []).append(fact_id)
        return entry

    def quarantine_facts(
        self,
        facts: list[tuple[str, float]] | list[tuple[str, float, str]],
        window_id: str,
        source_label: str = "",
    ) -> list[QuarantineEntry]:
        """Quarantine a batch of facts.

        Facts can be (fact_id, confidence) or (fact_id, confidence, text).
        """
        entries = []
        for item in facts:
            if len(item) >= 3:
                fid, conf, text = item[0], item[1], item[2]
            else:
                fid, conf, text = item[0], item[1], ""
            entries.append(
                self.quarantine_fact(fid, conf, window_id, source_label, text)
            )
        return entries

    def get_penalized_confidence(self, fact_id: str) -> float | None:
        """Get quarantine-penalized confidence for a fact."""
        entry = self._quarantined.get(fact_id)
        if entry is None:
            return None
        if entry.promoted:
            return entry.original_confidence
        return entry.penalized_confidence

    def is_quarantined(self, fact_id: str) -> bool:
        """Check if a fact is in active quarantine."""
        entry = self._quarantined.get(fact_id)
        if entry is None:
            return False
        return not entry.promoted and not entry.rejected

    def validate_and_promote(
        self,
        current_window_id: str,
        extraction_fact_texts: dict[str, str],
        similarity_threshold: float = 0.5,
    ) -> QuarantineReport:
        """Cross-reference validation: promote or reject quarantined facts (§6F.2).

        Facts quarantined in an earlier window are validated against
        extraction-derived facts. Text overlap > threshold → promote.

        Args:
            current_window_id: Current window being processed
            extraction_fact_texts: {fact_id: text} from extraction pipeline
            similarity_threshold: Word overlap threshold for cross-reference

        Returns:
            QuarantineReport with promotion/rejection counts
        """
        report = QuarantineReport()
        extraction_words_sets = {
            fid: set(text.lower().split())
            for fid, text in extraction_fact_texts.items()
        }

        # Check only facts quarantined in a PREVIOUS window
        pending = [
            (fid, entry) for fid, entry in self._quarantined.items()
            if not entry.promoted and not entry.rejected
            and entry.quarantine_window_id != current_window_id
        ]

        report.total_quarantined = len(pending)
        promoted_count = 0
        rejected_count = 0

        for fid, entry in pending:
            # Cross-reference against extraction facts via word overlap
            matched = False
            # Look up the quarantined fact's text for similarity comparison
            q_text = self._fact_texts.get(fid, "")
            q_words = set(q_text.lower().split()) if q_text else set()

            for ext_fid, ext_words in extraction_words_sets.items():
                # Exact ID match — same fact re-extracted
                if ext_fid == fid:
                    matched = True
                    break
                # Word-overlap similarity: Jaccard-like measure
                if q_words and ext_words:
                    overlap = len(q_words & ext_words)
                    union = len(q_words | ext_words)
                    if union > 0 and (overlap / union) >= similarity_threshold:
                        matched = True
                        break

            if matched:
                entry.promoted = True
                promoted_count += 1
                report.details.append(f"promoted:{fid}")
            else:
                entry.rejected = True
                entry.rejection_reason = "no_cross_reference"
                rejected_count += 1
                report.details.append(f"rejected:{fid}")

        report.promoted = promoted_count
        report.rejected = rejected_count

        # Batch poisoning detection (§6F.3)
        if report.total_quarantined > 0:
            reject_ratio = rejected_count / report.total_quarantined
            if reject_ratio > self._batch_threshold:
                report.batch_poisoned = True
                # Mark all promoted facts as rejected too
                for _fid, entry in pending:
                    if entry.promoted:
                        entry.promoted = False
                        entry.rejected = True
                        entry.rejection_reason = "batch_poisoning"
                        report.promoted -= 1
                        report.rejected += 1
                report.details.append(
                    f"batch_poisoned: {reject_ratio:.0%} > {self._batch_threshold:.0%}"
                )

        self._promotion_history.append(report)
        return report

    def get_active_entries(self) -> list[QuarantineEntry]:
        """Return all currently quarantined (non-promoted, non-rejected) entries."""
        return [
            e for e in self._quarantined.values()
            if not e.promoted and not e.rejected
        ]

    def clear(self) -> None:
        """Clear all quarantine state."""
        self._quarantined.clear()
        self._window_batches.clear()
        self._fact_texts.clear()
        self._promotion_history.clear()
