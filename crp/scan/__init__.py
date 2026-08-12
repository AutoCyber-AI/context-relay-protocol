# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Scan — static AI-governance scanner + Remediation Engine.

Public API:
    SemanticCodeIngestion  — SPEC-039 code knowledge graph builder
    RemediationEngine      — SPEC-036 diff + PR proposal generator
    ScanFinding            — finding data model
    RemediationProposal    — proposal data model
    AICallSite             — detected call site data model
    CodeGraph              — code knowledge graph
    CodeFact               — code entity fact
"""

from __future__ import annotations

from .remediation import RemediationEngine, RemediationProposal, ScanFinding
from .semantic_ingestion import AICallSite, CodeFact, CodeGraph, SemanticCodeIngestion

__all__ = [
    "AICallSite",
    "CodeFact",
    "CodeGraph",
    "RemediationEngine",
    "RemediationProposal",
    "ScanFinding",
    "SemanticCodeIngestion",
]
