# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Async HTTP clients for CRP Gateway and CRP Comply backends.

The clients degrade cleanly when backend URLs or API keys are missing, returning
``BackendNotConfigured`` so that MCP tools can fall back to safe stubs.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class BackendNotConfigured(Exception):
    """Raised when a backend call is requested but env is missing or incomplete."""


class BackendError(Exception):
    """Raised when a backend call fails after configuration is present."""


class CRPBackendClient:
    """Generic async JSON client for a CRP backend service."""

    def __init__(self, base_url: str | None, api_key: str | None) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _ensure_configured(self) -> None:
        if not self.base_url or not self.api_key:
            raise BackendNotConfigured("backend not configured")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_configured()
        try:
            response = await self.client.request(
                method,
                path,
                json=json,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise BackendError(
                f"backend_http_error:{exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise BackendError(f"backend_request_error:{exc}") from exc

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


class GatewayClient(CRPBackendClient):
    """Client for the CRP Gateway metered-calls and deployment API."""

    def __init__(self) -> None:
        super().__init__(
            base_url=os.environ.get("CRP_GATEWAY_URL"),
            api_key=os.environ.get("CRP_HOSTED_API_KEY"),
        )

    async def create_api_key(self, name: str) -> dict[str, Any]:
        return await self.request("POST", "/keys", json={"name": name})

    async def test_call(self, message: str, model: str) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/test-call",
            json={"message": message, "model": model},
        )

    async def deploy_endpoint(self, pipeline_id: str, region: str) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/deployments",
            json={"pipeline_id": pipeline_id, "region": region},
        )

    async def run_benchmark(self, dataset: str) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/benchmarks",
            json={"dataset": dataset},
        )


class ComplyClient(CRPBackendClient):
    """Client for the CRP Comply governance and checkpoint API."""

    def __init__(self) -> None:
        super().__init__(
            base_url=os.environ.get("CRP_COMPLY_BASE_URL"),
            api_key=os.environ.get("CRP_HOSTED_API_KEY"),
        )

    async def create_analysis(self, repo_ref: str, framework: str) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/analyses",
            json={"repo_ref": repo_ref, "framework": framework},
        )

    async def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/analyses/{analysis_id}")

    async def diff_analysis(
        self, analysis_id: str, baseline_id: str
    ) -> dict[str, Any]:
        return await self.request(
            "GET",
            f"/analyses/{analysis_id}/diff",
            params={"baseline": baseline_id},
        )

    async def create_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/checkpoints", json=payload)


class ScanClient(CRPBackendClient):
    """Client for the CRP Scan repository-scanning backend."""

    def __init__(self) -> None:
        super().__init__(
            base_url=os.environ.get("CRP_SCAN_BASE_URL"),
            api_key=os.environ.get("CRP_HOSTED_API_KEY"),
        )

    async def create_scan(self, repo_ref: str, branch: str) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/scans",
            json={"repo_ref": repo_ref, "branch": branch},
        )

    async def get_scan(self, scan_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/scans/{scan_id}")
