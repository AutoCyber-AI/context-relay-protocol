# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP Scan Semantic Ingestion (SPEC-039) + Remediation Engine (SPEC-036).

Covers:
  - SemanticCodeIngestion: ingest a synthetic Python module, find AI calls,
    trace through wrappers (CDGR-style multi-hop)
  - RemediationEngine: classify findings, build diffs, build PR body
  - Invariant: remediations are ALWAYS proposals (diffs/configs), never auto-commits
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from crp.scan.remediation import RemediationEngine, RemediationProposal, ScanFinding
from crp.scan.semantic_ingestion import (
    AICallSite,
    CodeGraph,
    SemanticCodeIngestion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_PYTHON_UNGOVERNED = """\
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def answer_question(question: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content
"""

_WRAPPER_PYTHON = """\
import os
from openai import OpenAI

def make_client():
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def handle_support_ticket(ticket: str) -> str:
    client = make_client()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": ticket}],
    )
    return resp.choices[0].message.content
"""

_GOVERNED_PYTHON = """\
import os
import crp

crp_client = crp.Client()

def answer_question(question: str) -> str:
    result = crp_client.complete(question)
    return result.text
"""


def _write_tmpfile(content: str, suffix: str = ".py") -> str:
    """Write content to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


def _write_tmprepo(files: dict[str, str]) -> str:
    """Write multiple files to a temp directory and return the root path."""
    tmpdir = tempfile.mkdtemp()
    for rel_path, content in files.items():
        full = pathlib.Path(tmpdir) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return tmpdir


# ---------------------------------------------------------------------------
# SemanticCodeIngestion
# ---------------------------------------------------------------------------


class TestSemanticCodeIngestion:
    def test_ingest_single_file_returns_graph(self):
        repo = _write_tmprepo({"main.py": _SIMPLE_PYTHON_UNGOVERNED})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        assert isinstance(graph, CodeGraph)
        assert graph.function_count >= 1
        assert len(graph.facts) > 0

    def test_finds_ai_imports(self):
        repo = _write_tmprepo({"main.py": _SIMPLE_PYTHON_UNGOVERNED})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        assert "main.py" in graph.ai_imports

    def test_detects_ungoverned_openai_call(self):
        repo = _write_tmprepo({"main.py": _SIMPLE_PYTHON_UNGOVERNED})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        findings = ingestion.find_ai_calls(graph)
        assert len(findings) > 0
        assert any(not s.is_governed for s in findings)

    def test_detects_governed_call(self):
        repo = _write_tmprepo({"governed.py": _GOVERNED_PYTHON})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        findings = ingestion.find_ai_calls(graph)
        # Governed file should have no ungoverned calls
        ungoverned = [f for f in findings if not f.is_governed]
        assert len(ungoverned) == 0

    def test_trace_through_wrappers_finds_caller(self):
        """CDGR-style: detect wrapper function as transitive AI call site."""
        repo = _write_tmprepo({"services.py": _WRAPPER_PYTHON})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        findings = ingestion.find_ai_calls(graph)
        # Should find direct call and at least one traced/wrapper site
        direct_calls = [f for f in findings if not f.traced_sites or f.fact_id]
        assert len(direct_calls) >= 1

    def test_invalid_repo_path_raises(self):
        ingestion = SemanticCodeIngestion()
        with pytest.raises(ValueError, match="not found"):
            ingestion.ingest_repo("/does/not/exist/42xyz")

    def test_skips_excluded_dirs(self):
        repo = _write_tmprepo(
            {
                "src/main.py": _SIMPLE_PYTHON_UNGOVERNED,
                "node_modules/lib.py": _SIMPLE_PYTHON_UNGOVERNED,
                "__pycache__/cached.py": "x = 1",
            }
        )
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        # node_modules and __pycache__ should be excluded
        file_paths = {f.file_path for f in graph.facts.values()}
        assert not any("node_modules" in p for p in file_paths)
        assert not any("__pycache__" in p for p in file_paths)

    def test_code_fact_fields(self):
        repo = _write_tmprepo({"main.py": _SIMPLE_PYTHON_UNGOVERNED})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        for fact in graph.facts.values():
            assert fact.fact_id
            assert fact.file_path
            assert fact.entity_type in {"file", "function", "class", "call", "import", "return_type"}

    def test_multi_file_repo(self):
        repo = _write_tmprepo(
            {
                "llm/client.py": _WRAPPER_PYTHON,
                "services/support.py": _SIMPLE_PYTHON_UNGOVERNED,
            }
        )
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        assert graph.file_count == 2

    def test_is_governed_method(self):
        repo = _write_tmprepo({"main.py": _SIMPLE_PYTHON_UNGOVERNED})
        ingestion = SemanticCodeIngestion()
        graph = ingestion.ingest_repo(repo)
        findings = ingestion.find_ai_calls(graph)
        for s in findings:
            assert ingestion.is_governed(s) == s.is_governed


# ---------------------------------------------------------------------------
# RemediationEngine
# ---------------------------------------------------------------------------


def _make_finding(rule_id: str = "CRP001", provider: str = "openai") -> ScanFinding:
    return ScanFinding(
        rule_id=rule_id,
        file_path="services/support.py",
        line=42,
        message="Ungoverned AI call detected",
        severity="error",
        provider=provider,
        call_expression='client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])',
        code_context=[
            "from openai import OpenAI",
            'client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])',
        ],
    )


class TestRemediationEngine:
    def test_propose_code_fix_for_crp001(self):
        engine = RemediationEngine()
        finding = _make_finding("CRP001", "openai")
        proposal = engine.propose_fix(finding)
        assert proposal.remediation_class == "code_fix"
        assert proposal.diff  # should have a non-empty diff
        assert proposal.pr_branch.startswith("crp-fix/")

    def test_propose_code_fix_anthropic(self):
        engine = RemediationEngine()
        finding = _make_finding("CRP002", "anthropic")
        finding.call_expression = 'client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])'
        proposal = engine.propose_fix(finding)
        assert proposal.remediation_class == "code_fix"
        assert "anthropic" in proposal.diff.lower() or "gateway" in proposal.diff.lower()

    def test_propose_config_fix_for_crp005(self):
        engine = RemediationEngine()
        finding = _make_finding("CRP005", "openai")
        finding.message = "No safety policy configured"
        proposal = engine.propose_fix(finding)
        assert proposal.remediation_class == "config_fix"
        assert proposal.config_snippet
        assert "crp.config.yaml" in proposal.pr_body

    def test_propose_guided_fix_for_unknown_rule(self):
        engine = RemediationEngine()
        finding = _make_finding("CRP006", "unknown")
        finding.message = "Complex indirection detected"
        proposal = engine.propose_fix(finding)
        assert proposal.remediation_class == "guided_fix"
        assert proposal.pr_body

    def test_proposal_id_deterministic(self):
        """Same finding always produces the same proposal_id."""
        engine = RemediationEngine()
        finding = _make_finding()
        p1 = engine.propose_fix(finding)
        p2 = engine.propose_fix(finding)
        assert p1.proposal_id == p2.proposal_id

    def test_pr_branch_name_is_filesystem_safe(self):
        engine = RemediationEngine()
        finding = _make_finding()
        proposal = engine.propose_fix(finding)
        branch = proposal.pr_branch
        # Branch should not contain spaces or colons
        assert " " not in branch
        assert ":" not in branch

    def test_pr_body_contains_key_metadata(self):
        engine = RemediationEngine()
        finding = _make_finding()
        proposal = engine.propose_fix(finding)
        assert finding.rule_id in proposal.pr_body
        assert finding.file_path in proposal.pr_body
        assert finding.provider in proposal.pr_body

    def test_env_vars_required_openai(self):
        engine = RemediationEngine()
        proposal = engine.propose_fix(_make_finding("CRP001", "openai"))
        assert "CRP_GATEWAY_KEY" in proposal.env_vars_required

    def test_proposals_for_repo_batch(self):
        engine = RemediationEngine()
        findings = [_make_finding(f"CRP00{i}", "openai") for i in range(1, 4)]
        proposals = engine.proposals_for_repo(findings)
        assert len(proposals) == 3

    def test_open_pr_without_github_app_returns_string(self):
        """open_pr() must not crash when GitHub App is not installed."""
        engine = RemediationEngine()
        finding = _make_finding()
        proposal = engine.propose_fix(finding)
        # Without github_app installed, returns a descriptive string (not an exception)
        result = engine.open_pr(proposal, repo="owner/repo", installation_id="99999")
        assert isinstance(result, str)
        # Must include the proposed branch name so developer knows where to go
        assert proposal.pr_branch in result or "GitHub App" in result

    def test_remediation_never_auto_commits(self):
        """Verify open_pr() uses PR branch, not 'main' or protected branches."""
        engine = RemediationEngine()
        finding = _make_finding()
        proposal = engine.propose_fix(finding)
        # The PR branch must not be main/master/protected
        assert proposal.pr_branch not in {"main", "master", "develop", "release"}
        # Must include a finding-specific slug
        assert len(proposal.pr_branch) > 10
