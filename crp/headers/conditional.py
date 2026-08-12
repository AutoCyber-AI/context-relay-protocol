# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Conditional dispatch — ETag computation + HTTP 304/424 evaluation (SPEC-002 §4.8-4.11).

This is the library-side decision logic for conditional context dispatch.  A
gateway computes the current CKF fact-set :func:`compute_etag`, compares it to
the client's ``CRP-Context-If-Match`` value, evaluates ``CRP-Context-Cache``
directives, and uses :func:`evaluate_conditional` to decide whether to:

* serve a fresh envelope (HTTP 200, ``Cache-Status: MISS``),
* skip reconstruction and return HTTP 304 (``Cache-Status: HIT``), or
* refuse with HTTP 424 when ``only-if-ckf`` is set but the CKF has no facts.

The actual HTTP response object is the gateway's concern; this module returns a
structured :class:`ConditionalResult` so any transport can act on it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from . import names as H

_MAX_AGE_RE = re.compile(r"^max-age=(\d+)$", re.IGNORECASE)

#: Recognised cache directives (SPEC-002 §4.10).
VALID_CACHE_DIRECTIVES: frozenset[str] = frozenset(
    {"no-store", "no-cache", "reuse-ckf", "only-if-ckf"}
)


def compute_etag(facts: Iterable[tuple[str, str]]) -> str:
    """Compute the CKF fact-set ETag (SPEC-002 §4.8).

    The ETag is ``"sha256:" + SHA-256(sorted "fact_id:content_hash" lines)``.
    Sorting makes the hash order-independent, so two gateways with the same
    fact-set produce the same ETag regardless of insertion order.

    Args:
        facts: iterable of ``(fact_id, content_hash)`` pairs.

    Returns:
        ``"sha256:<hex>"`` — or the canonical empty-set ETag when *facts* is
        empty.
    """
    lines = sorted(f"{fid}:{chash}" for fid, chash in facts)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass
class CacheDirectives:
    """Parsed ``CRP-Context-Cache`` directive set (SPEC-002 §4.10)."""

    no_store: bool = False
    no_cache: bool = False
    reuse_ckf: bool = False
    only_if_ckf: bool = False
    max_age: int | None = None
    unknown: list[str] = field(default_factory=list)


def parse_cache_directives(directives: Sequence[str] | None) -> CacheDirectives:
    """Parse a list of raw cache-directive tokens into :class:`CacheDirectives`."""
    out = CacheDirectives()
    for raw in directives or ():
        token = raw.strip()
        low = token.lower()
        if low == "no-store":
            out.no_store = True
        elif low == "no-cache":
            out.no_cache = True
        elif low == "reuse-ckf":
            out.reuse_ckf = True
        elif low == "only-if-ckf":
            out.only_if_ckf = True
        else:
            m = _MAX_AGE_RE.match(token)
            if m:
                out.max_age = int(m.group(1))
            else:
                out.unknown.append(token)
    return out


@dataclass
class ConditionalResult:
    """Outcome of a conditional-dispatch evaluation."""

    http_status: int  # 200 (build), 304 (not modified), 424 (failed dependency)
    cache_status: str  # HIT / MISS / PARTIAL
    reason: str | None = None
    etag: str | None = None

    @property
    def not_modified(self) -> bool:
        """Return whether the not modified condition holds."""
        return self.http_status == 304

    @property
    def failed_dependency(self) -> bool:
        """Return whether the failed dependency condition holds."""
        return self.http_status == 424

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        out: dict[str, str] = {}
        if self.etag is not None:
            out[H.CONTEXT_ETAG] = self.etag
        status = self.cache_status
        if self.reason:
            status = f"{status}; reason={self.reason}"
        out[H.CONTEXT_CACHE_STATUS] = status
        return out


def evaluate_conditional(
    *,
    if_match: str | None,
    current_etag: str,
    cache: CacheDirectives | Sequence[str] | None = None,
    ckf_has_relevant_facts: bool = True,
) -> ConditionalResult:
    """Decide the conditional-dispatch outcome for one call (SPEC-002 §4.9-4.11).

    Args:
        if_match: client's ``CRP-Context-If-Match`` (an ETag or ``"*"``), or None.
        current_etag: the gateway's freshly computed CKF ETag.
        cache: parsed :class:`CacheDirectives` or a raw token list.
        ckf_has_relevant_facts: whether the CKF holds facts relevant to the query.

    Returns:
        :class:`ConditionalResult`.
    """
    directives = (
        cache if isinstance(cache, CacheDirectives) else parse_cache_directives(cache)
    )

    # only-if-ckf: refuse when the CKF cannot satisfy the query (§4.10 → 424).
    if directives.only_if_ckf and not ckf_has_relevant_facts:
        return ConditionalResult(
            http_status=424,
            cache_status="MISS",
            reason="only-if-ckf",
            etag=current_etag,
        )

    # no-cache forces a full rebuild even if the ETag matches (§4.10).
    if directives.no_cache:
        return ConditionalResult(
            http_status=200, cache_status="MISS", reason="no-cache", etag=current_etag
        )

    # Conditional match → 304 Context Not Modified (§4.9).
    if if_match is not None and (if_match == "*" or if_match == current_etag):
        return ConditionalResult(
            http_status=304, cache_status="HIT", etag=current_etag
        )

    return ConditionalResult(http_status=200, cache_status="MISS", etag=current_etag)
