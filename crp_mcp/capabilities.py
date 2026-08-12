# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRPv4 capability catalogue — specs, keywords, intents, examples.

This module is the single source of truth for what CRPv4 can do, so the MCP server
can explain it, scaffold it, validate intent against it, and refuse to fabricate.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _spec_titles() -> dict[str, str]:
    """Scan site-docs/spec for spec ids and titles."""
    titles: dict[str, str] = {}
    roots = [Path.cwd(), Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent / "spec_corpus"]
    for root in roots:
        spec_dir = root / "site-docs/spec"
        if not spec_dir.is_dir():
            continue
        for path in sorted(spec_dir.glob("CRP-SPEC-*.md")):
            m = re.search(r"CRP-SPEC-([0-9]+|[A-Z-]+)", path.name)
            if not m:
                continue
            spec_id = f"CRP-SPEC-{m.group(1)}"
            try:
                first = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
            except Exception:
                continue
            title = first.lstrip("# ").strip() if first.startswith("#") else spec_id
            titles[spec_id] = title
    return titles


CRP_SPECS: dict[str, str] = _spec_titles()

CRP_TOPICS: dict[str, str] = {
    "ai-compliance": "AI compliance overview",
    "ai-governance": "AI governance overview",
    "ai-safety": "AI safety overview",
    "context-management": "Context management in CRP",
    "crp-vs-rag-mcp": "CRP vs RAG, MCP, A2A, AIPREF",
    "index": "Topics index",
}

CRP_SCHEMAS: list[str] = [
    "cost-estimate",
    "crp-error",
    "envelope-preview",
    "openapi",
    "persisted-state-header",
    "quality-report",
    "session-handle",
    "session-status",
    "stream-event",
    "task-intent",
]

SAFETY_PROFILES: list[str] = ["balanced", "strict", "medical", "financial", "public"]

CONTEXT_MODES: list[str] = ["auto", "document", "conversation", "hybrid", "zero-ckf"]

DEPTH_LEVELS: list[str] = ["auto", "quick", "standard", "thorough", "exhaustive"]

STORAGE_BACKENDS: list[str] = ["memory", "sqlite", "redis", "s3"]

SUPPORTED_STACKS: list[str] = [
    "python-openai",
    "python-anthropic",
    "node-openai",
    "node-anthropic",
    "typescript-openai",
    "langchain",
    "fastapi",
    "django",
    "nextjs",
    "cli",
    "docker",
]

SDK_TASKS: list[str] = [
    "ingest",
    "ask",
    "complete",
    "tool",
    "session",
    "safety",
    "checkpoint",
    "profile",
    "audit",
    "conformance",
    "migrate",
]

# ---------------------------------------------------------------------------
# CRPv4 capability map — each entry ties a user-facing intent to specs and code.
# ---------------------------------------------------------------------------
CRP_CAPABILITY_MAP: list[dict[str, Any]] = [
    {
        "name": "governance_drop_in",
        "description": "Govern every LLM call with a one-line base_url change",
        "specs": ["CRP-SPEC-032"],
        "intents": ["govern_calls", "drop_in_governance"],
        "sdk": "client = crp.SDKClient(api_key=CRP_API_KEY); client.complete(...)",
    },
    {
        "name": "grounded_generation",
        "description": "Generate answers grounded in the developer's knowledge (CKF)",
        "specs": ["CRP-SPEC-009", "CRP-SPEC-025", "CRP-SPEC-032"],
        "intents": ["ground_answers", "ingest_docs", "reduce_hallucinations"],
        "sdk": "client.knowledge.ingest('docs/'); answer = client.ask('...')",
    },
    {
        "name": "hallucination_detection",
        "description": "Detect fabrications, distortions, and contradictions in LLM output",
        "specs": ["CRP-SPEC-005"],
        "intents": ["prevent_hallucinations", "detect_fabrications", "detect_distortions"],
        "sdk": "answer.crp.risk, answer.crp.grounded",
    },
    {
        "name": "safety_policy_enforcement",
        "description": "Declare and enforce a CSP-like safety policy with halts",
        "specs": ["CRP-SPEC-006", "CRP-SPEC-033"],
        "intents": ["safety_policy", "halt_on_risk", "block_pii", "block_fabrication"],
        "sdk": "client.safety.set_profile('medical'); client.safety.set(...)",
    },
    {
        "name": "human_in_the_loop",
        "description": "Inline checkpoints that pause for human approval",
        "specs": ["CRP-SPEC-033"],
        "intents": ["human_oversight", "checkpoint_review", "require_approval"],
        "sdk": "client.safety.checkpoint(trigger='RISK_HIGH')",
    },
    {
        "name": "tamper_evident_audit",
        "description": "HMAC-chain audit trail for every governed call",
        "specs": ["CRP-SPEC-011"],
        "intents": ["audit_trail", "compliance_evidence", "tamper_evident"],
        "sdk": "client.audit.export()",
    },
    {
        "name": "multi_agent_safety_budget",
        "description": "Cumulative risk budget across agent chains",
        "specs": ["CRP-SPEC-012"],
        "intents": ["agent_budget", "multi_agent_safety", "circuit_breaker"],
        "sdk": "answer.crp.safety_budget_remaining",
    },
    {
        "name": "semantic_task_layer",
        "description": "Classify tasks, negotiate depth, and choose retrieval strategy",
        "specs": ["CRP-SPEC-031"],
        "intents": ["task_classification", "depth_control", "strategy_selection"],
        "sdk": "client.ask('...', depth='thorough')",
    },
    {
        "name": "continuation",
        "description": "Continue generation across model context/output windows",
        "specs": ["CRP-SPEC-004"],
        "intents": ["long_output", "continuation", "unbounded_generation"],
        "sdk": "continuation handled automatically by the Gateway",
    },
    {
        "name": "conversational_context",
        "description": "Multi-turn conversation with reference resolution",
        "specs": ["CRP-SPEC-028"],
        "intents": ["chat", "conversation", "reference_resolution"],
        "sdk": "chat = client.session(); chat.ask('...')",
    },
    {
        "name": "compliance_mapping",
        "description": "Map calls to EU AI Act, ISO 42001, GDPR, NIST",
        "specs": ["CRP-SPEC-010", "CRP-SPEC-040"],
        "intents": ["compliance", "eu_ai_act", "iso_42001", "gdpr"],
        "sdk": "answer.crp.compliant",
    },
    {
        "name": "crp_scan",
        "description": "Find ungoverned AI calls in a codebase and remediate",
        "specs": ["CRP-SPEC-013", "CRP-SPEC-036"],
        "intents": ["scan_repo", "find_ungoverned_ai", "remediation"],
        "sdk": "CRP Scan GitHub Action or crp_scan_repo MCP tool",
    },
    {
        "name": "gateway_runtime",
        "description": "Hosted governed AI runtime with visual console",
        "specs": ["CRP-SPEC-016", "CRP-SPEC-043"],
        "intents": ["gateway", "hosted_runtime", "deploy_endpoint"],
        "sdk": "OpenAI client with base_url=https://gateway.crprotocol.io/v1",
    },
    {
        "name": "storage_backends",
        "description": "Pluggable warm-state storage (memory/sqlite/redis/s3)",
        "specs": ["CRP-SPEC-038"],
        "intents": ["storage", "state_backend", "redis", "s3"],
        "sdk": "context.storage.backend config key",
    },
    {
        "name": "conformance_vectors",
        "description": "Standardized test vectors for CRP implementations",
        "specs": ["CRP-SPEC-014"],
        "intents": ["conformance", "test_vectors", "certification"],
        "sdk": "crp.conformance.run()",
    },
    {
        "name": "authoritative_domain_agent",
        "description": "Agent bound to an official corpus that refuses to fabricate",
        "specs": ["CRP-SPEC-044"],
        "intents": ["ada", "authoritative_agent", "corpus_grounded"],
        "sdk": "CRP Comply agent mode",
    },
    {
        "name": "semantic_quality_benchmark",
        "description": "Benchmark quality by factual F1 + judge score",
        "specs": ["CRP-SPEC-026"],
        "intents": ["benchmark", "quality", "factual_f1"],
        "sdk": "crp_benchmark MCP tool",
    },
]


def capability_names() -> list[str]:
    return [c["name"] for c in CRP_CAPABILITY_MAP]


def capability_by_name(name: str) -> dict[str, Any] | None:
    for cap in CRP_CAPABILITY_MAP:
        if cap["name"] == name:
            return cap
    return None


def specs_for_intent(intent: str) -> list[str]:
    out: list[str] = []
    for cap in CRP_CAPABILITY_MAP:
        if intent.lower() in [i.lower() for i in cap["intents"]]:
            out.extend(cap["specs"])
    return sorted(set(out))
