# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Scan — Remediation Engine (SPEC-036).

For each ungoverned AI call site detected by Scan, the Remediation Engine
produces the exact code change that governs it.  Remediations are delivered
as pull-request-ready diffs — never auto-committed.

Three remediation classes (SPEC-036 §2):
  CODE FIX    — governed-client diff (PR) for ungoverned AI calls.
  CONFIG FIX  — safety/policy settings applied in CRP Comply control plane.
  GUIDED FIX  — checkpoint-style task when human judgment is required.

CRITICAL INVARIANT (AGENTS.md §NON-NEGOTIABLE):
  Remediations are ALWAYS proposals (PRs).  NEVER auto-commit to protected
  branches.  The ``open_pr()`` method only opens a PR; the caller must hold
  a valid GitHub installation token and a dedicated (non-protected) branch.

Usage::

    engine = RemediationEngine()
    proposal = engine.propose_fix(scan_finding)
    print(proposal.diff)
    # For paid users with GitHub App connected:
    pr_url = engine.open_pr(proposal, repo="owner/repo", installation_id="12345")
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import pathlib
import textwrap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ScanFinding:
    """A single finding from CRP Scan.

    Maps to the SARIF result structure emitted by ``crp-scan`` GitHub Action.
    """

    rule_id: str  # e.g. CRP001 – CRP006
    file_path: str
    line: int
    message: str
    severity: str  # "error" | "warning" | "note"
    provider: str  # "openai" | "anthropic" | "langchain" | etc.
    # The detected call expression (may be empty if extracted from SARIF)
    call_expression: str = ""
    # Existing surrounding code context (3–5 lines around the finding)
    code_context: list[str] = dataclasses.field(default_factory=list)
    # Whether the file currently imports from any CRP package
    has_crp_import: bool = False


@dataclasses.dataclass
class RemediationProposal:
    """A concrete, actionable remediation for a ScanFinding.

    Always produced by the engine before any PR is opened.  The diff field
    contains the unified diff ready for ``git apply`` / PR creation.
    """

    proposal_id: str
    finding: ScanFinding
    remediation_class: str  # "code_fix" | "config_fix" | "guided_fix"
    title: str
    description: str
    diff: str  # unified diff (empty for config/guided fixes)
    config_snippet: str  # crp.config.yaml fragment (for config fixes)
    pr_branch: str  # suggested branch name for the PR
    pr_body: str  # PR description markdown
    env_vars_required: list[str] = dataclasses.field(default_factory=list)
    doc_links: list[str] = dataclasses.field(default_factory=list)
    # Verification step: command to run after applying the fix
    verification_command: str = ""


# ---------------------------------------------------------------------------
# Template library
# ---------------------------------------------------------------------------

# Jinja-style templates rendered with simple str.format_map().
# Full Jinja2 template files would live in crp/scan/templates/ for production.

_TEMPLATE_OPENAI_GATEWAY = """\
client = OpenAI(
    api_key=os.environ["CRP_GATEWAY_KEY"],
    base_url="https://gateway.crprotocol.io/v1",
)
"""

_TEMPLATE_ANTHROPIC_GATEWAY = """\
client = anthropic.Anthropic(
    api_key=os.environ["CRP_GATEWAY_KEY"],
    base_url="https://gateway.crprotocol.io/v1/anthropic",
)
"""

_TEMPLATE_LANGCHAIN_GATEWAY = """\
llm = ChatOpenAI(
    model="{model_name}",
    openai_api_key=os.environ["CRP_GATEWAY_KEY"],
    openai_api_base="https://gateway.crprotocol.io/v1",
)
"""

_TEMPLATE_CRP_CLIENT = """\
import crp

crp_client = crp.Client()  # governance layer
result = crp_client.complete({original_call_args})
"""

_PR_BODY_TEMPLATE = """\
## CRP Scan — Remediation PR

**Finding:** `{rule_id}` — {message}
**File:** `{file_path}` (line {line})
**Provider:** {provider}

### What Was Detected

{finding_description}

### What This Change Does

Routes the AI call through the CRP Gateway so every call is automatically
governed: fabrication detection, hallucination scoring, grounding verification,
audit trail, and compliance evidence.

### Required Environment Variable

Add the following environment variable to your deployment:

```
CRP_GATEWAY_KEY=<your-crp-gateway-key>
```

Get your Gateway key at: https://crprotocol.io/dashboard

### After Merging

1. Set the `CRP_GATEWAY_KEY` env var.
2. Remove the old provider API key from your env (the Gateway holds it securely).
3. Verify: `{verification_command}`

### Documentation

- [CRP Gateway docs](https://crprotocol.io/docs/gateway)
- [Migration guide](https://crprotocol.io/docs/migrate)
- [Finding detail: {rule_id}](https://crprotocol.io/docs/scan/{rule_id_lower})
"""

_CONFIG_FIX_TEMPLATE = """\
# Add to crp.config.yaml (or create the file in your project root)
safety:
  profile: "{safety_profile}"
  halt_on: "{halt_level}"
  require_grounding: {grounding_threshold}
"""


# ---------------------------------------------------------------------------
# Remediation Engine
# ---------------------------------------------------------------------------


class RemediationEngine:
    """Generate concrete remediation proposals for CRP Scan findings.

    Args:
        templates_dir: Optional path to a directory containing Jinja2
            ``.py.j2`` and ``.yaml.j2`` templates for provider-specific
            remediations.  If None, built-in string templates are used.
    """

    def __init__(self, templates_dir: str | None = None) -> None:
        self._templates_dir = (
            pathlib.Path(templates_dir) if templates_dir else self._default_templates_dir()
        )

    # ------------------------------------------------------------------
    # Public API (SPEC-036 §3–§5)
    # ------------------------------------------------------------------

    def propose_fix(self, finding: ScanFinding) -> RemediationProposal:
        """Produce a remediation proposal for *finding*.

        Determines the remediation class, selects the appropriate template,
        and renders the diff / config snippet + PR body.

        Args:
            finding: A ScanFinding from the scan engine.

        Returns:
            RemediationProposal with all fields populated.  The ``diff``
            field will be non-empty for code fixes; ``config_snippet`` for
            config fixes.
        """
        rem_class = self._classify(finding)

        if rem_class == "code_fix":
            return self._build_code_fix(finding)
        if rem_class == "config_fix":
            return self._build_config_fix(finding)
        return self._build_guided_fix(finding)

    def open_pr(
        self,
        proposal: RemediationProposal,
        repo: str,
        installation_id: str,
        base_branch: str = "main",
    ) -> str:
        """Open a pull request with the remediation diff.

        ALWAYS opens a PR to a dedicated branch — NEVER commits directly to
        a protected branch (AGENTS.md invariant #11).

        Args:
            proposal: RemediationProposal produced by :meth:`propose_fix`.
            repo: Full repository name, e.g. ``"owner/repo"``.
            installation_id: GitHub App installation ID for the repo.
            base_branch: The target base branch for the PR.  Default ``main``.

        Returns:
            The URL of the created pull request.

        Note:
            This method requires ``crp.scan.github_app`` (Agent B Round 3)
            to provide the GitHub App token-minting facility.  If not yet
            installed, returns a descriptive error string.
        """
        try:
            from crp.scan.github_app import GithubAppClient  # type: ignore[import]
        except ImportError:
            return (
                f"[GitHub App not connected — install crp[github] and configure "
                f"GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY. "
                f"Proposed branch: {proposal.pr_branch}]"
            )

        # NEVER commit to base_branch directly — use the PR branch from the proposal.
        try:
            github = GithubAppClient.from_env()
        except RuntimeError:
            return (
                f"[GitHub App not configured — set GITHUB_APP_ID + "
                f"GITHUB_APP_PRIVATE_KEY (or GITHUB_APP_PRIVATE_KEY_PATH). "
                f"Proposed branch: {proposal.pr_branch}]"
            )
        # Split owner/repo from the repo full name
        owner_name, repo_name = repo.split("/", 1) if "/" in repo else ("", repo)
        pr_url = github.open_remediation_pr(
            installation_id=installation_id,
            owner=owner_name,
            repo=repo_name,
            base_branch=base_branch,
            file_changes={proposal.target_file or "crp.config.yaml": proposal.diff},
            pr_title=proposal.title,
            pr_body=proposal.pr_body,
        )
        logger.info("Remediation PR opened: %s → %s", repo, pr_url)
        return pr_url

    def proposals_for_repo(self, findings: list[ScanFinding]) -> list[RemediationProposal]:
        """Produce proposals for all *findings* in a repo scan result."""
        return [self.propose_fix(f) for f in findings]

    # ------------------------------------------------------------------
    # Remediation class determination
    # ------------------------------------------------------------------

    def _classify(self, finding: ScanFinding) -> str:
        """Determine the remediation class for a finding (SPEC-036 §2)."""
        # Ungoverned AI call → code fix (most common)
        if finding.rule_id in {"CRP001", "CRP002", "CRP003", "CRP004"}:
            return "code_fix"
        # Missing safety policy / no audit trail → config fix
        if finding.rule_id in {"CRP005"}:
            return "config_fix"
        # Complex / ambiguous findings → guided fix
        return "guided_fix"

    # ------------------------------------------------------------------
    # Code fix (§3 of SPEC-036)
    # ------------------------------------------------------------------

    def _build_code_fix(self, finding: ScanFinding) -> RemediationProposal:
        """Build a governed-client diff PR for an ungoverned AI call."""
        provider = finding.provider.lower()
        template_key = self._select_code_template(provider, finding)
        diff = self._render_code_diff(template_key, finding)

        pr_branch = self._pr_branch_name(finding)
        pr_body = _PR_BODY_TEMPLATE.format_map(
            {
                "rule_id": finding.rule_id,
                "message": finding.message,
                "file_path": finding.file_path,
                "line": finding.line,
                "provider": finding.provider,
                "finding_description": self._finding_description(finding),
                "verification_command": "python -c \"import crp; print('CRP gateway active')\"",
                "rule_id_lower": finding.rule_id.lower(),
            }
        )

        return RemediationProposal(
            proposal_id=self._proposal_id(finding),
            finding=finding,
            remediation_class="code_fix",
            title=f"fix(crp-scan): govern {provider} call in {pathlib.Path(finding.file_path).name}",
            description=(
                f"Route the ungoverned {finding.provider} call at "
                f"`{finding.file_path}:{finding.line}` through the CRP Gateway."
            ),
            diff=diff,
            config_snippet="",
            pr_branch=pr_branch,
            pr_body=pr_body,
            env_vars_required=["CRP_GATEWAY_KEY"],
            doc_links=[
                "https://crprotocol.io/docs/gateway",
                f"https://crprotocol.io/docs/scan/{finding.rule_id.lower()}",
            ],
            verification_command="python -c \"import crp; print('ok')\"",
        )

    def _select_code_template(self, provider: str, finding: ScanFinding) -> str:
        """Select the appropriate template key based on provider and context."""
        if "langchain" in provider or "langchain" in finding.call_expression.lower():
            return "langchain_gateway"
        if "anthropic" in provider or "claude" in finding.call_expression.lower():
            return "anthropic_gateway"
        if "openai" in provider or "gpt" in finding.call_expression.lower():
            return "openai_gateway"
        return "crp_client"

    def _render_code_diff(self, template_key: str, finding: ScanFinding) -> str:
        """Render a ``git apply``-ready unified diff from a template.

        Reads the file at :attr:`finding.file_path`, replaces the line at
        :attr:`finding.line` with the rendered gateway/CRP-client block, and
        returns a unified diff.  If the file cannot be read, falls back to the
        raw replacement block so callers still receive a proposal.
        """
        import difflib
        import re

        call_expr = finding.call_expression
        key_env = "OPENAI_API_KEY"
        env_match = re.search(r'os\.environ\[["\'](\w+)["\']\]', call_expr)
        if env_match:
            key_env = env_match.group(1)

        model_name = "gpt-4o"
        model_match = re.search(r"""model=['"]([\w.-]+)['"]""", call_expr)
        if model_match:
            model_name = model_match.group(1)

        templates: dict[str, str] = {
            "openai_gateway": _TEMPLATE_OPENAI_GATEWAY,
            "anthropic_gateway": _TEMPLATE_ANTHROPIC_GATEWAY,
            "langchain_gateway": _TEMPLATE_LANGCHAIN_GATEWAY,
            "crp_client": _TEMPLATE_CRP_CLIENT,
        }
        raw = templates.get(template_key, _TEMPLATE_CRP_CLIENT)
        try:
            replacement = raw.format_map(
                {
                    "original_key_env": key_env,
                    "model_name": model_name,
                    "original_call": call_expr,
                    "original_call_args": f'"{finding.message[:60]}"',
                }
            )
        except KeyError:
            replacement = raw

        # Ensure the replacement block ends with a newline so it can replace a
        # single source line cleanly.
        if not replacement.endswith("\n"):
            replacement += "\n"

        try:
            original_lines = pathlib.Path(finding.file_path).read_text(
                encoding="utf-8"
            ).splitlines(keepends=True)
        except (OSError, UnicodeDecodeError):
            original_lines = []

        if not original_lines:
            # Fallback: return the raw template so callers still see a proposal.
            return replacement

        line_idx = max(0, min(finding.line - 1, len(original_lines) - 1))
        replacement_lines = replacement.splitlines(keepends=True)
        modified_lines = (
            original_lines[:line_idx]
            + replacement_lines
            + original_lines[line_idx + 1 :]
        )

        return "".join(
            difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{finding.file_path}",
                tofile=f"b/{finding.file_path}",
            )
        )

    # ------------------------------------------------------------------
    # Config fix (§4 of SPEC-036)
    # ------------------------------------------------------------------

    def _build_config_fix(self, finding: ScanFinding) -> RemediationProposal:
        """Build a crp.config.yaml fragment for a missing safety policy."""
        safety_profile = "balanced"
        halt_level = "CRITICAL"
        grounding = 0.70

        if "medical" in finding.message.lower() or "healthcare" in finding.message.lower():
            safety_profile = "medical"
            halt_level = "HIGH"
            grounding = 0.90
        elif "financial" in finding.message.lower():
            safety_profile = "financial"
            halt_level = "HIGH"
            grounding = 0.85

        config_snippet = _CONFIG_FIX_TEMPLATE.format_map(
            {
                "safety_profile": safety_profile,
                "halt_level": halt_level,
                "grounding_threshold": grounding,
            }
        )
        pr_branch = self._pr_branch_name(finding, prefix="config")
        pr_body = (
            f"## CRP Scan — Configuration Fix\n\n"
            f"**Finding:** `{finding.rule_id}` — {finding.message}\n\n"
            f"Adds a `crp.config.yaml` snippet to establish a safety policy for your "
            f"AI calls.  Review and merge to apply governance configuration.\n\n"
            f"```yaml\n{config_snippet}```\n"
        )
        return RemediationProposal(
            proposal_id=self._proposal_id(finding),
            finding=finding,
            remediation_class="config_fix",
            title=f"fix(crp-scan): add safety policy config ({finding.rule_id})",
            description=(
                f"Add a `crp.config.yaml` governance policy for finding {finding.rule_id}."
            ),
            diff="",
            config_snippet=config_snippet,
            pr_branch=pr_branch,
            pr_body=pr_body,
            env_vars_required=[],
            doc_links=["https://crprotocol.io/docs/config"],
            verification_command="crp config validate",
        )

    # ------------------------------------------------------------------
    # Guided fix (§5 of SPEC-036)
    # ------------------------------------------------------------------

    def _build_guided_fix(self, finding: ScanFinding) -> RemediationProposal:
        """Build a checkpoint-style guided task for findings needing judgment."""
        description = textwrap.dedent(f"""\
            This finding requires human judgment to remediate.

            **Finding:** {finding.rule_id} — {finding.message}
            **Location:** {finding.file_path}:{finding.line}

            **Suggested actions:**
            1. Review the AI call at the location above.
            2. Decide whether to:
               - Route it through the CRP Gateway (recommended).
               - Add a crp.config.yaml safety policy.
               - Add a human-in-the-loop Checkpoint around this call.
            3. Apply the chosen fix and re-run `crp scan` to verify.

            See https://crprotocol.io/docs/scan/{finding.rule_id.lower()} for guidance.
        """)
        return RemediationProposal(
            proposal_id=self._proposal_id(finding),
            finding=finding,
            remediation_class="guided_fix",
            title=f"fix(crp-scan): review {finding.rule_id} at {pathlib.Path(finding.file_path).name}",
            description=description,
            diff="",
            config_snippet="",
            pr_branch=self._pr_branch_name(finding, prefix="guided"),
            pr_body=description,
            doc_links=[
                f"https://crprotocol.io/docs/scan/{finding.rule_id.lower()}",
                "https://crprotocol.io/docs/checkpoint",
            ],
            verification_command="crp scan",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _finding_description(self, finding: ScanFinding) -> str:
        return (
            f"An ungoverned `{finding.provider}` call was found at "
            f"`{finding.file_path}:{finding.line}`. "
            f"This call is not routed through CRP — fabrication detection, audit trail, "
            f"and grounding verification are inactive for this call."
        )

    def _pr_branch_name(self, finding: ScanFinding, prefix: str = "crp-fix") -> str:
        """Generate a deterministic, safe PR branch name for a finding."""
        file_slug = pathlib.Path(finding.file_path).stem[:20].replace(" ", "-")
        h = hashlib.sha1(f"{finding.file_path}{finding.line}".encode()).hexdigest()[:6]
        return f"{prefix}/{file_slug}-{finding.rule_id.lower()}-{h}"

    def _proposal_id(self, finding: ScanFinding) -> str:
        h = hashlib.sha256(
            f"{finding.file_path}:{finding.line}:{finding.rule_id}".encode()
        ).hexdigest()[:12]
        return f"rem_{h}"

    def _default_templates_dir(self) -> pathlib.Path:
        return pathlib.Path(__file__).parent / "templates"
