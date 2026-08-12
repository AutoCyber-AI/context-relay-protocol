# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP CLI entry point — ``crp init | dispatch | ingest | status | preview | serve | scan | scan-remediate``.

UNIX-friendly: reads stdin, writes JSON to stdout, pipe-compatible.
Requires the ``click`` package (``pip install crprotocol[cli]``).
"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Any


def _require_click():
    """Import click with a friendly error if missing."""
    try:
        import click
        return click
    except ImportError as exc:
        raise SystemExit(
            "The CRP CLI requires 'click'.  Install with:  pip install crprotocol[cli]"
        ) from exc


# ── Session store (in-memory for CLI lifetime) ──────────────────────────

_sessions: dict[str, dict] = {}


def _get_session(session_id: str) -> dict:
    """Retrieve a live session or exit with error."""
    if session_id not in _sessions:
        sys.stderr.write(f"Error: unknown session '{session_id}'\n")
        raise SystemExit(1)
    return _sessions[session_id]


# ── Scan helpers (used by ``crp scan`` and ``crp scan-remediate``) ───────

def _scan_findings(paths: str, fail_on: str, min_version: str, min_grounding: float) -> list[dict]:
    """Run the CRP regex scanner and return normalized finding dicts.

    This mirrors the logic originally embedded in ``crp scan`` so both
    ``crp scan`` and ``crp scan-remediate`` stay consistent.  ``fail_on`` and
    ``min_grounding`` are accepted for interface parity but do not affect the
    returned list.
    """
    import os
    import re
    from pathlib import Path

    target_paths = [p.strip() for p in paths.split(",") if p.strip()]
    findings: list[dict] = []

    def _already_governed(line: str) -> bool:
        lowered = line.lower()
        return "crp." in lowered or "crprotocol" in lowered or "crp-" in lowered

    # Patterns for ungoverned LLM calls and missing safety controls.
    # Each tuple: (regex, rule_id, message, severity)
    raw_patterns = [
        # Python / JS / TS class instantiations
        (r"(?<!crp\.)\bOpenAI\s*\(", "CRP001", "Direct OpenAI client instantiation without CRP governance", "HIGH"),
        (r"(?<!crp\.)\bAnthropic\s*\(", "CRP001", "Direct Anthropic client instantiation without CRP governance", "HIGH"),
        # Python / JS / TS SDK method calls
        (r"\.chat\.completions\.create\(", "CRP001", "Direct OpenAI chat completions call without CRP governance", "HIGH"),
        (r"\.messages\.create\(", "CRP001", "Direct Anthropic messages call without CRP governance", "HIGH"),
        (r"(?<!crp\.)openai\.Completion\.create\(", "CRP001", "Direct OpenAI Completion call without CRP governance", "HIGH"),
        (r"(?<!crp\.)anthropic\.(Client|Anthropic)\(", "CRP001", "Direct Anthropic client creation without CRP governance", "HIGH"),
        (r"(?<!crp\.)google\.generativeai\.GenerativeModel\(", "CRP001", "Direct Gemini call without CRP governance", "HIGH"),
        (r"(?<!crp\.)\bgenai\.GenerativeModel\(", "CRP001", "Direct Gemini call without CRP governance", "HIGH"),
        # Raw HTTP / fetch / axios to LLM APIs
        (r"requests\.(post|get|put|patch)\([^)]*https://api\.(openai|anthropic|gemini)", "CRP003", "Raw HTTP call to LLM API without governance", "HIGH"),
        (r"fetch\s*\(\s*[\"\']https://api\.(openai|anthropic|gemini)", "CRP003", "Raw HTTP call to LLM API without governance", "HIGH"),
        (r"axios\.(post|get|put|patch)\s*\(\s*[\"\']https://api\.(openai|anthropic|gemini)", "CRP003", "Raw HTTP call to LLM API without governance", "HIGH"),
        (r"curl\s+.*https://api\.(openai|anthropic|gemini)", "CRP003", "Raw shell call to LLM API without governance", "HIGH"),
        # Missing safety headers
        (r"headers\s*=\s*\{[^}]*[\"\'][Xx]-[Aa][Ii]-[^\"\']*[\"\']", "CRP002", "AI request without CRP safety headers", "MEDIUM"),
        # API key access
        (r"os\.(?:environ|getenv)\([\"\']OPENAI_API_KEY[\"\']", "CRP004", "API key accessed directly — consider CRP Gateway for key management", "LOW"),
        (r"os\.environ\.get\([\"\']OPENAI_API_KEY[\"\']", "CRP004", "API key accessed directly — consider CRP Gateway for key management", "LOW"),
        (r"process\.env\.OPENAI_API_KEY", "CRP004", "API key accessed directly — consider CRP Gateway for key management", "LOW"),
        # Hard-coded API key-like strings
        (r"[\"\']sk-[a-zA-Z0-9]{20,}", "CRP006", "Hard-coded API key detected", "HIGH"),
    ]
    patterns = [(re.compile(p), rule, msg, sev) for p, rule, msg, sev in raw_patterns]

    file_extensions = {
        ".py", ".ts", ".js", ".mjs", ".cjs", ".jsx", ".tsx",
        ".java", ".go", ".rs", ".cs", ".rb", ".php", ".swift", ".kt",
    }

    for target in target_paths:
        if not os.path.exists(target):
            continue
        if os.path.isfile(target):
            files = [target]
        else:
            files = []
            for root, _dirs, filenames in os.walk(target):
                # Skip common non-source directories
                if any(part.startswith(".") for part in Path(root).parts):
                    continue
                for name in filenames:
                    ext = os.path.splitext(name)[1]
                    if ext in file_extensions:
                        files.append(os.path.join(root, name))

        for file_path in files:
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line_num, line in enumerate(lines, start=1):
                for compiled, rule_id, message, severity in patterns:
                    match = compiled.search(line)
                    if not match:
                        continue
                    if _already_governed(line):
                        continue
                    column = match.start() + 1
                    suggestion = "Wrap in CRP Client: from crp import Client; client = Client()"
                    if rule_id == "CRP002":
                        suggestion = 'Add CRP safety headers: {"CRP-Safety-Policy": "...", "CRP-Governance": "..."}'
                    elif rule_id == "CRP003":
                        suggestion = "Route through CRP Gateway or wrap the HTTP call with crp.Client()"
                    elif rule_id == "CRP004":
                        suggestion = "Use CRP Gateway key vault or CRP Client secrets binding"
                    elif rule_id == "CRP006":
                        suggestion = "Move API key to environment variables or a secrets manager"
                    findings.append({
                        "rule_id": rule_id,
                        "message": message,
                        "severity": severity,
                        "file": file_path,
                        "line": line_num,
                        "column": column,
                        "suggestion": suggestion,
                    })

    # Version check
    if min_version:
        try:
            from packaging import version as pkg_version

            from crp._version import __version__ as current_version
            if pkg_version.parse(current_version) < pkg_version.parse(min_version):
                findings.insert(0, {
                    "rule_id": "CRP005",
                    "message": f"crprotocol version {current_version} < required {min_version}",
                    "severity": "CRITICAL",
                    "file": "crp",
                    "line": 0,
                    "column": 0,
                    "suggestion": f"pip install --upgrade crprotocol>={min_version}",
                })
        except ImportError:
            pass

    # Deduplicate
    seen = set()
    unique: list[dict] = []
    for finding in findings:
        key = (finding["file"], finding["line"], finding["rule_id"])
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    findings = unique

    # Sort by severity
    severity_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    findings.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
    return findings


def _findings_to_scan_findings(findings: list[dict]) -> list[Any]:
    """Convert raw scanner dicts into RemediationEngine ``ScanFinding`` objects."""
    from pathlib import Path

    from crp.scan.remediation import ScanFinding

    severity_map = {"LOW": "note", "MEDIUM": "warning", "HIGH": "error", "CRITICAL": "error"}

    def _infer_provider(finding: dict) -> str:
        msg = finding.get("message", "")
        if "OpenAI" in msg or "openai" in msg:
            return "openai"
        if "Anthropic" in msg or "Claude" in msg:
            return "anthropic"
        if "Gemini" in msg or "GenerativeModel" in msg or "genai" in msg:
            return "google"
        if "HTTP" in msg:
            return "http"
        return "unknown"

    def _code_context(file_path: str, line: int) -> list[str]:
        try:
            lines = Path(file_path).read_text(encoding="utf-8").splitlines()
            start = max(0, line - 3)
            end = min(len(lines), line + 2)
            return lines[start:end]
        except Exception:
            return []

    def _has_crp_import(file_path: str) -> bool:
        try:
            text = Path(file_path).read_text(encoding="utf-8").lower()
            return "import crp" in text or "from crp" in text
        except Exception:
            return False

    result: list[Any] = []
    for f in findings:
        file_path = Path(f.get("file", "")).as_posix()
        line = f.get("line", 0)
        result.append(ScanFinding(
            rule_id=f.get("rule_id", ""),
            file_path=file_path,
            line=line,
            message=f.get("message", ""),
            severity=severity_map.get(f.get("severity", "LOW"), "note"),
            provider=_infer_provider(f),
            call_expression="",
            code_context=_code_context(file_path, line),
            has_crp_import=_has_crp_import(file_path),
        ))
    return result


def _build_remediation_pr_body(proposals: list[Any]) -> str:
    """Build a markdown PR body for an aggregated remediation PR."""
    lines = [
        "## CRP Scan — Automated Remediation",
        "",
        f"This PR remediates **{len(proposals)}** finding(s) detected by CRP Scan.",
        "",
        "### Findings",
    ]
    for proposal in proposals:
        finding = proposal.finding
        lines.append(
            f"- **{finding.rule_id}** at `{finding.file_path}:{finding.line}` — {finding.message}"
        )
    lines.extend([
        "",
        "### Changes",
        "- Code fixes route ungoverned AI calls through the CRP Gateway.",
        "- Configuration fixes add governance policy to `crp.config.yaml`.",
        "",
        "Please review before merging.",
    ])
    return "\n".join(lines)


# ── Click application ───────────────────────────────────────────────────

def cli() -> None:
    """CRP CLI entry point — delegates to click group."""
    # Fix Windows cp1252 encoding — ensure UTF-8 for Unicode output
    if sys.platform == "win32":
        import io
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name)
            if hasattr(stream, "buffer"):
                wrapped = io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace",
                )
                wrapped.reconfigure(line_buffering=True)
                setattr(sys, stream_name, wrapped)

    click = _require_click()

    # Build the Click group lazily so the module can be imported
    # without click being installed (for embedded library use).
    @click.group(context_settings={"help_option_names": ["-h", "--help"]})
    @click.version_option(package_name="crp")
    def _cli():
        """CRP — Context Relay Protocol CLI."""

    # ── crp init ────────────────────────────────────────────────────

    @_cli.command()
    @click.option("--model", default="custom", help="Model name for diagnostics.")
    @click.option("--context-window", default=128_000, type=int,
                  help="Context window size in tokens.")
    @click.option("--max-output", default=4096, type=int,
                  help="Max output tokens per generation.")
    @click.option("--timeout", default=86400, type=int,
                  help="Session timeout in seconds.")
    @click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
    def init(model, context_window, max_output, timeout, as_json):
        """Create a new CRP session and print the session ID."""
        from crp.cli.startup import run_startup
        from crp.providers.custom import CustomProvider

        # Build a stub provider — real LLM endpoint comes via dispatch
        provider = CustomProvider(
            generate_fn=lambda msgs, **kw: ("", "stop"),
            count_tokens_fn=lambda t: max(1, len(t) // 4),
            context_size=context_window,
            name=model,
            max_output=max_output,
        )

        result, ctx = run_startup(
            provider=provider,
            config_overrides={"session_timeout": timeout},
            skip_health=True,
        )

        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            "id": session_id,
            "provider": provider,
            "config": ctx.get("config"),
            "emitter": ctx.get("emitter"),
            "orchestrator": None,  # lazy
        }

        if as_json:
            click.echo(json.dumps({
                "session_id": session_id,
                "model": model,
                "context_window": context_window,
                "startup_ok": result.ok,
                "startup_ms": round(result.total_ms, 2),
            }))
        else:
            click.echo(session_id)

    # ── crp dispatch ────────────────────────────────────────────────

    @_cli.command()
    @click.option("--session", "session_id", default=None, help="Session ID (auto-creates if omitted).")
    @click.option("--task", required=True, help="Task input text.")
    @click.option("--system", default="You are a helpful assistant.",
                  help="System prompt.")
    @click.option("--json", "as_json", is_flag=True, help="Output JSON report.")
    def dispatch(session_id, task, system, as_json):
        """Dispatch a task to the LLM via CRP and print the output.

        If --session is omitted a one-shot session is created automatically
        so that ``crp dispatch --task "Hello"`` works without ``crp init``.
        """
        if session_id is None:
            # Auto-init a one-shot session
            from crp.cli.startup import run_startup
            from crp.providers.custom import CustomProvider

            provider = CustomProvider(
                generate_fn=lambda msgs, **kw: ("", "stop"),
                count_tokens_fn=lambda t: max(1, len(t) // 4),
                context_size=128_000,
            )
            result, ctx = run_startup(
                provider=provider, skip_health=True,
            )
            session_id = str(uuid.uuid4())
            _sessions[session_id] = {
                "id": session_id,
                "provider": provider,
                "config": ctx.get("config"),
                "emitter": ctx.get("emitter"),
                "orchestrator": None,
            }
        sess = _get_session(session_id)
        orch = _ensure_orchestrator(sess)

        output, report = orch.dispatch(system, task)

        if as_json:
            click.echo(json.dumps({
                "session_id": report.session_id,
                "window_id": report.window_id,
                "output": output,
                "facts_extracted": report.facts_extracted,
            }))
        else:
            click.echo(output)

    # ── crp ingest ──────────────────────────────────────────────────

    @_cli.command()
    @click.option("--session", "session_id", required=True, help="Session ID.")
    @click.option("--label", default="stdin", help="Source label.")
    @click.option("--json", "as_json", is_flag=True, help="Output JSON.")
    @click.argument("file", default="-", type=click.File("r"))
    def ingest(session_id, label, as_json, file):
        """Ingest raw text (file or stdin) into the session."""
        sess = _get_session(session_id)
        orch = _ensure_orchestrator(sess)
        text = file.read()
        result = orch.ingest(text, source_label=label)

        if as_json:
            click.echo(json.dumps({
                "facts_extracted": result.facts_extracted,
                "source_label": result.source_label,
                "fact_ids": result.fact_ids,
            }))
        else:
            click.echo(f"Ingested {result.facts_extracted} facts from '{label}'")

    # ── crp status ──────────────────────────────────────────────────

    @_cli.command()
    @click.option("--session", "session_id", required=True, help="Session ID.")
    def status(session_id):
        """Print session status as JSON."""
        sess = _get_session(session_id)
        orch = _ensure_orchestrator(sess)
        st = orch.session_status()
        click.echo(json.dumps({
            "session_id": st.session_id,
            "windows_completed": st.windows_completed,
            "total_input_tokens": st.total_input_tokens,
            "total_output_tokens": st.total_output_tokens,
            "facts_in_warm_state": st.facts_in_warm_state,
            "overhead_ratio": st.overhead_ratio,
        }, indent=2))

    # ── crp preview ─────────────────────────────────────────────────

    @_cli.command()
    @click.option("--session", "session_id", required=True, help="Session ID.")
    @click.option("--task", required=True, help="Task input text.")
    @click.option("--system", default="You are a helpful assistant.",
                  help="System prompt.")
    def preview(session_id, task, system):
        """Preview envelope without dispatching — prints JSON."""
        sess = _get_session(session_id)
        orch = _ensure_orchestrator(sess)
        ep = orch.preview_envelope(system, task)
        click.echo(json.dumps({
            "total_tokens": ep.total_tokens,
            "envelope_tokens": ep.envelope_tokens,
            "generation_reserve": ep.generation_reserve,
            "facts_included": ep.facts_included,
            "facts_available": ep.facts_available,
            "saturation": round(ep.saturation, 4),
        }, indent=2))

    # ── crp serve (HTTP sidecar for inter-LLM context sharing) ────

    @_cli.command()
    @click.option("--port", default=9470, type=int, help="Port number.")
    @click.option("--bind-all", is_flag=True, default=False,
                  help="Bind to 0.0.0.0 instead of 127.0.0.1. Requires --auth-token unless --allow-unauthenticated is set.")
    @click.option("--auth-token", default=None, help="Bearer token for authentication (strongly recommended).")
    @click.option("--allow-unauthenticated", is_flag=True, default=False,
                  help="Allow running without auth token (NOT recommended for --bind-all).")
    @click.option("--max-sessions", default=64, type=int, help="Maximum concurrent sessions.")
    @click.option("--rate-limit", default=120, type=int, help="Max requests per IP per rate window.")
    def serve(port, bind_all, auth_token, allow_unauthenticated, max_sessions, rate_limit):
        """Start the CRP HTTP sidecar for inter-LLM context sharing.

        The sidecar is OPTIONAL — it is never started automatically.
        It exposes CRP sessions over HTTP, enabling multiple applications
        and LLMs to share extracted knowledge.

        \b
        SECURITY:
          - Binds to 127.0.0.1 (loopback) by default
          - --auth-token enables bearer-token authentication
          - --bind-all requires --auth-token (or explicit --allow-unauthenticated)
          - Per-IP rate limiting (default: 120 req/60s)
          - Session ownership: only the token that created a session can access it
          - 10 MB request body limit
          - No HTTPS — deploy behind a TLS reverse proxy for production

        \b
        ENDPOINTS (all 6 dispatch variants + knowledge sharing):
          POST /sessions                          Create session
          POST /sessions/:id/dispatch             Basic dispatch
          POST /sessions/:id/dispatch/tools       Tool-mediated dispatch
          POST /sessions/:id/dispatch/reflexive   Reflexive dispatch
          POST /sessions/:id/dispatch/progressive Progressive dispatch
          POST /sessions/:id/dispatch/stream-augmented  Stream-augmented
          POST /sessions/:id/dispatch/agentic     Agentic dispatch
          POST /sessions/:id/ingest               Ingest text
          GET  /sessions/:id/facts                Query facts
          POST /sessions/:id/facts/share          SHARE facts between sessions
          POST /sessions/:id/facts/feedback       Boost/penalize/reject facts
          POST /sessions/:id/providers            Register fallback provider
          POST /sessions/:id/estimate             Cost estimation
          GET  /sessions/:id/status               Session status
          GET  /sessions/:id/envelope             Envelope preview
          POST /sessions/:id/close                Close session
          GET  /sessions                          List sessions (owned only)
          GET  /health                            Health check

        The /facts/share endpoint is the core differentiator — it enables
        two LLMs using CRP to share each other's extracted knowledge.
        """
        from crp.cli.sidecar import start_sidecar

        host = "0.0.0.0" if bind_all else "127.0.0.1"

        # Security gate: --bind-all requires auth unless explicitly waived
        if bind_all and not auth_token and not allow_unauthenticated:
            click.echo("ERROR: --bind-all requires --auth-token for security.", err=True)
            click.echo("  Use --allow-unauthenticated to override (NOT recommended).", err=True)
            raise SystemExit(1)

        if bind_all and not auth_token:
            click.echo("WARNING: Binding to 0.0.0.0 WITHOUT authentication!", err=True)
            click.echo("  Any process on the network can access CRP sessions.", err=True)

        click.echo(f"CRP sidecar starting on {host}:{port}")
        click.echo(f"  Auth: {'Bearer token required' if auth_token else 'DISABLED'}")
        click.echo(f"  Max sessions: {max_sessions}")
        click.echo(f"  Rate limit: {rate_limit} req/60s per IP")
        click.echo()
        click.echo("  Dispatch variants: basic, tools, reflexive, progressive, stream-augmented, agentic")
        click.echo("  POST /sessions/:id/facts/share  ← Inter-LLM context sharing")
        click.echo("  POST /sessions/:id/facts/feedback  ← Fact confidence adjustment")
        click.echo("  GET  /health")
        click.echo()

        server = start_sidecar(host=host, port=port, auth_token=auth_token,
                               max_sessions=max_sessions, rate_limit=rate_limit)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            click.echo("\nShutting down sidecar...")
            server.shutdown()

    # ── crp scan ────────────────────────────────────────────────────

    @_cli.command()
    @click.option('--format', 'fmt', default='json', type=click.Choice(['json', 'sarif', 'text']))
    @click.option('--fail-on', default='HIGH', type=click.Choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']))
    @click.option('--paths', default='.', help='Comma-separated paths to scan')
    @click.option('--min-version', default='', help='Minimum crprotocol version to enforce')
    @click.option('--sarif', default=None, type=click.Path(), help='Write SARIF output to a file')
    @click.option('--summary', default=None, type=click.Path(), help='Write markdown summary to a file')
    @click.option('--report-only', is_flag=True, help='Report findings but always exit 0')
    @click.option('--min-grounding', default=0.0, type=float, help='Minimum grounding score (advisory)')
    def scan(fmt, fail_on, paths, min_version, sarif, summary, report_only, min_grounding):
        """Scan source code for ungoverned LLM calls and missing safety policies."""
        from pathlib import Path

        severity_rank = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        min_rank = severity_rank.get(fail_on, 3)
        findings = _scan_findings(paths, fail_on, min_version, min_grounding)

        # Build SARIF document once for optional file + stdout
        def _build_sarif():
            return {
                '$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
                'version': '2.1.0',
                'runs': [{
                    'tool': {'driver': {'name': 'CRP Scan', 'informationUri': 'https://crprotocol.io'}},
                    'results': [{
                        'ruleId': f['rule_id'],
                        'message': {'text': f['message']},
                        'level': f['severity'].lower(),
                        'locations': [{
                            'physicalLocation': {
                                'artifactLocation': {'uri': f['file']},
                                'region': {'startLine': f['line'], 'startColumn': f['column']},
                            }
                        }],
                    } for f in findings],
                }],
            }

        if fmt == 'json':
            click.echo(json.dumps(findings))
        elif fmt == 'sarif':
            click.echo(json.dumps(_build_sarif(), indent=2))
        else:
            for f in findings:
                click.echo(f"{f['rule_id']}: {f['severity']} — {f['message']} ({f['file']}:{f['line']})")

        if sarif:
            Path(sarif).write_text(json.dumps(_build_sarif(), indent=2), encoding='utf-8')

        if summary:
            summary_lines = ['# CRP Scan Summary\n', '| Severity | Count |', '|----------|-------|']
            counts = {sev: 0 for sev in severity_rank}
            for f in findings:
                counts[f['severity']] = counts.get(f['severity'], 0) + 1
            for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                summary_lines.append(f'| {sev} | {counts.get(sev, 0)} |')
            summary_lines.append(f'\n**Total findings:** {len(findings)}\n')
            if findings:
                summary_lines.append('## Findings\n')
                for f in findings:
                    summary_lines.append(f"- **{f['rule_id']}** ({f['severity']}) — {f['message']} at `{f['file']}:{f['line']}`")
            Path(summary).write_text('\n'.join(summary_lines), encoding='utf-8')

        # Advisory: min-grounding is accepted but not enforced by the regex scanner.
        if min_grounding:
            pass

        # Exit non-zero if any finding meets fail-on threshold
        max_rank = max((severity_rank.get(f['severity'], 0) for f in findings), default=0)
        if not report_only and max_rank >= min_rank:
            raise SystemExit(1)

    # ── crp scan-remediate ──────────────────────────────────────────

    @_cli.command("scan-remediate")
    @click.option("--paths", default=".", help="Comma-separated paths to scan")
    @click.option("--fail-on", default="HIGH", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))
    @click.option("--repo", default=None, help="Repository slug (owner/repo) for PR mode")
    @click.option("--branch", default=None, help="Remediation branch to create")
    @click.option("--base-branch", default="main", help="Base branch to branch from")
    @click.option("--gh-token", default=None, envvar="GH_TOKEN", help="GitHub token for push/PR")
    def scan_remediate(paths, fail_on, repo, branch, base_branch, gh_token):
        """Scan for CRP findings and produce a remediation plan or open a PR.

        Without --repo and --branch, prints a JSON remediation plan and exits 0.
        With --repo and --branch, creates a dedicated branch, applies code/config
        fixes, pushes, and opens a pull request.  NEVER commits to the base branch.
        """
        import os
        import subprocess
        import tempfile
        from pathlib import Path

        from crp.scan.remediation import RemediationEngine

        raw_findings = _scan_findings(paths, fail_on, "", 0.0)
        scan_findings = _findings_to_scan_findings(raw_findings)
        engine = RemediationEngine()
        proposals = engine.proposals_for_repo(scan_findings)

        plan: dict[str, Any] = {
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "rule_id": p.finding.rule_id,
                    "file_path": p.finding.file_path,
                    "line": p.finding.line,
                    "remediation_class": p.remediation_class,
                    "title": p.title,
                    "description": p.description,
                    "diff": p.diff,
                    "config_snippet": p.config_snippet,
                    "pr_branch": p.pr_branch,
                }
                for p in proposals
            ],
        }

        if not proposals:
            click.echo(json.dumps(plan, indent=2))
            return

        if not repo or not branch:
            click.echo(json.dumps(plan, indent=2))
            return

        if not gh_token:
            click.echo("ERROR: --gh-token (or GH_TOKEN env) is required for PR mode.", err=True)
            raise SystemExit(1)

        repo_root = Path(".")

        def _run_git(args, check=True):
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if check and result.returncode != 0:
                click.echo(f"ERROR: git {' '.join(args)} failed: {result.stderr.strip()}", err=True)
                raise SystemExit(1)
            return result

        # Configure git identity
        _run_git(["config", "user.name", "CRP Scan Bot"])
        _run_git(["config", "user.email", "crp-scan@crprotocol.io"])

        # Create dedicated remediation branch from base branch
        _run_git(["checkout", "-b", branch, base_branch])

        # Apply proposals: code fixes via git apply, config fixes via crp.config.yaml
        config_snippets = []
        for proposal in proposals:
            if proposal.remediation_class == "code_fix" and proposal.diff:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".diff", delete=False, encoding="utf-8"
                ) as diff_file:
                    diff_file.write(proposal.diff)
                    diff_path = diff_file.name
                try:
                    check = _run_git(["apply", "--check", diff_path], check=False)
                    if check.returncode == 0:
                        _run_git(["apply", diff_path])
                        _run_git(["add", proposal.finding.file_path])
                    else:
                        click.echo(
                            f"WARNING: git apply failed for {proposal.finding.file_path}: "
                            f"{check.stderr.strip()}",
                            err=True,
                        )
                finally:
                    os.unlink(diff_path)
            elif proposal.remediation_class == "config_fix" and proposal.config_snippet:
                config_snippets.append(proposal.config_snippet)

        if config_snippets:
            config_path = repo_root / "crp.config.yaml"
            existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
            with open(config_path, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                for snippet in config_snippets:
                    f.write(snippet)
                    if not snippet.endswith("\n"):
                        f.write("\n")
            _run_git(["add", "crp.config.yaml"])

        # Verify something was staged
        status = _run_git(["diff", "--cached", "--quiet"], check=False)
        if status.returncode == 0:
            click.echo("No changes to commit — remediation already applied or diffs failed.")
            click.echo(json.dumps(plan, indent=2))
            return

        # Commit and push to dedicated branch
        commit_message = (
            f"fix(crp-scan): automated remediation for {len(proposals)} finding(s)\n\n"
            "Generated by CRP Scan auto-remediation."
        )
        _run_git(["commit", "-m", commit_message])

        remote_url = f"https://x-access-token:{gh_token}@github.com/{repo}.git"
        _run_git(["remote", "set-url", "origin", remote_url])
        _run_git(["push", "origin", branch])

        # Open PR via GitHub CLI
        pr_title = f"fix(crp-scan): automated remediation ({len(proposals)} finding(s))"
        pr_body = _build_remediation_pr_body(proposals)
        env = os.environ.copy()
        env["GH_TOKEN"] = gh_token
        pr_result = subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", repo,
                "--base", base_branch,
                "--head", branch,
                "--title", pr_title,
                "--body", pr_body,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if pr_result.returncode != 0:
            click.echo(f"ERROR: gh pr create failed: {pr_result.stderr.strip()}", err=True)
            raise SystemExit(1)

        pr_url = pr_result.stdout.strip()
        click.echo(pr_url)
        Path("/tmp/crp_remediation_pr_url").write_text(pr_url, encoding="utf-8")
        plan["pr_url"] = pr_url

    # ── crp download-models ─────────────────────────────────────────

    @_cli.command("download-models")
    @click.option("--model", "which", default="all",
                  type=click.Choice(["intent", "prm", "safety", "embeddings", "all"]),
                  help="Which model to download (default: all).")
    @click.option("--model-dir", default=None, envvar="CRP_MODEL_DIR",
                  help="Target directory (default: $CRP_MODEL_DIR or ./crp_models).")
    def download_models(which, model_dir):
        """Download CRP ML models from Hugging Face (CRPv6 Phase A)."""
        from crp.ml.downloader import download_all, download_model

        key_map = {
            "intent": "crp.isa.intent",
            "prm": "crp.vr.prm",
            "safety": "crp.security.safety",
            "embeddings": "crp.embeddings.default",
        }
        try:
            if which == "all":
                results = download_all(model_dir)
            else:
                results = {key_map[which]: download_model(key_map[which], model_dir)}
        except ImportError:
            click.echo(
                "ERROR: huggingface_hub is required — pip install huggingface-hub",
                err=True,
            )
            raise SystemExit(1) from None
        for key, path in results.items():
            click.echo(f"{key} -> {path}")

    _cli(standalone_mode=True)


# ── Helpers ─────────────────────────────────────────────────────────────

def _ensure_orchestrator(sess: dict) -> Any:  # type: ignore[type-arg]
    """Lazily build the orchestrator for this session."""
    if sess["orchestrator"] is None:
        from crp.core.orchestrator import CRPOrchestrator

        orch = CRPOrchestrator(
            provider=sess["provider"],
            config=sess["config"],
        )
        sess["orchestrator"] = orch
    return sess["orchestrator"]
