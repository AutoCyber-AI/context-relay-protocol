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
import json
import os
import re
import threading
import time
import uuid
from typing import Any

from crp.agent.budget import AgentSafetyBudget
from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
from crp.core.app_profile import ContextStrategy
from crp.core.context_enforcer import detect_injection_signals
from crp.core.context_source import ContextSource, SourceKind, TrustLevel
from crp.envelope.packer import PackedFact
from crp.extraction.types import Fact
from crp.headers.conditional import compute_etag
from crp.headers.emit import emit_headers
from crp.headers.halt import HaltReason, build_halt_response
from crp.policy.enforce import enforce_policy, extract_signals
from crp.policy.grammar import parse_policy
from crp.policy.model import RiskLevel
from crp.provenance import (
    DecisionProvenanceEngine,
    ProvenanceConfig,
    collect_quality_headers,
)
from crp.provenance.rqa_stages import detect_cross_window_contradictions
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


def _package_version() -> str:
    """Protocol version label — tracks the live ``crp`` package version.

    ``crp.__version__`` is checked first so editable installs report the
    current source tree; ``importlib.metadata`` is the fallback for regular
    installs (where it matches the installed distribution).
    """
    try:
        from crp._version import __version__
        return __version__
    except Exception:  # noqa: BLE001 — fall back to installed distribution
        from importlib.metadata import version
        return version("crprotocol")


PROTOCOL_VERSION = _package_version()

# The demos run the DPE in pure-lexical mode: the optional cross-encoder NLI
# model (sentence-transformers / torch) is disabled so the apps stay
# "clone and run" with zero heavyweight ML dependencies. Grounding,
# fabrication and risk are all still computed from lexical attribution.
_DEMO_DPE_CONFIG = ProvenanceConfig(entailment_enabled=False)

# App 2 replays the last turns (sliding window) AND grounds each new window
# from the CKF fabric - the protocol's own name for that is HYBRID.
_CONTEXT_STRATEGY = ContextStrategy.HYBRID.value


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
            "refresh. CRP works without a model too - governance signals are "
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
    # Generous ceiling for the non-streaming fallback path only; the streaming
    # path sends no cap at all and lets the server stop naturally.
    return LlamaCppAdapter(server_url=primary.endpoint, context_size=ctx, max_tokens=8192)


def _generate(provider: Any | None, messages: list[dict[str, str]]) -> tuple[str, str]:
    if provider is None:
        return ("", "no-model")
    try:
        text, reason = provider.generate_chat(messages)
        return (text or "", reason or "stop")
    except Exception as exc:  # noqa: BLE001 — demo must degrade gracefully
        return (f"[generation failed: {exc}]", "error")


def stream_generate(
    primary: DetectedModel | None,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
) -> Any:
    """Stream a chat completion from the detected runtime.

    A generator yielding ``("reasoning", delta)`` and ``("content", delta)``
    tuples as tokens arrive, then a final ``("done", {text, finish_reason,
    gen_ms})`` tuple. Falls back to non-streaming for runtimes without an
    OpenAI-compatible SSE endpoint (Ollama's native API) or when no model is
    loaded, so callers can treat every runtime uniformly.

    No token budget is imposed: the server runs the model to its natural
    stop and reports ``finish_reason`` (``stop`` / ``length``), which is the
    honest behaviour for a protocol demo - CRP governs, it does not truncate.
    ``extra_body`` is merged into the request payload (LM Studio extras such
    as ``chat_template_kwargs`` ride through here).
    """
    if primary is None:
        yield ("done", {"text": "", "finish_reason": "no-model", "gen_ms": 0})
        return
    if primary.runtime.value == "ollama":
        t0 = time.time()
        text, reason = _generate(_provider_for(primary), messages)
        yield ("done", {"text": text, "finish_reason": reason,
                        "gen_ms": round((time.time() - t0) * 1000)})
        return
    import urllib.request

    base = primary.endpoint.rstrip("/")
    url = base + "/v1/chat/completions"
    request_body: dict[str, Any] = {
        "model": primary.id, "messages": messages, "stream": True,
    }
    if max_tokens:
        request_body["max_tokens"] = max_tokens
    if extra_body:
        request_body.update(extra_body)
    payload = json.dumps(request_body).encode("utf-8")
    t0 = time.time()
    text_parts: list[str] = []
    finish_reason = "stop"
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    content = delta.get("content")
                    if reasoning:
                        yield ("reasoning", reasoning)
                    if content:
                        text_parts.append(content)
                        yield ("content", content)
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
    except Exception as exc:  # noqa: BLE001 — degrade to an error finish
        yield ("done", {"text": f"[generation failed: {exc}]",
                        "finish_reason": "error",
                        "gen_ms": round((time.time() - t0) * 1000)})
        return
    yield ("done", {"text": "".join(text_parts), "finish_reason": finish_reason,
                    "gen_ms": round((time.time() - t0) * 1000)})


# ───────────────────────── shared helpers ───────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_RE = re.compile(r";\s+")
_CJK_RE = re.compile(
    "[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    "\uac00-\ud7af\u0e00-\u0e7f\u0400-\u04ff]")


def _cjk_fraction(text: str) -> float:
    """Fraction of non-Latin-script characters (CJK/Hangul/Thai/Cyrillic)."""
    if not text:
        return 0.0
    return len(_CJK_RE.findall(text)) / len(text)


def _facts_from_text(text: str, category: str) -> list[Fact]:
    """Split text into coarse 'facts' — one per sentence — for the demos.

    Trust is distinguished, not flattened: a user's statement is stored at
    high confidence, while a model's own claim is a *candidate* fact at
    lower confidence (it asserts, CRP does not take its word for it).
    Questions the model asks and thinking-style filler are not facts and
    are dropped."""
    facts: list[Fact] = []
    confidence = 0.9 if category == "user_statement" else 0.5
    for sentence in _SENTENCE_RE.split(text.strip()):
        # A very long sentence carries several claims; split at clause breaks.
        chunks = _CLAUSE_RE.split(sentence) if len(sentence) > 240 else [sentence]
        for chunk in chunks:
            chunk = chunk.strip(" \t-")
            if len(chunk) < 12:
                continue
            if category == "assistant_claim" and chunk.rstrip().endswith("?"):
                continue  # a question the model asked is not a fact
            facts.append(Fact(text=chunk, category=category, confidence=confidence))
    return facts


# Acronym-expansion pairs such as "CRP (Conflict Resolution Protocol)" or the
# inverse "Context Relay Protocol (CRP)". A model confidently expanding an
# acronym it was never told is the classic low-stakes hallucination; when the
# user later supplies the real expansion, the stale claim must be reconciled.
_ACRONYM_FIRST_RE = re.compile(
    r"\b([A-Z]{2,12}(?:\s+[A-Z]{2,12}){0,3})"
    r"\s*\(([A-Za-z][A-Za-z .&-]{2,48})\)")
_NAME_FIRST_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Za-z][a-z]+){1,6})"
    r"\s*\(([A-Z]{2,12})\)")


def _clean_expansion(text: str) -> str:
    """Strip leading interrogatives/articles an expansion may capture when the
    pair appears inside a question, e.g. "What is the Context Relay Protocol"."""
    return re.sub(r"^(?:(?:what|who|which)\s+(?:is|are|was|were)\s+)?(?:(?:the|a|an)\s+)",
                  "", text.strip(), flags=re.IGNORECASE)


def _norm_expansion(text: str) -> str:
    return " ".join(_clean_expansion(text).lower().split())


def _acronym_pairs(text: str) -> dict[str, str]:
    """Map acronym -> expansion found in *text* (both word orders)."""
    pairs: dict[str, str] = {}
    for acronym, expansion in _ACRONYM_FIRST_RE.findall(text):
        pairs.setdefault(acronym.strip(), _clean_expansion(expansion))
    for name, acronym in _NAME_FIRST_RE.findall(text):
        pairs.setdefault(acronym.strip(), _clean_expansion(name))
    return pairs


def _acronym_conflict(new_text: str, old_text: str) -> str | None:
    """Return a human-readable conflict if both texts expand the same acronym
    differently, else None."""
    new_pairs, old_pairs = _acronym_pairs(new_text), _acronym_pairs(old_text)
    for acronym, new_exp in new_pairs.items():
        old_exp = old_pairs.get(acronym)
        if old_exp and _norm_expansion(new_exp) != _norm_expansion(old_exp):
            return f"acronym '{acronym}' redefined: '{old_exp}' -> '{new_exp}'"
    return None


def _reconcile_turn(sess: _Session, new_facts: list[Fact],
                    window_number: int) -> list[dict[str, Any]]:
    """Self-correction: a high-trust user statement overrides earlier
    low-trust model claims it contradicts.

    Two protocol-native checks run per (new user fact, old model claim) pair:
    the cross-window contradiction detector (numeric / temporal / stance) and
    an acronym-redefinition check for definition-swap hallucinations the rule
    engine does not cover. Conflicting claims are marked superseded via the
    CKF's own supersession primitive - kept in the fabric for provenance,
    excluded from recall - and the correction is audit-logged."""
    corrections: list[dict[str, Any]] = []
    if not sess.fact_ids:
        return corrections
    by_text = {sf.fact.text: sf for sf in sess.ckf._warm.get_facts()}  # noqa: SLF001
    for nf in new_facts:
        if nf.category != "user_statement":
            continue
        new_sf = by_text.get(nf.text)
        if new_sf is None:
            continue
        for sf in sess.ckf._warm.get_facts():  # noqa: SLF001 — demo introspection
            if sf.fact.category != "assistant_claim" or sf.is_superseded:
                continue
            old_window = sf.fact.source_window_id or ""
            if old_window == f"w{window_number}":
                continue  # only reconcile against earlier windows' claims
            reason = _acronym_conflict(nf.text, sf.fact.text)
            if reason is None:
                try:
                    coherence = detect_cross_window_contradictions(
                        nf.text, [sf.fact.text])
                except Exception:  # noqa: BLE001 — reconciliation is best-effort
                    coherence = None
                if coherence is None or not coherence.contradictions:
                    continue
                reason = (f"cross-window contradiction "
                          f"({coherence.contradictions[0].contradiction_type})")
            sf.supersede(by_fact_id=new_sf.id, confidence=nf.confidence or 0.9)
            sess.superseded[sf.id] = {
                "by_window": window_number,
                "by_text": nf.text,
                "old_text": sf.fact.text,
                "reason": reason,
            }
            sess.audit.record(ComplianceEventType.CONTRADICTION_DETECTED,
                              data={"superseded_fact": sf.fact.text[:120],
                                    "reason": reason, "window": window_number})
            corrections.append({"superseded_text": sf.fact.text,
                                "correction": nf.text, "reason": reason,
                                "window": window_number})
    return corrections


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

# Which HaltReason best describes each policy ViolationType. Violations not
# listed here map to the generic SAFETY_POLICY_VIOLATION.
_HALT_REASON_BY_VIOLATION: dict[str, HaltReason] = {
    "GROUNDING_BELOW_THRESHOLD": HaltReason.GROUNDING_BELOW_THRESHOLD,
    "ENTAILMENT_BELOW_THRESHOLD": HaltReason.GROUNDING_BELOW_THRESHOLD,
    "QUALITY_TIER_REJECTED": HaltReason.QUALITY_TIER_REJECTED,
    "SOURCE_NOT_TRUSTED": HaltReason.UNTRUSTED_SOURCE,
    "UNGROUNDED_CLAIM": HaltReason.UNTRUSTED_SOURCE,
    "MIXED_CONTENT": HaltReason.UNTRUSTED_SOURCE,
    "PARAMETRIC_CONTENT": HaltReason.UNTRUSTED_SOURCE,
    "FABRICATION_DETECTED": HaltReason.CRITICAL_HALLUCINATION_RISK,
    "PII_DETECTED": HaltReason.SAFETY_POLICY_VIOLATION,
    "HALT_ON_RISK": HaltReason.CRITICAL_HALLUCINATION_RISK,
}

# Lower rank = more specific and explanatory. A concrete threshold breach
# beats the generic untrusted-source / policy umbrella.
_REASON_SPECIFICITY: dict[HaltReason | None, int] = {
    HaltReason.GROUNDING_BELOW_THRESHOLD: 0,
    HaltReason.QUALITY_TIER_REJECTED: 1,
    HaltReason.CRITICAL_HALLUCINATION_RISK: 2,
    HaltReason.UNTRUSTED_SOURCE: 3,
    HaltReason.SAFETY_POLICY_VIOLATION: 4,
    None: 5,
}


def _dominant_halt_reason(
    violations: list[Any],
    injection: list[Any],
    risk_level: str,
) -> HaltReason:
    """Pick the HaltReason that names the *real* dominant violation.

    A detected prompt injection always wins (it is the clearest signal);
    otherwise the halting violation with the most specific mapped reason
    wins (a concrete threshold breach beats the generic untrusted-source
    umbrella). Falls back to CRITICAL_HALLUCINATION_RISK for a CRITICAL-risk
    halt with no concrete violation, then SAFETY_POLICY_VIOLATION.
    """
    if injection:
        return HaltReason.PROMPT_INJECTION_DETECTED
    best: HaltReason | None = None
    for v in violations:
        if getattr(v.action, "value", v.action) != "HALT":
            continue
        vtype = getattr(v.violation_type, "value", v.violation_type)
        mapped = _HALT_REASON_BY_VIOLATION.get(str(vtype))
        # Lower rank = more specific/explanatory. Unmapped violations map to
        # the generic SAFETY_POLICY_VIOLATION (worst rank).
        rank = _REASON_SPECIFICITY.get(mapped, len(_REASON_SPECIFICITY))
        if best is None or rank < _REASON_SPECIFICITY.get(
            best, len(_REASON_SPECIFICITY)
        ):
            best = mapped
    if best is not None:
        return best
    if risk_level == "CRITICAL":
        return HaltReason.CRITICAL_HALLUCINATION_RISK
    return HaltReason.SAFETY_POLICY_VIOLATION


def run_safety_pipeline(
    *,
    system_prompt: str,
    question: str,
    context_facts: list[str],
    policy_str: str,
    token_sink: Any = None,
) -> dict[str, Any]:
    """App 1 — run a full governed generation and return every CRP signal.

    When *token_sink* is provided it is called as ``token_sink(kind, delta)``
    with live ``"reasoning"``/``"content"`` tokens as the model generates;
    governance still runs on the complete output afterwards."""
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
    if token_sink is not None:
        output, finish_reason, gen_ms = "", "stop", 0
        for kind, delta in stream_generate(primary, messages):
            if kind == "done":
                output = delta["text"]
                finish_reason = delta["finish_reason"]
                gen_ms = delta["gen_ms"]
            else:
                try:
                    token_sink(kind, delta)
                except Exception:  # noqa: BLE001 — the display sink is best-effort
                    pass
    else:
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
        reason = _dominant_halt_reason(decision.violations, injection, risk_level)
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
        self.superseded: dict[str, dict[str, Any]] = {}
        self.safety_budget = AgentSafetyBudget()
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

    def known(self, session_id: str) -> bool:
        """True only if this session exists in this server process.

        Unlike ``_get`` this never creates a session — the browser uses it to
        decide whether a restored (sessionStorage) session is still live or
        belongs to a previous server run.
        """
        with self._lock:
            return session_id in self._sessions

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

    def turn(self, session_id: str, message: str,
             token_sink: Any = None) -> dict[str, Any]:
        sess = self._get(session_id)
        report = discover_local_llms(timeout=2.5)
        primary = report.primary_model()
        provider = _provider_for(primary)

        sess.window_number += 1
        wnum = sess.window_number
        window_id = f"w{wnum}"

        # 1) Retrieve prior facts from the CKF as grounding context.
        # Superseded (corrected) facts stay in the fabric for provenance but
        # are never recalled into a later window.
        retrieved: list[dict[str, Any]] = []
        if sess.fact_ids:
            active_seed = [fid for fid in sess.fact_ids[-12:]
                           if fid not in sess.superseded]
            merge = sess.ckf.retrieve(
                seed_ids=set(active_seed),
                modes=["graph_walk", "pattern"],
                budget=12,
            )
            retrieved = [
                {"text": mf.fact.text, "score": round(mf.score, 4),
                 "category": mf.fact.category}
                for mf in merge.facts[:8]
            ]

        # 2) Generate a reply grounded in retrieved memory.
        context_block = "\n".join(f"- {r['text']}" for r in retrieved)
        sys = ("You are a helpful assistant with persistent memory. "
               "Use the remembered facts when relevant. "
               "Always respond in English, regardless of the language of the "
               "question or the remembered facts.")
        if context_block:
            sys += "\n\nREMEMBERED FACTS:\n" + context_block
        messages = [{"role": "system", "content": sys}]
        messages += sess.history[-6:]
        messages.append({"role": "user", "content": message})
        t0 = time.time()
        if token_sink is not None:
            reply, finish_reason, gen_ms = "", "stop", 0
            # No token cap: the model stops when it is done and the server
            # says so via finish_reason.
            for kind, delta in stream_generate(primary, messages):
                if kind == "done":
                    reply = delta["text"]
                    finish_reason = delta["finish_reason"]
                    gen_ms = delta["gen_ms"]
                else:
                    try:
                        token_sink(kind, delta)
                    except Exception:  # noqa: BLE001 — display sink is best-effort
                        pass
        else:
            reply, finish_reason = _generate(provider, messages)
            gen_ms = round((time.time() - t0) * 1000)
        sess.history.append({"role": "user", "content": message})
        if reply:
            sess.history.append({"role": "assistant", "content": reply})
            # Language guard (advisory): local models sometimes drift into the
            # question's language despite the English directive. Flag it in
            # the audit trail so the turn result can surface a warning.
            cjk = _cjk_fraction(reply)
            if cjk > 0.05:
                sess.audit.record(ComplianceEventType.DATA_PROCESSED, data={
                    "warning": "non_latin_script_drift",
                    "cjk_fraction": round(cjk, 4),
                    "window": window_id,
                })

        # 3) Extract facts from this turn and store them in the CKF.
        new_facts = _facts_from_text(message, "user_statement")
        new_facts += _facts_from_text(reply, "assistant_claim")
        if new_facts:
            sess.ckf.store(new_facts, window_id=window_id)
            # Sync with what the fabric actually holds: the CKF dedupes
            # identical facts, so fact_ids must not count re-stated ones.
            sess.fact_ids = [sf.id for sf in sess.ckf._warm.get_facts()]  # noqa: SLF001
            sess.audit.record(ComplianceEventType.FACTS_EXTRACTED,
                              data={"count": len(new_facts), "window": window_id})
            corrections = _reconcile_turn(sess, new_facts, wnum)
            # Re-sync: superseded facts stay in the fabric but leave the
            # active set that recall, KPIs and ETag are computed over.
            sess.fact_ids = [sf.id for sf in sess.ckf._warm.get_facts()]  # noqa: SLF001
        else:
            corrections = []

        # 3b) Real risk assessment (heuristic DPE, same engine as App 1)
        # drives the protocol's safety-budget accountant.
        risk_level: RiskLevel | None = None
        dpe_report_hash = _sha256("")
        if reply and finish_reason not in ("error", "no-model"):
            try:
                dpe = DecisionProvenanceEngine(config=_DEMO_DPE_CONFIG)
                packed = [
                    PackedFact(fact_id=_sha256(r["text"]), text=r["text"],
                               score=r["score"],
                               tokens=max(1, len(r["text"]) // 4))
                    for r in retrieved
                ]
                dpe_report = dpe.analyse(
                    reply, packed, session_id=session_id, window_id=window_id,
                    query=message, window_number=wnum,
                )
                level = str(getattr(
                    getattr(dpe_report.risk_report, "window_risk_level", None),
                    "value", "")).upper()
                if level in RiskLevel._value2member_map_:
                    risk_level = RiskLevel(level)
                dpe_report_hash = _sha256(json.dumps({
                    "grounding": dpe_report.grounding_ratio,
                    "risk": level,
                    "fabrications": getattr(dpe_report.fidelity,
                                            "fabrication_count", 0),
                }, sort_keys=True))
                sess.audit.record(ComplianceEventType.RISK_ASSESSMENT, data={
                    "grounding_ratio": dpe_report.grounding_ratio,
                    "risk_level": level, "window": window_id,
                })
            except Exception:  # noqa: BLE001 — budget accounting is best-effort
                pass
        budget_decision = sess.safety_budget.account(risk_level)

        # 4) Extend the HMAC window chain (tamper-evident provenance).
        response_hash = _sha256(reply or message)
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
            chain_tip=whmac, ckf_hash=ckf_hash, strategy=_CONTEXT_STRATEGY,
            safety_budget=sess.safety_budget.budget,
        )
        set_session = format_set_session_header(token, payload)

        # 6) ETag over the CKF state (SPEC-002 §4.8 canonical form) + headers.
        active_facts = sess.ckf._warm.get_facts()  # noqa: SLF001 — demo introspection
        etag = compute_etag((sf.id, _sha256(sf.fact.text)) for sf in active_facts)
        headers = emit_headers(
            session_id=session_id, window=wnum,
            protocol_version=PROTOCOL_VERSION, strategy=_CONTEXT_STRATEGY,
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
            "corrections": corrections,
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
                "budget_health": budget_decision.health.value,
                "circuit_state": budget_decision.circuit_state.value,
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

    def facts(self, session_id: str) -> dict[str, Any]:
        """Every fact in the session's CKF - the full fabric, not a recall slice."""
        sess = self._get(session_id)
        items = []
        for sf in sess.ckf._warm.get_facts(include_superseded=True):  # noqa: SLF001 — demo introspection
            correction = sess.superseded.get(sf.id)
            items.append({
                "id": sf.id,
                "text": sf.fact.text,
                "category": sf.fact.category,
                "confidence": sf.fact.confidence,
                "window": sf.fact.source_window_id or "",
                "superseded": bool(getattr(sf, "is_superseded", False)),
                "correction": correction,
            })
        return {"session_id": session_id, "count": len(items), "facts": items}


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
        return ("No model loaded - chain, CKF and token signals still work, but "
                "replies will be empty. Load a model in LM Studio to chat.")
    util = primary.context_utilisation
    extra = ""
    if util and primary.max_context_length:
        extra = (f" It can handle {primary.max_context_length:,} tokens but only "
                 f"{primary.loaded_context_length:,} are allocated "
                 f"({util * 100:.1f}%) - exactly why context management matters.")
    return f"Chatting with **{primary.id}**.{extra}"
