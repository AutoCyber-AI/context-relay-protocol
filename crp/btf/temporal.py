# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Bi-temporal CKF — event-time vs ingestion-time fact validity (CRP-SPEC-057)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BiTemporalFact:
    """A CKF fact with both event-time and ingestion-time validity intervals."""

    subject: str
    predicate: str
    object: str
    valid_from: datetime                          # event time
    valid_to: datetime | None = None              # None = still valid in world
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    invalidated_at: datetime | None = None        # when CRP stopped believing it

    def true_in_world_at(self, t: datetime) -> bool:
        """Was this fact true in the world at ``t``?"""
        return self.valid_from <= t and (self.valid_to is None or t < self.valid_to)

    def believed_by_system_at(self, t: datetime) -> bool:
        """Did the system believe this fact at ``t``?"""
        return self.ingested_at <= t and (self.invalidated_at is None or t < self.invalidated_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "ingested_at": self.ingested_at.isoformat(),
            "invalidated_at": self.invalidated_at.isoformat() if self.invalidated_at else None,
        }


class TemporalCKF:
    """Minimal in-memory bi-temporal fact store."""

    def __init__(self) -> None:
        self._facts: list[BiTemporalFact] = []

    def insert(self, fact: BiTemporalFact) -> None:
        """Insert a new fact."""
        self._facts.append(fact)

    def facts(self, *, subject: str | None = None, predicate: str | None = None) -> list[BiTemporalFact]:
        """Return facts matching optional filters."""
        return [
            f for f in self._facts
            if (subject is None or f.subject == subject)
            and (predicate is None or f.predicate == predicate)
        ]

    def supersede(
        self,
        fact: BiTemporalFact,
        new_object: str,
        at: datetime,
    ) -> BiTemporalFact:
        """Close the old fact and insert a successor.

        Returns:
            The newly inserted fact.
        """
        fact.valid_to = at
        fact.invalidated_at = datetime.now(timezone.utc)
        new_fact = BiTemporalFact(
            subject=fact.subject,
            predicate=fact.predicate,
            object=new_object,
            valid_from=at,
            ingested_at=datetime.now(timezone.utc),
        )
        self.insert(new_fact)
        return new_fact

    def retrieve_as_of(
        self,
        subject: str,
        predicate: str,
        world_time: datetime,
    ) -> BiTemporalFact | None:
        """Return the fact that was true in the world at ``world_time``."""
        candidates = self.facts(subject=subject, predicate=predicate)
        return next((f for f in candidates if f.true_in_world_at(world_time)), None)

    def current(
        self,
        subject: str,
        predicate: str,
    ) -> BiTemporalFact | None:
        """Return the currently valid fact (``valid_to is None``)."""
        candidates = self.facts(subject=subject, predicate=predicate)
        return next((f for f in candidates if f.valid_to is None), None)
