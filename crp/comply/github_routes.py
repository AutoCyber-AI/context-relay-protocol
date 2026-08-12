# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""GitHub + Scan route handlers (SPEC-048).

Returns dicts for framework integration (FastAPI, Flask, etc.).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from crp.comply.signup import claim_results, is_public_repo, store_anonymous_results
from crp.scan.github_app import GithubAppClient

logger = logging.getLogger(__name__)

_GITHUB_APP_PUBLIC_LINK = "https://github.com/apps/crp-comply"


# ---------------------------------------------------------------------------
# GitHub App OAuth / Webhook routes
# ---------------------------------------------------------------------------


def github_callback(query_params: dict[str, str]) -> dict[str, Any]:
    """GET /api/github/callback — OAuth callback after App installation.

    Query params: ``installation_id``, ``setup_action`` (install|update).
    Maps installation_id to Clerk org/tenant.
    """
    installation_id = query_params.get("installation_id")
    setup_action = query_params.get("setup_action", "install")
    if not installation_id:
        return {"error": "Missing installation_id", "status": 400}

    # In a real app, map installation_id to the Clerk org from the session
    # For now, return the installation ID for the frontend to complete linking
    return {
        "status": "ok",
        "installation_id": installation_id,
        "setup_action": setup_action,
        "message": "Link this installation to your Clerk org in Settings",
    }


def github_installed(query_params: dict[str, str]) -> dict[str, Any]:
    """GET /api/github/installed — post-install landing page."""
    installation_id = query_params.get("installation_id")
    return {
        "status": "ok",
        "installation_id": installation_id,
        "message": "GitHub App installed. Return to Comply to select repositories.",
    }


def github_connect() -> dict[str, Any]:
    """GET /api/github/connect — redirect to GitHub App install."""
    return {
        "status": "redirect",
        "url": _GITHUB_APP_PUBLIC_LINK + "/installations/new",
    }


def github_webhook(body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    """POST /api/github/webhook — receive GitHub App events.

    Verifies HMAC-SHA256 signature before processing.
    """
    sig_header = headers.get("X-Hub-Signature-256", "")
    event_type = headers.get("X-GitHub-Event", "")
    webhook_secret = os.environ.get("GITHUB_APP_WEBHOOK_SECRET", "")

    if not webhook_secret:
        return {"error": "Webhook secret not configured", "status": 500}

    if not GithubAppClient.verify_webhook(body, sig_header, webhook_secret):
        logger.warning("GitHub webhook signature verification failed")
        return {"error": "Invalid signature", "status": 400}

    payload = json.loads(body)

    if event_type == "push":
        repo = payload.get("repository", {})
        logger.info("Push event on %s/%s — trigger scan", repo.get("owner", {}).get("login"), repo.get("name"))
        # TODO: enqueue scan job
        return {"status": "ok", "action": "scan_enqueued"}

    if event_type == "installation":
        action = payload.get("action")
        installation = payload.get("installation", {})
        logger.info("Installation %s: id=%s", action, installation.get("id"))
        return {"status": "ok", "action": action}

    if event_type == "installation_repositories":
        action = payload.get("action")
        repos_added = [r["full_name"] for r in payload.get("repositories_added", [])]
        repos_removed = [r["full_name"] for r in payload.get("repositories_removed", [])]
        logger.info("Repos changed: +%d -%d", len(repos_added), len(repos_removed))
        return {"status": "ok", "added": repos_added, "removed": repos_removed}

    if event_type == "installation" and payload.get("action") == "deleted":
        installation_id = payload.get("installation", {}).get("id")
        logger.info("Installation %s deleted — cleanup", installation_id)
        return {"status": "ok", "action": "cleanup"}

    logger.debug("Unhandled GitHub event: %s", event_type)
    return {"status": "ok", "event": event_type}


# ---------------------------------------------------------------------------
# Scan routes
# ---------------------------------------------------------------------------


def scan_anonymous(body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/scan/anonymous — store findings for pre-auth users."""
    findings = body.get("findings", [])
    repo_url = body.get("repo_url", "")

    # Security boundary: private repos require auth
    if repo_url and not is_public_repo(repo_url):
        return {
            "error": "Private repositories require authentication",
            "status": 403,
        }

    token = store_anonymous_results(findings)
    return {"status": "ok", "claim_token": token, "ttl_days": 30}


def scan_claim(body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/scan/claim — claim anonymous results after signup."""
    token = body.get("token", "")
    org_id = body.get("org_id", "")
    if not token or not org_id:
        return {"error": "Missing token or org_id", "status": 400}

    result = claim_results(token, org_id)
    return {**result, "status": 200 if result["status"] == "claimed" else 400}


def scan_ingest_sarif(body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/scan/ingest-sarif — ingest SARIF from crp-scan Action."""
    sarif = body.get("sarif", {})
    org_id = body.get("org_id", "")

    # Extract findings from SARIF
    runs = sarif.get("runs", [])
    findings: list[dict[str, Any]] = []
    for run in runs:
        for result in run.get("results", []):
            findings.append({
                "rule_id": result.get("ruleId", "unknown"),
                "message": result.get("message", {}).get("text", ""),
                "locations": result.get("locations", []),
                "severity": result.get("level", "warning"),
            })

    if org_id:
        # Directly attach to org
        from crp.comply.signup import claim_results
        token = store_anonymous_results(findings)
        claim_results(token, org_id)
        return {"status": "ok", "findings_count": len(findings)}

    # No org — store anonymously
    token = store_anonymous_results(findings)
    return {"status": "ok", "claim_token": token, "findings_count": len(findings)}


# ---------------------------------------------------------------------------
# Config application
# ---------------------------------------------------------------------------


def comply_apply_config(body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/comply/apply-config — one-click apply Safety Manifest change.

    Body: ``{"intent": {...}}`` — forwarded to No-Code Translator.
    """
    from crp.comply.no_code import generate_config, NoCodeTranslatorError

    intent = body.get("intent", {})
    try:
        config_yaml = generate_config(intent)
        return {"status": "ok", "config_yaml": config_yaml}
    except NoCodeTranslatorError as exc:
        return {"error": str(exc), "status": 400}
