# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for anonymous scan + signup (SPEC-048 Part C)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from crp.comply.signup import (
    _anonymous_store,
    claim_results,
    is_public_repo,
    store_anonymous_results,
)


class TestStoreAnonymousResults:
    def test_returns_token(self) -> None:
        tok = store_anonymous_results([{"finding": 1}])
        assert isinstance(tok, str)
        assert len(tok) > 20

    def test_stores_findings(self) -> None:
        tok = store_anonymous_results([{"finding": 1}])
        assert tok in _anonymous_store
        assert _anonymous_store[tok]["findings"] == [{"finding": 1}]


@pytest.fixture(autouse=True)
def _clerk_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from crp.comply.billing import entitlements

    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_clerk")
    # Reset the module-level cache so tests that run after others without the
    # env var still see the mocked secret.
    entitlements._CLERK_SECRET = None


class TestClaimResults:
    @patch("crp.comply.signup.requests.get")
    @patch("crp.comply.signup.requests.patch")
    def test_claims_successfully(self, mock_patch: MagicMock, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {"public_metadata": {"scanResults": []}}
        mock_get.return_value.raise_for_status = lambda: None
        mock_patch.return_value.raise_for_status = lambda: None

        tok = store_anonymous_results([{"finding": 1}])
        result = claim_results(tok, "org_1")
        assert result["status"] == "claimed"
        assert result["findings_count"] == 1

    def test_claim_unknown_token(self) -> None:
        result = claim_results("badtoken", "org_1")
        assert result["status"] == "not_found"

    def test_double_claim_same_org(self) -> None:
        with patch("crp.comply.signup.requests.get") as mock_get, \
             patch("crp.comply.signup.requests.patch") as mock_patch:
            mock_get.return_value.json.return_value = {"public_metadata": {"scanResults": []}}
            mock_get.return_value.raise_for_status = lambda: None
            mock_patch.return_value.raise_for_status = lambda: None
            tok = store_anonymous_results([{"finding": 1}])
            claim_results(tok, "org_1")
            result = claim_results(tok, "org_1")
            assert result["status"] == "already_claimed"

    def test_claim_expired_token(self) -> None:
        tok = store_anonymous_results([{"finding": 1}], ttl_days=-1)
        result = claim_results(tok, "org_1")
        assert result["status"] == "expired"


class TestIsPublicRepo:
    @patch("crp.comply.signup.requests.get")
    def test_detects_public_repo(self, mock_get: MagicMock) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"private": False}
        assert is_public_repo("https://github.com/torvalds/linux") is True

    @patch("crp.comply.signup.requests.get")
    def test_detects_private_repo(self, mock_get: MagicMock) -> None:
        mock_get.return_value.status_code = 404
        assert is_public_repo("https://github.com/acme/secret") is False
