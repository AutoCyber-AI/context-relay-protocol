# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP MCP server.

One package, two modes:
  * Local  (stdio): no secrets, no CRP network; knowledge + static validation.
  * Hosted (Streamable HTTP): account-linked actions with safe fallbacks when
    Clerk/Stripe backend env is not configured.

No ``eval``, ``exec``, or ``subprocess`` is used with user input.
"""

from __future__ import annotations

import functools
import inspect
import json
import os
from typing import Any

from crp_mcp import MODE_HOSTED, get_mode
from crp_mcp.agent_tools import (
    crp_audit_project,
    crp_build_integration_plan,
    crp_config_from_text,
    crp_generate_gateway_compose,
    crp_generate_scan_workflow,
    crp_list_profiles,
    crp_list_schemas,
    crp_list_specs,
    crp_list_stacks,
    crp_quickstart,
    crp_read_spec,
    crp_recommend_capability,
    crp_validate_safety_policy,
)
from crp_mcp.auth import ClerkTokenVerifier, hosted_available
from crp_mcp.completions import handle_completion
from crp_mcp.comply_tools import (
    ComplyDiffInput,
    ComplyPolicyInput,
    ComplyRepoInput,
    ComplyStatusInput,
    crp_comply_diff,
    crp_comply_link,
    crp_comply_policy,
    crp_comply_repo,
    crp_comply_status,
)
from crp_mcp.dpe_tools import (
    BuildSessionInput,
    ContextStrategyInput,
    ContinuationPlanInput,
    EnvelopePreviewInput,
    EstimateCostInput,
    crp_build_session,
    crp_context_strategy,
    crp_continuation_plan,
    crp_envelope_preview,
    crp_estimate_cost,
)
from crp_mcp.gateway_tools import (
    BenchmarkInput,
    CreateApiKeyInput,
    DeployInput,
    GetPlanInput,
    ProductPlanInput,
    TestCallInput,
    WhoamiInput,
    crp_benchmark,
    crp_connect_repo_link,
    crp_create_api_key,
    crp_deploy_endpoint,
    crp_gateway_status,
    crp_get_plan,
    crp_signup_link,
    crp_test_call,
    crp_upgrade_link,
    crp_whoami,
)
from crp_mcp.local_tools import (
    CapabilityMapInput,
    CompareInput,
    ConformanceInput,
    ExplainInput,
    GenerateConfigInput,
    GeneratePolicyInput,
    LintHeadersInput,
    ScaffoldInput,
    SdkExampleInput,
    SpecLookupInput,
    ValidateConfigInput,
    crp_capability_map,
    crp_compare,
    crp_conformance_check,
    crp_explain,
    crp_generate_config,
    crp_generate_safety_policy,
    crp_lint_headers,
    crp_list_topics,
    crp_migrate_v3_v4,
    crp_safety_registry,
    crp_scaffold_integration,
    crp_sdk_example,
    crp_spec_lookup,
    crp_validate_config,
)
from crp_mcp.permissions import ToolPermissionStore, resolve_identity
from crp_mcp.prompts import (
    audit_ai_calls,
    context_strategy_for_task,
    debug_halt,
    discover_crp,
    integrate_crp,
    write_safety_policy,
)
from crp_mcp.prompts import (
    migrate_v3_v4 as prompt_migrate_v3_v4,
)
from crp_mcp.resources import (
    get_config_template,
    get_example_resource,
    get_header_registry,
    get_oauth_authorization_server_metadata,
    get_oauth_resource_server_metadata,
    get_policy_template,
    get_safety_registry,
    get_schema_resource,
    get_spec_resource,
    get_topic_resource,
)
from crp_mcp.safety_tools import (
    SafetyCheckpointInput,
    SafetyCheckpointWhenInput,
    SafetyExplainInput,
    SafetyProfileInput,
    SafetyResolveCheckpointInput,
    SafetySetInput,
    crp_resolve_checkpoint,
    crp_safety_checkpoint,
    crp_safety_checkpoint_when,
    crp_safety_explain,
    crp_safety_profile,
    crp_safety_set,
    crp_safety_show,
)
from crp_mcp.scan_tools import (
    RemediationPlanInput,
    ScanLocalPreviewInput,
    ScanRepoInput,
    ScanReportInput,
    ScanStatusInput,
    crp_remediation_plan,
    crp_scan_local_preview,
    crp_scan_repo,
    crp_scan_report,
    crp_scan_status,
)
from crp_mcp.types import CRPToolResult, ResourceLink

try:
    from mcp.server.fastmcp import FastMCP
except Exception as _import_err:  # pragma: no cover - surfaced on server start
    raise ImportError(
        "The CRP MCP server requires the 'mcp' package. "
        "Install it with: pip install crprotocol[mcp]"
    ) from _import_err


MODE = get_mode()
HOSTED = MODE == MODE_HOSTED

_INSTRUCTIONS = (
    "You are the CRP (Context Relay Protocol) MCP assistant. Your job is to help "
    "the user build, configure, and operate CRPv4 integrations safely. "
    "Ground every claim in the authoritative CRP spec corpus. Never fabricate "
    "capabilities. For state-changing or spending actions, always require explicit "
    "human confirmation (confirm=true). Prefer the CRP SDK and Gateway base_url swap "
    "over hand-written headers."
)

# In hosted mode with Clerk configured, enable FastMCP's built-in Bearer auth
# middleware so the HTTP transport rejects unauthenticated requests before they
# reach tool handlers.
if HOSTED and hosted_available():
    try:
        from mcp.server.auth.settings import AuthSettings
    except Exception:  # pragma: no cover
        AuthSettings = None  # type: ignore[misc,assignment]

    if AuthSettings is not None:
        from crp_mcp.auth import public_origin

        mcp = FastMCP(
            "crp_mcp",
            instructions=_INSTRUCTIONS,
            website_url="https://crprotocol.io",
            auth=AuthSettings(
                issuer_url=os.environ["CLERK_ISSUER"],
                resource_server_url=public_origin(),
                required_scopes=None,
            ),
            token_verifier=ClerkTokenVerifier(),
        )
    else:
        mcp = FastMCP(
            "crp_mcp",
            instructions=_INSTRUCTIONS,
            website_url="https://crprotocol.io",
        )
else:
    mcp = FastMCP(
        "crp_mcp",
        instructions=_INSTRUCTIONS,
        website_url="https://crprotocol.io",
    )
mcp._mcp_server.version = "4.0.0"

def _permission_store() -> ToolPermissionStore:
    """Return a fresh permission store so env changes are honoured at call time."""
    return ToolPermissionStore(mode=MODE)


def _resource_links(tool_name: str, arguments: dict[str, Any]) -> list[ResourceLink]:
    """Return contextual MCP resource links for a tool result (MCP spec 2025-06-18)."""
    links: list[ResourceLink] = []

    def _add(uri: str, mime_type: str, title: str) -> None:
        links.append(ResourceLink(uri=uri, mimeType=mime_type, title=title))

    if tool_name == "crp_read_spec":
        spec_id = arguments.get("spec_id")
        if spec_id:
            _add(f"crp://spec/{spec_id}", "text/markdown", f"CRP spec {spec_id}")
    elif tool_name in {"crp_explain", "crp_spec_lookup"}:
        topic = arguments.get("topic", "")
        if topic:
            if str(topic).startswith("CRP-SPEC-"):
                _add(f"crp://spec/{topic}", "text/markdown", f"CRP spec {topic}")
            else:
                _add(f"crp://topic/{topic}", "text/markdown", f"CRP topic {topic}")
    elif tool_name == "crp_safety_profile":
        profile = arguments.get("profile")
        if profile:
            _add(f"crp://template/policy/{profile}", "text/plain", f"{profile} policy template")
            _add("crp://registry/safety", "application/json", "CRP Safety Registry")
    elif tool_name in {"crp_list_profiles", "crp_safety_show", "crp_safety_registry"}:
        _add("crp://registry/safety", "application/json", "CRP Safety Registry")
    elif tool_name == "crp_list_specs":
        _add("crp://spec/CRP-SPEC-001", "text/markdown", "Example CRP spec")
    elif tool_name in {"crp_generate_config", "crp_validate_config"}:
        _add("crp://template/config/balanced", "text/x-yaml", "Balanced config template")

    return links


def register_crp_tool(
    name: str,
    description: str,
    fn: Any,
    annotations: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Register a CRP tool with structured output, permission checks, and audit.

    The original tool function continues to return a JSON string so direct
    callers and tests are unaffected.  The wrapper returned to the MCP runtime
    produces a ``CRPToolResult`` model, giving clients an ``outputSchema`` and
    ``structuredContent`` while preserving the legacy text content.
    """
    if not name.startswith("crp_"):
        raise ValueError(f"CRP tool names must start with 'crp_': {name}")

    annotations = annotations or {}
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs_call: Any) -> CRPToolResult:
        bound = sig.bind(*args, **kwargs_call)
        bound.apply_defaults()

        # 1. Input validation (OWASP MCP05).
        try:
            store = _permission_store()
            store.validate_inputs(bound.arguments)
        except ValueError as exc:
            return CRPToolResult(ok=False, error=f"input_validation_failed: {exc}")

        # 2. Resolve identity and role.
        ctx = bound.arguments.get("ctx") or bound.arguments.get("context")
        identity = resolve_identity(ctx)
        store = _permission_store()
        role = identity.org_role or store.current_role()
        user_id = identity.user_id or "local"
        org_id = identity.org_id

        # 3. Authorisation (OWASP MCP02 / MCP07).
        allowed = store.is_allowed(name, annotations)
        if not allowed:
            result = CRPToolResult(
                ok=False,
                error=(
                    f"permission_denied: role={role} is not allowed to call {name}. "
                    "Contact your CRP organisation admin to enable this tool."
                ),
            )
            store.audit(
                tool=name,
                role=role,
                user_id=user_id,
                org_id=org_id,
                allowed=False,
                args=bound.arguments,
                outcome="denied",
                error=result.error,
            )
            return result

        # 4. Execute and normalise to CRPToolResult.
        try:
            raw = await fn(*args, **kwargs_call)
            if isinstance(raw, str):
                data = json.loads(raw)
            elif isinstance(raw, CRPToolResult):
                data = raw.model_dump()
            elif isinstance(raw, dict):
                data = raw
            else:
                data = {"value": raw}
            result = CRPToolResult.model_validate(data)
        except Exception as exc:
            result = CRPToolResult(ok=False, error=f"tool_execution_failed: {exc}")

        # 5. Attach resource links when a relevant resource exists (MCP spec).
        links = _resource_links(name, bound.arguments)
        if links:
            if result.resource_links is None:
                result.resource_links = []
            result.resource_links.extend(links)

        # 6. Audit telemetry (OWASP MCP08).
        store.audit(
            tool=name,
            role=role,
            user_id=user_id,
            org_id=org_id,
            allowed=True,
            args=bound.arguments,
            outcome="success" if result.ok else "error",
            error=result.error,
        )
        return result

    # Preserve the original signature for FastMCP parameter discovery, but
    # advertise the structured output model.
    wrapper.__signature__ = sig.replace(  # type: ignore[attr-defined]
        parameters=params,
        return_annotation=CRPToolResult,
    )

    return mcp.tool(name=name, description=description, annotations=annotations, **kwargs)(wrapper)

__all__ = [
    # Server instance
    "mcp",
    # Local tool inputs
    "ExplainInput",
    "SpecLookupInput",
    "CompareInput",
    "ScaffoldInput",
    "GenerateConfigInput",
    "GeneratePolicyInput",
    "SdkExampleInput",
    "ValidateConfigInput",
    "LintHeadersInput",
    "ConformanceInput",
    "CapabilityMapInput",
    # Safety tool inputs
    "SafetyProfileInput",
    "SafetySetInput",
    "SafetyExplainInput",
    "SafetyCheckpointInput",
    "SafetyCheckpointWhenInput",
    "SafetyResolveCheckpointInput",
    # DPE tool inputs
    "EnvelopePreviewInput",
    "ContextStrategyInput",
    "EstimateCostInput",
    "ContinuationPlanInput",
    "BuildSessionInput",
    # Hosted tool inputs
    "WhoamiInput",
    "GetPlanInput",
    "ProductPlanInput",
    "CreateApiKeyInput",
    "TestCallInput",
    "DeployInput",
    "BenchmarkInput",
    # Scan inputs
    "ScanRepoInput",
    "ScanStatusInput",
    "ScanReportInput",
    "ScanLocalPreviewInput",
    "RemediationPlanInput",
    # Comply inputs
    "ComplyRepoInput",
    "ComplyStatusInput",
    "ComplyDiffInput",
    "ComplyPolicyInput",
]


# ---------------------------------------------------------------------------
# Tool registration — local / knowledge
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_explain",
    description="Explain a CRPv4 concept with citations from the authoritative spec corpus.",
    annotations={"title": "Explain a CRP concept", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_explain,
)

register_crp_tool(
    name="crp_spec_lookup",
    description="Retrieve authoritative CRP spec excerpts with citations.",
    annotations={"title": "Look up CRP spec text", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_spec_lookup,
)

register_crp_tool(
    name="crp_compare",
    description="Compare CRP to MCP, A2A, AIPREF, RAG, or vector-DB.",
    annotations={"title": "Compare CRP to another technology", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_compare,
)

register_crp_tool(
    name="crp_scaffold_integration",
    description="Generate copy-paste integration code for a supported stack.",
    annotations={"title": "Scaffold a CRP integration", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_scaffold_integration,
)

register_crp_tool(
    name="crp_generate_config",
    description="Turn plain-language governance intent into a valid crp.config.yaml fragment.",
    annotations={"title": "Generate crp.config.yaml", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_generate_config,
)

register_crp_tool(
    name="crp_generate_safety_policy",
    description="Turn plain-language safety intent into a CRP-Safety-Policy directive string.",
    annotations={"title": "Generate a CRP Safety-Policy directive", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_generate_safety_policy,
)

register_crp_tool(
    name="crp_sdk_example",
    description="Return a copy-paste CRP SDK snippet for a common task.",
    annotations={"title": "Get a copy-paste SDK example", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_sdk_example,
)

register_crp_tool(
    name="crp_migrate_v3_v4",
    description="Return high-level CRP v3 to v4 migration guidance.",
    annotations={"title": "v3 to v4 migration guidance", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_migrate_v3_v4,
)

register_crp_tool(
    name="crp_validate_config",
    description="Validate a crp.config.yaml document against the CRP v4 schema.",
    annotations={"title": "Validate a CRP config", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_validate_config,
)

register_crp_tool(
    name="crp_lint_headers",
    description="Check CRP-* header usage for correctness and anti-patterns.",
    annotations={"title": "Lint CRP header usage", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_lint_headers,
)

register_crp_tool(
    name="crp_conformance_check",
    description="Run the CRP conformance vectors locally and return a summary.",
    annotations={"title": "Run CRP conformance vectors", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_conformance_check,
)

register_crp_tool(
    name="crp_safety_registry",
    description="Return the CRP Safety Control Plane registry.",
    annotations={"title": "List CRP Safety Control Plane capabilities", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_registry,
)

register_crp_tool(
    name="crp_capability_map",
    description="List every CRPv4 capability and the specs/SDKs needed to implement it.",
    annotations={"title": "CRPv4 capability map", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_capability_map,
)

register_crp_tool(
    name="crp_list_topics",
    description="List available CRP topic pages.",
    annotations={"title": "List CRP topics", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_list_topics,
)


# ---------------------------------------------------------------------------
# Tool registration — agent-centric builders
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_list_specs",
    description="List every authoritative CRP specification with its title.",
    annotations={"title": "List CRP specs", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_list_specs,
)

register_crp_tool(
    name="crp_read_spec",
    description="Read the full authoritative text of a CRP specification.",
    annotations={"title": "Read a CRP spec", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_read_spec,
)

register_crp_tool(
    name="crp_list_schemas",
    description="List the CRP JSON schemas available as resources.",
    annotations={"title": "List CRP JSON schemas", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_list_schemas,
)

register_crp_tool(
    name="crp_list_profiles",
    description="List the built-in CRP safety profiles.",
    annotations={"title": "List safety profiles", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_list_profiles,
)

register_crp_tool(
    name="crp_list_stacks",
    description="List the integration stacks supported by the scaffold tool.",
    annotations={"title": "List supported stacks", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_list_stacks,
)

register_crp_tool(
    name="crp_recommend_capability",
    description="Recommend CRPv4 capabilities and specs for a stated goal.",
    annotations={"title": "Recommend CRP capabilities", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_recommend_capability,
)

register_crp_tool(
    name="crp_build_integration_plan",
    description="Produce a step-by-step CRP integration plan with config and code.",
    annotations={"title": "Build CRP integration plan", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_build_integration_plan,
)

register_crp_tool(
    name="crp_validate_safety_policy",
    description="Parse a CRP-Safety-Policy string and report issues.",
    annotations={"title": "Validate safety policy", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_validate_safety_policy,
)

register_crp_tool(
    name="crp_generate_scan_workflow",
    description="Return a GitHub Actions workflow YAML for CRP Scan.",
    annotations={"title": "Generate scan workflow", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_generate_scan_workflow,
)

register_crp_tool(
    name="crp_generate_gateway_compose",
    description="Return a docker-compose snippet for self-hosting the CRP Gateway.",
    annotations={"title": "Generate gateway compose", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_generate_gateway_compose,
)

register_crp_tool(
    name="crp_config_from_text",
    description="Generate crp.config.yaml and safety policy from plain English.",
    annotations={"title": "Config from plain text", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_config_from_text,
)

register_crp_tool(
    name="crp_audit_project",
    description="Audit a project for CRP readiness and return a remediation checklist.",
    annotations={"title": "Audit project for CRP readiness", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_audit_project,
)

register_crp_tool(
    name="crp_quickstart",
    description="Return a concise getting-started guide for CRPv4.",
    annotations={"title": "CRPv4 quickstart", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_quickstart,
)


# ---------------------------------------------------------------------------
# Tool registration — safety Control Plane
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_safety_profile",
    description="Return the policy directive and config fragment for a named safety profile.",
    annotations={"title": "Get a safety profile", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_profile,
)

register_crp_tool(
    name="crp_safety_set",
    description="Translate safety settings into a CRP-Safety-Policy directive string.",
    annotations={"title": "Set safety settings", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_set,
)

register_crp_tool(
    name="crp_safety_show",
    description="Show the default CRP Safety Control Plane capabilities and coverage map.",
    annotations={"title": "Show safety capabilities", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_show,
)

register_crp_tool(
    name="crp_safety_explain",
    description="Explain a single CRP Safety Control Plane capability by key.",
    annotations={"title": "Explain a safety capability", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_explain,
)

register_crp_tool(
    name="crp_safety_checkpoint",
    description="Preview or create a human-in-the-loop safety checkpoint.",
    annotations={"title": "Safety checkpoint", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    fn=crp_safety_checkpoint,
)

register_crp_tool(
    name="crp_safety_checkpoint_when",
    description="Evaluate a checkpoint policy condition and resolve the review channel.",
    annotations={"title": "Evaluate checkpoint policy", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_safety_checkpoint_when,
)

register_crp_tool(
    name="crp_resolve_checkpoint",
    description="Resolve a pending checkpoint with approved/rejected (supports multi-approver).",
    annotations={"title": "Resolve checkpoint", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    fn=crp_resolve_checkpoint,
)


# ---------------------------------------------------------------------------
# Tool registration — Data Plane Extension
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_envelope_preview",
    description="Preview the CRP context envelope that would be built for a payload.",
    annotations={"title": "Preview CRP context envelope", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_envelope_preview,
)

register_crp_tool(
    name="crp_context_strategy",
    description="Recommend CRP context settings for a task.",
    annotations={"title": "Recommend context strategy", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_context_strategy,
)

register_crp_tool(
    name="crp_estimate_cost",
    description="Return a rough cost/token estimate for a governed call.",
    annotations={"title": "Estimate CRP call cost", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_estimate_cost,
)

register_crp_tool(
    name="crp_continuation_plan",
    description="Produce a continuation plan for long-generation tasks.",
    annotations={"title": "Plan continuation", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_continuation_plan,
)

register_crp_tool(
    name="crp_build_session",
    description="Create a local session handle for multi-turn conversation.",
    annotations={"title": "Build CRP session handle", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_build_session,
)


# ---------------------------------------------------------------------------
# Tool registration — hosted/onboarding
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_signup_link",
    description="Return a signup URL for the human to open in their browser.",
    annotations={"title": "Get CRP signup link", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    fn=crp_signup_link,
)

register_crp_tool(
    name="crp_upgrade_link",
    description="Return the Stripe Checkout URL for the chosen plan.",
    annotations={"title": "Get Stripe checkout link", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    fn=crp_upgrade_link,
)

register_crp_tool(
    name="crp_connect_repo_link",
    description="Return the GitHub App install URL.",
    annotations={"title": "Get GitHub App install link", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    fn=crp_connect_repo_link,
)

register_crp_tool(
    name="crp_whoami",
    description="Report the signed-in user's identity and plan metadata.",
    annotations={"title": "Who is signed in", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_whoami,
)

register_crp_tool(
    name="crp_get_plan",
    description="Return current Gateway/Comply/Scan plan and quota.",
    annotations={"title": "Get current plan and quota", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_get_plan,
)

register_crp_tool(
    name="crp_gateway_status",
    description="Report whether the hosted CRP Gateway backend is configured.",
    annotations={"title": "Gateway backend status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_gateway_status,
)


# ---------------------------------------------------------------------------
# Tool registration — hosted/state-changing (HITL via confirm=true)
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_create_api_key",
    description="Mint a scoped, revocable Gateway API key. Requires auth + human confirmation.",
    annotations={"title": "Create Gateway API key", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    fn=crp_create_api_key,
)

register_crp_tool(
    name="crp_test_call",
    description="Run one real governed call. Metered against the user's plan.",
    annotations={"title": "Run one governed call", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    fn=crp_test_call,
)

register_crp_tool(
    name="crp_deploy_endpoint",
    description="Deploy a built pipeline as a live production endpoint.",
    annotations={"title": "Deploy pipeline endpoint", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True},
    fn=crp_deploy_endpoint,
)

register_crp_tool(
    name="crp_benchmark",
    description="Run an SQB-style quality benchmark. Metered against the user's plan.",
    annotations={"title": "Run SQB benchmark", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    fn=crp_benchmark,
)


# ---------------------------------------------------------------------------
# Tool registration — scan
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_scan_repo",
    description="Queue or preview a CRP Scan for ungoverned AI calls.",
    annotations={"title": "Scan repository", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    fn=crp_scan_repo,
)

register_crp_tool(
    name="crp_scan_status",
    description="Return the status of a CRP Scan job.",
    annotations={"title": "Scan job status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_scan_status,
)

register_crp_tool(
    name="crp_scan_report",
    description="Return the findings of a CRP Scan job.",
    annotations={"title": "Scan report", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_scan_report,
)

register_crp_tool(
    name="crp_scan_local_preview",
    description="Scan a source snippet locally for ungoverned AI calls.",
    annotations={"title": "Local scan preview", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_scan_local_preview,
)

register_crp_tool(
    name="crp_remediation_plan",
    description="Generate a remediation plan from CRP Scan findings.",
    annotations={"title": "Remediation plan", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_remediation_plan,
)


# ---------------------------------------------------------------------------
# Tool registration — comply
# ---------------------------------------------------------------------------
register_crp_tool(
    name="crp_comply_repo",
    description="Run or preview a CRP Comply analysis for a repository.",
    annotations={"title": "Comply repository analysis", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    fn=crp_comply_repo,
)

register_crp_tool(
    name="crp_comply_status",
    description="Return the status of a CRP Comply analysis.",
    annotations={"title": "Comply analysis status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_comply_status,
)

register_crp_tool(
    name="crp_comply_diff",
    description="Compare two CRP Comply analysis reports.",
    annotations={"title": "Comply diff", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_comply_diff,
)

register_crp_tool(
    name="crp_comply_policy",
    description="Return the CRP control-to-framework mapping for a compliance standard.",
    annotations={"title": "Comply policy mapping", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    fn=crp_comply_policy,
)

register_crp_tool(
    name="crp_comply_link",
    description="Return the CRP Comply web app link.",
    annotations={"title": "Open CRP Comply", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    fn=crp_comply_link,
)


# ---------------------------------------------------------------------------
# Resource registration
# ---------------------------------------------------------------------------
mcp.resource(
    uri="crp://spec/{spec_id}",
    name="CRP spec",
    description="Full authoritative text of a CRP specification.",
    mime_type="text/markdown",
)(get_spec_resource)

mcp.resource(
    uri="crp://topic/{topic}",
    name="CRP topic",
    description="Full text of a CRP topic page.",
    mime_type="text/markdown",
)(get_topic_resource)

mcp.resource(
    uri="crp://schema/{schema_name}",
    name="CRP JSON schema",
    description="A CRP JSON schema from the schemas/ directory.",
    mime_type="application/json",
)(get_schema_resource)

mcp.resource(
    uri="crp://template/config/{profile}",
    name="CRP config template",
    description="Ready-to-use crp.config.yaml fragment for a safety profile.",
    mime_type="text/x-yaml",
)(get_config_template)

mcp.resource(
    uri="crp://template/policy/{profile}",
    name="CRP safety policy template",
    description="CRP-Safety-Policy directive string for a safety profile.",
    mime_type="text/plain",
)(get_policy_template)

mcp.resource(
    uri="crp://example/{task}",
    name="CRP SDK example",
    description="Copy-paste SDK snippet for a common task.",
    mime_type="text/plain",
)(get_example_resource)

mcp.resource(
    uri="crp://registry/safety",
    name="CRP Safety Registry",
    description="JSON safety capability registry.",
    mime_type="application/json",
)(get_safety_registry)

mcp.resource(
    uri="crp://registry/headers",
    name="CRP Header Registry",
    description="JSON catalog of CRP-* headers.",
    mime_type="application/json",
)(get_header_registry)

mcp.resource(
    uri="crp://.well-known/oauth-authorization-server",
    name="OAuth Authorization Server Metadata",
    description="OAuth 2.0 authorization server metadata for CRP hosted services.",
    mime_type="application/json",
)(get_oauth_authorization_server_metadata)

mcp.resource(
    uri="crp://.well-known/oauth-resource-server",
    name="OAuth Resource Server Metadata",
    description="RFC 8707 resource server metadata for CRP hosted services.",
    mime_type="application/json",
)(get_oauth_resource_server_metadata)


# ---------------------------------------------------------------------------
# Prompt registration
# ---------------------------------------------------------------------------
mcp.prompt(name="discover_crp", description="Introduce CRP and the simplest integration.")(discover_crp)
mcp.prompt(name="integrate_crp", description="Walk through adding CRP to a stack.")(integrate_crp)
mcp.prompt(name="write_safety_policy", description="Write a CRP-Safety-Policy directive.")(write_safety_policy)
mcp.prompt(name="context_strategy_for_task", description="Recommend CRP context settings for a task.")(context_strategy_for_task)
mcp.prompt(name="audit_ai_calls", description="Audit a codebase for ungoverned AI calls.")(audit_ai_calls)
mcp.prompt(name="debug_halt", description="Explain a CRP 451 halt response.")(debug_halt)
mcp.prompt(name="migrate_v3_v4", description="CRP v3 to v4 migration checklist.")(prompt_migrate_v3_v4)


# ---------------------------------------------------------------------------
# Completion registration
# ---------------------------------------------------------------------------
mcp.completion()(handle_completion)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if HOSTED:
        port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="streamable_http", port=port)
    else:
        # stdio: all logging must go to stderr; stdout is the MCP transport.
        mcp.run()


if __name__ == "__main__":
    main()
