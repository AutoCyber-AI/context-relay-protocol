# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Inbound CRP request-header parsing + Axiom-4 stripping (CRP-SPEC-002/015).

Two responsibilities:

1. :func:`parse_request_headers` — read the client's CRP request preferences
   (safety policy, accepted quality/strategy/risk, conditional-dispatch ETag,
   cache directives, grounding mode, session token, data residency,
   reproducibility seed) into a structured :class:`RequestDirectives`.

2. :func:`strip_crp_headers` — **Axiom 4**: the gateway MUST NOT forward any
   ``CRP-*`` header to the LLM provider.  An *allowlist*-free, prefix-based
   filter guarantees no governance header leaks downstream.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from . import names as H


@dataclass
class RequestDirectives:
    """Structured view of inbound CRP request preferences."""

    safety_policy: str | None = None
    safety_policy_report_only: str | None = None
    safety_mode: str | None = None
    safety_nonce: str | None = None
    accept_quality: list[str] = field(default_factory=list)
    accept_strategy: str | None = None
    accept_risk: str | None = None
    if_match: str | None = None
    cache: list[str] = field(default_factory=list)
    grounding_mode: str | None = None
    session_token: str | None = None
    session_action: str | None = None
    session_parent: str | None = None
    data_residency: str | None = None
    reproducibility_seed: int | None = None
    oversight_token: str | None = None

    @property
    def has_policy(self) -> bool:
        """Return whether this object has policy."""
        return bool(self.safety_policy or self.safety_policy_report_only or self.safety_mode)


def _ci_get(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup against a mapping."""
    target = name.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return v
    return None


def parse_request_headers(headers: Mapping[str, str]) -> RequestDirectives:
    """Parse a mapping of inbound HTTP headers into :class:`RequestDirectives`."""
    d = RequestDirectives()

    d.safety_policy = _ci_get(headers, H.SAFETY_POLICY)
    d.safety_policy_report_only = _ci_get(headers, H.SAFETY_POLICY_REPORT_ONLY)
    d.safety_mode = _ci_get(headers, H.SAFETY_MODE)
    d.safety_nonce = _ci_get(headers, H.SAFETY_NONCE)

    aq = _ci_get(headers, H.ACCEPT_QUALITY)
    if aq:
        d.accept_quality = [t.strip() for t in aq.replace(",", " ").split() if t.strip()]

    d.accept_strategy = _ci_get(headers, H.ACCEPT_STRATEGY)
    d.accept_risk = _ci_get(headers, H.ACCEPT_RISK)
    d.if_match = _ci_get(headers, H.CONTEXT_IF_MATCH)

    cache = _ci_get(headers, H.CONTEXT_CACHE)
    if cache:
        d.cache = [t.strip() for t in cache.split(",") if t.strip()]

    d.grounding_mode = _ci_get(headers, H.LLM_GROUNDING_MODE)
    d.session_token = _ci_get(headers, H.SESSION_TOKEN)
    d.session_action = _ci_get(headers, H.SESSION_ACTION)
    d.session_parent = _ci_get(headers, H.AGENT_SESSION_PARENT)
    d.data_residency = _ci_get(headers, H.COMPLIANCE_DATA_RESIDENCY)
    d.oversight_token = _ci_get(headers, H.OVERSIGHT_TOKEN)

    seed = _ci_get(headers, H.LLM_REPRODUCIBILITY_SEED)
    if seed is not None:
        try:
            d.reproducibility_seed = int(seed)
        except ValueError:
            d.reproducibility_seed = None

    return d


# ---------------------------------------------------------------------------
# Axiom 4 — header stripping
# ---------------------------------------------------------------------------


def strip_crp_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return *headers* with every ``CRP-*`` header removed.

    **Axiom 4 (CRP-SPEC-001/015):** no CRP governance header may reach the LLM
    provider.  This filter is prefix-based so it is robust to future header
    additions — anything starting with ``CRP-`` is dropped.
    """
    return {k: v for k, v in headers.items() if not H.is_crp_header(k)}


def assert_no_crp_headers(headers: Iterable[str]) -> None:
    """Raise ``AssertionError`` if any name in *headers* is a CRP header.

    Intended for conformance tests (TV-002) that verify Axiom-4 compliance on
    the outbound provider request.
    """
    leaked = [name for name in headers if H.is_crp_header(name)]
    if leaked:
        raise AssertionError(f"Axiom 4 violation — CRP headers leaked to provider: {leaked}")


# ---------------------------------------------------------------------------
# SPEC-002 §14.1 — inbound forbidden response-namespace headers
# ---------------------------------------------------------------------------

#: Response-only CRP namespaces a *client* MUST NOT set on a request.  The
#: gateway MUST validate and strip these before processing, otherwise a client
#: could spoof safety/provenance/compliance signals.
FORBIDDEN_REQUEST_PREFIXES: tuple[str, ...] = (
    "CRP-Safety-",
    "CRP-Provenance-",
    "CRP-Compliance-",
    "CRP-Quality-",
)

#: Explicit allowlist of request-side headers that share a forbidden prefix but
#: are legitimately client-settable (declarative inputs, not gateway outputs).
_REQUEST_ALLOWLIST: frozenset[str] = frozenset(
    n.lower()
    for n in (
        H.SAFETY_POLICY,
        H.SAFETY_POLICY_REPORT_ONLY,
        H.SAFETY_MODE,
        H.SAFETY_NONCE,
        H.SAFETY_REPORT_URI,
    )
)


def is_forbidden_request_header(name: str) -> bool:
    """Return ``True`` if *name* is a response-namespace header forbidden on
    requests per SPEC-002 §14.1 (and not on the request allowlist)."""
    upper = name.upper()
    if name.lower() in _REQUEST_ALLOWLIST:
        return False
    return any(upper.startswith(p.upper()) for p in FORBIDDEN_REQUEST_PREFIXES)


def strip_inbound_forbidden_headers(
    headers: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Strip client-spoofed response-namespace headers from an inbound request.

    SPEC-002 §14.1: ``CRP-Safety-*``/``CRP-Provenance-*``/``CRP-Compliance-*``/
    ``CRP-Quality-*`` are gateway-authoritative response headers.  A client MUST
    NOT set them; the gateway MUST strip any it receives.

    Returns ``(cleaned_headers, stripped_names)``.
    """
    cleaned: dict[str, str] = {}
    stripped: list[str] = []
    for k, v in headers.items():
        if is_forbidden_request_header(k):
            stripped.append(k)
        else:
            cleaned[k] = v
    return cleaned, stripped
