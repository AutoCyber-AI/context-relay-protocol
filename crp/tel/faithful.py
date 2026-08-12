# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Faithful-narration contract — check a claim against the event trace (CRP-SPEC-056 §8.3.2).

Narration claims are gated through the NLI entailment stack from
``crp.provenance.entailment_verifier`` (cross-encoder, lazy-loaded): a claim
is only shown when the flattened trajectory/tool-result evidence *entails*
it. When the NLI model is unavailable or inference fails, the module falls
back to the deterministic word-subset heuristic so the contract still holds
on every profile.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger("crp.tel.faithful")

# A small English stop-word set, used by the heuristic fallback.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "and", "but", "or", "yet", "so", "if", "because",
    "although", "though", "while", "where", "when", "that", "which", "who",
    "whom", "whose", "what", "this", "these", "those", "i", "you", "he",
    "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "its", "our", "their", "mine", "yours", "hers", "ours",
    "theirs", "am", "it's", "dont", "doesnt", "didnt", "wont",
    "wouldnt", "couldnt", "shouldnt", "isnt", "arent", "wasnt", "werent",
}


def _stems(tok: str) -> set[str]:
    """Return the token plus a naive singular/plural stem."""
    stems = {tok}
    if tok.endswith("s") and len(tok) > 3:
        stems.add(tok[:-1])
    return stems


def _tokenize(text: str) -> set[str]:
    """Extract lowercase alphanumeric content words and their naive stems."""
    words = {
        tok
        for tok in re.findall(r"[a-z0-9]+", text.lower())
        if tok not in _STOPWORDS and len(tok) > 1
    }
    return set().union(*(_stems(w) for w in words))


def _trace_text(trace: Iterable[Any]) -> str:
    """Flatten a trace into one searchable string."""
    parts: list[str] = []
    for item in trace:
        if hasattr(item, "to_dict"):
            item = item.to_dict()
        if isinstance(item, dict):
            parts.append(str(item.get("detail", "")))
            parts.append(str(item.get("content", "")))
            parts.append(str(item.get("operation", "")))
            payload = item.get("payload") or item.get("data") or {}
            parts.append(str(payload.get("value", "")))
            parts.append(str(payload.get("content", "")))
        else:
            parts.append(str(item))
    # Expose underscored keys as separate words so "open_ports" supports "ports".
    return " ".join(parts).replace("_", " ")


# ---------------------------------------------------------------------------
# NLI-backed entailment (lazy; falls back to the heuristic on any failure)
# ---------------------------------------------------------------------------

_nli_unavailable = False


def reset_nli_cache() -> None:
    """Reset the NLI availability flag (for testing)."""
    global _nli_unavailable  # noqa: PLW0603
    _nli_unavailable = False


def _get_nli_model() -> Any:
    """Return the shared NLI cross-encoder, or ``None`` when unavailable."""
    global _nli_unavailable  # noqa: PLW0603
    if _nli_unavailable:
        return None
    try:
        from crp.provenance._types import ProvenanceConfig
        from crp.provenance.entailment_verifier import _get_nli_model as _load

        model = _load(ProvenanceConfig().entailment_model)
        if model is None:
            _nli_unavailable = True
        return model
    except Exception as exc:
        logger.debug("NLI entailment unavailable, using heuristic: %s", exc)
        _nli_unavailable = True
        return None


def _nli_entails(claim: str, premise: str) -> bool | None:
    """Classify (premise, claim) with the NLI model.

    Returns ``True``/``False`` when the model produced a verdict, or ``None``
    when the NLI stack is unavailable or inference failed (caller must fall
    back to the heuristic). Label order follows
    ``crp.provenance.entailment_verifier``: ``[contradiction, entailment,
    neutral]``.
    """
    model = _get_nli_model()
    if model is None:
        return None
    try:
        import math

        scores = model.predict([(premise, claim)])
        row = scores[0]
        if len(row) == 3:
            vals = [float(row[1]), float(row[0]), float(row[2])]  # ent, con, neu
        else:
            ent = float(row[0]) if len(row) > 0 else 0.0
            vals = [ent, 0.0, 1.0 - ent]
        max_v = max(vals)
        exps = [math.exp(v - max_v) for v in vals]
        best = exps.index(max(exps))
        return best == 0  # entailed only when entailment is the top label
    except Exception as exc:
        logger.debug("NLI inference failed, using heuristic: %s", exc)
        return None


def _heuristic_entailment_check(claim: str, evidence: Iterable[Any]) -> bool:
    """Word-subset fallback: every content word must appear in the evidence."""
    claim_words = _tokenize(claim)
    if not claim_words:
        return True
    evidence_words = _tokenize(_trace_text(evidence))
    return claim_words.issubset(evidence_words)


def entailment_check(claim: str, evidence: Iterable[Any]) -> bool:
    """Return ``True`` when the evidence entails/supports ``claim``.

    Prefers the NLI cross-encoder from ``crp.provenance`` (premise = flattened
    trace, hypothesis = claim). Falls back to the deterministic word-subset
    heuristic when the model is unavailable or inference fails. Unsupported
    claims must be withheld from the user stream.
    """
    if not claim.strip():
        return True
    verdict = _nli_entails(claim, _trace_text(evidence))
    if verdict is not None:
        return verdict
    return _heuristic_entailment_check(claim, evidence)


def filter_faithful(claims: Iterable[str], evidence: Iterable[Any]) -> list[str]:
    """Return only claims supported by the evidence."""
    evidence_list = list(evidence)
    premise = _trace_text(evidence_list)
    supported: list[str] = []
    for claim in claims:
        if not _tokenize(claim):
            supported.append(claim)
            continue
        verdict = _nli_entails(claim, premise)
        if verdict is None:
            verdict = _heuristic_entailment_check(claim, evidence_list)
        if verdict:
            supported.append(claim)
    return supported
