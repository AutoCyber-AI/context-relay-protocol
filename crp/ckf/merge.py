# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF multi-mode merge — deduplicate, score, rank, community boost (§3.8).

``multi_mode_merge()`` combines results from all four CKF retrieval modes
into a single ranked list, applying deduplication and community-coherence boosting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from crp.extraction.types import Fact

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Weight per mode (graph_walk, pattern, semantic, community)
DEFAULT_MODE_WEIGHTS: dict[str, float] = {
    "graph_walk": 0.30,
    "pattern": 0.25,
    "semantic": 0.30,
    "community": 0.15,
}

# Community coherence boost: facts from same community as top fact get +boost
COMMUNITY_BOOST = 0.10


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class MergedFact:
    """A fact with a merged score from multiple retrieval modes."""

    fact: Fact
    score: float = 0.0
    sources: list[str] = field(default_factory=list)
    community_boosted: bool = False


@dataclass
class MergeResult:
    """Result of multi-mode merge."""

    facts: list[MergedFact] = field(default_factory=list)
    total_candidates: int = 0
    deduplicated: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def multi_mode_merge(
    mode_results: dict[str, list[tuple[Fact, float]]],
    fact_to_community: dict[str, int] | None = None,
    mode_weights: dict[str, float] | None = None,
    max_results: int = 200,
) -> MergeResult:
    """Merge results from multiple CKF retrieval modes.

    Parameters
    ----------
    mode_results : dict[str, list[tuple[Fact, float]]]
        Mapping of mode name → list of (fact, score) tuples.
        Mode names: "graph_walk", "pattern", "semantic", "community".
    fact_to_community : dict[str, int] | None
        Mapping of fact_id → community_id for community boosting.
    mode_weights : dict[str, float] | None
        Override default mode weights.
    max_results : int
        Maximum number of facts to return.
    """
    weights = mode_weights or DEFAULT_MODE_WEIGHTS

    # --- Phase 1: Aggregate scores ---
    scores: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    fact_by_id: dict[str, Fact] = {}
    total_candidates = 0

    for mode_name, results in mode_results.items():
        weight = weights.get(mode_name, 0.2)
        for fact, raw_score in results:
            total_candidates += 1
            fid = fact.id
            fact_by_id[fid] = fact
            scores[fid] = scores.get(fid, 0.0) + raw_score * weight
            sources.setdefault(fid, []).append(mode_name)

    # --- Phase 2: Community boost ---
    if fact_to_community and scores:
        # Find the top fact's community
        top_fid = max(scores, key=lambda k: scores[k])
        top_comm = fact_to_community.get(top_fid)
        if top_comm is not None:
            for fid in scores:
                if fact_to_community.get(fid) == top_comm and fid != top_fid:
                    scores[fid] += COMMUNITY_BOOST

    # --- Phase 3: Rank and build result ---
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    merged_facts: list[MergedFact] = []
    for fid, score in ranked[:max_results]:
        fact = fact_by_id.get(fid)  # type: ignore[assignment]
        if fact is None:
            continue
        boosted = False
        if fact_to_community:
            top_fid = ranked[0][0] if ranked else ""
            top_comm = fact_to_community.get(top_fid)
            if top_comm is not None and fact_to_community.get(fid) == top_comm and fid != top_fid:
                boosted = True
        merged_facts.append(
            MergedFact(
                fact=fact,
                score=score,
                sources=sources.get(fid, []),
                community_boosted=boosted,
            )
        )

    return MergeResult(
        facts=merged_facts,
        total_candidates=total_candidates,
        deduplicated=total_candidates - len(merged_facts),
    )
