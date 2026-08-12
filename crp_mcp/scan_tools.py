# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Scan MCP tools — find ungoverned AI calls and generate remediation plans."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from pydantic import Field

from crp_mcp.auth import (
    AuthenticationError,
    HostedNotConfigured,
    authenticate,
    hosted_available,
)
from crp_mcp.backend_client import BackendError, BackendNotConfigured, ScanClient
from crp_mcp.types import err, not_configured, ok

try:
    from mcp.server.fastmcp import Context
except Exception:  # pragma: no cover
    Context = Any  # type: ignore[misc,assignment]


class ScanRepoInput:
    repo_ref: str
    branch: str
    confirm: bool


class ScanStatusInput:
    scan_id: str


class ScanReportInput:
    scan_id: str


class ScanLocalPreviewInput:
    source_text: str


class RemediationPlanInput:
    finding_json: str


# Patterns used for local static scans (no code execution).
_AI_CALL_PATTERNS: list[dict[str, Any]] = [
    {"name": "OpenAI client", "pattern": re.compile(r"OpenAI\(|openai\.ChatCompletion"), "severity": "medium"},
    {"name": "Anthropic client", "pattern": re.compile(r"anthropic\.Anthropic\(|Messages\("), "severity": "medium"},
    {"name": "LangChain LLM", "pattern": re.compile(r"ChatOpenAI|ChatAnthropic|LLMChain"), "severity": "medium"},
    {"name": "raw requests to LLM", "pattern": re.compile(r"requests\.(post|get).*api\.openai|api\.anthropic"), "severity": "high"},
    {"name": "CRP governed", "pattern": re.compile(r"gateway\.crprotocol\.io|crp\.SDKClient"), "severity": "governed"},
]


async def crp_scan_repo(
    ctx: Context,
    repo_ref: Annotated[
        str,
        Field(description="GitHub repo 'owner/repo' or local path to scan.", min_length=1, max_length=200),
    ],
    branch: Annotated[
        str,
        Field(default="main", description="Branch to scan when repo_ref is a GitHub repo.", max_length=100),
    ] = "main",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Queue or preview a CRP Scan for ungoverned AI calls.

    In hosted mode this triggers a real scan; locally it returns a preview and
    requires explicit confirmation.
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
                "message": f"Scan '{repo_ref}' for ungoverned AI calls? This may read the repository contents. Re-call with confirm=true to proceed.",
                "configured": configured,
            }
        )

    if not configured:
        return ok(
            not_configured("scan_repo").copy()
            | {
                "action": "preview_only",
                "repo_ref": repo_ref,
                "branch": branch,
                "suggestion": "Use the CRP Scan GitHub Action for local scans: https://crprotocol.io/scan-action",
            }
        )

    client = ScanClient()
    try:
        result = await client.create_scan(repo_ref, branch)
        return ok(
            {
                "live": True,
                "scan_id": result.get("scan_id", result.get("id")),
                "repo_ref": repo_ref,
                "branch": branch,
                "status": result.get("status", "queued"),
            }
        )
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "scan_id": f"scan-{abs(hash(repo_ref)) % 10**8:08d}",
                "repo_ref": repo_ref,
                "branch": branch,
                "status": "queued",
                "message": "Scan backend unavailable; returning stub identifier.",
            }
        )


async def crp_scan_status(
    ctx: Context,
    scan_id: Annotated[
        str,
        Field(description="Scan identifier returned by crp_scan_repo.", min_length=1, max_length=100),
    ],
) -> str:
    """Return the status of a CRP Scan job."""
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("scan_status"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    client = ScanClient()
    try:
        result = await client.get_scan(scan_id)
        return ok({"live": True, **result})
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "scan_id": scan_id,
                "status": "STUB: not available without scan backend.",
                "findings_count": 0,
                "report_url": None,
            }
        )


async def crp_scan_report(
    ctx: Context,
    scan_id: Annotated[
        str,
        Field(description="Scan identifier returned by crp_scan_repo.", min_length=1, max_length=100),
    ],
) -> str:
    """Return the findings of a CRP Scan job."""
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("scan_report"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    client = ScanClient()
    try:
        result = await client.get_scan(scan_id)
        return ok(
            {
                "live": True,
                "scan_id": scan_id,
                "findings": result.get("findings", []),
            }
        )
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "scan_id": scan_id,
                "findings": [],
                "message": "STUB: no report without scan backend.",
            }
        )


async def crp_scan_local_preview(
    source_text: Annotated[
        str,
        Field(description="Source code snippet to scan locally for ungoverned AI calls.", min_length=1, max_length=50000),
    ],
) -> str:
    """Scan a snippet of source code locally for ungoverned AI calls."""
    findings: list[dict[str, Any]] = []
    already_governed = any(
        p["pattern"].search(source_text)
        for p in _AI_CALL_PATTERNS
        if p["severity"] == "governed"
    )
    for item in _AI_CALL_PATTERNS:
        if item["severity"] == "governed":
            continue
        for m in item["pattern"].finditer(source_text):
            findings.append(
                {
                    "pattern": item["name"],
                    "severity": item["severity"],
                    "start": m.start(),
                    "end": m.end(),
                    "matched": m.group(0),
                    "governed": already_governed,
                }
            )
    remediation = _build_remediation(findings, already_governed)
    return ok(
        {
            "findings": findings,
            "already_governed": already_governed,
            "remediation": remediation,
        }
    )


def _build_remediation(findings: list[dict[str, Any]], governed: bool) -> list[str]:
    if not findings:
        return ["No ungoverned AI-call patterns detected in the snippet."]
    steps = [
        "1. Replace raw LLM client initialisation with a CRP SDK client or base_url swap.",
        "2. Set a CRP safety profile via client.safety.set_profile('balanced').",
        "3. Run crp_scan_repo on the full repository for a complete report.",
    ]
    if governed:
        steps.append("4. The snippet already contains CRP governance markers — verify headers/policy are active.")
    return steps


async def crp_remediation_plan(
    finding_json: Annotated[
        str,
        Field(description='JSON array of findings from crp_scan_local_preview or crp_scan_report.', min_length=1, max_length=20000),
    ],
) -> str:
    """Generate a remediation plan from CRP Scan findings."""
    try:
        findings = json.loads(finding_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON findings: {exc}")
    if not isinstance(findings, list):
        return err("finding_json must be a JSON array.")
    plan: list[dict[str, Any]] = []
    for f in findings:
        plan.append(
            {
                "pattern": f.get("pattern", "unknown"),
                "action": "Replace with CRP Gateway base_url or SDK client.",
                "code": "client = OpenAI(base_url='https://gateway.crprotocol.io/v1', api_key=os.environ['CRP_API_KEY'])",
                "verification": "Run crp_scan_local_preview after editing.",
            }
        )
    return ok({"plan": plan, "count": len(plan)})
