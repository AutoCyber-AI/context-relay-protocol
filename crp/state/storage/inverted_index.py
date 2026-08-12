# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Inverted Index — exact-match lookup primitive (SPEC-035 §2.4).

Term-to-fact and key-to-fact inverted index for exact-match retrieval.
Microsecond lookups for named entities, identifiers, and structured fields.

This is the right primitive when the access pattern is "the fact named X"
or "facts mentioning entity Y exactly" — as opposed to "facts similar in
meaning to X" (that's the CKF graph).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexedFact:
    """A fact stored in the inverted index with its terms and keys."""

    fact_id: str
    fact: Any
    terms: set[str] = field(default_factory=set)   # tokenised text terms
    keys: set[str] = field(default_factory=set)    # named keys / identifiers


class InvertedIndex:
    """Exact-match inverted index for fast keyed and term-based lookup.

    Maintains two indexes:
    - ``_term_index``: term → {fact_id} for token-based search
    - ``_key_index``:  key → {fact_id} for exact named lookup
    - ``_facts``:      fact_id → IndexedFact for O(1) retrieval
    """

    def __init__(self) -> None:
        self._term_index: dict[str, set[str]] = defaultdict(set)
        self._key_index: dict[str, set[str]] = defaultdict(set)
        self._facts: dict[str, IndexedFact] = {}

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add(self, fact_id: str, fact: Any, text: str = "", keys: list[str] | None = None) -> None:
        """Index a fact by its text terms and optional explicit keys."""
        terms = _tokenize(text) if text else set()
        key_set = set(keys or [])

        # Remove previous entry if re-indexing
        self.remove(fact_id)

        indexed = IndexedFact(fact_id=fact_id, fact=fact, terms=terms, keys=key_set)
        self._facts[fact_id] = indexed

        for term in terms:
            self._term_index[term].add(fact_id)
        for key in key_set:
            self._key_index[key.lower()].add(fact_id)

    def remove(self, fact_id: str) -> None:
        """Remove a fact from all indexes."""
        indexed = self._facts.pop(fact_id, None)
        if indexed is None:
            return
        for term in indexed.terms:
            self._term_index[term].discard(fact_id)
        for key in indexed.keys:
            self._key_index[key.lower()].discard(fact_id)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup_key(self, key: str) -> list[Any]:
        """Exact key lookup — returns facts matching the key exactly."""
        fact_ids = self._key_index.get(key.lower(), set())
        return [self._facts[fid].fact for fid in fact_ids if fid in self._facts]

    def lookup_term(self, term: str) -> list[Any]:
        """Single-term lookup — returns all facts containing the term."""
        fact_ids = self._term_index.get(term.lower(), set())
        return [self._facts[fid].fact for fid in fact_ids if fid in self._facts]

    def lookup_terms(self, terms: list[str], mode: str = "any") -> list[Any]:
        """Multi-term lookup.

        mode="any"  — facts matching ANY of the terms (union)
        mode="all"  — facts matching ALL of the terms (intersection)
        """
        if not terms:
            return []
        sets = [self._term_index.get(t.lower(), set()) for t in terms]
        if mode == "all":
            fact_ids = sets[0].copy()
            for s in sets[1:]:
                fact_ids &= s
        else:
            fact_ids = set().union(*sets)
        return [self._facts[fid].fact for fid in fact_ids if fid in self._facts]

    def get_fact(self, fact_id: str) -> Any | None:
        """Direct fact_id → fact lookup."""
        indexed = self._facts.get(fact_id)
        return indexed.fact if indexed else None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def fact_count(self) -> int:
        """Return the number of facts in the index."""
        return len(self._facts)

    def term_count(self) -> int:
        """Return the number of unique terms in the index."""
        return len(self._term_index)

    def clear(self) -> None:
        """Remove all facts and terms from the index."""
        self._term_index.clear()
        self._key_index.clear()
        self._facts.clear()


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + punctuation tokeniser for the inverted index."""
    import re
    tokens = re.findall(r"[a-z0-9_\-]+", text.lower())
    # Filter stop words and very short tokens
    _STOP = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "on", "at", "by", "for", "with", "and",
        "or", "not", "it", "its", "this", "that", "as", "from",
    }
    return {t for t in tokens if len(t) > 2 and t not in _STOP}
