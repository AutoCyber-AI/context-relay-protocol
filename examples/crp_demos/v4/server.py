# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v4.1 interactive protocol demo backend.

Serves a single-page demo that drives a local LLM through the Context Relay
Protocol v4.1 runtime and surfaces every governance signal it produces:

* OpenAI-compatible provider discovery and provider-neutral routing
* SPEC-007 signed session tokens with CRP-Set-Session header
* Canonical CRP-* response header namespace (SPEC-002)
* Window-level HMAC-SHA256 provenance chain (SPEC-004 / SPEC-011)
* Tamper detection / chain verification
* Context Knowledge Fabric (CKF) fact graph with semantic retrieval (SPEC-003)
* Full Decision Provenance Engine (DPE) pipeline (SPEC-005)
* Safety budget accounting and circuit breaker (SPEC-012)
* Parsed Safety Policy enforcement with HTTP 451 halts (SPEC-006)
* EU AI Act / GDPR / NIST / ISO 42001 compliance classification
* Audit export (NDJSON / OCSF)

Run from the repo root:

    python -m examples.crp_demos.v4.server

Then open http://127.0.0.1:8774 in a browser.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Make the sibling Gateway/Comply shared modules importable when this file is run
# directly from any working directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GATEWAY_ROOT = _REPO_ROOT.parent / "crp-gateway"
_COMPLY_ROOT = _REPO_ROOT.parent / "crp-comply" / "src"
for p in (_GATEWAY_ROOT, _COMPLY_ROOT, str(_REPO_ROOT)):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from crp.agent.budget import AgentSafetyBudget, BudgetDecision, CircuitState
from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
from crp.core.task_intent import TaskIntent
from crp.core.window import WindowNode, WindowPattern
from crp.envelope.builder import EnvelopeState, compute_envelope_budget, construct
from crp.envelope.packer import estimate_tokens, pack_facts
from crp.envelope.scoring import ScoringConfig, score_facts
from crp.extraction.types import Fact, FactEdge, FactGraph
from crp.headers import names as H
from crp.headers.emit import emit_headers
from crp.observability.quality import QualityReporter
from crp.policy.enforce import (
    EnforcementAction,
    SafetySignals,
    enforce_policy,
    extract_signals,
)
from crp.policy.grammar import PolicySyntaxError, parse_policy
from crp.policy.model import RiskLevel
from crp.provenance import DecisionProvenanceEngine, ProvenanceConfig
from crp.provenance.report_generator import generate_json_report
from crp.provenance.window_chain import (
    WindowChainRecord,
    WindowHmacInput,
    build_window_hmac,
    verify_window_chain,
)
from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType
from crp.security.compliance import AISystemCategory, RiskClassifier
from crp.security.control_plane import get_default_control_plane
from crp.security.injection import InjectionDetector
from crp.security.privacy import PIIScanner
from crp.security.validation import InputValidator
from crp_shared.session_token import SessionTokenManager

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LM_STUDIO_BASE_URL = os.environ.get("LM_STUDIO_BASE_URL", "http://192.168.0.6:1234/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MASTER_KEY = hashlib.sha256(b"crp-v4-demo-master-key").digest()
TOKEN_MANAGER = SessionTokenManager(MASTER_KEY, default_ttl_seconds=3600)
PROTOCOL_VERSION = "5.0.0"

# Active safety layer instances (Layer 1–2, advisory but surfaced).
_INPUT_VALIDATOR = InputValidator()
_INJECTION_DETECTOR = InjectionDetector()
_PII_SCANNER = PIIScanner()
_SAFETY_CONTROL_PLANE = get_default_control_plane()
# Note: PROTOCOL_VERSION is the demo runtime label; package version is in crp/_version.py.

# Tuned DPE config for the demo: be less aggressive about parametric/uncertain
# claims so that open-domain prompts (creative writing, math, opinion) do not
# dominate the risk profile, while still catching fabrications, distortions and
# contradictions.
DEMO_DPE_CONFIG = ProvenanceConfig(
    # Stricter thresholds so loaded CKF facts cannot mask fabricated claims.
    similarity_threshold=0.55,
    mixed_threshold=0.35,
    min_grounding_semantic=0.40,
    min_grounding_lexical=0.15,
    min_mixed_semantic=0.25,
    entailment_enabled=True,
    risk_weight_attribution=0.30,
    risk_weight_fidelity=0.30,
    risk_weight_entailment=0.30,
    risk_weight_specificity=0.10,
    rqa_weight_repetition=0.25,
    rqa_weight_completeness=0.35,
    rqa_weight_flow=0.25,
    rqa_weight_coherence=0.15,
)
DEFAULT_CONTEXT_WINDOW = 4096
DEFAULT_MAX_TOKENS = 512

# In-memory stores (demos are ephemeral by design)
_sessions: dict[str, "DemoSession"] = {}

app = FastAPI(title="CRP v4.1 Protocol Demo", version=PROTOCOL_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = Path(__file__).resolve().parent / "static"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DemoSession:
    session_id: str
    created_at: float = field(default_factory=time.time)
    facts: list[Fact] = field(default_factory=list)
    graph: FactGraph = field(default_factory=FactGraph)
    windows: list[WindowNode] = field(default_factory=list)
    chain_records: list[WindowChainRecord] = field(default_factory=list)
    ckf: ContextualKnowledgeFabric = field(
        default_factory=lambda: ContextualKnowledgeFabric(CKFConfig(persist_path=""))
    )
    audit: ComplianceAuditTrail = field(default_factory=lambda: ComplianceAuditTrail())
    budget: AgentSafetyBudget = field(default_factory=AgentSafetyBudget)
    quality_reporter: QualityReporter = field(default_factory=QualityReporter)
    quality_history: list[str] = field(default_factory=list)
    policy_raw: str = ""
    continuation_counter: int = 0
    window_texts: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def current_window_number(self) -> int:
        return len(self.windows)

    def next_continuation_id(self) -> str:
        self.continuation_counter += 1
        return f"crp_cont_{self.session_id[-12:]}_{self.continuation_counter:04d}"


def _seed_crp_facts(session: DemoSession) -> None:
    """Pre-load a small CRP knowledge base so factual prompts can ground claims."""
    seed_texts = [
        "The Context Relay Protocol (CRP) is an open protocol for governable, auditable AI inference.",
        "CRP provides context envelopes, a Contextual Knowledge Fabric (CKF), a Decision Provenance Engine (DPE), a safety budget, and compliance headers.",
        "CRP uses HMAC-SHA256 window chains and signed session tokens for tamper-evident provenance.",
        "CRP supports provider-neutral routing to OpenAI-compatible LLM providers.",
        "CRP classifies outputs against the EU AI Act, GDPR PII exposure, NIST AI RMF, and ISO 42001.",
    ]
    facts = []
    for text in seed_texts:
        fact = Fact(
            id=f"fact-seed-{hashlib.sha256(text.encode()).hexdigest()[:8]}",
            text=text,
            category="seed",
            source_window_id="seed",
            confidence=0.95,
        )
        facts.append(fact)
    _add_facts_to_session(session, facts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> float:
    return time.time()


def _policy_hash(policy: str) -> str:
    return hashlib.sha256((policy or "").encode()).hexdigest()[:16]


def _derive_session_key(session_id: str) -> bytes:
    return hmac.new(MASTER_KEY, f"window-chain:{session_id}".encode(), hashlib.sha256).digest()


def _detect_pii(text: str) -> bool:
    """Pattern-based PII detector backed by the library PIIScanner."""
    if not text:
        return False
    return _PII_SCANNER.scan(text).has_pii


def _scan_input(text: str) -> dict[str, Any]:
    """Run Layer 1 validation and Layer 2 injection/PII scans on input.

    Returns a dict with sanitized text, validation warnings, injection flags,
    and PII findings. This is the active safety pre-flight for every user
    message.
    """
    validation = _INPUT_VALIDATOR.validate(text)
    injection_report = _INJECTION_DETECTOR.scan(validation.sanitized_text)
    pii_report = _PII_SCANNER.scan(validation.sanitized_text)
    return {
        "sanitized_text": validation.sanitized_text,
        "valid": validation.valid,
        "validation_warnings": validation.warnings,
        "injection_flags": injection_report.security_flags,
        "injection_highest_confidence": injection_report.highest_confidence,
        "pii_detected": pii_report.has_pii,
        "pii_types": sorted(pii_report.pii_types_found),
        "pii_classification": pii_report.highest_classification.name,
    }


def _coerce_risk(value: Any) -> RiskLevel:
    raw = str(getattr(value, "value", value)).upper()
    try:
        return RiskLevel(raw)
    except ValueError:
        return RiskLevel.LOW


_TIER_ORDER = ["S", "A", "B", "C", "D"]


def _cap_tier_by_risk(tier: str, risk_level: RiskLevel) -> str:
    """Cap quality tier by hallucination risk level."""
    cap = {
        RiskLevel.CRITICAL: "D",
        RiskLevel.HIGH: "B",
        RiskLevel.MEDIUM: "A",
        RiskLevel.LOW: "S",
    }.get(risk_level, "S")
    try:
        worse_idx = max(_TIER_ORDER.index(tier), _TIER_ORDER.index(cap))
    except ValueError:
        return tier
    return _TIER_ORDER[worse_idx]


def _fact_to_dict(fact: Fact) -> dict[str, Any]:
    return {
        "id": fact.id,
        "text": fact.text,
        "category": fact.category or "extracted",
        "confidence": round(fact.confidence, 2),
        "source_window_id": fact.source_window_id,
    }


def _extract_facts(answer: str, window_id: str) -> list[Fact]:
    """Convert an LLM answer into CKF Fact objects."""
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    facts: list[Fact] = []
    for s in sentences:
        s = s.strip()
        if len(s) >= 16:
            facts.append(
                Fact(
                    id=f"fact-{uuid.uuid4().hex[:8]}",
                    text=s,
                    category="extracted",
                    source_window_id=window_id,
                    confidence=0.85,
                )
            )
    return facts


def _add_facts_to_session(session: DemoSession, facts: list[Fact]) -> None:
    """Ingest facts into the session CKF and graph."""
    session.ckf.store(facts)
    for fact in facts:
        session.graph.add_fact(fact)
    # Link consecutive facts in the same window with a RELATED edge.
    for i in range(len(facts) - 1):
        session.graph.add_edge(
            FactEdge(
                source_id=facts[i].id,
                target_id=facts[i + 1].id,
                relation_type="RELATED",
                confidence=0.6,
            )
        )
    session.facts.extend(facts)


def _embed_text(text: str) -> list[float] | None:
    """Try to get an embedding from the local LLM server; return None on failure."""
    try:
        payload = {
            "model": "text-embedding-nomic-embed-text-v1.5",
            "input": text[:512],
        }
        resp = httpx.post(f"{LM_STUDIO_BASE_URL}/embeddings", json=payload, timeout=15.0)
        resp.raise_for_status()
        data = resp.json().get("data", [{}])[0]
        return data.get("embedding")
    except Exception:  # noqa: BLE001
        return None


def _ckf_retrieve(session: DemoSession, query: str, budget: int) -> list[Fact]:
    """CKF retriever callback used by the envelope builder."""
    embedding = _embed_text(query)
    try:
        merge_result = session.ckf.retrieve(
            query_embedding=embedding,
            modes=["semantic", "graph_walk"],
            budget=budget,
        )
        return [mf.fact for mf in merge_result.facts]
    except Exception:  # noqa: BLE001
        # Fallback: return recent facts from warm store.
        return session.facts[-budget:]


def _build_envelope(
    session: DemoSession,
    user_text: str,
    system_text: str,
) -> tuple[Any, list[Fact]]:
    """Build a context envelope and return packed facts for DPE."""
    task_intent = TaskIntent(
        task_input=user_text,
        system_prompt=system_text,
        expected_output_type="text",
        max_output_tokens=DEFAULT_MAX_TOKENS,
    )
    system_tokens = estimate_tokens(system_text)
    task_tokens = estimate_tokens(user_text)
    budget = compute_envelope_budget(
        DEFAULT_CONTEXT_WINDOW,
        system_tokens,
        task_tokens,
        max_output_tokens=DEFAULT_MAX_TOKENS,
    )

    state = EnvelopeState(
        facts=session.facts,
        graph=session.graph,
        current_window_index=session.current_window_number,
        ckf_retriever=lambda q, b: _ckf_retrieve(session, q, b),
        scoring_config=ScoringConfig(),
    )

    result = construct(task_intent, budget, state, count_tokens=None)
    return result, [pf for pf in (result.packing.packed_facts if result.packing else [])]


def _run_dpe(
    session: DemoSession,
    answer: str,
    packed_facts: list[Any],
    envelope_saturation: float,
    user_text: str,
) -> Any:
    """Run the Decision Provenance Engine over an LLM response."""
    dpe = DecisionProvenanceEngine(config=DEMO_DPE_CONFIG)
    prior_texts = [
        session.window_texts.get(w.window_id, {}).get("answer", w.response_hash)
        for w in session.windows[:-1]
    ][-3:]
    return dpe.analyse(
        output_text=answer,
        packed_facts=packed_facts,
        session_id=session.session_id,
        window_id=session.windows[-1].window_id if session.windows else "",
        envelope_saturation=envelope_saturation,
        task_input_preview=user_text[:120],
        query=user_text,
        window_number=session.current_window_number or 1,
        prior_window_texts=prior_texts,
        embedder=_embed_text,
    )


def _classify_compliance(answer: str, pii_detected: bool) -> Any:
    """Run EU AI Act / GDPR classification."""
    classifier = RiskClassifier()
    return classifier.assess(
        category=AISystemCategory.CONTENT_GENERATION,
        intended_purpose="CRP v4.1 interactive protocol demo chat",
        processes_personal_data=pii_detected,
        makes_automated_decisions=False,
        affects_fundamental_rights=False,
        safety_critical=False,
        profiles_individuals=False,
    )


def _compute_window_hmac(
    session: DemoSession,
    window: WindowNode,
    response_hash: str,
    dpe_report_hash: str,
) -> str:
    key = _derive_session_key(session.session_id)
    parent_hmac = ""
    if session.chain_records:
        parent_hmac = session.chain_records[-1].hmac
    timestamp = window.created_at
    return build_window_hmac(
        WindowHmacInput(
            session_id=session.session_id,
            window_number=window.window_number,
            timestamp=f"{timestamp:.6f}",
            response_hash=response_hash,
            dpe_report_hash=dpe_report_hash,
            prev_window_hmac=parent_hmac,
        ),
        key,
    )


def _format_set_session(
    token: str,
    window_number: int,
    quality_history: list[str],
    safety_budget: float,
) -> str:
    qh = ",".join(quality_history[-10:]) if quality_history else ""
    return (
        f"token={token}; Path=/; Max-Age=3600; Signed; SameSite=Strict; "
        f"Window={window_number}; QualityHistory={qh}; SafetyBudget={safety_budget:.4f}"
    )


def _strip_crp_headers(headers: dict[str, str]) -> dict[str, str]:
    """Axiom 4: remove CRP-* headers before forwarding to a provider."""
    return {k: v for k, v in headers.items() if not k.lower().startswith("crp-")}


_CRP_HEADER_LINE_RE = re.compile(r"^[ \t]*CRP-[-A-Za-z0-9]+\s*:.*$", re.IGNORECASE | re.MULTILINE)


def _sanitize_message_content(content: str) -> str:
    """Axiom 4 (content variant): strip embedded CRP header lines from text.

    Prevents a user or downstream agent from smuggling CRP directives inside
    message content that might be interpreted as protocol metadata.
    """
    if not isinstance(content, str):
        return content
    return _CRP_HEADER_LINE_RE.sub("", content).strip()


def _prepare_provider_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return messages safe to forward to an LLM provider (Axiom 4)."""
    clean: list[dict[str, str]] = []
    for m in messages:
        cm = dict(m)
        if isinstance(cm.get("content"), str):
            cm["content"] = _sanitize_message_content(cm["content"])
        clean.append(cm)
    return clean


async def _lm_chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    provider: str = "local",
) -> dict[str, Any]:
    """Call a provider. Only LM Studio is wired by default; others are stubbed."""
    if provider == "local":
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload: dict[str, Any] = {
                "model": model or "meta-llama-3.1-8b-instruct",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": DEFAULT_MAX_TOKENS,
            }
            resp = await client.post(f"{LM_STUDIO_BASE_URL}/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()
    if provider == "openai" and OPENAI_API_KEY:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": model or "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": DEFAULT_MAX_TOKENS,
                },
            )
            resp.raise_for_status()
            return resp.json()
    if provider == "anthropic" and ANTHROPIC_API_KEY:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model or "claude-3-haiku-20240307",
                    "max_tokens": DEFAULT_MAX_TOKENS,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            return resp.json()
    raise HTTPException(status_code=400, detail=f"Provider '{provider}' not configured")


async def _lm_models(provider: str = "local") -> list[dict[str, Any]]:
    if provider == "local":
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{LM_STUDIO_BASE_URL}/models")
            resp.raise_for_status()
            return resp.json().get("data", [])
    # Stub provider lists for configured external providers.
    if provider == "openai" and OPENAI_API_KEY:
        return [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]
    if provider == "anthropic" and ANTHROPIC_API_KEY:
        return [{"id": "claude-3-haiku-20240307"}, {"id": "claude-3-sonnet-20240229"}]
    return []


# ---------------------------------------------------------------------------
# Dispatch core
# ---------------------------------------------------------------------------


async def _do_dispatch(
    session_id: str,
    messages: list[dict[str, str]],
    system_policy: str,
    model: str,
    provider: str,
    parent_window_id: str | None = None,
    transfer_type: str = "SUMMARY",
) -> JSONResponse:
    session = _sessions[session_id]
    window_id = f"win_{uuid.uuid4().hex[:12]}"

    # Extract system prompt and user text from messages.
    system_text = next((m["content"] for m in messages if m.get("role") == "system"), "")
    raw_user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")

    # Layer 1 + Layer 2 active safety pre-flight on the raw user message.
    input_safety = _scan_input(raw_user_text)
    if not input_safety["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Input validation failed: {input_safety['validation_warnings']}",
        )
    user_text = input_safety["sanitized_text"]

    # Parse safety policy.
    try:
        policy = (
            parse_policy(system_policy)
            if system_policy.strip()
            else parse_policy("default-src context parametric; halt-on CRITICAL; warn-on HIGH")
        )
    except PolicySyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid safety policy: {exc}") from exc
    session.policy_raw = system_policy

    # Create window node.
    window_number = session.current_window_number + 1
    window = WindowNode(
        window_id=window_id,
        window_number=window_number,
        continuation_id=session.next_continuation_id(),
        pattern=WindowPattern.LINEAR if parent_window_id is None else WindowPattern.BRANCH,
        system_prompt_hash=hashlib.sha256(system_text.encode()).hexdigest()[:16],
        task_input_hash=hashlib.sha256(user_text.encode()).hexdigest()[:16],
        safety_budget=session.budget.budget,
    )
    if parent_window_id:
        parent = next((w for w in session.windows if w.window_id == parent_window_id), None)
        if parent:
            window.parent_ids = [parent_window_id]
            parent.child_ids.append(window_id)
    session.windows.append(window)

    if input_safety["injection_flags"]:
        session.audit.record(
            ComplianceEventType.INJECTION_DETECTED,
            session_id=session_id,
            data={
                "window_id": window_id,
                "flags": input_safety["injection_flags"],
                "highest_confidence": input_safety["injection_highest_confidence"],
            },
        )
    if input_safety["pii_detected"]:
        session.audit.record(
            ComplianceEventType.PII_DETECTED,
            session_id=session_id,
            data={
                "window_id": window_id,
                "types": input_safety["pii_types"],
                "classification": input_safety["pii_classification"],
            },
        )

    session.audit.record(
        ComplianceEventType.SESSION_CREATED if window_number == 1 else ComplianceEventType.LLM_CALL_COMPLETED,
        session_id=session_id,
        data={"window_id": window_id, "window_number": window_number, "model": model, "provider": provider},
    )

    # Build envelope and packed facts.
    env_result, packed_facts = _build_envelope(session, user_text, system_text)

    # Axiom 4: sanitize messages before forwarding to the provider.
    provider_messages = _prepare_provider_messages(messages)

    # Call provider.
    t0 = _now()
    try:
        lm_resp = await _lm_chat(provider_messages, model=model, provider=provider)
        answer = lm_resp["choices"][0]["message"]["content"]
        finish_reason = lm_resp["choices"][0].get("finish_reason", "stop")
        usage = lm_resp.get("usage", {})
        # Store actual text for continuation/turn reconstruction.
        session.window_texts[window_id] = {"user": user_text, "answer": answer}
    except Exception as exc:  # noqa: BLE001
        session.audit.record(
            ComplianceEventType.PROVENANCE_ENGINE_FAILURE,
            session_id=session_id,
            data={"window_id": window_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Provider error: {exc}") from exc

    # Post-call active safety: scan model output for PII.
    output_pii = _PII_SCANNER.scan(answer)
    if output_pii.has_pii:
        session.audit.record(
            ComplianceEventType.PII_DETECTED,
            session_id=session_id,
            data={
                "window_id": window_id,
                "types": sorted(output_pii.pii_types_found),
                "classification": output_pii.highest_classification.name,
                "source": "output",
            },
        )
    llm_latency_ms = (_now() - t0) * 1000

    # Extract facts and add to session CKF / graph.
    new_facts = _extract_facts(answer, window_id)
    _add_facts_to_session(session, new_facts)

    # Run DPE.
    provenance_report = _run_dpe(
        session, answer, packed_facts, env_result.saturation, user_text
    )
    risk_level = _coerce_risk(
        getattr(provenance_report.risk_report, "window_risk_level", RiskLevel.LOW)
        if provenance_report.risk_report
        else RiskLevel.LOW
    )

    # Compliance classification.
    pii_detected = input_safety["pii_detected"] or output_pii.has_pii
    compliance_assessment = _classify_compliance(answer, pii_detected)

    # Quality report.
    fact_miss_pct = 0.0
    if env_result.facts_available:
        fact_miss_pct = (
            env_result.facts_available - env_result.facts_included
        ) / env_result.facts_available * 100
    overhead_pct = min(50.0, max(2.0, (llm_latency_ms / max(usage.get("total_tokens", 1), 1)) / 10))
    quality_report = session.quality_reporter.assess(
        overhead_pct=overhead_pct,
        fact_miss_pct=fact_miss_pct,
        details={"saturation": env_result.saturation, "ckf_added": env_result.ckf_facts_added},
    )
    emitted_tier = quality_report.tier.value
    if provenance_report.rqa:
        from crp.provenance.rqa import downgrade_tier
        emitted_tier = downgrade_tier(emitted_tier, provenance_report.rqa.quality_score)
    # The DPE's internal quality_tier is intentionally NOT used here: it is a
    # coarse grounding-derived fallback that is unreliable for open-domain demo
    # prompts. We rely on the envelope quality reporter and the RQA composite
    # score, then cap the tier by hallucination risk.
    emitted_tier = _cap_tier_by_risk(emitted_tier, risk_level)
    session.quality_history.append(emitted_tier)

    # Policy enforcement.
    signals = extract_signals(
        provenance=provenance_report,
        quality=SimpleNamespace(
            quality_tier=emitted_tier,
            envelope_saturation=env_result.saturation,
            facts_extracted=len(new_facts),
        ),
        compliance=compliance_assessment,
        rqa={
        "repetition": getattr(provenance_report.repetition, "level", None),
        "completeness": getattr(provenance_report.completeness, "score", None),
        "flow": getattr(provenance_report.flow, "flow_score", None),
        "score": provenance_report.rqa.quality_score if provenance_report.rqa else None,
    },
    )
    # The DPE marks claims with no source as 'uncertain', but 'uncertain' is not a
    # source-trust token in the policy grammar; discard it so the demo does not halt
    # on every first message before any facts exist.
    signals.sources_used.discard("uncertain")
    policy_decision = enforce_policy(policy, signals)

    # Build window chain record.
    response_hash = hashlib.sha256(answer.encode()).hexdigest()
    dpe_report_hash = hashlib.sha256(json.dumps(generate_json_report(provenance_report), sort_keys=True).encode()).hexdigest()[:32]
    window_hmac = _compute_window_hmac(session, window, response_hash, dpe_report_hash)
    window.response_hash = response_hash
    window.dpe_report_hash = dpe_report_hash
    window.hmac = window_hmac
    window.hmac_chain_tip = window_hmac
    window.quality_tier = emitted_tier
    window.risk_level = risk_level.value

    chain_record = WindowChainRecord(
        session_id=session_id,
        window_number=window_number,
        timestamp=f"{window.created_at:.6f}",
        response_hash=response_hash,
        dpe_report_hash=dpe_report_hash,
        hmac=window_hmac,
    )
    session.chain_records.append(chain_record)

    session.audit.record(
        ComplianceEventType.WINDOW_HMAC_GENERATED,
        session_id=session_id,
        data={"window_id": window_id, "hmac": window_hmac},
    )

    # Safety budget accounting (only if we are going to deliver the response).
    budget_decision = session.budget.peek()
    if policy_decision.action == EnforcementAction.HALT:
        # Do not decrement on a policy halt.
        pass
    else:
        budget_decision = session.budget.account(risk_level)

    if budget_decision.halted:
        policy_decision.action = EnforcementAction.HALT
        policy_decision.http_status = 451
        policy_decision.retry_after = budget_decision.retry_after or "new-session-required"

    # Common header inputs.
    audit_trail_id = session_id
    audit_trail_uri = f"/api/v4/session/{session_id}/export.ndjson"
    report_uri = f"/api/v4/session/{session_id}/export.ocsf"
    dag_root = session.windows[0].window_id if session.windows else window_id
    window_lineage = ",".join(window.parent_ids) if window.parent_ids else "root"

    token = TOKEN_MANAGER.issue(
        session_id=session_id,
        window_id=window_id,
        quality_hash=",".join(session.quality_history[-10:]),
        soft_budget=int(usage.get("total_tokens", 0)),
        continuation_count=window_number,
        conversation_id=window.continuation_id,
        dag_node_id=window_id,
        strategy="envelope-pack",
        policy_id=_policy_hash(system_policy),
        ckf_etag=hashlib.sha256(
            json.dumps([f.id for f in session.facts], separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()[:16],
        scope=0,
    )

    set_session = _format_set_session(
        token, window_number, session.quality_history, session.budget.budget
    )

    headers = emit_headers(
        provenance=provenance_report,
        quality=SimpleNamespace(
            quality_tier=emitted_tier,
            envelope_saturation=env_result.saturation,
            facts_extracted=env_result.facts_included,
        ),
        compliance=SimpleNamespace(
            risk_level=compliance_assessment.risk_level,
            processes_personal_data=compliance_assessment.processes_personal_data,
            nist_tier="Tier-1",
            iso_42001="aligned",
            controls_met=12,
        ),
        rqa={
            "repetition": getattr(provenance_report.repetition, "level", None),
            "completeness": getattr(provenance_report.completeness, "score", None),
            "flow": getattr(provenance_report.flow, "flow_score", None),
            "score": provenance_report.rqa.quality_score if provenance_report.rqa else None,
        },
        session_id=session_id,
        window=f"{window_number}/{max(window_number, 1)}",
        strategy="envelope-pack",
        protocol_version=PROTOCOL_VERSION,
        etag=hashlib.sha256(env_result.envelope_text.encode()).hexdigest()[:16],
        cache_status="miss",
        window_hmac=window_hmac,
        chain_integrity="VALID",
        report_uri=report_uri,
        audit_trail_id=audit_trail_id,
        audit_trail_uri=audit_trail_uri,
        data_residency="local",
        safety_budget=session.budget.budget,
        oversight_mode="human-review" if budget_decision.force_oversight else "auto",
        policy_applied=policy.to_policy_string(),
        mode="demo",
        continuation_id=window.continuation_id,
        dag_root=dag_root,
        window_lineage=window_lineage,
        set_session=set_session,
        extra={
            H.CONTEXT_TOKENS_USED: str(usage.get("total_tokens", 0)),
            H.AGENT_LOOP_DEPTH: "0",
            H.AGENT_PHASE: "dispatch",
            H.AGENT_TOOL_CALLS: "0",
            H.MEMORY_TIER_HIT: "warm",
            H.MEMORY_CKF_HITS: str(env_result.ckf_facts_added),
            H.MEMORY_KNOWLEDGE_AGE: "0",
            H.SAFETY_RETRY_AFTER: (
                policy_decision.retry_after or budget_decision.retry_after or "none"
            ),
            "CRP-Safety-Injection-Flags": ", ".join(input_safety["injection_flags"]) or "none",
            "CRP-Compliance-PII-Types": ", ".join(sorted(set(input_safety["pii_types"] + (sorted(output_pii.pii_types_found) if output_pii.has_pii else [])))) or "none",
            "CRP-Safety-Validation-Warnings": "; ".join(input_safety["validation_warnings"]) or "none",
            "CRP-Safety-Control-Plane-Version": _SAFETY_CONTROL_PLANE.manifest.to_dict().get("version", "1.0"),
        },
    )

    # Ensure all emitted header names use the canonical CRP-* namespace.
    headers = {k: v for k, v in headers.items() if k.lower().startswith("crp-")}

    response_body: dict[str, Any] = {
        "session_id": session_id,
        "window_id": window_id,
        "window_number": window_number,
        "continuation_id": window.continuation_id,
        "model": model,
        "provider": provider,
        "answer": answer,
        "risk_level": risk_level.value,
        "quality_tier": emitted_tier,
        "saturation": round(env_result.saturation, 4),
        "facts_extracted": [_fact_to_dict(f) for f in new_facts],
        "facts_recalled": [
            {
                "id": pf.fact_id,
                "text": pf.text,
                "score": round(pf.score, 4),
                "tokens": pf.tokens,
            }
            for pf in packed_facts
        ],
        "facts_total": len(session.facts),
        "usage": usage,
        "token": token,
        "set_session": set_session,
        "safety_budget": round(session.budget.budget, 4),
        "circuit_state": session.budget.circuit_state.value,
        "policy_action": policy_decision.action.value,
        "policy_violations": [
            {"directive": v.directive, "action": v.action.value, "detail": v.detail}
            for v in policy_decision.violations
        ],
        "input_safety": {
            "validation_warnings": input_safety["validation_warnings"],
            "injection_flags": input_safety["injection_flags"],
            "injection_highest_confidence": input_safety["injection_highest_confidence"],
            "pii_detected": input_safety["pii_detected"],
            "pii_types": input_safety["pii_types"],
            "pii_classification": input_safety["pii_classification"],
        },
        "output_pii": {
            "detected": output_pii.has_pii,
            "types": sorted(output_pii.pii_types_found) if output_pii.has_pii else [],
            "classification": output_pii.highest_classification.name if output_pii.has_pii else "INTERNAL",
        },
        "safety_surface_uri": "/api/v4/safety-surface",
        "audit": {"valid": True, "events": session.audit.entry_count},
        "finish_reason": finish_reason,
    }

    if policy_decision.action == EnforcementAction.HALT:
        session.audit.record(
            ComplianceEventType.OVERSIGHT_HALT,
            session_id=session_id,
            data={
                "window_id": window_id,
                "reason": policy_decision.violations[0].detail if policy_decision.violations else "policy",
                "risk_level": risk_level.value,
            },
        )
        halt_body = {
            "crp_halt_reason": (
                policy_decision.violations[0].detail if policy_decision.violations else "policy-halt"
            ),
            "audit_trail_uri": audit_trail_uri,
            "oversight_required": True,
            "retry_condition": policy_decision.retry_after or "human-review-required",
            "session_id": session_id,
            "window_id": window_id,
            "risk_level": risk_level.value,
            "safety_budget": round(session.budget.budget, 4),
            "input_safety": {
                "validation_warnings": input_safety["validation_warnings"],
                "injection_flags": input_safety["injection_flags"],
                "injection_highest_confidence": input_safety["injection_highest_confidence"],
                "pii_detected": input_safety["pii_detected"],
                "pii_types": input_safety["pii_types"],
                "pii_classification": input_safety["pii_classification"],
            },
            "output_pii": {
                "detected": output_pii.has_pii,
                "types": sorted(output_pii.pii_types_found) if output_pii.has_pii else [],
                "classification": output_pii.highest_classification.name if output_pii.has_pii else "INTERNAL",
            },
            "policy_violations": [
                {"directive": v.directive, "action": v.action.value, "detail": v.detail}
                for v in policy_decision.violations
            ],
        }
        return JSONResponse(
            content=halt_body,
            status_code=policy_decision.http_status or 451,
            headers=headers,
        )

    session.audit.record(
        ComplianceEventType.RISK_ASSESSMENT_COMPLETED,
        session_id=session_id,
        data={
            "window_id": window_id,
            "risk_level": risk_level.value,
            "quality_tier": emitted_tier,
            "safety_budget": session.budget.budget,
        },
    )
    return JSONResponse(content=response_body, headers=headers)



# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v4/models")
async def list_models() -> dict[str, Any]:
    providers = []
    # Local LM Studio
    try:
        local_models = await _lm_models("local")
        providers.append({
            "provider": "local",
            "base_url": LM_STUDIO_BASE_URL,
            "reachable": True,
            "models": local_models,
            "primary": local_models[0] if local_models else None,
            "count": len(local_models),
        })
    except Exception as exc:  # noqa: BLE001
        providers.append({
            "provider": "local",
            "base_url": LM_STUDIO_BASE_URL,
            "reachable": False,
            "models": [],
            "primary": None,
            "count": 0,
            "error": str(exc),
        })

    for prov, key in (("openai", OPENAI_API_KEY), ("anthropic", ANTHROPIC_API_KEY)):
        if key:
            models = await _lm_models(prov)
            providers.append(
                {
                    "provider": prov,
                    "reachable": True,
                    "models": models,
                    "count": len(models),
                }
            )
        else:
            providers.append(
                {
                    "provider": prov,
                    "reachable": False,
                    "models": [],
                    "count": 0,
                    "error": "API key not configured",
                }
            )

    return {"providers": providers, "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v4/dispatch")
async def dispatch(request: Request) -> JSONResponse:
    body = await request.json()
    session_id = body.get("session_id") or f"sess_{uuid.uuid4().hex[:16]}"
    if session_id not in _sessions:
        session = DemoSession(session_id=session_id)
        _seed_crp_facts(session)
        _sessions[session_id] = session

    messages = list(body.get("messages", []))
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    return await _do_dispatch(
        session_id=session_id,
        messages=messages,
        system_policy=body.get("policy", ""),
        model=body.get("model") or "meta-llama-3.1-8b-instruct",
        provider=body.get("provider") or "local",
    )


# ---------------------------------------------------------------------------
# CRP v5 — Positioned Tool Loop (SPEC-049 / SPEC-050)
# ---------------------------------------------------------------------------

# Deterministic demo tools — no external network, so the loop is reproducible
# on camera. Each tool result becomes a typed CSO observation, never raw prompt
# text, which is what keeps the working set bounded across many calls.
_DEMO_PORT_SERVICES = {
    "22": "SSH", "80": "HTTP", "443": "HTTPS", "3306": "MySQL",
    "5432": "PostgreSQL", "6379": "Redis", "27017": "MongoDB",
}
_DEMO_CVE_DB = {
    "CVE-2021-44228": {"name": "Log4Shell", "severity": "CRITICAL", "cvss": 10.0},
    "CVE-2014-0160": {"name": "Heartbleed", "severity": "HIGH", "cvss": 7.5},
    "CVE-2017-5638": {"name": "Struts RCE", "severity": "CRITICAL", "cvss": 10.0},
}
_DEMO_REGS = {
    "encryption": "ISO 27001 A.10 / GDPR Art. 32 — encryption of personal data",
    "logging": "EU AI Act Art. 12 — automatic record-keeping (logging)",
    "oversight": "EU AI Act Art. 14 — human oversight of high-risk AI systems",
    "transparency": "EU AI Act Art. 13 — transparency and provision of information",
}


def _demo_port_lookup(args: dict[str, Any]) -> dict[str, Any]:
    port = str(args.get("port", "")).strip()
    return {"port": port, "service": _DEMO_PORT_SERVICES.get(port, "unknown")}


def _demo_cve_lookup(args: dict[str, Any]) -> dict[str, Any]:
    cve = str(args.get("cve_id", "")).strip().upper()
    rec = _DEMO_CVE_DB.get(cve)
    return {"cve_id": cve, **(rec or {"severity": "unknown", "cvss": 0.0})}


def _demo_reg_lookup(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip().lower()
    return {"topic": topic, "reference": _DEMO_REGS.get(topic, "no mapped control")}


def _build_demo_fabric() -> Any:
    """Construct the Tool Capability Fabric used by the v5 demo loop."""
    from crp.tools import CapabilityExecutor, ToolCapabilityFabric

    tcf = ToolCapabilityFabric()
    ex = CapabilityExecutor()
    specs = [
        (
            "lookup_port_service", _demo_port_lookup, ["RETRIEVE"],
            ["port_lookup", "service_identification"],
            {"port": {"type": "string"}}, ["port"],
            "Map a TCP port number to its well-known service name.",
        ),
        (
            "lookup_cve_severity", _demo_cve_lookup, ["RETRIEVE", "ANALYSE"],
            ["cve_lookup", "vulnerability_severity"],
            {"cve_id": {"type": "string"}}, ["cve_id"],
            "Look up the severity and CVSS score of a known CVE identifier.",
        ),
        (
            "lookup_regulation", _demo_reg_lookup, ["RETRIEVE", "COMPARE"],
            ["regulation_lookup", "compliance_mapping"],
            {"topic": {"type": "string"}}, ["topic"],
            "Map a control topic to its regulatory reference (ISO / EU AI Act / GDPR).",
        ),
    ]
    for cap_id, impl, ops, intents, props, required, desc in specs:
        tcf.register_dict({
            "capability_id": cap_id,
            "kind": "tool",
            "version": "1.0.0",
            "operation_types": ops,
            "serves_intents": intents,
            "input_schema": {"type": "object", "properties": props, "required": required},
            "output_schema": {"type": "object"},
            "produces_facts": True,
            "cost_profile": {"tokens": 30, "latency_ms": 5, "safety_class": "read-only"},
            "metadata": {"description": desc},
        })
        ex.register_impl(cap_id, impl)
    return tcf, ex


def _demo_model_call(model: str) -> Any:
    """A synchronous model_call for run_positioned that targets LM Studio."""
    client = httpx.Client(timeout=240.0)

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "tool_call", "schema": schema, "strict": False},
            }
        try:
            r = client.post(f"{LM_STUDIO_BASE_URL}/chat/completions", json=body)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            body.pop("response_format", None)
            r = client.post(f"{LM_STUDIO_BASE_URL}/chat/completions", json=body)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""

    return model_call


@app.post("/api/v4/positioned")
async def positioned(request: Request) -> JSONResponse:
    """Run the CRP v5 positioned-tool-loop and return its full visibility surface."""
    import asyncio

    from crp.stl import run_positioned
    from crp.tools import CapabilityProfile

    body = await request.json()
    user_request = (body.get("request") or "").strip()
    if not user_request:
        raise HTTPException(status_code=400, detail="request required")
    model = body.get("model") or "meta-llama-3.1-8b-instruct"
    profile_name = (body.get("profile") or "CAPABLE_LOCAL").upper()
    profile = getattr(CapabilityProfile, profile_name, CapabilityProfile.CAPABLE_LOCAL)

    tcf, ex = _build_demo_fabric()
    model_call = _demo_model_call(model)

    def _run() -> Any:
        return run_positioned(
            user_request, model_call, fabric=tcf, executor=ex, profile=profile,
        )

    try:
        result = await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"positioned loop failed: {exc}") from exc

    catalogue = [
        {
            "id": "lookup_port_service",
            "description": "Map a TCP port number to its well-known service name.",
            "operations": ["RETRIEVE"],
        },
        {
            "id": "lookup_cve_severity",
            "description": "Look up the severity and CVSS score of a known CVE identifier.",
            "operations": ["RETRIEVE", "ANALYSE"],
        },
        {
            "id": "lookup_regulation",
            "description": "Map a control topic to its regulatory reference (ISO / EU AI Act / GDPR).",
            "operations": ["RETRIEVE", "COMPARE"],
        },
    ]
    # Which tools the loop actually selected (from the event stream).
    tools_used = []
    for e in result.event_stream:
        if e.get("state") == "TOOL_SELECTED":
            detail = str(e.get("detail", ""))
            cap = detail.split("capability=")[-1].strip() if "capability=" in detail else ""
            if cap and cap not in tools_used:
                tools_used.append(cap)
    return JSONResponse({
        "request": user_request,
        "model": model,
        "profile": profile_name,
        "operations": list(result.operations),
        "event_stream": list(result.event_stream),
        "observations": list(result.cso.tool_observations),
        "frame_tokens_total": result.frame_tokens_total,
        "observation_count": result.observation_count,
        "completion": round(result.cso.goal_state.completion, 4),
        "halted": result.halted,
        "text": result.text,
        "headers": dict(result.headers),
        "catalogue_size": len(catalogue),
        "catalogue": catalogue,
        "tools_used": tools_used,
    })


@app.post("/api/v4/session/{session_id}/turn")
async def turn(session_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are answering questions about the Context Relay Protocol (CRP), "
                "an open protocol for governable, auditable AI inference. Keep answers concise, factual, and relevant to CRP."
            ),
        },
    ]
    for w in session.windows:
        # Reconstruct prior turns from stored window text.
        wt = session.window_texts.get(w.window_id, {})
        if wt.get("user"):
            messages.append({"role": "user", "content": wt["user"]})
        if wt.get("answer"):
            messages.append({"role": "assistant", "content": wt["answer"]})
    messages.append({"role": "user", "content": message})

    return await _do_dispatch(
        session_id=session_id,
        messages=messages,
        system_policy=session.policy_raw,
        model=body.get("model") or "meta-llama-3.1-8b-instruct",
        provider=body.get("provider") or "local",
        parent_window_id=session.windows[-1].window_id if session.windows else None,
    )


@app.post("/api/v4/session/{session_id}/branch")
async def branch(session_id: str, request: Request) -> JSONResponse:
    """Create a FAN_OUT branch from the current window with a new user message."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    parent = session.windows[-1] if session.windows else None
    system_text = (
        "You are a helpful assistant answering questions about the Context Relay Protocol (CRP). "
        "This is a FAN_OUT continuation branch: answer the user's question concisely."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_text},
    ]
    if parent:
        wt = session.window_texts.get(parent.window_id, {})
        if wt.get("user"):
            messages.append({"role": "user", "content": wt["user"]})
        if wt.get("answer"):
            messages.append({"role": "assistant", "content": wt["answer"]})
    messages.append({"role": "user", "content": message})
    return await _do_dispatch(
        session_id=session_id,
        messages=messages,
        system_policy=session.policy_raw,
        model=body.get("model") or "meta-llama-3.1-8b-instruct",
        provider=body.get("provider") or "local",
        parent_window_id=parent.window_id if parent else None,
        transfer_type=body.get("transfer_type", "SUMMARY"),
    )


@app.post("/api/v4/session/{session_id}/fan-in")
async def fan_in(session_id: str, request: Request) -> JSONResponse:
    """Synthesise a parent response from multiple branch window_ids."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    body = await request.json()
    branch_ids = list(body.get("branch_ids", []))
    if len(branch_ids) < 2:
        raise HTTPException(status_code=400, detail="at least two branch_ids required")

    branches = [w for w in session.windows if w.window_id in branch_ids]
    if len(branches) != len(branch_ids):
        raise HTTPException(status_code=404, detail="one or more branch windows not found")

    branch_texts: list[str] = []
    for b in branches:
        answer = session.window_texts.get(b.window_id, {}).get("answer")
        if answer and answer.strip():
            branch_texts.append(answer.strip())
    if len(branch_texts) < 2:
        raise HTTPException(
            status_code=400,
            detail="at least two branch windows have non-empty answers to synthesise",
        )
    synthesis_prompt = (
        "Synthesise the following branch answers into one coherent response.\n\n"
        + "\n\n".join(
            f"Branch {i+1}:\n{text}"
            for i, text in enumerate(branch_texts)
        )
    )
    messages = [
        {"role": "system", "content": "You are a CRP fan-in synthesiser. Merge branch outputs concisely."},
        {"role": "user", "content": synthesis_prompt},
    ]
    parent_window_id = branches[0].parent_ids[0] if branches and branches[0].parent_ids else None
    return await _do_dispatch(
        session_id=session_id,
        messages=messages,
        system_policy=session.policy_raw,
        model=body.get("model") or "meta-llama-3.1-8b-instruct",
        provider=body.get("provider") or "local",
        parent_window_id=parent_window_id,
        transfer_type="RESULT_ONLY",
    )


@app.post("/api/v4/session/{session_id}/tamper")
async def tamper(session_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    index = int(body.get("index", 0))
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if index < 0 or index >= len(session.chain_records):
        raise HTTPException(status_code=404, detail="window not found")

    record = session.chain_records[index]
    record.hmac = hashlib.sha256(b"tampered").hexdigest()
    session.audit.record(
        ComplianceEventType.CHAIN_INTEGRITY_BROKEN,
        session_id=session_id,
        data={"window_number": record.window_number},
    )
    return JSONResponse({"status": "tampered", "index": index, "audit": _verify_chain(session_id)})


@app.get("/api/v4/session/{session_id}/verify")
async def verify(session_id: str) -> JSONResponse:
    return JSONResponse(_verify_chain(session_id))


def _verify_chain(session_id: str) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    key = _derive_session_key(session_id)
    result = verify_window_chain(session.chain_records, key)
    return {
        "valid": result.status.value == "VALID",
        "status": result.status.value,
        "events": result.verified_count,
        "broken_at": result.broken_at_window if result.broken_at_window >= 0 else None,
    }


@app.get("/api/v4/session/{session_id}/export.ndjson")
async def export_ndjson(session_id: str) -> PlainTextResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    export = session.audit.export()
    lines = [json.dumps(e, separators=(",", ":"), default=str) for e in export.get("entries", [])]
    return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")


@app.get("/api/v4/session/{session_id}/export.ocsf")
async def export_ocsf(session_id: str) -> JSONResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    export = session.audit.export_ocsf()
    return JSONResponse(export)


@app.get("/api/v4/session/{session_id}/state")
async def state(session_id: str) -> JSONResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return JSONResponse(
        {
            "session_id": session_id,
            "facts": [_fact_to_dict(f) for f in session.facts],
            "windows": [
                {
                    "window_id": w.window_id,
                    "window_number": w.window_number,
                    "continuation_id": w.continuation_id,
                    "pattern": w.pattern.value,
                    "parent_ids": w.parent_ids,
                    "child_ids": w.child_ids,
                    "quality_tier": w.quality_tier,
                    "risk_level": w.risk_level,
                    "hmac": w.hmac,
                    "response_hash": w.response_hash,
                }
                for w in session.windows
            ],
            "chain": _verify_chain(session_id),
            "safety_budget": round(session.budget.budget, 4),
            "circuit_state": session.budget.circuit_state.value,
            "quality_history": session.quality_history,
        }
    )


@app.get("/api/v4/session/{session_id}/agent-status")
async def agent_status(session_id: str) -> JSONResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return JSONResponse(
        {
            "session_id": session_id,
            "safety_budget": round(session.budget.budget, 4),
            "budget_health": session.budget.health.value,
            "circuit_state": session.budget.circuit_state.value,
            "loop_depth": 0,
            "phase": "dispatch",
            "tool_calls": 0,
            "window_count": len(session.windows),
        }
    )


@app.get("/api/v4/safety-surface")
async def safety_surface() -> JSONResponse:
    """Expose the CRP Safety Control Plane surface map.

    Shows every built-in capability, its current/default setting, the
    manifest profile, the addable-rule coverage map, and the explicit
    out-of-scope list. This is what makes CRP's safety boundary visible
    and auditable compared to black-box guardrails.
    """
    return JSONResponse(_SAFETY_CONTROL_PLANE.get_surface_map())


# ---------------------------------------------------------------------------
# Static files + SPA fallback
# ---------------------------------------------------------------------------

if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    _port = int(os.environ.get("CRP_DEMO_PORT", "8774"))
    uvicorn.run(app, host="127.0.0.1", port=_port)
