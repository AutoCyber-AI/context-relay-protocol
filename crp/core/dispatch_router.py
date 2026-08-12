# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Dispatch router mixin — all CRP dispatch strategies (§2.5, §6.5).

Extracted from orchestrator.py for maintainability. This mixin provides
all dispatch method implementations. The CRPOrchestrator inherits from
this class.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from crp.continuation.manager import ContinuationConfig, ContinuationManager
from crp.core.errors import (
    ProviderError,
    RateLimitExceededError,
    ValidationError,
)
from crp.core.session import QualityReport, SecurityFlags
from crp.core.task_intent import TaskIntent
from crp.core.window import (
    WindowMetrics,
    WindowNode,
    WindowState,
    compute_envelope_budget,
    resolve_generation_reserve,
)
from crp.security.audit_trail import ComplianceEventType

if TYPE_CHECKING:
    from crp.envelope.builder import EnvelopeResult
    from crp.extraction.types import Fact

logger = logging.getLogger("crp.orchestrator")


# ---------------------------------------------------------------------------
# Quality Tier Classification (§2.10)
# ---------------------------------------------------------------------------

def _classify_quality_tier(
    *,
    facts_extracted: int,
    continuation_windows: int,
    saturation: float,
    finish_reason: str,
    output_tokens: int,
    output_length: int,
) -> str:
    """Classify output quality into S/A/B/C/D tiers."""
    if output_length < 10 or finish_reason == "error":
        return "D"
    score = 0
    if facts_extracted >= 10:
        score += 30
    elif facts_extracted >= 5:
        score += 20
    elif facts_extracted >= 2:
        score += 10
    elif facts_extracted >= 1:
        score += 5
    if finish_reason == "stop" and continuation_windows == 0:
        score += 25
    elif finish_reason == "stop":
        score += 20
    elif continuation_windows > 0:
        score += 10
    if output_tokens >= 500:
        score += 25
    elif output_tokens >= 200:
        score += 15
    elif output_tokens >= 50:
        score += 10
    if saturation >= 0.7:
        score += 20
    elif saturation >= 0.4:
        score += 10
    elif saturation > 0:
        score += 5
    if score >= 80:
        return "S"
    elif score >= 60:
        return "A"
    elif score >= 40:
        return "B"
    elif score >= 20:
        return "C"
    else:
        return "D"


# ---------------------------------------------------------------------------
# StreamEvent (§6.10.5)
# ---------------------------------------------------------------------------

@dataclass
class StreamEvent:
    """Events emitted during streaming dispatch (§6.10.5)."""
    event_type: str
    data: Any


@dataclass
class ExtractionProgress:
    """Progress update during extraction pipeline."""
    stage: str = ""
    facts_so_far: int = 0


@dataclass
class ContinuationInfo:
    """Emitted when a streaming continuation window is triggered."""

    continuation_index: int = 0
    reason: str = ""


@dataclass
class WindowSummary:
    """Summary of a completed window."""
    window_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    wall_time_ms: int = 0


# ---------------------------------------------------------------------------
# Message assembly (§4.1, Axiom 4)
# ---------------------------------------------------------------------------

def assemble_messages(
    system_prompt: str,
    envelope: str,
    task_input: str,
    *,
    manifest: Any = None,
    observed_sources: Any = None,
    enforcer: Any = None,
) -> list[dict[str, str]]:
    """Build the chat message array sent to the LLM.

    Structural Injection Defense (§7.5.1):
      Envelope and task_input are placed in SEPARATE user messages with
      provenance boundary markers.

    Invariants (Axiom 4 — Model Ignorance):
      - system_prompt is NEVER modified
      - task_input content is NEVER modified
      - No CRP-internal protocol metadata is injected

    Context enforcement (§7.14.4, CRP 2.2):
      If *manifest* or *observed_sources* is supplied, the configured
      :class:`crp.core.context_enforcer.ContextEnforcer` runs before the
      messages are returned. When none is passed explicitly, the
      process-wide default set via
      :func:`crp.core.context_enforcer.set_default_enforcer` is used.
      Applications with no enforcer installed pay zero cost — this code
      path short-circuits.

    Parameters
    ----------
    manifest
        Optional :class:`~crp.core.context_source.ContextManifest` covering
        this turn.
    observed_sources
        Optional iterable of :class:`~crp.core.context_source.ContextSource`
        objects (or ``observed_content()`` bundles) describing what the
        envelope exposes.
    enforcer
        Optional :class:`~crp.core.context_enforcer.ContextEnforcer` to use
        for this call. Overrides the process-wide default.
    """
    # --- Enforcement pipeline (CRP 2.2) ------------------------------------
    if manifest is not None or observed_sources is not None:
        from crp.core.context_enforcer import ContextEnforcer as _Enf
        from crp.core.context_enforcer import default_enforcer as _default_enf
        active = enforcer if enforcer is not None else _default_enf()
        if active is not None and isinstance(active, _Enf):
            active.check(manifest, list(observed_sources or ()), emit=True)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    if envelope:
        messages.append({
            "role": "user",
            "content": f"[VERIFIED CONTEXT]\n{envelope}\n[END VERIFIED CONTEXT]",
        })
    messages.append({
        "role": "user",
        "content": task_input,
    })
    return messages


def _safe_provider_error(exc: Exception) -> str:
    """Sanitize provider exception for external visibility (§audit4 SEC-M1)."""
    return f"{type(exc).__name__}: provider call failed"


class DispatchMixin:
    """Mixin providing all CRP dispatch strategies.

    Methods access orchestrator state via ``self`` (multiple inheritance).
    """

    def _build_envelope(
        self,
        system_prompt: str,
        task_input: str,
        generation_reserve: int,
    ) -> EnvelopeResult:
        """Build budget-aware envelope from WarmStore facts via 6-phase pipeline."""
        from crp.envelope.builder import (
            EnvelopeResult,
            EnvelopeState,
        )
        from crp.envelope.builder import (
            construct as construct_envelope,
        )

        context_window = self._provider.context_window_size()
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)

        budget = compute_envelope_budget(context_window, s_tokens, t_tokens, generation_reserve)
        if budget <= 0 or self._warm_store.fact_count == 0:
            return EnvelopeResult(budget_tokens=budget)

        # Build envelope state from warm store
        active_facts = self._warm_store.get_active_facts_as_extraction()
        critical_sections = self._warm_store.critical_state.to_sections()

        # CKF retriever callback for Phase 6 of envelope builder (GAP A fix)
        def ckf_retriever(query_text: str, budget_tokens: int) -> list[Fact]:
            """Execute CKF retriever and return the result.

                Args:
                    query_text (str): The query text value.
                    budget_tokens (int): The budget tokens value.

                Returns:
                    ``list[Fact]``.
            """
            try:
                # Compute query embedding for semantic mode
                query_emb = None
                if self._embedding_fn is not None:
                    try:
                        query_emb = self._embedding_fn(query_text)
                    except Exception as emb_exc:
                        logger.debug("CKF embedding failed (semantic mode unavailable): %s", emb_exc)

                # Gather seed IDs from recently packed facts for graph walk
                seed_ids: set[str] | None = None
                recent = self._warm_store.get_ranked_facts(limit=5)
                if recent:
                    seed_ids = {f.id for f in recent}

                result = self._ckf.retrieve(
                    query_embedding=query_emb,
                    seed_ids=seed_ids,
                    topic=query_text[:100] if query_text else None,
                    budget=min(budget_tokens, 200),
                )
                if not result.facts:
                    logger.debug("CKF retrieval returned 0 facts for query: %.100s", query_text)
                # MergedFact wraps Fact — unwrap for scoring/packing
                return [mf.fact for mf in result.facts]
            except Exception as exc:
                # V7 fix: Log CKF retrieval failures instead of silently swallowing
                logger.warning("CKF retrieval failed (facts unavailable): %s", exc)
                return []

        # ── V1 fix: Route curator synthesis through envelope pipeline ──
        # Instead of appending post-pack (bypassing budget), include as a
        # section so it competes for budget via section_overhead in builder.
        if self._curator.current_synthesis:
            curator_text = self._curator.format_for_envelope()
            if curator_text:
                critical_sections["LLM_SYNTHESIS"] = curator_text

        # ── V2 fix: Route meta-learning scaffold through envelope pipeline ──
        # Instead of appending post-pack (unbudgeted), include as a section
        # so the builder accounts for it in the budget formula.
        context_window = self._provider.context_window_size()
        if context_window <= 32_000:  # Small model
            scaffold = self._meta_learning.build_reasoning_scaffold(
                task_intent=task_input[:200],
            )
            if scaffold:
                critical_sections["REASONING_SCAFFOLD"] = scaffold

        envelope_state = EnvelopeState(
            facts=active_facts,
            graph=self._warm_store.graph,
            current_window_index=self._windows_completed,
            seen_counts=self._warm_store.get_seen_counts(),
            fact_window_indices=self._warm_store.get_fact_window_indices(),
            sections=critical_sections,
            ckf_retriever=ckf_retriever,
        )

        task_intent = TaskIntent(
            description=task_input[:200],
            task_input=task_input,
            system_prompt=system_prompt,
        )

        envelope = construct_envelope(
            task_intent=task_intent,
            budget_tokens=budget,
            state=envelope_state,
            count_tokens=self._provider.count_tokens,
        )

        # Augment envelope with source grounding passages (§17)
        # Source passages are post-pack because they annotate packed facts.
        # Budget-checked: only added if within remaining budget.
        if self._source_grounding.passage_count > 0 and envelope.facts_included:
            grounded_section_parts: list[str] = []
            for fid in [f.fact_id for f in (envelope.packing.packed_facts if envelope.packing else [])]:
                passages = self._source_grounding.get_passages_for_fact(fid)
                if passages:
                    for p in passages[:1]:  # Top passage per fact
                        grounded_section_parts.append(
                            f"[SOURCE w{p.source_window}] \"{p.text[:200]}\""
                        )
            if grounded_section_parts:
                source_section = "\n--- Source Passages ---\n" + "\n".join(grounded_section_parts)
                source_tokens = self._provider.count_tokens(source_section)
                # Only include if within budget
                if envelope.envelope_tokens + source_tokens <= envelope.budget_tokens:
                    envelope = EnvelopeResult(
                        envelope_text=f"{envelope.envelope_text}\n{source_section}",
                        envelope_tokens=envelope.envelope_tokens + source_tokens,
                        budget_tokens=envelope.budget_tokens,
                        saturation=envelope.saturation,
                        facts_included=envelope.facts_included,
                        packing=envelope.packing,
                    )

        return envelope

    # ------------------------------------------------------------------
    # Internal: input-side continuation (multi-window input processing)
    # ------------------------------------------------------------------

    def _run_input_continuation(
        self,
        system_prompt: str,
        task_input: str,
        generation_reserve: int,
    ) -> str:
        """Process an oversized input across multiple full windows.

        Each window receives a chunk of the original input plus a directive to
        extract relevant facts.  Extracted facts are stored in the warm store
        and CKF so the final answer window can operate with a compact task
        reference instead of the bulky input.

        Args:
            system_prompt: System prompt for each input window.
            task_input: The oversized task or context.
            generation_reserve: Generation reserve for the final answer window.

        Returns:
            A compact task reference that replaces the original ``task_input``.
        """
        from crp.continuation.input_planner import InputContinuationPlanner

        context_window = self._provider.context_window_size()
        planner = InputContinuationPlanner(count_tokens=self._provider.count_tokens)
        plan = planner.plan(task_input, system_prompt, context_window)

        logger.info(
            "Input continuation: %d chunks for %d-token task (window=%d)",
            len(plan.chunks),
            self._provider.count_tokens(task_input),
            context_window,
        )

        prior_summary = ""
        task_summary = self._extract_task_title(task_input)
        input_window_count = 0

        for chunk in plan.chunks:
            input_window_count += 1
            chunk_task = planner.build_chunk_task(chunk, task_summary, prior_summary)
            chunk_messages = assemble_messages(system_prompt, "", chunk_task)

            chunk_window_id = f"input-cont-{input_window_count}-{uuid.uuid4().hex[:8]}"
            self._warm_store.advance_window(chunk_window_id)

            chunk_node = WindowNode(
                window_id=chunk_window_id,
                system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
                task_input_hash=hashlib.sha256(chunk.text[:200].encode()).hexdigest(),
                continuation_index=0,
            )
            self._dag.add_node(chunk_node)
            chunk_node.advance(WindowState.ASSEMBLED)
            chunk_node.advance(WindowState.DISPATCHED)
            chunk_node.advance(WindowState.GENERATING)

            _cont_pause = float(self._config.get("continuation_pause_s", 0.0))
            if _cont_pause > 0.0:
                time.sleep(_cont_pause)

            try:
                chunk_output, chunk_finish = self._provider.generate_chat(
                    chunk_messages,
                    # Small output budget — we only want fact extraction.
                    max_tokens=min(512, context_window // 4),
                )
            except Exception as exc:
                logger.error("Input continuation window failed: %s", exc)
                chunk_output = ""
                chunk_finish = "error"

            chunk_node.advance(WindowState.COMPLETED)

            # Extract facts from the chunk output.
            try:
                chunk_extraction = self._extraction.extract(
                    chunk_output,
                    source_window_id=chunk_window_id,
                )
                chunk_facts = chunk_extraction.facts
            except Exception as exc:
                logger.warning("Fact extraction failed for input chunk: %s", exc)
                chunk_facts = []

            # Store facts.
            fact_ids: list[str] = []
            for fact in chunk_facts:
                fact.source_window_id = chunk_window_id
                self._warm_store.add_facts([fact])
                self._ckf.store([fact], window_id=chunk_window_id)
                fact_ids.append(fact.id)
            chunk_node.facts_produced = fact_ids
            chunk_node.advance(WindowState.EXTRACTED)

            # Build a running summary for the next chunk.
            if chunk_facts:
                prior_summary = self._summarize_facts(chunk_facts, limit_tokens=256)
            else:
                prior_summary = "[No new facts extracted from previous chunk.]"

            self._compliance_audit.record(
                ComplianceEventType.CONTINUATION_DECIDED,
                session_id=self._session.session_id,
                data={
                    "operation": "input_continuation",
                    "window_id": chunk_window_id,
                    "chunk_index": chunk.index,
                    "chunk_total": chunk.total,
                    "facts_extracted": len(chunk_facts),
                    "finish_reason": chunk_finish,
                },
            )

        logger.info(
            "Input continuation complete: %d windows, %d total facts",
            input_window_count,
            self._warm_store.fact_count,
        )
        return planner.build_final_task_reference(task_input)

    def _summarize_facts(self, facts: list[Fact], limit_tokens: int = 256) -> str:
        """Create a concise summary of facts for relay between input windows."""
        if not facts:
            return ""
        lines = [f"- {f.text}" for f in facts[:20]]
        summary = "\n".join(lines)
        # Simple iterative truncation to respect token budget.
        while self._provider.count_tokens(summary) > limit_tokens and lines:
            lines.pop()
            summary = "\n".join(lines)
        return summary

    # ------------------------------------------------------------------
    # Internal: security scanning
    # ------------------------------------------------------------------

    def _extract_task_title(self, task_input: str) -> str:
        """Extract a one-line title from the task input for continuation reference.

        Uses the document title if present (e.g. 'Write a document titled "X"'),
        otherwise uses the first meaningful line truncated to 120 chars.
        """
        import re as _re

        # Try to find an explicit title in quotes
        m = _re.search(r'titled?\s+"([^"]+)"', task_input, _re.IGNORECASE)
        if m:
            return m.group(1)

        m = _re.search(r"titled?\s+'([^']+)'", task_input, _re.IGNORECASE)
        if m:
            return m.group(1)

        # Fall back to first non-empty line that looks like a directive
        for line in task_input.split("\n"):
            line = line.strip()
            if line and len(line) > 10 and not line.startswith(("#", "-", "*", "```")):
                return line[:120] + ("..." if len(line) > 120 else "")

        return task_input[:120] + ("..." if len(task_input) > 120 else "")

    def _scan_injection(self, task_input: str) -> SecurityFlags:
        """Advisory injection detection — NEVER blocks (§7.5)."""
        report = self._injection_detector.scan(task_input)
        flags = SecurityFlags(
            injection_markers_detected=len(report.flags),
        )
        if report.flags:
            flags.injection_marker_details = [
                {
                    "type": f.injection_type.value,
                    "pattern": f.pattern_name,
                    "confidence": f.confidence,
                }
                for f in report.flags
            ]
        return flags

    # ------------------------------------------------------------------
    # Resource snapshot for WindowMetrics
    # ------------------------------------------------------------------

    def _resource_fields(self) -> dict[str, object]:
        """Compute resource-related fields for WindowMetrics."""
        mgr = getattr(self, "_resource_manager", None)
        if mgr is None:
            return {}
        mgr.update_fact_count(self._warm_store.fact_count)
        snap = mgr.snapshot()
        return {
            "ram_available_mb": max(int(snap.budget_mb - snap.crp_estimated_mb), 0),
            "ram_used_by_crp_mb": int(snap.crp_estimated_mb),
            "pressure_level": snap.pressure_level,
        }

    # ------------------------------------------------------------------
    # Marginal gain / sections covered for WindowMetrics
    # ------------------------------------------------------------------

    _SECTION_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

    def _marginal_fields(
        self, output_text: str, facts_before: int,
    ) -> dict[str, object]:
        """Compute marginal_gain and sections_covered from dispatch output."""
        facts_after = self._warm_store.fact_count
        new_facts = max(facts_after - facts_before, 0)
        marginal = new_facts / max(facts_after, 1)

        sections = len(set(self._SECTION_RE.findall(output_text))) if output_text else 0
        return {
            "marginal_gain": round(marginal, 4),
            "sections_covered": sections,
        }

    # ------------------------------------------------------------------
    # Adaptive allocator fields for WindowMetrics (§resource-alloc)
    # ------------------------------------------------------------------

    def _allocator_fields(self) -> dict[str, object]:
        """Compute adaptive-allocator telemetry for WindowMetrics."""
        alloc = getattr(self, "_adaptive_allocator", None)
        if alloc is None:
            return {}
        disabled = alloc.disabled_stages
        om = getattr(self, "_overhead_manager", None)
        shed_count = 0
        if om is not None:
            from crp.resources.overhead_manager import SHEDDING_CASCADE
            shed_count = sum(1 for f in SHEDDING_CASCADE if not om.is_feature_enabled(f))
        return {
            "adaptive_ewma_overhead_pct": round(alloc.ewma_overhead_pct, 1),
            "adaptive_features_shed": shed_count,
            "adaptive_stages_disabled": ",".join(str(s) for s in sorted(disabled)),
            "adaptive_consecutive_over": alloc.consecutive_over_cap,
        }

    def _record_dispatch_overhead(
        self,
        total_dispatch_ms: float,
        total_llm_ms: float,
        *,
        envelope_ms: float = 0.0,
        extraction_ms: float = 0.0,
    ) -> None:
        """Feed overhead measurement into adaptive allocator after dispatch."""
        alloc = getattr(self, "_adaptive_allocator", None)
        if alloc is None:
            return
        alloc.record_window(
            total_ms=total_dispatch_ms,
            llm_ms=total_llm_ms,
            envelope_ms=envelope_ms,
            extraction_ms=extraction_ms,
        )
        # Trigger model unloading if needed
        if alloc.should_unload_models():
            for model_name in alloc.idle_models():
                self._resource_manager.mark_model_unloaded(model_name)
        # Trigger GC if needed
        if alloc.should_run_gc():
            self._resource_manager.trigger_gc()

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Dispatch a task window to the LLM with full envelope + extraction.

        Pipeline:
        1. Advisory injection scan on task_input
        2. Build envelope from WarmStore facts (6-phase)
        3. Assemble messages (Axiom 4 — no modification)
        4. Dispatch to LLM
        5. Extract facts from output (graduated 6-stage pipeline)
        6. Store facts in WarmStore + CKF
        7. Continuation loop if wall hit + gap remaining + info flowing

        Returns (stitched_output, QualityReport). Output is UNMODIFIED (Axiom 9).
        """
        with self._lock:
            return self._dispatch_locked(system_prompt, task_input, **kwargs)

    def _dispatch_locked(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Internal dispatch implementation — called under self._lock."""
        # Set correlation ID for structured log tracing (§audit H9)
        from crp.observability.structured_logging import new_correlation_id, set_session_context
        cid = new_correlation_id()
        set_session_context(self._session.session_id)
        logger.debug("dispatch started [correlation_id=%s]", cid)

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        self._check_session()

        # ---------- Session binding verification (§7.1, §6A.3) ----------
        if self._session_binding.binding is not None:
            _binding_payload = (
                self._session.session_id + ":" + str(len(task_input))
            ).encode("utf-8")
            _binding_sig = self._session_binding.sign_request(_binding_payload)
            if not self._session_binding.verify_request_signature(
                _binding_payload, _binding_sig
            ):
                raise RuntimeError(
                    "Session binding verification failed — "
                    "cryptographic integrity compromised"
                )

        # ---------- Compliance imports (§7.14) ----------
        from crp.security.consent import ProcessingPurpose
        from crp.security.privacy import DataClassification

        # ---------- Compliance audit: dispatch started (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_PROCESSED,
            session_id=self._session.session_id,
            data={"operation": "dispatch", "phase": "started",
                  "input_preview_length": min(len(task_input), 200)},
        )

        # ---------- Human oversight check (§7.13, EU AI Act Art. 14) ----------
        if self._human_oversight.requires_approval("dispatch"):
            oversight_event = self._human_oversight.request_approval(
                "dispatch", details={"input_length": len(task_input)},
            )
            self._compliance_audit.record(
                ComplianceEventType.OVERSIGHT_APPROVAL_REQUESTED,
                session_id=self._session.session_id,
                data={"operation": "dispatch", "event_id": oversight_event.event_id},
            )
        self._human_oversight.record_autonomous_dispatch()

        # ---------- Consent verification (§7.13) ----------
        self._consent_manager.check_required(ProcessingPurpose.CONTEXT_MANAGEMENT)
        self._consent_manager.check_required(ProcessingPurpose.FACT_EXTRACTION)

        # ---------- Emit dispatch.started event (§9) ----------
        self._emitter.emit("dispatch.started", {
            "session_id": self._session.session_id,
            "task_preview": task_input[:200],
        })

        # ---------- Scale mode configuration (§scale D6 fix) ----------
        estimated_tokens = self._provider.count_tokens(task_input)
        session_config = self._scale_mode.configure_session(
            estimated_tokens=estimated_tokens,
        )
        logger.debug("Scale mode: %s (estimated %d tokens)", session_config.processing_mode, estimated_tokens)

        # ---------- RBAC permission + rate limit check (§7.10) ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RBAC_DENIED,
                session_id=self._session.session_id,
                data={"operation": "dispatch", "reason": perm_result.reason},
            )
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RATE_LIMIT_HIT,
                session_id=self._session.session_id,
                data={"operation": "dispatch", "reason": rate_result.reason},
            )
            raise RateLimitExceededError(rate_result.reason)

        # ---------- Input validation — Layer 1, cannot disable (§7.4) ----------
        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        # ---------- PII scanning on input (§7.12) ----------
        pii_result = self._pii_scanner.scan(task_input)
        if pii_result.has_pii:
            self._compliance_audit.record(
                ComplianceEventType.PII_DETECTED,
                session_id=self._session.session_id,
                data={
                    "operation": "dispatch",
                    "phase": "input",
                    "pii_types": sorted(pii_result.pii_types_found),
                    "detection_count": len(pii_result.detections),
                    "classification": pii_result.highest_classification.name,
                },
            )
            if self._human_oversight.should_halt_on_pii():
                self._human_oversight.record_halt(
                    "dispatch", "PII detected in input",
                    details={"pii_types": sorted(pii_result.pii_types_found)},
                )
                self._compliance_audit.record(
                    ComplianceEventType.OVERSIGHT_HALT,
                    session_id=self._session.session_id,
                    data={"reason": "pii_in_input",
                          "pii_types": sorted(pii_result.pii_types_found)},
                )
            logger.info("PII detected in dispatch input: %s", pii_result.pii_types_found)

        # ---------- Security scan (advisory) ----------
        security_flags = self._scan_injection(task_input)
        # Populate structural validation stats into security flags
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Audit injection detections (§7.14) ----------
        if security_flags.injection_markers_detected > 0:
            self._compliance_audit.record(
                ComplianceEventType.INJECTION_DETECTED,
                session_id=self._session.session_id,
                data={
                    "operation": "dispatch",
                    "phase": "input",
                    "flags_count": security_flags.injection_markers_detected,
                    "details": security_flags.injection_marker_details,
                },
            )
            if self._human_oversight.should_halt_on_injection():
                self._human_oversight.record_halt(
                    "dispatch", "Injection detected in input",
                    details={"flags_count": security_flags.injection_markers_detected},
                )
                self._compliance_audit.record(
                    ComplianceEventType.OVERSIGHT_HALT,
                    session_id=self._session.session_id,
                    data={"reason": "injection_in_input",
                          "flags_count": security_flags.injection_markers_detected},
                )

        # ---------- Measure tokens ----------
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out,
            self._provider.max_output_tokens,
            context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # ---------- Auto-ingest / input-side continuation (§4.6) ----------
        # If task_input alone exceeds context budget, either use multi-window
        # input continuation (new) or legacy auto-ingest (chunk externally and
        # replace with a synthesized reference).
        available = context_window - s_tokens - g
        input_continuation_mode = str(
            self._config.get("input_continuation_mode", "auto_ingest")
        ).lower()
        if t_tokens > available and available > 0:
            if input_continuation_mode == "multi_window":
                logger.info(
                    "Input continuation triggered: task_input=%d tokens > available=%d",
                    t_tokens, available,
                )
                task_input = self._run_input_continuation(
                    system_prompt=system_prompt,
                    task_input=task_input,
                    generation_reserve=g,
                )
                t_tokens = self._provider.count_tokens(task_input)
            else:
                logger.info(
                    "Auto-ingest triggered: task_input=%d tokens > available=%d",
                    t_tokens, available,
                )
                from crp.advanced.auto_ingest import IngestFact, auto_ingest

                def _extract_fn(text: str, intent: str) -> list[IngestFact]:
                    """Adapter: run graduated extraction and return IngestFacts."""
                    result = self._extraction.extract(
                        text, source_window_id="auto-ingest",
                    )
                    return [
                        IngestFact(
                            text=f.text, confidence=f.confidence,
                            source=f.source_window_id or "auto-ingest",
                        )
                        for f in result.facts
                    ]

                ingest_facts, ingest_result = auto_ingest(
                    system_prompt=system_prompt,
                    task_input=task_input,
                    task_intent_text=task_input[:200],
                    context_window=context_window,
                    count_tokens=self._provider.count_tokens,
                    extract_fn=_extract_fn,
                )

                # V9 fix: Create a DAG node for auto-ingest so facts are traceable
                ingest_window_id = f"auto-ingest-{uuid.uuid4().hex[:8]}"
                ingest_node = WindowNode(
                    window_id=ingest_window_id,
                    system_prompt_hash=hashlib.sha256(b"auto-ingest").hexdigest(),
                    task_input_hash=hashlib.sha256(task_input[:200].encode()).hexdigest(),
                    continuation_index=0,
                )
                self._dag.add_node(ingest_node)

                # Store ingested facts in warm store + CKF
                from crp.extraction.types import Fact
                ingest_fact_ids: list[str] = []
                for ifact in ingest_facts:
                    fact = Fact(
                        text=ifact.text,
                        confidence=ifact.confidence,
                        source_window_id=ingest_window_id,
                        extraction_stage=0,
                    )
                    self._warm_store.add_facts([fact])
                    self._ckf.store([fact], window_id=ingest_window_id)
                    ingest_fact_ids.append(fact.id)

                # Track facts in DAG node for auditability
                ingest_node.facts_produced = ingest_fact_ids
                # Advance through all required states (forward-only invariant)
                ingest_node.advance(WindowState.ASSEMBLED)
                ingest_node.advance(WindowState.DISPATCHED)
                ingest_node.advance(WindowState.GENERATING)
                ingest_node.advance(WindowState.COMPLETED)
                ingest_node.advance(WindowState.EXTRACTED)

                # Replace task_input with synthesized reference
                task_input = ingest_result.synthesized_task
                t_tokens = self._provider.count_tokens(task_input)
                logger.info(
                    "Auto-ingest complete: %d chunks, %d facts → synthesized %d tokens",
                    ingest_result.chunks_created,
                    ingest_result.facts_after_reconciliation,
                    t_tokens,
                )

        # ---------- Build envelope from accumulated facts ----------
        _t_env0 = time.monotonic_ns()
        envelope_result = self._build_envelope(system_prompt, task_input, g)
        envelope = envelope_result.envelope_text
        _envelope_ms_primary = (time.monotonic_ns() - _t_env0) / 1_000_000

        self._emitter.emit("envelope.built", {
            "session_id": self._session.session_id,
            "facts_included": envelope_result.facts_included,
            "saturation": round(envelope_result.saturation, 3),
            "envelope_tokens": self._provider.count_tokens(envelope) if envelope else 0,
        })

        # ---------- Audit: envelope context selection provenance (§7.14.2) ----------
        _packed_fact_ids: list[str] = []
        _packed_fact_scores: list[dict[str, object]] = []
        if envelope_result.packing and envelope_result.packing.packed_facts:
            for pf in envelope_result.packing.packed_facts:
                _packed_fact_ids.append(pf.fact_id)
                _packed_fact_scores.append({
                    "fact_id": pf.fact_id,
                    "relevance_score": round(pf.score, 4),
                    "tokens": pf.tokens,
                    "is_compressed": pf.is_compressed,
                    "is_bookend": pf.is_bookend,
                    "is_neighbour": pf.is_neighbour,
                })
        self._compliance_audit.record(
            ComplianceEventType.ENVELOPE_CONTEXT_SELECTED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "window_id": "primary",
                "facts_available": self._warm_store.fact_count,
                "facts_included": envelope_result.facts_included,
                "facts_considered": (
                    envelope_result.packing.facts_considered
                    if envelope_result.packing else 0
                ),
                "budget_tokens": envelope_result.budget_tokens,
                "envelope_tokens": (
                    self._provider.count_tokens(envelope) if envelope else 0
                ),
                "saturation": round(envelope_result.saturation, 4),
                "ckf_facts_added": envelope_result.ckf_facts_added,
                "compressed_count": envelope_result.compressed_count,
                "bookend_count": envelope_result.bookend_count,
                "packed_facts": _packed_fact_scores,
                "source_of_truth": (
                    "warm_store + ckf (knowledge graph)"
                    if envelope_result.ckf_facts_added > 0
                    else "warm_store (accumulated facts)"
                ),
                "selection_rationale": (
                    "Facts ranked by recency-weighted relevance score; "
                    "top-scoring facts packed into envelope within token budget; "
                    "CKF graph neighbours and bookend facts supplement gaps."
                ),
            },
        )

        e_tokens = self._provider.count_tokens(envelope) if envelope else 0
        input_tokens = s_tokens + t_tokens + e_tokens

        # ---------- Check budget ----------
        self._check_budget(input_tokens)

        # ---------- Advance warm store window ----------
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        # ---------- Build window node ----------
        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)

        self._emitter.emit("window.opened", {
            "session_id": self._session.session_id,
            "window_id": window_id,
            "input_tokens": input_tokens,
        })

        # ---------- Application-profile context attestation ----------
        manifest = self._app_context_manifest()
        observed_sources: Any | None = kwargs.pop("observed_sources", None)
        if manifest is not None and observed_sources is None:
            try:
                observed_sources = manifest.sources
            except Exception:
                observed_sources = None

        # ---------- Assemble messages ----------
        messages = assemble_messages(
            system_prompt, envelope, task_input,
            manifest=manifest, observed_sources=observed_sources,
        )

        # ---------- Dispatch to LLM ----------
        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # Circuit breaker gate (§audit H4)
        if not self._circuit_breaker.allow_request():
            raise ProviderError(
                "Circuit breaker OPEN — provider unavailable, "
                "retry after recovery timeout"
            )

        start_ms = time.monotonic_ns()
        try:
            output, finish_reason = self._provider.generate_chat(
                messages,
                max_tokens=g,
            )
            self._circuit_breaker.record_success()
        except Exception as exc:
            self._circuit_breaker.record_failure()
            logger.error("Provider error: %s", exc)
            raise ProviderError(_safe_provider_error(exc)) from exc

        wall_ms = (time.monotonic_ns() - start_ms) / 1_000_000
        node.finish_reason = finish_reason
        node.raw_output_id = str(uuid.uuid4())
        node.advance(WindowState.COMPLETED)

        logger.info(
            "Primary window done: finish_reason=%s, wall_ms=%.0f, output_chars=%d",
            finish_reason, wall_ms, len(output),
        )

        # ---------- Output tokens ----------
        output_tokens = self._provider.count_tokens(output)

        # ---------- Audit: LLM call provenance (§7.14.2) ----------
        self._compliance_audit.record(
            ComplianceEventType.LLM_CALL_COMPLETED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "window_id": window_id,
                "window_type": "primary",
                "system_prompt_hash": hashlib.sha256(
                    system_prompt.encode()
                ).hexdigest()[:16],
                "task_input_hash": hashlib.sha256(
                    task_input.encode()
                ).hexdigest()[:16],
                "envelope_provided": bool(envelope),
                "envelope_facts_count": envelope_result.facts_included,
                "envelope_saturation": round(envelope_result.saturation, 4),
                "input_tokens": input_tokens,
                "system_tokens": s_tokens,
                "task_tokens": t_tokens,
                "envelope_tokens": e_tokens,
                "generation_reserve": g,
                "output_tokens": output_tokens,
                "output_length_chars": len(output),
                "finish_reason": finish_reason,
                "wall_time_ms": round(wall_ms, 1),
                "context_window": context_window,
                "context_utilization": round(input_tokens / context_window, 4)
                if context_window > 0 else 0.0,
                "reasoning_content_present": getattr(
                    self._provider, "last_reasoning_content", None
                ) is not None,
                "decision_basis": (
                    f"LLM received {s_tokens} system tokens, "
                    f"{e_tokens} envelope tokens ({envelope_result.facts_included} facts), "
                    f"and {t_tokens} task tokens. "
                    f"finish_reason='{finish_reason}' indicates "
                    + (
                        "model chose to stop (believes task complete)."
                        if finish_reason == "stop"
                        else "output hit token limit (may be incomplete)."
                        if finish_reason == "length"
                        else f"generation ended with reason '{finish_reason}'."
                    )
                ),
            },
        )

        # ---------- CQS: Detect context hunger in output (§CQS D1 fix) ----------
        cqs_signals = self._cqs_detector.detect_context_hunger(
            output, window_id=window_id, tokens_generated=output_tokens,
        )
        if cqs_signals:
            cqs_response = self._cqs_detector.respond_to_context_hunger(
                cqs_signals, tokens_generated=output_tokens,
            )
            logger.info("CQS: %d hunger signals detected, action=%s",
                        len(cqs_signals), cqs_response.action)

        # ---------- Capture reasoning content (thinking models) ----------
        primary_reasoning = getattr(self._provider, "last_reasoning_content", None)
        total_reasoning_tokens = 0
        if primary_reasoning:
            total_reasoning_tokens += self._provider.count_tokens(primary_reasoning)

        # Gap F fix: Extract facts from primary window reasoning content.
        # Thinking model reasoning often contains analysis and insights that
        # enrich the fact store for subsequent continuation windows.
        if primary_reasoning and len(primary_reasoning) > 100:
            try:
                _reasoning_task_intent = TaskIntent(
                    task_input=task_input,
                    system_prompt=system_prompt,
                )
                reasoning_extraction = self._extract_and_store(
                    primary_reasoning,
                    f"{window_id}_reasoning",
                    _reasoning_task_intent,
                )
                if reasoning_extraction.total_facts > 0:
                    logger.info(
                        "Gap F: extracted %d facts from primary reasoning (%d tokens)",
                        reasoning_extraction.total_facts,
                        total_reasoning_tokens,
                    )
            except Exception:  # noqa: BLE001
                logger.debug("Gap F: primary reasoning extraction failed (non-fatal)")

        # ---------- Extract facts from output ----------
        _t_ext0 = time.monotonic_ns()
        task_intent = TaskIntent(
            task_input=task_input,
            system_prompt=system_prompt,
        )
        extraction = self._extract_and_store(output, window_id, task_intent)
        _extraction_ms_primary = (time.monotonic_ns() - _t_ext0) / 1_000_000
        node.advance(WindowState.EXTRACTED)
        logger.info("Primary extraction: %d facts", extraction.total_facts)
        node.facts_produced = [f.id for f in extraction.facts]

        # ---------- Emit fact events (§9 F6 fix) ----------
        for fact in extraction.facts:
            self._emitter.emit("fact.created", {
                "fact_id": fact.id,
                "window_id": window_id,
                "confidence": round(fact.confidence, 3),
                "stage": fact.extraction_stage,
            })
        self._emitter.emit("extraction.completed", {
            "window_id": window_id,
            "facts_extracted": extraction.total_facts,
        })

        # ---------- Audit: fact extraction provenance (§7.14.2) ----------
        _extracted_fact_details: list[dict[str, object]] = []
        for fact in extraction.facts:
            _extracted_fact_details.append({
                "fact_id": fact.id,
                "confidence": round(fact.confidence, 4),
                "extraction_stage": fact.extraction_stage,
                "text_preview": fact.text[:120],
                "flagged": bool(fact.flagged_confidence),
                "flag_reason": getattr(fact, "confidence_flag_reason", ""),
            })
        self._compliance_audit.record(
            ComplianceEventType.FACTS_EXTRACTED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "window_id": window_id,
                "window_type": "primary",
                "total_facts": extraction.total_facts,
                "average_confidence": round(extraction.average_confidence, 4),
                "quality_gate_passed": extraction.quality_gate_passed,
                "stages_run": extraction.stages_run,
                "per_stage_latency_ms": {
                    str(k): round(v * 1000, 1)
                    for k, v in extraction.per_stage_latency.items()
                } if extraction.per_stage_latency else {},
                "extraction_latency_ms": round(_extraction_ms_primary, 1),
                "facts": _extracted_fact_details,
                "source_of_truth": (
                    f"Facts extracted from LLM output of window {window_id}. "
                    f"The LLM generated this output based on "
                    f"{envelope_result.facts_included} envelope facts and the "
                    f"user task input. Extraction ran stages "
                    f"{extraction.stages_run} with quality gate "
                    f"{'PASSED' if extraction.quality_gate_passed else 'FAILED'}."
                ),
            },
        )

        # ---------- Apply feedback loop adjustments (§feedback D3 fix) ----------
        if extraction.facts and self._feedback_loop.entry_count > 0:
            for fact in extraction.facts:
                adjusted = self._feedback_loop.get_adjusted_confidence(
                    fact.id, fact.confidence,
                )
                if adjusted != fact.confidence:
                    fact.confidence = adjusted

        # ---------- Track output-side injection detections (§7.5.2) ----------
        if extraction.facts:
            penalized = sum(1 for f in extraction.facts if f.flagged_confidence
                           and "injection_in_fact" in f.confidence_flag_reason)
            security_flags.output_injection_facts_penalized = penalized

        # ---------- Quarantine promotion (§7.8) ----------
        # Cross-reference quarantined facts against extraction-derived facts
        if self._quarantine.quarantine_count > 0 and extraction.facts:
            extraction_texts = {f.id: f.text for f in extraction.facts}
            self._quarantine.validate_and_promote(window_id, extraction_texts)

        # ---------- PII scan on output (§7.12) ----------
        output_pii = self._pii_scanner.scan(output)
        if output_pii.has_pii:
            self._compliance_audit.record(
                ComplianceEventType.PII_DETECTED,
                session_id=self._session.session_id,
                data={
                    "operation": "dispatch",
                    "phase": "output",
                    "pii_types": sorted(output_pii.pii_types_found),
                    "detection_count": len(output_pii.detections),
                    "classification": output_pii.highest_classification.name,
                },
            )

        # ---------- Retention + lineage tracking for extracted facts (§7.12) ----------
        _input_classification = (
            pii_result.highest_classification if pii_result.has_pii
            else DataClassification.INTERNAL
        )
        _output_classification = (
            output_pii.highest_classification if output_pii.has_pii
            else _input_classification
        )
        for fact in extraction.facts:
            self._retention_manager.register(
                data_id=fact.id,
                classification=_output_classification,
                source_label=f"dispatch:{window_id}",
            )
            self._lineage_tracker.record(
                data_id=fact.id,
                origin="dispatch",
                source_label=f"window:{window_id}",
                classification=_output_classification,
            )

        # ---------- Processing record (§7.13 — GDPR Art. 30) ----------
        self._processing_records.record(
            purpose=ProcessingPurpose.CONTEXT_MANAGEMENT,
            data_categories=["task_input", "llm_output", "extracted_facts"],
            legal_basis="legitimate_interest",
            input_size_bytes=len(task_input.encode("utf-8")),
            output_size_bytes=len(output.encode("utf-8")),
            automated_decision=True,
            human_oversight=self._human_oversight.requires_approval("dispatch"),
            retention_period="session",
        )

        # ---------- LLM context curation (§18) ----------
        # Run periodic curation to synthesize accumulated understanding.
        # Curator synthesis feeds into next dispatch's envelope via sections
        # (V1 fix routes it through the budget pipeline, not post-pack append).
        if self._curator.should_curate(self._windows_completed):
            try:
                ranked_facts = self._warm_store.get_ranked_facts(limit=50)
                fact_texts = [f.text for f in ranked_facts]
                self._curator.curate(
                    window_index=self._windows_completed,
                    top_facts=fact_texts,
                    recent_output_summary=output[:500],
                )
            except Exception as exc:
                logger.debug("Curator skipped: %s", exc)

        # ---------- Mark consumed facts as seen ----------
        if envelope_result.packing and envelope_result.packing.packed_facts:
            consumed_ids = [pf.fact_id for pf in envelope_result.packing.packed_facts]
            self._warm_store.mark_seen(consumed_ids, window_id)
            node.facts_consumed = consumed_ids

        # ---------- Continuation loop ----------
        continuation_windows = 0
        final_output = output
        total_facts_extracted = extraction.total_facts

        # Timing accumulators for CRP overhead telemetry
        _total_llm_ms = wall_ms           # LLM generation time (primary)
        _total_extraction_ms = _extraction_ms_primary
        _total_envelope_ms = _envelope_ms_primary
        _total_output_tokens = output_tokens
        _per_window_detail: list[dict] = []  # per-continuation-window telemetry

        from crp.continuation.manager import ContinuationManager
        cont_config = getattr(self, "_continuation_config", None) or ContinuationConfig(
            max_continuations=int(self._config.get("max_continuations", 50)),
        )
        cont_mgr = ContinuationManager(cont_config)
        cont_state = cont_mgr.process_window(
            task_intent=task_input,
            output=output,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            facts=extraction.facts,
            window_id=window_id,
        )

        logger.info(
            "Continuation check: finished=%s, reason=%s, gap_score=%.3f",
            cont_state.finished,
            cont_state.termination_reason or "n/a",
            cont_state.gap_result.gap_score if cont_state.gap_result else 0.0,
        )

        # ---------- Audit: initial continuation decision (§7.14.2) ----------
        _gap_score = (
            round(cont_state.gap_result.gap_score, 4)
            if cont_state.gap_result else 0.0
        )
        _trigger_info: dict[str, object] = {}
        if cont_state.trigger_result:
            _trigger_info = {
                "should_continue": cont_state.trigger_result.should_continue,
                "reason": cont_state.trigger_result.reason,
                "wall_hit": cont_state.trigger_result.wall_hit,
                "gap_remaining": round(cont_state.trigger_result.gap_remaining, 4),
                "info_flow": round(cont_state.trigger_result.info_flow, 4),
                "continuation_count": cont_state.trigger_result.continuation_count,
            }
        self._compliance_audit.record(
            ComplianceEventType.CONTINUATION_DECIDED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "window_id": window_id,
                "evaluation_point": "post_primary_window",
                "continuation_triggered": not cont_state.finished,
                "gap_score": _gap_score,
                "gap_coverage": round(1.0 - _gap_score, 4),
                "termination_reason": cont_state.termination_reason or "",
                "trigger_details": _trigger_info,
                "finish_reason": finish_reason,
                "output_tokens": output_tokens,
                "facts_extracted": extraction.total_facts,
                "decision_rationale": (
                    f"Gap score {_gap_score:.3f} "
                    + (
                        f"indicates {round((1 - _gap_score) * 100, 1)}% task coverage. "
                    )
                    + (
                        f"Continuation NOT needed: {cont_state.termination_reason}."
                        if cont_state.finished
                        else "Continuation triggered to improve coverage."
                    )
                ),
            },
        )

        last_window_output = final_output  # style anchor for first continuation
        _consecutive_empty = 0  # Track consecutive thinking-only windows
        _dispatch_timeout = int(self._config.get("dispatch_timeout", 3600))
        _continuation_deadline = time.monotonic() + _dispatch_timeout

        while not cont_state.finished:
            if time.monotonic() > _continuation_deadline:
                logger.warning(
                    "Continuation wall-time deadline reached (%ds)", _dispatch_timeout,
                )
                cont_state.termination_reason = "wall_time_deadline"
                break
            continuation_windows += 1
            logger.info("=== Continuation window %d starting ===", continuation_windows)

            # Build continuation envelope
            _t_ce0 = time.monotonic_ns()
            cont_envelope = cont_mgr.build_continuation_envelope(
                task_intent=task_input,
                gap_result=cont_state.gap_result,
                structural_state=self._warm_store.structural_state.to_dict(),
                last_output=last_window_output,
            )

            # Build the continuation task.  We provide a COMPACT reference
            # to the original task (title only) rather than the full text,
            # so the model focuses on the continuation directive instead
            # of re-reading the full task and restarting from scratch.
            # The continuation envelope already contains: the directive
            # (what to write next), document map (what's done), remaining
            # requirements, style anchor, and key findings.
            #
            # V10 fix: Use explicit boundary markers so the LLM can
            # distinguish the original task reference from CRP directives.
            task_title = self._extract_task_title(task_input)
            cont_task = (
                f"=== ORIGINAL TASK ===\n"
                f"{task_title}\n"
                f"=== CONTINUATION DIRECTIVES ===\n"
                f"{cont_envelope}\n"
                f"=== END DIRECTIVES ==="
            )
            # V3+D fix: Continuation-aware budget calculation.
            # The continuation directive consumes context tokens, but must
            # not starve the fact envelope.  We use a reduced generation
            # reserve for continuation windows (model is extending, not
            # starting fresh) to free budget for fact packing.  A minimum
            # envelope budget floor is enforced so facts always participate.
            _cont_g = max(g // 2, 512)  # halve generation reserve for continuation
            cont_env_result = self._build_envelope(system_prompt, cont_task, _cont_g)
            # If envelope budget was zero (directive too large), retry with
            # title-only budget and accept slight context overflow — the
            # model simply generates fewer tokens.
            if cont_env_result.budget_tokens <= 0 and self._warm_store.fact_count > 0:
                logger.info("Gap D: continuation envelope starved, retrying with title-only budget")
                cont_env_result = self._build_envelope(system_prompt, task_title, _cont_g)
            _cont_env_ms = (time.monotonic_ns() - _t_ce0) / 1_000_000
            _total_envelope_ms += _cont_env_ms

            cont_messages = assemble_messages(
                system_prompt, cont_env_result.envelope_text, cont_task,
                manifest=manifest, observed_sources=observed_sources,
            )

            # Dispatch continuation window
            cont_window_id = str(uuid.uuid4())
            self._warm_store.advance_window(cont_window_id)

            cont_node = WindowNode(
                window_id=cont_window_id,
                system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
                task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
                continuation_index=continuation_windows,
                parent_ids=[node.window_id],
            )
            self._dag.add_node(cont_node)
            cont_node.advance(WindowState.ASSEMBLED)
            cont_node.advance(WindowState.DISPATCHED)
            cont_node.advance(WindowState.GENERATING)

            # Brief pause between windows — local inference servers
            # (LM Studio, llama.cpp) may need time to reset after a
            # completion before accepting the next request. Configurable
            # via ``continuation_pause_s`` (default 0.0 — no pause).
            _cont_pause = float(self._config.get("continuation_pause_s", 0.0))
            if _cont_pause > 0.0:
                time.sleep(_cont_pause)

            _t_llm0 = time.monotonic_ns()
            try:
                cont_output, cont_finish = self._provider.generate_chat(
                    cont_messages, max_tokens=g,
                )
            except Exception as exc:
                logger.error(
                    "Continuation window %d: provider failure — %s: %s",
                    continuation_windows, type(exc).__name__, exc,
                )
                cont_state.termination_reason = f"provider_error:{type(exc).__name__}"
                break  # Provider failure stops continuation
            _cont_llm_ms = (time.monotonic_ns() - _t_llm0) / 1_000_000
            _total_llm_ms += _cont_llm_ms

            # Provider returned error
            if cont_finish == "error":
                logger.warning("Continuation window %d: provider returned error, stopping", continuation_windows)
                cont_state.termination_reason = "provider_returned_error"
                break

            # Capture reasoning from thinking model
            cont_reasoning = getattr(self._provider, "last_reasoning_content", None)
            if cont_reasoning:
                total_reasoning_tokens += self._provider.count_tokens(cont_reasoning)

            # Gap F fix: Extract useful insights from thinking model reasoning.
            # The model's reasoning often contains analysis, comparisons, and
            # planning that are valuable facts.  Extract them using stages 1-2
            # (cheap regex+statistical) and store alongside regular facts.
            if cont_reasoning and len(cont_reasoning) > 100:
                try:
                    reasoning_extraction = self._extract_and_store(
                        cont_reasoning,
                        f"{cont_window_id}_reasoning",
                        TaskIntent(task_input=task_input, system_prompt=system_prompt),
                    )
                    if reasoning_extraction.total_facts > 0:
                        total_facts_extracted += reasoning_extraction.total_facts
                        logger.info(
                            "Gap F: extracted %d facts from thinking model reasoning (%d tokens)",
                            reasoning_extraction.total_facts,
                            self._provider.count_tokens(cont_reasoning),
                        )
                except Exception:  # noqa: BLE001
                    logger.debug("Gap F: reasoning extraction failed (non-fatal)")

            # Handle thinking model: empty output but budget exhausted
            # (model spent all tokens on reasoning, no content produced).
            # Skip extraction for this window but continue to the next —
            # the model may produce content with a fresh window.
            if not cont_output and cont_finish == "length":
                _consecutive_empty += 1
                logger.info(
                    "Continuation window %d: thinking model produced no content "
                    "(reasoning only). consecutive_empty=%d",
                    continuation_windows, _consecutive_empty,
                )
                if _consecutive_empty >= 3:
                    logger.warning(
                        "Continuation window %d: %d consecutive empty windows, stopping",
                        continuation_windows, _consecutive_empty,
                    )
                    cont_state.termination_reason = "consecutive_empty_windows"
                    break
                # Record minimal telemetry and continue
                cont_node.finish_reason = cont_finish
                cont_node.raw_output_id = str(uuid.uuid4())
                cont_node.advance(WindowState.COMPLETED)
                _per_window_detail.append({
                    "window": continuation_windows,
                    "llm_ms": round(_cont_llm_ms),
                    "extraction_ms": 0,
                    "envelope_ms": round(_cont_env_ms),
                    "output_tokens": 0,
                    "output_chars": 0,
                    "facts": 0,
                    "finish_reason": "length (reasoning only)",
                    "envelope_saturation": round(cont_env_result.saturation, 3),
                    "envelope_facts_packed": cont_env_result.facts_included,
                    "reasoning_tokens": self._provider.count_tokens(cont_reasoning) if cont_reasoning else 0,
                    "gap_score": round(cont_state.gap_result.gap_score, 3) if cont_state.gap_result else 0.0,
                })
                self._windows_completed += 1
                continue

            # Empty output with non-length finish reason — model is done
            if not cont_output:
                logger.warning("Continuation window %d: empty output (finish=%s), stopping",
                               continuation_windows, cont_finish)
                cont_state.termination_reason = f"empty_output:{cont_finish}"
                break

            # Reset consecutive empty counter on successful content
            _consecutive_empty = 0

            # Update style anchor for next window
            last_window_output = cont_output

            cont_node.finish_reason = cont_finish
            cont_node.raw_output_id = str(uuid.uuid4())
            cont_node.advance(WindowState.COMPLETED)

            logger.info(
                "Continuation window %d done: finish=%s, chars=%d",
                continuation_windows, cont_finish, len(cont_output),
            )

            cont_output_tokens = self._provider.count_tokens(cont_output)

            # Extract from continuation output
            _t_cext0 = time.monotonic_ns()
            cont_extraction = self._extract_and_store(cont_output, cont_window_id, task_intent)
            _cont_ext_ms = (time.monotonic_ns() - _t_cext0) / 1_000_000
            _total_extraction_ms += _cont_ext_ms
            cont_node.advance(WindowState.EXTRACTED)
            cont_node.facts_produced = [f.id for f in cont_extraction.facts]
            total_facts_extracted += cont_extraction.total_facts
            _total_output_tokens += cont_output_tokens

            # ---------- Emit continuation window events (§9) ----------
            self._emitter.emit("window.continued", {
                "session_id": self._session.session_id,
                "window_id": cont_window_id,
                "continuation_index": continuation_windows,
                "output_tokens": cont_output_tokens,
                "facts_extracted": cont_extraction.total_facts,
            })

            # ---------- ReviewCycle checkpoint (§review D5 fix) ----------
            review_guidance = self._review_cycle.checkpoint_review(
                window_index=continuation_windows,
                review_interval=self._config.get("review_interval", 20),
                task_intent=task_input[:200],
                top_facts=[f.text for f in cont_extraction.facts[:5]],
            )
            if review_guidance and not review_guidance.on_track:
                logger.info("ReviewCycle: off-track at window %d, contradictions=%d",
                            continuation_windows, len(review_guidance.contradictions))

            # Per-window telemetry record
            _per_window_detail.append({
                "window": continuation_windows,
                "llm_ms": round(_cont_llm_ms),
                "extraction_ms": round(_cont_ext_ms),
                "envelope_ms": round(_cont_env_ms),
                "output_tokens": cont_output_tokens,
                "output_chars": len(cont_output),
                "facts": cont_extraction.total_facts,
                "finish_reason": cont_finish,
                "envelope_saturation": round(cont_env_result.saturation, 3),
                "envelope_facts_packed": cont_env_result.facts_included,
                "reasoning_tokens": self._provider.count_tokens(cont_reasoning) if cont_reasoning else 0,
                "gap_score": round(cont_state.gap_result.gap_score, 3) if cont_state.gap_result else 0.0,
            })

            # Update counters
            self._windows_completed += 1
            self._total_input_tokens += self._provider.count_tokens(
                system_prompt + (cont_env_result.envelope_text or "") + cont_task
            )
            self._total_output_tokens += cont_output_tokens

            # Process window for continuation decision
            cont_state = cont_mgr.process_window(
                task_intent=task_input,
                output=cont_output,
                finish_reason=cont_finish,
                output_tokens=cont_output_tokens,
                facts=cont_extraction.facts,
                window_id=cont_window_id,
            )
            if cont_state is None:  # §audit3 H1: guard corrupted state
                logger.error("Continuation state is None after window %d — aborting", continuation_windows)
                break
            logger.info(
                "Continuation %d decision: finished=%s, reason=%s",
                continuation_windows,
                cont_state.finished,
                cont_state.termination_reason or "continuing",
            )

            # ---------- Audit: continuation loop decision (§7.14.2) ----------
            _cont_gap = (
                round(cont_state.gap_result.gap_score, 4)
                if cont_state.gap_result else 0.0
            )
            _cont_trigger: dict[str, object] = {}
            if cont_state.trigger_result:
                _cont_trigger = {
                    "should_continue": cont_state.trigger_result.should_continue,
                    "reason": cont_state.trigger_result.reason,
                    "wall_hit": cont_state.trigger_result.wall_hit,
                    "gap_remaining": round(
                        cont_state.trigger_result.gap_remaining, 4
                    ),
                    "info_flow": round(cont_state.trigger_result.info_flow, 4),
                }
            self._compliance_audit.record(
                ComplianceEventType.CONTINUATION_DECIDED,
                session_id=self._session.session_id,
                data={
                    "operation": "dispatch",
                    "window_id": cont_window_id,
                    "evaluation_point": f"continuation_window_{continuation_windows}",
                    "continuation_triggered": not cont_state.finished,
                    "gap_score": _cont_gap,
                    "gap_coverage": round(1.0 - _cont_gap, 4),
                    "termination_reason": cont_state.termination_reason or "",
                    "trigger_details": _cont_trigger,
                    "finish_reason": cont_finish,
                    "output_tokens": cont_output_tokens,
                    "facts_extracted": cont_extraction.total_facts,
                    "decision_rationale": (
                        f"Continuation window {continuation_windows}: "
                        f"gap score {_cont_gap:.3f} "
                        f"({round((1 - _cont_gap) * 100, 1)}% coverage). "
                        + (
                            f"Stopping: {cont_state.termination_reason}."
                            if cont_state.finished
                            else "Continuing to next window."
                        )
                    ),
                },
            )

        # Use stitched output from continuation manager (guard None: \u00a7audit4 C1)
        if cont_state is not None and continuation_windows > 0 and cont_state.stitched_output:
            final_output = cont_state.stitched_output
        self._continuation_windows_total += continuation_windows

        # ---------- Cross-window validation (§cross-window D2 fix) ----------
        if continuation_windows > 0:
            try:
                ranked_facts = self._warm_store.get_ranked_facts(limit=30)
                fact_dicts = [{"text": f.text, "id": f.id} for f in ranked_facts]
                validation_result = self._cross_window_validator.extraction_based_validation(
                    facts=fact_dicts,
                )
                if validation_result.issues:
                    logger.info(
                        "Cross-window validation: %d consistency issues found",
                        len(validation_result.issues),
                    )
            except Exception as exc:
                logger.warning("Cross-window validation skipped: %s", exc)

        # ---------- Post-generation assessment (§review D5 fix) ----------
        if continuation_windows > 0:
            try:
                assessment = self._review_cycle.post_generation_assessment(
                    accumulated_output=final_output[:2000],
                    task_intent=task_input[:500],
                )
                logger.info("Post-generation assessment: score=%.2f", assessment.score)
            except Exception as exc:
                logger.debug("Post-generation assessment skipped: %s", exc)

        # ---------- Window completed event (§9) ----------
        self._emitter.emit("window.completed", {
            "session_id": self._session.session_id,
            "window_id": node.window_id,
            "continuation_windows": continuation_windows,
            "total_facts": total_facts_extracted,
        })

        # ---------- Update counters (primary window) ----------
        self._windows_completed += 1
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        # ---------- Record RBAC rate limit counters (§7.10) ----------
        self._rbac.record_dispatch(tokens_used=output_tokens)

        # ---------- Check output budget ----------
        max_out_total = self._config.max_total_output_tokens
        if max_out_total and self._total_output_tokens > max_out_total:
            logger.warning(
                "Output token cap exceeded (%d > %d)",
                self._total_output_tokens,
                max_out_total,
            )

        # ---------- Metrics ----------
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
        _crp_overhead_ms = _total_dispatch_ms - _total_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        saturation = envelope_result.saturation if envelope_result.envelope_tokens > 0 else 0.0
        gen_speed = _total_output_tokens / (_total_llm_ms / 1000) if _total_llm_ms > 0 else 0.0

        # Final gap score from last continuation check
        _final_gap = 0.0
        if cont_state.gap_result:
            _final_gap = cont_state.gap_result.gap_score

        metrics = WindowMetrics(
            window_id=node.window_id,
            chain_position=continuation_windows,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=e_tokens,
            envelope_budget=envelope_result.budget_tokens,
            saturation=saturation,
            generation_reserve=g,
            generation_tokens=_total_output_tokens,
            generation_speed=gen_speed,
            wall_time_ms=int(_total_llm_ms),
            finish_reason=finish_reason,
            facts_extracted=total_facts_extracted,
            continuation_triggered=continuation_windows > 0,
            continuation_index=continuation_windows,
            # Newly wired latency fields
            envelope_latency_ms=round(_total_envelope_ms, 1),
            extraction_latency_ms=round(_total_extraction_ms, 1),
            extraction_stage_used=",".join(str(s) for s in getattr(extraction, "stages_run", [])),
            # Gap / flow
            gap_coverage=round(1.0 - _final_gap, 3),
            final_gap_score=round(_final_gap, 3),
            total_output_tokens=_total_output_tokens,
            # Reasoning / thinking
            reasoning_tokens=total_reasoning_tokens,
            # CRP overhead
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            total_extraction_ms=round(_total_extraction_ms),
            total_envelope_ms=round(_total_envelope_ms),
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            # Per-window continuation detail
            continuation_windows_detail=_per_window_detail,
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(final_output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        # Feed overhead into adaptive allocator
        self._record_dispatch_overhead(
            _total_dispatch_ms, _total_llm_ms,
            envelope_ms=_total_envelope_ms,
            extraction_ms=_total_extraction_ms,
        )
        quality_tier = _classify_quality_tier(
            facts_extracted=total_facts_extracted,
            continuation_windows=continuation_windows,
            saturation=envelope_result.saturation,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(final_output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=node.window_id,
            output=final_output,
            facts_extracted=total_facts_extracted,
            security_flags=security_flags,
            continuation_windows=continuation_windows,
            envelope_saturation=envelope_result.saturation,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        # ---------- Audit: quality tier assignment provenance (§7.14.2) ----------
        self._compliance_audit.record(
            ComplianceEventType.QUALITY_TIER_ASSIGNED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "window_id": node.window_id,
                "quality_tier": quality_tier,
                "facts_extracted": total_facts_extracted,
                "continuation_windows": continuation_windows,
                "envelope_saturation": round(envelope_result.saturation, 4),
                "finish_reason": finish_reason,
                "output_tokens": output_tokens,
                "output_length_chars": len(final_output),
                "final_gap_score": round(_final_gap, 4),
                "gap_coverage": round(1.0 - _final_gap, 4),
                "total_dispatch_ms": round(_total_dispatch_ms),
                "crp_overhead_pct": round(_crp_overhead_pct, 1),
                "pii_in_input": pii_result.has_pii,
                "pii_in_output": output_pii.has_pii,
                "injection_markers": security_flags.injection_markers_detected,
                "scoring_rationale": (
                    f"Tier '{quality_tier}' assigned based on: "
                    f"{total_facts_extracted} facts extracted "
                    f"(extraction score component), "
                    f"finish_reason='{finish_reason}' with "
                    f"{continuation_windows} continuations "
                    f"(completion score component), "
                    f"{output_tokens} output tokens "
                    f"(substance score component), "
                    f"saturation={round(envelope_result.saturation, 3)} "
                    f"(context utilization component). "
                    f"Final gap coverage: {round((1 - _final_gap) * 100, 1)}%."
                ),
                "decision_chain_summary": (
                    f"Input → {envelope_result.facts_included} facts selected → "
                    f"LLM call ({round(wall_ms)}ms) → "
                    f"{extraction.total_facts} facts extracted → "
                    + (
                        f"{continuation_windows} continuations → "
                        if continuation_windows > 0 else ""
                    )
                    + f"tier '{quality_tier}' "
                    f"(gap coverage {round((1 - _final_gap) * 100, 1)}%)"
                ),
            },
        )

        # ---------- Decision Provenance Engine (§7.14.3) ----------
        if self._provenance_engine.enabled:
            try:
                provenance_report = self._provenance_engine.analyse(
                    output_text=final_output,
                    packed_facts=list(envelope_result.packing.packed_facts) if envelope_result.packing else [],
                    session_id=self._session.session_id,
                    window_id=node.window_id,
                    envelope_saturation=envelope_result.saturation,
                    task_input_preview=task_input[:120],
                )

                # Record per-claim attribution audit entries
                for attr in provenance_report.attributions:
                    from crp.provenance import AttributionType
                    if attr.attribution_type == AttributionType.PARAMETRIC:
                        self._compliance_audit.record(
                            ComplianceEventType.PARAMETRIC_DETECTED,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_index": attr.claim_index,
                                "claim_preview": attr.claim_text[:120],
                                "top_score": round(attr.top_score, 4),
                            },
                        )
                    elif attr.attribution_type == AttributionType.UNCERTAIN:
                        self._compliance_audit.record(
                            ComplianceEventType.ATTRIBUTION_UNCERTAIN,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_index": attr.claim_index,
                                "claim_preview": attr.claim_text[:120],
                            },
                        )

                # Record the full attribution report
                self._compliance_audit.record(
                    ComplianceEventType.ATTRIBUTION_REPORT,
                    session_id=self._session.session_id,
                    data={
                        "window_id": node.window_id,
                        "total_claims": provenance_report.total_claims,
                        "factual_claims": provenance_report.factual_claims,
                        "context_grounded": provenance_report.context_grounded_count,
                        "parametric": provenance_report.parametric_count,
                        "mixed": provenance_report.mixed_count,
                        "uncertain": provenance_report.uncertain_count,
                        "grounding_ratio": provenance_report.grounding_ratio,
                        "envelope_facts_count": provenance_report.envelope_facts_count,
                    },
                )

                # Record fidelity verification events
                fid = provenance_report.fidelity
                if fid is not None:
                    for d in fid.distortions:
                        self._compliance_audit.record(
                            ComplianceEventType.DISTORTION_DETECTED,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_index": d.claim_index,
                                "distortion_type": d.distortion_type.value,
                                "severity": d.severity,
                                "detail": d.detail[:200],
                            },
                        )
                    for f in fid.fabrications:
                        self._compliance_audit.record(
                            ComplianceEventType.FABRICATION_DETECTED,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_index": f.claim_index,
                                "entity_type": f.entity_type.value,
                                "fabricated_entity": f.fabricated_entity[:100],
                                "severity": f.severity,
                            },
                        )
                    from crp.provenance._types import OmissionSeverity
                    for o in fid.omissions:
                        if o.severity in (OmissionSeverity.CRITICAL, OmissionSeverity.HIGH):
                            self._compliance_audit.record(
                                ComplianceEventType.OMISSION_DETECTED,
                                session_id=self._session.session_id,
                                data={
                                    "window_id": node.window_id,
                                    "fact_id": o.fact_id,
                                    "severity": o.severity.value,
                                    "relevance_score": round(o.fact_relevance_score, 4),
                                },
                            )
                    for c in fid.contradictions:
                        self._compliance_audit.record(
                            ComplianceEventType.CONTRADICTION_DETECTED,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_a_index": c.claim_a_index,
                                "claim_b_index": c.claim_b_index,
                                "contradiction_type": c.contradiction_type,
                                "severity": c.severity,
                            },
                        )

                # Record semantic entailment events
                for er in provenance_report.entailment_results:
                    from crp.provenance._types import EntailmentLabel
                    if er.label == EntailmentLabel.CONTRADICTION:
                        self._compliance_audit.record(
                            ComplianceEventType.ENTAILMENT_CONTRADICTION,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "claim_index": er.claim_index,
                                "fact_id": er.fact_id,
                                "contradiction_score": round(er.contradiction_score, 4),
                                "used_model": er.used_model,
                            },
                        )

                # Record entailment model/method status (A-3)
                if provenance_report.entailment_results:
                    any_model = any(er.used_model for er in provenance_report.entailment_results)
                    self._compliance_audit.record(
                        ComplianceEventType.ENTAILMENT_MODEL_STATUS,
                        session_id=self._session.session_id,
                        data={
                            "window_id": node.window_id,
                            "method": "nli_model" if any_model else "heuristic",
                            "pairs_checked": len(provenance_report.entailment_results),
                        },
                    )

                # Record hallucination risk events
                risk = provenance_report.risk_report
                if risk is not None:
                    from crp.provenance._types import HallucinationRisk
                    if risk.critical_risk_count > 0 or risk.high_risk_count > 0:
                        self._compliance_audit.record(
                            ComplianceEventType.RISK_ASSESSMENT_COMPLETED,
                            session_id=self._session.session_id,
                            data={
                                "window_id": node.window_id,
                                "window_risk_level": risk.window_risk_level.value,
                                "mean_risk_score": risk.mean_risk_score,
                                "high_risk_count": risk.high_risk_count,
                                "critical_risk_count": risk.critical_risk_count,
                            },
                        )
                    for a in risk.assessments:
                        if a.risk_level == HallucinationRisk.CRITICAL:
                            self._compliance_audit.record(
                                ComplianceEventType.HALLUCINATION_RISK_CRITICAL,
                                session_id=self._session.session_id,
                                data={
                                    "window_id": node.window_id,
                                    "claim_index": a.claim_index,
                                    "risk_score": a.risk_score,
                                    "risk_factors": a.risk_factors[:5],
                                },
                            )
                        elif a.risk_level == HallucinationRisk.HIGH:
                            self._compliance_audit.record(
                                ComplianceEventType.HALLUCINATION_RISK_HIGH,
                                session_id=self._session.session_id,
                                data={
                                    "window_id": node.window_id,
                                    "claim_index": a.claim_index,
                                    "risk_score": a.risk_score,
                                    "risk_factors": a.risk_factors[:5],
                                },
                            )
            except Exception as exc:
                logger.warning("Decision provenance engine error: %s", exc)
                self._compliance_audit.record(
                    ComplianceEventType.PROVENANCE_ENGINE_FAILURE,
                    session_id=self._session.session_id,
                    data={
                        "window_id": node.window_id,
                        "error": str(exc)[:500],
                        "error_type": type(exc).__name__,
                    },
                )
        else:
            self._compliance_audit.record(
                ComplianceEventType.PROVENANCE_DISABLED,
                session_id=self._session.session_id,
                data={"window_id": node.window_id},
            )

        # ---------- Risk classification (§7.15.1, EU AI Act Art. 9) ----------
        _risk_assessment = self._risk_classifier.assess(
            intended_purpose=task_input[:200],
            processes_personal_data=pii_result.has_pii or output_pii.has_pii,
            makes_automated_decisions=False,
        )
        self._compliance_audit.record(
            ComplianceEventType.RISK_ASSESSMENT,
            session_id=self._session.session_id,
            data={
                "window_id": node.window_id,
                "risk_level": _risk_assessment.risk_level.value,
                "assessment_id": _risk_assessment.assessment_id,
                "mitigations_count": len(_risk_assessment.mitigations),
                "residual_risks_count": len(_risk_assessment.residual_risks),
            },
        )

        # ---------- Emit dispatch.completed + write telemetry (§9 F6+D8 fix) ----------
        self._emitter.emit("dispatch.completed", {
            "session_id": self._session.session_id,
            "window_id": node.window_id,
            "quality_tier": quality_tier,
            "facts_extracted": total_facts_extracted,
            "continuation_windows": continuation_windows,
            "dispatch_ms": round(_total_dispatch_ms),
            "crp_overhead_pct": round(_crp_overhead_pct, 1),
        })
        if self._telemetry_writer is not None:
            from crp.observability.telemetry import WindowTelemetry
            self._telemetry_writer.write(WindowTelemetry(
                session_id=self._session.session_id,
                window_id=node.window_id,
                input_tokens=input_tokens,
                output_tokens=_total_output_tokens,
                overhead_tokens=e_tokens,
                facts_included=envelope_result.facts_included,
                facts_available=self._warm_store.fact_count,
                latency_ms=round(_total_dispatch_ms, 1),
                quality_tier=quality_tier,
            ))

        # ---------- Compliance audit: dispatch completed (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_PROCESSED,
            session_id=self._session.session_id,
            data={
                "operation": "dispatch",
                "phase": "completed",
                "window_id": node.window_id,
                "quality_tier": quality_tier,
                "facts_extracted": total_facts_extracted,
                "continuation_windows": continuation_windows,
                "dispatch_ms": round(_total_dispatch_ms),
                "output_tokens": _total_output_tokens,
                "pii_in_input": pii_result.has_pii,
                "pii_in_output": output_pii.has_pii,
            },
        )

        # ---------- Retention enforcement (§7.12) ----------
        expired_ids = self._retention_manager.enforce()
        if expired_ids:
            self._compliance_audit.record(
                ComplianceEventType.RETENTION_PURGED,
                session_id=self._session.session_id,
                data={"purged_count": len(expired_ids), "purged_ids": expired_ids[:10]},
            )

        # ---------- Compliance report generation (§7.15.3) ----------
        _session_stats = {
            "window_id": node.window_id,
            "quality_tier": quality_tier,
            "facts_extracted": total_facts_extracted,
            "continuation_windows": continuation_windows,
            "dispatch_ms": round(_total_dispatch_ms),
            "pii_detected_input": pii_result.has_pii,
            "pii_detected_output": output_pii.has_pii,
            "injection_markers": security_flags.injection_markers_detected,
            "audit_entries": self._compliance_audit.entry_count,
        }
        _compliance_report = self._compliance_reporter.generate_report(
            session_stats=_session_stats,
            risk_assessment=_risk_assessment,
        )
        logger.info(
            "Compliance report: %d/%d controls implemented (%.1f%%)",
            _compliance_report["summary"]["implemented"],
            _compliance_report["summary"]["total_controls"],
            _compliance_report["summary"]["compliance_score"],
        )

        # Apply license watermark to output
        from crp.license_guard import watermark_output
        final_output = watermark_output(final_output, self._session.session_id)

        return final_output, report

    # ------------------------------------------------------------------
    # Tool-mediated dispatch — PULL-based context relay (§20)
    # ------------------------------------------------------------------

    def dispatch_with_tools(
        self,
        system_prompt: str,
        task_input: str,
        *,
        max_tool_rounds: int = 10,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Dispatch with tool-mediated context relay (pull model).

        Instead of pre-loading ALL context into the envelope (push model),
        this method:
        1. Sends the task to the LLM with CRP context tools
        2. The LLM requests context on demand via tool calls
        3. CRP executes tool calls against WarmStore/CKF
        4. Results are fed back, and the LLM continues
        5. When the LLM finishes (stop/length), extraction proceeds normally

        Falls back to push-based dispatch() if the provider doesn't
        support tool calling.

        Args:
            system_prompt: System prompt (unmodified per Axiom 4).
            task_input:    User task/prompt.
            max_tool_rounds: Maximum tool call round-trips (safety cap).
            **kwargs:      Provider-specific overrides.

        Returns:
            (output_text, QualityReport) — same interface as dispatch().
        """
        # Fall back to push-based if provider doesn't support tools
        if not self._provider.supports_tools():
            logger.info(
                "Provider %s doesn't support tools — falling back to push-based dispatch",
                self._provider.model_name,
            )
            return self.dispatch(system_prompt, task_input, **kwargs)

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        self._check_session()

        # ---------- RBAC + validation (same as dispatch) ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Token measurements ----------
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # ---------- Set up context tool executor ----------
        from crp.core.context_tools import (
            CRP_CONTEXT_TOOLS,
            ContextToolExecutor,
            ToolCall,
            build_tool_system_prompt,
            tool_results_to_messages,
        )

        executor = ContextToolExecutor(
            warm_store=self._warm_store,
            ckf=self._ckf,
            count_tokens=self._provider.count_tokens,
            embed_fn=self._embedding_fn if hasattr(self, "_embedding_fn") else None,
        )

        # ---------- Build tool-aware system prompt ----------
        tool_system = build_tool_system_prompt(
            system_prompt, self._warm_store.fact_count,
        )

        # ---------- Build MINIMAL initial messages ----------
        # Key difference from push model: NO envelope.
        # The LLM will pull context on demand via tool calls.
        messages: list[dict[str, object]] = [
            {"role": "system", "content": tool_system},
            {"role": "user", "content": task_input},
        ]

        # ---------- Advance warm store window ----------
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)
        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # ---------- Iterative tool-mediated generation loop ----------
        total_tool_rounds = 0
        total_tool_tokens = 0
        tool_calls_log: list[dict[str, Any]] = []
        _total_llm_ms = 0.0

        output = ""
        finish_reason = "stop"

        for _round_idx in range(max_tool_rounds + 1):  # +1 for final generation
            # Circuit breaker gate (§audit3: protect all dispatch variants)
            if not self._circuit_breaker.allow_request():
                raise ProviderError(
                    "Circuit breaker OPEN — provider unavailable, "
                    "retry after recovery timeout"
                )

            _t0 = time.monotonic_ns()
            try:
                text, reason, raw_tool_calls, raw_msg = self._provider.generate_chat_with_tools(
                    messages, CRP_CONTEXT_TOOLS, max_tokens=g,
                )
                self._circuit_breaker.record_success()
            except Exception as exc:
                self._circuit_breaker.record_failure()
                logger.error("Provider error (tool dispatch): %s", exc)
                raise ProviderError(_safe_provider_error(exc)) from exc
            _round_ms = (time.monotonic_ns() - _t0) / 1_000_000
            _total_llm_ms += _round_ms

            if reason == "tool_calls" and raw_tool_calls and raw_msg:
                total_tool_rounds += 1
                logger.info(
                    "Tool round %d: %d calls requested",
                    total_tool_rounds, len(raw_tool_calls),
                )

                # Safety: prevent runaway tool loops
                if total_tool_rounds > max_tool_rounds:
                    logger.warning(
                        "Max tool rounds (%d) exceeded — forcing completion",
                        max_tool_rounds,
                    )
                    # Re-send without tools to force a text response
                    try:
                        output, finish_reason = self._provider.generate_chat(
                            messages, max_tokens=g,
                        )
                    except Exception as exc:
                        logger.error("Provider error (tool fallback): %s", exc)
                        raise ProviderError(_safe_provider_error(exc)) from exc
                    break

                # Execute tool calls
                parsed_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    )
                    for tc in raw_tool_calls
                ]
                results = executor.execute_batch(parsed_calls)
                total_tool_tokens += sum(r.tokens_used for r in results)

                # Log tool calls for telemetry
                for tc, result in zip(parsed_calls, results):
                    tool_calls_log.append({
                        "round": total_tool_rounds,
                        "tool": tc.name,
                        "args": tc.arguments,
                        "tokens_returned": result.tokens_used,
                    })

                # Build round-trip messages and append to conversation
                round_messages = tool_results_to_messages(raw_msg, results)
                messages.extend(round_messages)

                logger.info(
                    "Tool round %d complete: %d tokens served (cumulative: %d)",
                    total_tool_rounds, sum(r.tokens_used for r in results),
                    total_tool_tokens,
                )
                continue  # Next iteration — LLM gets tool results

            # Not a tool call — we have final output
            output = text
            finish_reason = reason
            break

        # ---------- Output continuation for tool-mediated dispatch ----------
        # If the final generation hit the token wall, continue across additional
        # windows just like plain dispatch().  Tool rounds are complete; these
        # windows only extend the answer.
        from crp.continuation.manager import ContinuationManager
        cont_mgr = ContinuationManager(self._continuation_config)
        _cont_facts = self._extraction.extract(output, source_window_id=window_id).facts
        cont_state = cont_mgr.process_window(
            task_intent=task_input,
            output=output,
            finish_reason=finish_reason,
            output_tokens=self._provider.count_tokens(output),
            facts=_cont_facts,
            window_id=window_id,
        )
        _cont_window_count = 0
        _last_output = output
        _cont_deadline = time.monotonic() + int(self._config.get("dispatch_timeout", 3600))
        while not cont_state.finished:
            if time.monotonic() > _cont_deadline:
                cont_state.termination_reason = "wall_time_deadline"
                break
            _cont_window_count += 1
            if _cont_window_count > int(self._config.get("max_continuations", 50)):
                cont_state.termination_reason = "max_continuations"
                break

            cont_env = cont_mgr.build_continuation_envelope(
                task_intent=task_input,
                gap_result=cont_state.gap_result,
                structural_state=self._warm_store.structural_state.to_dict(),
                last_output=_last_output,
            )
            cont_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_input},
                {"role": "assistant", "content": output},
                {"role": "user", "content": f"[CONTINUATION]\n{cont_env}"},
            ]
            _t0 = time.monotonic_ns()
            try:
                cont_text, cont_reason = self._provider.generate_chat(
                    cont_messages, max_tokens=g,
                )
                self._circuit_breaker.record_success()
            except Exception as exc:
                self._circuit_breaker.record_failure()
                logger.error("Provider error (tool continuation): %s", exc)
                break
            _total_llm_ms += (time.monotonic_ns() - _t0) / 1_000_000

            cont_wid = f"{window_id}-cont-{_cont_window_count}"
            cont_facts = self._extraction.extract(cont_text, source_window_id=cont_wid).facts
            _last_output = cont_text
            output = f"{output}\n\n{cont_text}"
            finish_reason = cont_reason
            cont_state = cont_mgr.process_window(
                task_intent=task_input,
                output=cont_text,
                finish_reason=cont_reason,
                output_tokens=self._provider.count_tokens(cont_text),
                facts=cont_facts,
                window_id=cont_wid,
            )

        if _cont_window_count > 0 and cont_state.stitched_output:
            output = cont_state.stitched_output
            finish_reason = "stop"

        node.finish_reason = finish_reason
        node.raw_output_id = str(uuid.uuid4())
        node.advance(WindowState.COMPLETED)

        logger.info(
            "Tool-mediated dispatch done: finish=%s, tool_rounds=%d, "
            "cont_windows=%d, tool_tokens=%d, output_chars=%d, llm_ms=%.0f",
            finish_reason, total_tool_rounds, _cont_window_count,
            total_tool_tokens, len(output), _total_llm_ms,
        )

        # ---------- Extract facts from output ----------
        output_tokens = self._provider.count_tokens(output)
        task_intent = TaskIntent(
            task_input=task_input,
            system_prompt=system_prompt,
        )
        extraction = self._extract_and_store(output, window_id, task_intent)
        node.advance(WindowState.EXTRACTED)
        node.facts_produced = [f.id for f in extraction.facts]

        # ---------- Track injection in output ----------
        if extraction.facts:
            penalized = sum(1 for f in extraction.facts if f.flagged_confidence
                           and "injection_in_fact" in f.confidence_flag_reason)
            security_flags.output_injection_facts_penalized = penalized

        # ---------- Quarantine promotion ----------
        if self._quarantine.quarantine_count > 0 and extraction.facts:
            extraction_texts = {f.id: f.text for f in extraction.facts}
            self._quarantine.validate_and_promote(window_id, extraction_texts)

        # ---------- LLM context curation ----------
        if self._curator.should_curate(self._windows_completed):
            try:
                ranked_facts = self._warm_store.get_ranked_facts(limit=50)
                fact_texts = [f.text for f in ranked_facts]
                self._curator.curate(
                    window_index=self._windows_completed,
                    top_facts=fact_texts,
                    recent_output_summary=output[:500],
                )
            except Exception as exc:
                logger.debug("Curator skipped: %s", exc)

        # ---------- Update counters ----------
        self._windows_completed += 1
        e_tokens = total_tool_tokens  # Context served via tools, not envelope
        input_tokens = s_tokens + t_tokens + e_tokens
        self._total_input_tokens += input_tokens
        # Recompute output tokens after any continuation windows.
        output_tokens = self._provider.count_tokens(output)
        self._total_output_tokens += output_tokens
        self._rbac.record_dispatch(tokens_used=output_tokens)

        # ---------- Metrics ----------
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
        _crp_overhead_ms = _total_dispatch_ms - _total_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        metrics = WindowMetrics(
            window_id=node.window_id,
            chain_position=0,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=0,  # No envelope in pull mode
            envelope_budget=0,
            saturation=0.0,   # N/A — context pulled on demand
            generation_reserve=g,
            generation_tokens=output_tokens,
            generation_speed=output_tokens / (_total_llm_ms / 1000) if _total_llm_ms > 0 else 0.0,
            wall_time_ms=int(_total_llm_ms),
            finish_reason=finish_reason,
            facts_extracted=extraction.total_facts,
            continuation_triggered=_cont_window_count > 0,
            continuation_index=_cont_window_count,
            envelope_latency_ms=0.0,
            extraction_latency_ms=0.0,
            extraction_stage_used=",".join(str(s) for s in getattr(extraction, "stages_run", [])),
            gap_coverage=0.0,
            final_gap_score=0.0,
            total_output_tokens=output_tokens,
            reasoning_tokens=0,
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            total_extraction_ms=0.0,
            total_envelope_ms=0.0,
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            # Tool-mediated telemetry (new fields)
            tool_rounds=total_tool_rounds,
            tool_tokens_served=total_tool_tokens,
            tool_calls_detail=tool_calls_log,
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        self._record_dispatch_overhead(_total_dispatch_ms, _total_llm_ms)

        quality_tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=_cont_window_count,
            saturation=0.0,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=node.window_id,
            output=output,
            facts_extracted=extraction.total_facts,
            security_flags=security_flags,
            continuation_windows=0,
            envelope_saturation=0.0,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        return output, report

    # ------------------------------------------------------------------
    # §21.1  Reflexive dispatch — Verify-then-Refine
    # ------------------------------------------------------------------

    def dispatch_reflexive(
        self,
        system_prompt: str,
        task_input: str,
        *,
        max_refinement_passes: int = 2,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Reflexive dispatch — generate first, verify against KB, refine.

        Unlike push (all context upfront) or pull (LLM asks for context),
        reflexive dispatch lets the model generate freely, then CRP
        fact-checks the output against the knowledge base and sends
        back targeted corrections.  The model refines based on SPECIFIC
        evidence rather than wading through pre-loaded context.

        Flow:
          Pass 1: Generate with NO envelope (pure parametric knowledge)
          CRP:    Analyze output — find contradictions, unsupported claims
          Pass 2: Send model its own output + correction payload
          Model:  Refines with surgical precision
          (Optional Pass 3+ if coverage remains low)

        Args:
            system_prompt: System prompt (unmodified per Axiom 4).
            task_input:    User task/prompt.
            max_refinement_passes: Max verify-refine cycles (safety cap).
            **kwargs:      Provider-specific overrides.

        Returns:
            (output_text, QualityReport) — same interface as dispatch().
        """
        from crp.core.relay_strategies import (
            analyze_output_against_kb,
            build_refinement_prompt,
        )

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        _cont_window_count = 0  # reflexive does not implement internal continuation
        self._check_session()

        # ---------- RBAC + validation ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Token measurements ----------
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # ---------- Advance warm store window ----------
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)

        # ===== PASS 1: Generate with NO context (pure parametric knowledge) =====
        messages_pass1: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_input},
        ]

        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # Circuit breaker gate (§audit3: protect all dispatch variants)
        if not self._circuit_breaker.allow_request():
            raise ProviderError(
                "Circuit breaker OPEN — provider unavailable, "
                "retry after recovery timeout"
            )

        _llm_start = time.monotonic_ns()
        try:
            output, finish_reason = self._provider.generate_chat(messages_pass1, max_tokens=g)
            self._circuit_breaker.record_success()
        except Exception as exc:
            self._circuit_breaker.record_failure()
            logger.error("Provider error (reflexive): %s", exc)
            raise ProviderError(_safe_provider_error(exc)) from exc
        _total_llm_ms = (time.monotonic_ns() - _llm_start) / 1_000_000

        total_passes = 1
        total_corrections = 0
        final_coverage = 0.0

        logger.info(
            "Reflexive pass 1 (no context): %d chars, finish=%s",
            len(output), finish_reason,
        )

        # ===== VERIFY & REFINE LOOP =====
        embed_fn = self._embedding_fn if hasattr(self, "_embedding_fn") else None
        for pass_num in range(max_refinement_passes):
            # Analyze output against knowledge base
            analysis = analyze_output_against_kb(
                output=output,
                warm_store=self._warm_store,
                count_tokens=self._provider.count_tokens,
                embed_fn=embed_fn,
            )
            final_coverage = analysis.coverage_score
            total_corrections += len(analysis.corrections)

            if not analysis.needs_refinement:
                logger.info(
                    "Reflexive pass %d: coverage=%.2f, no refinement needed",
                    pass_num + 1, analysis.coverage_score,
                )
                break

            # Build correction payload
            correction_prompt = build_refinement_prompt(
                original_output=output,
                analysis=analysis,
                count_tokens=self._provider.count_tokens,
            )

            # Pass 2+: Send model its own output + corrections
            messages_refine: list[dict[str, str]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_input},
                {"role": "assistant", "content": output},
                {"role": "user", "content": correction_prompt},
            ]

            # Circuit breaker gate for refinement pass (§audit4 M6)
            if not self._circuit_breaker.allow_request():
                raise ProviderError(
                    "Circuit breaker OPEN — provider unavailable during reflexive refinement"
                )

            _llm_refine_start = time.monotonic_ns()
            try:
                output, finish_reason = self._provider.generate_chat(
                    messages_refine, max_tokens=g,
                )
                self._circuit_breaker.record_success()
            except Exception as exc:
                self._circuit_breaker.record_failure()
                logger.error("Provider error (reflexive refinement): %s", exc)
                raise ProviderError(_safe_provider_error(exc)) from exc
            _total_llm_ms += (time.monotonic_ns() - _llm_refine_start) / 1_000_000
            total_passes += 1

            logger.info(
                "Reflexive pass %d: %d corrections applied, coverage=%.2f → %d chars",
                pass_num + 2, len(analysis.corrections),
                analysis.coverage_score, len(output),
            )

        node.finish_reason = finish_reason
        node.raw_output_id = str(uuid.uuid4())
        node.advance(WindowState.COMPLETED)

        # ---------- Extract facts from FINAL output ----------
        output_tokens = self._provider.count_tokens(output)
        task_intent = TaskIntent(task_input=task_input, system_prompt=system_prompt)
        extraction = self._extract_and_store(output, window_id, task_intent)
        node.advance(WindowState.EXTRACTED)
        node.facts_produced = [f.id for f in extraction.facts]

        # ---------- Update counters ----------
        self._windows_completed += 1
        input_tokens = s_tokens + t_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._rbac.record_dispatch(tokens_used=output_tokens)

        # ---------- Metrics ----------
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
        _crp_overhead_ms = _total_dispatch_ms - _total_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        metrics = WindowMetrics(
            window_id=node.window_id,
            chain_position=0,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=0,
            envelope_budget=0,
            saturation=0.0,
            generation_reserve=g,
            generation_tokens=output_tokens,
            generation_speed=output_tokens / (_total_llm_ms / 1000) if _total_llm_ms > 0 else 0.0,
            wall_time_ms=int(_total_llm_ms),
            finish_reason=finish_reason,
            facts_extracted=extraction.total_facts,
            continuation_triggered=False,
            continuation_index=0,
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            total_output_tokens=output_tokens,
            extraction_stage_used=",".join(str(s) for s in getattr(extraction, "stages_run", [])),
            # §21.1 Reflexive telemetry
            relay_strategy="reflexive",
            reflexive_passes=total_passes,
            reflexive_corrections=total_corrections,
            reflexive_coverage=round(final_coverage, 3),
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        self._record_dispatch_overhead(_total_dispatch_ms, _total_llm_ms)

        quality_tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=_cont_window_count,
            saturation=0.0,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=node.window_id,
            output=output,
            facts_extracted=extraction.total_facts,
            security_flags=security_flags,
            continuation_windows=_cont_window_count,
            envelope_saturation=0.0,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        return output, report

    # ------------------------------------------------------------------
    # §21.2  Progressive disclosure — Index → Detail on Demand
    # ------------------------------------------------------------------

    def dispatch_progressive(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Progressive disclosure — send context INDEX first, details on demand.

        Instead of sending ALL facts (push) or none (pull/tools),
        progressive disclosure sends a compact INDEX of available facts
        — one-line summaries — so the model sees WHAT knowledge exists
        at ~10% of the token cost.  After initial generation, CRP detects
        which indexed facts were actually referenced, expands them to
        full detail, and the model refines with targeted depth.

        Flow:
          Step 1: Build compact context index from WarmStore
          Step 2: Send task + index to model (model sees all topics cheaply)
          Step 3: CRP detects which index entries were referenced
          Step 4: Expand referenced entries to full detail
          Step 5: Model refines with deep context on referenced items only

        Args:
            system_prompt: System prompt (unmodified per Axiom 4).
            task_input:    User task/prompt.
            **kwargs:      Provider-specific overrides.

        Returns:
            (output_text, QualityReport) — same interface as dispatch().
        """
        from crp.core.relay_strategies import (
            build_context_index,
            build_detail_injection,
            detect_index_references,
        )

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        self._check_session()

        # ---------- RBAC + validation ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Token measurements ----------
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # ---------- Build context index ----------
        index = build_context_index(
            warm_store=self._warm_store,
            count_tokens=self._provider.count_tokens,
        )
        index_text = index.to_text()
        index_tokens = self._provider.count_tokens(index_text) if index_text else 0

        # ---------- Advance warm store window ----------
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)

        # ===== PASS 1: Generate with context INDEX (not full facts) =====
        messages_indexed: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        if index_text:
            messages_indexed.append({
                "role": "user",
                "content": (
                    f"[CONTEXT INDEX — compact summaries of verified knowledge]\n"
                    f"{index_text}\n"
                    f"[END CONTEXT INDEX]\n\n"
                    f"You may reference items by their [F#] ID if you find them "
                    f"relevant to the task."
                ),
            })
        messages_indexed.append({"role": "user", "content": task_input})

        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # Circuit breaker gate (§audit3: protect all dispatch variants)
        if not self._circuit_breaker.allow_request():
            raise ProviderError(
                "Circuit breaker OPEN — provider unavailable, "
                "retry after recovery timeout"
            )

        _llm_start = time.monotonic_ns()
        try:
            output, finish_reason = self._provider.generate_chat(
                messages_indexed, max_tokens=g,
            )
            self._circuit_breaker.record_success()
        except Exception as exc:
            self._circuit_breaker.record_failure()
            logger.error("Provider error (progressive index): %s", exc)
            raise ProviderError(_safe_provider_error(exc)) from exc
        _total_llm_ms = (time.monotonic_ns() - _llm_start) / 1_000_000

        logger.info(
            "Progressive pass 1 (index): %d index entries (%d tokens), "
            "output=%d chars",
            len(index.entries), index_tokens, len(output),
        )

        # ===== DETECT REFERENCES & EXPAND =====
        detail_tokens = 0
        detail_entries = 0
        if index.entries:
            referenced = detect_index_references(output, index)
            detail_entries = len(referenced)

            if referenced:
                detail_text = build_detail_injection(
                    referenced,
                    count_tokens=self._provider.count_tokens,
                )
                detail_tokens = self._provider.count_tokens(detail_text) if detail_text else 0

                if detail_text:
                    # Pass 2: Refine with expanded details
                    messages_detail: list[dict[str, str]] = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task_input},
                        {"role": "assistant", "content": output},
                        {
                            "role": "user",
                            "content": (
                                f"{detail_text}\n\n"
                                f"Please refine your response incorporating the "
                                f"expanded details above. Maintain your structure "
                                f"but enhance accuracy with the full verified content."
                            ),
                        },
                    ]

                    # Circuit breaker gate for detail pass (\u00a7audit4 M7)
                    if not self._circuit_breaker.allow_request():
                        raise ProviderError(
                            "Circuit breaker OPEN \u2014 provider unavailable during progressive detail"
                        )

                    _llm_detail_start = time.monotonic_ns()
                    try:
                        output, finish_reason = self._provider.generate_chat(
                            messages_detail, max_tokens=g,
                        )
                        self._circuit_breaker.record_success()
                    except Exception as exc:
                        self._circuit_breaker.record_failure()
                        logger.error("Provider error (progressive detail): %s", exc)
                        raise ProviderError(_safe_provider_error(exc)) from exc
                    _total_llm_ms += (time.monotonic_ns() - _llm_detail_start) / 1_000_000

                    logger.info(
                        "Progressive pass 2 (detail): %d entries expanded (%d tokens), "
                        "output=%d chars",
                        detail_entries, detail_tokens, len(output),
                    )

        node.finish_reason = finish_reason
        node.raw_output_id = str(uuid.uuid4())
        node.advance(WindowState.COMPLETED)

        # ---------- Extract facts from final output ----------
        output_tokens = self._provider.count_tokens(output)
        task_intent = TaskIntent(task_input=task_input, system_prompt=system_prompt)
        extraction = self._extract_and_store(output, window_id, task_intent)
        node.advance(WindowState.EXTRACTED)
        node.facts_produced = [f.id for f in extraction.facts]

        # ---------- Update counters ----------
        self._windows_completed += 1
        input_tokens = s_tokens + t_tokens + index_tokens + detail_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._rbac.record_dispatch(tokens_used=output_tokens)

        # ---------- Metrics ----------
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
        _crp_overhead_ms = _total_dispatch_ms - _total_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        metrics = WindowMetrics(
            window_id=node.window_id,
            chain_position=0,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=index_tokens + detail_tokens,
            envelope_budget=0,
            saturation=0.0,
            generation_reserve=g,
            generation_tokens=output_tokens,
            generation_speed=output_tokens / (_total_llm_ms / 1000) if _total_llm_ms > 0 else 0.0,
            wall_time_ms=int(_total_llm_ms),
            finish_reason=finish_reason,
            facts_extracted=extraction.total_facts,
            continuation_triggered=False,
            continuation_index=0,
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            total_output_tokens=output_tokens,
            extraction_stage_used=",".join(str(s) for s in getattr(extraction, "stages_run", [])),
            # §21.2 Progressive telemetry
            relay_strategy="progressive",
            progressive_index_entries=len(index.entries),
            progressive_index_tokens=index_tokens,
            progressive_detail_entries=detail_entries,
            progressive_detail_tokens=detail_tokens,
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        self._record_dispatch_overhead(_total_dispatch_ms, _total_llm_ms)

        quality_tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=0,
            saturation=0.0,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=node.window_id,
            output=output,
            facts_extracted=extraction.total_facts,
            security_flags=security_flags,
            continuation_windows=0,
            envelope_saturation=0.0,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        return output, report

    # ------------------------------------------------------------------
    # §21.3  Stream-augmented generation — Real-time Context Injection
    # ------------------------------------------------------------------

    def dispatch_stream_augmented(
        self,
        system_prompt: str,
        task_input: str,
        *,
        max_injections: int = 5,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Stream-augmented generation — inject context mid-generation.

        The most novel strategy: CRP monitors the LLM's output stream
        in real-time, buffering sentences.  After each sentence, CRP
        checks if relevant WarmStore facts exist for the topic being
        generated.  When relevant facts are found, generation is
        PAUSED, the partial output + injected facts are sent as a
        continuation, and the model resumes — now informed.

        The model receives context EXACTLY when it's generating about
        a relevant topic, not before (wasted) and not only when it
        asks (pull).  This is point-of-need context delivery.

        Flow:
          1. Start streaming generation (no envelope)
          2. Buffer tokens into sentences
          3. After each sentence: CRP fact-matches against WarmStore
          4. If relevant NEW facts found → stop generation
          5. Send partial output + injected facts as continuation prompt
          6. Resume generation from where model left off
          7. Repeat until generation completes or max_injections reached

        Args:
            system_prompt: System prompt (unmodified per Axiom 4).
            task_input:    User task/prompt.
            max_injections: Maximum mid-stream injections (safety cap).
            **kwargs:      Provider-specific overrides.

        Returns:
            (output_text, QualityReport) — same interface as dispatch().
        """
        from crp.core.relay_strategies import (
            AugmentationEvent,
            StreamAugmentationState,
            build_augmented_continuation,
            find_relevant_facts_for_sentence,
        )

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        self._check_session()

        # ---------- RBAC + validation ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Token measurements ----------
        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out, self._provider.max_output_tokens, context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # ---------- Advance warm store window ----------
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)
        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # ===== STREAMING WITH REAL-TIME AUGMENTATION =====
        aug_state = StreamAugmentationState()
        already_injected: set[str] = set()
        _total_llm_ms = 0.0
        finish_reason = "stop"
        accumulated_output = ""
        self._embedding_fn if hasattr(self, "_embedding_fn") else None

        # Initial messages — no envelope, just system prompt + task
        current_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_input},
        ]

        generation_round = 0
        while generation_round <= max_injections:
            generation_round += 1
            sentence_buffer = ""
            round_output_chunks: list[str] = []
            injection_triggered = False

            # Circuit breaker gate (§audit3: protect all dispatch variants)
            if not self._circuit_breaker.allow_request():
                raise ProviderError(
                    "Circuit breaker OPEN — provider unavailable, "
                    "retry after recovery timeout"
                )

            _llm_start = time.monotonic_ns()
            try:
                gen = self._provider.generate_chat_stream(
                    current_messages, max_tokens=g,
                )
                while True:
                    try:
                        chunk = next(gen)
                        round_output_chunks.append(chunk)
                        sentence_buffer += chunk

                        # Check for sentence boundary
                        if any(sentence_buffer.rstrip().endswith(p) for p in ".!?\n"):
                            aug_state.sentences_completed += 1

                            # Only check every 2 sentences to avoid overhead
                            if aug_state.should_check and aug_state.total_injections < max_injections:
                                relevant = find_relevant_facts_for_sentence(
                                    sentence=sentence_buffer,
                                    warm_store=self._warm_store,
                                    already_injected=already_injected,
                                    count_tokens=self._provider.count_tokens,
                                )
                                if relevant:
                                    # INJECTION POINT — pause generation
                                    _total_llm_ms += (time.monotonic_ns() - _llm_start) / 1_000_000

                                    # Record partial output
                                    round_text = "".join(round_output_chunks)
                                    accumulated_output += round_text

                                    # Track injection
                                    injection_tokens = sum(
                                        self._provider.count_tokens(text)
                                        for _, text in relevant
                                    )
                                    already_injected.update(fid for fid, _ in relevant)
                                    aug_state.total_injections += 1
                                    aug_state.total_injection_tokens += injection_tokens
                                    aug_state.augmentation_events.append(
                                        AugmentationEvent(
                                            sentence_index=aug_state.sentences_completed,
                                            trigger_text=sentence_buffer[:100],
                                            facts_injected=len(relevant),
                                            injection_tokens=injection_tokens,
                                            resumption_point=accumulated_output[-50:],
                                        )
                                    )

                                    logger.info(
                                        "Stream augmentation #%d at sentence %d: "
                                        "%d facts injected (%d tokens)",
                                        aug_state.total_injections,
                                        aug_state.sentences_completed,
                                        len(relevant), injection_tokens,
                                    )

                                    # Build continuation messages
                                    current_messages = build_augmented_continuation(
                                        system_prompt=system_prompt,
                                        partial_output=accumulated_output,
                                        injected_facts=relevant,
                                        task_input=task_input,
                                    )
                                    injection_triggered = True
                                    break  # Break out of streaming loop to restart

                            sentence_buffer = ""  # Reset buffer after check

                    except StopIteration as stop:
                        finish_reason = stop.value or "stop"
                        self._circuit_breaker.record_success()
                        break

            except Exception as exc:
                self._circuit_breaker.record_failure()
                logger.error("Stream augmentation error: %s", exc)
                finish_reason = "error"
                break

            _total_llm_ms += (time.monotonic_ns() - _llm_start) / 1_000_000

            if not injection_triggered:
                # Generation completed normally
                accumulated_output += "".join(round_output_chunks)
                break

        output = accumulated_output

        # ---------- Output continuation for stream-augmented dispatch ----------
        # If the final generation hit the token wall, continue across additional
        # windows just like plain dispatch().  Mid-stream injections are complete;
        # these windows only extend the answer.
        task_intent = TaskIntent(task_input=task_input, system_prompt=system_prompt)
        initial_extraction = self._extraction.extract(output, source_window_id=window_id)
        cont_config = getattr(self, "_continuation_config", None) or ContinuationConfig(
            max_continuations=int(self._config.get("max_continuations", 50)),
        )
        cont_mgr = ContinuationManager(cont_config)
        cont_state = cont_mgr.process_window(
            task_intent=task_input,
            output=output,
            finish_reason=finish_reason,
            output_tokens=self._provider.count_tokens(output),
            facts=initial_extraction.facts,
            window_id=window_id,
        )
        _cont_window_count = 0
        _last_output = output
        _cont_deadline = time.monotonic() + int(self._config.get("dispatch_timeout", 3600))
        _max_continuations = int(self._config.get("max_continuations", 50))
        while not cont_state.finished:
            if time.monotonic() > _cont_deadline:
                cont_state.termination_reason = "wall_time_deadline"
                break
            _cont_window_count += 1
            if _cont_window_count > _max_continuations:
                cont_state.termination_reason = "max_continuations"
                break

            cont_env = cont_mgr.build_continuation_envelope(
                task_intent=task_input,
                gap_result=cont_state.gap_result,
                structural_state=self._warm_store.structural_state.to_dict(),
                last_output=_last_output,
            )
            cont_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_input},
                {"role": "assistant", "content": output},
                {"role": "user", "content": f"[CONTINUATION]\n{cont_env}"},
            ]
            _t0 = time.monotonic_ns()
            try:
                cont_text, cont_reason = self._provider.generate_chat(cont_messages, max_tokens=g)
                self._circuit_breaker.record_success()
            except Exception as exc:
                self._circuit_breaker.record_failure()
                logger.error("Provider error (stream-augmented continuation): %s", exc)
                break
            _total_llm_ms += (time.monotonic_ns() - _t0) / 1_000_000

            cont_wid = f"{window_id}-cont-{_cont_window_count}"
            cont_facts = self._extraction.extract(cont_text, source_window_id=cont_wid).facts
            _last_output = cont_text
            output = f"{output}\n\n{cont_text}"
            finish_reason = cont_reason
            cont_state = cont_mgr.process_window(
                task_intent=task_input,
                output=cont_text,
                finish_reason=cont_reason,
                output_tokens=self._provider.count_tokens(cont_text),
                facts=cont_facts,
                window_id=cont_wid,
            )

        if _cont_window_count > 0 and cont_state.stitched_output:
            output = cont_state.stitched_output
            finish_reason = "stop"

        node.finish_reason = finish_reason
        node.raw_output_id = str(uuid.uuid4())
        node.advance(WindowState.COMPLETED)

        # ---------- Extract facts from final output ----------
        output_tokens = self._provider.count_tokens(output)
        task_intent = TaskIntent(task_input=task_input, system_prompt=system_prompt)
        extraction = self._extract_and_store(output, window_id, task_intent)
        node.advance(WindowState.EXTRACTED)
        node.facts_produced = [f.id for f in extraction.facts]

        # ---------- Update counters ----------
        self._windows_completed += 1
        input_tokens = s_tokens + t_tokens + aug_state.total_injection_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._rbac.record_dispatch(tokens_used=output_tokens)

        # ---------- Metrics ----------
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
        _crp_overhead_ms = _total_dispatch_ms - _total_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        metrics = WindowMetrics(
            window_id=node.window_id,
            chain_position=0,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=aug_state.total_injection_tokens,
            envelope_budget=0,
            saturation=0.0,
            generation_reserve=g,
            generation_tokens=output_tokens,
            generation_speed=output_tokens / (_total_llm_ms / 1000) if _total_llm_ms > 0 else 0.0,
            wall_time_ms=int(_total_llm_ms),
            finish_reason=finish_reason,
            facts_extracted=extraction.total_facts,
            continuation_triggered=(aug_state.total_injections > 0) or (_cont_window_count > 0),
            continuation_index=aug_state.total_injections + _cont_window_count,
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            total_output_tokens=output_tokens,
            extraction_stage_used=",".join(str(s) for s in getattr(extraction, "stages_run", [])),
            # §21.3 Stream-augmented telemetry
            relay_strategy="stream_augmented",
            stream_augment_injections=aug_state.total_injections,
            stream_augment_injection_tokens=aug_state.total_injection_tokens,
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        self._record_dispatch_overhead(_total_dispatch_ms, _total_llm_ms)

        quality_tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=0,
            saturation=0.0,
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=node.window_id,
            output=output,
            facts_extracted=extraction.total_facts,
            security_flags=security_flags,
            continuation_windows=_cont_window_count,
            envelope_saturation=0.0,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        return output, report

    # ------------------------------------------------------------------
    # Agentic dispatch — LLM-in-the-loop cognitive engine (§22)
    # ------------------------------------------------------------------

    def dispatch_agentic(
        self,
        system_prompt: str,
        task_input: str,
        *,
        max_revision_rounds: int = 2,
        enable_curation: bool = True,
        enable_planning: bool = True,
        **kwargs: Any,
    ) -> tuple[str, QualityReport]:
        """Agentic dispatch — CRP uses the LLM as its internal brain.

        ╔═══════════════════════════════════════════════════════════╗
        ║                 §22 AGENTIC COGNITIVE LOOP               ║
        ╠═══════════════════════════════════════════════════════════╣
        ║  1. ANALYZE   — LLM analyzes task complexity & needs     ║
        ║  2. PLAN      — LLM decomposes complex tasks             ║
        ║  3. SYNTHESIZE — LLM pre-processes KB facts              ║
        ║  4. ROUTE     — LLM picks optimal dispatch strategy      ║
        ║  5. GENERATE  — Execute chosen dispatch strategy         ║
        ║  6. EVALUATE  — LLM evaluates output quality             ║
        ║  7. REVISE    — If evaluation says revision needed        ║
        ║  8. CURATE    — LLM manages CRP's knowledge base         ║
        ╚═══════════════════════════════════════════════════════════╝

        The LLM is INSIDE CRP.  CRP orchestrates all reasoning.
        Every decision point uses the LLM instead of heuristics.
        """
        from crp.core.facilitator import CRPFacilitator

        _dispatch_start_ns = time.monotonic_ns()
        _facts_before = self._warm_store.fact_count
        self._check_session()

        # ---------- RBAC + validation (same as dispatch) ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(
                val_result.warnings[0] if val_result.warnings else "Input validation failed"
            )
        task_input = val_result.sanitized_text

        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        # ---------- Initialize facilitator ----------
        facilitator = CRPFacilitator(
            provider=self._provider,
            count_tokens=self._provider.count_tokens,
        )

        # ══════════════════════════════════════════════════════════
        # PHASE 1: TASK ANALYSIS — LLM understands the task
        # ══════════════════════════════════════════════════════════
        logger.info("§22 Phase 1: Task Analysis")
        task_analysis = facilitator.analyze_task(
            task_input=task_input,
            system_prompt=system_prompt,
            fact_count=self._warm_store.fact_count,
        )
        logger.info(
            "Task analysis: complexity=%s, domain=%s, needs=%s, confidence=%.2f",
            task_analysis.complexity,
            task_analysis.domain,
            task_analysis.knowledge_needs[:3],
            task_analysis.confidence,
        )

        # ══════════════════════════════════════════════════════════
        # PHASE 2: EXECUTION PLANNING — LLM decomposes if complex
        # ══════════════════════════════════════════════════════════
        plan = None
        if enable_planning and task_analysis.complexity in ("complex", "multi_part"):
            logger.info("§22 Phase 2: Execution Planning")
            plan = facilitator.plan_execution(
                analysis=task_analysis,
                fact_count=self._warm_store.fact_count,
            )
            logger.info(
                "Execution plan: %d steps, estimated_windows=%d",
                len(plan.steps), plan.estimated_windows,
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 3: FACT SYNTHESIS — LLM pre-processes knowledge
        # ══════════════════════════════════════════════════════════
        synthesis = None
        if self._warm_store.fact_count > 0:
            logger.info("§22 Phase 3: Fact Synthesis")
            ranked = self._warm_store.get_ranked_facts(limit=30)
            facts_for_synthesis = [
                (f.id, f.text, f.confidence) for f in ranked
            ]
            synthesis = facilitator.synthesize_facts(
                facts=facts_for_synthesis,
                task_context=task_input[:200],
            )
            logger.info(
                "Synthesis: %d insights, %d gaps, %d redundant",
                len(synthesis.key_insights),
                len(synthesis.knowledge_gaps),
                len(synthesis.redundant_fact_ids),
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 4: STRATEGY ROUTING — LLM picks optimal strategy
        # ══════════════════════════════════════════════════════════
        logger.info("§22 Phase 4: Strategy Routing")
        available_strategies = ["push", "reflexive", "progressive", "stream_augmented"]
        strategy_decision = facilitator.route_strategy(
            analysis=task_analysis,
            fact_count=self._warm_store.fact_count,
            available_strategies=available_strategies,
        )
        chosen_strategy = strategy_decision.strategy
        logger.info(
            "Strategy: %s (confidence=%.2f, reasoning=%s)",
            chosen_strategy,
            strategy_decision.confidence,
            strategy_decision.reasoning[:80],
        )

        # ══════════════════════════════════════════════════════════
        # PHASE 5: GENERATE — Execute via chosen strategy
        #
        #   §22-FIX-A: Multi-step plan execution.
        #   If Phase 2 produced a plan with >1 step, CRP executes
        #   EACH step sequentially with its own strategy, feeding
        #   accumulated outputs forward.  This turns the ExecutionPlan
        #   from dead code into real multi-window orchestration.
        #
        #   §22-FIX-D: Synthesis into augmented system prompt with
        #   explicit structural markers for the LLM.
        # ══════════════════════════════════════════════════════════
        logger.info("§22 Phase 5: Generate via strategy=%s", chosen_strategy)

        # Augment system prompt with synthesis if available
        augmented_system = system_prompt
        if synthesis and synthesis.summary:
            augmented_system = (
                f"{system_prompt}\n\n"
                f"[CRP KNOWLEDGE SYNTHESIS]\n"
                f"{synthesis.summary}\n"
            )
            if synthesis.key_insights:
                augmented_system += "Key insights:\n" + "\n".join(
                    f"- {i}" for i in synthesis.key_insights[:5]
                ) + "\n"
            if synthesis.knowledge_gaps:
                augmented_system += "Knowledge gaps:\n" + "\n".join(
                    f"- {g}" for g in synthesis.knowledge_gaps[:3]
                ) + "\n"
            if synthesis.contradictions:
                augmented_system += "Contradictions to resolve:\n" + "\n".join(
                    f"- {c}" for c in synthesis.contradictions[:3]
                ) + "\n"

        # Strategy dispatch map for all strategies
        _strategy_dispatch_map: dict[str, Any] = {
            "push": self.dispatch,
            "reflexive": self.dispatch_reflexive,
            "progressive": self.dispatch_progressive,
            "stream_augmented": self.dispatch_stream_augmented,
        }

        # §22-FIX-A: Multi-step plan execution
        if plan and len(plan.steps) > 1:
            logger.info(
                "§22 Phase 5: Multi-step execution — %d steps",
                len(plan.steps),
            )
            accumulated_outputs: list[tuple[str, str]] = []  # (step_desc, output)
            output = ""
            inner_report = None

            # Sort steps by priority (lower = higher priority) and
            # respect dependency ordering: a step can only execute
            # after all steps in its depends_on list are complete.
            completed_indices: set[int] = set()
            remaining = list(enumerate(plan.steps))

            while remaining:
                # Find next runnable step (dependencies satisfied)
                runnable = [
                    (idx, step)
                    for idx, step in remaining
                    if all(d in completed_indices for d in step.depends_on)
                ]
                if not runnable:
                    # Deadlock — remaining steps have unresolvable deps.
                    # Run them sequentially to avoid stalling.
                    runnable = remaining

                step_idx, step = runnable[0]
                remaining = [
                    (i, s) for i, s in remaining if i != step_idx
                ]

                step_strategy = step.strategy
                step_fn = _strategy_dispatch_map.get(step_strategy, self.dispatch)

                # Build step-specific task with accumulated context
                if accumulated_outputs:
                    prior_context = "\n\n".join(
                        f"[Step: {desc}]\n{out[:800]}"
                        for desc, out in accumulated_outputs[-3:]  # Last 3 steps
                    )
                    step_task = (
                        f"=== ORIGINAL TASK ===\n{task_input[:400]}\n"
                        f"=== COMPLETED STEPS ===\n{prior_context}\n"
                        f"=== CURRENT STEP ===\n{step.description}\n"
                        f"Context needs: {', '.join(step.context_needs[:3])}\n"
                        f"=== GENERATE OUTPUT FOR THIS STEP ==="
                    )
                else:
                    step_task = (
                        f"=== TASK ===\n{task_input[:500]}\n"
                        f"=== CURRENT STEP ===\n{step.description}\n"
                        f"Context needs: {', '.join(step.context_needs[:3])}\n"
                        f"=== GENERATE OUTPUT FOR THIS STEP ==="
                    )

                logger.info(
                    "§22 Step %d/%d: strategy=%s, desc=%s",
                    step_idx + 1, len(plan.steps),
                    step_strategy, step.description[:60],
                )

                step_output, step_report = step_fn(
                    augmented_system, step_task, **kwargs,
                )
                accumulated_outputs.append((step.description, step_output))
                completed_indices.add(step_idx)

                # Keep the last step's output and report as primary
                output = step_output
                inner_report = step_report

            # For multi-step: combine all step outputs into final output
            if len(accumulated_outputs) > 1:
                output = "\n\n".join(
                    out for _, out in accumulated_outputs
                )

            logger.info(
                "§22 Multi-step execution complete: %d steps, total_chars=%d",
                len(accumulated_outputs), len(output),
            )
        else:
            # Single-step dispatch (original path)
            dispatch_fn = _strategy_dispatch_map.get(chosen_strategy, self.dispatch)
            output, inner_report = dispatch_fn(
                augmented_system, task_input, **kwargs,
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 5b: CONTINUATION AWARENESS
        #
        #   §22-FIX-B: Extract continuation info from inner dispatch.
        #   The inner dispatch may have used multiple continuation
        #   windows.  This context feeds into evaluation so the LLM
        #   knows whether the output is complete or truncated.
        # ══════════════════════════════════════════════════════════
        inner_telemetry = inner_report.telemetry or {} if inner_report else {}
        inner_continuation_count = (
            inner_report.continuation_windows if inner_report else 0
        )
        inner_finish = inner_telemetry.get("finish_reason", "stop")

        if inner_continuation_count > 0:
            logger.info(
                "§22 Phase 5b: Inner dispatch used %d continuation windows "
                "(finish=%s)",
                inner_continuation_count, inner_finish,
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 5c: AGENTIC CONTINUATION WRAPPER
        #
        #   If the inner strategy (reflexive/progressive/stream_augmented)
        #   hits the token wall and does not continue internally, run a
        #   bounded push-based continuation loop here so agentic dispatch
        #   never returns silently truncated output.
        # ══════════════════════════════════════════════════════════
        agentic_continuation_windows = 0
        if inner_finish == "length" and inner_continuation_count == 0 and inner_report:
            logger.info("§22 Phase 5c: Agentic continuation wrapper triggered")
            cont_config = getattr(self, "_continuation_config", None) or ContinuationConfig(
                max_continuations=int(self._config.get("max_continuations", 50)),
            )
            cont_mgr = ContinuationManager(cont_config)
            TaskIntent(task_input=task_input, system_prompt=system_prompt)
            init_facts = self._extraction.extract(
                output, source_window_id=inner_report.window_id,
            ).facts
            cont_state = cont_mgr.process_window(
                task_intent=task_input,
                output=output,
                finish_reason=inner_finish,
                output_tokens=self._provider.count_tokens(output),
                facts=init_facts,
                window_id=inner_report.window_id,
            )
            _last_output = output
            _cont_deadline = time.monotonic() + int(self._config.get("dispatch_timeout", 3600))
            _max_continuations = cont_config.max_continuations
            while not cont_state.finished:
                if time.monotonic() > _cont_deadline:
                    cont_state.termination_reason = "wall_time_deadline"
                    break
                agentic_continuation_windows += 1
                if agentic_continuation_windows > _max_continuations:
                    cont_state.termination_reason = "max_continuations"
                    break

                cont_env = cont_mgr.build_continuation_envelope(
                    task_intent=task_input,
                    gap_result=cont_state.gap_result,
                    structural_state=self._warm_store.structural_state.to_dict(),
                    last_output=_last_output,
                )
                task_title = self._extract_task_title(task_input)
                cont_task = (
                    f"=== ORIGINAL TASK ===\n"
                    f"{task_title}\n"
                    f"=== CONTINUATION DIRECTIVES ===\n"
                    f"{cont_env}\n"
                    f"=== END DIRECTIVES ==="
                )
                try:
                    cont_output, cont_report = self.dispatch(
                        augmented_system, cont_task, **kwargs,
                    )
                except Exception as exc:
                    logger.error("Agentic continuation window failed: %s", exc)
                    break

                cont_wid = cont_report.window_id if cont_report else ""
                cont_facts = self._extraction.extract(
                    cont_output, source_window_id=cont_wid or inner_report.window_id,
                ).facts
                _last_output = cont_output
                output = f"{output}\n\n{cont_output}"
                inner_finish = cont_report.telemetry.get("finish_reason", "stop") if cont_report else "stop"
                agentic_continuation_windows += getattr(cont_report, "continuation_windows", 0)
                cont_state = cont_mgr.process_window(
                    task_intent=task_input,
                    output=cont_output,
                    finish_reason=inner_finish,
                    output_tokens=self._provider.count_tokens(cont_output),
                    facts=cont_facts,
                    window_id=cont_wid or inner_report.window_id,
                )

            if agentic_continuation_windows > 0 and cont_state.stitched_output:
                output = cont_state.stitched_output
                inner_finish = "stop"

            inner_continuation_count += agentic_continuation_windows

        # ══════════════════════════════════════════════════════════
        # PHASE 6: EVALUATE — LLM assesses output quality
        #
        #   §22-FIX-B: Evaluation now knows about continuation state
        #   so it can assess whether truncation hurt quality.
        # ══════════════════════════════════════════════════════════
        logger.info("§22 Phase 6: Output Evaluation")
        evaluation = facilitator.evaluate_output(
            task_input=task_input,
            output=output,
            facts_used=inner_report.facts_extracted if inner_report else 0,
        )
        logger.info(
            "Evaluation: grade=%s, completion=%.2f, revision_needed=%s, "
            "continuations=%d",
            evaluation.overall_grade,
            evaluation.task_completion,
            evaluation.revision_needed,
            inner_continuation_count,
        )

        # ══════════════════════════════════════════════════════════
        # PHASE 7: REVISE — If evaluation says output needs work
        #
        #   §22-FIX-C: Enhanced revision. Instead of a bare
        #   "please revise" message, CRP feeds:
        #   - Structured evaluation scores (completion, coherence)
        #   - Specific missing elements as knowledge gaps
        #   - Synthesis insights that may not have been used
        #   - Continuation context (was output truncated?)
        #   - Strategy adjustment: if chosen strategy scored poorly,
        #     try an alternative strategy on revision.
        # ══════════════════════════════════════════════════════════
        revision_rounds = 0
        # Track strategy for potential adjustment during revision
        revision_strategy = chosen_strategy

        while (
            evaluation.revision_needed
            and revision_rounds < max_revision_rounds
            and evaluation.task_completion < 0.7
        ):
            revision_rounds += 1
            logger.info(
                "§22 Phase 7: Revision round %d — focus: %s",
                revision_rounds, evaluation.revision_focus,
            )

            # §22-FIX-C: Strategy adjustment on poor first attempt
            # If first attempt scored very poorly (< 0.4 completion),
            # try a different strategy for the revision.
            if (
                revision_rounds == 1
                and evaluation.task_completion < 0.4
                and revision_strategy in _strategy_dispatch_map
            ):
                alt_strategies = [
                    s for s in _strategy_dispatch_map
                    if s != revision_strategy
                ]
                if alt_strategies:
                    revision_strategy = alt_strategies[0]
                    logger.info(
                        "§22 Strategy adjustment: %s → %s (completion=%.2f too low)",
                        chosen_strategy, revision_strategy,
                        evaluation.task_completion,
                    )

            revision_fn = _strategy_dispatch_map.get(
                revision_strategy, self.dispatch,
            )

            # §22-FIX-C: Build enhanced revision directive with
            # structured feedback, synthesis carry-forward, and
            # continuation awareness.
            _missing = ", ".join(evaluation.missing_elements[:5]) or "none identified"
            _synthesis_hints = ""
            if synthesis and synthesis.key_insights:
                unused_insights = synthesis.key_insights[:3]
                _synthesis_hints = (
                    "Available knowledge (may help fill gaps):\n"
                    + "\n".join(f"- {i}" for i in unused_insights) + "\n"
                )
            _continuation_note = ""
            if inner_continuation_count > 0 and inner_finish == "length":
                _continuation_note = (
                    "NOTE: Previous output may have been truncated "
                    f"(used {inner_continuation_count} continuation windows). "
                    "Ensure the revision is complete.\n"
                )

            revision_task = (
                f"=== REVISION REQUEST (Round {revision_rounds}) ===\n"
                f"Original task: {task_input[:300]}\n\n"
                f"[EVALUATION FEEDBACK]\n"
                f"  Task completion: {evaluation.task_completion:.0%}\n"
                f"  Factual accuracy: {evaluation.factual_accuracy:.0%}\n"
                f"  Coherence: {evaluation.coherence:.0%}\n"
                f"  Grade: {evaluation.overall_grade}\n"
                f"  Revision focus: {evaluation.revision_focus}\n"
                f"  Missing elements: {_missing}\n\n"
                f"{_synthesis_hints}"
                f"{_continuation_note}"
                f"[PREVIOUS OUTPUT (for reference)]\n{output[:1000]}\n\n"
                f"=== PROVIDE IMPROVED, COMPLETE OUTPUT ==="
            )

            # §22-FIX-C: Augment system prompt with evaluation context
            revision_system = augmented_system
            if evaluation.overall_grade in ("C", "D"):
                revision_system = (
                    f"{augmented_system}\n\n"
                    f"[CRP REVISION CONTEXT]\n"
                    f"The previous output scored {evaluation.overall_grade}. "
                    f"Focus on: {evaluation.revision_focus}. "
                    f"Missing: {_missing}."
                )

            output, inner_report = revision_fn(
                revision_system, revision_task, **kwargs,
            )

            # Re-evaluate
            evaluation = facilitator.evaluate_output(
                task_input=task_input,
                output=output,
                facts_used=inner_report.facts_extracted,
            )
            logger.info(
                "Revision %d evaluation: grade=%s, completion=%.2f",
                revision_rounds, evaluation.overall_grade, evaluation.task_completion,
            )

            # §22-FIX-E: Post-revision curation — run intermediate
            # curation after each revision so knowledge base reflects
            # what was learned from the revision attempt.
            if enable_curation and self._warm_store.fact_count > 5:
                ranked = self._warm_store.get_ranked_facts(limit=15)
                revision_facts = [
                    (f.id, f.text, f.confidence, getattr(f, "age", 0))
                    for f in ranked
                ]
                rev_curation = facilitator.curate_memory(
                    facts=revision_facts,
                    recent_task=f"Revision round {revision_rounds}: {evaluation.revision_focus}",
                )
                for fid in rev_curation.promote_ids:
                    try:
                        self._warm_store.boost_confidence(fid, 0.05)
                    except Exception:
                        pass
                for fid in rev_curation.demote_ids:
                    try:
                        self._warm_store.reduce_confidence(fid, 0.05)
                    except Exception:
                        pass

        # ══════════════════════════════════════════════════════════
        # PHASE 8: CURATE — LLM manages CRP's memory
        # ══════════════════════════════════════════════════════════
        curation_actions = 0
        if enable_curation and self._warm_store.fact_count > 5:
            logger.info("§22 Phase 8: Memory Curation")
            ranked = self._warm_store.get_ranked_facts(limit=25)
            facts_for_curation = [
                (f.id, f.text, f.confidence, getattr(f, "age", 0))
                for f in ranked
            ]
            curation = facilitator.curate_memory(
                facts=facts_for_curation,
                recent_task=task_input[:200],
            )

            # Execute curation decisions on WarmStore
            for fid in curation.promote_ids:
                try:
                    self._warm_store.boost_confidence(fid, 0.1)
                    curation_actions += 1
                except Exception:
                    pass  # Fact may no longer exist

            for fid in curation.demote_ids:
                try:
                    self._warm_store.reduce_confidence(fid, 0.1)
                    curation_actions += 1
                except Exception:
                    pass

            logger.info(
                "Curation: promote=%d, demote=%d, actions=%d — %s",
                len(curation.promote_ids),
                len(curation.demote_ids),
                curation_actions,
                curation.reasoning[:80],
            )

        # ══════════════════════════════════════════════════════════
        # Build telemetry + quality report
        # ══════════════════════════════════════════════════════════
        fac_metrics = facilitator.metrics
        _total_dispatch_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000

        # Parse inner report telemetry for LLM time
        inner_telemetry = inner_report.telemetry or {}
        inner_llm_ms = inner_telemetry.get("total_llm_ms", 0)
        inner_extraction_ms = inner_telemetry.get("total_extraction_ms", 0)
        inner_envelope_ms = inner_telemetry.get("total_envelope_ms", 0)

        _total_llm_ms = inner_llm_ms + fac_metrics.total_cognitive_ms
        _crp_overhead_ms = _total_dispatch_ms - inner_llm_ms
        _crp_overhead_pct = (_crp_overhead_ms / _total_dispatch_ms * 100) if _total_dispatch_ms > 0 else 0.0

        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        output_tokens = self._provider.count_tokens(output)

        metrics = WindowMetrics(
            window_id=inner_report.window_id,
            chain_position=inner_continuation_count,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=inner_telemetry.get("envelope_tokens", 0),
            envelope_budget=inner_telemetry.get("envelope_budget", 0),
            saturation=inner_report.envelope_saturation,
            generation_reserve=inner_telemetry.get("generation_reserve", 0),
            generation_tokens=output_tokens,
            wall_time_ms=int(_total_dispatch_ms),
            finish_reason=inner_finish,
            facts_extracted=inner_report.facts_extracted,
            continuation_triggered=inner_continuation_count > 0,
            continuation_index=inner_continuation_count,
            # CRP overhead
            total_dispatch_ms=round(_total_dispatch_ms),
            total_llm_ms=round(_total_llm_ms),
            total_extraction_ms=round(inner_extraction_ms),
            total_envelope_ms=round(inner_envelope_ms),
            crp_overhead_ms=round(_crp_overhead_ms),
            crp_overhead_pct=round(_crp_overhead_pct, 1),
            # Relay strategy
            relay_strategy="agentic",
            # §22 Agentic telemetry
            agentic_cognitive_calls=fac_metrics.cognitive_calls,
            agentic_cognitive_tokens=fac_metrics.total_cognitive_tokens,
            agentic_cognitive_ms=round(fac_metrics.total_cognitive_ms, 1),
            agentic_task_complexity=task_analysis.complexity,
            agentic_strategy_chosen=chosen_strategy,
            agentic_strategy_confidence=strategy_decision.confidence,
            agentic_synthesis_insights=len(synthesis.key_insights) if synthesis else 0,
            agentic_evaluation_grade=evaluation.overall_grade,
            agentic_revision_rounds=revision_rounds,
            agentic_curation_actions=curation_actions,
            agentic_plan_steps=len(plan.steps) if plan else 0,
            # Resource tracking
            **self._resource_fields(),
            # Marginal gain / sections
            **self._marginal_fields(output, _facts_before),
            # Adaptive allocator telemetry
            **self._allocator_fields(),
        )
        self._record_dispatch_overhead(_total_dispatch_ms, _total_llm_ms)

        quality_tier = _classify_quality_tier(
            facts_extracted=inner_report.facts_extracted,
            continuation_windows=inner_continuation_count,
            saturation=inner_report.envelope_saturation,
            finish_reason=inner_finish,
            output_tokens=output_tokens,
            output_length=len(output),
        )

        report = QualityReport(
            session_id=self._session.session_id,
            window_id=inner_report.window_id,
            output=output,
            facts_extracted=inner_report.facts_extracted,
            security_flags=security_flags,
            continuation_windows=inner_continuation_count,
            envelope_saturation=inner_report.envelope_saturation,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )

        logger.info(
            "§22 Agentic dispatch complete: strategy=%s, grade=%s, "
            "cognitive_calls=%d, cognitive_tokens=%d, revisions=%d, "
            "curation_actions=%d",
            chosen_strategy, evaluation.overall_grade,
            fac_metrics.cognitive_calls, fac_metrics.total_cognitive_tokens,
            revision_rounds, curation_actions,
        )

        return output, report

    def dispatch_intent(self, intent: TaskIntent) -> tuple[str, QualityReport]:
        """Dispatch using an explicit TaskIntent object."""
        return self.dispatch(
            system_prompt=intent.system_prompt or "",
            task_input=intent.task_input or "",
            max_output_tokens=intent.max_output_tokens,
        )

    def dispatch_hierarchical(
        self,
        system_prompt: str,
        large_input: str,
        task_intent: str = "",
        **kwargs: Any,
    ) -> tuple[list[str], QualityReport]:
        """Hierarchical map-reduce dispatch for oversized inputs (§14).

        Segments the input, dispatches each segment through the LLM,
        then iteratively reduces the syntheses. All facts extracted
        from every segment are stored in the warm store + CKF.

        Returns (final_syntheses, QualityReport).
        """
        self._check_session()

        # ---------- RBAC permission + rate limit check (§7.10) ----------
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        # ---------- Input validation — Layer 1, cannot disable (§7.4) ----------
        val_result = self._input_validator.validate(large_input)
        if not val_result.valid:
            raise ValidationError(
                val_result.warnings[0] if val_result.warnings else "Input validation failed"
            )
        large_input = val_result.sanitized_text

        # ---------- Advisory injection scan on full input (§7.5) ----------
        security_flags = self._scan_injection(large_input)

        from crp.advanced.hierarchical import HierarchicalProcessor

        processor = HierarchicalProcessor(
            dispatch_fn=lambda sys, task, **kw: self._provider.generate_chat(
                [{"role": "system", "content": sys}, {"role": "user", "content": task}],
                **kw,
            ),
            count_tokens=self._provider.count_tokens,
            context_window=self._provider.context_window_size(),
        )

        intent_text = task_intent or large_input[:200]
        syntheses, plan = processor.hierarchical_dispatch(
            task_intent=intent_text,
            large_input=large_input,
        )

        # Extract facts from all syntheses
        total_facts = 0
        for _i, synthesis in enumerate(syntheses):
            window_id = str(uuid.uuid4())
            self._warm_store.advance_window(window_id)
            ti = TaskIntent(task_input=intent_text, system_prompt=system_prompt)
            extraction = self._extract_and_store(synthesis, window_id, ti)
            total_facts += extraction.total_facts
            self._windows_completed += 1
            self._total_input_tokens += self._provider.count_tokens(synthesis)
            self._total_output_tokens += self._provider.count_tokens(synthesis)

        report = QualityReport(
            session_id=self._session.session_id,
            window_id="hierarchical",
            output="\n\n".join(syntheses),
            facts_extracted=total_facts,
            continuation_windows=plan.segment_count,
            security_flags=security_flags,
            quality_tier=_classify_quality_tier(
                facts_extracted=total_facts,
                continuation_windows=plan.segment_count,
                saturation=0.0,
                finish_reason="stop",
                output_tokens=sum(self._provider.count_tokens(s) for s in syntheses),
                output_length=sum(len(s) for s in syntheses),
            ),
        )

        # Record dispatch for rate limiting (§7.10)
        total_tokens = sum(self._provider.count_tokens(s) for s in syntheses)
        self._rbac.record_dispatch(total_tokens)

        return syntheses, report

    def dispatch_batch(
        self,
        intents: list[dict[str, str]],
    ) -> list[tuple[str, QualityReport]]:
        """Batch dispatch multiple tasks sequentially (§6.6).

        Each intent dict should have "system_prompt" and "task_input" keys.
        Returns list of (output, QualityReport) tuples.
        """
        self._check_session()
        results: list[tuple[str, QualityReport]] = []
        for intent in intents:
            sys_prompt = intent.get("system_prompt", "")
            task_input = intent.get("task_input", "")
            try:
                output, report = self.dispatch(sys_prompt, task_input)
                results.append((output, report))
            except Exception as exc:
                error_report = QualityReport(
                    session_id=self._session.session_id,
                    window_id="batch-error",
                    output="",
                    facts_extracted=0,
                    quality_tier="D",
                )
                results.append(("", error_report))
                logger.warning("Batch item failed: %s", exc)
        return results

    def _stream_segment(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> Generator[StreamEvent, None, tuple[str, str]]:
        """Stream a single provider segment and return (output, finish_reason).

        Yields ``token`` events as chunks arrive.  On provider error, yields
        an ``error`` event and returns ("", "error").  The finish reason is
        taken from the provider's ``StopIteration.value``.
        """
        output_chunks: list[str] = []
        finish_reason = "stop"
        try:
            gen = self._provider.generate_chat_stream(messages, max_tokens=max_tokens)
            while True:
                try:
                    chunk = next(gen)
                    output_chunks.append(chunk)
                    yield StreamEvent(event_type="token", data=chunk)
                except StopIteration as stop:
                    finish_reason = stop.value or "stop"
                    self._circuit_breaker.record_success()
                    break
        except Exception as exc:
            self._circuit_breaker.record_failure()
            logger.error("Streaming segment error: %s", exc)
            finish_reason = "error"
            yield StreamEvent(event_type="error", data=_safe_provider_error(exc))
        return "".join(output_chunks), finish_reason

    def _create_stream_continuation_node(
        self,
        parent_node: WindowNode,
        continuation_index: int,
    ) -> WindowNode:
        """Create a child WindowNode for a streaming continuation segment."""
        with self._lock:
            window_id = str(uuid.uuid4())
            self._warm_store.advance_window(window_id)
            node = WindowNode(
                window_id=window_id,
                system_prompt_hash=parent_node.system_prompt_hash,
                task_input_hash=parent_node.task_input_hash,
                continuation_index=continuation_index,
                parent_ids=[parent_node.window_id],
            )
            self._dag.add_node(node)
            node.advance(WindowState.ASSEMBLED)
            return node

    def dispatch_stream(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> Generator[StreamEvent, None, None]:
        """Streaming dispatch — yields StreamEvent objects.

        Stream contract:
        - Emits one or more "token" events in generation order.
        - Emits "extraction" events as facts are discovered.
        - Emits one "window_complete" event per stream segment.
        - Emits exactly one "done" event as the final event (or "error").
        - Token concatenation MUST produce the same string as dispatch().
        - No reordering of token events.
        - Continues automatically when the provider hits the token wall.
        """
        self._check_session()

        # RBAC permission + rate limit check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.DISPATCH)
        if not perm_result.allowed:
            raise RateLimitExceededError(perm_result.reason)
        rate_result = self._rbac.check_rate_limit(Permission.DISPATCH)
        if not rate_result.allowed:
            raise RateLimitExceededError(rate_result.reason)

        # Input validation — Layer 1, cannot disable (§7.4)
        val_result = self._input_validator.validate(task_input)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        task_input = val_result.sanitized_text

        # Security scan (advisory)
        security_flags = self._scan_injection(task_input)
        security_flags.unicode_normalized = val_result.sanitized_size != val_result.original_size
        security_flags.control_chars_stripped = val_result.control_chars_removed

        s_tokens = self._provider.count_tokens(system_prompt)
        t_tokens = self._provider.count_tokens(task_input)
        context_window = self._provider.context_window_size()

        max_out = kwargs.get("max_output_tokens")
        g = resolve_generation_reserve(
            max_out,
            self._provider.max_output_tokens,
            context_window,
            is_thinking_model=getattr(self._provider, "is_thinking_model", False),
        )

        # Build envelope from accumulated facts
        envelope_result = self._build_envelope(system_prompt, task_input, g)
        envelope = envelope_result.envelope_text

        e_tokens = self._provider.count_tokens(envelope) if envelope else 0
        input_tokens = s_tokens + t_tokens + e_tokens
        self._check_budget(input_tokens)

        # Advance warm store window
        window_id = str(uuid.uuid4())
        self._warm_store.advance_window(window_id)

        node = WindowNode(
            window_id=window_id,
            system_prompt_hash=hashlib.sha256(system_prompt.encode()).hexdigest(),
            task_input_hash=hashlib.sha256(task_input.encode()).hexdigest(),
            continuation_index=0,
        )
        self._dag.add_node(node)
        node.advance(WindowState.ASSEMBLED)

        messages = assemble_messages(system_prompt, envelope, task_input)

        node.advance(WindowState.DISPATCHED)
        node.advance(WindowState.GENERATING)

        # Circuit breaker gate (§audit3: protect all dispatch variants)
        if not self._circuit_breaker.allow_request():
            raise ProviderError(
                "Circuit breaker OPEN — provider unavailable, "
                "retry after recovery timeout"
            )

        start_ms = time.monotonic_ns()
        task_intent = TaskIntent(task_input=task_input, system_prompt=system_prompt)
        cont_config = getattr(self, "_continuation_config", None) or ContinuationConfig(
            max_continuations=int(self._config.get("max_continuations", 50)),
        )
        cont_mgr = ContinuationManager(cont_config)
        cont_state: Any = None
        accumulated_output = ""
        continuation_windows = 0
        total_input_tokens = input_tokens
        total_output_tokens = 0
        total_llm_ms = 0.0
        max_continuations = int(self._config.get("max_continuations", 50))
        _cont_deadline = time.monotonic() + int(self._config.get("dispatch_timeout", 3600))
        last_output = ""
        first_node = node
        current_node = node
        current_messages = messages
        current_g = g
        current_envelope_result = envelope_result

        while True:
            segment_start = time.monotonic_ns()
            segment_gen = self._stream_segment(current_messages, current_g)
            try:
                output_segment, finish_reason = yield from segment_gen
            except Exception as exc:
                # Defensive: _stream_segment already yields error and returns,
                # but yield from can propagate exceptions from the consumer.
                logger.error("Streaming segment failed: %s", exc)
                finish_reason = "error"
                output_segment = ""

            segment_ms = (time.monotonic_ns() - segment_start) / 1_000_000
            total_llm_ms += segment_ms

            accumulated_output += output_segment
            last_output = output_segment
            segment_output_tokens = self._provider.count_tokens(output_segment)
            total_output_tokens += segment_output_tokens

            current_node.finish_reason = finish_reason
            current_node.raw_output_id = str(uuid.uuid4())
            current_node.advance(WindowState.COMPLETED)
            current_node.advance(WindowState.EXTRACTED)

            # Extract facts from segment output
            if output_segment and finish_reason != "error":
                extraction = self._extract_and_store(
                    output_segment, current_node.window_id, task_intent,
                )
                current_node.facts_produced = [f.id for f in extraction.facts]
            else:
                extraction = self._extract_and_store("", current_node.window_id, task_intent)
                current_node.facts_produced = []

            # Mark consumed facts as seen for the first segment only
            if continuation_windows == 0:
                if current_envelope_result.packing and current_envelope_result.packing.packed_facts:
                    consumed_ids = [
                        pf.fact_id for pf in current_envelope_result.packing.packed_facts
                    ]
                    self._warm_store.mark_seen(consumed_ids, first_node.window_id)

            # Emit extraction progress
            if extraction.total_facts > 0:
                yield StreamEvent(
                    event_type="extraction",
                    data=ExtractionProgress(
                        stage=f"stages {extraction.stages_run}",
                        facts_so_far=extraction.total_facts,
                    ),
                )

            # Window complete event for this segment
            yield StreamEvent(
                event_type="window_complete",
                data=WindowSummary(
                    window_id=current_node.window_id,
                    input_tokens=total_input_tokens if continuation_windows == 0 else 0,
                    output_tokens=segment_output_tokens,
                    wall_time_ms=int(segment_ms),
                ),
            )

            # Decide whether to continue
            cont_state = cont_mgr.process_window(
                task_intent=task_input,
                output=output_segment,
                finish_reason=finish_reason,
                output_tokens=segment_output_tokens,
                facts=extraction.facts,
                window_id=current_node.window_id,
            )

            if cont_state.finished or finish_reason == "error":
                break
            if continuation_windows >= max_continuations:
                cont_state.termination_reason = "max_continuations"
                break
            if time.monotonic() > _cont_deadline:
                cont_state.termination_reason = "wall_time_deadline"
                break

            # Build continuation envelope and messages
            continuation_windows += 1
            _cont_g = max(g // 2, 512)
            cont_envelope = cont_mgr.build_continuation_envelope(
                task_intent=task_input,
                gap_result=cont_state.gap_result,
                structural_state=self._warm_store.structural_state.to_dict(),
                last_output=last_output,
            )
            task_title = self._extract_task_title(task_input)
            cont_task = (
                f"=== ORIGINAL TASK ===\n"
                f"{task_title}\n"
                f"=== CONTINUATION DIRECTIVES ===\n"
                f"{cont_envelope}\n"
                f"=== END DIRECTIVES ==="
            )
            cont_env_result = self._build_envelope(system_prompt, cont_task, _cont_g)
            if cont_env_result.budget_tokens <= 0 and self._warm_store.fact_count > 0:
                logger.info("Stream continuation: envelope starved, retrying with title-only budget")
                cont_env_result = self._build_envelope(system_prompt, task_title, _cont_g)

            current_messages = assemble_messages(
                system_prompt, cont_env_result.envelope_text, cont_task,
            )
            current_envelope_result = cont_env_result
            current_g = _cont_g

            # Create child node under lock
            current_node = self._create_stream_continuation_node(
                first_node, continuation_windows,
            )
            current_node.advance(WindowState.DISPATCHED)
            current_node.advance(WindowState.GENERATING)

            # Add continuation input tokens to running total
            total_input_tokens += self._provider.count_tokens(
                system_prompt + (cont_env_result.envelope_text or "") + cont_task
            )

            yield StreamEvent(
                event_type="continuation",
                data=ContinuationInfo(
                    continuation_index=continuation_windows,
                    reason=cont_state.trigger_result.reason if cont_state.trigger_result else "",
                ),
            )

        # Final output is the concatenation of all streamed segments.
        # We intentionally do NOT use cont_state.stitched_output here because
        # the streaming contract requires that concatenating every emitted
        # token event equals the final report output.
        final_output = accumulated_output

        wall_ms = (time.monotonic_ns() - start_ms) / 1_000_000
        final_finish_reason = finish_reason

        # Update session counters
        self._windows_completed += 1
        self._total_input_tokens += total_input_tokens
        self._total_output_tokens += total_output_tokens
        self._continuation_windows_total += continuation_windows
        self._rbac.record_dispatch(tokens_used=total_output_tokens)

        quality_tier = _classify_quality_tier(
            facts_extracted=extraction.total_facts,
            continuation_windows=continuation_windows,
            saturation=envelope_result.saturation,
            finish_reason=final_finish_reason,
            output_tokens=total_output_tokens,
            output_length=len(final_output),
        )

        metrics = WindowMetrics(
            window_id=first_node.window_id,
            chain_position=continuation_windows,
            system_tokens=s_tokens,
            task_tokens=t_tokens,
            envelope_tokens=e_tokens,
            envelope_budget=envelope_result.budget_tokens,
            saturation=envelope_result.saturation,
            generation_reserve=g,
            generation_tokens=total_output_tokens,
            generation_speed=total_output_tokens / (total_llm_ms / 1000) if total_llm_ms > 0 else 0.0,
            wall_time_ms=int(total_llm_ms),
            finish_reason=final_finish_reason,
            facts_extracted=extraction.total_facts,
            continuation_triggered=continuation_windows > 0,
            continuation_index=continuation_windows,
            total_output_tokens=total_output_tokens,
            total_dispatch_ms=round(wall_ms),
            total_llm_ms=round(total_llm_ms),
            crp_overhead_ms=round(wall_ms - total_llm_ms),
            crp_overhead_pct=round(
                (wall_ms - total_llm_ms) / wall_ms * 100, 1
            ) if wall_ms > 0 else 0.0,
            **self._resource_fields(),
            **self._marginal_fields(final_output, self._warm_store.fact_count - extraction.total_facts),
            **self._allocator_fields(),
        )

        # Done event — final report
        report = QualityReport(
            session_id=self._session.session_id,
            window_id=first_node.window_id,
            output=final_output,
            facts_extracted=extraction.total_facts,
            security_flags=security_flags,
            continuation_windows=continuation_windows,
            envelope_saturation=envelope_result.saturation,
            quality_tier=quality_tier,
            telemetry=metrics.to_dict(),
        )
        yield StreamEvent(event_type="done", data=report)

    # ------------------------------------------------------------------
    # Zero-LLM ingestion (§2.5)
    # ------------------------------------------------------------------

