# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unit tests for CRP v4 response headers."""

from __future__ import annotations

from crp_shared.crp_headers import (
    CRP_HEADER_NAMES,
    HeaderContext,
    build_crp_headers,
)


def test_header_count_meets_spec() -> None:
    ctx = HeaderContext(
        session_id="s1",
        window_id="w1",
        conversation_id="c1",
        dag_node_id="d1",
        continuation_count=3,
        window_number=2,
        quality_hash="sha256:qh",
        dpe_hash="sha256:dpe",
        soft_budget_used=100,
        soft_budget_total=2000,
        hard_budget_used=500,
        hard_budget_total=8000,
        strategy="balanced",
        policy_id="pol-1",
        policy_version="1.0",
        risk_score=0.42,
        risk_level="medium",
        fabrication_score=0.1,
        distortion_score=0.05,
        contradiction_score=0.02,
        repetition_score=0.0,
        completeness_score=0.95,
        lineage_hash="sha256:lh",
        chain_tip_hmac="sha256:tip",
        window_hmac="sha256:wh",
        ckf_etag="etag-1",
        retrieval_confidence=0.88,
        provenance_id="prov-1",
        pii_detected=True,
        eu_ai_act_class="high",
        model_family="gpt",
        model_name="gpt-4o",
        model_provider="openai",
        latency_ms=123.45,
        region="us-east",
        tenant_id="t1",
        user_id="u1",
    )
    headers = build_crp_headers(ctx)

    for name in CRP_HEADER_NAMES:
        assert name in headers, f"Missing required header {name}"

    assert headers["CRP-Session-Id"] == "s1"
    assert headers["CRP-Risk-Score"] == "0.4200"
    assert headers["CRP-PII-Detected"] == "true"
    assert headers["CRP-EU-AI-Act-Class"] == "high"


def test_empty_string_fields_omitted() -> None:
    ctx = HeaderContext(session_id="s1")
    headers = build_crp_headers(ctx)
    assert headers["CRP-Session-Id"] == "s1"
    assert "CRP-Window-Id" not in headers
    assert "CRP-Model-Family" not in headers


def test_extras_propagated() -> None:
    ctx = HeaderContext(session_id="s1", extras={"CRP-Custom": "value"})
    headers = build_crp_headers(ctx)
    assert headers["CRP-Custom"] == "value"
