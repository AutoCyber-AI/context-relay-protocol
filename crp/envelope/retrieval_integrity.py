# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Retrieval Integrity — recency decay, contradiction detection, parallel isolation (SPEC-027).

Fixes three correctness gaps in CRP's retrieval layer:
  - Gap 5 (Recency): stale-but-novel facts outrank fresh-but-covered ones
  - Gap 4 (Contradiction): mutually contradictory facts handed to model together
  - Gap 3 (Concurrency): parallel fan-out branches race on shared Coverage Set
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("crp.envelope.retrieval_integrity")


# ── Gap 5: Recency Decay ───────────────────────────────────────────────────


def apply_recency_decay(
    fact_timestamp: datetime,
    session_time: datetime | None = None,
    half_life_days: float = 30.0,
    floor: float = 0.1,
) -> float:
    """Return a recency multiplier for the CDR formula (SPEC-027 §2).

    Newer facts weighted higher. Exponential decay with configurable half-life.
    """
    if session_time is None:
        session_time = datetime.now(timezone.utc)
    if fact_timestamp.tzinfo is None:
        fact_timestamp = fact_timestamp.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (session_time - fact_timestamp).total_seconds() / 86400.0)
    decay = floor + (1.0 - floor) * math.exp2(-age_days / half_life_days)
    return round(decay, 4)


# ── Gap 4: Contradiction Detection ─────────────────────────────────────────


@dataclass
class ContradictionSignal:
    """Detected contradiction between two facts."""

    fact_a_id: str
    fact_b_id: str
    contradiction_type: str  # "numeric", "boolean", "temporal", "semantic"
    confidence: float  # 0.0–1.0


def _extract_number(text: str) -> float | None:
    """Try to extract a single numeric value from text."""
    import re
    nums = re.findall(r"[-+]?[\d,]+\.?\d*", text.replace(",", ""))
    if len(nums) == 1:
        try:
            return float(nums[0])
        except ValueError:
            return None
    return None


def detect_contradication(fact_a: Any, fact_b: Any) -> ContradictionSignal | None:
    """Flag contradicting facts — emit to DPE §6 contradiction detection (SPEC-027 §3).

    Lightweight heuristics (sub-millisecond). Returns None if no contradiction
    detected or if facts are not comparable.
    """
    content_a = getattr(fact_a, "content", str(fact_a))
    content_b = getattr(fact_b, "content", str(fact_b))
    fid_a = getattr(fact_a, "fact_id", "a")
    fid_b = getattr(fact_b, "fact_id", "b")

    # Numeric contradiction: same subject, opposite numbers
    num_a = _extract_number(content_a)
    num_b = _extract_number(content_b)
    if num_a is not None and num_b is not None:
        if abs(num_a - num_b) > 1e-6 and num_a != 0 and num_b != 0:
            # Heuristic: if both contain the same key noun, flag contradiction
            words_a = set(content_a.lower().split())
            words_b = set(content_b.lower().split())
            shared = words_a & words_b
            if len(shared) >= 2:
                return ContradictionSignal(
                    fact_a_id=fid_a,
                    fact_b_id=fid_b,
                    contradiction_type="numeric",
                    confidence=0.7,
                )

    # Boolean contradiction: explicit negation words
    negations = {"not", "no", "never", "false", "disabled", "inactive"}
    a_has_neg = any(w in content_a.lower() for w in negations)
    b_has_neg = any(w in content_b.lower() for w in negations)
    if a_has_neg != b_has_neg:
        words_a = set(content_a.lower().split())
        words_b = set(content_b.lower().split())
        shared = words_a & words_b
        if len(shared) >= 3:
            return ContradictionSignal(
                fact_a_id=fid_a,
                fact_b_id=fid_b,
                contradiction_type="boolean",
                confidence=0.6,
            )

    return None


def resolve_fact_authority(facts: list[Any]) -> list[Any]:
    """Fact Authority Resolution: when contradictions exist, keep the authoritative fact.

    Authority heuristic: more recent + higher source trust wins.
    Returns de-duplicated list with contradictions resolved.
    """
    if not facts:
        return []

    def _authority_score(f: Any) -> float:
        ts = getattr(f, "ingested_at", datetime.min)
        if isinstance(ts, datetime):
            recency = apply_recency_decay(ts, half_life_days=7.0)
        else:
            recency = 0.5
        trust = getattr(f, "source_trust", 0.5)
        return recency + trust

    # Group facts by shared semantic signature (simplified: shared words)
    groups: list[list[Any]] = []
    for f in facts:
        content = getattr(f, "content", str(f)).lower()
        placed = False
        for g in groups:
            g_content = getattr(g[0], "content", str(g[0])).lower()
            shared = set(content.split()) & set(g_content.split())
            if len(shared) >= 3:
                g.append(f)
                placed = True
                break
        if not placed:
            groups.append([f])

    result: list[Any] = []
    for g in groups:
        # Check for contradictions within group
        has_contra = False
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if detect_contradication(g[i], g[j]) is not None:
                    has_contra = True
                    break
            if has_contra:
                break

        if has_contra:
            # Keep highest-authority fact
            g.sort(key=_authority_score, reverse=True)
            result.append(g[0])
            logger.debug("Resolved contradiction in group of %d facts; kept %s", len(g), getattr(g[0], "fact_id", "?"))
        else:
            result.extend(g)

    return result


# ── Gap 3: Parallel Coverage Isolation ─────────────────────────────────────


def isolate_parallel_coverage(facts: list[Any], sessions: list[Any]) -> list[Any]:
    """SPEC-027 §1: separate coverage sets for fan-out (multi-agent) scenarios.

    Pre-partitions facts into disjoint scopes so parallel branches cannot
    retrieve duplicates. Simplified implementation: round-robin by topic hash.
    """
    if not sessions or len(sessions) <= 1:
        return facts

    import hashlib

    num_branches = len(sessions)
    partitioned: list[list[Any]] = [[] for _ in range(num_branches)]

    for f in facts:
        content = getattr(f, "content", str(f))
        topic_hash = int(hashlib.blake2b(content.encode(), digest_size=4).hexdigest(), 16)
        branch_idx = topic_hash % num_branches
        partitioned[branch_idx].append(f)

    # Flatten back in order but with branch attribution metadata
    result: list[Any] = []
    for idx, branch_facts in enumerate(partitioned):
        for f in branch_facts:
            # Attach branch isolation metadata without mutating original
            f_iso = _shallow_copy_with_meta(f, {"branch_scope": idx})
            result.append(f_iso)

    logger.debug("Isolated %d facts across %d branches", len(facts), num_branches)
    return result


def _shallow_copy_with_meta(obj: Any, meta: dict[str, Any]) -> Any:
    """Create a shallow copy of a dataclass-like object with extra metadata."""
    if hasattr(obj, "__dataclass_fields__"):
        import copy
        new_obj = copy.copy(obj)
        # Attach metadata on a private attribute
        existing = getattr(new_obj, "_crp_meta", {})
        new_obj._crp_meta = {**existing, **meta}  # type: ignore[attr-defined]
        return new_obj
    return obj
