# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Semantic entropy — uncertainty from meaning-level divergence (CRP-SPEC-055 §7.3.1)."""

from __future__ import annotations

import math
import os
from typing import Any

from crp.ml import MANAGER


def _nli_loader() -> Any:
    """Lazily load a small NLI model for semantic equivalence."""
    from transformers import pipeline  # type: ignore[import-untyped]

    # v3-xsmall is the smallest DeBERTa NLI model; falls back to any available NLI.
    model_name = os.getenv("CRP_NLI_MODEL", "cross-encoder/nli-deberta-v3-xsmall")
    return pipeline("text-classification", model=model_name, top_k=None)


MANAGER.register(
    "crp.ep.nli",
    _nli_loader,
    budget_ms=100.0,
    load_timeout_ms=60000.0,
)


def _equivalent(model: Any, a: str, b: str) -> bool:
    """Bidirectional entailment => semantic equivalence."""
    ab = max(model(f"{a} [SEP] {b}"), key=lambda d: d["score"])["label"]
    ba = max(model(f"{b} [SEP] {a}"), key=lambda d: d["score"])["label"]
    return ab == "ENTAILMENT" and ba == "ENTAILMENT"


def _fallback_equivalent(a: str, b: str) -> bool:
    """Lightweight fallback: normalised string equality."""
    return a.strip().lower() == b.strip().lower()


def semantic_entropy(samples: list[str], budget_ms: float = 100.0) -> float:
    """Compute normalised semantic entropy over ``samples``.

    Uses a local NLI model when available, otherwise falls back to string
    equality.  The call is budgeted; if it exceeds ``budget_ms`` the fallback
    path is returned.
    """
    if not samples:
        return 0.0
    n = len(samples)
    if n == 1:
        return 0.0

    def _cluster(model: Any | None) -> list[list[str]]:
        clusters: list[list[str]] = []
        equivalent_fn = _equivalent if model is not None else _fallback_equivalent
        for s in samples:
            placed = False
            for c in clusters:
                if equivalent_fn(c[0], s) if model is None else equivalent_fn(model, c[0], s):
                    c.append(s)
                    placed = True
                    break
            if not placed:
                clusters.append([s])
        return clusters

    clusters = MANAGER.run(
        "crp.ep.nli",
        lambda model: _cluster(model),
        budget_ms=budget_ms,
        fallback=_cluster(None),
    )
    if clusters is None:
        clusters = _cluster(None)

    probs = [len(c) / n for c in clusters]
    h = -sum(p * math.log(p) for p in probs)
    return round(h / math.log(n), 3)
