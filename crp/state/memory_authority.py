# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Memory write-authority lattice — governed read/remember/recall (SPEC-045).

Agent memory is split into tiers and guarded by authority levels.  The lattice
prevents a low-authority actor (e.g., a tool observation) from overwriting a
high-authority fact (e.g., a user assertion or system constraint).  Every
write, conflict, and erasure is recorded in an append-only audit log so the
memory store remains provably accountable.

Authority order (high → low):
  ``SYSTEM`` > ``USER`` > ``AGENT`` > ``TOOL``

Memory tiers (high persistence → low persistence):
  ``PERSISTENT`` > ``CONVERSATIONAL`` > ``EPHEMERAL``
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Authority(str, Enum):
    """Actor authority levels in the memory lattice."""

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"


class MemoryTier(str, Enum):
    """Memory persistence tiers."""

    PERSISTENT = "persistent"
    CONVERSATIONAL = "conversational"
    EPHEMERAL = "ephemeral"


class MemoryOperation(str, Enum):
    """Kinds of memory operations recorded in the audit log."""

    WRITE = "write"
    OVERWRITE = "overwrite"
    REJECT = "reject"
    RECALL = "recall"
    ERASE = "erase"


# Numeric rank: higher = more authority.
_AUTHORITY_RANK: dict[Authority, int] = {
    Authority.SYSTEM: 4,
    Authority.USER: 3,
    Authority.AGENT: 2,
    Authority.TOOL: 1,
}

# Minimum authority required to create a memory entry in each tier.
_TIER_WRITE_MIN: dict[MemoryTier, Authority] = {
    MemoryTier.PERSISTENT: Authority.USER,
    MemoryTier.CONVERSATIONAL: Authority.AGENT,
    MemoryTier.EPHEMERAL: Authority.TOOL,
}

# Rank of the minimum authority for each tier.
_TIER_MIN_RANK: dict[MemoryTier, int] = {
    tier: _AUTHORITY_RANK[auth] for tier, auth in _TIER_WRITE_MIN.items()
}


@dataclass
class MemoryEntry:
    """A single governed memory entry."""

    key: str
    value: Any
    tier: MemoryTier
    authority: Authority
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    entry_id: str = field(default_factory=lambda: _new_id())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "entry_id": self.entry_id,
            "key": self.key,
            "value": self.value,
            "tier": self.tier.value,
            "authority": self.authority.value,
            "source": self.source,
            "timestamp": self.timestamp,
        }


@dataclass
class MemoryAuditEvent:
    """One recorded memory operation."""

    event_id: str
    operation: MemoryOperation
    key: str
    actor: Authority
    tier: MemoryTier
    allowed: bool
    reason: str
    timestamp: float
    entry_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "event_id": self.event_id,
            "operation": self.operation.value,
            "key": self.key,
            "actor": self.actor.value,
            "tier": self.tier.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "entry_id": self.entry_id,
        }


def _new_id() -> str:
    """Return a short unique identifier."""
    import uuid

    return uuid.uuid4().hex[:16]


class MemoryAuthorityLattice:
    """Governed memory store with write-authority enforcement.

    Usage::

        mem = MemoryAuthorityLattice()
        mem.remember("user_goal", "deploy to prod", Authority.USER, MemoryTier.PERSISTENT)
        mem.recall("user_goal")  # returns the entry
        mem.remember("user_goal", "delete prod", Authority.AGENT, MemoryTier.PERSISTENT)
        # rejected: AGENT cannot overwrite USER persistent fact
    """

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}
        self._audit_log: list[MemoryAuditEvent] = []
        self._lock = threading.Lock()

    @property
    def audit_log(self) -> list[MemoryAuditEvent]:
        """Append-only audit log of memory operations."""
        return list(self._audit_log)

    def _rank(self, authority: Authority) -> int:
        return _AUTHORITY_RANK.get(authority, 0)

    def _can_write(self, tier: MemoryTier, authority: Authority) -> tuple[bool, str]:
        """Return whether *authority* can write to *tier* and the reason."""
        rank = self._rank(authority)
        min_rank = _TIER_MIN_RANK[tier]
        if rank < min_rank:
            return False, (
                f"{authority.value} rank {rank} < tier {tier.value} min rank {min_rank}"
            )
        return True, ""

    def _can_overwrite(
        self,
        existing: MemoryEntry,
        new_authority: Authority,
    ) -> tuple[bool, str]:
        """Return whether *new_authority* can overwrite *existing* entry."""
        new_rank = self._rank(new_authority)
        existing_rank = self._rank(existing.authority)
        if new_rank < existing_rank:
            return False, (
                f"{new_authority.value} rank {new_rank} < existing {existing.authority.value} "
                f"rank {existing_rank}"
            )
        return True, ""

    def _record(
        self,
        operation: MemoryOperation,
        key: str,
        actor: Authority,
        tier: MemoryTier,
        allowed: bool,
        reason: str,
        entry_id: str | None = None,
    ) -> None:
        self._audit_log.append(
            MemoryAuditEvent(
                event_id=_new_id(),
                operation=operation,
                key=key,
                actor=actor,
                tier=tier,
                allowed=allowed,
                reason=reason,
                timestamp=time.time(),
                entry_id=entry_id,
            )
        )

    def remember(
        self,
        key: str,
        value: Any,
        actor: Authority,
        tier: MemoryTier,
        source: str = "",
    ) -> MemoryEntry | None:
        """Write or overwrite a memory entry, enforcing authority rules.

        Args:
            key: Memory key.
            value: Value to store.
            actor: Authority level of the writer.
            tier: Persistence tier.
            source: Human-readable source identifier.

        Returns:
            The stored ``MemoryEntry`` if the write was allowed, else ``None``.
        """
        with self._lock:
            allowed, reason = self._can_write(tier, actor)
            if not allowed:
                self._record(
                    MemoryOperation.REJECT, key, actor, tier, False, reason,
                )
                return None

            existing = self._store.get(key)
            if existing is not None:
                allowed, reason = self._can_overwrite(existing, actor)
                if not allowed:
                    self._record(
                        MemoryOperation.REJECT, key, actor, tier, False, reason,
                    )
                    return None
                operation = MemoryOperation.OVERWRITE
            else:
                operation = MemoryOperation.WRITE

            entry = MemoryEntry(
                key=key,
                value=value,
                tier=tier,
                authority=actor,
                source=source,
            )
            self._store[key] = entry
            self._record(operation, key, actor, tier, True, reason, entry.entry_id)
            return entry

    def recall(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key.

        Args:
            key: Memory key.

        Returns:
            The entry or ``None`` if not found.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                self._record(
                    MemoryOperation.RECALL,
                    key,
                    Authority.SYSTEM,
                    entry.tier,
                    True,
                    "recalled",
                    entry.entry_id,
                )
            return entry

    def erase(self, key: str, actor: Authority) -> bool:
        """Erase a memory entry if *actor* has sufficient authority.

        Erasure requires actor authority >= the entry's authority.

        Args:
            key: Memory key.
            actor: Authority requesting erasure.

        Returns:
            True if the entry was erased.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            actor_rank = self._rank(actor)
            entry_rank = self._rank(entry.authority)
            if actor_rank < entry_rank:
                reason = (
                    f"{actor.value} rank {actor_rank} < entry {entry.authority.value} "
                    f"rank {entry_rank}"
                )
                self._record(
                    MemoryOperation.ERASE, key, actor, entry.tier, False, reason,
                )
                return False
            del self._store[key]
            self._record(
                MemoryOperation.ERASE, key, actor, entry.tier, True, "erased",
            )
            return True

    def list_keys(self) -> list[str]:
        """Return all memory keys."""
        return list(self._store.keys())

    def list_entries(self) -> list[MemoryEntry]:
        """Return all memory entries."""
        return list(self._store.values())

    def to_dict(self) -> dict[str, Any]:
        """Serialize store + audit log to a dict."""
        return {
            "entries": {k: v.to_dict() for k, v in self._store.items()},
            "audit_log": [e.to_dict() for e in self._audit_log],
        }
