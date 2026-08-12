# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP demo pipeline — the governance brain behind both demo apps.

This module contains *all* the Context Relay Protocol integration logic the
two browser demos rely on. It is deliberately framework-free (stdlib only) so
the demos stay "clone and run". Three public entry points:

* :func:`detect_runtime` — discover local LLMs and their capabilities.
* :func:`run_safety_pipeline` — App 1: prompt-injection shield, grounded
  generation, Decision Provenance Engine, policy enforcement (HTTP 451 halt),
  tamper-evident audit trail, and the full ``CRP-*`` response-header set.
* The :class:`ContextSessionStore` — App 2: stateful multi-window
  conversation with CKF fact accumulation, an HMAC window chain (with a
  tamper button), session tokens, and per-window CRP headers.

Every signal shown in the UI is computed by the *real* ``crp`` package — there
are no mocks.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import uuid
from typing import Any

from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
from crp.core.context_source import ContextSource, SourceKind, TrustLevel
from crp.core.context_enforcer import detect_injection_signals
from crp.envelope.packer import PackedFact
from crp.extraction.types import Fact
from crp.headers.emit import emit_headers
from crp.headers.halt import HaltReason, build_halt_response
from crp.policy.enforce import enforce_policy, extract_signals
from crp.policy.grammar import parse_policy
from crp.provenance import (
    DecisionProvenanceEngine,
    ProvenanceConfig,
    collect_quality_headers,
)
from crp.provenance.window_chain import (
    WindowChainRecord,
    WindowHmacInput,
    build_window_hmac,
    verify_window_chain,
)
from crp.providers.discovery import DetectedModel, discover_local_llms
from crp.providers.llamacpp import LlamaCppAdapter
from crp.providers.ollama import OllamaAdapter
from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType
from crp.security.session_token import format_set_session_header, issue_token

PROTOCOL_VERSION = "3.0"

# The demos run the DPE in pure-lexical mode: the optional cross-encoder NLI
# model (sentence-transformers / torch) is disabled so the apps stay
# "clone and run" with zero heavyweight ML dependencies. Grounding,
# fabrication and risk are all still computed from lexical attribution.
_DEMO_DPE_CONFIG = ProvenanceConfig(entailment_enabled=False)


# ───────────────────────────── LLM detection ────────────────────────────────

def detect_runtime() -> dict[str, Any]:
    """Discover every local LLM runtime and return a UI-ready report."""
    report = discover_local_llms(timeout=2.5)
    primary = report.primary_model()
    return {
        "any_reachable": report.any_reachable,
        "runtimes": [r.to_dict() for r in report.runtimes],
        "models": [m.to_dict() for m in report.models],
        "loaded_models": [m.to_dict() for m in report.loaded_models],
        "primary": primary.to_dict() if primary else None,
        "guidance": _detection_guidance(report.primary_model(), report.any_reachable),
    }


def _detection_guidance(primary: DetectedModel | None, reachable: bool) -> str:
    if not reachable:
        return (
            "No local LLM runtime detected. Start LM Studio (Developer → Start "
            "Server on port 1234) or run `ollama serve`, load a model, then "
            "refresh. CRP works without a model too — governance signals are "
            "still computed, but generation is skipped."
        )
    if primary is None:
        return "A runtime is reachable but no chat model is loaded. Load one to generate."
    bits = [f"Detected **{primary.id}** on {primary.runtime.value}."]
    if primary.max_context_length:
        bits.append(f"Max context {primary.max_context_length:,} tokens.")
    if primary.loaded_context_length:
        util = primary.context_utilisation
        pct = f" ({util * 100:.1f}% of max allocated)" if util else ""
        bits.append(f"Loaded window {primary.loaded_context_length:,} tokens{pct}.")
    caps = []
    if primary.supports_tools:
        caps.append("tool/function calling")
    if primary.is_reasoning_model:
        caps.append("extended reasoning")
    if primary.is_vision_model:
        caps.append("vision")
    if caps:
        bits.append("Capabilities: " + ", ".join(caps) + ".")
    return " ".join(bits)


def _provider_for(primary: DetectedModel | None) -> Any | None:
    """Build a CRP provider adapter for the detected primary model."""
    if primary is None:
        return None
    runtime = primary.runtime.value
    if runtime == "ollama":
        return OllamaAdapter(model=primary.id, base_url=primary.endpoint)
    # LM Studio + llama.cpp + generic OpenAI-compatible all speak the
    # OpenAI chat API that LlamaCppAdapter's HTTP mode targets.
    ctx = primary.loaded_context_length or 4096
    return LlamaCppAdapter(server_url=primary.endpoint, context_size=ctx, max_tokens=512)


def _generate(provider: Any | None, messages: list[dict[str, str]]) -> tuple[str, str]:
    if provider is None:
        return ("", "no-model")
    try:
        text, reason = provider.generate_chat(messages)
        return (text or "", reason or "stop")
    except Exception as exc:  # noqa: BLE001 — demo must degrade gracefully
        return (f"[generation failed: {exc}]", "error")


# ───────────────────────── shared helpers ───────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _facts_from_text(text: str, category: str) -> list[Fact]:
    """Split text into coarse 'facts' — one per sentence — for the demos."""
    facts: list[Fact] = []
    for chunk in _SENTENCE_RE.split(text.strip()):
        chunk = chunk.strip()
        if len(chunk) >= 12:
            facts.append(Fact(text=chunk, category=category, confidence=0.9))
    return facts


def _packed_from_facts(facts: list[Fact]) -> list[PackedFact]:
    return [
        PackedFact(fact_id=f.id, text=f.text, score=f.confidence or 0.5,
                   tokens=max(1, len(f.text) // 4))
        for f in facts
    ]


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# ════════════════════════════ APP 1: SAFETY ═════════════════════════════════

# A sensible default EU-AI-Act-aligned policy for the console.
DEFAULT_SAFETY_POLICY = (
    "default-src context; halt-on CRITICAL; warn-on HIGH; "
    "require-grounding 0.70; require-quality S A B C"
)


def run_safety_pipeline(
    *,
    system_prompt: str,
    question: str,
    context_facts: list[str],
    policy_str: str,
) -> dict[str, Any]:
    """App 1 — run a full governed generation and return every CRP signal."""
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    signing_key = os.urandom(32)
    audit = ComplianceAuditTrail(signing_key=signing_key, session_id=session_id)
    audit.record(ComplianceEventType.SESSION_CREATED, data={"app": "safety-console"})

    # 1) Detect the model we are about to govern.
    report = discover_local_llms(timeout=2.5)
    primary = report.primary_model()
    provider = _provider_for(primary)

    # 2) Prompt-injection shield over the *trusted* envelope inputs.
    user_src = ContextSource(
        kind=SourceKind.USER_TURN, source_id="end-user",
        trust_level=TrustLevel.TRUSTED,
    )
    injection = detect_injection_signals(question, user_src, only_trusted=True)
    sys_src = ContextSource(
        kind=SourceKind.SYSTEM_PROMPT, source_id="app-system-prompt",
        trust_level=TrustLevel.TRUSTED,
    )
    injection += detect_injection_signals(system_prompt, sys_src, only_trusted=True)
    if injection:
        audit.record(
            ComplianceEventType.INJECTION_DETECTED,
            data={"count": len(injection),
                  "patterns": [s.pattern_id for s in injection]},
        )
    audit.record(ComplianceEventType.DATA_INGESTED,
                 data={"facts": len(context_facts), "question_len": len(question)})

    # 3) Build the grounded envelope + call the LLM.
    facts = [Fact(text=f.strip(), category="context", confidence=0.95)
             for f in context_facts if f.strip()]
    packed = _packed_from_facts(facts)
    context_block = "\n".join(f"- {f.text}" for f in facts) or "(no context provided)"
    messages = [
        {"role": "system",
         "content": (system_prompt or "You are a careful assistant.")
         + "\n\nUse ONLY the following context to answer. If the context does "
           "not contain the answer, say you do not know.\n\nCONTEXT:\n"
         + context_block},
        {"role": "user", "content": question},
    ]
    t0 = time.time()
    output, finish_reason = _generate(provider, messages)
    gen_ms = round((time.time() - t0) * 1000)
    audit.record(ComplianceEventType.LLM_CALL_COMPLETED,
                 data={"model": primary.id if primary else None,
                       "finish_reason": finish_reason, "latency_ms": gen_ms})

    # 4) Decision Provenance Engine — grounding / fabrication / risk.
    dpe = DecisionProvenanceEngine(config=_DEMO_DPE_CONFIG)
    window_id = "w1"
    if output and finish_reason not in ("error", "no-model"):
        dpe_report = dpe.analyse(
            output, packed, session_id=session_id, window_id=window_id,
            query=question, window_number=1,
        )
    else:
        dpe_report = dpe.analyse("", packed, session_id=session_id,
                                 window_id=window_id, query=question)

    audit.record(ComplianceEventType.RISK_ASSESSMENT, data={
        "grounding_ratio": dpe_report.grounding_ratio,
        "fabrication_count": getattr(dpe_report.fidelity, "fabrication_count", 0),
    })

    # 5) Policy enforcement → PolicyDecision (may HALT with HTTP 451).
    policy = parse_policy(policy_str or DEFAULT_SAFETY_POLICY)
    signals = extract_signals(provenance=dpe_report, quality=dpe_report)
    decision = enforce_policy(policy, signals)

    risk_report = dpe_report.risk_report
    risk_level = str(getattr(getattr(risk_report, "window_risk_level", None),
                             "value", "UNKNOWN"))
    hallucination_risk = risk_level

    halt_payload: dict[str, Any] | None = None
    http_status = 200
    if decision.halted:
        http_status = 451
        reason = (HaltReason.UNACCEPTABLE_EU_AI_ACT
                  if risk_level in ("CRITICAL", "HIGH")
                  else HaltReason.CRITICAL_HALLUCINATION_RISK)
        halt = build_halt_response(
            reason=reason, session_id=session_id,
            audit_trail_uri=f"/api/safety/audit/{session_id}",
            oversight_required=True, hallucination_risk=hallucination_risk,
        )
        halt_payload = {"http_status": halt.http_status, "body": halt.body,
                        "headers": halt.headers}
        audit.record(ComplianceEventType.OVERSIGHT_HALT,
                     data={"reason": reason.value, "risk": risk_level})

    # 6) Emit the full CRP response-header set.
    quality_headers = collect_quality_headers(dpe_report)
    headers = emit_headers(
        provenance=dpe_report, quality=dpe_report, session_id=session_id,
        window=1, protocol_version=PROTOCOL_VERSION,
        audit_trail_id=session_id,
        audit_trail_uri=f"/api/safety/audit/{session_id}",
        policy_applied=policy_str or DEFAULT_SAFETY_POLICY,
    )
    headers.update(quality_headers)
    headers.update(decision.headers)
    if halt_payload:
        headers.update(halt_payload["headers"])

    chain_ok, broken_at = audit.verify_chain()

    fidelity = dpe_report.fidelity
    return {
        "session_id": session_id,
        "http_status": http_status,
        "detected_model": primary.to_dict() if primary else None,
        "generation": {"output": output, "finish_reason": finish_reason,
                       "latency_ms": gen_ms},
        "injection_signals": [
            {"pattern_id": s.pattern_id, "severity": s.severity,
             "excerpt": s.excerpt} for s in injection
        ],
        "provenance": {
            "grounding_ratio": dpe_report.grounding_ratio,
            "total_claims": dpe_report.total_claims,
            "context_grounded_count": dpe_report.context_grounded_count,
            "parametric_count": dpe_report.parametric_count,
            "mixed_count": dpe_report.mixed_count,
            "uncertain_count": dpe_report.uncertain_count,
            "fabrication_count": getattr(fidelity, "fabrication_count", 0),
            "distortion_count": getattr(fidelity, "distortion_count", 0),
            "fidelity_score": getattr(fidelity, "fidelity_score", None),
            "risk_level": risk_level,
            "mean_risk_score": getattr(risk_report, "mean_risk_score", None),
            "critical_risk_count": getattr(risk_report, "critical_risk_count", 0),
            "quality_tier": dpe_report.quality_tier,
        },
        "decision": {
            "action": decision.action.value,
            "halted": decision.halted,
            "http_status": decision.http_status,
            "violations": [
                {"directive": v.directive,
                 "type": v.violation_type.value,
                 "action": v.action.value,
                 "detail": v.detail} for v in decision.violations
            ],
        },
        "halt_response": halt_payload,
        "headers": headers,
        "audit": {
            "entry_count": audit.entry_count,
            "chain_valid": chain_ok,
            "broken_at": broken_at,
            "entries": [e.to_dict() for e in audit.query()],
            "ocsf_sample": audit.export_ocsf(
                provider=(primary.runtime.value if primary else "none"),
                model=(primary.id if primary else "none"),
            ),
        },
        "policy": policy_str or DEFAULT_SAFETY_POLICY,
    }


# ════════════════════════ APP 2: CONTEXT / PROVENANCE ═══════════════════════

class _Session:
    """In-memory state for one context-management conversation."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.signing_key = os.urandom(32)
        self.master_key = os.urandom(32)
        self.ckf = ContextualKnowledgeFabric(config=CKFConfig())
        self.audit = ComplianceAuditTrail(signing_key=self.signing_key,
                                          session_id=session_id)
        self.records: list[WindowChainRecord] = []
        self.window_number = 0
        self.fact_ids: list[str] = []
        self.history: list[dict[str, str]] = []
        self.turns: list[dict[str, Any]] = []
        self.audit.record(ComplianceEventType.SESSION_CREATED,
                          data={"app": "context-explorer"})


class ContextSessionStore:
    """Thread-safe registry of context-management demo sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def _get(self, session_id: str) -> _Session:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is None:
                sess = _Session(session_id)
                self._sessions[session_id] = sess
            return sess

    def new_session(self) -> dict[str, Any]:
        session_id = f"ctx-{uuid.uuid4().hex[:12]}"
        self._get(session_id)
        report = discover_local_llms(timeout=2.5)
        primary = report.primary_model()
        return {
            "session_id": session_id,
            "detected_model": primary.to_dict() if primary else None,
            "guidance": _context_guidance(primary),
        }

    def turn(self, session_id: str, message: str) -> dict[str, Any]:
        sess = self._get(session_id)
        report = discover_local_llms(timeout=2.5)
        primary = report.primary_model()
        provider = _provider_for(primary)

        sess.window_number += 1
        wnum = sess.window_number
        window_id = f"w{wnum}"

        # 1) Retrieve prior facts from the CKF as grounding context.
        retrieved: list[dict[str, Any]] = []
        if sess.fact_ids:
            merge = sess.ckf.retrieve(
                seed_ids=set(sess.fact_ids[-12:]),
                modes=["graph_walk", "pattern"],
                budget=12,
            )
            retrieved = [
                {"text": mf.fact.text, "score": round(mf.score, 4)}
                for mf in merge.facts[:8]
            ]

        # 2) Generate a reply grounded in retrieved memory.
        context_block = "\n".join(f"- {r['text']}" for r in retrieved)
        sys = ("You are a helpful assistant with persistent memory. "
               "Use the remembered facts when relevant.")
        if context_block:
            sys += "\n\nREMEMBERED FACTS:\n" + context_block
        messages = [{"role": "system", "content": sys}]
        messages += sess.history[-6:]
        messages.append({"role": "user", "content": message})
        t0 = time.time()
        reply, finish_reason = _generate(provider, messages)
        gen_ms = round((time.time() - t0) * 1000)
        sess.history.append({"role": "user", "content": message})
        if reply:
            sess.history.append({"role": "assistant", "content": reply})

        # 3) Extract facts from this turn and store them in the CKF.
        new_facts = _facts_from_text(message, "user_statement")
        new_facts += _facts_from_text(reply, "assistant_claim")
        if new_facts:
            sess.ckf.store(new_facts, window_id=window_id)
            sess.fact_ids.extend(f.id for f in new_facts)
            sess.audit.record(ComplianceEventType.FACTS_EXTRACTED,
                              data={"count": len(new_facts), "window": window_id})

        # 4) Extend the HMAC window chain (tamper-evident provenance).
        response_hash = _sha256(reply or message)
        dpe_report_hash = _sha256(f"{wnum}:{len(new_facts)}:{len(retrieved)}")
        timestamp = f"{time.time():.3f}"
        prev_hmac = sess.records[-1].hmac if sess.records else ""
        whmac = build_window_hmac(
            WindowHmacInput(
                session_id=session_id, window_number=wnum, timestamp=timestamp,
                response_hash=response_hash, dpe_report_hash=dpe_report_hash,
                prev_window_hmac=prev_hmac,
            ),
            sess.signing_key,
        )
        record = WindowChainRecord(
            session_id=session_id, window_number=wnum, timestamp=timestamp,
            response_hash=response_hash, dpe_report_hash=dpe_report_hash,
            hmac=whmac,
        )
        sess.records.append(record)
        sess.audit.record(ComplianceEventType.WINDOW_HMAC_GENERATED,
                          data={"window": wnum, "hmac": whmac[:23] + "…"})

        verification = verify_window_chain(sess.records, sess.signing_key)

        # 5) Issue / refresh the session token (carries the chain tip).
        ckf_hash = _sha256(",".join(sess.fact_ids))[:23]
        token, payload = issue_token(
            session_id=session_id, master_key=sess.master_key, window=wnum,
            chain_tip=whmac, ckf_hash=ckf_hash, strategy="incremental",
            safety_budget=round(max(0.0, 1.0 - wnum * 0.05), 2),
        )
        set_session = format_set_session_header(token, payload)

        # 6) ETag over the CKF state + full CRP header set.
        etag = '"' + hashlib.sha256(",".join(sess.fact_ids).encode()).hexdigest()[:16] + '"'
        headers = emit_headers(
            session_id=session_id, window=wnum,
            protocol_version=PROTOCOL_VERSION, strategy="incremental",
            etag=etag, window_hmac=whmac,
            chain_integrity=verification.status.value,
            audit_trail_id=session_id,
            audit_trail_uri=f"/api/context/audit/{session_id}",
            set_session=set_session,
        )

        turn_view = {
            "window_number": wnum,
            "user_message": message,
            "reply": reply,
            "finish_reason": finish_reason,
            "latency_ms": gen_ms,
            "retrieved_facts": retrieved,
            "new_facts": [{"text": f.text, "category": f.category} for f in new_facts],
            "window_hmac": whmac,
            "prev_window_hmac": prev_hmac,
            "response_hash": response_hash,
        }
        sess.turns.append(turn_view)

        chain_ok, _ = sess.audit.verify_chain()
        return {
            "session_id": session_id,
            "detected_model": primary.to_dict() if primary else None,
            "turn": turn_view,
            "chain": _chain_view(sess, verification),
            "ckf": {
                "total_facts": len(sess.fact_ids),
                "facts_this_window": len(new_facts),
                "retrieved": len(retrieved),
            },
            "context_pressure": _context_pressure(primary, sess),
            "token": {
                "set_session_header": set_session,
                "window": payload.win,
                "safety_budget": payload.sb,
                "chain_tip": payload.ct[:23] + "…",
            },
            "headers": headers,
            "audit": {"entry_count": sess.audit.entry_count, "chain_valid": chain_ok},
        }

    def tamper(self, session_id: str, window_number: int) -> dict[str, Any]:
        """Corrupt a window's response hash and re-verify → BROKEN."""
        sess = self._get(session_id)
        target = next((r for r in sess.records
                       if r.window_number == window_number), None)
        if target is None:
            return {"error": f"window {window_number} not found"}
        original = target.response_hash
        target.response_hash = _sha256("TAMPERED:" + original)
        verification = verify_window_chain(sess.records, sess.signing_key)
        sess.audit.record(ComplianceEventType.CHAIN_INTEGRITY_BROKEN,
                          data={"tampered_window": window_number,
                                "broken_at": verification.broken_at_window})
        return {
            "session_id": session_id,
            "tampered_window": window_number,
            "chain": _chain_view(sess, verification),
        }

    def state(self, session_id: str) -> dict[str, Any]:
        sess = self._get(session_id)
        verification = verify_window_chain(sess.records, sess.signing_key)
        return {
            "session_id": session_id,
            "turns": sess.turns,
            "chain": _chain_view(sess, verification),
            "ckf": {"total_facts": len(sess.fact_ids)},
        }


def _chain_view(sess: _Session, verification: Any) -> dict[str, Any]:
    return {
        "status": verification.status.value,
        "broken_at_window": verification.broken_at_window,
        "verified_count": verification.verified_count,
        "windows": [
            {"window_number": r.window_number,
             "hmac": r.hmac,
             "response_hash": r.response_hash,
             "prev_hmac": (sess.records[i - 1].hmac if i > 0 else "")}
            for i, r in enumerate(sess.records)
        ],
    }


def _context_pressure(primary: DetectedModel | None, sess: _Session) -> dict[str, Any]:
    """Illustrate *why* context management matters for this model."""
    if primary is None:
        return {"available": False}
    loaded = primary.loaded_context_length or 0
    maximum = primary.max_context_length or 0
    # Rough token estimate of the raw conversation if nothing were managed.
    raw_chars = sum(len(m["content"]) for m in sess.history)
    raw_tokens = raw_chars // 4
    return {
        "available": True,
        "loaded_context_length": loaded,
        "max_context_length": maximum,
        "context_utilisation": primary.context_utilisation,
        "raw_conversation_tokens": raw_tokens,
        "ckf_managed_facts": len(sess.fact_ids),
        "note": (
            f"This model exposes only {loaded:,} of its {maximum:,}-token ceiling. "
            "CRP's CKF keeps the conversation grounded by storing facts in a "
            "queryable fabric instead of replaying the whole transcript."
        ) if loaded and maximum else "",
    }


def _context_guidance(primary: DetectedModel | None) -> str:
    if primary is None:
        return ("No model loaded — chain, CKF and token signals still work, but "
                "replies will be empty. Load a model in LM Studio to chat.")
    util = primary.context_utilisation
    extra = ""
    if util and primary.max_context_length:
        extra = (f" It can handle {primary.max_context_length:,} tokens but only "
                 f"{primary.loaded_context_length:,} are allocated "
                 f"({util * 100:.1f}%) — exactly why context management matters.")
    return f"Chatting with **{primary.id}**.{extra}"
