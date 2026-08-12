# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Namespace proxies for the progressive CRP SDK (SPEC-032).

These proxies expose internal CRP subsystems through a stable, discoverable
SDK surface. Each proxy receives the orchestrator instance and uses lazy
imports to avoid heavy dependencies and circular imports.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger("crp.sdk.proxies")


# ── Safety ─────────────────────────────────────────────────────────────────


class _SafetyProxy:
    """Safety Control Plane proxy (SPEC-033, SPEC-034).

    Provides access to the safety registry, manifest, coverage map,
    checkpoints, and the active safety profile.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def control_plane(self) -> Any:
        """Return the orchestrator's ``SafetyControlPlane`` instance.

        Instantiates a new control plane using the orchestrator's security
        manager settings if one is not already attached.

        Returns:
            SafetyControlPlane instance.
        """
        from crp.security.control_plane import SafetyControlPlane

        if hasattr(self._orchestrator, "_safety_control_plane"):
            return self._orchestrator._safety_control_plane

        sm = getattr(self._orchestrator, "_security", None)
        manifest = self.manifest()
        coverage = self.coverage_map()
        cp = SafetyControlPlane(manifest=manifest, coverage=coverage)
        if sm is not None:
            for key in ("halt_on_injection_detection", "halt_on_pii_detection"):
                val = getattr(getattr(sm, "_human_oversight", None), key, None)
                if val is not None:
                    cp.manifest.set(key, val)
        self._orchestrator._safety_control_plane = cp
        return cp

    def manifest(self) -> Any:
        """Return the current ``SafetyManifest``.

        Returns:
            SafetyManifest instance.
        """
        from crp.security.safety_manifest import SafetyManifest

        existing = getattr(self._orchestrator, "_safety_manifest", None)
        if existing is not None:
            return existing
        manifest = SafetyManifest()
        self._orchestrator._safety_manifest = manifest
        return manifest

    def coverage_map(self) -> Any:
        """Return the current ``SafetyCoverageMap``.

        Returns:
            SafetyCoverageMap instance.
        """
        from crp.security.coverage import SafetyCoverageMap

        existing = getattr(self._orchestrator, "_safety_coverage", None)
        if existing is not None:
            return existing
        coverage = SafetyCoverageMap()
        self._orchestrator._safety_coverage = coverage
        return coverage

    def add_rule(
        self,
        name: str,
        check_fn: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a custom safety rule on the control plane.

        Args:
            name: Unique rule name.
            check_fn: Callable invoked by the rule (optional).
            **kwargs: Additional metadata forwarded to ``CustomSafetyRule``.

        Returns:
            The registered ``CustomSafetyRule`` instance.
        """
        from crp.security.control_plane import CustomSafetyRule

        rule = CustomSafetyRule(name=name, check_fn=check_fn or (lambda x: None), **kwargs)
        self.control_plane().register_rule(rule)
        return rule

    def checkpoint(
        self,
        trigger: str = "RISK_HIGH",
        timeout_action: str = "ESCALATE",
        reject_action: str = "HALT",
        timeout: int = 300,
    ) -> Any:
        """Create a human-in-the-loop checkpoint (SPEC-033 §3).

        Args:
            trigger: Condition that fires the checkpoint.
            timeout_action: Action on timeout (``APPROVE``, ``REJECT``,
                ``ESCALATE``).
            reject_action: Action on reject (``HALT``, ``REVISE``,
                ``FALLBACK``).
            timeout: Seconds before auto-resolution.

        Returns:
            Checkpoint instance configured with the orchestrator's security
            manager.
        """
        from crp.security.checkpoint import (
            Checkpoint,
            CheckpointRejectAction,
            CheckpointTimeoutAction,
            CheckpointTrigger,
        )

        sm = getattr(self._orchestrator, "_security", None)
        context: dict[str, Any] = {"session_id": getattr(self._orchestrator._session, "session_id", "")}
        if sm is not None:
            context["security_manager_present"] = True

        def _trigger(value: str) -> CheckpointTrigger:
            try:
                return CheckpointTrigger(value)
            except ValueError:
                return CheckpointTrigger.CUSTOM_RULE

        def _timeout_action(value: str) -> CheckpointTimeoutAction:
            try:
                return CheckpointTimeoutAction(value)
            except ValueError:
                return CheckpointTimeoutAction.ESCALATE

        def _reject_action(value: str) -> CheckpointRejectAction:
            try:
                return CheckpointRejectAction(value)
            except ValueError:
                return CheckpointRejectAction.FALLBACK

        cp = Checkpoint(
            trigger=_trigger(trigger),
            timeout=timeout,
            on_timeout=_timeout_action(timeout_action),
            on_reject=_reject_action(reject_action),
            context=context,
        )
        return cp

    @property
    def profile(self) -> Any:
        """Return the current safety profile name or dict.

        Returns:
            Profile name (str) or settings dict.
        """
        return self.manifest().profile

    def set_profile(self, profile: str) -> None:
        """Apply a named safety profile (balanced/strict/medical/financial).

        Args:
            profile: One of the supported profile names.
        """
        from crp.security.safety_manifest import DEFAULT_PROFILES

        if profile not in DEFAULT_PROFILES:
            raise ValueError(f"unknown safety profile: {profile}")
        manifest = self.manifest()
        manifest.profile = profile
        manifest.settings = DEFAULT_PROFILES[profile].copy()

    def set(self, **kwargs: Any) -> None:
        """Tune one or more manifest safety settings by key.

        Example::

            client.safety.set(require_grounding=0.8, hallucination_halt="HIGH")
        """
        manifest = self.manifest()
        for key, value in kwargs.items():
            manifest.set(key, value)

    def show(self) -> str:
        """Return a human-readable summary of the full safety surface."""
        return self.control_plane().show()

    def registry(self) -> list[dict[str, Any]]:
        """Return the safety capability registry as a list of dicts."""
        return [cap.to_dict() for cap in self.control_plane().list_capabilities()]

    def explain(self, name: str) -> str:
        """Explain a single safety capability or setting.

        Args:
            name: Capability or setting name.

        Returns:
            Human-readable explanation, or a refusal if unknown.
        """
        cp = self.control_plane()
        cap = cp.get_capability(name)
        if cap is not None:
            lines = [
                f"{cap.name}",
                f"  What: {cap.description}",
                f"  Default: {cap.default}",
                f"  Current: {cap.current}",
            ]
            if cap.allowed_range:
                lines.append(f"  Allowed range: {cap.allowed_range}")
            lines.append(f"  Effect: {cap.effect}")
            lines.append(f"  Spec: CRP-SPEC-{cap.spec}")
            return "\n".join(lines)
        if name in cp.coverage.out_of_scope:
            return f"{name} is explicitly out of scope for CRP safety."
        return f"{name}: unknown CRP safety capability or setting."


# ── CKF ────────────────────────────────────────────────────────────────────


class _CKFProxy:
    """Contextual Knowledge Fabric proxy (SPEC-009, SPEC-025).

    Exposes CKF query, search, graph walk, community detection, CDGR
    expansion, persistence, pub/sub, and health introspection.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def _ckf(self) -> Any:
        return self._orchestrator.ckf

    def query(self, **kwargs: Any) -> Any:
        """Run a pattern query on the CKF fact graph.

        Returns:
            PatternQueryResult from the CKF.
        """
        return self._ckf().query(**kwargs)

    def search(self, query: str, top_k: int = 5, **kwargs: Any) -> Any:
        """Semantic search over the CKF.

        Embeds ``query`` when an embedding function is available; otherwise
        falls back to the CKF's text/keyword modes.

        Args:
            query: Query text.
            top_k: Maximum number of facts to return.
            **kwargs: Additional retrieval options.

        Returns:
            MergeResult containing ranked facts.
        """
        embedding = None
        try:
            from crp.provenance._embeddings import encode_texts

            embeddings = encode_texts([query])
            embedding = embeddings[0] if embeddings else None
        except Exception:
            logger.debug("Semantic embedding unavailable for CKF search")
        return self._ckf().retrieve(
            query_embedding=embedding,
            budget=top_k,
            **kwargs,
        )

    def graph_walk(self, start_fact_id: str, max_hops: int = 3, **kwargs: Any) -> Any:
        """Walk the CKF graph from a seed fact.

        Args:
            start_fact_id: Seed fact identifier.
            max_hops: Maximum BFS distance from the seed.
            **kwargs: Additional options forwarded to ``graph_walk``.

        Returns:
            GraphWalkResult.
        """
        from crp.ckf.graph_walk import graph_walk

        graph = self._ckf()._warm._graph
        return graph_walk(graph, {start_fact_id}, max_hops=max_hops, **kwargs)

    def community_summary(self, **kwargs: Any) -> Any:
        """Run community detection on the CKF fact graph.

        Returns:
            CommunityResult.
        """
        from crp.ckf.community import CommunityDetector

        graph = self._ckf()._warm._graph
        return CommunityDetector().detect(graph, **kwargs)

    def cdgr_expand(self, query: str, **kwargs: Any) -> Any:
        """Run Coverage-Differential Graph Retrieval expansion (SPEC-025).

        Args:
            query: Query text used to seed CDR anchors.
            **kwargs: Additional options for ``cdgr_expand``.

        Returns:
            CDGRResult with anchors and connector facts.
        """
        from crp.ckf.cdgr import cdgr_expand
        from crp.envelope.cdr import cdr_rank
        from crp.state.coverage_set import CoverageSet

        ckf = self._ckf()
        graph = ckf._warm._graph
        facts = [sf.fact for sf in ckf._warm._facts.values()]
        if not facts:
            from crp.ckf.cdgr import CDGRResult

            return CDGRResult(anchors=[], connectors=[], assembled=[])

        embedding = None
        try:
            from crp.provenance._embeddings import encode_texts

            embeddings = encode_texts([query])
            embedding = embeddings[0] if embeddings else None
        except Exception:
            logger.debug("Embedding unavailable for CDGR expansion")

        coverage = CoverageSet()
        if embedding is not None:
            cdr_result = cdr_rank(facts, embedding, coverage, **kwargs)
            anchor_facts = [sf.fact for sf in cdr_result.ranked[:20]]
        else:
            anchor_facts = facts[:20]

        try:
            from crp.ckf.graph_edges import GraphEdgeStore, build_edges

            edge_store = build_edges(graph)
        except Exception:
            edge_store = GraphEdgeStore()

        fact_lookup = {f.id: f for f in facts if hasattr(f, "id")}
        return cdgr_expand(
            anchor_facts=anchor_facts,
            edge_store=edge_store,
            coverage_set=coverage,
            fact_lookup=fact_lookup,
            **kwargs,
        )

    def persist(self, path: str | Path | None = None) -> None:
        """Persist CKF state to ``path``.

        Args:
            path: Destination path. If ``None``, uses the configured CKF
                persist path.

        Raises:
            NotImplementedError: If the CKF does not support persistence.
        """
        ckf = self._ckf()
        target = path or getattr(ckf._config, "persist_path", None)
        if not target:
            raise NotImplementedError("No CKF persist path configured")
        if not hasattr(ckf, "persist"):
            raise NotImplementedError("CKF persist is not available")
        ckf.persist(target)

    def restore(self, path: str | Path | None = None) -> Any:
        """Restore CKF state from ``path``.

        Args:
            path: Source path. If ``None``, uses the configured CKF
                persist path.

        Returns:
            Restore warnings if available.

        Raises:
            NotImplementedError: If the CKF does not support restore.
        """
        ckf = self._ckf()
        target = path or getattr(ckf._config, "persist_path", None)
        if not target:
            raise NotImplementedError("No CKF persist path configured")
        if not hasattr(ckf, "restore"):
            raise NotImplementedError("CKF restore is not available")
        return ckf.restore(target)

    def subscribe(self, event_type: Any, callback: Any) -> None:
        """Subscribe to CKF pub/sub events if available.

        Args:
            event_type: CKF event type or string.
            callback: Callable invoked when the event fires.
        """
        ckf = self._ckf()
        if not hasattr(ckf, "subscribe"):
            logger.warning("CKF pub/sub is not available")
            return
        try:
            ckf.subscribe(event_type, callback)
        except Exception as exc:
            logger.warning("CKF subscribe failed: %s", exc)

    def health(self) -> Any:
        """Return a CKF health snapshot.

        Returns:
            CKFHealth report.
        """
        return self._ckf().health()

    def fact_count(self) -> int:
        """Return the number of facts in the CKF."""
        return self._ckf().fact_count()


# ── CSO ────────────────────────────────────────────────────────────────────


class _CSOProxy:
    """Cognitive State Object proxy (SPEC-030).

    Exposes the current CSO and its components (decisions, goals,
    dependencies, established facts).
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def get(self) -> Any:
        """Return the current ``CognitiveStateObject``.

        If the orchestrator session holds a CSO, that object is returned.
        Otherwise a CSO is built from the warm store and any available
        decisions.

        Returns:
            CognitiveStateObject instance.
        """
        from crp.state.cso import CognitiveStateObject, EstablishedFact, ProvenanceKind

        session = getattr(self._orchestrator, "_session", None)
        if session is not None:
            cso = getattr(session, "cso", None)
            if cso is not None:
                return cso

        cso = CognitiveStateObject()
        warm = getattr(self._orchestrator, "warm_store", None)
        if warm is not None:
            try:
                for i, sf in enumerate(warm.get_ranked_facts(limit=50)):
                    fact = sf.fact
                    cso.established_facts.append(
                        EstablishedFact(
                            fact_id=getattr(fact, "id", f"cso_{i}"),
                            statement=getattr(fact, "text", "") or "",
                            provenance=ProvenanceKind.CKF,
                            provenance_ref=getattr(fact, "source_window_id", ""),
                            confidence=getattr(fact, "confidence", 0.85) or 0.85,
                        )
                    )
            except Exception as exc:
                logger.debug("Could not build CSO from warm store: %s", exc)
        return cso

    def decisions(self) -> list[Any]:
        """Return the list of CSO decisions."""
        return list(self.get().decisions)

    def goals(self) -> list[Any]:
        """Return the list of goal states."""
        gs = self.get().goal_state
        return [gs] if gs else []

    def dependencies(self) -> list[Any]:
        """Return the CSO dependency edges."""
        return list(self.get().dependency_graph)

    def established_facts(self) -> list[Any]:
        """Return established facts from the current CSO."""
        return list(self.get().established_facts)


# ── Provenance ─────────────────────────────────────────────────────────────


class _ProvenanceProxy:
    """Decision Provenance Engine proxy (SPEC-005, SPEC-011).

    Exposes provenance chains, DPE scoring, and combined provenance reports.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def _dpe(self) -> Any:
        return getattr(self._orchestrator, "_provenance_engine", None)

    def _ckf(self) -> Any:
        return self._orchestrator.ckf

    def _facts_for_dpe(self) -> list[Any]:
        try:
            from crp.envelope.packer import PackedFact

            facts: list[Any] = []
            for sf in self._ckf()._warm._facts.values():
                fact = sf.fact
                facts.append(
                    PackedFact(
                        fact_id=getattr(fact, "id", ""),
                        text=getattr(fact, "text", ""),
                        score=getattr(fact, "confidence", 0.5) or 0.5,
                    )
                )
            return facts
        except Exception:
            return []

    def chains(self, output_text: str, **kwargs: Any) -> list[Any]:
        """Build provenance chains for ``output_text``.

        Args:
            output_text: LLM output to trace back to source facts.
            **kwargs: Additional options forwarded to the DPE/chain builder.

        Returns:
            List of ProvenanceChain objects.
        """
        dpe = self._dpe()
        if dpe is None:
            return []

        facts = self._facts_for_dpe()
        session_id = getattr(self._orchestrator._session, "session_id", "")
        try:
            report = dpe.analyse(
                output_text=output_text,
                packed_facts=facts,
                session_id=session_id,
                window_id=kwargs.get("window_id", ""),
                envelope_saturation=kwargs.get("envelope_saturation", 0.0),
                task_input_preview=kwargs.get("task_input_preview", ""),
            )
            return list(report.chains)
        except Exception as exc:
            logger.warning("Provenance chain build failed: %s", exc)
            return []

    def score(self, output_text: str) -> dict[str, Any]:
        """Run DPE scorers against ``output_text``.

        Returns:
            Dict with ``fabrications``, ``distortions``, ``contradictions``,
            ``omissions``, and ``grounded`` counts/scores.
        """
        dpe = self._dpe()
        if dpe is None:
            return {
                "fabrications": 0,
                "distortions": 0,
                "contradictions": 0,
                "omissions": 0,
                "grounded": False,
            }

        facts = self._facts_for_dpe()
        session_id = getattr(self._orchestrator._session, "session_id", "")
        try:
            report = dpe.analyse(
                output_text=output_text,
                packed_facts=facts,
                session_id=session_id,
                window_id="",
            )
            fidelity = getattr(report, "fidelity", None) or SimpleNamespace(
                fabrication_count=0,
                distortion_count=0,
                contradiction_count=0,
                critical_omission_count=0,
            )
            return {
                "fabrications": getattr(fidelity, "fabrication_count", 0),
                "distortions": getattr(fidelity, "distortion_count", 0),
                "contradictions": getattr(fidelity, "contradiction_count", 0),
                "omissions": getattr(fidelity, "critical_omission_count", 0),
                "grounded": getattr(report, "grounding_ratio", 0.0) > 0.5,
            }
        except Exception as exc:
            logger.warning("Provenance scoring failed: %s", exc)
            return {
                "fabrications": 0,
                "distortions": 0,
                "contradictions": 0,
                "omissions": 0,
                "grounded": False,
            }

    def report(self, output_text: str) -> dict[str, Any]:
        """Return a combined provenance report for ``output_text``.

        Returns:
            Dict with chain count, scores, grounding ratio, and quality tier.
        """
        score = self.score(output_text)
        chains = self.chains(output_text)
        return {
            "chains": len(chains),
            **score,
            "chain_ids": [getattr(c, "claim_index", None) for c in chains],
        }


# ── Reasoning ──────────────────────────────────────────────────────────────


class _ReasoningProxy:
    """Reasoning / meta-learning proxy (SPEC-019, §12, §13).

    Exposes reasoning scaffolds, source grounding retrieval, CQS detection,
    and cross-window validation.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def scaffold(self, task: str, **kwargs: Any) -> str:
        """Build a reasoning scaffold for ``task``.

        Args:
            task: Task description.
            **kwargs: Additional options forwarded to the meta-learning engine.

        Returns:
            Scaffold string (empty if scaffolding is disabled).
        """
        engine = getattr(self._orchestrator, "_meta_learning", None)
        if engine is None or not hasattr(engine, "build_reasoning_scaffold"):
            return ""
        try:
            return engine.build_reasoning_scaffold(task, **kwargs)
        except Exception as exc:
            logger.warning("Scaffold build failed: %s", exc)
            return ""

    def sources(self, fact_id: str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve source passages linked to a fact.

        Args:
            fact_id: Fact identifier. If ``None``, all passages are returned.
            **kwargs: Additional filtering options.

        Returns:
            List of source passage dicts.
        """
        engine = getattr(self._orchestrator, "_source_grounding", None)
        if engine is None:
            return []
        try:
            if fact_id is None:
                passages = [
                    p.to_dict() for p in getattr(engine, "_passages", {}).values()
                ]
                return passages
            passages = engine.get_passages_for_fact(fact_id)
            return [p.to_dict() for p in passages]
        except Exception as exc:
            logger.warning("Source retrieval failed: %s", exc)
            return []

    def cqs(self, signal: str) -> dict[str, Any]:
        """Detect Context Quality Signals (CQS) in ``signal``.

        Args:
            signal: Text to scan for context hunger signals.

        Returns:
            Dict describing detected signals and recommended action.
        """
        from crp.advanced.cqs import CQSDetector

        detector = CQSDetector()
        try:
            signals = detector.detect_context_hunger(signal)
            response = detector.respond_to_context_hunger(signals)
            return {
                "action": response.action,
                "signals": [
                    {
                        "type": s.signal_type,
                        "strength": s.strength,
                        "topic": s.topic,
                    }
                    for s in signals
                ],
                "enrichment_budget": response.enrichment_budget,
                "enrichment_topics": response.enrichment_topics,
            }
        except Exception as exc:
            logger.warning("CQS detection failed: %s", exc)
            return {"action": "none", "signals": [], "enrichment_budget": 0, "enrichment_topics": []}

    def cross_window_validate(self, windows: list[str], **kwargs: Any) -> dict[str, Any]:
        """Run cross-window consistency validation.

        Args:
            windows: List of window output strings.
            **kwargs: Additional options forwarded to the validator.

        Returns:
            Dict with issues and severity counts.
        """
        from crp.advanced.cross_window import CrossWindowValidator

        validator = CrossWindowValidator(**kwargs)
        try:
            facts: list[dict[str, Any]] = []
            for w in windows:
                facts.extend({"text": line} for line in w.split("\n") if line.strip())
            result = validator.extraction_based_validation(facts, window_outputs=windows)
            return {
                "tier": result.tier,
                "has_issues": result.has_issues,
                "high_severity_count": result.high_severity_count,
                "issues": [
                    {
                        "type": i.issue_type,
                        "description": i.description,
                        "severity": i.severity,
                    }
                    for i in result.issues
                ],
            }
        except Exception as exc:
            logger.warning("Cross-window validation failed: %s", exc)
            return {"tier": 1, "has_issues": False, "high_severity_count": 0, "issues": []}


# ── Activation ─────────────────────────────────────────────────────────────


class _ActivationProxy:
    """Activation-mode proxy (SPEC-017).

    Exposes mode detection, tier-cap application, and per-call coverage.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def mode(self) -> str:
        """Detect the current CRP activation mode.

        Returns:
            One of ``zero-ckf``, ``partial-ckf``, or ``full-ckf``.
        """
        from crp.activation.mode import detect_mode

        try:
            fact_count = self._orchestrator.ckf.fact_count()
            health = self._orchestrator.ckf.health()
            community_count = getattr(health, "community_count", 0)
            return detect_mode(fact_count, community_count).value
        except Exception as exc:
            logger.warning("Mode detection failed: %s", exc)
            return "zero-ckf"

    def apply_tier_cap(self, quality_tier: str) -> str:
        """Apply the Partial-CKF tier cap to ``quality_tier``.

        Args:
            quality_tier: Candidate quality tier (S/A/B/C/D).

        Returns:
            Capped tier string.
        """
        from crp.activation.mode import apply_tier_cap

        current_mode = self.mode()
        cap = None
        if current_mode == "partial-ckf":
            cap = "B"
        elif current_mode == "zero-ckf":
            cap = "C"
        return apply_tier_cap(quality_tier, cap)

    def coverage(self) -> dict[str, Any]:
        """Return the current per-call coverage result.

        Returns:
            Dict with ``coverage``, ``effective_mode``, ``tier_cap``,
            and ``reason``.
        """
        from crp.activation.mode import assess_coverage

        try:
            fact_count = self._orchestrator.ckf.fact_count()
            result = assess_coverage(matching_facts=fact_count, expected_facts_needed=max(1, fact_count))
            return {
                "coverage": result.coverage,
                "effective_mode": result.effective_mode.value,
                "tier_cap": result.tier_cap,
                "reason": result.reason,
            }
        except Exception as exc:
            logger.warning("Coverage assessment failed: %s", exc)
            return {"coverage": 0.0, "effective_mode": "zero-ckf", "tier_cap": "C", "reason": "error"}


# ── Agent ──────────────────────────────────────────────────────────────────


class _AgentProxy:
    """Multi-agent safety budget and chain proxy (SPEC-012).

    Exposes the agent safety budget, event accounting, sub-agent linking,
    and quality aggregation.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def budget(self) -> Any:
        """Return the orchestrator's ``AgentSafetyBudget`` if present.

        Returns:
            AgentSafetyBudget instance.
        """
        from crp.agent.budget import AgentSafetyBudget

        existing = getattr(self._orchestrator, "_agent_budget", None)
        if isinstance(existing, AgentSafetyBudget):
            return existing
        budget = AgentSafetyBudget()
        self._orchestrator._agent_budget = budget
        return budget

    def account_event(self, risk_level: str) -> dict[str, Any]:
        """Account a risk event against the agent safety budget.

        Args:
            risk_level: One of ``LOW``, ``MEDIUM``, ``HIGH``, ``CRITICAL``.

        Returns:
            Dict with ``budget``, ``health``, ``circuit_state``, and
            ``halted`` status.
        """
        from crp.policy.model import RiskLevel

        budget = self.budget()
        try:
            level = RiskLevel[risk_level.upper()]
        except KeyError:
            level = RiskLevel.LOW
        decision = budget.account(level)
        return {
            "budget": decision.budget,
            "health": decision.health.value,
            "circuit_state": decision.circuit_state.value,
            "halted": decision.halted,
        }

    def link_sub_agent(self, parent_handle: str, child_handle: str) -> str:
        """Link a sub-agent session into the orchestrator HMAC chain.

        Args:
            parent_handle: Parent session/window identifier.
            child_handle: Child session/window identifier.

        Returns:
            HMAC link string.
        """
        from crp.agent.chain import fan_in_hmac

        try:
            key = self._orchestrator._security.session_key
        except Exception:
            key = b""
        return fan_in_hmac([parent_handle, child_handle], key)

    def aggregate(self, results: list[Any]) -> dict[str, Any]:
        """Aggregate quality across sub-agent results.

        Args:
            results: Sub-agent response strings or result objects.

        Returns:
            Dict with coherence and completeness summaries.
        """
        from crp.agent.chain import aggregate_sub_agent_quality

        try:
            responses = [r if isinstance(r, str) else getattr(r, "text", str(r)) for r in results]
            result = aggregate_sub_agent_quality("", responses)
            return {
                "coherent": result.is_coherent,
                "contradiction_count": result.contradiction_count,
                "has_critical": result.has_critical,
            }
        except Exception as exc:
            logger.warning("Sub-agent aggregation failed: %s", exc)
            return {"coherent": True, "contradiction_count": 0, "has_critical": False}


# ── Events ─────────────────────────────────────────────────────────────────


class _EventsProxy:
    """Protocol event bus proxy (§9).

    Subscribes, unsubscribes, and emits events through the orchestrator's
    event emitter.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def _emitter(self) -> Any:
        return getattr(self._orchestrator, "_emitter", None)

    def subscribe(self, event_type: str, callback: Any) -> None:
        """Subscribe ``callback`` to ``event_type``.

        Args:
            event_type: Event name.
            callback: Callable invoked when the event fires.
        """
        emitter = self._emitter()
        if emitter is None:
            return
        try:
            emitter.on(event_type, callback)
        except Exception as exc:
            logger.warning("Event subscribe failed: %s", exc)

    def unsubscribe(self, event_type: str, callback: Any) -> None:
        """Unsubscribe ``callback`` from ``event_type``.

        Args:
            event_type: Event name.
            callback: Previously registered callable.
        """
        emitter = self._emitter()
        if emitter is None:
            return
        try:
            emitter.off(event_type, callback)
        except Exception as exc:
            logger.warning("Event unsubscribe failed: %s", exc)

    def emit(self, event_type: str, payload: Any) -> None:
        """Emit ``event_type`` with ``payload``.

        Args:
            event_type: Event name.
            payload: Event data.
        """
        emitter = self._emitter()
        if emitter is None:
            return
        try:
            emitter.emit(event_type, payload)
        except Exception as exc:
            logger.warning("Event emit failed: %s", exc)


# ── Providers ──────────────────────────────────────────────────────────────


class _ProvidersProxy:
    """LLM provider registry proxy (SPEC-008).

    Registers providers, returns the current default provider, and lists
    supported provider names.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def register(self, provider: Any) -> None:
        """Register ``provider`` on the orchestrator if possible.

        Args:
            provider: An LLMProvider instance.
        """
        pm = getattr(self._orchestrator, "_provider_manager", None)
        if pm is not None and hasattr(pm, "register"):
            try:
                pm.register(provider)
                return
            except Exception as exc:
                logger.warning("Provider manager registration failed: %s", exc)
        if hasattr(self._orchestrator, "_provider"):
            self._orchestrator._provider = provider
        else:
            raise NotImplementedError("Cannot register provider on this orchestrator")

    def default(self) -> Any:
        """Return the orchestrator's current default provider."""
        return getattr(self._orchestrator, "_provider", None)

    def list_supported(self) -> list[str]:
        """Return the list of known/supported provider names."""
        return ["openai", "anthropic", "azure", "ollama", "local", "custom"]


# ── Extraction ─────────────────────────────────────────────────────────────


class _ExtractionProxy:
    """Graduated extraction pipeline proxy (§2.5).

    Runs extraction over text and returns facts or the full fact graph.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def run(self, text: str, content_type: str | None = None, **kwargs: Any) -> Any:
        """Run the extraction pipeline on ``text``.

        Args:
            text: Input text to extract facts from.
            content_type: Optional MIME-like content hint.
            **kwargs: Additional options forwarded to ``extract``.

        Returns:
            ExtractionResult / PipelineExtractionResult from the pipeline.
        """
        pipeline = getattr(self._orchestrator, "extraction_pipeline", None)
        if pipeline is None:
            raise NotImplementedError("Extraction pipeline is not available")
        # Some extraction pipelines do not accept ``content_type``; try with,
        # then fall back to without to remain compatible with all variants.
        if content_type is not None:
            try:
                return pipeline.extract(text, content_type=content_type, **kwargs)
            except TypeError:
                logger.debug("Pipeline does not accept content_type; dropping it")
        return pipeline.extract(text, **kwargs)

    def facts(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Return extracted facts from ``text`` as plain dicts.

        Args:
            text: Input text.
            **kwargs: Options forwarded to :meth:`run`.

        Returns:
            List of fact dicts.
        """
        result = self.run(text, **kwargs)
        facts = getattr(result, "facts", [])
        return [
            {
                "id": getattr(f, "id", ""),
                "text": getattr(f, "text", ""),
                "confidence": getattr(f, "confidence", 0.0),
                "source_window_id": getattr(f, "source_window_id", ""),
            }
            for f in facts
        ]

    def graph(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Return the extracted fact graph from ``text``.

        Args:
            text: Input text.
            **kwargs: Options forwarded to :meth:`run`.

        Returns:
            Dict with ``nodes`` and ``edges`` lists.
        """
        result = self.run(text, **kwargs)
        graph = getattr(result, "fact_graph", None) or getattr(result, "graph", None)
        if graph is None:
            return {"nodes": [], "edges": []}
        nodes = [
            {
                "id": getattr(f, "id", ""),
                "text": getattr(f, "text", ""),
                "confidence": getattr(f, "confidence", 0.0),
            }
            for f in getattr(graph, "nodes", {}).values()
        ]
        edges = [
            {
                "source_id": getattr(e, "source_id", ""),
                "target_id": getattr(e, "target_id", ""),
                "relation": getattr(e, "relation", ""),
            }
            for e in getattr(graph, "edges", [])
        ]
        return {"nodes": nodes, "edges": edges}


# ── Existing visibility proxies (extended) ─────────────────────────────────


class _StorageProxy:
    """Storage visibility proxy backed by the orchestrator WarmStateStore."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def overview(self) -> list[dict[str, Any]]:
        """Return a list of storage primitive overviews."""
        ws = self._orchestrator.warm_store
        return [
            {"primitive": "warm_store", "backend": "in-memory", "size": ws.fact_count}
            | ws.to_dict(),
        ]

    def fact_count(self) -> int:
        """Return the warm-store fact count."""
        return self._orchestrator.warm_store.fact_count

    def windows(self) -> int:
        """Return the warm-store window count."""
        return self._orchestrator.warm_store.window_count

    def save(self, path: str | Path) -> None:
        """Persist warm-store state to ``path``.

        Args:
            path: Destination file path.

        Raises:
            NotImplementedError: If persistence is not available.
        """
        ws = self._orchestrator.warm_store
        target = str(path)
        if hasattr(ws, "persist"):
            ws.persist(target)
            return
        # Fallback: use cold-storage helper if available
        from crp.state.cold_storage import persist_to_cold
        from crp.state.event_log import FactEventLog

        persist_to_cold(ws, FactEventLog(), target)

    def load(self, path: str | Path) -> Any:
        """Restore warm-store state from ``path``.

        Args:
            path: Source file path.

        Returns:
            Restore warnings or empty list.
        """
        ws = self._orchestrator.warm_store
        target = str(path)
        if hasattr(ws, "restore"):
            return ws.restore(target)
        from crp.state.cold_storage import restore_from_cold
        from crp.state.event_log import FactEventLog

        _header, warnings, _community_map = restore_from_cold(ws, FactEventLog(), target)
        return warnings

    @property
    def backend(self) -> str:
        """Return the active storage backend name."""
        ws = self._orchestrator.warm_store
        cfg = getattr(ws, "_config", None)
        if cfg is not None and getattr(cfg, "persist_enabled", False):
            return "sqlite"
        return "memory"

    @property
    def config(self) -> dict[str, Any]:
        """Return the warm-store configuration as a dict."""
        ws = self._orchestrator.warm_store
        cfg = getattr(ws, "_config", None)
        if cfg is None:
            return {}
        return {
            "max_facts": getattr(cfg, "max_facts", 10_000),
            "persist_enabled": getattr(cfg, "persist_enabled", False),
            "persist_path": getattr(cfg, "persist_path", ""),
        }


class _KnowledgeProxy:
    """Knowledge-location proxy backed by the Contextual Knowledge Fabric."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    @property
    def location(self) -> str:
        """Return the knowledge location identifier.

        Inspects the backend configuration when available; defaults to ``CKF``.
        """
        ckf = self._orchestrator.ckf
        cfg = getattr(ckf, "_config", None)
        persist_path = getattr(cfg, "persist_path", None) if cfg is not None else None
        if persist_path:
            return f"CKF (persist={persist_path})"
        return "CKF"

    def query(self, **kwargs: Any) -> Any:
        """Pattern query on the CKF fact graph."""
        return self._orchestrator.ckf.query(**kwargs)

    def search(self, query: str, top_k: int = 5, **kwargs: Any) -> Any:
        """Semantic search over the CKF."""
        try:
            from crp.provenance._embeddings import encode_texts

            embeddings = encode_texts([query])
            embedding = embeddings[0] if embeddings else None
        except Exception:
            embedding = None
        return self._orchestrator.ckf.retrieve(
            query_embedding=embedding,
            budget=top_k,
            **kwargs,
        )

    def health(self) -> Any:
        """CKF health snapshot."""
        return self._orchestrator.ckf.health()

    def graph_walk(self, start_fact_id: str, max_hops: int = 3, **kwargs: Any) -> Any:
        """Graph walk from ``start_fact_id``."""
        from crp.ckf.graph_walk import graph_walk

        graph = self._orchestrator.ckf._warm._graph
        return graph_walk(graph, {start_fact_id}, max_hops=max_hops, **kwargs)

    def community_summary(self, topic: str = "", **kwargs: Any) -> Any:
        """Return communities matching ``topic``.

        Args:
            topic: Optional topic filter.
            **kwargs: Ignored — kept for API consistency.

        Returns:
            CommunityResult or list of matching Community objects.
        """
        from crp.ckf.community import CommunityDetector

        ckf = self._orchestrator.ckf
        graph = ckf._warm._graph
        detector = CommunityDetector()
        result = detector.detect(graph)
        if not topic:
            return result
        topic_lower = topic.lower()
        matched = []
        for comm in result.communities:
            if topic_lower in comm.summary.lower():
                matched.append(comm)
                continue
            for fid in comm.fact_ids:
                fact = graph.nodes.get(fid)
                if fact and topic_lower in fact.text.lower():
                    matched.append(comm)
                    break
        return matched

    def cdgr_expand(self, query: str, **kwargs: Any) -> Any:
        """CDGR expansion from ``query`` (SPEC-025)."""
        proxy = _CKFProxy(self._orchestrator)
        return proxy.cdgr_expand(query, **kwargs)

    def persist(self, path: str | Path | None = None) -> None:
        """Persist CKF state to ``path``."""
        proxy = _CKFProxy(self._orchestrator)
        proxy.persist(path)

    def restore(self, path: str | Path | None = None) -> Any:
        """Restore CKF state from ``path``."""
        proxy = _CKFProxy(self._orchestrator)
        return proxy.restore(path)

    def subscribe(self, event_type: Any, callback: Any) -> None:
        """Subscribe to CKF pub/sub events."""
        proxy = _CKFProxy(self._orchestrator)
        proxy.subscribe(event_type, callback)


class _AuditProxy:
    """Tamper-evident audit-trail proxy."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def _trail(self) -> Any:
        return self._orchestrator._security.compliance_audit

    def events(self, *, event_type: str | None = None, since: float | None = None) -> list[dict[str, Any]]:
        """Return audit events as plain dicts."""
        entries = self._trail().query(event_type=event_type, since=since)
        return [e.to_dict() for e in entries]

    def export(self, *, include_signatures: bool = True) -> dict[str, Any]:
        """Export the full audit trail with chain-integrity status."""
        return self._trail().export(include_signatures=include_signatures)

    def verify(self) -> tuple[bool, int]:
        """Verify the HMAC chain. Returns (valid, broken_at_sequence)."""
        return self._trail().verify_chain()

    def summary(self) -> dict[str, Any]:
        """Short summary of the audit trail."""
        trail = self._trail()
        return {
            "entry_count": trail.entry_count,
            "session_id": self._orchestrator._session.session_id,
            "verified": trail.verify_chain()[0],
        }

    def record(self, event_type: str, details: dict[str, Any]) -> None:
        """Record a custom event on the audit trail.

        Args:
            event_type: Event type string.
            details: Arbitrary event payload.
        """
        from crp.security.audit_trail import ComplianceEventType

        trail = self._trail()
        try:
            et = ComplianceEventType(event_type)
        except ValueError:
            et = ComplianceEventType.DATA_PROCESSED
        trail.record(
            et,
            session_id=self._orchestrator._session.session_id,
            data=details,
        )

    def query(
        self,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit events with an optional limit.

        Args:
            event_type: Filter by event type.
            since: Unix timestamp lower bound.
            limit: Maximum events to return.

        Returns:
            List of event dicts.
        """
        entries = self._trail().query(event_type=event_type, since=since)
        return [e.to_dict() for e in entries[:limit]]

    @property
    def chain_hash(self) -> str:
        """Return the current audit chain tip hash if available."""
        trail = self._trail()
        tip = getattr(trail, "chain_tip", None)
        if tip is None:
            entries = getattr(trail, "_entries", [])
            if entries:
                last = entries[-1]
                return getattr(last, "chain_hash", "")
        return tip or ""


class _ComplianceProxy:
    """EU AI Act / ISO 42001 compliance helpers."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def classify(
        self,
        intended_purpose: str = "",
        *,
        processes_personal_data: bool = False,
        makes_automated_decisions: bool = False,
        affects_fundamental_rights: bool = False,
        safety_critical: bool = False,
        profiles_individuals: bool = False,
    ) -> dict[str, Any]:
        """Run EU AI Act risk classification for the current use case."""
        classifier = self._orchestrator._security.risk_classifier
        assessment = classifier.assess(
            intended_purpose=intended_purpose,
            processes_personal_data=processes_personal_data,
            makes_automated_decisions=makes_automated_decisions,
            affects_fundamental_rights=affects_fundamental_rights,
            safety_critical=safety_critical,
            profiles_individuals=profiles_individuals,
        )
        return assessment.to_dict()

    def report(self) -> dict[str, Any]:
        """Generate a compliance status report for the current session."""
        reporter = self._orchestrator._security.compliance_reporter
        return reporter.generate_report()

    def controls(self) -> list[dict[str, Any]]:
        """List available compliance controls."""
        reporter = self._orchestrator._security.compliance_reporter
        controls = getattr(reporter, "controls", [])
        return [c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in controls]

    def risk_level(self) -> str:
        """Return the latest risk classification level, if any."""
        reporter = self._orchestrator._security.compliance_reporter
        report = reporter.generate_report()
        return report.get("risk_level", "UNCLASSIFIED")

    def transparency_declaration(self) -> dict[str, Any]:
        """Return a transparency declaration for the current session.

        Returns:
            Dict summarising purpose, data categories, and retention.
        """
        from crp.security.consent import ProcessingPurpose

        records = getattr(self._orchestrator._security.processing_records, "records", [])
        purposes: set[str] = set()
        for r in records:
            purpose = getattr(r, "purpose", None)
            if purpose is None:
                purpose = ProcessingPurpose.CONTEXT_MANAGEMENT
            purposes.add(purpose.value)
        purposes_sorted = sorted(purposes)
        return {
            "session_id": self._orchestrator._session.session_id,
            "purposes": purposes_sorted,
            "record_count": len(records),
            "has_human_oversight": getattr(
                self._orchestrator._security.human_oversight._config, "level", None
            ) is not None,
        }

    def processing_records(self) -> list[dict[str, Any]]:
        """Return GDPR Art. 30 processing records as plain dicts."""
        keeper = self._orchestrator._security.processing_records
        records = getattr(keeper, "records", [])
        return [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in records]
