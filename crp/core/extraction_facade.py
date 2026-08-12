# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Extraction facade mixin — fact extraction and ingestion (§2.5).

Extracted from orchestrator.py for maintainability. This mixin provides
extraction and ingestion method implementations. The CRPOrchestrator
inherits from this class.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from crp.core.task_intent import TaskIntent

if TYPE_CHECKING:
    from crp.extraction.types import ExtractionResult as PipelineExtractionResult

logger = logging.getLogger("crp.orchestrator")


# ---------------------------------------------------------------------------
# ExtractionResult (for ingest)
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Result of zero-LLM ingestion."""
    facts_extracted: int = 0
    source_label: str = ""
    fact_ids: list[str] = field(default_factory=list)


class ExtractionMixin:
    """Mixin providing CRP extraction and ingestion methods.

    Methods access orchestrator state via ``self`` (multiple inheritance).
    """

    def _extract_and_store(
        self,
        text: str,
        source_window_id: str,
        task_intent: TaskIntent | None = None,
    ) -> PipelineExtractionResult:
        """Run graduated extraction on text, store facts in WarmStore + CKF."""
        from crp.extraction.quality_gate import run_quality_gate

        result = self._extraction.extract(
            text,
            task_intent=task_intent,
            source_window_id=source_window_id,
        )

        # Quality gate (3-tier validation)
        result = run_quality_gate(
            result,
            history=list(self._extraction_history)[-10:] if self._extraction_history else None,
        )
        self._extraction_history.append(result)

        # ── Output-side injection firewall (§7.5.2) ───────────
        # Scan EACH extracted fact for injection patterns.
        # If an LLM output contains injection payloads that survive
        # extraction as verbatim text (e.g. key_sentence, list_item),
        # penalize their confidence so they rank lower in envelope
        # packing and are less likely to propagate to the next window.
        if result.facts:
            for fact in result.facts:
                fact_report = self._injection_detector.scan(fact.text)
                if fact_report.has_flags:
                    # Penalize confidence: 0.3× for high-confidence injection,
                    # 0.6× for lower-confidence matches
                    penalty = 0.3 if fact_report.highest_confidence >= 0.80 else 0.6
                    fact.confidence *= penalty
                    fact.flagged_confidence = True
                    fact.confidence_flag_reason = (
                        f"injection_in_fact:{fact_report.flags[0].pattern_name}"
                        f":{fact_report.highest_confidence:.2f}"
                    )
                    logger.warning(
                        "Output-side injection detected in fact %s: %s (conf=%.2f, "
                        "fact confidence penalized to %.2f)",
                        fact.id, fact_report.flags[0].pattern_name,
                        fact_report.highest_confidence, fact.confidence,
                    )

        # Store in WarmStateStore (fact ranking, aging, seen tracking)
        if result.facts:
            self._warm_store.add_facts(result.facts, result.edges or None)

        # Add facts to integrity chain (§7.2, §7.7)
        if result.facts:
            for fact in result.facts:
                self._integrity_chain.add_fact(fact.id, fact.text)

        # Store in CKF (4-mode retrieval: graph walk, pattern, semantic, community)
        if result.facts:
            self._ckf.store(result.facts, window_id=source_window_id)
            if result.edges:
                self._ckf.store_edges(result.edges)

        # Store source passages for high-confidence facts (§17)
        if result.facts:
            from crp.advanced.source_grounding import SourcePassage
            for fact in result.facts:
                passage = SourcePassage(
                    passage_id=f"{source_window_id}:{fact.id}",
                    text=fact.text,
                    source_window=self._windows_completed,
                    linked_fact_ids=[fact.id],
                    relevance_score=fact.confidence,
                )
                self._source_grounding.store_passage(
                    passage=passage,
                    fact_confidence=fact.confidence,
                )

        # Auto-compact warm store if thresholds exceeded (§7.4)
        from crp.state.compaction import should_compact, compact
        if should_compact(self._warm_store):
            try:
                compact(
                    self._warm_store,
                    self._ckf._event_log,
                    source_window_id,
                )
                logger.debug("Auto-compaction complete")
            except Exception as exc:
                logger.debug("Compaction skipped: %s", exc)

        return result

    # ------------------------------------------------------------------
    # Internal: envelope construction
    # ------------------------------------------------------------------

    def ingest_batch(
        self,
        texts: list[str],
        task_intent: str = "",
    ) -> list[int]:
        """Batch ingest multiple texts, returning facts extracted per text (§6.6)."""
        self._check_session()
        results: list[int] = []
        for text in texts:
            try:
                facts_count = self.ingest(text)
                results.append(facts_count)
            except Exception as exc:
                results.append(0)
                logger.warning("Batch ingest item failed: %s", exc)
        return results

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def ingest(
        self,
        raw_text: str,
        source_label: str | None = None,
    ) -> ExtractionResult:
        """Ingest raw text without LLM invocation (§2.5).

        Runs graduated extraction pipeline on raw_text, adds facts to
        WarmStateStore and CKF.  No LLM call, no window creation, no envelope.
        """
        with self._lock:
            return self._ingest_locked(raw_text, source_label=source_label)

    def _ingest_locked(
        self,
        raw_text: str,
        source_label: str | None = None,
    ) -> ExtractionResult:
        """Internal ingest implementation — called under self._lock."""
        # Set correlation ID for structured log tracing (§audit M10)
        from crp.observability.structured_logging import new_correlation_id
        cid = new_correlation_id()
        logger.info("ingest started [correlation_id=%s, label=%s]", cid, source_label)

        self._check_session()

        # ---------- Input sanitization (§audit H10) ----------
        max_ingest_bytes = self._config.get("max_ram_mb", 512) * 1024 * 1024
        # Cap single ingest to 10 MB or 1% of memory budget, whichever is smaller
        max_ingest_size = min(10 * 1024 * 1024, max_ingest_bytes // 100)
        if len(raw_text) > max_ingest_size:
            raise ValidationError(
                f"Ingest text too large ({len(raw_text):,} chars, "
                f"max {max_ingest_size:,})"
            )

        # ---------- Compliance imports (§7.14) ----------
        from crp.security.audit_trail import ComplianceEventType
        from crp.security.consent import ProcessingPurpose
        from crp.security.privacy import DataClassification

        # ---------- Compliance audit: ingest started (§7.14) ----------
        label = source_label or "unnamed"
        self._compliance_audit.record(
            ComplianceEventType.DATA_INGESTED,
            session_id=self._session.session_id,
            data={"operation": "ingest", "phase": "started",
                  "source_label": label,
                  "input_length": len(raw_text)},
        )

        # ---------- Consent verification (§7.13) ----------
        self._consent_manager.check_required(ProcessingPurpose.FACT_EXTRACTION)

        # RBAC permission + rate limit check (§7.10)
        from crp.security.rbac import Permission
        perm_result = self._rbac.check_permission(Permission.INGEST)
        if not perm_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RBAC_DENIED,
                session_id=self._session.session_id,
                data={"operation": "ingest", "reason": perm_result.reason},
            )
            raise RateLimitExceededError(perm_result.reason)

        if not raw_text:
            return ExtractionResult(
                facts_extracted=0,
                source_label=source_label or "",
            )

        # Input validation — Layer 1, cannot disable (§7.4)
        val_result = self._input_validator.validate(raw_text)
        if not val_result.valid:
            raise ValidationError(val_result.warnings[0] if val_result.warnings else "Input validation failed")
        raw_text = val_result.sanitized_text

        # Rate limit check with payload size
        payload_bytes = len(raw_text.encode("utf-8"))
        rate_result = self._rbac.check_rate_limit(Permission.INGEST, payload_bytes=payload_bytes)
        if not rate_result.allowed:
            self._compliance_audit.record(
                ComplianceEventType.RATE_LIMIT_HIT,
                session_id=self._session.session_id,
                data={"operation": "ingest", "reason": rate_result.reason},
            )
            raise RateLimitExceededError(rate_result.reason)

        source_window_id = f"ingest:{label}"

        # ---------- PII scanning on ingested text (§7.12) ----------
        pii_result = self._pii_scanner.scan(raw_text)
        if pii_result.has_pii:
            self._compliance_audit.record(
                ComplianceEventType.PII_DETECTED,
                session_id=self._session.session_id,
                data={
                    "operation": "ingest",
                    "source_label": label,
                    "pii_types": sorted(pii_result.pii_types_found),
                    "detection_count": len(pii_result.detections),
                    "classification": pii_result.highest_classification.name,
                },
            )
            if self._human_oversight.should_halt_on_pii():
                self._human_oversight.record_halt(
                    "ingest", "PII detected in ingested text",
                    details={"pii_types": sorted(pii_result.pii_types_found)},
                )

        # Advisory injection scan on ingested text (§7.5.2)
        ingest_report = self._injection_detector.scan(raw_text)
        if ingest_report.has_flags:
            logger.warning(
                "Injection patterns detected in ingested text '%s': %d flags, "
                "highest confidence=%.2f — facts will be quarantined + penalized",
                label, len(ingest_report.flags), ingest_report.highest_confidence,
            )
            self._compliance_audit.record(
                ComplianceEventType.INJECTION_DETECTED,
                session_id=self._session.session_id,
                data={
                    "operation": "ingest",
                    "source_label": label,
                    "flags_count": len(ingest_report.flags),
                    "highest_confidence": ingest_report.highest_confidence,
                },
            )
            if self._human_oversight.should_halt_on_injection():
                self._human_oversight.record_halt(
                    "ingest", "Injection detected in ingested text",
                    details={"flags_count": len(ingest_report.flags)},
                )

        # Run full graduated extraction pipeline
        # (output-side injection firewall in _extract_and_store will
        #  penalize any facts that carry injection patterns)
        pipeline_result = self._extract_and_store(raw_text, source_window_id)

        # Quarantine ingested facts with 0.7× confidence penalty (§7.8)
        if pipeline_result.facts:
            window_id = f"ingest-q:{label}"
            self._quarantine.quarantine_facts(
                [(f.id, f.confidence, f.text) for f in pipeline_result.facts],
                window_id=window_id,
                source_label=label,
            )

        # ---------- Retention + lineage tracking for ingested facts (§7.12) ----------
        _classification = (
            pii_result.highest_classification if pii_result.has_pii
            else DataClassification.INTERNAL
        )
        for fact in pipeline_result.facts:
            self._retention_manager.register(
                data_id=fact.id,
                classification=_classification,
                source_label=f"ingest:{label}",
            )
            self._lineage_tracker.record(
                data_id=fact.id,
                origin="ingest",
                source_label=label,
                classification=_classification,
            )

        # ---------- Processing record (§7.13 — GDPR Art. 30) ----------
        self._processing_records.record(
            purpose=ProcessingPurpose.FACT_EXTRACTION,
            data_categories=["raw_text", "extracted_facts"],
            legal_basis="legitimate_interest",
            input_size_bytes=payload_bytes,
            output_size_bytes=sum(len(f.text.encode("utf-8")) for f in pipeline_result.facts),
            automated_decision=True,
            human_oversight=False,
            retention_period="session",
        )

        # Record ingest for rate limiting
        self._rbac.record_ingest(payload_bytes)

        # ---------- Compliance audit: ingest completed (§7.14) ----------
        self._compliance_audit.record(
            ComplianceEventType.DATA_INGESTED,
            session_id=self._session.session_id,
            data={
                "operation": "ingest",
                "phase": "completed",
                "source_label": label,
                "facts_extracted": pipeline_result.total_facts,
                "quarantined": self._quarantine.quarantine_count,
                "pii_detected": pii_result.has_pii,
                "injection_detected": ingest_report.has_flags,
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

        logger.info(
            "Ingested %d facts from source '%s' (stages=%s, quarantined=%d)",
            pipeline_result.total_facts, label, pipeline_result.stages_run,
            self._quarantine.quarantine_count,
        )

        return ExtractionResult(
            facts_extracted=pipeline_result.total_facts,
            source_label=label,
            fact_ids=[f.id for f in pipeline_result.facts],
        )

    # ------------------------------------------------------------------
    # State export (§2.5)
    # ------------------------------------------------------------------

