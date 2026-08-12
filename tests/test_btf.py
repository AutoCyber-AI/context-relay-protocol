# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Bi-Temporal CKF (CRP-SPEC-057)."""

from __future__ import annotations

from datetime import datetime, timezone

from crp.btf import BiTemporalFact, TemporalCKF


class TestBiTemporalCKF:
    def test_retrieve_as_of(self) -> None:
        ckf = TemporalCKF()
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2024, 6, 1, tzinfo=timezone.utc)
        f1 = BiTemporalFact("db", "host", "old.internal", valid_from=t1)
        ckf.insert(f1)
        new = ckf.supersede(f1, "new.internal", at=t2)

        as_of = ckf.retrieve_as_of("db", "host", datetime(2024, 3, 1, tzinfo=timezone.utc))
        assert as_of is not None
        assert as_of.object == "old.internal"

        current = ckf.current("db", "host")
        assert current is not None
        assert current.object == "new.internal"

    def test_true_in_world_bounds(self) -> None:
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2024, 2, 1, tzinfo=timezone.utc)
        fact = BiTemporalFact("db", "host", "x", valid_from=t1, valid_to=t2)
        assert fact.true_in_world_at(datetime(2024, 1, 15, tzinfo=timezone.utc))
        assert not fact.true_in_world_at(datetime(2024, 3, 1, tzinfo=timezone.utc))
