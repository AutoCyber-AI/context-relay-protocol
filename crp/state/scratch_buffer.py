# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Scratch Buffer — structured, freshness-gated, reference-addressable store for ephemeral context (SPEC-029).

Tier E of the Multi-Horizon Model. Manages tool outputs, intermediate results,
and working data with instant-decay lifecycle.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.state.scratch_buffer")


# ── Persistence enum ───────────────────────────────────────────────────────


class ScratchPersistence(str, Enum):
    """How long a scratch entry lives."""

    EPHEMERAL = "ephemeral"  # evaporates when TTL expires
    PINNED = "pinned"        # user explicitly cares about this result


# ── ScratchEntry ───────────────────────────────────────────────────────────


@dataclass
class ScratchEntry:
    """One item in the Scratch Buffer."""

    scratch_id: str
    tool_name: str
    tool_call_args: dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""
    raw_token_count: int = 0
    summary: str = ""
    structured: Any = None
    created_at: float = field(default_factory=time.time)
    freshness_ttl: int = 30  # seconds
    persistence: ScratchPersistence = ScratchPersistence.EPHEMERAL
    referenced_by: list[int] = field(default_factory=list)
    provenance_hash: str = ""

    def __post_init__(self) -> None:
        if not self.provenance_hash and self.raw_output:
            self.provenance_hash = hashlib.blake2b(
                self.raw_output.encode(), digest_size=16
            ).hexdigest()

    @property
    def is_fresh(self) -> bool:
        """Return whether this object is fresh."""
        return (time.time() - self.created_at) < self.freshness_ttl


# ── ScratchBuffer ──────────────────────────────────────────────────────────


@dataclass
class ScratchBuffer:
    """Tier E store — high-volume working data with pointer-based access (SPEC-029).

    Data stays in memory/disk; only pointers and summaries live in the session.
    """

    session_id: str = ""
    entries: dict[str, ScratchEntry] = field(default_factory=dict)

    def store(
        self,
        data: Any,
        entry_id: str,
        tool_name: str = "",
        freshness_ttl: int = 30,
        structure: str = "auto",
    ) -> str:
        """Store data and return a pointer. Data written to ephemeral store.

        Args:
            data: The raw output to store.
            entry_id: Addressable ID, e.g. "scratch_sql_001".
            tool_name: Which tool produced this.
            freshness_ttl: Seconds until entry becomes stale.
            structure: "auto" | "tabular" | "json" | "code" | "text".
        """
        raw = str(data) if not isinstance(data, str) else data
        token_count = len(raw.split())  # rough word-level estimate

        summary = self._summarise(raw, structure, tool_name)
        structured = None
        if structure == "json" or (structure == "auto" and raw.strip().startswith(("{", "["))):
            try:
                structured = json.loads(raw)
            except json.JSONDecodeError:
                pass

        entry = ScratchEntry(
            scratch_id=entry_id,
            tool_name=tool_name,
            raw_output=raw,
            raw_token_count=token_count,
            summary=summary,
            structured=structured,
            freshness_ttl=freshness_ttl,
            provenance_hash=hashlib.blake2b(raw.encode(), digest_size=16).hexdigest(),
        )
        self.entries[entry_id] = entry
        logger.debug("Stored scratch entry %s (%s, %d tokens)", entry_id, tool_name, token_count)
        return entry_id

    def get_fresh(self, entry_id: str) -> ScratchEntry | None:
        """Returns None if entry has expired."""
        entry = self.entries.get(entry_id)
        if entry is None:
            return None
        if not entry.is_fresh and entry.persistence != ScratchPersistence.PINNED:
            logger.debug("Scratch entry %s expired (ttl=%ss)", entry_id, entry.freshness_ttl)
            return None
        return entry

    def summarise(self, entry_id: str, max_tokens: int = 200) -> str:
        """Structure-aware summarisation for inclusion in Operation Frames."""
        entry = self.entries.get(entry_id)
        if entry is None:
            return ""
        # Return pre-computed summary if within budget
        words = entry.summary.split()
        if len(words) <= max_tokens:
            return entry.summary
        return " ".join(words[:max_tokens]) + "..."

    def get_provenance(self, entry_id: str) -> dict[str, Any]:
        """SPEC-029 §6: TOOL_GROUNDED provenance for decisions based on tool output."""
        entry = self.entries.get(entry_id)
        if entry is None:
            return {}
        return {
            "type": "TOOL_GROUNDED",
            "tool": entry.tool_name,
            "args": entry.tool_call_args,
            "hash": entry.provenance_hash,
            "fresh": entry.is_fresh,
            "created_at": entry.created_at,
        }

    def pin(self, entry_id: str) -> None:
        """Promote an entry from ephemeral to pinned persistence."""
        entry = self.entries.get(entry_id)
        if entry is not None:
            entry.persistence = ScratchPersistence.PINNED
            logger.info("Pinned scratch entry %s", entry_id)

    def purge_expired(self) -> int:
        """Remove expired ephemeral entries. Returns count removed."""
        expired = [
            k for k, v in self.entries.items()
            if v.persistence == ScratchPersistence.EPHEMERAL and not v.is_fresh
        ]
        for k in expired:
            del self.entries[k]
        if expired:
            logger.debug("Purged %d expired scratch entries", len(expired))
        return len(expired)

    # ------------------------------------------------------------------
    # Internal: structure-aware summarisation
    # ------------------------------------------------------------------

    def _summarise(self, raw: str, structure: str, tool_name: str) -> str:
        if structure == "auto":
            structure = self._detect_structure(raw)

        if structure == "tabular":
            lines = raw.strip().splitlines()
            if len(lines) >= 2:
                header = lines[0]
                row_count = len(lines) - 1
                # Sample first 3 data rows
                sample = lines[1:4]
                return f"[{tool_name}] {row_count} rows. Header: {header}. Sample: {' | '.join(sample)}"
            return f"[{tool_name}] Table: {raw[:200]}"

        if structure == "json":
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    keys = list(obj.keys())
                    return f"[{tool_name}] JSON object with keys: {', '.join(keys[:10])}"
                if isinstance(obj, list):
                    return f"[{tool_name}] JSON array with {len(obj)} items"
                return f"[{tool_name}] JSON scalar"
            except json.JSONDecodeError:
                pass

        if structure == "code":
            lines = raw.splitlines()
            return f"[{tool_name}] Code block ({len(lines)} lines). First line: {lines[0][:80] if lines else 'empty'}"

        # Long text / default
        words = raw.split()
        if len(words) > 50:
            return f"[{tool_name}] {len(words)} words. Summary: {' '.join(words[:40])}..."
        return f"[{tool_name}] {raw[:200]}"

    def _detect_structure(self, raw: str) -> str:
        stripped = raw.strip()
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                pass
        lines = stripped.splitlines()
        if len(lines) > 1 and ("\t" in lines[0] or "|" in lines[0] or "," in lines[0]):
            return "tabular"
        if any(kw in stripped for kw in ("def ", "class ", "function", "import ", "#include")):
            return "code"
        return "text"
