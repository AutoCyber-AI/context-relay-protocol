# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""GitHub App client — JWT, installation tokens, transient clone, PRs (SPEC-048).

Security invariants:
  - Installation tokens minted per-use, ~1h TTL, NEVER persisted.
  - Private key loaded from env path only, never in code.
  - Remediation PRs always to dedicated branches — never direct commits.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import subprocess
import tempfile
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_APP_TOKEN_TTL_SECONDS = 600  # 10 minutes
_INSTALL_TOKEN_TTL_SECONDS = 3600  # 1 hour


class GithubAppClient:
    """CRP Comply GitHub App client.

    Usage::

        client = GithubAppClient.from_env()
        token = client.installation_token(installation_id="123")
        repos = client.list_repos(installation_id="123")
    """

    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._app_id = app_id
        self._private_key_pem = private_key_pem
        self._client_id = client_id
        self._client_secret = client_secret

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "GithubAppClient":
        """Create client from environment variables."""
        app_id = os.environ.get("GITHUB_APP_ID", "")
        client_id = os.environ.get("GITHUB_APP_CLIENT_ID", "")
        client_secret = os.environ.get("GITHUB_APP_CLIENT_SECRET", "")
        pem_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")

        if not app_id:
            raise RuntimeError("GITHUB_APP_ID environment variable is not set")

        private_key_pem = ""
        if pem_path and os.path.isfile(pem_path):
            private_key_pem = open(pem_path, encoding="utf-8").read()
        else:
            # Fallback: read raw PEM from env (for Railway-style env vars)
            raw_pem = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
            if raw_pem:
                private_key_pem = raw_pem.replace("\\n", "\n")

        if not private_key_pem or "PRIVATE KEY" not in private_key_pem:
            raise RuntimeError("GitHub App private key not found — set GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY")

        return cls(
            app_id=app_id,
            private_key_pem=private_key_pem,
            client_id=client_id or None,
            client_secret=client_secret or None,
        )

    # ------------------------------------------------------------------
    # JWT + Token minting
    # ------------------------------------------------------------------

    def _app_jwt(self) -> str:
        """Sign a 10-minute JWT with RS256 for GitHub App auth."""
        import jwt  # PyJWT

        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + _APP_TOKEN_TTL_SECONDS,
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key_pem, algorithm="RS256")  # type: ignore[no-any-return]

    def installation_token(self, installation_id: str | int) -> str:
        """Mint a short-lived (~1h) installation access token.

        The token is returned to the caller and NEVER persisted.
        """
        url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {self._app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = requests.post(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        token = resp.json().get("token", "")
        if not token:
            raise RuntimeError("GitHub returned empty installation token")
        logger.debug("Minted installation token for %s", installation_id)
        return token

    # ------------------------------------------------------------------
    # Repository operations
    # ------------------------------------------------------------------

    def list_repos(self, installation_id: str | int) -> list[dict[str, Any]]:
        """List repositories accessible to this installation.

        GitHub's endpoint for this is ``GET /installation/repositories``
        (singular ``installation``, no ID in the path) -- the installation
        is implied entirely by the installation access token used for auth.
        There is no ``/installations/{id}/repositories`` route; using it
        returns a 404 regardless of a valid installation_id/token.
        """
        token = self.installation_token(installation_id)
        url = f"{_GITHUB_API_BASE}/installation/repositories"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        repos: list[dict[str, Any]] = []
        while url:
            resp = requests.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            repos.extend(data.get("repositories", []))
            url = resp.links.get("next", {}).get("url")
        return repos

    def fetch_repo(
        self,
        installation_id: str | int,
        owner: str,
        repo: str,
        branch: str = "main",
    ) -> str:
        """Transiently clone a repo and return the temp directory path.

        Caller MUST delete the directory after scanning.
        """
        token = self.installation_token(installation_id)
        clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        tmpdir = tempfile.mkdtemp(prefix=f"crp_scan_{owner}_{repo}_")
        cmd = [
            "git", "clone",
            "--depth", "1",
            "--branch", branch,
            clone_url,
            tmpdir,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
            logger.info("Cloned %s/%s to %s", owner, repo, tmpdir)
        except subprocess.CalledProcessError as exc:
            logger.error("Git clone failed: %s", exc.stderr)
            raise RuntimeError(f"Failed to clone {owner}/{repo}") from exc
        return tmpdir

    # ------------------------------------------------------------------
    # Remediation PR (always to dedicated branch)
    # ------------------------------------------------------------------

    def create_branch(
        self,
        installation_id: str | int,
        owner: str,
        repo: str,
        branch_name: str,
        from_sha: str,
    ) -> dict[str, Any]:
        """Create a new branch from a SHA."""
        token = self.installation_token(installation_id)
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.post(
            url,
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": from_sha},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def commit_file(
        self,
        installation_id: str | int,
        owner: str,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> dict[str, Any]:
        """Commit a file via the Contents API (creates or updates)."""
        token = self.installation_token(installation_id)
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        # Check if file exists to get SHA for update
        existing_sha = ""
        get_resp = requests.get(
            url, headers=headers, params={"ref": branch}, timeout=10.0,
        )
        if get_resp.status_code == 200:
            existing_sha = get_resp.json().get("sha", "")

        import base64
        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if existing_sha:
            body["sha"] = existing_sha

        resp = requests.put(url, headers=headers, json=body, timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    def open_pr(
        self,
        installation_id: str | int,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> dict[str, Any]:
        """Open a pull request from *head* to *base*."""
        token = self.installation_token(installation_id)
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.post(
            url,
            headers=headers,
            json={"title": title, "head": head, "base": base, "body": body},
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info("Opened PR %s/%s:%s -> %s", owner, repo, head, base)
        return resp.json()

    def open_remediation_pr(
        self,
        installation_id: str | int,
        owner: str,
        repo: str,
        base_branch: str,
        file_changes: dict[str, str],
        pr_title: str,
        pr_body: str,
    ) -> dict[str, Any]:
        """Full remediation flow: create branch → commit files → open PR.

        Args:
            file_changes: dict of ``{path: new_content}``.
        """
        # Get default branch SHA
        token = self.installation_token(installation_id)
        repo_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        repo_info = requests.get(repo_url, headers=headers, timeout=10.0).json()
        default_branch = repo_info.get("default_branch", "main")

        # Get SHA of default branch
        ref_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{default_branch}"
        ref_info = requests.get(ref_url, headers=headers, timeout=10.0).json()
        from_sha = ref_info["object"]["sha"]

        # Dedicated remediation branch
        import uuid
        branch_name = f"crp-remediation-{uuid.uuid4().hex[:8]}"

        self.create_branch(installation_id, owner, repo, branch_name, from_sha)
        for path, content in file_changes.items():
            self.commit_file(installation_id, owner, repo, path, content, branch_name, f"CRP remediation: {path}")

        return self.open_pr(
            installation_id, owner, repo, pr_title, branch_name, default_branch, pr_body,
        )

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    @staticmethod
    def verify_webhook(body: bytes, sig_header: str, webhook_secret: str) -> bool:
        """Verify GitHub webhook HMAC-SHA256 signature.

        Args:
            body: Raw request body bytes.
            sig_header: The ``X-Hub-Signature-256`` header value (``sha256=...``).
            webhook_secret: The GitHub App webhook secret.

        Returns:
            True if signature is valid.
        """
        if not sig_header.startswith("sha256="):
            return False
        expected = sig_header[7:]
        computed = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, computed)
