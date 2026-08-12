# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SDK response types — the ``.crp`` governance summary object (SPEC-032 §2.3).

At Level 0 the developer sees a five-field summary, not 58 headers::

    response = client.complete("Summarise the EU AI Act")
    print(response.crp.risk)         # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    print(response.crp.grounded)     # bool
    print(response.crp.fabrications) # int
    print(response.crp.chain_valid)  # bool
    print(response.crp.audit_url)    # tamper-evident deep link

At Level 1 quality signals are added::

    a = client.ask("Write a complete deployment guide")
    print(a.quality)     # "S" | "A" | "B" | "C" | "D"
    print(a.sources)     # [{title, doc_id, used_facts}]
    print(a.complete)    # bool — covered whole task
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Level 0 — Governance summary ───────────────────────────────────────────


@dataclass
class CRPResponseMeta:
    """The one governance object — five fields, not 58 headers (SPEC-032 §2.3)."""

    risk: str = "LOW"                 # LOW | MEDIUM | HIGH | CRITICAL
    grounded: bool = True
    fabrications: int = 0
    chain_valid: bool = True
    audit_url: str = ""
    compliant: bool = True            # EU AI Act / ISO mapping result
    injection_detected: bool = False
    pii_detected: bool = False
    safety_budget_remaining: float = 1.0
    session_id: str = ""              # stable session identifier
    window_id: str = ""               # turn-scoped window identifier


@dataclass
class CRPCompletionResponse:
    """Level 0 response — drop-in governance (SPEC-032 §2)."""

    text: str = ""
    crp: CRPResponseMeta = field(default_factory=CRPResponseMeta)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw_headers: dict[str, str] = field(default_factory=dict)  # infrastructure access

    def __str__(self) -> str:
        return self.text


# ── Level 1 — Quality + sources ────────────────────────────────────────────


@dataclass
class SourceAttribution:
    """One source document cited in the response."""

    title: str = ""
    doc_id: str = ""
    used_facts: int = 0
    relevance_score: float = 0.0


@dataclass
class CRPAskResponse:
    """Level 1+2 response — quality-aware with inspectable reasoning (SPEC-032 §3–4)."""

    text: str = ""
    quality: str = "B"                # S | A | B | C | D
    sources: list[SourceAttribution] = field(default_factory=list)
    complete: bool = False            # covered whole task
    crp: CRPResponseMeta = field(default_factory=CRPResponseMeta)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw_headers: dict[str, str] = field(default_factory=dict)
    # Level 2 — inspect reasoning
    decisions: list[dict[str, Any]] = field(default_factory=list)
    how_it_was_built: str = ""        # STL operation sequence, human-readable
    open_questions: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.text
