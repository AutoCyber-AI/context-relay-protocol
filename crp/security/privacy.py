# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Privacy controls — data classification, PII detection, retention, erasure (§7.12).

Implements:
  - Data sensitivity classification (PUBLIC → CRITICAL)
  - PII detection with configurable patterns
  - Data minimization enforcement
  - Retention policies with automatic expiry
  - Right to erasure (GDPR Article 17 / EU AI Act transparency)
  - Data lineage tracking

EU AI Act: Art. 10 (data governance), Art. 12 (record-keeping), Art. 13 (transparency)
ISO 42001: A.6.2.4 (impact assessment), A.6.2.6 (data management), A.6.2.7 (data subject rights)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger("crp.security.privacy")


# ---------------------------------------------------------------------------
# Data classification levels
# ---------------------------------------------------------------------------


class DataClassification(IntEnum):
    """Data sensitivity classification (§7.12.1).

    Higher values = more sensitive. Controls encryption, retention,
    access requirements, and audit verbosity.
    """

    PUBLIC = 0  # Non-sensitive: documentation, public facts
    INTERNAL = 1  # Internal business context (default for all ingested text)
    CONFIDENTIAL = 2  # Contains business-sensitive information
    RESTRICTED = 3  # Contains PII or regulated data
    CRITICAL = 4  # Contains credentials, secrets, or highly sensitive PII


# Classification → minimum security requirements
_CLASSIFICATION_REQUIREMENTS: dict[DataClassification, dict[str, Any]] = {
    DataClassification.PUBLIC: {
        "encrypt_at_rest": False,
        "max_retention_hours": 0,  # 0 = no limit
        "audit_access": False,
        "require_consent": False,
        "allow_export": True,
    },
    DataClassification.INTERNAL: {
        "encrypt_at_rest": True,
        "max_retention_hours": 720,  # 30 days
        "audit_access": False,
        "require_consent": False,
        "allow_export": True,
    },
    DataClassification.CONFIDENTIAL: {
        "encrypt_at_rest": True,
        "max_retention_hours": 168,  # 7 days
        "audit_access": True,
        "require_consent": False,
        "allow_export": True,
    },
    DataClassification.RESTRICTED: {
        "encrypt_at_rest": True,
        "max_retention_hours": 24,  # 24 hours
        "audit_access": True,
        "require_consent": True,
        "allow_export": False,  # Must be explicitly authorized
    },
    DataClassification.CRITICAL: {
        "encrypt_at_rest": True,
        "max_retention_hours": 1,  # 1 hour — process and discard
        "audit_access": True,
        "require_consent": True,
        "allow_export": False,
    },
}


def classification_requirements(level: DataClassification) -> dict[str, Any]:
    """Return minimum security requirements for a data classification level."""
    return _CLASSIFICATION_REQUIREMENTS[level].copy()


# ---------------------------------------------------------------------------
# PII detection patterns
# ---------------------------------------------------------------------------

# Compiled regex patterns for common PII types.
# These are intentionally conservative (high precision, lower recall)
# to avoid false positives that would degrade user experience.
_PII_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "email",
        "Email address",
        re.compile(
            r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",
        ),
    ),
    (
        "phone_international",
        "International phone number",
        re.compile(
            r"(?<!\d)\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}(?!\d)",
        ),
    ),
    (
        "credit_card",
        "Credit card number",
        re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
            r"[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
        ),
    ),
    (
        "ssn_us",
        "US Social Security Number",
        re.compile(
            r"\b\d{3}[\s\-]\d{2}[\s\-]\d{4}\b",
        ),
    ),
    (
        "ip_address",
        "IP address (v4)",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
        ),
    ),
    (
        "iban",
        "International Bank Account Number",
        re.compile(
            r"\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?(?:[A-Z0-9]{4}[\s]?){2,7}[A-Z0-9]{1,4}\b",
        ),
    ),
    (
        "passport",
        "Passport number pattern",
        re.compile(
            r"\b[A-Z]{1,2}\d{6,9}\b",
        ),
    ),
    (
        "api_key_generic",
        "Generic API key / secret",
        re.compile(
            r"\b(?:sk|pk|api|key|secret|token|bearer)[_\-]"
            r"[a-zA-Z0-9]{20,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "aws_key",
        "AWS access key",
        re.compile(
            r"\bAKIA[0-9A-Z]{16}\b",
        ),
    ),
]


@dataclass
class PIIDetection:
    """Result of PII scan on a piece of text."""

    pii_type: str  # e.g. "email", "credit_card"
    description: str  # Human-readable
    position: int  # Character offset
    length: int  # Length of matched text
    text_hash: str  # SHA-256 hash of matched text (not the text itself)


@dataclass
class PIIScanResult:
    """Aggregate result of PII scanning."""

    detections: list[PIIDetection] = field(default_factory=list)
    scanned_length: int = 0
    scan_time_ms: float = 0.0

    @property
    def has_pii(self) -> bool:
        """Return whether this object has PII."""
        return len(self.detections) > 0

    @property
    def pii_types_found(self) -> set[str]:
        """Return the PII types found."""
        return {d.pii_type for d in self.detections}

    @property
    def highest_classification(self) -> DataClassification:
        """Return the highest data classification implied by detected PII."""
        if not self.detections:
            return DataClassification.INTERNAL
        types = self.pii_types_found
        if types & {"credit_card", "ssn_us", "aws_key", "api_key_generic"}:
            return DataClassification.CRITICAL
        if types & {"iban", "passport"}:
            return DataClassification.RESTRICTED
        if types & {"email", "phone_international", "ip_address"}:
            return DataClassification.CONFIDENTIAL
        return DataClassification.INTERNAL

    def to_dict(self) -> dict[str, Any]:
        """Serialize the PII scan result to a dict."""
        return {
            "has_pii": self.has_pii,
            "detection_count": len(self.detections),
            "pii_types": sorted(self.pii_types_found),
            "highest_classification": self.highest_classification.name,
            "scanned_length": self.scanned_length,
            "scan_time_ms": round(self.scan_time_ms, 2),
        }


class PIIScanner:
    """Detect PII patterns in text (§7.12.2).

    IMPORTANT: This scanner is advisory. It NEVER modifies, redacts, or blocks
    content (Axiom 9 — output integrity). It reports findings for the user
    to act upon.

    Usage::

        scanner = PIIScanner()
        result = scanner.scan("Contact john@example.com for details.")
        if result.has_pii:
            print(f"Found PII: {result.pii_types_found}")
    """

    def __init__(
        self,
        *,
        extra_patterns: list[tuple[str, str, re.Pattern[str]]] | None = None,
        disabled_types: set[str] | None = None,
    ) -> None:
        self._patterns = list(_PII_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)
        self._disabled = disabled_types or set()

    def scan(self, text: str) -> PIIScanResult:
        """Scan text for PII patterns.

        Returns PIIScanResult with detections. Text of matches is NEVER
        stored — only SHA-256 hashes for audit trail purposes.
        """
        t0 = time.monotonic()
        detections: list[PIIDetection] = []

        for pii_type, description, pattern in self._patterns:
            if pii_type in self._disabled:
                continue
            for match in pattern.finditer(text):
                matched_text = match.group()
                detections.append(
                    PIIDetection(
                        pii_type=pii_type,
                        description=description,
                        position=match.start(),
                        length=len(matched_text),
                        # Hash the matched text — NEVER store raw PII
                        text_hash=hashlib.sha256(
                            matched_text.encode("utf-8")
                        ).hexdigest()[:16],
                    )
                )

        elapsed_ms = (time.monotonic() - t0) * 1000

        if detections:
            logger.info(
                "PII scan: %d detections across %d types in %d chars (%.1fms)",
                len(detections),
                len({d.pii_type for d in detections}),
                len(text),
                elapsed_ms,
            )

        return PIIScanResult(
            detections=detections,
            scanned_length=len(text),
            scan_time_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# Data retention policy
# ---------------------------------------------------------------------------


@dataclass
class RetentionPolicy:
    """Data retention policy configuration (§7.12.3).

    Defines how long different classifications of data are retained
    and what happens at expiry.
    """

    default_retention_hours: float = 720.0  # 30 days
    restricted_retention_hours: float = 24.0  # 24 hours
    critical_retention_hours: float = 1.0  # 1 hour
    auto_purge: bool = True  # Automatically delete expired data
    purge_method: str = "zero_fill"  # "zero_fill" or "delete"


@dataclass
class RetentionRecord:
    """Tracks retention status for a piece of data."""

    data_id: str
    classification: DataClassification
    created_at: float
    expires_at: float
    source_label: str = ""
    purged: bool = False
    purged_at: float = 0.0


class RetentionManager:
    """Manages data retention and automatic purging (§7.12.3).

    EU AI Act Art. 12: Record-keeping with defined retention periods.
    ISO 42001 A.6.2.8: Records management with lifecycle tracking.

    Usage::

        rm = RetentionManager()
        rm.register("fact-123", DataClassification.RESTRICTED, "user-input")
        expired = rm.get_expired()  # Returns IDs ready for purging
        rm.mark_purged("fact-123")
    """

    def __init__(self, policy: RetentionPolicy | None = None) -> None:
        self._policy = policy or RetentionPolicy()
        self._records: dict[str, RetentionRecord] = {}

    @property
    def tracked_count(self) -> int:
        """Return the current tracked count."""
        return len(self._records)

    @property
    def active_count(self) -> int:
        """Return the current active count."""
        return sum(1 for r in self._records.values() if not r.purged)

    def _retention_hours(self, classification: DataClassification) -> float:
        """Get retention hours for a classification level."""
        req = _CLASSIFICATION_REQUIREMENTS.get(classification, {})
        max_hours = req.get("max_retention_hours", 0)
        if max_hours > 0:
            return float(max_hours)
        return self._policy.default_retention_hours

    def register(
        self,
        data_id: str,
        classification: DataClassification,
        source_label: str = "",
    ) -> RetentionRecord:
        """Register a data item for retention tracking."""
        now = time.time()
        hours = self._retention_hours(classification)
        expires_at = now + (hours * 3600) if hours > 0 else 0.0

        record = RetentionRecord(
            data_id=data_id,
            classification=classification,
            created_at=now,
            expires_at=expires_at,
            source_label=source_label,
        )
        self._records[data_id] = record
        return record

    def get_expired(self) -> list[str]:
        """Return IDs of all expired, non-purged data items."""
        now = time.time()
        return [
            rid
            for rid, rec in self._records.items()
            if not rec.purged and rec.expires_at > 0 and now > rec.expires_at
        ]

    def mark_purged(self, data_id: str) -> bool:
        """Mark a data item as purged. Returns True if found."""
        rec = self._records.get(data_id)
        if rec is None:
            return False
        rec.purged = True
        rec.purged_at = time.time()
        return True

    def enforce(self) -> list[str]:
        """Run retention enforcement: return IDs of newly expired items.

        The caller is responsible for actually deleting the data.
        This method only identifies what needs purging.
        """
        expired = self.get_expired()
        if expired:
            logger.info(
                "Retention enforcement: %d items expired and pending purge",
                len(expired),
            )
        return expired

    def get_record(self, data_id: str) -> RetentionRecord | None:
        """Get retention record for a data item."""
        return self._records.get(data_id)

    def to_dict(self) -> dict[str, Any]:
        """Export retention state for audit/compliance reporting."""
        return {
            "tracked_count": self.tracked_count,
            "active_count": self.active_count,
            "purged_count": self.tracked_count - self.active_count,
            "policy": {
                "default_retention_hours": self._policy.default_retention_hours,
                "restricted_retention_hours": self._policy.restricted_retention_hours,
                "critical_retention_hours": self._policy.critical_retention_hours,
                "auto_purge": self._policy.auto_purge,
                "purge_method": self._policy.purge_method,
            },
        }


# ---------------------------------------------------------------------------
# Right to erasure (GDPR Article 17)
# ---------------------------------------------------------------------------


@dataclass
class ErasureRequest:
    """Tracks a right-to-erasure (data deletion) request."""

    request_id: str
    requester_hash: str  # SHA-256 hash of requester identifier
    requested_at: float = field(default_factory=time.time)
    scope: str = "session"  # "session" | "all" | "specific_facts"
    target_ids: list[str] = field(default_factory=list)
    completed: bool = False
    completed_at: float = 0.0
    items_erased: int = 0


class ErasureManager:
    """Handles right-to-erasure requests (GDPR Article 17) (§7.12.4).

    Tracks erasure requests, ensures they are fulfilled, and maintains
    an audit trail of what was deleted and when.

    Usage::

        em = ErasureManager()
        req = em.create_request("user-hash-abc", scope="session")
        # ... caller erases the actual data ...
        em.complete_request(req.request_id, items_erased=42)
    """

    def __init__(self) -> None:
        self._requests: dict[str, ErasureRequest] = {}

    def create_request(
        self,
        requester_hash: str,
        scope: str = "session",
        target_ids: list[str] | None = None,
    ) -> ErasureRequest:
        """Create a new erasure request.

        Args:
            requester_hash: SHA-256 hash of the requester's identity.
            scope: "session" (all data in current session),
                   "all" (all data across sessions),
                   "specific_facts" (only listed fact IDs).
            target_ids: Specific fact IDs when scope="specific_facts".

        Returns:
            ErasureRequest with a unique request_id.
        """
        import uuid

        request_id = f"erasure-{uuid.uuid4().hex[:12]}"
        req = ErasureRequest(
            request_id=request_id,
            requester_hash=requester_hash,
            scope=scope,
            target_ids=target_ids or [],
        )
        self._requests[request_id] = req

        logger.info(
            "Erasure request created: %s (scope=%s, targets=%d)",
            request_id,
            scope,
            len(req.target_ids),
        )
        return req

    def complete_request(
        self,
        request_id: str,
        items_erased: int = 0,
    ) -> bool:
        """Mark an erasure request as completed.

        Returns True if request was found and completed.
        """
        req = self._requests.get(request_id)
        if req is None:
            return False
        req.completed = True
        req.completed_at = time.time()
        req.items_erased = items_erased

        logger.info(
            "Erasure request completed: %s (%d items erased in %.1fs)",
            request_id,
            items_erased,
            req.completed_at - req.requested_at,
        )
        return True

    def pending_requests(self) -> list[ErasureRequest]:
        """Return all pending (incomplete) erasure requests."""
        return [r for r in self._requests.values() if not r.completed]

    def to_dict(self) -> dict[str, Any]:
        """Export erasure state for audit/compliance reporting."""
        return {
            "total_requests": len(self._requests),
            "completed": sum(1 for r in self._requests.values() if r.completed),
            "pending": sum(1 for r in self._requests.values() if not r.completed),
            "total_items_erased": sum(
                r.items_erased for r in self._requests.values() if r.completed
            ),
            "requests": [
                {
                    "request_id": r.request_id,
                    "scope": r.scope,
                    "completed": r.completed,
                    "items_erased": r.items_erased,
                    "requested_at": r.requested_at,
                    "completed_at": r.completed_at if r.completed else None,
                }
                for r in self._requests.values()
            ],
        }


# ---------------------------------------------------------------------------
# Data lineage tracking
# ---------------------------------------------------------------------------


@dataclass
class DataLineageEntry:
    """Tracks the origin and transformations of a piece of data."""

    data_id: str
    origin: str  # "ingest", "extraction", "dispatch_output", "share"
    source_label: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    created_at: float = field(default_factory=time.time)
    transformations: list[str] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)


class DataLineageTracker:
    """Track data provenance and transformation history (§7.12.5).

    ISO 42001 A.6.2.6: Data management requires tracking data origin,
    quality, and transformations throughout the AI lifecycle.

    Usage::

        tracker = DataLineageTracker()
        tracker.record("fact-1", "extraction", "user-input", DataClassification.INTERNAL)
        tracker.add_transformation("fact-1", "quarantine_promoted")
    """

    def __init__(self) -> None:
        self._entries: dict[str, DataLineageEntry] = {}

    def record(
        self,
        data_id: str,
        origin: str,
        source_label: str = "",
        classification: DataClassification = DataClassification.INTERNAL,
        parent_ids: list[str] | None = None,
    ) -> DataLineageEntry:
        """Record a new data lineage entry."""
        entry = DataLineageEntry(
            data_id=data_id,
            origin=origin,
            source_label=source_label,
            classification=classification,
            parent_ids=parent_ids or [],
        )
        self._entries[data_id] = entry
        return entry

    def add_transformation(self, data_id: str, transformation: str) -> bool:
        """Record a transformation applied to data. Returns True if found."""
        entry = self._entries.get(data_id)
        if entry is None:
            return False
        entry.transformations.append(transformation)
        return True

    def reclassify(
        self, data_id: str, new_classification: DataClassification
    ) -> bool:
        """Update classification level for a data item. Returns True if found."""
        entry = self._entries.get(data_id)
        if entry is None:
            return False
        old = entry.classification
        entry.classification = new_classification
        entry.transformations.append(
            f"reclassified:{old.name}->{new_classification.name}"
        )
        return True

    def get_lineage(self, data_id: str) -> DataLineageEntry | None:
        """Get lineage entry for a data item."""
        return self._entries.get(data_id)

    def get_by_classification(
        self, level: DataClassification
    ) -> list[DataLineageEntry]:
        """Get all entries at or above a classification level."""
        return [e for e in self._entries.values() if e.classification >= level]

    def to_dict(self) -> dict[str, Any]:
        """Export lineage state for audit/compliance reporting."""
        by_class = {}
        for entry in self._entries.values():
            name = entry.classification.name
            by_class[name] = by_class.get(name, 0) + 1

        return {
            "total_tracked": len(self._entries),
            "by_classification": by_class,
            "by_origin": self._count_by_field("origin"),
        }

    def _count_by_field(self, field_name: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._entries.values():
            val = getattr(entry, field_name, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts
