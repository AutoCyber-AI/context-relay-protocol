# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Generation quality monitor — Q(t,w) real-time scoring (§10)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass
class QualityScore:
    """Q(t,w) composite quality score and sub-scores."""

    overall: float  # 0.0–1.0 composite
    information_density: float  # facts per 100 tokens
    coherence: float  # sentence-level coherence (0–1)
    novelty: float  # 1 - 5-gram overlap ratio (0–1)
    window_id: str = ""

    @property
    def is_anomaly(self) -> bool:
        """Sudden quality drop: overall < 0.2."""
        return self.overall < 0.2


@dataclass
class QualityConfig:
    """Weights for Q(t,w) sub-scores."""

    density_weight: float = 0.40
    coherence_weight: float = 0.30
    novelty_weight: float = 0.30
    anomaly_threshold: float = 0.2
    anomaly_drop_ratio: float = 0.5  # >50% drop from rolling avg = anomaly


class GenerationQualityMonitor:
    """Real-time Q(t,w) scoring: information density + coherence + novelty (§10).

    Detects quality anomalies (sudden Q(t,w) drops) to trigger re-evaluation.
    """

    def __init__(self, config: QualityConfig | None = None) -> None:
        self._config = config or QualityConfig()
        self._history: list[QualityScore] = []
        self._prior_ngrams: Counter[tuple[str, ...]] = Counter()
        self._rolling_window = 5

    def score(
        self,
        text: str,
        facts_produced: int,
        window_id: str = "",
    ) -> QualityScore:
        """Compute Q(t,w) for a generation window output."""
        tokens = text.split()
        token_count = max(1, len(tokens))

        density = min(1.0, (facts_produced / token_count) * 100.0)

        coherence = self._sentence_coherence(text)

        novelty = self._ngram_novelty(tokens, n=5)

        cfg = self._config
        overall = (
            cfg.density_weight * density
            + cfg.coherence_weight * coherence
            + cfg.novelty_weight * novelty
        )
        overall = max(0.0, min(1.0, overall))

        score = QualityScore(
            overall=overall,
            information_density=density,
            coherence=coherence,
            novelty=novelty,
            window_id=window_id,
        )
        self._history.append(score)

        # Update n-gram pool for future novelty computation
        self._update_ngrams(tokens, n=5)

        return score

    def detect_anomaly(self) -> bool:
        """Check if latest score is an anomaly (sudden drop)."""
        if len(self._history) < 2:
            return False

        latest = self._history[-1].overall
        cfg = self._config

        if latest < cfg.anomaly_threshold:
            return True

        rolling = self._rolling_average()
        return rolling > 0 and latest / rolling < cfg.anomaly_drop_ratio

    def rolling_quality(self) -> float:
        """Rolling average Q(t,w) over last N windows."""
        return self._rolling_average()

    @property
    def history(self) -> list[QualityScore]:
        """Return the history."""
        return list(self._history)

    def reset(self) -> None:
        """Clear all state."""
        self._history.clear()
        self._prior_ngrams.clear()

    # ── Internal ──────────────────────────────────────────────

    def _sentence_coherence(self, text: str) -> float:
        """Measure sentence-level coherence via transition markers and length variance."""
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
        if len(sentences) < 2:
            return 1.0

        transition_words = {
            "however", "therefore", "moreover", "furthermore", "additionally",
            "consequently", "thus", "hence", "meanwhile", "nevertheless",
            "specifically", "for example", "in contrast", "similarly",
            "first", "second", "third", "finally", "next", "then",
        }
        transitions = 0
        for s in sentences[1:]:
            words = s.lower().split()
            if words and words[0] in transition_words:
                transitions += 1

        transition_ratio = transitions / max(1, len(sentences) - 1)

        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        if mean_len == 0:
            return 0.5
        variance = sum((length - mean_len) ** 2 for length in lengths) / len(lengths)
        cv = (variance ** 0.5) / mean_len
        length_consistency = max(0.0, 1.0 - cv)

        return 0.5 * min(1.0, transition_ratio * 3.0) + 0.5 * length_consistency

    def _ngram_novelty(self, tokens: list[str], n: int = 5) -> float:
        """1 - (overlap ratio of n-grams with prior windows)."""
        if len(tokens) < n:
            return 1.0

        current = Counter(
            tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)
        )

        if not self._prior_ngrams:
            return 1.0

        overlap = sum((current & self._prior_ngrams).values())
        total = sum(current.values())
        if total == 0:
            return 1.0

        return 1.0 - (overlap / total)

    def _update_ngrams(self, tokens: list[str], n: int = 5) -> None:
        """Add current window's n-grams to the pool."""
        if len(tokens) < n:
            return
        for i in range(len(tokens) - n + 1):
            self._prior_ngrams[tuple(tokens[i:i + n])] += 1

    def _rolling_average(self) -> float:
        """Average Q(t,w) over last N windows."""
        if not self._history:
            return 0.0
        recent = self._history[-self._rolling_window:]
        return sum(s.overall for s in recent) / len(recent)
