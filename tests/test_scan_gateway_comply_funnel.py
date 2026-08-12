# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Integration test: Scan -> Gateway -> Comply evidence funnel (SPEC-013/016/042).

This test proves the product loop described in CRP_v6_Agent_SDK_and_Launch_Completion:

    1. CRP Scan finds an ungoverned AI call in source code.
    2. The remediation engine proposes routing that call through the CRP Gateway.
    3. A request processed by the Gateway emits audit events.
    4. The Comply Gateway Client receives those events and builds an evidence pack.

No external APIs, LLMs, or network calls are required.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def ungoverned_repo() -> str:
    """Create a temporary repository containing one ungoverned OpenAI call."""
    code = '''\
import os
import openai

openai.api_key = os.environ["OPENAI_API_KEY"]


def answer_ticket(question: str) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content
'''
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "support_bot.py").write_text(code, encoding="utf-8")
        yield str(repo)


class _FakeRouter:
    """Router that returns a deterministic governed response without network."""

    def dispatch(self, request: Any, messages: list[Any], session: Any) -> Any:
        from crp.gateway.api import ProviderResponse

        return ProviderResponse(
            content="Governed answer from CRP Gateway",
            model=request.model,
            finish_reason="stop",
        )


def test_scan_finds_ungoverned_call_and_proposes_gateway_fix(ungoverned_repo: str) -> None:
    """Scan detects the call and remediation routes it through the Gateway."""
    from crp.scan.remediation import RemediationEngine, ScanFinding
    from crp.scan.semantic_ingestion import SemanticCodeIngestion

    ingestion = SemanticCodeIngestion()
    graph = ingestion.ingest_repo(ungoverned_repo)
    sites = ingestion.find_ai_calls(graph)

    ungoverned = [s for s in sites if not s.is_governed]
    assert len(ungoverned) >= 1, "expected at least one ungoverned OpenAI call site"

    site = ungoverned[0]
    finding = ScanFinding(
        rule_id="CRP001",
        file_path=site.file_path,
        line=site.line,
        message="Direct OpenAI client instantiation without CRP governance",
        severity="error",
        provider=site.provider,
        call_expression=site.call_expression,
        code_context=[site.call_expression],
        has_crp_import=False,
    )

    engine = RemediationEngine()
    proposal = engine.propose_fix(finding)

    assert proposal.remediation_class == "code_fix"
    assert "gateway.crprotocol.io" in proposal.diff or "crp.Client" in proposal.diff
    assert "CRP_GATEWAY_KEY" in proposal.env_vars_required


def test_gateway_emits_audit_events_to_comply() -> None:
    """A Gateway request produces a Comply evidence pack."""
    from crp.comply.gateway_client import _evidence_store, get_evidence_pack
    from crp.gateway.api import GatewayRequestLifecycle

    _evidence_store.clear()

    lifecycle = GatewayRequestLifecycle(router=_FakeRouter())
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "What is CRP?"}],
    }
    headers = {"Authorization": "Bearer sk-test", "CRP-Safety-Profile": "balanced"}

    result = lifecycle.process(body, headers)

    assert result["status_code"] == 200
    assert "CRP-Risk-Level" in result["headers"]

    pack = get_evidence_pack("local")
    assert pack["event_count"] > 0
    assert "Art. 12 (Logging)" in pack["article_coverage"]
    assert pack["risk_summary"]

    # Each event should carry regulation article mapping.
    for event in pack["events"]:
        assert "regulation_articles" in event
        assert event["tenant_id"] == "local"


def test_full_funnel_scan_to_comply(ungoverned_repo: str) -> None:
    """End-to-end: scan finding -> gateway remediation -> comply evidence."""
    from crp.comply.gateway_client import _evidence_store, get_evidence_pack
    from crp.gateway.api import GatewayRequestLifecycle
    from crp.scan.remediation import RemediationEngine, ScanFinding
    from crp.scan.semantic_ingestion import SemanticCodeIngestion

    _evidence_store.clear()

    # 1. Scan
    graph = SemanticCodeIngestion().ingest_repo(ungoverned_repo)
    sites = [s for s in SemanticCodeIngestion().find_ai_calls(graph) if not s.is_governed]
    assert sites

    finding = ScanFinding(
        rule_id="CRP001",
        file_path=sites[0].file_path,
        line=sites[0].line,
        message="Direct OpenAI client instantiation without CRP governance",
        severity="error",
        provider=sites[0].provider,
        call_expression=sites[0].call_expression,
        code_context=[sites[0].call_expression],
        has_crp_import=False,
    )

    # 2. Remediation proposes Gateway route
    proposal = RemediationEngine().propose_fix(finding)
    assert proposal.remediation_class == "code_fix"

    # 3. A governed request flows through Gateway
    lifecycle = GatewayRequestLifecycle(router=_FakeRouter())
    result = lifecycle.process(
        {"model": "gpt-4o", "messages": [{"role": "user", "content": "Fix it"}]},
        {"Authorization": "Bearer sk-test"},
    )
    assert result["status_code"] == 200

    # 4. Comply has evidence
    pack = get_evidence_pack("local")
    assert pack["event_count"] > 0
    assert pack["article_coverage"]
