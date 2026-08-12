# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""End-to-end MCP server coverage — every tool, resource, prompt, and completion."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from mcp.types import CompletionArgument, PromptReference, ResourceTemplateReference

from crp_mcp.completions import handle_completion
from crp_mcp.server import mcp

MINIMAL_ARGS: dict[str, dict[str, Any]] = {
    "crp_explain": {"topic": "grounding"},
    "crp_spec_lookup": {"topic": "grounding"},
    "crp_compare": {"against": "MCP"},
    "crp_scaffold_integration": {"stack": "python-openai"},
    "crp_generate_config": {"intent_json": "{}"},
    "crp_generate_safety_policy": {"intent_json": "{}"},
    "crp_sdk_example": {},
    "crp_migrate_v3_v4": {},
    "crp_validate_config": {"yaml_text": 'version: "4.0"\n'},
    "crp_lint_headers": {"source_text": "CRP-Safety-Policy: strict"},
    "crp_conformance_check": {},
    "crp_safety_registry": {},
    "crp_capability_map": {},
    "crp_list_topics": {},
    "crp_safety_profile": {"profile": "balanced"},
    "crp_safety_set": {"intent_json": "{}"},
    "crp_safety_show": {},
    "crp_safety_explain": {"key": "grounding_verification"},
    "crp_safety_checkpoint": {},
    "crp_safety_checkpoint_when": {
        "condition": "risk >= HIGH",
        "context_json": '{"risk": "HIGH", "amount": 1500000}',
    },
    "crp_resolve_checkpoint": {
        "checkpoint_id": "cov-checkpoint-1",
        "decision": "approved",
        "reviewer": "tester",
    },
    "crp_envelope_preview": {"payload_json": "{}"},
    "crp_context_strategy": {"task": "write a user guide"},
    "crp_estimate_cost": {"payload_json": "{}"},
    "crp_continuation_plan": {"task": "generate a long report"},
    "crp_build_session": {},
    "crp_signup_link": {},
    "crp_upgrade_link": {"product": "gateway", "plan": "pro"},
    "crp_connect_repo_link": {},
    "crp_whoami": {},
    "crp_get_plan": {},
    "crp_gateway_status": {},
    "crp_create_api_key": {},
    "crp_test_call": {},
    "crp_deploy_endpoint": {"pipeline_id": "pipe-123"},
    "crp_benchmark": {},
    "crp_scan_repo": {"repo_ref": "owner/repo"},
    "crp_scan_status": {"scan_id": "123"},
    "crp_scan_report": {"scan_id": "123"},
    "crp_scan_local_preview": {"source_text": "openai.OpenAI()"},
    "crp_remediation_plan": {"finding_json": "[]"},
    "crp_comply_repo": {"repo_ref": "owner/repo"},
    "crp_comply_status": {"analysis_id": "123"},
    "crp_comply_diff": {"analysis_id": "123", "baseline_id": "456"},
    "crp_comply_policy": {},
    "crp_comply_link": {},
    "crp_list_specs": {},
    "crp_read_spec": {"spec_id": "CRP-SPEC-001"},
    "crp_list_schemas": {},
    "crp_list_profiles": {},
    "crp_list_stacks": {},
    "crp_recommend_capability": {"goal": "stop hallucinations"},
    "crp_build_integration_plan": {"goal": "govern calls"},
    "crp_validate_safety_policy": {"policy": "default-src 'self'; halt-on CRITICAL"},
    "crp_generate_scan_workflow": {"repo_ref": "owner/repo"},
    "crp_generate_gateway_compose": {},
    "crp_config_from_text": {"description": "block hallucinations and redact PII"},
    "crp_audit_project": {},
    "crp_quickstart": {},
}


RESOURCE_CASES: list[str] = [
    "crp://spec/CRP-SPEC-001",
    "crp://topic/index",
    "crp://schema/session-handle",
    "crp://template/config/balanced",
    "crp://template/policy/strict",
    "crp://example/ingest",
    "crp://registry/safety",
    "crp://registry/headers",
    "crp://.well-known/oauth-authorization-server",
    "crp://.well-known/oauth-resource-server",
]


PROMPT_CASES: dict[str, dict[str, Any]] = {
    "discover_crp": {},
    "integrate_crp": {"stack": "python-openai"},
    "write_safety_policy": {"goal": "balanced governance"},
    "context_strategy_for_task": {"task": "write a guide"},
    "audit_ai_calls": {"codebase_path": "./"},
    "debug_halt": {"halt_response": "451"},
    "migrate_v3_v4": {},
}


COMPLETION_CASES: list[tuple[Any, CompletionArgument]] = [
    (
        ResourceTemplateReference(uri="crp://spec/{spec_id}", type="ref/resource"),
        CompletionArgument(name="spec_id", value="001"),
    ),
    (
        ResourceTemplateReference(uri="crp://template/config/{profile}", type="ref/resource"),
        CompletionArgument(name="profile", value="bal"),
    ),
    (
        PromptReference(name="integrate_crp", type="ref/prompt"),
        CompletionArgument(name="stack", value="pyth"),
    ),
]


def _tool_text(result: Any) -> str:
    content, _meta = result
    return content[0].text


def _resource_text(result: Any) -> str:
    return result[0].content


@pytest.fixture(autouse=True)
def _clear_clerk_env() -> None:
    """Ensure hosted backend is not configured for coverage tests."""
    for key in ("CLERK_ISSUER", "CLERK_AUTHORIZED_PARTIES", "CLERK_SECRET_KEY"):
        os.environ.pop(key, None)

    # Seed a checkpoint so the resolve tool has a target during coverage runs.
    from crp_mcp import checkpoint_service

    checkpoint_service._checkpoints["cov-checkpoint-1"] = checkpoint_service.CheckpointRecord(
        checkpoint_id="cov-checkpoint-1",
        trigger="RISK_HIGH",
        message="coverage test checkpoint",
    )


@pytest.mark.asyncio
async def test_all_tools_listed() -> None:
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(MINIMAL_ARGS)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(MINIMAL_ARGS))
async def test_tool_runs(name: str) -> None:
    result = await mcp.call_tool(name, MINIMAL_ARGS[name])
    text = _tool_text(result)
    data = json.loads(text)
    assert data["ok"] is True, f"{name} failed: {text[:200]}"


@pytest.mark.asyncio
async def test_hitl_confirm_gate() -> None:
    """State-changing tools must ask for confirmation before acting."""
    os.environ["CRP_MCP_HOSTED_BYPASS_AUTH"] = "1"
    try:
        for name, args in (
            ("crp_create_api_key", {}),
            ("crp_test_call", {}),
            ("crp_deploy_endpoint", {"pipeline_id": "pipe-123"}),
            ("crp_benchmark", {}),
        ):
            result = await mcp.call_tool(name, args)
            data = json.loads(_tool_text(result))
            assert data["ok"] is True
            assert data.get("requires_confirmation") is True
    finally:
        os.environ.pop("CRP_MCP_HOSTED_BYPASS_AUTH", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("uri", RESOURCE_CASES)
async def test_resource_readable(uri: str) -> None:
    result = await mcp.read_resource(uri)
    text = _resource_text(result)
    assert text
    assert "Not found" not in text or "CRP-SPEC-001" in uri


@pytest.mark.asyncio
async def test_all_resources_listed() -> None:
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    uris = {str(r.uri) for r in resources}
    template_uris = {t.uriTemplate for t in templates}
    for case in RESOURCE_CASES:
        assert case in uris or any(case.startswith(t.split("{")[0]) for t in template_uris)


@pytest.mark.asyncio
@pytest.mark.parametrize("name,args", list(PROMPT_CASES.items()))
async def test_prompt_runs(name: str, args: dict[str, Any]) -> None:
    prompt = await mcp.get_prompt(name, args)
    assert prompt.messages


@pytest.mark.asyncio
async def test_all_prompts_listed() -> None:
    prompts = await mcp.list_prompts()
    names = {p.name for p in prompts}
    assert names == set(PROMPT_CASES)


@pytest.mark.asyncio
@pytest.mark.parametrize("ref,argument", COMPLETION_CASES)
async def test_completion_runs(ref: Any, argument: CompletionArgument) -> None:
    completion = await handle_completion(ref, argument, None)
    assert completion is not None
    assert completion.values
