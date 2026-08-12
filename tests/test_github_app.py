# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for GitHub App client (SPEC-048).

All GitHub API calls are mocked — no live network.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crp.scan.github_app import GithubAppClient


# Test RSA key pair (PEM) — generated at import time for testing only.
# This avoids committing any real-looking private key to the repository.
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_TEST_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PRIVATE_KEY = _TEST_RSA_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

# Derive public key from private key for JWT verification
_private_key_obj = serialization.load_pem_private_key(
    _TEST_PRIVATE_KEY.encode(), password=None, backend=default_backend()
)
_TEST_PUBLIC_KEY = _private_key_obj.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> GithubAppClient:
    monkeypatch.setenv("GITHUB_APP_ID", "3971977")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _TEST_PRIVATE_KEY)
    return GithubAppClient.from_env()


class TestAppJWT:
    def test_jwt_has_correct_claims(self, client: GithubAppClient) -> None:
        token = client._app_jwt()
        import jwt
        decoded = jwt.decode(token, _TEST_PUBLIC_KEY, algorithms=["RS256"], options={"verify_exp": False})
        assert decoded["iss"] == "3971977"
        assert "exp" in decoded
        assert "iat" in decoded


class TestInstallationToken:
    @patch("crp.scan.github_app.requests.post")
    def test_mints_token(self, mock_post: MagicMock, client: GithubAppClient) -> None:
        mock_post.return_value.json.return_value = {"token": "ghs_testtoken"}
        mock_post.return_value.raise_for_status = lambda: None
        tok = client.installation_token("123")
        assert tok == "ghs_testtoken"


class TestListRepos:
    @patch("crp.scan.github_app.requests.get")
    @patch("crp.scan.github_app.requests.post")
    def test_lists_repositories(self, mock_post: MagicMock, mock_get: MagicMock, client: GithubAppClient) -> None:
        mock_post.return_value.json.return_value = {"token": "ghs_test"}
        mock_post.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {"repositories": [{"full_name": "acme/repo1"}]}
        mock_get.return_value.links = {}
        mock_get.return_value.raise_for_status = lambda: None
        repos = client.list_repos("123")
        assert len(repos) == 1
        assert repos[0]["full_name"] == "acme/repo1"

    @patch("crp.scan.github_app.requests.get")
    @patch("crp.scan.github_app.requests.post")
    def test_uses_correct_github_endpoint(
        self, mock_post: MagicMock, mock_get: MagicMock, client: GithubAppClient
    ) -> None:
        """Regression test: GitHub's real endpoint is GET /installation/repositories
        (singular, no ID in the path -- the installation is implied by the token).
        There is no /installations/{id}/repositories route; that URL 404s even
        with a valid installation_id and a valid token."""
        mock_post.return_value.json.return_value = {"token": "ghs_test"}
        mock_post.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {"repositories": []}
        mock_get.return_value.links = {}
        mock_get.return_value.raise_for_status = lambda: None
        client.list_repos("138425465")
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://api.github.com/installation/repositories"
        assert "138425465" not in called_url


class TestWebhookVerification:
    def test_verify_valid_signature(self) -> None:
        body = b'{"action":"push"}'
        secret = "testsecret"
        import hmac, hashlib
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert GithubAppClient.verify_webhook(body, sig, secret) is True

    def test_verify_invalid_signature(self) -> None:
        body = b'{"action":"push"}'
        assert GithubAppClient.verify_webhook(body, "sha256=bad", "secret") is False

    def test_verify_missing_prefix(self) -> None:
        body = b'{"action":"push"}'
        assert GithubAppClient.verify_webhook(body, "badprefix", "secret") is False
