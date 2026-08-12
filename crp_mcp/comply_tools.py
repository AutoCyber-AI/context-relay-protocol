# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Comply MCP tools — compliance-as-code, policy diff, and repo attestation.

The live CRP Comply service is a separate deployed project.  These tools provide
safe local previews and defer to the human to open the hosted service in a browser
when the backend is not configured.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from crp_mcp.auth import (
    AuthenticationError,
    HostedNotConfigured,
    authenticate,
    hosted_available,
)
from crp_mcp.backend_client import BackendError, BackendNotConfigured, ComplyClient
from crp_mcp.types import err, not_configured, ok

try:
    from mcp.server.fastmcp import Context
except Exception:  # pragma: no cover
    Context = Any  # type: ignore[misc,assignment]


class ComplyRepoInput:
    repo_ref: str
    framework: str
    confirm: bool


class ComplyStatusInput:
    analysis_id: str


class ComplyDiffInput:
    analysis_id: str
    baseline_id: str


class ComplyPolicyInput:
    framework: str


async def crp_comply_repo(
    ctx: Context,
    repo_ref: Annotated[
        str,
        Field(description="GitHub repo 'owner/repo' or local path to analyse.", min_length=1, max_length=200),
    ],
    framework: Annotated[
        str,
        Field(default="EU AI Act", description="Compliance framework: EU AI Act, ISO 42001, GDPR, NIST RMF.", max_length=60),
    ] = "EU AI Act",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Run or preview a CRP Comply analysis for a repository.

    This reads code and config to map AI calls to compliance controls. In hosted
    mode it queues a real analysis; locally it returns a preview.
    """
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        configured = False
    except AuthenticationError:
        configured = hosted_available()
    else:
        configured = hosted_available()

    if not confirm:
        return ok(
            {
                "requires_confirmation": True,
                "message": f"Run CRP Comply analysis on '{repo_ref}' for {framework}? This reads repository contents. Re-call with confirm=true to proceed.",
                "configured": configured,
            }
        )

    if not configured:
        return ok(
            not_configured("comply_repo").copy()
            | {
                "action": "preview_only",
                "repo_ref": repo_ref,
                "framework": framework,
                "suggestion": "Open the CRP Comply app: https://crprotocol.io/comply",
            }
        )

    client = ComplyClient()
    try:
        result = await client.create_analysis(repo_ref, framework)
        return ok(
            {
                "live": True,
                "analysis_id": result.get("analysis_id", result.get("id")),
                "repo_ref": repo_ref,
                "framework": framework,
                "status": result.get("status", "queued"),
            }
        )
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "analysis_id": f"comply-{abs(hash(repo_ref + framework)) % 10**8:08d}",
                "repo_ref": repo_ref,
                "framework": framework,
                "status": "queued",
                "message": "Comply backend unavailable; returning stub identifier.",
            }
        )


async def crp_comply_status(
    ctx: Context,
    analysis_id: Annotated[
        str,
        Field(description="Analysis identifier returned by crp_comply_repo.", min_length=1, max_length=100),
    ],
) -> str:
    """Return the status of a CRP Comply analysis."""
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("comply_status"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    client = ComplyClient()
    try:
        result = await client.get_analysis(analysis_id)
        return ok({"live": True, **result})
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "analysis_id": analysis_id,
                "status": "STUB: not available without comply backend.",
                "findings_count": 0,
                "report_url": None,
            }
        )


async def crp_comply_diff(
    ctx: Context,
    analysis_id: Annotated[
        str,
        Field(description="Analysis identifier to diff.", min_length=1, max_length=100),
    ],
    baseline_id: Annotated[
        str,
        Field(description="Baseline analysis identifier to compare against.", min_length=1, max_length=100),
    ],
) -> str:
    """Compare two CRP Comply analysis reports."""
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("comply_diff"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    client = ComplyClient()
    try:
        result = await client.diff_analysis(analysis_id, baseline_id)
        return ok({"live": True, **result})
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "analysis_id": analysis_id,
                "baseline_id": baseline_id,
                "new_findings": [],
                "resolved_findings": [],
                "message": "STUB: diff requires comply backend.",
            }
        )


async def crp_comply_policy(
    framework: Annotated[
        str,
        Field(default="EU AI Act", description="Compliance framework to map.", max_length=60),
    ] = "EU AI Act",
) -> str:
    """Return the CRP control-to-framework mapping for a compliance standard."""
    mappings: dict[str, list[dict[str, str]]] = {
        "EU AI Act": [
            {"control": "grounding_verification", "article": "Article 10 (Data governance)", "evidence": "answer.crp.grounded"},
            {"control": "human_oversight", "article": "Article 14", "evidence": "client.safety.checkpoint(...)"},
            {"control": "tamper_evident_audit", "article": "Article 12 (Record-keeping)", "evidence": "client.audit.export(...)"},
            {"control": "risk_scoring", "article": "Article 9 (Risk management)", "evidence": "answer.crp.risk"},
        ],
        "ISO 42001": [
            {"control": "risk_assessment", "clause": "6.1", "evidence": "answer.crp.risk + safety budget"},
            {"control": "human_oversight", "clause": "A.7", "evidence": "client.safety.checkpoint(...)"},
            {"control": "audit", "clause": "A.8", "evidence": "client.audit.export(...)"},
        ],
        "GDPR": [
            {"control": "pii_detection", "article": "Article 5", "evidence": "block-pii directive"},
            {"control": "audit", "article": "Article 30 (Records)", "evidence": "client.audit.export(...)"},
        ],
        "NIST RMF": [
            {"control": "risk_scoring", "function": "Govern", "evidence": "answer.crp.risk"},
            {"control": "human_oversight", "function": "Govern", "evidence": "client.safety.checkpoint(...)"},
        ],
    }
    key = framework.strip()
    if key not in mappings:
        return err(
            f"Framework '{framework}' not in built-in catalogue. "
            f"Try one of: {', '.join(mappings)}."
        )
    return ok({"framework": key, "mappings": mappings[key]})


async def crp_comply_link() -> str:
    """Return the CRP Comply web app link."""
    return ok(
        {
            "action": "open_in_browser",
            "url": "https://crprotocol.io/comply",
            "message": "Open CRP Comply in your browser to run compliance analysis on a connected repository.",
        }
    )
