# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Local-only MCP tools: knowledge, validation, scaffolds, conformance.

These tools never call remote backends and need no authentication.
"""

from __future__ import annotations

import json
from typing import Annotated

import yaml  # type: ignore[import-untyped]
from pydantic import Field

from crp_mcp.capabilities import CRP_CAPABILITY_MAP, CRP_TOPICS
from crp_mcp.config_tools import generate_config, generate_safety_policy, validate_config_yaml
from crp_mcp.corpus import get_corpus
from crp_mcp.headers_lint import lint as lint_headers
from crp_mcp.scaffold import integration as scaffold_integration
from crp_mcp.types import err, ok


# ---------------------------------------------------------------------------
# Input models kept for re-export / external callers.
# ---------------------------------------------------------------------------
class ExplainInput:
    topic: str


class SpecLookupInput:
    topic: str


class CompareInput:
    against: str


class ScaffoldInput:
    stack: str
    goal: str


class GenerateConfigInput:
    intent_json: str


class GeneratePolicyInput:
    intent_json: str


class SdkExampleInput:
    task: str


class ValidateConfigInput:
    yaml_text: str


class LintHeadersInput:
    source_text: str


class ConformanceInput:
    level: str


class CapabilityMapInput:
    intent: str


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
async def crp_explain(
    topic: Annotated[
        str,
        Field(description="A CRPv4 concept or spec, e.g. 'CDR', 'STL', 'safety policy'.", min_length=1, max_length=200),
    ],
) -> str:
    """Explain a CRPv4 concept, grounded in and cited from the authoritative CRP specs."""
    corpus = get_corpus()
    if not corpus.available():
        return err("Spec corpus not found. Set CRP_SPEC_CORPUS to the repo root containing site-docs/")
    result = corpus.explain(topic, top_k=5)
    return ok(result)


async def crp_spec_lookup(
    topic: Annotated[
        str,
        Field(description="A CRPv4 topic to look up in the specs.", min_length=1, max_length=200),
    ],
) -> str:
    """Retrieve authoritative CRP spec excerpts with citations."""
    corpus = get_corpus()
    if not corpus.available():
        return err("Spec corpus not found. Set CRP_SPEC_CORPUS to the repo root containing site-docs/")
    result = corpus.lookup(topic, top_k=3)
    return ok(result)


async def crp_compare(
    against: Annotated[
        str,
        Field(description="Compare CRP to one of: MCP, A2A, AIPREF, RAG, vector-DB.", min_length=1, max_length=60),
    ],
) -> str:
    """Compare CRP to MCP, A2A, AIPREF, RAG, or vector-DB."""
    target = against.lower().strip()
    comparisons: dict[str, str] = {
        "mcp": (
            "MCP standardises how AI agents discover and call tools; CRP governs the "
            "inference calls those tools make. Use MCP for tool transport, CRP for "
            "safety, grounding, provenance, and compliance. (site-docs/topics/crp-vs-rag-mcp.md)"
        ),
        "a2a": (
            "A2A standardises agent-to-agent messaging; CRP governs the LLM calls "
            "inside each agent and carries multi-agent safety budgets across loops. "
            "Use A2A for inter-agent choreography, CRP for governed reasoning. "
            "(site-docs/spec/CRP-SPEC-012-multi-agent-safety.md)"
        ),
        "aipref": (
            "AIPREF expresses training-data preferences (opt-in/opt-out). CRP is a "
            "runtime governance layer for inference, not a training-preference protocol. "
            "They are complementary. (site-docs/topics/crp-vs-rag-mcp.md)"
        ),
        "rag": (
            "RAG retrieves relevant documents and passes them to an LLM. CRP includes "
            "retrieval (CKF/CDGR) but adds safety policy, risk scoring, continuation, "
            "and tamper-evident audit. Use RAG for simple retrieval; use CRP when "
            "governance and provenance matter. (site-docs/topics/crp-vs-rag-mcp.md)"
        ),
        "vector-db": (
            "A vector database is a retrieval component. CRP's CKF can use vector "
            "stores but adds graph retrieval, source attestation, safety policy, and "
            "audit. CRP is not a replacement for a vector DB; it is a governance layer "
            "that may sit above one. (site-docs/spec/CRP-SPEC-009-ckf.md)"
        ),
    }
    for key, text in comparisons.items():
        if key in target or target.replace(" ", "-").replace("_", "-") == key:
            return ok({"against": against, "comparison": text})
    return err(
        f"No built-in comparison for '{against}'. "
        "Try one of: MCP, A2A, AIPREF, RAG, vector-DB."
    )


async def crp_scaffold_integration(
    stack: Annotated[
        str,
        Field(description="Target stack, e.g. 'python-openai', 'node-openai', 'langchain', 'fastapi'.", min_length=1, max_length=60),
    ],
    goal: Annotated[
        str,
        Field(default="govern all LLM calls", description="What the integration should achieve.", max_length=300),
    ] = "govern all LLM calls",
) -> str:
    """Generate integration code (the base_url swap + minimal config) for a stack."""
    code = scaffold_integration(stack=stack, goal=goal)
    return ok({"stack": stack, "code": code})


async def crp_generate_config(
    intent_json: Annotated[
        str,
        Field(description='JSON object of governance intent, e.g. {"prevent_hallucinations": true, "grounding_threshold": 0.85}.', min_length=1, max_length=5000),
    ],
) -> str:
    """Turn plain-language governance intent into a valid crp.config.yaml fragment."""
    try:
        intent = json.loads(intent_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON intent: {exc}")
    if not isinstance(intent, dict):
        return err("intent_json must be a JSON object.")
    result = generate_config(intent)
    return ok(result)


async def crp_generate_safety_policy(
    intent_json: Annotated[
        str,
        Field(description='JSON object of safety intent, e.g. {"grounding_threshold": 0.85, "halt_on": "HIGH"}.', min_length=1, max_length=5000),
    ],
) -> str:
    """Turn plain-language safety intent into a CRP-Safety-Policy directive string."""
    try:
        intent = json.loads(intent_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON intent: {exc}")
    if not isinstance(intent, dict):
        return err("intent_json must be a JSON object.")
    result = generate_safety_policy(intent)
    return ok(result)


async def crp_sdk_example(
    task: Annotated[
        str,
        Field(default="ingest", description="SDK task: 'ingest', 'ask', 'complete', 'tool', 'safety', 'checkpoint', 'session', 'profile', 'audit', 'conformance', 'migrate'.", max_length=60),
    ] = "ingest",
) -> str:
    """Return a copy-paste CRP SDK snippet for a common task."""
    task_norm = task.lower().strip()
    examples: dict[str, str] = {
        "ingest": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.knowledge.ingest("docs/")\n',
        "ask": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.knowledge.ingest("docs/")\nanswer = client.ask("What is our refund policy?")\nprint(answer.text)\nprint(answer.crp.risk, answer.crp.grounded)\n',
        "complete": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nr = client.complete("Summarise the EU AI Act")\nprint(r.text)\nprint(r.crp.risk, r.crp.grounded)\n',
        "tool": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\n\n@client.tool\ndef get_metrics(service: str) -> dict:\n    return {"cpu": 0.5}\n\nanswer = client.ask("How is the API service doing?", depth="thorough")\nprint(answer.text)\n',
        "safety": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.safety.set(require_grounding=0.8, hallucination_halt="HIGH")\nclient.safety.set_profile("medical")\nprint(client.safety.show())\n',
        "checkpoint": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\ncheckpoint = client.safety.checkpoint(trigger="RISK_HIGH")\n',
        "session": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nsession = client.session()\nprint(session.id, session.status)\n',
        "profile": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.safety.set_profile("medical")\nprint(client.safety.show())\n',
        "audit": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.audit.export(format="jsonl")\n',
        "conformance": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nreport = client.conformance.run(level="standard")\nprint(report.passed, report.summary)\n',
        "migrate": 'import crp\n# v3 -> v4: use crp.SDKClient, crp.config.yaml, and client.safety.* helpers\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\n',
    }
    code = examples.get(task_norm)
    if code is None:
        return err(f"Unknown task '{task}'. Try one of: {', '.join(examples)}.")
    return ok({"task": task, "code": code})


async def crp_migrate_v3_v4() -> str:
    """Return high-level CRP v3 to v4 migration guidance."""
    guidance = """CRP v3 → v4 migration checklist (see CRP-SPEC-032 and CRP-SPEC-037):

1. Use `crp.SDKClient` instead of the legacy `crp.Client` alias for progressive disclosure.
2. Move custom config into `crp.config.yaml` with `version: "4.0"`.
3. Replace hand-written `CRP-*` header logic with `client.safety.*` helpers.
4. Adopt `client.knowledge.ingest()` + `client.ask()` for grounded generation.
5. Use the Safety Control Plane (`client.safety.show()`, `client.safety.set()`) instead of raw policy strings.
6. Verify with `crp_validate_config` and `crp_conformance_check`.
"""
    return ok({"guidance": guidance})


async def crp_validate_config(
    yaml_text: Annotated[
        str,
        Field(description="A crp.config.yaml document to validate.", min_length=1, max_length=50000),
    ],
) -> str:
    """Validate a crp.config.yaml against the CRP v4 schema."""
    try:
        yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return err(f"YAML parse error: {exc}")
    result = validate_config_yaml(yaml_text)
    return ok(result)


async def crp_lint_headers(
    source_text: Annotated[
        str,
        Field(description="Source code or header dump to lint for CRP-* usage.", min_length=1, max_length=50000),
    ],
) -> str:
    """Check CRP-* header usage for correctness and anti-patterns."""
    result = lint_headers(source_text)
    return ok(result)


async def crp_conformance_check(
    level: Annotated[
        str,
        Field(default="all", description="Conformance level filter: 'basic', 'standard', 'full', or 'all'.", max_length=20),
    ] = "all",
) -> str:
    """Run the CRP conformance vectors locally and return a summary."""
    try:
        from tests.conformance.runner import run_all
    except Exception as exc:
        return err(
            f"Conformance runner not available in this environment: {exc}. "
            "Run from the repo source with pytest tests/conformance/"
        )
    try:
        results = run_all()
    except Exception as exc:
        return err(f"Conformance run failed: {exc}")

    level_filter = level.lower().strip()
    filtered = [
        r
        for r in results
        if level_filter in {"all", ""} or r.conformance_level == level_filter
    ]
    total = len(filtered)
    passed = sum(1 for r in filtered if r.passed)
    failures = [
        {"test_id": r.test_id, "category": r.category, "failures": r.failures}
        for r in filtered
        if not r.passed
    ]
    return ok(
        {
            "level_filter": level_filter,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "failures": failures,
        }
    )


async def crp_safety_registry() -> str:
    """Return the CRP Safety Control Plane registry."""
    from crp.security.control_plane import get_default_control_plane

    cp = get_default_control_plane()
    return ok(
        {
            "capabilities": [cap.to_dict() for cap in cp.list_capabilities()],
            "out_of_scope": list(cp.coverage.out_of_scope),
        }
    )


async def crp_capability_map(
    intent: Annotated[
        str,
        Field(default="", description="Optional intent keyword to filter capabilities.", max_length=100),
    ] = "",
) -> str:
    """List every CRPv4 capability and the specs/SDKs needed to implement it."""
    intent_norm = intent.lower().strip()
    if intent_norm:
        caps = [
            c
            for c in CRP_CAPABILITY_MAP
            if any(intent_norm in i for i in c["intents"])
            or intent_norm in c["name"]
            or intent_norm in c["description"].lower()
        ]
    else:
        caps = CRP_CAPABILITY_MAP
    return ok({"capabilities": caps, "count": len(caps)})


async def crp_list_topics() -> str:
    """List available CRP topic pages."""
    corpus = get_corpus()
    if not corpus.available():
        return err("Spec corpus not found.")
    topics = corpus.list_topics()
    # Merge with capability catalogue topics.
    merged = {**{k: k for k in CRP_TOPICS}, **topics}
    return ok({"topics": merged})
