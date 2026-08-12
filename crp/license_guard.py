# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""
License enforcement guard for CRP™ — Context Relay Protocol.

This module implements CODE-LEVEL IP protections that complement the
Elastic License 2.0 (ELv2) legal protections.  It MUST NOT be removed,
modified, or bypassed.  Doing so constitutes a violation of the license.

Enforcement levels (graduated):
  BLOCK   — Hard stop (raises CRPError).  Managed-service usage without
            a commercial license is prohibited under ELv2 §2.
  DEGRADE — Feature degradation.  If license headers are tampered with,
            advanced features (Stage 3+, CKF graph retrieval, continuation)
            are disabled for the session.
  WARN    — Advisory warning logged and emitted.  Informational only.

Protections:
  1. Runtime license header verification on core modules
  2. Managed-service usage detection & blocking (§ELv2 Limitation)
  3. Attribution verification (copyright notices must be preserved)
  4. Module integrity fingerprint validation
  5. Output watermarking with license metadata
  6. Violation telemetry (local logging only — no phone-home)
  7. Fork/clone provenance binding — origin verification
  8. Code-signature chain —  tamper-evident module registry
  9. Redistribution detection — package metadata binding
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LICENSE_MARKER = "Licensed under Elastic License 2.0"
_COPYRIGHT_MARKER = "Constantinos Vidiniotis"
_LICENSOR = "Constantinos Vidiniotis / AutoCyber AI Pty Ltd"
_LICENSE_URL = "https://crprotocol.io"
_ABN = "22 697 087 166"
_PRODUCT = "Context Relay Protocol (CRP)™"

# Core modules that MUST retain license headers
_CORE_MODULES = [
    "crp.core.orchestrator",
    "crp.core.dispatch_router",
    "crp.core.session",
    "crp.core.config",
    "crp.envelope.builder",
    "crp.extraction.pipeline",
    "crp.continuation.manager",
    "crp.ckf.fabric",
    "crp.security.integrity",
]

# Environment variables that indicate managed-service deployment
_MANAGED_SERVICE_INDICATORS = [
    "CRP_MANAGED_SERVICE",     # Explicit flag
    "CRP_MULTI_TENANT",        # Multi-tenant mode
    "CRP_SAAS_MODE",           # SaaS deployment
]

# Infrastructure indicators that strongly suggest managed-service
_INFRA_INDICATORS = [
    "KUBERNETES_SERVICE_HOST",  # Running in k8s
    "ECS_CONTAINER_METADATA_URI",  # AWS ECS
    "GAE_APPLICATION",          # Google App Engine
    "WEBSITE_INSTANCE_ID",      # Azure App Service
]


# ---------------------------------------------------------------------------
# Enforcement state
# ---------------------------------------------------------------------------

@dataclass
class _EnforcementState:
    """Tracks the enforcement state for the current session."""
    managed_service_blocked: bool = False
    tamper_detected: bool = False
    tampered_modules: list[str] = field(default_factory=list)
    features_degraded: bool = False
    violation_count: int = 0
    checked_at: float = 0.0
    commercial_license: bool = False


_state = _EnforcementState()


# ---------------------------------------------------------------------------
# Commercial license bypass
# ---------------------------------------------------------------------------

def _check_commercial_license() -> bool:
    """Check if a valid commercial license key is present.

    Commercial license holders set CRP_LICENSE_KEY to their key.
    This bypasses managed-service restrictions (but NOT header tampering).
    """
    key = os.environ.get("CRP_LICENSE_KEY", "").strip()
    if not key:
        return False
    # Commercial keys are 64-char hex strings with a known prefix
    if len(key) >= 64 and key[:4] == "CRP-":
        # Validate key format: CRP-<60 hex chars>
        try:
            int(key[4:], 16)
            logger.info("Commercial license key detected — managed-service restriction lifted")
            return True
        except ValueError:
            pass
    logger.warning("Invalid CRP_LICENSE_KEY format — commercial license not recognized")
    return False


# ---------------------------------------------------------------------------
# License verification (DEGRADE on failure)
# ---------------------------------------------------------------------------

def verify_license_headers() -> list[str]:
    """Verify that core modules retain their license headers.

    Returns a list of modules with missing/modified headers.
    If any are found, sets _state.tamper_detected = True and
    triggers feature degradation.
    """
    violations: list[str] = []
    for mod_name in _CORE_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            source_file = getattr(mod, "__file__", None)
            if source_file and os.path.isfile(source_file):
                with open(source_file, encoding="utf-8", errors="ignore") as f:
                    header = f.read(500)
                if _LICENSE_MARKER not in header or _COPYRIGHT_MARKER not in header:
                    violations.append(mod_name)
        except (ImportError, OSError):
            pass

    if violations:
        _state.tamper_detected = True
        _state.tampered_modules = violations
        _state.features_degraded = True
        _state.violation_count += len(violations)

        for mod_name in violations:
            logger.error(
                "LICENSE VIOLATION: License header removed or modified in %s. "
                "This software is protected by copyright and Elastic License 2.0. "
                "Removing license headers is a violation of the license and "
                "applicable copyright law. "
                "Advanced features have been DISABLED for this session.",
                mod_name,
            )

        warnings.warn(
            f"CRP™ license headers modified in {len(violations)} module(s): "
            f"{', '.join(violations)}. "
            f"Advanced features (Stage 3+ extraction, CKF graph retrieval, "
            f"continuation beyond 3 windows) have been DISABLED. "
            f"Restore original license headers to re-enable full functionality. "
            f"License: Elastic License 2.0 | Licensor: {_LICENSOR}",
            UserWarning,
            stacklevel=2,
        )

        _log_violation("license_header_tamper", {
            "modules": violations,
            "degraded": True,
        })

    return violations


# ---------------------------------------------------------------------------
# Managed-service detection (BLOCK on detection)
# ---------------------------------------------------------------------------

def check_managed_service_restriction() -> bool:
    """Check if CRP is being deployed as a managed service.

    Under the Elastic License 2.0 §2, providing the functionality
    of CRP to third parties as a managed service is PROHIBITED
    without a commercial license from the Licensor.

    This function BLOCKS (raises CRPError) if managed-service indicators
    are detected AND no commercial license key is present.

    Returns True if managed-service indicators are detected (blocked or licensed).
    """
    if _state.commercial_license:
        return False

    detected_indicators: list[str] = []
    for env_var in _MANAGED_SERVICE_INDICATORS:
        val = os.environ.get(env_var)
        if val and val.lower() not in ("0", "false", "no"):
            detected_indicators.append(env_var)

    infra_signals: list[str] = []
    for env_var in _INFRA_INDICATORS:
        if os.environ.get(env_var):
            infra_signals.append(env_var)

    if not detected_indicators:
        if infra_signals:
            logger.info(
                "CRP running in cloud infrastructure (%s). If this is a "
                "managed service offering, set CRP_LICENSE_KEY or contact "
                "contact@crprotocol.io for a commercial license.",
                ", ".join(infra_signals),
            )
        return False

    # Managed-service explicitly flagged — BLOCK
    _state.managed_service_blocked = True
    _state.violation_count += 1

    _log_violation("managed_service_blocked", {
        "indicators": detected_indicators,
        "infra_signals": infra_signals,
    })

    from crp.core.errors import CRPError, ErrorCode

    raise CRPError(
        code=ErrorCode.SECURITY_INVARIANT_ERROR,
        message=(
            f"CRP™ MANAGED SERVICE VIOLATION — Elastic License 2.0 §2\n"
            f"\n"
            f"Providing the functionality of CRP to third parties as a managed "
            f"service is PROHIBITED without a commercial license.\n"
            f"\n"
            f"Detected indicators: {', '.join(detected_indicators)}\n"
            f"\n"
            f"To resolve:\n"
            f"  1. Obtain a commercial license: contact@crprotocol.io\n"
            f"  2. Set CRP_LICENSE_KEY=<your-key> in environment\n"
            f"  3. Or remove the managed-service flags if this is self-hosted use\n"
            f"\n"
            f"Licensor: {_LICENSOR} | ABN: {_ABN}\n"
            f"Website: {_LICENSE_URL}"
        ),
        details={
            "violation_type": "managed_service",
            "indicators": detected_indicators,
            "license": "Elastic License 2.0",
            "contact": "contact@crprotocol.io",
        },
    )


# ---------------------------------------------------------------------------
# Feature gate — enforcement point for degraded mode
# ---------------------------------------------------------------------------

def is_feature_allowed(feature: str) -> bool:
    """Check if a feature is allowed under current enforcement state.

    When license headers have been tampered with, advanced features are
    disabled.  This function is called at feature entry points.

    Features gated:
        - "stage_3": GLiNER extraction
        - "stage_4": UIE relation extraction
        - "stage_5": Discourse extraction
        - "stage_6": LLM-assisted extraction
        - "ckf_graph": CKF graph-aware retrieval
        - "continuation_extended": Continuation beyond 3 windows
        - "cross_encoder": Cross-encoder reranking
    """
    if not _state.features_degraded:
        return True

    _ALLOWED_IN_DEGRADED = {"stage_1", "stage_2", "basic_dispatch"}
    if feature in _ALLOWED_IN_DEGRADED:
        return True

    logger.warning(
        "Feature '%s' BLOCKED — license headers have been tampered with. "
        "Restore original license headers to re-enable. "
        "License: Elastic License 2.0 | Licensor: %s",
        feature, _LICENSOR,
    )
    return False


# ---------------------------------------------------------------------------
# Output watermarking
# ---------------------------------------------------------------------------

def watermark_output(output: str, session_id: str = "") -> str:
    """Embed a license watermark in CRP output.

    The watermark is a minimal metadata comment appended to the output.
    It identifies this output as produced by CRP under the Elastic
    License 2.0.

    Watermarking can be disabled by setting the environment variable
    ``CRP_DISABLE_WATERMARK=1`` (used by the test suite to assert exact
    provider outputs).
    """
    if not output or not output.strip():
        return output

    if os.environ.get("CRP_DISABLE_WATERMARK", "").lower() in {"1", "true", "yes"}:
        return output

    content_hash = hashlib.sha256(output.encode("utf-8")).hexdigest()[:12]
    ts = int(time.time())

    watermark = (
        f"\n<!-- CRP™ | ELv2 | {_LICENSOR} | "
        f"h:{content_hash} | t:{ts} -->"
    )

    return output + watermark


# ---------------------------------------------------------------------------
# Module integrity fingerprinting
# ---------------------------------------------------------------------------

def compute_module_fingerprint(module_name: str) -> str | None:
    """Compute SHA-256 fingerprint of a module's source file."""
    try:
        mod = importlib.import_module(module_name)
        source_file = getattr(mod, "__file__", None)
        if source_file and os.path.isfile(source_file):
            with open(source_file, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    except (ImportError, OSError):
        pass
    return None


def get_module_fingerprints() -> dict[str, str | None]:
    """Compute fingerprints for all core modules."""
    return {mod: compute_module_fingerprint(mod) for mod in _CORE_MODULES}


# ---------------------------------------------------------------------------
# Provenance binding — detects unauthorized redistribution
# ---------------------------------------------------------------------------

# Canonical package metadata that MUST match.  If someone forks the repo,
# renames the package, and publishes it — this check fires.
_CANONICAL_PACKAGE = "crp"
_CANONICAL_AUTHOR = "Constantinos Vidiniotis"
_CANONICAL_REPO = "Constantinos-uni/context-relay-protocol"

def verify_package_provenance() -> list[str]:
    """Verify that the installed package matches canonical provenance.

    Catches:
      - Renamed forks published to PyPI under a different name
      - Vendored copies with altered metadata
      - pip-installed copies with stripped attribution

    Returns list of provenance violations (empty = clean).
    """
    violations: list[str] = []

    # 1. Check importlib.metadata (pip-installed copy)
    try:
        from importlib.metadata import metadata as _pkg_metadata
        meta = _pkg_metadata(_CANONICAL_PACKAGE)
        author = meta.get("Author", "") or ""
        author_email = meta.get("Author-email", "") or ""
        pkg_license = meta.get("License", "") or ""
        home_page = meta.get("Home-page", "") or meta.get("Project-URL", "") or ""

        if _CANONICAL_AUTHOR.lower() not in author.lower() and \
           _CANONICAL_AUTHOR.lower() not in author_email.lower():
            violations.append(
                f"package_author_mismatch: expected '{_CANONICAL_AUTHOR}', "
                f"got '{author}' / '{author_email}'"
            )

        if "elastic" not in pkg_license.lower() and "elv2" not in pkg_license.lower():
            if pkg_license and "unknown" not in pkg_license.lower():
                violations.append(
                    f"package_license_mismatch: expected ELv2, got '{pkg_license}'"
                )
    except Exception:
        # Not installed via pip (dev mode / editable) — skip
        pass

    # 2. Check that the package wasn't cloned and re-branded
    try:
        from crp._version import __version__ as _ver
        # The version module MUST exist and contain our version string
        if not _ver or not isinstance(_ver, str):
            violations.append("version_missing: crp._version.__version__ is empty")
    except ImportError:
        violations.append("version_module_missing: crp._version not found")

    # 3. Verify this module itself hasn't been hollowed out
    # (attacker keeps the file but guts the enforcement logic)
    _self_markers = [
        "_startup_check",
        "verify_license_headers",
        "check_managed_service_restriction",
        "_CANONICAL_PACKAGE",
        "_log_violation",
    ]
    try:
        with open(__file__, encoding="utf-8", errors="ignore") as f:
            self_source = f.read()
        for marker in _self_markers:
            if marker not in self_source:
                violations.append(f"self_tamper: '{marker}' removed from license_guard.py")
    except OSError:
        violations.append("self_tamper: cannot read license_guard.py source")

    if violations:
        _state.tamper_detected = True
        _state.violation_count += len(violations)
        _log_violation("provenance_violation", {"violations": violations})

        for v in violations:
            logger.error(
                "PROVENANCE VIOLATION: %s — This software is the intellectual "
                "property of %s, protected by copyright and Elastic License 2.0. "
                "Unauthorized redistribution is prohibited.",
                v, _LICENSOR,
            )

    return violations


# ---------------------------------------------------------------------------
# Fork/clone origin binding
# ---------------------------------------------------------------------------

def verify_origin_binding() -> list[str]:
    """Check if the code is running from an authorized origin.

    Detects:
      - Git remote pointing to a non-canonical repository (fork/clone theft)
      - Missing .git directory (source archive redistribution)
      - Modified origin URL (repo transferred/stolen)

    This is ADVISORY — does not block, only logs.  Forks for personal
    study/modification are permitted under ELv2, but redistribution as
    a managed service is not.
    """
    warnings_list: list[str] = []

    try:
        import subprocess
        # Find the repo root relative to this file
        repo_root = Path(__file__).resolve().parent.parent
        git_dir = repo_root / ".git"

        if not git_dir.is_dir():
            # Not a git repo — could be a pip install or archive extraction
            # This is fine for end-users, but we log it
            return warnings_list

        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            origin = result.stdout.strip().lower()
            canonical_lower = _CANONICAL_REPO.lower()
            if canonical_lower not in origin and "context-relay-protocol" not in origin:
                warnings_list.append(
                    f"non_canonical_origin: git remote is '{origin}', "
                    f"expected '{_CANONICAL_REPO}'"
                )
                _log_violation("fork_detection", {
                    "origin": origin,
                    "expected": _CANONICAL_REPO,
                })
                logger.warning(
                    "CRP™ fork detected — origin '%s' does not match canonical "
                    "repository '%s'. If you are redistributing CRP as a "
                    "managed service, you MUST obtain a commercial license. "
                    "Contact: contact@crprotocol.io",
                    origin, _CANONICAL_REPO,
                )
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return warnings_list


# ---------------------------------------------------------------------------
# Code-signature chain — tamper-evident module registry
# ---------------------------------------------------------------------------

def build_integrity_manifest() -> dict[str, Any]:
    """Build a tamper-evident manifest of all core CRP modules.

    Returns a dict mapping module names to their SHA-256 fingerprints
    plus a combined chain hash.  If any module is modified, the chain
    hash changes — making it trivially detectable.
    """
    fingerprints = get_module_fingerprints()
    # Build a deterministic chain: sort by module name, hash the concatenation
    chain_input = "|".join(
        f"{mod}:{fp}" for mod, fp in sorted(fingerprints.items()) if fp
    )
    chain_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    return {
        "version": _PRODUCT,
        "generated_at": time.time(),
        "modules": fingerprints,
        "chain_hash": chain_hash,
        "licensor": _LICENSOR,
    }


def verify_integrity_manifest(manifest: dict[str, Any]) -> list[str]:
    """Verify a previously-built integrity manifest against current state.

    Returns list of modules whose fingerprints have changed.
    """
    current = get_module_fingerprints()
    changes: list[str] = []

    stored = manifest.get("modules", {})
    for mod, stored_fp in stored.items():
        current_fp = current.get(mod)
        if stored_fp and current_fp and stored_fp != current_fp:
            changes.append(mod)

    if changes:
        _log_violation("integrity_manifest_mismatch", {
            "changed_modules": changes,
            "stored_chain": manifest.get("chain_hash"),
        })

    return changes


# ---------------------------------------------------------------------------
# Anti-stripping protection
# ---------------------------------------------------------------------------

def verify_guard_integrity() -> bool:
    """Verify that this license guard module has not been gutted/stubbed.

    Attackers may replace license_guard.py with a stub that passes all
    checks.  This function verifies the module's own source has a minimum
    complexity threshold (line count > 200, size > 5KB), contains required
    enforcement function names, and the startup check is wired.
    """
    try:
        with open(__file__, "rb") as f:
            source = f.read()

        # Minimum size check — a gutted stub would be much smaller
        if len(source) < 5000:
            _state.tamper_detected = True
            _log_violation("guard_stripped", {"size": len(source)})
            return False

        source_text = source.decode("utf-8", errors="ignore")

        # Must contain all enforcement functions
        required = [
            "def verify_license_headers",
            "def check_managed_service_restriction",
            "def is_feature_allowed",
            "def watermark_output",
            "def _startup_check",
            "def _log_violation",
            "CRPError",
            "_CORE_MODULES",
        ]
        for req in required:
            if req not in source_text:
                _state.tamper_detected = True
                _log_violation("guard_gutted", {"missing": req})
                return False

        # Line count check
        line_count = source_text.count("\n")
        if line_count < 200:
            _state.tamper_detected = True
            _log_violation("guard_truncated", {"lines": line_count})
            return False

        return True
    except OSError:
        _state.tamper_detected = True
        return False

def get_license_info() -> dict[str, Any]:
    """Return machine-readable license metadata for this installation."""
    return {
        "license": "Elastic License 2.0 (ELv2)",
        "licensor": _LICENSOR,
        "abn": _ABN,
        "product": _PRODUCT,
        "url": _LICENSE_URL,
        "contact": "contact@crprotocol.io",
        "security": "security@crprotocol.io",
        "restriction": "May not be provided as a managed service without commercial license",
        "enforcement": {
            "tamper_detected": _state.tamper_detected,
            "features_degraded": _state.features_degraded,
            "violation_count": _state.violation_count,
            "commercial_license": _state.commercial_license,
        },
    }


# ---------------------------------------------------------------------------
# Violation telemetry (LOCAL ONLY — no network calls)
# ---------------------------------------------------------------------------

def _log_violation(violation_type: str, details: dict[str, Any]) -> None:
    """Log a license violation to the local telemetry file.

    No network calls. All data stays on the local filesystem.
    Violations are logged to ~/.crp/violations.jsonl for audit.
    """
    entry = {
        "timestamp": time.time(),
        "type": violation_type,
        "product": _PRODUCT,
        "licensor": _LICENSOR,
        **details,
    }

    try:
        violations_dir = Path.home() / ".crp"
        violations_dir.mkdir(exist_ok=True)
        violations_file = violations_dir / "violations.jsonl"
        with open(violations_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    logger.warning("License violation logged: %s — %s", violation_type, details)


# ---------------------------------------------------------------------------
# Startup check (ENFORCED — runs on first import of crp)
# ---------------------------------------------------------------------------

def _startup_check() -> None:
    """Run license enforcement checks at import time.

    Order:
    1. Check for commercial license key
    2. Block managed-service usage (raises CRPError if detected)
    3. Verify license headers (degrades features if tampered)
    4. Verify package provenance (detects renamed forks)
    5. Verify guard integrity (detects stubbed-out guard)
    6. Check origin binding (advisory — logs non-canonical forks)
    """
    _state.checked_at = time.time()

    # 1. Commercial license
    _state.commercial_license = _check_commercial_license()

    # 2. Managed-service restriction (BLOCKS if violated)
    check_managed_service_restriction()

    # 3. License header verification (DEGRADES if violated)
    violations = verify_license_headers()
    if violations:
        logger.error(
            "LICENSE ENFORCEMENT: %d core module(s) have tampered headers. "
            "Advanced features DISABLED. Modules: %s",
            len(violations),
            ", ".join(violations),
        )

    # 4. Package provenance (DEGRADES if violated)
    prov_violations = verify_package_provenance()
    if prov_violations:
        _state.features_degraded = True
        logger.error(
            "PROVENANCE ENFORCEMENT: Package provenance check failed — %d violation(s). "
            "Advanced features DISABLED.",
            len(prov_violations),
        )

    # 5. Guard integrity (DEGRADES if violated)
    if not verify_guard_integrity():
        _state.features_degraded = True
        logger.error(
            "GUARD INTEGRITY: license_guard.py appears to have been "
            "stripped or gutted. Advanced features DISABLED."
        )

    # 6. Origin binding (advisory only — logs warnings)
    verify_origin_binding()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "verify_license_headers",
    "check_managed_service_restriction",
    "is_feature_allowed",
    "watermark_output",
    "get_license_info",
    "get_module_fingerprints",
    "compute_module_fingerprint",
    "verify_package_provenance",
    "verify_origin_binding",
    "build_integrity_manifest",
    "verify_integrity_manifest",
    "verify_guard_integrity",
]
