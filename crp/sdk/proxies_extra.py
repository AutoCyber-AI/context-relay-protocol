# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Additional curated namespace proxies for product-facing CRP subsystems.

These proxies extend the progressive SDK surface with typed accessors for
Gateway, HTTP headers, observability, policy, Scan, and Comply.  Each proxy
receives the orchestrator instance and uses lazy imports to avoid heavy
dependencies and circular imports.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("crp.sdk.proxies_extra")


# ── Gateway ─────────────────────────────────────────────────────────────────


class _GatewayProxy:
    """CRP Gateway proxy (SPEC-016).

    Exposes lightweight accessors for Gateway session state, provider routing,
    and the per-tenant key vault.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def session(self) -> Any:
        """Return a fresh ``GatewaySession`` instance.

        The session is independent of the SDK orchestrator; identifiers default
        to empty / ``sdk`` values suitable for local exploration.

        Returns:
            GatewaySession instance.
        """
        from crp.gateway.api import GatewaySession

        session_id = ""
        tenant_id = "sdk"
        orch = self._orchestrator
        if orch is not None:
            session_id = getattr(getattr(orch, "_session", None), "session_id", "") or session_id
            tenant_id = getattr(getattr(orch, "_session", None), "tenant_id", tenant_id) or tenant_id
        return GatewaySession(session_id=session_id, tenant_id=tenant_id)

    def router(self) -> Any:
        """Return the orchestrator's Gateway router when present.

        Falls back to a default ``ProviderRouter`` if the orchestrator has no
        gateway router attached.

        Returns:
            ProviderRouter instance.
        """
        from crp.gateway.router import ProviderRouter

        existing = getattr(self._orchestrator, "_gateway_router", None)
        if existing is not None:
            return existing
        return ProviderRouter()

    def key_vault(self) -> Any:
        """Return a fresh ``KeyVault`` instance.

        Returns:
            KeyVault instance.
        """
        from crp.gateway.key_vault import KeyVault

        return KeyVault()


# ── Headers ─────────────────────────────────────────────────────────────────


class _HeadersProxy:
    """CRP HTTP header surface proxy (SPEC-002).

    Exposes header emission, parsing, canonical-name listing, and halt
    detection without requiring manual imports.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def emit(self, headers: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, str]:
        """Emit CRP response headers from a mapping of analysis values.

        Args:
            headers: Optional dict of header inputs forwarded as keyword args.
            **kwargs: Additional header inputs (e.g. ``session_id``, ``window``).

        Returns:
            Dict of canonical ``CRP-*`` header names to string values.
        """
        from crp.headers.emit import emit_headers

        merged = dict(headers or {})
        merged.update(kwargs)
        return emit_headers(**merged)

    def parse(self, header_string: Any) -> Any:
        """Parse inbound CRP request headers.

        Args:
            header_string: A mapping of headers, a raw header string, or a
                previously parsed ``RequestDirectives`` object.

        Returns:
            RequestDirectives (or a plain dict fallback).
        """
        from crp.headers import parse as parse_mod

        # Prefer an exact parse_headers function if one exists.
        if hasattr(parse_mod, "parse_headers"):
            return parse_mod.parse_headers(header_string)

        from crp.headers.parse import parse_request_headers

        if isinstance(header_string, dict):
            return parse_request_headers(header_string)

        if isinstance(header_string, str):
            parsed: dict[str, str] = {}
            for line in header_string.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                parsed[key.strip()] = value.strip()
            return parse_request_headers(parsed)

        # Already parsed object
        return header_string

    def names(self) -> list[str]:
        """Return the list of canonical CRP header-name constants.

        Returns:
            Sorted list of canonical header-name strings.
        """
        from crp.headers import names as names_mod

        return sorted(
            value
            for name, value in vars(names_mod).items()
            if isinstance(value, str) and name.isupper() and value.startswith("CRP-")
        )

    def should_halt(self, headers: dict[str, str]) -> bool:
        """Return ``True`` if the headers indicate a safety halt.

        Args:
            headers: Mapping of CRP response headers.

        Returns:
            Boolean halt signal.
        """
        from crp.headers import halt as halt_mod

        if hasattr(halt_mod, "should_halt"):
            return halt_mod.should_halt(headers)

        # Graceful fallback: detect explicit halt header or critical risk.
        return (
            headers.get("CRP-Safety-Halt") in {"1", "true", "yes"}
            or headers.get("CRP-Risk-Level", "").upper() == "CRITICAL"
        )


# ── Observability ───────────────────────────────────────────────────────────


class _ObservabilityProxy:
    """Observability proxy (§8.9, §9).

    Exposes audit logs, event emission, metrics, quality monitoring,
    per-window telemetry, and structured logging.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def audit_events(self) -> Any:
        """Return an ``AuditLogger`` instance.

        If the orchestrator exposes a compatible audit trail, that object is
        returned; otherwise a fresh ``AuditLogger`` is created.

        Returns:
            AuditLogger or orchestrator audit trail.
        """
        from crp.observability.audit import AuditLog

        orch = self._orchestrator
        if orch is not None:
            security = getattr(orch, "_security", None)
            if security is not None:
                trail = getattr(security, "compliance_audit", None)
                if trail is not None:
                    return trail
        return AuditLog()

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> Any:
        """Emit a ``CRPEvent`` through the orchestrator event bus when present.

        Args:
            event_type: Canonical event type string.
            payload: Event data dict.

        Returns:
            The emitted ``CRPEvent`` instance.
        """
        from crp.observability.events import CRPEvent

        event = CRPEvent(event_type=event_type, data=payload or {})
        orch = self._orchestrator
        if orch is not None:
            emitter = getattr(orch, "_emitter", None)
            if emitter is not None and hasattr(emitter, "emit"):
                try:
                    emitter.emit(event_type, payload or {})
                except Exception as exc:
                    logger.debug("Could not emit event through orchestrator: %s", exc)
        return event

    def metrics(self) -> Any:
        """Return a ``MetricsExporter`` instance.

        Returns:
            MetricsExporter instance.
        """
        from crp.observability.metrics import MetricsExporter

        return MetricsExporter()

    def quality(self) -> Any:
        """Return a quality monitor instance.

        Returns ``QualityMonitor`` if available; otherwise falls back to
        ``QualityReporter``.

        Returns:
            Quality reporter/monitor instance.
        """
        from crp.observability import quality as quality_mod

        if hasattr(quality_mod, "QualityMonitor"):
            return quality_mod.QualityMonitor()
        return quality_mod.QualityReporter()

    def telemetry(self, window_id: str = "") -> Any:
        """Return a ``WindowTelemetry`` record for the current session/window.

        Args:
            window_id: Window identifier. Defaults to empty string.

        Returns:
            WindowTelemetry instance.
        """
        from crp.observability.telemetry import WindowTelemetry

        session_id = ""
        orch = self._orchestrator
        if orch is not None:
            session_id = getattr(getattr(orch, "_session", None), "session_id", "") or session_id
        return WindowTelemetry(session_id=session_id, window_id=window_id)

    def structured_log(self, record: Any) -> str:
        """Format a log record as structured JSON.

        Args:
            record: A ``logging.LogRecord`` or dict describing the event.

        Returns:
            JSON-formatted log line.
        """
        import logging

        from crp.observability.structured_logging import StructuredFormatter

        formatter = StructuredFormatter()
        if isinstance(record, logging.LogRecord):
            return formatter.format(record)

        # Build a minimal LogRecord from a dict for formatting.
        msg = record.get("msg", "") if isinstance(record, dict) else str(record)
        log_record = logging.LogRecord(
            name=record.get("name", "crp.sdk.observability") if isinstance(record, dict) else "crp.sdk.observability",
            level=record.get("level", logging.INFO) if isinstance(record, dict) else logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        return formatter.format(log_record)


# ── Policy ──────────────────────────────────────────────────────────────────


class _PolicyProxy:
    """Safety policy proxy (SPEC-006).

    Exposes policy enforcement, named profiles, violation reporting, and
    risk-level lookups.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def enforce(self, policy_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Evaluate ``policy_text`` against ``context``.

        Args:
            policy_text: Policy directive string (CSP-inspired syntax).
            context: Optional dict of signals (e.g. ``risk_level``, ``grounding_pct``).

        Returns:
            Policy decision as a plain dict.
        """
        from crp.policy.enforce import SafetySignals, enforce_policy, extract_signals
        from crp.policy.grammar import parse_policy
        from crp.policy.profiles import resolve_policy

        try:
            policy = resolve_policy(policy_text)
        except Exception:
            policy = parse_policy(policy_text)

        signals = SafetySignals()
        if context:
            signals = extract_signals(**context)
            if context.get("risk_level"):
                from crp.policy.model import RiskLevel

                try:
                    signals.risk_level = RiskLevel[str(context["risk_level"]).upper()]
                except KeyError:
                    pass
            if "grounding_pct" in context:
                signals.grounding_pct = float(context["grounding_pct"])
            if "fabrication_count" in context:
                signals.fabrication_count = int(context["fabrication_count"])

        decision = enforce_policy(policy, signals)
        return {
            "action": decision.action.value,
            "halted": decision.halted,
            "violations": [
                {
                    "directive": v.directive,
                    "type": v.violation_type.value,
                    "action": v.action.value,
                }
                for v in decision.violations
            ],
        }

    def profiles(self) -> dict[str, str]:
        """Return the dict of named policy-profile directive strings.

        Returns:
            Mapping from profile name to directive string.
        """
        from crp.policy import profiles as profiles_mod

        if hasattr(profiles_mod, "DEFAULT_PROFILES"):
            return dict(profiles_mod.DEFAULT_PROFILES)
        return dict(profiles_mod.PROFILES)

    def report(self, violations: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a violation-report dict from raw violations.

        Args:
            violations: List of violation dicts.

        Returns:
            Violation report dict.
        """
        from crp.policy.report import ViolationReport

        return ViolationReport(violations=violations).to_dict()

    def risk_level(self, level: str) -> Any:
        """Return the ``RiskLevel`` enum member for ``level``.

        Args:
            level: One of ``LOW``, ``MEDIUM``, ``HIGH``, ``CRITICAL``.

        Returns:
            RiskLevel enum member.
        """
        from crp.policy.model import RiskLevel

        return RiskLevel[level.upper()]


# ── Scan ────────────────────────────────────────────────────────────────────


class CRPScanGitHubApp:
    """Lazy wrapper around ``crp.scan.github_app.GithubAppClient``.

    The underlying client is instantiated only when a method that requires
    GitHub credentials is called, keeping ``client.scan.github_app()``
    side-effect-free.
    """

    def __init__(self) -> None:
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Return a configured GithubAppClient, raising if env is missing."""
        if self._client is None:
            from crp.scan.github_app import GithubAppClient

            self._client = GithubAppClient.from_env()
        return self._client

    def installation_token(self, installation_id: str | int) -> str:
        """Mint a short-lived installation access token."""
        return self._ensure_client().installation_token(installation_id)

    def list_repos(self, installation_id: str | int) -> list[dict[str, Any]]:
        """List repositories accessible to the installation."""
        return self._ensure_client().list_repos(installation_id)

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
        """Open a remediation pull request (always to a dedicated branch)."""
        return self._ensure_client().open_remediation_pr(
            installation_id, owner, repo, base_branch, file_changes, pr_title, pr_body
        )


class _ScanProxy:
    """CRP Scan proxy (SPEC-013, SPEC-036, SPEC-039, SPEC-048).

    Exposes the GitHub App client, remediation planning, and semantic code
    ingestion.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def github_app(self) -> Any:
        """Return the GitHub App client for scan remediations.

        Returns:
            CRPScanGitHubApp wrapper instance.
        """
        try:
            from crp.scan.github_app import CRPScanGitHubApp as _RealApp

            return _RealApp()
        except ImportError:
            return CRPScanGitHubApp()

    def remediation(self, advisory: dict[str, Any] | str) -> Any:
        """Plan a remediation for a scan advisory.

        Args:
            advisory: Either a dict describing a finding or a short message.

        Returns:
            RemediationProposal instance.
        """
        from crp.scan.remediation import RemediationEngine, ScanFinding

        engine = RemediationEngine()

        if isinstance(advisory, dict):
            finding = ScanFinding(
                rule_id=advisory.get("rule_id", "CRP001"),
                file_path=advisory.get("file_path", ""),
                line=advisory.get("line", 0),
                message=advisory.get("message", ""),
                severity=advisory.get("severity", "warning"),
                provider=advisory.get("provider", "openai"),
                call_expression=advisory.get("call_expression", ""),
                code_context=advisory.get("code_context", []),
                has_crp_import=advisory.get("has_crp_import", False),
            )
        else:
            finding = ScanFinding(
                rule_id="CRP001",
                file_path="",
                line=0,
                message=str(advisory),
                severity="warning",
                provider="openai",
            )

        return engine.propose_fix(finding)

    def ingest_code(self, text: str) -> Any:
        """Add ``text`` as a fact node to a ``CodeGraph``.

        Args:
            text: Arbitrary text to store as a code fact.

        Returns:
            The fact_id of the created fact.
        """
        from crp.scan.semantic_ingestion import CodeFact, CodeGraph

        graph = CodeGraph(repo_path="sdk://scratch")
        fact = CodeFact(
            fact_id="sdk_scratch_001",
            file_path="sdk://scratch",
            line=1,
            entity_type="text",
            name="scratch_fact",
            content=text,
        )
        graph.add_fact(fact)
        return fact.fact_id


# ── Comply ──────────────────────────────────────────────────────────────────


class ComplyGatewayClient:
    """Lightweight adapter exposing Comply Gateway integration helpers.

    Wraps the functions in ``crp.comply.gateway_client`` so the SDK surface
    returns a stable object rather than requiring manual imports.
    """

    def subscribe_to_audit_stream(self, events: list[dict[str, Any]], tenant_id: str) -> None:
        """Stream audit events into Comply evidence storage."""
        from crp.comply.gateway_client import stream_audit_events

        stream_audit_events(events, tenant_id)

    def get_evidence_pack(self, tenant_id: str, period: str | None = None) -> dict[str, Any]:
        """Return an EU AI Act evidence pack for ``tenant_id``."""
        from crp.comply.gateway_client import get_evidence_pack

        return get_evidence_pack(tenant_id, period)

    def map_to_regulation(self, event_type: str) -> list[str]:
        """Map a Gateway audit event type to EU AI Act article citations."""
        from crp.comply.gateway_client import map_to_regulation

        return map_to_regulation(event_type)


class _ComplyProxy:
    """CRP Comply proxy (SPEC-040, SPEC-042, SPEC-047, SPEC-048).

    Exposes the Gateway client, quota gate, no-code governance translator,
    and billing webhook helpers.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def gateway_client(self) -> Any:
        """Return a Comply Gateway client adapter.

        Returns:
            ComplyGatewayClient instance (or the real class if available).
        """
        try:
            from crp.comply.gateway_client import ComplyGatewayClient as RealClient

            return RealClient()
        except ImportError:
            return ComplyGatewayClient()

    def quota_gate(self, headers: Any) -> dict[str, Any]:
        """Check whether ``headers`` pass the Comply quota gate.

        Args:
            headers: Either an org identifier string or a header mapping
                containing ``x-org-id``, ``crp-org-id``, or ``org_id``.

        Returns:
            Quota gate result dict.
        """
        from crp.comply.quota_gate import QuotaGate

        org_id = headers
        if isinstance(headers, dict):
            for key in ("x-org-id", "X-Org-Id", "crp-org-id", "CRP-Org-Id", "org_id", "orgId"):
                if key in headers:
                    org_id = headers[key]
                    break
            if isinstance(org_id, dict):
                org_id = ""
        return QuotaGate().check(str(org_id) if org_id else "")

    def no_code(self, rule: dict[str, Any] | str) -> dict[str, Any]:
        """Translate a no-code ``rule`` into validated CRP intent.

        Args:
            rule: Structured intent dict or a short text rule.

        Returns:
            Validated intent result dict.
        """
        from crp.comply.no_code import NoCodeTranslatorError, express_requirement

        intent: dict[str, Any]
        if isinstance(rule, dict):
            intent = rule
        else:
            # Minimal text-to-intent heuristic for exploration.
            text = str(rule).lower()
            intent = {
                "prevent_hallucinations": "hallucination" in text or "prevent" in text,
                "require_grounding": 0.75 if "ground" in text else None,
                "halt_on_critical": "critical" in text or "halt" in text,
            }
            intent = {k: v for k, v in intent.items() if v is not None}

        try:
            return express_requirement(intent)
        except NoCodeTranslatorError as exc:
            return {"valid": False, "error": str(exc), "capabilities": [], "settings": {}}

    def billing_webhook(self, payload: Any) -> dict[str, Any]:
        """Process a Stripe billing webhook payload.

        Args:
            payload: Raw webhook bytes, a dict, or a JSON string.

        Returns:
            Webhook handler result dict.
        """
        from crp.comply.billing import webhook as webhook_mod

        if hasattr(webhook_mod, "handle_webhook"):
            return webhook_mod.handle_webhook(payload)

        from crp.comply.billing.webhook import StripeWebhookHandler

        if isinstance(payload, dict):
            import json

            payload = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")

        try:
            handler = StripeWebhookHandler()
            return handler.process(payload, sig_header="")
        except RuntimeError as exc:
            return {"error": str(exc), "status": 400}
