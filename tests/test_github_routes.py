# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for GitHub + Scan route handlers (SPEC-048)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crp.comply.github_routes import (
    github_callback,
    github_connect,
    github_installed,
    github_webhook,
    scan_anonymous,
    scan_claim,
    scan_ingest_sarif,
    comply_apply_config,
)


class TestGithubCallback:
    def test_returns_installation_id(self) -> None:
        result = github_callback({"installation_id": "123", "setup_action": "install"})
        assert result["status"] == "ok"
        assert result["installation_id"] == "123"

    def test_missing_id_returns_error(self) -> None:
        result = github_callback({})
        assert result["status"] == 400


class TestGithubInstalled:
    def test_returns_ok(self) -> None:
        result = github_installed({"installation_id": "123"})
        assert result["status"] == "ok"


class TestGithubConnect:
    def test_redirects_to_install(self) -> None:
        result = github_connect()
        assert result["status"] == "redirect"
        assert "github.com/apps/crp-comply" in result["url"]


class TestGithubWebhook:
    @patch.dict("os.environ", {"GITHUB_APP_WEBHOOK_SECRET": "testsecret"}, clear=False)
    def test_verifies_and_routes_push(self) -> None:
        import json, hmac, hashlib
        body = json.dumps({"repository": {"owner": {"login": "acme"}, "name": "repo1"}}).encode()
        sig = "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
        result = github_webhook(body, {"X-Hub-Signature-256": sig, "X-GitHub-Event": "push"})
        assert result["status"] == "ok"
        assert result["action"] == "scan_enqueued"

    @patch.dict("os.environ", {"GITHUB_APP_WEBHOOK_SECRET": "testsecret"}, clear=False)
    def test_rejects_bad_signature(self) -> None:
        result = github_webhook(b"{}", {"X-Hub-Signature-256": "sha256=bad", "X-GitHub-Event": "push"})
        assert result["status"] == 400


class TestScanAnonymous:
    @patch("crp.comply.github_routes.is_public_repo", return_value=True)
    def test_stores_public_repo(self, mock_public: MagicMock) -> None:
        result = scan_anonymous({"findings": [{"rule": "r1"}], "repo_url": "https://github.com/torvalds/linux"})
        assert result["status"] == "ok"
        assert "claim_token" in result

    @patch("crp.comply.github_routes.is_public_repo", return_value=False)
    def test_rejects_private_repo(self, mock_public: MagicMock) -> None:
        result = scan_anonymous({"findings": [{"rule": "r1"}], "repo_url": "https://github.com/acme/secret"})
        assert result["status"] == 403


class TestScanClaim:
    @patch("crp.comply.signup.requests.get")
    @patch("crp.comply.signup.requests.patch")
    def test_claims_token(self, mock_patch: MagicMock, mock_get: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_clerk")
        mock_get.return_value.json.return_value = {"public_metadata": {"scanResults": []}}
        mock_get.return_value.raise_for_status = lambda: None
        mock_patch.return_value.raise_for_status = lambda: None
        from crp.comply.signup import store_anonymous_results
        tok = store_anonymous_results([{"rule": "r1"}])
        result = scan_claim({"token": tok, "org_id": "org_x"})
        assert result["status"] == 200


class TestScanIngestSarif:
    def test_ingests_sarif(self) -> None:
        sarif = {
            "runs": [{
                "results": [
                    {"ruleId": "r1", "message": {"text": "msg"}, "locations": [], "level": "warning"}
                ]
            }]
        }
        result = scan_ingest_sarif({"sarif": sarif})
        assert result["status"] == "ok"
        assert result["findings_count"] == 1


class TestComplyApplyConfig:
    def test_applies_valid_intent(self) -> None:
        result = comply_apply_config({"intent": {"prevent_hallucinations": True, "profile": "strict"}})
        assert result["status"] == "ok"
        assert "config_yaml" in result

    def test_rejects_invalid_intent(self) -> None:
        result = comply_apply_config({"intent": {"time_travel": True}})
        assert result["status"] == 400
