# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP HTTP header-name constants (CRP-SPEC-002).

Single source of truth for every ``CRP-*`` header name emitted or parsed by
the protocol surface.  Grouped by namespace.  The ten provisional IANA
registrations are flagged in :data:`IANA_PRIORITY`.

All names are canonical (Title-Case, hyphenated) per RFC 9110 §5.1.  HTTP
header names are case-insensitive, but emitting canonical casing keeps the
wire format tidy and audit-friendly.
"""

from __future__ import annotations

# ── CRP-Context-* — envelope / session state ──────────────────────────────
CONTEXT_PROTOCOL_VERSION = "CRP-Context-Protocol-Version"
CONTEXT_SESSION_ID = "CRP-Context-Session-Id"
CONTEXT_WINDOW = "CRP-Context-Window"
CONTEXT_QUALITY_TIER = "CRP-Context-Quality-Tier"
CONTEXT_SATURATION = "CRP-Context-Saturation"
CONTEXT_FACTS_USED = "CRP-Context-Facts-Used"
CONTEXT_TOKENS_USED = "CRP-Context-Tokens-Used"
CONTEXT_STRATEGY = "CRP-Context-Strategy"
CONTEXT_ETAG = "CRP-Context-ETag"
CONTEXT_IF_MATCH = "CRP-Context-If-Match"
CONTEXT_CACHE = "CRP-Context-Cache"
CONTEXT_CACHE_STATUS = "CRP-Context-Cache-Status"
CONTEXT_MODE = "CRP-Context-Mode"
CONTEXT_MODE_TRANSITION = "CRP-Context-Mode-Transition"
CONTEXT_COVERAGE = "CRP-Context-Coverage"
CONTEXT_CONTINUATION_ID = "CRP-Context-Continuation-Id"  # §4.12 (BOTH directions)

# ── CRP-Safety-* — DPE risk surface + policy enforcement ──────────────────
SAFETY_HALLUCINATION_RISK = "CRP-Safety-Hallucination-Risk"
SAFETY_HALLUCINATION_SCORE = "CRP-Safety-Hallucination-Score"
SAFETY_ATTRIBUTION = "CRP-Safety-Attribution"
SAFETY_GROUNDING_PCT = "CRP-Safety-Grounding-Pct"
SAFETY_FABRICATIONS = "CRP-Safety-Fabrications"
SAFETY_DISTORTIONS = "CRP-Safety-Distortions"
SAFETY_CONTRADICTIONS = "CRP-Safety-Contradictions"
SAFETY_OMISSIONS = "CRP-Safety-Omissions"
SAFETY_ENTAILMENT_SCORE = "CRP-Safety-Entailment-Score"
SAFETY_OVERSIGHT_MODE = "CRP-Safety-Oversight-Mode"
SAFETY_RETRY_AFTER = "CRP-Safety-Retry-After"
SAFETY_POLICY = "CRP-Safety-Policy"
SAFETY_POLICY_REPORT_ONLY = "CRP-Safety-Policy-Report-Only"
SAFETY_POLICY_APPLIED = "CRP-Safety-Policy-Applied"
SAFETY_POLICY_VIOLATION = "CRP-Safety-Policy-Violation"
SAFETY_POLICY_ADJUSTMENT = "CRP-Safety-Policy-Adjustment"
SAFETY_MODE = "CRP-Safety-Mode"
SAFETY_NONCE = "CRP-Safety-Nonce"
SAFETY_REPORT_URI = "CRP-Safety-Report-URI"  # §5.13 (request side)
SAFETY_PREVENTIVE_HALT = "CRP-Safety-Preventive-Halt"

# ── CRP-Provenance-* — HMAC chain / DPE report ────────────────────────────
PROVENANCE_HMAC = "CRP-Provenance-HMAC"
PROVENANCE_WINDOW_HMAC = "CRP-Provenance-Window-HMAC"
PROVENANCE_CHAIN_INTEGRITY = "CRP-Provenance-Chain-Integrity"
PROVENANCE_CLAIM_COUNT = "CRP-Provenance-Claim-Count"
PROVENANCE_ATTRIBUTION_SCORE = "CRP-Provenance-Attribution-Score"
PROVENANCE_FIDELITY_SCORE = "CRP-Provenance-Fidelity-Score"
PROVENANCE_DAG_ROOT = "CRP-Provenance-DAG-Root"
PROVENANCE_WINDOW_LINEAGE = "CRP-Provenance-Window-Lineage"
PROVENANCE_REPORT_URI = "CRP-Provenance-Report-URI"

# ── CRP-Compliance-* — regulatory classification ──────────────────────────
COMPLIANCE_EU_AI_ACT = "CRP-Compliance-EU-AI-Act"
COMPLIANCE_NIST_TIER = "CRP-Compliance-NIST-Tier"
COMPLIANCE_ISO_42001 = "CRP-Compliance-ISO-42001"
COMPLIANCE_GDPR_PII = "CRP-Compliance-GDPR-PII"
COMPLIANCE_CONTROLS_MET = "CRP-Compliance-Controls-Met"
COMPLIANCE_AUDIT_TRAIL_ID = "CRP-Compliance-Audit-Trail-Id"
COMPLIANCE_AUDIT_TRAIL_URI = "CRP-Compliance-Audit-Trail-URI"
COMPLIANCE_DATA_RESIDENCY = "CRP-Compliance-Data-Residency"

# ── CRP-Agent-* — multi-agent / dispatch ──────────────────────────────────
AGENT_PHASE = "CRP-Agent-Phase"
AGENT_LOOP_DEPTH = "CRP-Agent-Loop-Depth"
AGENT_SAFETY_BUDGET = "CRP-Agent-Safety-Budget"
AGENT_TOOL_CALLS = "CRP-Agent-Tool-Calls"
AGENT_SESSION_PARENT = "CRP-Agent-Session-Parent"
AGENT_DISPATCH_STRATEGY = "CRP-Agent-Dispatch-Strategy"
AGENT_REVISION_ROUND = "CRP-Agent-Revision-Round"
AGENT_SAFETY_BUDGET_WARNING = "CRP-Safety-Budget-Warning"
AGENT_CAPABILITY_PROFILE = "CRP-Agent-Capability-Profile"
AGENT_OPERATION_STATE = "CRP-Agent-Operation-State"
AGENT_OPERATION_TYPE = "CRP-Agent-Operation-Type"
AGENT_OPERATION_PLAN = "CRP-Agent-Operation-Plan"
AGENT_EXECUTION_MODE = "CRP-Agent-Execution-Mode"
OVERSIGHT_TOKEN = "CRP-Oversight-Token"

# ── CRP-Memory-* — CKF retrieval telemetry ────────────────────────────────
MEMORY_TIER_HIT = "CRP-Memory-Tier-Hit"
MEMORY_CKF_HITS = "CRP-Memory-CKF-Hits"
MEMORY_CKF_COMMUNITY = "CRP-Memory-CKF-Community"
MEMORY_KNOWLEDGE_AGE = "CRP-Memory-Knowledge-Age"

# ── CRP-Quality-* — RQA (NEW v3.0) ────────────────────────────────────────
QUALITY_REPETITION = "CRP-Quality-Repetition"
QUALITY_COMPLETENESS = "CRP-Quality-Completeness"
QUALITY_FLOW = "CRP-Quality-Flow"
QUALITY_SCORE = "CRP-Quality-Score"

# ── CRP-Activation-* / CRP-Onboarding-* — progressive activation (SPEC-017)
ACTIVATION_STATUS = "CRP-Activation-Status"
ACTIVATION_FEATURES = "CRP-Activation-Features"
ONBOARDING_ACTIVE = "CRP-Onboarding-Active"
ONBOARDING_DAYS_REMAINING = "CRP-Onboarding-Days-Remaining"
ONBOARDING_NEXT_ACTION = "CRP-Onboarding-Next-Action"
ONBOARDING_HINT = "CRP-Onboarding-Hint"

# ── Session token relay (SPEC-007) ────────────────────────────────────────
SET_SESSION = "CRP-Set-Session"
SESSION_TOKEN = "CRP-Session-Token"
SESSION_ACTION = "CRP-Session-Action"

# ── Inbound client preference headers (request side) ──────────────────────
ACCEPT_QUALITY = "CRP-Accept-Quality"
ACCEPT_STRATEGY = "CRP-Accept-Strategy"
ACCEPT_RISK = "CRP-Accept-Risk"
LLM_GROUNDING_MODE = "CRP-LLM-Grounding-Mode"
LLM_REPRODUCIBILITY_SEED = "CRP-LLM-Reproducibility-Seed"
LLM_STRUCTURED_OUTPUT_MODE = "CRP-LLM-Structured-Output-Mode"
LLM_STRUCTURED_OUTPUT_SCHEMA = "CRP-LLM-Structured-Output-Schema"
LLM_PROMPT_CACHE_HINT = "CRP-LLM-Prompt-Cache-Hint"
STRUCTURED_OUTPUT_CONTRACT = "CRP-Structured-Output-Contract"

# ── CRP-Tool-* — capability fabric (SPEC-050) ─────────────────────────────
TOOL_POSITIONING_FRAME = "CRP-Tool-Positioning-Frame"
TOOL_OBSERVATION_COUNT = "CRP-Tool-Observation-Count"
TOOL_ALLOWLIST = "CRP-Tool-Allowlist"
TOOL_BLOCKLIST = "CRP-Tool-Blocklist"


# ── Provisional IANA registrations (10) ───────────────────────────────────
IANA_PRIORITY: tuple[str, ...] = (
    SAFETY_HALLUCINATION_RISK,
    SAFETY_GROUNDING_PCT,
    SAFETY_POLICY,
    PROVENANCE_HMAC,
    PROVENANCE_CHAIN_INTEGRITY,
    COMPLIANCE_EU_AI_ACT,
    COMPLIANCE_GDPR_PII,
    CONTEXT_QUALITY_TIER,
    CONTEXT_SESSION_ID,
    SESSION_TOKEN,
)

#: Header-name prefix shared by every CRP header.  Used by the Axiom-4
#: stripping filter to guarantee no governance header reaches the LLM.
CRP_PREFIX = "CRP-"


def is_crp_header(name: str) -> bool:
    """Return ``True`` if *name* is a CRP protocol header (case-insensitive)."""
    return name.upper().startswith(CRP_PREFIX.upper())
