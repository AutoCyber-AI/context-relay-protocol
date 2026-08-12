# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""EU AI Act + ISO 42001 compliance framework (§7.15).

Implements:
  - AI system risk classification (EU AI Act Art. 6)
  - Transparency declarations (EU AI Act Art. 13)
  - Technical documentation generation (EU AI Act Art. 11)
  - Compliance status reporting (EU AI Act Art. 9, ISO 42001 9.1)
  - AI impact assessment (ISO 42001 A.6.2.4)
  - Quality management system integration (EU AI Act Art. 17)

EU AI Act: Art. 6 (classification), Art. 9-17 (high-risk requirements)
ISO 42001: 4-10 (full AIMS lifecycle), A.6.2 (AI-specific controls)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.compliance")


# ---------------------------------------------------------------------------
# AI risk classification (EU AI Act Art. 6)
# ---------------------------------------------------------------------------


class AIRiskLevel(str, Enum):
    """EU AI Act risk classification levels (Art. 6) (§7.15.1)."""

    MINIMAL = "minimal"  # Unregulated (spam filters, video games)
    LIMITED = "limited"  # Transparency obligations (chatbots, deepfakes)
    HIGH = "high"  # Full compliance required (see Annex III)
    UNACCEPTABLE = "unacceptable"  # Prohibited (social scoring, etc.)


class AISystemCategory(str, Enum):
    """Categories of AI system use cases relevant to risk classification."""

    GENERAL_PURPOSE = "general_purpose"  # GPAI model provider/integrator
    CONTEXT_MANAGEMENT = "context_management"  # CRP core function
    CONTENT_GENERATION = "content_generation"  # Text generation via LLM
    DECISION_SUPPORT = "decision_support"  # AI-assisted decisions
    AUTOMATED_DECISION = "automated_decision"  # Automated decision-making
    BIOMETRIC = "biometric"  # Biometric processing
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"  # Safety-critical
    EMPLOYMENT = "employment"  # HR/recruitment
    EDUCATION = "education"  # Education assessment
    LAW_ENFORCEMENT = "law_enforcement"  # Law enforcement
    HEALTHCARE = "healthcare"  # Health/medical
    FINANCIAL = "financial"  # Credit scoring, insurance


@dataclass
class RiskAssessment:
    """AI system risk assessment result (§7.15.1).

    EU AI Act Art. 9: Providers must establish a risk management system
    for the entire lifecycle of the high-risk AI system.
    """

    assessment_id: str
    timestamp: float = field(default_factory=time.time)
    risk_level: AIRiskLevel = AIRiskLevel.MINIMAL
    system_category: AISystemCategory = AISystemCategory.CONTEXT_MANAGEMENT
    intended_purpose: str = ""
    # Risk factors
    processes_personal_data: bool = False
    makes_automated_decisions: bool = False
    affects_fundamental_rights: bool = False
    safety_critical: bool = False
    profiles_individuals: bool = False
    # Mitigation measures
    mitigations: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)
    # Assessment outcome
    assessment_notes: str = ""
    assessor: str = ""  # Who performed the assessment
    review_date: float = 0.0  # When to review again

    def to_dict(self) -> dict[str, Any]:
        """Serialise the risk assessment to a JSON-safe dict.

        Returns:
            Dict representation including risk level, category, factors,
            mitigations, and residual risks.
        """
        return {
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "risk_level": self.risk_level.value,
            "system_category": self.system_category.value,
            "intended_purpose": self.intended_purpose,
            "risk_factors": {
                "processes_personal_data": self.processes_personal_data,
                "makes_automated_decisions": self.makes_automated_decisions,
                "affects_fundamental_rights": self.affects_fundamental_rights,
                "safety_critical": self.safety_critical,
                "profiles_individuals": self.profiles_individuals,
            },
            "mitigations": self.mitigations,
            "residual_risks": self.residual_risks,
            "assessment_notes": self.assessment_notes,
            "assessor": self.assessor,
            "review_date": self.review_date,
        }


class RiskClassifier:
    """Classify AI system risk level per EU AI Act (§7.15.1).

    Helps users determine their obligation level based on how they
    deploy CRP within their AI system.

    CRP itself is a context management tool — typically MINIMAL or LIMITED
    risk. However, if CRP is integrated into a high-risk AI system
    (e.g., employment screening, credit scoring), the overall system
    inherits the higher classification.

    Usage::

        classifier = RiskClassifier()
        assessment = classifier.assess(
            category=AISystemCategory.CONTEXT_MANAGEMENT,
            intended_purpose="Managing context for a customer support chatbot",
            processes_personal_data=True,
        )
        print(f"Risk level: {assessment.risk_level.value}")
    """

    # Categories that are always HIGH risk per EU AI Act Annex III
    _HIGH_RISK_CATEGORIES: frozenset[AISystemCategory] = frozenset(
        {
            AISystemCategory.BIOMETRIC,
            AISystemCategory.CRITICAL_INFRASTRUCTURE,
            AISystemCategory.EMPLOYMENT,
            AISystemCategory.EDUCATION,
            AISystemCategory.LAW_ENFORCEMENT,
            AISystemCategory.HEALTHCARE,
            AISystemCategory.FINANCIAL,
        }
    )

    # Categories that are always UNACCEPTABLE
    _PROHIBITED_INDICATORS: list[str] = [
        "social_scoring",
        "subliminal_manipulation",
        "vulnerability_exploitation",
        "emotion_recognition_workplace",
        "untargeted_facial_scraping",
        "predictive_policing_profiling",
    ]

    def assess(
        self,
        category: AISystemCategory = AISystemCategory.CONTEXT_MANAGEMENT,
        intended_purpose: str = "",
        processes_personal_data: bool = False,
        makes_automated_decisions: bool = False,
        affects_fundamental_rights: bool = False,
        safety_critical: bool = False,
        profiles_individuals: bool = False,
    ) -> RiskAssessment:
        """Perform risk assessment based on EU AI Act criteria.

        Args:
            category: AI system use-case category.
            intended_purpose: Human-readable description of the system's purpose.
            processes_personal_data: Whether the system processes personal data.
            makes_automated_decisions: Whether decisions are automated.
            affects_fundamental_rights: Whether outputs affect fundamental rights.
            safety_critical: Whether the system is safety-critical.
            profiles_individuals: Whether individuals are profiled.

        Returns:
            ``RiskAssessment`` with level, mitigations, and residual risks.
        """
        import uuid

        # Determine risk level
        risk_level = self._classify(
            category=category,
            processes_personal_data=processes_personal_data,
            makes_automated_decisions=makes_automated_decisions,
            affects_fundamental_rights=affects_fundamental_rights,
            safety_critical=safety_critical,
            profiles_individuals=profiles_individuals,
        )

        # Determine mitigations (CRP provides these natively)
        mitigations = self._get_native_mitigations(risk_level)

        # Identify residual risks
        residual_risks = self._get_residual_risks(
            risk_level, processes_personal_data, makes_automated_decisions
        )

        assessment = RiskAssessment(
            assessment_id=f"risk-{uuid.uuid4().hex[:12]}",
            risk_level=risk_level,
            system_category=category,
            intended_purpose=intended_purpose,
            processes_personal_data=processes_personal_data,
            makes_automated_decisions=makes_automated_decisions,
            affects_fundamental_rights=affects_fundamental_rights,
            safety_critical=safety_critical,
            profiles_individuals=profiles_individuals,
            mitigations=mitigations,
            residual_risks=residual_risks,
        )

        logger.info(
            "Risk assessment: %s → %s (category=%s)",
            assessment.assessment_id,
            risk_level.value,
            category.value,
        )
        return assessment

    def _classify(
        self,
        category: AISystemCategory,
        processes_personal_data: bool,
        makes_automated_decisions: bool,
        affects_fundamental_rights: bool,
        safety_critical: bool,
        profiles_individuals: bool,
    ) -> AIRiskLevel:
        """Apply EU AI Act classification rules.

        Args:
            category: AI system use-case category.
            processes_personal_data: Personal data processing indicator.
            makes_automated_decisions: Automated decision indicator.
            affects_fundamental_rights: Fundamental rights indicator.
            safety_critical: Safety-critical indicator.
            profiles_individuals: Profiling indicator.

        Returns:
            Determined ``AIRiskLevel``.
        """
        # Annex III high-risk categories
        if category in self._HIGH_RISK_CATEGORIES:
            return AIRiskLevel.HIGH

        # Profiling individuals always at least HIGH (Art. 6.2)
        if profiles_individuals:
            return AIRiskLevel.HIGH

        # Safety-critical → HIGH
        if safety_critical:
            return AIRiskLevel.HIGH

        # Automated decisions affecting fundamental rights → HIGH
        if makes_automated_decisions and affects_fundamental_rights:
            return AIRiskLevel.HIGH

        # AI systems that interact with humans → LIMITED (transparency)
        if category in (
            AISystemCategory.CONTENT_GENERATION,
            AISystemCategory.DECISION_SUPPORT,
            AISystemCategory.GENERAL_PURPOSE,
        ):
            return AIRiskLevel.LIMITED

        # Context management with personal data → LIMITED
        if processes_personal_data:
            return AIRiskLevel.LIMITED

        # Default: MINIMAL
        return AIRiskLevel.MINIMAL

    def _get_native_mitigations(self, risk_level: AIRiskLevel) -> list[str]:
        """List CRP's native risk mitigations.

        Args:
            risk_level: Assessed risk level.

        Returns:
            List of mitigation descriptions relevant to the risk level.
        """
        mitigations = [
            "Session-scoped cryptographic isolation (§7.1)",
            "AES-256-GCM encryption at rest (§7.3)",
            "Input validation — always on, cannot disable (§7.4)",
            "Prompt injection detection — advisory, never blocks (§7.5)",
            "Anti-poisoning quarantine with confidence penalty (§7.8)",
            "RBAC with three-tier access control (§7.10)",
            "Embedding defense — SQ8 + XOR salting (§7.11)",
            "PII detection and data classification (§7.12)",
            "Consent management with purpose limitation (§7.13)",
            "Tamper-evident HMAC-signed audit trail (§7.14)",
            "Fact integrity chain — BLAKE3/SHA-256 (§7.2, §7.7)",
            "Data retention with automatic expiry (§7.12.3)",
            "Right to erasure support — GDPR Art. 17 (§7.12.4)",
        ]

        if risk_level in (AIRiskLevel.HIGH, AIRiskLevel.LIMITED):
            mitigations.extend(
                [
                    "Human oversight controls — configurable levels (§7.13.4)",
                    "Processing records — GDPR Art. 30 compliant (§7.13.3)",
                    "Data lineage tracking (§7.12.5)",
                    "Compliance audit trail export for regulatory review (§7.14)",
                ]
            )

        return mitigations

    def _get_residual_risks(
        self,
        risk_level: AIRiskLevel,
        processes_personal_data: bool,
        makes_automated_decisions: bool,
    ) -> list[str]:
        """Identify residual risks that CRP cannot fully mitigate.

        Args:
            risk_level: Assessed risk level.
            processes_personal_data: Whether personal data is processed.
            makes_automated_decisions: Whether automated decisions are made.

        Returns:
            List of residual risk descriptions.
        """
        risks: list[str] = []

        if risk_level == AIRiskLevel.HIGH:
            risks.append(
                "CRP provides context management — the deployer is responsible "
                "for the overall high-risk AI system conformity assessment"
            )
            risks.append(
                "LLM output quality and bias are the provider's responsibility "
                "(CRP relays output without modification — Axiom 9)"
            )

        if processes_personal_data:
            risks.append(
                "PII detection is pattern-based and may miss novel PII formats; "
                "deployers should implement additional domain-specific checks"
            )

        if makes_automated_decisions:
            risks.append(
                "CRP does not make decisions — it manages context for LLMs; "
                "decision-making logic is the deployer's responsibility"
            )

        risks.append(
            "XOR cipher fallback when cryptography package is not installed "
            "provides only obfuscation — install cryptography for production"
        )

        return risks


# ---------------------------------------------------------------------------
# Transparency declaration (EU AI Act Art. 13)
# ---------------------------------------------------------------------------


@dataclass
class TransparencyDeclaration:
    """Transparency declaration for AI system users (§7.15.2).

    EU AI Act Art. 13: Providers must ensure that high-risk AI systems
    are designed and developed in such a way that their operation is
    sufficiently transparent to enable deployers to interpret the
    system's output and use it appropriately.
    """

    system_name: str = "Context Relay Protocol (CRP)"
    system_version: str = ""
    provider: str = "AutoCyber AI Pty Ltd"
    provider_contact: str = "security@autocyberai.com"
    intended_purpose: str = (
        "CRP manages context windows for Large Language Model (LLM) "
        "applications. It extracts, stores, and retrieves knowledge "
        "across multi-window conversations to maximize LLM output quality."
    )
    ai_involvement: str = (
        "CRP uses AI/ML for: (1) fact extraction from text, "
        "(2) semantic similarity scoring for context selection, "
        "(3) prompt injection detection. CRP does NOT generate text — "
        "it relays context to an LLM chosen and controlled by the deployer."
    )
    data_processed: list[str] = field(
        default_factory=lambda: [
            "Text provided by the user for context management",
            "Facts extracted from text via NLP pipeline",
            "Knowledge graph relationships between facts",
            "Context envelopes assembled for LLM calls",
            "Quality scores for LLM output assessment",
        ]
    )
    data_not_processed: list[str] = field(
        default_factory=lambda: [
            "LLM API keys (never touch CRP servers)",
            "LLM request/response traffic (stays in user's process)",
            "System prompts (remain in user's application)",
            "User's application source code",
        ]
    )
    limitations: list[str] = field(
        default_factory=lambda: [
            "CRP does not generate text — quality depends on the LLM",
            "PII detection is pattern-based, not guaranteed comprehensive",
            "Injection detection is advisory, not guaranteed to catch all attacks",
            "Context selection is based on relevance scoring, not perfect recall",
        ]
    )
    human_oversight: str = (
        "CRP supports configurable human oversight levels: NONE, INFORMED, "
        "APPROVAL, and CONTROL. Deployers can require human approval "
        "before dispatch, ingest, export, or deletion operations."
    )
    risk_level: AIRiskLevel = AIRiskLevel.MINIMAL
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the transparency declaration to a JSON-safe dict.

        Returns:
            Dict representation suitable for disclosure dashboards or regulators.
        """
        return {
            "system_name": self.system_name,
            "system_version": self.system_version,
            "provider": self.provider,
            "provider_contact": self.provider_contact,
            "intended_purpose": self.intended_purpose,
            "ai_involvement": self.ai_involvement,
            "data_processed": self.data_processed,
            "data_not_processed": self.data_not_processed,
            "limitations": self.limitations,
            "human_oversight": self.human_oversight,
            "risk_level": self.risk_level.value,
            "last_updated": self.last_updated,
        }


# ---------------------------------------------------------------------------
# Compliance status report
# ---------------------------------------------------------------------------


@dataclass
class ComplianceControl:
    """Single compliance control status."""

    control_id: str
    framework: str  # "eu_ai_act" | "iso_42001"
    article: str  # e.g. "Art. 9" or "A.6.2.4"
    description: str
    status: str  # "implemented" | "partial" | "planned" | "not_applicable"
    implementation: str  # How CRP implements this control
    evidence: str = ""  # Where to find evidence (file, module, test)


class ComplianceReporter:
    """Generate compliance status reports (§7.15.3).

    Maps CRP's native security controls to EU AI Act articles and
    ISO 42001 clauses, reporting implementation status for each.

    Usage::

        reporter = ComplianceReporter()
        report = reporter.generate_report(session_stats={...})
        print(report["summary"]["compliance_score"])
    """

    def __init__(self) -> None:
        """Initialise the reporter with the built-in EU AI Act / ISO 42001 control map."""
        self._controls = self._build_control_map()

    def _build_control_map(self) -> list[ComplianceControl]:
        """Build the full control map — CRP features → regulations.

        Returns:
            List of ``ComplianceControl`` records mapping CRP implementation
            to EU AI Act articles and ISO 42001 clauses.
        """
        return [
            # ── EU AI Act ──────────────────────────────────────
            ComplianceControl(
                control_id="EUAI-01",
                framework="eu_ai_act",
                article="Art. 9",
                description="Risk management system",
                status="implemented",
                implementation=(
                    "RiskClassifier provides automated risk assessment. "
                    "Session-scoped security with 8-layer defense-in-depth."
                ),
                evidence="crp/security/compliance.py::RiskClassifier",
            ),
            ComplianceControl(
                control_id="EUAI-02",
                framework="eu_ai_act",
                article="Art. 10",
                description="Data governance",
                status="implemented",
                implementation=(
                    "DataClassification (5 levels), PII detection, "
                    "DataLineageTracker, RetentionManager with auto-expiry, "
                    "IngestQuarantine for anti-poisoning."
                ),
                evidence="crp/security/privacy.py, crp/security/quarantine.py",
            ),
            ComplianceControl(
                control_id="EUAI-03",
                framework="eu_ai_act",
                article="Art. 11",
                description="Technical documentation",
                status="implemented",
                implementation=(
                    "ComplianceReporter generates structured technical "
                    "documentation. TransparencyDeclaration provides "
                    "system-level documentation."
                ),
                evidence="crp/security/compliance.py::ComplianceReporter",
            ),
            ComplianceControl(
                control_id="EUAI-04",
                framework="eu_ai_act",
                article="Art. 12",
                description="Record-keeping (automatic logging)",
                status="implemented",
                implementation=(
                    "ComplianceAuditTrail with HMAC-signed tamper-evident "
                    "entries. ProcessingRecordKeeper for GDPR Art. 30. "
                    "EventEmitter with 30+ event types. TelemetryWriter "
                    "for per-window JSONL logs."
                ),
                evidence="crp/security/audit_trail.py, crp/observability/",
            ),
            ComplianceControl(
                control_id="EUAI-05",
                framework="eu_ai_act",
                article="Art. 13",
                description="Transparency",
                status="implemented",
                implementation=(
                    "TransparencyDeclaration documents system purpose, "
                    "AI involvement, data processed/not processed, "
                    "limitations. ConsentManager tracks processing purposes."
                ),
                evidence="crp/security/compliance.py, crp/security/consent.py",
            ),
            ComplianceControl(
                control_id="EUAI-06",
                framework="eu_ai_act",
                article="Art. 14",
                description="Human oversight",
                status="implemented",
                implementation=(
                    "HumanOversightController with 4 levels (NONE, INFORMED, "
                    "APPROVAL, CONTROL). Configurable approval requirements "
                    "per operation. Halt-on-detection for injection/PII."
                ),
                evidence="crp/security/consent.py::HumanOversightController",
            ),
            ComplianceControl(
                control_id="EUAI-07",
                framework="eu_ai_act",
                article="Art. 15",
                description="Accuracy, robustness, cybersecurity",
                status="implemented",
                implementation=(
                    "AES-256-GCM encryption, HMAC-SHA256 binding, "
                    "BLAKE3 integrity chains, 8-layer defense stack, "
                    "RBAC, rate limiting, input validation, injection "
                    "detection, anti-poisoning quarantine."
                ),
                evidence="crp/security/ (all 8 modules)",
            ),
            ComplianceControl(
                control_id="EUAI-08",
                framework="eu_ai_act",
                article="Art. 17",
                description="Quality management system",
                status="implemented",
                implementation=(
                    "QualityReport per dispatch with tier grading (S/A/B/C/D). "
                    "Overhead tracking, resource management, envelope "
                    "saturation metrics. ComplianceReporter for QMS evidence."
                ),
                evidence="crp/core/session.py::QualityReport, crp/observability/quality.py",
            ),
            # ── ISO 42001 ─────────────────────────────────────
            ComplianceControl(
                control_id="ISO-01",
                framework="iso_42001",
                article="A.6.2.3",
                description="Human oversight of AI systems",
                status="implemented",
                implementation=(
                    "HumanOversightController with configurable levels. "
                    "Approval workflows, halt mechanisms, autonomous limits."
                ),
                evidence="crp/security/consent.py::HumanOversightController",
            ),
            ComplianceControl(
                control_id="ISO-02",
                framework="iso_42001",
                article="A.6.2.4",
                description="AI impact assessment",
                status="implemented",
                implementation=(
                    "RiskClassifier performs AI risk assessment per EU AI Act "
                    "classification. Identifies mitigations and residual risks."
                ),
                evidence="crp/security/compliance.py::RiskClassifier",
            ),
            ComplianceControl(
                control_id="ISO-03",
                framework="iso_42001",
                article="A.6.2.5",
                description="Data for AI systems (collection & use)",
                status="implemented",
                implementation=(
                    "ConsentManager with processing purposes. ProcessingRecordKeeper "
                    "tracks all data processing activities with legal basis."
                ),
                evidence="crp/security/consent.py",
            ),
            ComplianceControl(
                control_id="ISO-04",
                framework="iso_42001",
                article="A.6.2.6",
                description="Data management",
                status="implemented",
                implementation=(
                    "DataClassification (5 levels), DataLineageTracker, "
                    "RetentionManager with auto-expiry, PII detection, "
                    "WarmStateStore with fact lifecycle management."
                ),
                evidence="crp/security/privacy.py",
            ),
            ComplianceControl(
                control_id="ISO-05",
                framework="iso_42001",
                article="A.6.2.7",
                description="Data subject rights",
                status="implemented",
                implementation=(
                    "ErasureManager for right to erasure (GDPR Art. 17). "
                    "export_state() for data portability. ConsentManager "
                    "for consent withdrawal."
                ),
                evidence="crp/security/privacy.py::ErasureManager",
            ),
            ComplianceControl(
                control_id="ISO-06",
                framework="iso_42001",
                article="A.6.2.8",
                description="Records management",
                status="implemented",
                implementation=(
                    "ComplianceAuditTrail with tamper-evident HMAC-signed entries. "
                    "ProcessingRecordKeeper for GDPR Art. 30. "
                    "EventEmitter + AuditLog for operational records."
                ),
                evidence="crp/security/audit_trail.py, crp/observability/audit.py",
            ),
            ComplianceControl(
                control_id="ISO-07",
                framework="iso_42001",
                article="9.1",
                description="Performance monitoring & measurement",
                status="implemented",
                implementation=(
                    "QualityReport with tier grading. TelemetryWriter for "
                    "per-window metrics. ResourceManager for memory tracking. "
                    "OverheadBudgetManager for performance caps."
                ),
                evidence="crp/observability/telemetry.py, crp/resources/",
            ),
            ComplianceControl(
                control_id="ISO-08",
                framework="iso_42001",
                article="10.1",
                description="Continual improvement",
                status="implemented",
                implementation=(
                    "Fact confidence decay, supersession, and archival. "
                    "Adaptive resource allocation. Meta-learning scaffolds. "
                    "Quality tier tracking across sessions."
                ),
                evidence="crp/state/warm_store.py, crp/advanced/meta_learning.py",
            ),
        ]

    def generate_report(
        self,
        session_stats: dict[str, Any] | None = None,
        risk_assessment: RiskAssessment | None = None,
    ) -> dict[str, Any]:
        """Generate a comprehensive compliance status report.

        Args:
            session_stats: Optional runtime/session statistics to include.
            risk_assessment: Optional ``RiskAssessment`` to attach.

        Returns:
            Dict with EU AI Act and ISO 42001 control lists, implementation
            counts, compliance percentages, and summary score.
        """
        eu_controls = [c for c in self._controls if c.framework == "eu_ai_act"]
        iso_controls = [c for c in self._controls if c.framework == "iso_42001"]

        eu_implemented = sum(1 for c in eu_controls if c.status == "implemented")
        iso_implemented = sum(1 for c in iso_controls if c.status == "implemented")

        report = {
            "report_type": "compliance_status",
            "generated_at": time.time(),
            "frameworks": {
                "eu_ai_act": {
                    "total_controls": len(eu_controls),
                    "implemented": eu_implemented,
                    "compliance_pct": round(
                        eu_implemented / len(eu_controls) * 100, 1
                    )
                    if eu_controls
                    else 0,
                    "controls": [
                        {
                            "control_id": c.control_id,
                            "article": c.article,
                            "description": c.description,
                            "status": c.status,
                            "implementation": c.implementation,
                            "evidence": c.evidence,
                        }
                        for c in eu_controls
                    ],
                },
                "iso_42001": {
                    "total_controls": len(iso_controls),
                    "implemented": iso_implemented,
                    "compliance_pct": round(
                        iso_implemented / len(iso_controls) * 100, 1
                    )
                    if iso_controls
                    else 0,
                    "controls": [
                        {
                            "control_id": c.control_id,
                            "article": c.article,
                            "description": c.description,
                            "status": c.status,
                            "implementation": c.implementation,
                            "evidence": c.evidence,
                        }
                        for c in iso_controls
                    ],
                },
            },
            "summary": {
                "total_controls": len(self._controls),
                "implemented": eu_implemented + iso_implemented,
                "compliance_score": round(
                    (eu_implemented + iso_implemented)
                    / len(self._controls)
                    * 100,
                    1,
                )
                if self._controls
                else 0,
            },
        }

        if risk_assessment:
            report["risk_assessment"] = risk_assessment.to_dict()

        if session_stats:
            report["session_stats"] = session_stats

        return report

    def generate_technical_documentation(
        self,
        transparency: TransparencyDeclaration | None = None,
        risk_assessment: RiskAssessment | None = None,
    ) -> dict[str, Any]:
        """Generate EU AI Act Art. 11 technical documentation.

        Args:
            transparency: Optional transparency declaration to embed.
            risk_assessment: Optional risk assessment to embed.

        Returns:
            Structured documentation dict suitable for submission to
            national competent authorities.
        """
        from crp._version import __version__

        doc = {
            "document_type": "technical_documentation",
            "document_version": "1.0",
            "generated_at": time.time(),
            "system": {
                "name": "Context Relay Protocol (CRP)",
                "version": __version__,
                "provider": "AutoCyber AI Pty Ltd",
                "provider_jurisdiction": "NSW, Australia",
                "license": "Elastic License 2.0",
            },
            "intended_purpose": (
                transparency.intended_purpose
                if transparency
                else "AI context management for LLM applications"
            ),
            "risk_classification": (
                risk_assessment.to_dict()
                if risk_assessment
                else {"risk_level": "minimal", "category": "context_management"}
            ),
            "architecture": {
                "type": "Context management middleware",
                "components": [
                    "Extraction pipeline (6-stage graduated NLP)",
                    "Warm state store (in-memory fact storage)",
                    "Contextual Knowledge Fabric (4-mode retrieval)",
                    "Envelope builder (6-phase context assembly)",
                    "Security layer (12 modules, 8-layer defense)",
                    "Observability layer (audit, events, telemetry, metrics)",
                ],
                "dependencies": {
                    "core": "Zero external dependencies",
                    "optional": "cryptography, blake3, keyring, sentence-transformers",
                },
            },
            "data_governance": {
                "data_classification_levels": 5,
                "pii_detection": "Pattern-based with configurable rules",
                "data_retention": "Configurable per classification level",
                "data_minimization": "Session-scoped, auto-purge on expiry",
                "right_to_erasure": "GDPR Article 17 compliant",
                "consent_management": "Purpose-based with 8 processing purposes",
            },
            "security_measures": {
                "encryption": "AES-256-GCM (NIST SP 800-38D)",
                "key_derivation": "HMAC-SHA256 + HKDF-SHA256 (RFC 5869)",
                "session_binding": "Cryptographic per-session isolation",
                "integrity": "BLAKE3/SHA-256 hash chains with HMAC signing",
                "access_control": "RBAC (OBSERVER/OPERATOR/ADMIN)",
                "input_validation": "Always-on, cannot be disabled",
                "injection_detection": "21 patterns + ML classifiers (advisory)",
                "anti_poisoning": "1-window quarantine with 0.7× confidence penalty",
                "embedding_protection": "SQ8 quantization + XOR salting",
                "audit_trail": "Tamper-evident HMAC-signed compliance logging",
            },
            "human_oversight": {
                "levels": ["NONE", "INFORMED", "APPROVAL", "CONTROL"],
                "configurable_per_operation": True,
                "halt_mechanisms": ["injection_detected", "pii_detected"],
                "autonomous_limits": "Configurable max dispatches",
            },
            "transparency": (
                transparency.to_dict()
                if transparency
                else {"note": "Generate with TransparencyDeclaration"}
            ),
            "compliance_controls": [
                {
                    "control_id": c.control_id,
                    "framework": c.framework,
                    "article": c.article,
                    "description": c.description,
                    "status": c.status,
                }
                for c in self._controls
            ],
        }

        return doc
