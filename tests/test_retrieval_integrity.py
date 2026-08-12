# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Retrieval Integrity — recency, contradiction, parallel isolation (SPEC-027)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from crp.envelope.retrieval_integrity import (
    apply_recency_decay,
    detect_contradication,
    resolve_fact_authority,
)


@dataclass
class _MockFact:
    fact_id: str
    content: str
    ingested_at: datetime
    source_trust: float = 0.5


class TestRecencyDecay:
    def test_fresh_fact(self) -> None:
        now = datetime.now(timezone.utc)
        fact_time = now - timedelta(hours=1)
        decay = apply_recency_decay(fact_time, now, half_life_days=30.0)
        assert decay > 0.95

    def test_old_fact(self) -> None:
        now = datetime.now(timezone.utc)
        fact_time = now - timedelta(days=60)
        decay = apply_recency_decay(fact_time, now, half_life_days=30.0)
        assert decay < 0.4
        assert decay >= 0.1

    def test_floor(self) -> None:
        now = datetime.now(timezone.utc)
        fact_time = now - timedelta(days=365)
        decay = apply_recency_decay(fact_time, now, half_life_days=7.0)
        assert decay == 0.1


class TestContradictionDetection:
    def test_numeric_contradiction(self) -> None:
        f1 = _MockFact("f1", "The speed limit is 60 km/h", datetime.now(timezone.utc))
        f2 = _MockFact("f2", "The speed limit is 80 km/h", datetime.now(timezone.utc))
        signal = detect_contradication(f1, f2)
        assert signal is not None
        assert signal.contradiction_type == "numeric"

    def test_no_contradiction(self) -> None:
        f1 = _MockFact("f1", "The sky is blue", datetime.now(timezone.utc))
        f2 = _MockFact("f2", "The grass is green", datetime.now(timezone.utc))
        signal = detect_contradication(f1, f2)
        assert signal is None

    def test_boolean_contradiction(self) -> None:
        f1 = _MockFact("f1", "The system is enabled", datetime.now(timezone.utc))
        f2 = _MockFact("f2", "The system is not enabled", datetime.now(timezone.utc))
        signal = detect_contradication(f1, f2)
        assert signal is not None
        assert signal.contradiction_type == "boolean"


class TestFactAuthorityResolution:
    def test_no_contradiction_returns_all(self) -> None:
        facts = [
            _MockFact("f1", "A", datetime.now(timezone.utc)),
            _MockFact("f2", "B", datetime.now(timezone.utc)),
        ]
        result = resolve_fact_authority(facts)
        assert len(result) == 2

    def test_resolves_contradiction(self) -> None:
        now = datetime.now(timezone.utc)
        facts = [
            _MockFact("f1", "The speed limit is 60", now - timedelta(days=1)),
            _MockFact("f2", "The speed limit is 80", now, source_trust=0.9),
        ]
        result = resolve_fact_authority(facts)
        assert len(result) == 1
        assert result[0].fact_id == "f2"
