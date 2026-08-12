# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Gateway — 22-step OpenAI-compatible request lifecycle.

Implements the full governance pipeline defined in CRP-SPEC-016 and
CRP-GATEWAY-BLUEPRINT.md.  The 22 steps are grouped into four phases:

  Inbound (1–5):    TLS, auth, rate-limit, quota, parse
  Governance prep (6–9):  session, safety policy, context mode, injection scan
  Execution (10–12):  envelope build / STL, header strip, provider dispatch
  Governance analysis (13–18): DPE, safety enforcement, CSO, HMAC, state update
  Outbound (19–22): emit headers, audit stream, re-issue token, return

CRITICAL INVARIANT — Axiom 4:
  Step 11 strips ALL CRP-* headers from the outbound provider request.
  NO CRP-* header may reach the LLM provider.  This is enforced by a hard
  allowlist filter tested in ``tests/test_gateway.py``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from typing import Any

from crp.agent.budget import AgentSafetyBudget
from crp.headers.emit import emit_headers
from crp.policy.enforce import EnforcementAction, SafetySignals, enforce_policy
from crp.policy.grammar import PolicySyntaxError, parse_policy
from crp.policy.model import RiskLevel, SafetyPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard allowlist of headers we forward to the LLM provider.
# EVERYTHING not in this list is stripped (Axiom 4).
_PROVIDER_HEADER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "authorization",
        "content-type",
        "accept",
        "user-agent",
        "x-request-id",
        "anthropic-version",
        "anthropic-beta",
    }
)

HTTP_451_REASON = "Unavailable For Legal Reasons — CRP Safety Halt"

# Built-in safety profiles mapped to CRP-Safety-Policy directive strings.
_SAFETY_PROFILES: dict[str, str] = {
    "strict": (
        "default-src context; halt-on HIGH; block-ungrounded; block-mixed; "
        "require-grounding 0.80; block-fabrication"
    ),
    "balanced": (
        "default-src context parametric; halt-on CRITICAL; warn-on HIGH; "
        "require-grounding 0.60"
    ),
    "permissive": (
        "default-src context parametric; halt-on CRITICAL; warn-on MEDIUM"
    ),
    "zero-ckf": "default-src parametric; halt-on CRITICAL",
}


# ---------------------------------------------------------------------------
# Data models (zero external deps)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ChatMessage:
    """A single message in a chat completion request (§2.1 of SPEC-016)."""

    role: str
    content: str
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the message as an OpenAI-compatible dict.

        Returns:
            Dict with ``role``, ``content``, and optional ``name`` fields.
        """
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatMessage:
        """Create a new instance from a dictionary.

            Args:
                d (dict[str, Any]): The d value.

            Returns:
                ``ChatMessage``.
        """
        return cls(role=d["role"], content=d.get("content", ""), name=d.get("name"))


@dataclasses.dataclass
class ChatRequest:
    """Parsed inbound /v1/chat/completions request."""

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    # OpenAI-compatible optional fields
    tools: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    tool_choice: Any = None
    response_format: dict[str, Any] | None = None
    # GBNF grammar for llama.cpp constrained decoding (SPEC-054)
    grammar: str | None = None
    # CRP-native fields extracted from headers
    crp_session_token: str | None = None
    crp_safety_profile: str | None = None
    crp_safety_policy: str | None = None
    crp_context_mode: str | None = None
    crp_depth: str = "standard"
    crp_verification_relay: bool = False
    # Resolved at step 2
    tenant_id: str | None = None
    api_key: str | None = None

    @classmethod
    def from_body(cls, body: dict[str, Any], headers: dict[str, str]) -> ChatRequest:
        """Parse from a raw request dict + header map."""
        messages = [ChatMessage.from_dict(m) for m in body.get("messages", [])]
        return cls(
            model=body.get("model", "gpt-4o"),
            messages=messages,
            stream=bool(body.get("stream", False)),
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens"),
            tools=list(body.get("tools", [])),
            tool_choice=body.get("tool_choice"),
            response_format=body.get("response_format"),
            crp_session_token=headers.get("crp-session-token")
            or headers.get("CRP-Session-Token"),
            crp_safety_profile=headers.get("crp-safety-profile")
            or headers.get("CRP-Safety-Profile"),
            crp_safety_policy=headers.get("crp-safety-policy")
            or headers.get("CRP-Safety-Policy"),
            crp_context_mode=headers.get("crp-context-mode")
            or headers.get("CRP-Context-Mode"),
            crp_depth=_first_header(headers, "crp-depth", "standard"),
            crp_verification_relay=_truthy_header(headers, "crp-verification-relay"),
            api_key=_extract_bearer(headers),
        )


def _extract_bearer(headers: dict[str, str]) -> str | None:
    raw = headers.get("authorization") or headers.get("Authorization", "")
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return None


def _first_header(headers: dict[str, str], name: str, default: str) -> str:
    """Return the first matching lowercase or canonical header value."""
    return headers.get(name.lower()) or headers.get(_canonical(name), default)


def _truthy_header(headers: dict[str, str], name: str) -> bool:
    """Return True if the named header is present and truthy."""
    value = _first_header(headers, name, "")
    return value.lower() in {"1", "true", "yes", "on"}


def _canonical(name: str) -> str:
    """Convert ``crp-foo-bar`` to ``CRP-Foo-Bar``."""
    return "-".join(part.capitalize() for part in name.split("-"))


@dataclasses.dataclass
class GatewaySession:
    """Lightweight in-process session state for one request lifecycle."""

    session_id: str
    tenant_id: str
    window_number: int = 0
    safety_budget: float = 1.0
    context_mode: str = "auto"
    safety_profile: str = "balanced"
    cso_ref: str = ""
    coverage_set_hash: str = ""
    hmac_chain_tip: str = ""
    completed_sections: list[str] = dataclasses.field(default_factory=list)
    # Audit events accumulated during this request
    audit_events: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def record_audit(self, event_type: str, data: dict[str, Any]) -> None:
        """Append a timestamped audit event to this session.

        Args:
            event_type: Category of the audit event.
            data: Additional event fields to record.
        """
        self.audit_events.append(
            {
                "event_type": event_type,
                "session_id": self.session_id,
                "window": self.window_number,
                "ts": time.time(),
                **data,
            }
        )


@dataclasses.dataclass
class ProviderResponse:
    """Normalised response from any provider."""

    content: str
    model: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class DPEReport:
    """Lightweight DPE analysis result (SPEC-005)."""

    risk_level: str = "LOW"  # LOW | MEDIUM | HIGH | CRITICAL
    grounded: bool = True
    fabrication_count: int = 0
    contradiction_count: int = 0
    halt_reason: str = ""
    coverage_score: float = 0.0
    chain_valid: bool = True
    verification_ratio: float = 1.0

    @property
    def should_halt(self) -> bool:
        """Return whether this object should halt."""
        return self.risk_level == "CRITICAL"


@dataclasses.dataclass
class HaltResponse:
    """HTTP 451 halt body (SPEC-033 §3.1, SPEC-016 §14)."""

    status_code: int = 451
    reason: str = HTTP_451_REASON
    halt_code: str = ""
    session_id: str = ""
    audit_ref: str = ""

    def to_body(self) -> dict[str, Any]:
        """Build the response body for an HTTP 451 safety halt.

        Returns:
            Dict containing the public error details and CRP audit reference.
        """
        return {
            "error": {
                "code": self.halt_code or "safety_halt",
                "message": self.reason,
                "type": "crp_safety_halt",
            },
            "crp": {
                "session_id": self.session_id,
                "audit_ref": self.audit_ref,
            },
        }


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def _step01_05_parse(
    body: dict[str, Any],
    headers: dict[str, str],
    rate_limit_store: dict[str, Any] | None = None,
    quota_store: dict[str, Any] | None = None,
) -> ChatRequest:
    """Steps 1–5: parse, auth, rate-limit, quota (§1 of blueprint)."""
    request = ChatRequest.from_body(body, headers)

    # Step 3 — rate-limit (advisory: log and continue if no store provided)
    if rate_limit_store is not None:
        key_bucket = rate_limit_store.get(request.api_key or "anon", {})
        if key_bucket.get("exceeded"):
            raise _RateLimitExceeded(f"Rate limit exceeded for key {request.api_key!r}")

    # Step 4 — quota (advisory: log and continue if no store provided)
    if quota_store is not None:
        quota = quota_store.get(request.tenant_id or "anon", {})
        if quota.get("exhausted"):
            raise _QuotaExhausted(f"Quota exhausted for tenant {request.tenant_id!r}")

    return request


def _step06_09_governance_prep(
    request: ChatRequest,
    session_store: dict[str, Any] | None = None,
) -> GatewaySession:
    """Steps 6–9: session load, safety policy, context mode, injection scan."""
    import uuid

    # Step 6 — resolve / create session
    session_id = (
        _parse_session_id(request.crp_session_token)
        or str(uuid.uuid4())
    )
    tenant_id = request.tenant_id or "local"

    # Step 7 — dynamic safety policy via SafetyControlPlane (SPEC-033)
    from crp.security.control_plane import get_default_control_plane
    scp = get_default_control_plane()
    manifest = scp.manifest
    # Header overrides SCP default; SCP provides the baseline
    safety_profile = request.crp_safety_profile or manifest.profile or "balanced"

    session = GatewaySession(
        session_id=session_id,
        tenant_id=tenant_id,
        safety_profile=safety_profile,
        context_mode=request.crp_context_mode or "auto",
    )
    session._scp = scp  # type: ignore[attr-defined]  # attached for later steps

    # Resolve effective safety policy (header wins, then profile)
    policy = _resolve_safety_policy(request, safety_profile)
    session._policy = policy  # type: ignore[attr-defined]

    # Maintain coverage set for CDR across windows
    if session_store is not None:
        session._coverage_set = session_store.get("_coverage_set")  # type: ignore[attr-defined]
    if not getattr(session, "_coverage_set", None):
        from crp.state.coverage_set import CoverageSet
        session._coverage_set = CoverageSet()  # type: ignore[attr-defined]

    # Restore persisted session state if available
    if session_store is not None:
        stored = session_store.get(session_id)
        if stored:
            session.window_number = stored.get("window_number", 0)
            session.hmac_chain_tip = stored.get("hmac_chain_tip", "")
            session.cso_ref = stored.get("cso_ref", "")
            session.coverage_set_hash = stored.get("coverage_set_hash", "")
            session.safety_budget = stored.get("safety_budget", 1.0)

    # Step 9 — injection scan (advisory in v4 — full detection in SPEC-015)
    last_user_msg = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            last_user_msg = msg.content
            break
    if _is_injection_attempt(last_user_msg):
        logger.warning("Possible prompt-injection detected — session=%s", session_id)
        session._injection_detected = True  # type: ignore[attr-defined]
        session.record_audit("injection_warning", {"snippet": last_user_msg[:120]})
    else:
        session._injection_detected = False  # type: ignore[attr-defined]

    return session


def _parse_session_id(token: str | None) -> str | None:
    """Extract session id from a CRP session token (best-effort, no verify)."""
    if not token:
        return None
    try:
        import base64

        padding = 4 - len(token) % 4
        padded = token + "=" * (padding % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload.get("sid")
    except Exception:
        return None


def _resolve_safety_policy(
    request: ChatRequest,
    safety_profile: str,
) -> SafetyPolicy:
    """Resolve the effective SafetyPolicy from header or profile."""
    header_policy = (
        request.crp_safety_policy
        if hasattr(request, "crp_safety_policy")
        else None
    )
    if header_policy:
        try:
            return parse_policy(header_policy)
        except PolicySyntaxError as exc:
            logger.warning("Invalid CRP-Safety-Policy header: %s", exc)

    raw_profile = _SAFETY_PROFILES.get(safety_profile, _SAFETY_PROFILES["balanced"])
    return parse_policy(raw_profile)


def _is_injection_attempt(text: str) -> bool:
    """Heuristic injection signal — SPEC-015 §4."""
    lower = text.lower()
    injection_patterns = [
        "ignore previous instructions",
        "ignore all prior",
        "disregard your",
        "forget your instructions",
        "you are now",
        "new system prompt",
        "override your",
    ]
    return any(p in lower for p in injection_patterns)


def _step10_build_envelope(
    request: ChatRequest,
    session: GatewaySession,
    router: Any | None = None,
) -> list[ChatMessage]:
    """Step 10: CDR/CDGR/retrieval-integrity envelope build.

    In ``zero-ckf`` mode the messages are forwarded as-is.  Otherwise the last
    user message is embedded and used to retrieve facts from the session's CKF
    (via ``router.ckf`` if available, or session-stored facts), rank them with
    CDR, expand connectors with CDGR, and filter contradictions with retrieval
    integrity before injecting a compact system context message.
    """
    if session.context_mode == "zero-ckf":
        return request.messages

    last_user = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            last_user = msg.content
            break
    if not last_user:
        return request.messages

    coverage_set = getattr(session, "_coverage_set", None)
    if coverage_set is None:
        return request.messages

    # Resolve CKF facts: prefer router-attached CKF, fall back to session store
    ckf_facts = _resolve_envelope_facts(session, router)
    if not ckf_facts:
        return request.messages

    try:
        from crp.envelope.cdr import cdr_rank
        from crp.provenance._embeddings import encode_texts

        query_embeddings = encode_texts([last_user])
        if not query_embeddings:
            return request.messages
        query_embedding = query_embeddings[0]

        # 1. CDR ranking
        cdr_result = cdr_rank(ckf_facts, query_embedding, coverage_set)
        anchors = [sf.fact for sf in cdr_result.ranked[:14]]

        # 2. CDGR multi-hop connector expansion (when edges are available)
        envelope_facts: list[Any] = list(anchors)
        edge_store = getattr(session, "_edge_store", None)
        if edge_store:
            from crp.ckf.cdgr import cdgr_expand

            cdgr_result = cdgr_expand(
                anchor_facts=anchors,
                edge_store=edge_store,
                coverage_set=coverage_set,
                fact_lookup={f.id: f for f in ckf_facts},
                max_hops=2,
                max_connectors=6,
            )
            envelope_facts = list(cdgr_result.assembled)

        # 3. Retrieval-integrity filtering (contradiction resolution)
        from crp.envelope.retrieval_integrity import resolve_fact_authority

        envelope_facts = resolve_fact_authority(envelope_facts)

        if envelope_facts:
            fact_lines = "\n".join(
                f"- {getattr(f, 'text', str(f))}" for f in envelope_facts[:20]
            )
            system_note = ChatMessage(
                role="system",
                content=f"[CRP Verified Context]\n{fact_lines}",
            )
            return [system_note] + request.messages
    except Exception as exc:
        logger.debug("CDR/CDGR envelope build failed (graceful fallback): %s", exc)

    return request.messages


def _resolve_envelope_facts(
    session: GatewaySession,
    router: Any | None = None,
) -> list[Any]:
    """Return facts available for envelope ranking.

    Priority:
      1. Cached facts already attached to the session.
      2. CKF attached to the router (``router.ckf``).
      3. Cold-storage facts restored into the session.
    """
    cached = getattr(session, "_ckf_facts", None)
    if cached:
        return cached

    ckf = getattr(router, "ckf", None) if router is not None else None
    if ckf is not None:
        try:
            # All active facts in the warm store are candidate envelope facts
            return ckf.warm_store.get_active_facts_as_extraction()
        except Exception as exc:
            logger.debug("Could not read router CKF facts: %s", exc)

    return []


def _step11_strip_crp_headers(headers: dict[str, str]) -> dict[str, str]:
    """Step 11: Strip ALL CRP-* headers before forwarding to provider.

    This is AXIOM 4 — a non-negotiable security invariant.  The outbound
    headers to the LLM provider are built from a hard allowlist only.
    Any CRP-* header, governance header, or non-allowlisted header is
    silently dropped.

    Args:
        headers: Raw outbound headers (may include CRP-* keys).

    Returns:
        Clean header dict with only allowlisted keys.
    """
    clean: dict[str, str] = {}
    dropped: list[str] = []

    for key, value in headers.items():
        normalised = key.lower().strip()
        if normalised in _PROVIDER_HEADER_ALLOWLIST:
            clean[key] = value
        else:
            dropped.append(key)

    if dropped:
        logger.debug("Axiom-4 strip: removed headers %s", dropped)

    return clean


def _step12_dispatch(
    request: ChatRequest,
    messages: list[ChatMessage],
    session: GatewaySession,
    router: Any | None = None,
    tool_implementations: dict[str, Any] | None = None,
) -> ProviderResponse:
    """Step 12: dispatch to provider via ProviderRouter (SPEC-016 §8).

    If the request carries ``tools``, route through the CRP Capability Router
    so the protocol selects and executes capabilities instead of proxying the
    raw tool catalogue to the provider.
    """
    if router is None:
        # Fallback: use the local ProviderRouter with no keys
        from crp.gateway.router import ProviderRouter as _Router

        router = _Router()

    if request.tools:
        from crp.gateway.capability_router import CapabilityRouter

        capability_router = CapabilityRouter(
            tools=request.tools,
            max_tokens=request.max_tokens or 1024,
            implementations=tool_implementations or {},
        )
        return capability_router.execute(request, session, router)

    return router.dispatch(request, messages, session)


async def _step13_18_governance_analysis_async(
    request: ChatRequest,
    response: ProviderResponse,
    session: GatewaySession,
) -> DPEReport:
    """Steps 13–18: DPE, policy enforcement, checkpoint, CSO, HMAC, budget."""
    content = response.content

    # Step 13 — DPE analysis (lightweight local analysis; full DPE in SPEC-005)
    report = _run_lightweight_dpe(content, session, request)

    # Step 14 — Safety policy enforcement via formal policy engine
    policy = getattr(session, "_policy", None)
    if policy is not None:
        signals = _build_safety_signals(report, session)
        decision = enforce_policy(policy, signals)
        if decision.action == EnforcementAction.HALT and not policy.report_only:
            report.risk_level = "CRITICAL"
            report.halt_reason = "policy_violation"
            session.record_audit(
                "safety_halt",
                {"risk_level": report.risk_level, "reason": report.halt_reason},
            )
            return report
        if decision.action in (EnforcementAction.WARN, EnforcementAction.REDISPATCH):
            session.record_audit(
                "policy_warn",
                {"violations": [v.violation_type.value for v in decision.violations]},
            )

    if report.should_halt:
        session.record_audit(
            "safety_halt",
            {"risk_level": report.risk_level, "reason": report.halt_reason},
        )
        return report

    # Step 14b — Checkpoint on HIGH/CRITICAL risk (human-in-the-loop, SPEC-034)
    if report.risk_level in {"HIGH", "CRITICAL"} and hasattr(session, "_scp"):
        scp = session._scp  # type: ignore[attr-defined]
        cp = scp.create_checkpoint(
            trigger=f"risk >= {report.risk_level}",
            timeout=300,
            on_timeout="escalate",
            on_reject="fallback",
            context={
                "session_id": session.session_id,
                "risk_level": report.risk_level,
                "coverage_score": report.coverage_score,
                "content_preview": content[:200],
            },
        )
        session.record_audit(
            "checkpoint_created",
            {"checkpoint_id": cp.checkpoint_id, "trigger": f"risk >= {report.risk_level}"},
        )
        resolution = await cp.wait_for_resolution()
        session.record_audit(
            "checkpoint_resolved",
            {
                "checkpoint_id": cp.checkpoint_id,
                "action": resolution.action.value,
                "reviewer": resolution.reviewer,
            },
        )
        if resolution.action.value == "reject":
            report.risk_level = "CRITICAL"
            report.halt_reason = "checkpoint_rejected"
            session.record_audit(
                "safety_halt",
                {"risk_level": report.risk_level, "reason": report.halt_reason},
            )
            return report
        if resolution.action.value == "edit" and resolution.edited_output:
            response.content = resolution.edited_output
            content = response.content

    # Step 15 — Update CSO (if available)
    try:
        from crp.state.cso import relay_cso

        prior_cso = getattr(session, "_cso", None)
        new_cso = relay_cso(
            prior_cso=prior_cso,
            window_output=content,
            window_number=session.window_number,
            dpe_report=dataclasses.asdict(report),
            hmac_key=hashlib.sha256(session.session_id.encode()).digest(),
            goal_sections=session.completed_sections,
        )
        session._cso = new_cso  # type: ignore[attr-defined]
        session.cso_ref = new_cso.cso_id
    except Exception as exc:
        # CSO relay must never block the response
        logger.debug("CSO relay failed (non-blocking): %s", exc)

    # Step 16 — Extend HMAC audit chain (SPEC-011)
    session.hmac_chain_tip = _extend_hmac_chain(
        prior_tip=session.hmac_chain_tip,
        content=content,
        session_id=session.session_id,
        window=session.window_number,
    )
    report.chain_valid = True

    # Step 17 — Increment window, update coverage only when CKF facts exist
    session.window_number += 1
    coverage_set = getattr(session, "_coverage_set", None)
    ckf_facts = getattr(session, "_ckf_facts", None)
    if coverage_set and ckf_facts and content:
        try:
            from crp.provenance._embeddings import encode_texts
            embeddings = encode_texts([content[:500]])
            if embeddings:
                coverage_set.update(
                    addressed_sub_queries=[{
                        "text": content[:500],
                        "embedding": embeddings[0],
                        "depth_weight": 0.5,
                    }],
                    window_number=session.window_number,
                )
        except Exception as exc:
            logger.debug("Coverage set update failed (non-blocking): %s", exc)

    # Step 18 — Decrement safety budget using the formal AgentSafetyBudget
    try:
        risk_level = RiskLevel(report.risk_level.upper())
    except ValueError:
        risk_level = RiskLevel.LOW
    budget = AgentSafetyBudget(budget=session.safety_budget)
    decision = budget.account(risk_level)
    session.safety_budget = decision.budget
    if decision.halted:
        report.risk_level = "CRITICAL"
        report.halt_reason = "safety_budget_depleted"
        session.record_audit(
            "safety_halt",
            {"risk_level": report.risk_level, "reason": report.halt_reason},
        )
        return report

    session.record_audit(
        "window_complete",
        {
            "window": session.window_number,
            "risk_level": report.risk_level,
            "coverage_score": report.coverage_score,
            "chain_tip": session.hmac_chain_tip[:16] + "...",
        },
    )

    return report


def _build_safety_signals(report: DPEReport, session: GatewaySession) -> SafetySignals:
    """Build normalised safety signals from the lightweight DPE report."""
    signals = SafetySignals()
    try:
        signals.risk_level = RiskLevel(report.risk_level.upper())
    except ValueError:
        signals.risk_level = RiskLevel.LOW
    signals.fabrication_count = report.fabrication_count
    signals.grounding_pct = 1.0 if report.grounded else 0.0
    signals.ungrounded_count = 0 if report.grounded else 1
    signals.pii_detected = bool(getattr(session, "_injection_detected", False))
    return signals


def _async_run_sync(coro: Any) -> Any:
    """Run an async coroutine from synchronous code, even inside a running loop."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already inside an event loop — run the coroutine in a side thread.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()


def _step13_18_governance_analysis(
    request: ChatRequest,
    response: ProviderResponse,
    session: GatewaySession,
) -> DPEReport:
    """Synchronous wrapper around the async governance-analysis step."""
    return _async_run_sync(
        _step13_18_governance_analysis_async(request, response, session)
    )


def _run_lightweight_dpe(
    content: str,
    session: GatewaySession,
    request: ChatRequest | None = None,
) -> DPEReport:
    """Lightweight DPE analysis — full implementation wires to SPEC-005.

    Performs heuristic checks for obvious safety issues and uses the
    full DPE provenance engine when available.  When the request depth is
    ``thorough``/``exhaustive`` or the ``crp-verification-relay`` header is set,
    it also runs the Verification Relay (SPEC-049) on extracted claims.
    """
    report = DPEReport()

    # Attempt full DPE integration
    try:
        from crp.provenance.hallucination import compute_hallucination_risk  # type: ignore[import]

        risk = compute_hallucination_risk(content)
        report.risk_level = risk.get("level", "LOW")
    except ImportError:
        # Heuristic fallback — check for known high-risk patterns
        lower = content.lower()
        if any(p in lower for p in ["i cannot provide", "as an ai", "i must refuse"]):
            # Model refusal — safe, not a halt condition
            pass

    # Coverage score proxy — word diversity as a stand-in for real CDR coverage
    words = content.split()
    unique_ratio = len(set(w.lower() for w in words)) / max(1, len(words))
    report.coverage_score = round(min(1.0, unique_ratio * 2), 3)

    # SPEC-049 — Verification Relay (depth-gated)
    if request is not None:
        depth = request.crp_depth
        vr_enabled = request.crp_verification_relay or depth in {"thorough", "exhaustive"}
        if vr_enabled:
            from crp.vr.extract import verify_text

            try:
                vr_report = verify_text(content, depth=depth)
                report.verification_ratio = vr_report.get("verification_ratio", 1.0)
                if vr_report.get("invalid", 0) > 0:
                    report.risk_level = "HIGH"
                    report.halt_reason = "verification_relay_invalid"
            except Exception as exc:
                logger.debug("Verification Relay failed (non-blocking): %s", exc)

    return report


def _extend_hmac_chain(prior_tip: str, content: str, session_id: str, window: int) -> str:
    """Extend the per-session HMAC audit chain (SPEC-011 §4).

    Each window produces a new chain tip = HMAC(prior_tip || window || hash(content)).
    The chain allows tampering detection: any modification to a prior window
    invalidates all subsequent tips.
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    message = f"{session_id}:{window}:{content_hash}:{prior_tip}"
    # Production: use a per-tenant secret key from KeyVault.
    # Dev/test: derive from session_id (not secret, but structurally correct).
    key = hashlib.sha256(session_id.encode()).digest()
    new_tip = hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return new_tip


def _step19_22_emit(
    request: ChatRequest,
    response: ProviderResponse,
    report: DPEReport,
    session: GatewaySession,
) -> dict[str, Any]:
    """Steps 19–22: emit CRP headers, audit stream, re-issue token, return.

    Returns a dict containing:
      - 'body': the response body (OpenAI-compatible)
      - 'headers': CRP-* response headers
      - 'session_token': updated session token string
    """
    # Step 19 — CRP response headers (SPEC-002)
    crp_headers = _build_crp_response_headers(report, session)

    # Step 20 — Stream audit event to Comply (fire-and-forget, no blocking)
    _fire_audit_stream(session)

    # Step 21 — Re-issue session token
    session_token = _reissue_session_token(session)

    # Step 22 — Build OpenAI-compatible response body
    body = _build_openai_response_body(request, response)

    return {
        "body": body,
        "headers": crp_headers,
        "session_token": session_token,
    }


class _ProvenanceAdapter:
    """Lightweight adapter so DPEReport can be consumed by emit_headers."""

    def __init__(self, report: DPEReport) -> None:
        self.risk_report = SimpleNamespace(
            window_risk_level=report.risk_level,
            mean_risk_score=0.5 if report.risk_level == "HIGH" else (
                0.85 if report.risk_level == "CRITICAL" else 0.1
            ),
        )
        self.fidelity = SimpleNamespace(
            fidelity_score=1.0,
            fabrication_count=report.fabrication_count,
            distortion_count=0,
            contradiction_count=report.contradiction_count,
            critical_omission_count=0,
        )
        self.grounding_ratio = 1.0 if report.grounded else 0.0
        self.context_grounded_count = 1 if report.grounded else 0
        self.parametric_count = 0 if report.grounded else 1
        self.mixed_count = 0
        self.uncertain_count = 0
        self.total_claims = 1


def _build_crp_response_headers(report: DPEReport, session: GatewaySession) -> dict[str, str]:
    """Build all CRP-* response headers from DPE report + session state (SPEC-002)."""
    # Canonical header surface via crp.headers.emit
    quality = SimpleNamespace(quality_tier="B")
    headers = emit_headers(
        provenance=_ProvenanceAdapter(report),
        quality=quality,
        session_id=session.session_id,
        window=session.window_number,
        safety_budget=session.safety_budget,
        chain_integrity="INTACT" if report.chain_valid else "BROKEN",
        window_hmac=session.hmac_chain_tip[:32],
        coverage=report.coverage_score,
    )

    # Backward-compatible aliases kept for existing clients/tests
    headers.setdefault("CRP-Risk-Level", report.risk_level)
    headers.setdefault("CRP-Grounded", str(report.grounded).lower())
    headers.setdefault("CRP-Fabrication-Count", str(report.fabrication_count))
    headers.setdefault("CRP-Context-Coverage", f"{report.coverage_score:.3f}")
    headers.setdefault("CRP-Window-Number", str(session.window_number))
    headers.setdefault("CRP-Safety-Budget-Remaining", f"{session.safety_budget:.2f}")
    headers.setdefault("CRP-Verification-Ratio", f"{report.verification_ratio:.3f}")

    # Safety Control Plane config hash when available (SPEC-033)
    if hasattr(session, "_scp"):
        scp = session._scp  # type: ignore[attr-defined]
        headers["CRP-Config-Hash"] = scp.manifest.compute_hash()
    if report.should_halt:
        headers["CRP-Safety-Halt"] = "1"
        headers["CRP-Halt-Reason"] = report.halt_reason or "safety_critical"

    return headers


def _fire_audit_stream(session: GatewaySession) -> None:
    """Step 20: send audit events to Comply (SPEC-042, non-blocking)."""
    if not session.audit_events:
        return
    try:
        from crp.comply.gateway_client import stream_audit_events  # type: ignore[import]

        stream_audit_events(session.audit_events, session.tenant_id)
    except ImportError:
        # Comply gateway client not yet wired — log locally
        logger.debug(
            "Audit stream (Comply not connected): %d events for session=%s",
            len(session.audit_events),
            session.session_id,
        )


def _reissue_session_token(session: GatewaySession) -> str:
    """Step 21: re-issue a compact session token (SPEC-007)."""
    try:
        import base64

        payload = {
            "sid": session.session_id,
            "tid": session.tenant_id,
            "win": session.window_number,
            "cso": session.cso_ref,
            "cov": session.coverage_set_hash,
            "chain": session.hmac_chain_tip[:32],
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return encoded
    except Exception as exc:
        logger.warning("Failed to re-issue session token: %s", exc)
        return ""


def _build_openai_response_body(
    request: ChatRequest, response: ProviderResponse
) -> dict[str, Any]:
    """Build an OpenAI-compatible response body."""
    import uuid

    return {
        "id": f"chatcmpl-crp-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": response.model or request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": response.finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.prompt_tokens + response.completion_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class _RateLimitExceeded(Exception):
    """Raised at step 3 when the per-key rate limit is hit (→ HTTP 429)."""


class _QuotaExhausted(Exception):
    """Raised at step 4 when the tenant quota is exhausted (→ HTTP 402)."""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class GatewayRequestLifecycle:
    """22-step CRP Gateway request lifecycle orchestrator.

    Instantiate once per service process, reuse across requests.

    Args:
        router: ProviderRouter instance.  If None, a default local router is used.
        session_store: Mutable dict used as a simple session persistence layer.
            In production, replace with Redis or another store.
        rate_limit_store: Per-key rate-limit state dict (optional).
        quota_store: Per-tenant quota state dict (optional).
    """

    def __init__(
        self,
        router: Any | None = None,
        session_store: dict[str, Any] | None = None,
        rate_limit_store: dict[str, Any] | None = None,
        quota_store: dict[str, Any] | None = None,
        tool_implementations: dict[str, Any] | None = None,
    ) -> None:
        self.router = router
        self.session_store: dict[str, Any] = session_store if session_store is not None else {}
        self.rate_limit_store = rate_limit_store
        self.quota_store = quota_store
        self.tool_implementations = tool_implementations or {}

    async def aprocess(
        self,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Async 22-step lifecycle (use this from async servers)."""
        return await self._run_lifecycle(body, headers, async_analysis=True)

    def process(
        self,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run the full 22-step lifecycle and return a response dict.

        Args:
            body:    Raw request body (JSON-decoded).
            headers: Raw request headers dict (lowercase keys preferred).

        Returns:
            Dict with keys 'body', 'headers', 'session_token'.
            If a safety halt fires, 'body' will be a HaltResponse dict and
            'headers' will include 'CRP-Safety-Halt: 1'.

        Raises:
            _RateLimitExceeded: step 3 — caller should return HTTP 429.
            _QuotaExhausted:    step 4 — caller should return HTTP 402.
        """
        return _async_run_sync(self._run_lifecycle(body, headers, async_analysis=False))

    async def _run_lifecycle(
        self,
        body: dict[str, Any],
        headers: dict[str, str] | None,
        async_analysis: bool,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        headers = headers or {}

        # Steps 1–5
        request = _step01_05_parse(
            body, headers, self.rate_limit_store, self.quota_store
        )

        # SPEC-050 — Quality-Tier-Supervised Router (optional learned selection)
        try:
            from crp.qsr.gateway import resolve_model

            request.model = resolve_model(request, headers)
        except Exception as exc:
            logger.debug("QSR model resolution failed (non-blocking): %s", exc)

        # Steps 6–9
        session = _step06_09_governance_prep(request, self.session_store)

        # Step 10 — envelope
        augmented_messages = _step10_build_envelope(request, session, self.router)

        # Build raw outbound headers for provider (stripped in step 11)
        raw_provider_headers: dict[str, str] = {}
        if request.api_key:
            raw_provider_headers["Authorization"] = f"Bearer {request.api_key}"
        raw_provider_headers["Content-Type"] = "application/json"

        # Step 11 — strip CRP-* (Axiom 4)
        _step11_strip_crp_headers(raw_provider_headers)

        # Step 12 — dispatch
        response = _step12_dispatch(request, augmented_messages, session, self.router, self.tool_implementations)

        # Steps 13–18 — governance analysis
        if async_analysis:
            report = await _step13_18_governance_analysis_async(request, response, session)
        else:
            report = _step13_18_governance_analysis(request, response, session)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "Gateway lifecycle: session=%s windows=%d elapsed=%.1fms",
            session.session_id,
            session.window_number,
            elapsed_ms,
        )

        # Step 14 check — halt
        if report.should_halt:
            halt = HaltResponse(
                halt_code=report.halt_reason or "safety_critical",
                session_id=session.session_id,
                audit_ref=session.hmac_chain_tip[:16],
            )
            halt_headers = _build_crp_response_headers(report, session)
            return {
                "body": halt.to_body(),
                "headers": halt_headers,
                "session_token": "",
                "status_code": 451,
            }

        # Steps 19–22 — emit + return
        result = _step19_22_emit(request, response, report, session)
        result["status_code"] = 200

        # Persist updated session state
        self.session_store[session.session_id] = {
            "window_number": session.window_number,
            "hmac_chain_tip": session.hmac_chain_tip,
            "cso_ref": session.cso_ref,
            "coverage_set_hash": session.coverage_set_hash,
            "safety_budget": session.safety_budget,
            "_coverage_set": getattr(session, "_coverage_set", None),
            "_cso": getattr(session, "_cso", None),
        }

        return result


def handle_chat_completions(
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    lifecycle: GatewayRequestLifecycle | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for /v1/chat/completions handler.

    Suitable for use in FastAPI/Starlette/ASGI routes or called directly in tests.

    Example::

        result = handle_chat_completions(
            body={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": "Bearer sk-test"},
        )
        assert result["status_code"] == 200
        assert "CRP-Risk-Level" in result["headers"]
    """
    if lifecycle is None:
        lifecycle = GatewayRequestLifecycle()
    return lifecycle.process(body, headers)
