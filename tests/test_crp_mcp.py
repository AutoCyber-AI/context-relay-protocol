# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the CRP MCP server (local tools + hosted stub fallbacks)."""

from __future__ import annotations

import json
import os

import pytest

from crp_mcp import config_tools, corpus, headers_lint, scaffold
from crp_mcp.server import (
    crp_compare,
    crp_conformance_check,
    crp_create_api_key,
    crp_deploy_endpoint,
    crp_explain,
    crp_generate_config,
    crp_generate_safety_policy,
    crp_get_plan,
    crp_lint_headers,
    crp_migrate_v3_v4,
    crp_safety_registry,
    crp_scaffold_integration,
    crp_sdk_example,
    crp_spec_lookup,
    crp_test_call,
    crp_upgrade_link,
    crp_validate_config,
    crp_whoami,
)


class _FakeCtx:
    """Minimal stand-in for an MCP Context object."""

    def __init__(self) -> None:
        self.request_context = None


@pytest.fixture
def ctx() -> _FakeCtx:
    return _FakeCtx()


@pytest.mark.asyncio
async def test_explain_returns_sources() -> None:
    result = await crp_explain(topic="grounding")
    data = json.loads(result)
    assert data["ok"]
    assert "grounding" in data["answer"].lower()
    assert data["sources"]


@pytest.mark.asyncio
async def test_spec_lookup_refuses_unknown_topic() -> None:
    result = await crp_spec_lookup(topic="xyz_nonexistent_12345")
    data = json.loads(result)
    assert data["ok"]
    assert not data["excerpts"]
    assert "no match" in data["note"].lower()


@pytest.mark.asyncio
async def test_compare_mcp() -> None:
    result = await crp_compare(against="MCP")
    data = json.loads(result)
    assert data["ok"]
    assert "transport" in data["comparison"].lower()


@pytest.mark.asyncio
async def test_scaffold_python_openai() -> None:
    result = await crp_scaffold_integration(stack="python-openai")
    data = json.loads(result)
    assert data["ok"]
    assert "gateway.crprotocol.io" in data["code"]


@pytest.mark.asyncio
async def test_generate_config_from_intent() -> None:
    result = await crp_generate_config(intent_json='{"grounding_threshold": 0.85}')
    data = json.loads(result)
    assert data["ok"]
    assert data["valid"]
    assert "grounding" in data["config_yaml"].lower()


@pytest.mark.asyncio
async def test_generate_safety_policy() -> None:
    result = await crp_generate_safety_policy(
        intent_json='{"grounding_threshold": 0.85, "halt_on": "HIGH"}'
    )
    data = json.loads(result)
    assert data["ok"]
    assert "require-grounding" in data["policy"]
    assert "halt-on HIGH" in data["policy"]


@pytest.mark.asyncio
async def test_validate_config_valid() -> None:
    yaml_text = """
version: "4.0"
safety:
  profile: balanced
"""
    result = await crp_validate_config(yaml_text=yaml_text)
    data = json.loads(result)
    assert data["ok"]
    assert data["valid"]
    assert not data["errors"]


@pytest.mark.asyncio
async def test_validate_config_invalid_profile() -> None:
    yaml_text = """
version: "4.0"
safety:
  profile: unknown-profile
"""
    result = await crp_validate_config(yaml_text=yaml_text)
    data = json.loads(result)
    assert data["ok"]
    assert not data["valid"]
    assert any("profile" in e for e in data["errors"])


@pytest.mark.asyncio
async def test_lint_headers() -> None:
    source = 'headers = {"CRP-Safety-Hallucination-Risk": "HIGH", "CRP-Fake-Header": "x"}'
    result = await crp_lint_headers(source_text=source)
    data = json.loads(result)
    assert not data["ok"]
    assert data["unknown_count"] == 1


@pytest.mark.asyncio
async def test_conformance_check_runs() -> None:
    result = await crp_conformance_check(level="all")
    data = json.loads(result)
    assert data["ok"]
    assert "total" in data
    assert "passed" in data


@pytest.mark.asyncio
async def test_safety_registry() -> None:
    result = await crp_safety_registry()
    data = json.loads(result)
    assert data["ok"]
    assert any(cap["name"] == "grounding_verification" for cap in data["capabilities"])


@pytest.mark.asyncio
async def test_sdk_example_unknown_task() -> None:
    result = await crp_sdk_example(task="unknown")
    data = json.loads(result)
    assert not data["ok"]


@pytest.mark.asyncio
async def test_migrate_guidance() -> None:
    result = await crp_migrate_v3_v4()
    data = json.loads(result)
    assert data["ok"]
    assert "SDKClient" in data["guidance"]


@pytest.mark.asyncio
async def test_hosted_stubs_without_config(ctx: _FakeCtx) -> None:
    """Hosted tools must degrade gracefully when Clerk/Stripe env is missing."""
    os.environ.pop("CLERK_ISSUER", None)
    os.environ.pop("CLERK_AUTHORIZED_PARTIES", None)
    os.environ.pop("CLERK_SECRET_KEY", None)

    for fn, kwargs in (
        (crp_whoami, {"ctx": ctx}),
        (crp_upgrade_link, {"product": "gateway", "plan": "pro", "ctx": ctx}),
        (crp_create_api_key, {"ctx": ctx}),
        (crp_test_call, {"ctx": ctx}),
        (crp_deploy_endpoint, {"pipeline_id": "pipe-123", "ctx": ctx}),
        (crp_get_plan, {"product": "gateway", "ctx": ctx}),
    ):
        result = await fn(**kwargs)  # type: ignore[operator]
        data = json.loads(result)
        assert data["ok"]
        assert data.get("configured") is False


# ---------------------------------------------------------------------------
# Unit tests for helper modules
# ---------------------------------------------------------------------------
def test_corpus_search_finds_grounding() -> None:
    corp = corpus.SpecCorpus()
    chunks = corp.search("grounding", top_k=3)
    assert chunks
    assert any("ground" in c.heading_path.lower() for c in chunks)


def test_scaffold_rejects_unknown_stack() -> None:
    out = scaffold.integration("fortran")
    assert "not in the built-in scaffold catalogue" in out


def test_config_tools_validation() -> None:
    result = config_tools.validate_config_yaml('version: "4.0"\n')
    assert result["valid"]


def test_headers_lint_known_unknown() -> None:
    result = headers_lint.lint("CRP-Safety-Policy: strict; CRP-Not-Real: x")
    assert result["unknown_count"] == 1
    assert result["ok"] is False


def test_no_eval_or_exec_in_modules() -> None:
    """Static check: config_tools and scaffold must not use eval/exec."""
    import inspect

    for mod in (config_tools, scaffold, headers_lint):
        source = inspect.getsource(mod)
        assert "eval(" not in source
        assert "exec(" not in source


# ---------------------------------------------------------------------------
# Expanded MCP capability tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_safety_profile() -> None:
    from crp_mcp.safety_tools import crp_safety_profile

    result = await crp_safety_profile(profile="balanced")
    data = json.loads(result)
    assert data["ok"]
    assert "require-grounding" in data["policy_directive"]


@pytest.mark.asyncio
async def test_safety_explain() -> None:
    from crp_mcp.safety_tools import crp_safety_explain

    result = await crp_safety_explain(key="grounding_verification")
    data = json.loads(result)
    assert data["ok"]
    assert "ground" in data["key"].lower()


@pytest.mark.asyncio
async def test_envelope_preview() -> None:
    from crp_mcp.dpe_tools import crp_envelope_preview

    payload = '{"task": "summarise", "messages": [{"role": "user", "content": "hi"}]}'
    result = await crp_envelope_preview(payload_json=payload)
    data = json.loads(result)
    assert data["ok"]
    assert data["preview"]["messages_count"] == 1


@pytest.mark.asyncio
async def test_context_strategy() -> None:
    from crp_mcp.dpe_tools import crp_context_strategy

    result = await crp_context_strategy(task="write a complete user guide")
    data = json.loads(result)
    assert data["ok"]
    assert data["recommended"]["depth"] in {"standard", "thorough"}


@pytest.mark.asyncio
async def test_estimate_cost() -> None:
    from crp_mcp.dpe_tools import crp_estimate_cost

    result = await crp_estimate_cost(
        payload_json='{"messages": [{"role": "user", "content": "hello"}], "expected_output_tokens": 100}'
    )
    data = json.loads(result)
    assert data["ok"]
    assert data["estimated_usd"] >= 0


@pytest.mark.asyncio
async def test_build_session() -> None:
    from crp_mcp.dpe_tools import crp_build_session

    result = await crp_build_session(name="test")
    data = json.loads(result)
    assert data["ok"]
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_scan_local_preview() -> None:
    from crp_mcp.scan_tools import crp_scan_local_preview

    source = 'import openai\nclient = openai.OpenAI(api_key="sk-xxx")\n'
    result = await crp_scan_local_preview(source_text=source)
    data = json.loads(result)
    assert data["ok"]
    assert data["findings"]
    assert any("OpenAI" in f["pattern"] for f in data["findings"])


@pytest.mark.asyncio
async def test_remediation_plan() -> None:
    from crp_mcp.scan_tools import crp_remediation_plan

    result = await crp_remediation_plan(finding_json='[{"pattern": "OpenAI client"}]')
    data = json.loads(result)
    assert data["ok"]
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_comply_policy() -> None:
    from crp_mcp.comply_tools import crp_comply_policy

    result = await crp_comply_policy(framework="EU AI Act")
    data = json.loads(result)
    assert data["ok"]
    assert any("grounding" in m["control"] for m in data["mappings"])


@pytest.mark.asyncio
async def test_gateway_status_without_config() -> None:
    from crp_mcp.gateway_tools import crp_gateway_status

    result = await crp_gateway_status()
    data = json.loads(result)
    assert data["ok"]
    assert data["configured"] is False


@pytest.mark.asyncio
async def test_resource_spec() -> None:
    from crp_mcp.resources import get_spec_resource

    text = await get_spec_resource("CRP-SPEC-001")
    assert "CRP-SPEC-001" in text or "# Not found" in text


@pytest.mark.asyncio
async def test_resource_schema() -> None:
    from crp_mcp.resources import get_schema_resource

    text = await get_schema_resource("session-handle")
    data = json.loads(text)
    assert "$schema" in data or "type" in data


@pytest.mark.asyncio
async def test_completion_for_stack() -> None:
    from mcp.types import CompletionArgument, PromptReference

    from crp_mcp.completions import handle_completion

    result = await handle_completion(
        PromptReference(name="integrate_crp", type="ref/prompt"),
        CompletionArgument(name="stack", value="pyth"),
        None,
    )
    assert result is not None
    assert any("python" in v for v in result.values)


# ---------------------------------------------------------------------------
# Agent-centric builder tools
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_specs() -> None:
    from crp_mcp.agent_tools import crp_list_specs

    result = await crp_list_specs()
    data = json.loads(result)
    assert data["ok"]
    assert "CRP-SPEC-001" in data["specs"] or data["count"] > 0


@pytest.mark.asyncio
async def test_read_spec() -> None:
    from crp_mcp.agent_tools import crp_read_spec

    result = await crp_read_spec(spec_id="CRP-SPEC-001")
    data = json.loads(result)
    assert data["ok"]
    assert "Core Protocol" in data["title"] or "CRP-SPEC-001" in data["text"]


@pytest.mark.asyncio
async def test_build_integration_plan() -> None:
    from crp_mcp.agent_tools import crp_build_integration_plan

    result = await crp_build_integration_plan(
        goal="govern all LLM calls", stack="python-openai", safety_profile="balanced"
    )
    data = json.loads(result)
    assert data["ok"]
    assert "crp.config.yaml" in data["plan"]


@pytest.mark.asyncio
async def test_validate_safety_policy() -> None:
    from crp_mcp.agent_tools import crp_validate_safety_policy

    result = await crp_validate_safety_policy(
        policy="default-src 'self'; halt-on CRITICAL; require-grounding 0.8"
    )
    data = json.loads(result)
    assert data["ok"]
    assert data["valid"]


@pytest.mark.asyncio
async def test_config_from_text() -> None:
    from crp_mcp.agent_tools import crp_config_from_text

    result = await crp_config_from_text(
        description="Prevent hallucinations, require grounding, redact PII"
    )
    data = json.loads(result)
    assert data["ok"]
    assert data["config"]["valid"]
    assert "grounding" in data["policy"]["policy"].lower()


@pytest.mark.asyncio
async def test_audit_project() -> None:
    from crp_mcp.agent_tools import crp_audit_project

    result = await crp_audit_project(source_text="openai.OpenAI()")
    data = json.loads(result)
    assert data["ok"]
    assert data["findings"]


@pytest.mark.asyncio
async def test_quickstart() -> None:
    from crp_mcp.agent_tools import crp_quickstart

    result = await crp_quickstart()
    data = json.loads(result)
    assert data["ok"]
    assert "CRPv4 quickstart" in data["guide"]
