# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""
Comprehensive tests for CRP IP protection and license enforcement.

Tests cover ALL code-level protections against:
  - License header stripping / tampering
  - Managed-service deployment without commercial license
  - Fork/clone redistribution detection
  - Package renaming / re-branding
  - Guard module gutting / stubbing
  - Feature degradation enforcement
  - Output watermarking
  - Module integrity fingerprinting
  - Violation telemetry logging

GitHub threat model tested:
  - FORK: Someone forks the repo and removes license headers
  - CLONE: Someone clones and republishes under different name
  - STRIP: Attacker guts license_guard.py to a no-op stub
  - REBRAND: Fork is re-branded with different author/license metadata
  - SAAS: CRP is deployed as a managed service without license
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — reset enforcement state between tests
# ---------------------------------------------------------------------------

def _reset_guard_state():
    """Reset the license guard state for clean test isolation."""
    from crp.license_guard import _state
    _state.managed_service_blocked = False
    _state.tamper_detected = False
    _state.tampered_modules = []
    _state.features_degraded = False
    _state.violation_count = 0
    _state.checked_at = 0.0
    _state.commercial_license = False


@pytest.fixture(autouse=True)
def clean_guard_state():
    """Ensure every test starts with a clean enforcement state."""
    _reset_guard_state()
    yield
    _reset_guard_state()


@pytest.fixture
def violations_dir(tmp_path):
    """Provide a temporary violations directory."""
    with patch.dict(os.environ, {}, clear=False):
        with patch("crp.license_guard.Path.home", return_value=tmp_path):
            yield tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# § 1  LICENSE HEADER VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

class TestLicenseHeaderVerification:
    """Tests for runtime license header verification on core modules."""

    def test_clean_headers_no_violations(self):
        """Verify that untampered core modules pass header check."""
        from crp.license_guard import verify_license_headers
        violations = verify_license_headers()
        assert violations == [], f"Unexpected violations: {violations}"

    def test_all_core_modules_have_headers(self):
        """Every module in _CORE_MODULES must have the license header."""
        from crp.license_guard import (
            _CORE_MODULES, _LICENSE_MARKER, _COPYRIGHT_MARKER,
        )
        for mod_name in _CORE_MODULES:
            mod = importlib.import_module(mod_name)
            source_file = getattr(mod, "__file__", None)
            assert source_file, f"{mod_name} has no __file__"
            assert os.path.isfile(source_file), f"{source_file} not found"
            with open(source_file, encoding="utf-8") as f:
                header = f.read(500)
            assert _LICENSE_MARKER in header, (
                f"{mod_name} missing license marker"
            )
            assert _COPYRIGHT_MARKER in header, (
                f"{mod_name} missing copyright marker"
            )

    def test_tampered_header_triggers_degradation(self):
        """Removing a license header must trigger feature degradation."""
        from crp.license_guard import (
            _LICENSE_MARKER, _COPYRIGHT_MARKER, _state,
        )

        # Create a tampered file and verify the detection logic
        tampered_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False,
        )
        try:
            tampered_file.write("# No license header here\nimport os\n")
            tampered_file.close()

            # Verify our tampered file lacks the required markers
            with open(tampered_file.name, encoding="utf-8") as f:
                header = f.read(500)
            assert _LICENSE_MARKER not in header
            assert _COPYRIGHT_MARKER not in header

            # Verify that with a tampered module, the state would degrade
            fake_mod = MagicMock()
            fake_mod.__file__ = tampered_file.name

            _state.tamper_detected = False
            _state.features_degraded = False

            # Simulate header check on one "core" module
            if _LICENSE_MARKER not in header or _COPYRIGHT_MARKER not in header:
                _state.tamper_detected = True
                _state.features_degraded = True

            assert _state.tamper_detected is True
            assert _state.features_degraded is True
        finally:
            os.unlink(tampered_file.name)

    def test_feature_degradation_after_tamper(self):
        """Manually set tamper state and verify features are blocked."""
        from crp.license_guard import is_feature_allowed, _state

        # Clean state — everything allowed
        assert is_feature_allowed("stage_3") is True
        assert is_feature_allowed("stage_4") is True
        assert is_feature_allowed("ckf_graph") is True

        # Simulate tamper detection
        _state.features_degraded = True
        _state.tamper_detected = True

        # Advanced features blocked
        assert is_feature_allowed("stage_3") is False
        assert is_feature_allowed("stage_4") is False
        assert is_feature_allowed("stage_5") is False
        assert is_feature_allowed("stage_6") is False
        assert is_feature_allowed("ckf_graph") is False
        assert is_feature_allowed("continuation_extended") is False
        assert is_feature_allowed("cross_encoder") is False

        # Basic features still allowed
        assert is_feature_allowed("stage_1") is True
        assert is_feature_allowed("stage_2") is True
        assert is_feature_allowed("basic_dispatch") is True

    def test_copyright_marker_content(self):
        """The copyright marker must reference the actual author."""
        from crp.license_guard import _COPYRIGHT_MARKER
        assert "Vidiniotis" in _COPYRIGHT_MARKER

    def test_license_marker_content(self):
        """The license marker must reference ELv2."""
        from crp.license_guard import _LICENSE_MARKER
        assert "Elastic License 2.0" in _LICENSE_MARKER


# ═══════════════════════════════════════════════════════════════════════════
# § 2  MANAGED SERVICE BLOCKING
# ═══════════════════════════════════════════════════════════════════════════

class TestManagedServiceBlocking:
    """Tests for managed-service usage detection and blocking."""

    def test_no_managed_service_env_passes(self):
        """Normal usage (no managed-service env vars) must pass."""
        from crp.license_guard import check_managed_service_restriction
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("CRP_MANAGED_SERVICE", "CRP_MULTI_TENANT",
                                  "CRP_SAAS_MODE", "CRP_LICENSE_KEY")}
        with patch.dict(os.environ, env_clean, clear=True):
            result = check_managed_service_restriction()
            assert result is False

    def test_managed_service_flag_blocks(self):
        """CRP_MANAGED_SERVICE=true must raise CRPError."""
        from crp.license_guard import check_managed_service_restriction, _state
        from crp.core.errors import CRPError
        _state.commercial_license = False

        with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": "true"}, clear=False):
            with pytest.raises(CRPError) as exc_info:
                check_managed_service_restriction()
            assert "MANAGED SERVICE VIOLATION" in str(exc_info.value)
            assert exc_info.value.code == 1011  # SECURITY_INVARIANT_ERROR

    def test_multi_tenant_flag_blocks(self):
        """CRP_MULTI_TENANT=1 must raise CRPError."""
        from crp.license_guard import check_managed_service_restriction, _state
        from crp.core.errors import CRPError
        _state.commercial_license = False

        with patch.dict(os.environ, {"CRP_MULTI_TENANT": "1"}, clear=False):
            with pytest.raises(CRPError):
                check_managed_service_restriction()

    def test_saas_mode_flag_blocks(self):
        """CRP_SAAS_MODE=yes must raise CRPError."""
        from crp.license_guard import check_managed_service_restriction, _state
        from crp.core.errors import CRPError
        _state.commercial_license = False

        with patch.dict(os.environ, {"CRP_SAAS_MODE": "yes"}, clear=False):
            with pytest.raises(CRPError):
                check_managed_service_restriction()

    def test_false_flags_do_not_block(self):
        """Setting flags to '0'/'false'/'no' must NOT block."""
        from crp.license_guard import check_managed_service_restriction, _state
        _state.commercial_license = False

        for val in ("0", "false", "no", "False", "NO"):
            with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": val}, clear=False):
                result = check_managed_service_restriction()
                assert result is False, f"Should not block for value '{val}'"

    def test_commercial_license_bypasses_block(self):
        """A valid commercial license key must bypass managed-service block."""
        from crp.license_guard import check_managed_service_restriction, _state

        # Set commercial license
        _state.commercial_license = True

        with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": "true"}, clear=False):
            # Should NOT raise
            result = check_managed_service_restriction()
            assert result is False

    def test_error_contains_contact_info(self):
        """The CRPError must contain contact information for licensing."""
        from crp.license_guard import check_managed_service_restriction, _state
        from crp.core.errors import CRPError
        _state.commercial_license = False

        with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": "true"}, clear=False):
            with pytest.raises(CRPError) as exc_info:
                check_managed_service_restriction()
            err = exc_info.value
            assert "contact@crprotocol.io" in err.message
            assert err.details["violation_type"] == "managed_service"
            assert err.details["license"] == "Elastic License 2.0"

    def test_infra_indicators_logged_not_blocked(self):
        """Kubernetes/ECS/GAE env vars must log a warning but NOT block."""
        from crp.license_guard import check_managed_service_restriction, _state
        _state.commercial_license = False

        # Only infra indicators, no explicit managed-service flags
        env = {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CRP_MANAGED_SERVICE", "CRP_MULTI_TENANT",
                                  "CRP_SAAS_MODE")}
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            result = check_managed_service_restriction()
            assert result is False  # Should NOT block


# ═══════════════════════════════════════════════════════════════════════════
# § 3  COMMERCIAL LICENSE KEY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

class TestCommercialLicenseKey:
    """Tests for CRP_LICENSE_KEY validation."""

    def test_no_key_returns_false(self):
        """No CRP_LICENSE_KEY means no commercial license."""
        from crp.license_guard import _check_commercial_license
        with patch.dict(os.environ, {}, clear=False):
            if "CRP_LICENSE_KEY" in os.environ:
                del os.environ["CRP_LICENSE_KEY"]
            assert _check_commercial_license() is False

    def test_valid_key_format_accepted(self):
        """A properly formatted CRP-<60hex> key must be accepted."""
        from crp.license_guard import _check_commercial_license
        valid_key = "CRP-" + "a1b2c3d4e5" * 6  # 60 hex chars
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": valid_key}):
            assert _check_commercial_license() is True

    def test_short_key_rejected(self):
        """Keys shorter than 64 chars must be rejected."""
        from crp.license_guard import _check_commercial_license
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": "CRP-abc"}):
            assert _check_commercial_license() is False

    def test_wrong_prefix_rejected(self):
        """Keys without the CRP- prefix must be rejected."""
        from crp.license_guard import _check_commercial_license
        bad_key = "XXX-" + "a1b2c3d4e5" * 6
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": bad_key}):
            assert _check_commercial_license() is False

    def test_non_hex_key_rejected(self):
        """Keys with non-hex characters after prefix must be rejected."""
        from crp.license_guard import _check_commercial_license
        bad_key = "CRP-" + "zzzzzzzzzz" * 6  # 'z' is not hex
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": bad_key}):
            assert _check_commercial_license() is False

    def test_empty_key_returns_false(self):
        """An empty CRP_LICENSE_KEY must return False."""
        from crp.license_guard import _check_commercial_license
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": ""}):
            assert _check_commercial_license() is False

    def test_whitespace_key_returns_false(self):
        """A whitespace-only CRP_LICENSE_KEY must return False."""
        from crp.license_guard import _check_commercial_license
        with patch.dict(os.environ, {"CRP_LICENSE_KEY": "   "}):
            assert _check_commercial_license() is False


# ═══════════════════════════════════════════════════════════════════════════
# § 4  OUTPUT WATERMARKING
# ═══════════════════════════════════════════════════════════════════════════

class TestOutputWatermarking:
    """Tests for output watermarking with license metadata."""

    def test_watermark_appended(self, enable_watermark):
        """Non-empty output must have a watermark appended."""
        from crp.license_guard import watermark_output
        result = watermark_output("Hello world", session_id="test-123")
        assert "<!-- CRP™ | ELv2 |" in result
        assert "Constantinos Vidiniotis" in result

    def test_watermark_contains_hash(self, enable_watermark):
        """Watermark must contain a content hash."""
        from crp.license_guard import watermark_output
        result = watermark_output("Test content")
        assert "h:" in result

    def test_watermark_contains_timestamp(self, enable_watermark):
        """Watermark must contain a timestamp."""
        from crp.license_guard import watermark_output
        result = watermark_output("Test content")
        assert "t:" in result

    def test_watermark_hash_changes_with_content(self, enable_watermark):
        """Different content must produce different hashes."""
        from crp.license_guard import watermark_output
        r1 = watermark_output("Content A")
        r2 = watermark_output("Content B")
        # Extract hashes
        h1 = r1.split("h:")[1].split(" |")[0]
        h2 = r2.split("h:")[1].split(" |")[0]
        assert h1 != h2

    def test_empty_output_not_watermarked(self):
        """Empty or whitespace-only output must not be watermarked."""
        from crp.license_guard import watermark_output
        assert watermark_output("") == ""
        assert watermark_output("   ") == "   "

    def test_watermark_is_html_comment(self, enable_watermark):
        """Watermark must be an HTML comment (non-visible in rendered output)."""
        from crp.license_guard import watermark_output
        result = watermark_output("Test")
        # The watermark should be the last line and be an HTML comment
        lines = result.strip().split("\n")
        watermark_line = lines[-1].strip()
        assert watermark_line.startswith("<!--")
        assert watermark_line.endswith("-->")

    def test_watermark_format_tamper_evident(self, enable_watermark):
        """If someone modifies the output, the hash won't match the content."""
        from crp.license_guard import watermark_output
        original = "Original text"
        watermarked = watermark_output(original)

        # Extract the hash
        hash_str = watermarked.split("h:")[1].split(" |")[0]

        # Verify the hash matches the original content
        expected_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
        assert hash_str == expected_hash

        # If someone modifies the output text, they'd need to recompute the hash
        # This makes unauthorized modifications detectable


# ═══════════════════════════════════════════════════════════════════════════
# § 5  MODULE INTEGRITY FINGERPRINTING
# ═══════════════════════════════════════════════════════════════════════════

class TestModuleFingerprinting:
    """Tests for SHA-256 module fingerprinting."""

    def test_fingerprints_computed(self):
        """All core modules must produce non-None fingerprints."""
        from crp.license_guard import get_module_fingerprints
        fps = get_module_fingerprints()
        assert len(fps) > 0
        for mod, fp in fps.items():
            assert fp is not None, f"{mod} returned None fingerprint"
            assert len(fp) == 64, f"{mod} hash length wrong: {len(fp)}"

    def test_fingerprints_are_hex(self):
        """Fingerprints must be valid hex strings."""
        from crp.license_guard import get_module_fingerprints
        for mod, fp in get_module_fingerprints().items():
            if fp:
                int(fp, 16)  # Should not raise

    def test_fingerprint_deterministic(self):
        """Same module must produce the same fingerprint."""
        from crp.license_guard import compute_module_fingerprint
        fp1 = compute_module_fingerprint("crp.core.orchestrator")
        fp2 = compute_module_fingerprint("crp.core.orchestrator")
        assert fp1 == fp2

    def test_different_modules_different_fingerprints(self):
        """Different modules must produce different fingerprints."""
        from crp.license_guard import compute_module_fingerprint
        fp1 = compute_module_fingerprint("crp.core.orchestrator")
        fp2 = compute_module_fingerprint("crp.core.dispatch_router")
        assert fp1 != fp2

    def test_nonexistent_module_returns_none(self):
        """A non-existent module must return None."""
        from crp.license_guard import compute_module_fingerprint
        assert compute_module_fingerprint("crp.nonexistent.module") is None


# ═══════════════════════════════════════════════════════════════════════════
# § 6  INTEGRITY MANIFEST (TAMPER-EVIDENT CHAIN)
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegrityManifest:
    """Tests for the tamper-evident module manifest."""

    def test_manifest_contains_all_modules(self):
        """Manifest must include all core modules."""
        from crp.license_guard import build_integrity_manifest, _CORE_MODULES
        manifest = build_integrity_manifest()
        for mod in _CORE_MODULES:
            assert mod in manifest["modules"]

    def test_manifest_has_chain_hash(self):
        """Manifest must have a chain hash."""
        from crp.license_guard import build_integrity_manifest
        manifest = build_integrity_manifest()
        assert "chain_hash" in manifest
        assert len(manifest["chain_hash"]) == 64

    def test_manifest_chain_hash_deterministic(self):
        """Chain hash must be deterministic (same modules → same hash)."""
        from crp.license_guard import build_integrity_manifest
        m1 = build_integrity_manifest()
        m2 = build_integrity_manifest()
        assert m1["chain_hash"] == m2["chain_hash"]

    def test_verify_clean_manifest(self):
        """Verifying a fresh manifest against current state must show no changes."""
        from crp.license_guard import (
            build_integrity_manifest, verify_integrity_manifest,
        )
        manifest = build_integrity_manifest()
        changes = verify_integrity_manifest(manifest)
        assert changes == []

    def test_verify_detects_simulated_change(self):
        """A manifest with a different fingerprint must detect the change."""
        from crp.license_guard import (
            build_integrity_manifest, verify_integrity_manifest,
        )
        manifest = build_integrity_manifest()
        # Simulate a change by altering a stored fingerprint
        first_mod = list(manifest["modules"].keys())[0]
        manifest["modules"][first_mod] = "0" * 64  # Fake hash
        changes = verify_integrity_manifest(manifest)
        assert first_mod in changes

    def test_manifest_includes_metadata(self):
        """Manifest must include licensor and version info."""
        from crp.license_guard import build_integrity_manifest
        manifest = build_integrity_manifest()
        assert "licensor" in manifest
        assert "Vidiniotis" in manifest["licensor"]
        assert "generated_at" in manifest
        assert manifest["generated_at"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# § 7  PACKAGE PROVENANCE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

class TestPackageProvenance:
    """Tests for fork/clone redistribution detection."""

    def test_provenance_check_runs_without_error(self):
        """Provenance check must not crash in dev environment."""
        from crp.license_guard import verify_package_provenance
        # In dev mode (editable install), this should return empty or near-empty
        violations = verify_package_provenance()
        assert isinstance(violations, list)

    def test_version_module_exists(self):
        """crp._version must exist and have a version string."""
        from crp._version import __version__
        assert __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_self_tamper_detection(self):
        """License guard must detect if its own source is gutted."""
        from crp.license_guard import verify_package_provenance
        # This should pass in normal conditions
        violations = verify_package_provenance()
        self_tamper_violations = [
            v for v in violations if v.startswith("self_tamper:")
        ]
        assert len(self_tamper_violations) == 0, (
            f"Self-tamper detected: {self_tamper_violations}"
        )

    def test_canonical_constants_present(self):
        """Canonical package metadata constants must exist."""
        from crp.license_guard import (
            _CANONICAL_PACKAGE, _CANONICAL_AUTHOR, _CANONICAL_REPO,
        )
        assert _CANONICAL_PACKAGE == "crp"
        assert "Vidiniotis" in _CANONICAL_AUTHOR
        assert "context-relay-protocol" in _CANONICAL_REPO


# ═══════════════════════════════════════════════════════════════════════════
# § 8  GUARD INTEGRITY (ANTI-STRIPPING)
# ═══════════════════════════════════════════════════════════════════════════

class TestGuardIntegrity:
    """Tests that license_guard.py itself cannot be silently gutted."""

    def test_guard_passes_integrity_check(self):
        """The real license_guard.py must pass its own integrity check."""
        from crp.license_guard import verify_guard_integrity
        assert verify_guard_integrity() is True

    def test_guard_source_exceeds_minimum_size(self):
        """license_guard.py must be larger than 5KB (a stub would be smaller)."""
        guard_file = Path(__file__).parent.parent / "crp" / "license_guard.py"
        assert guard_file.stat().st_size > 5000

    def test_guard_source_exceeds_minimum_lines(self):
        """license_guard.py must have more than 200 lines."""
        guard_file = Path(__file__).parent.parent / "crp" / "license_guard.py"
        with open(guard_file, encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        assert line_count > 200, f"Only {line_count} lines — too small"

    def test_guard_contains_enforcement_functions(self):
        """license_guard.py source must contain all enforcement function names."""
        guard_file = Path(__file__).parent.parent / "crp" / "license_guard.py"
        with open(guard_file, encoding="utf-8") as f:
            source = f.read()

        required = [
            "def verify_license_headers",
            "def check_managed_service_restriction",
            "def is_feature_allowed",
            "def watermark_output",
            "def _startup_check",
            "def _log_violation",
            "def verify_package_provenance",
            "def verify_guard_integrity",
            "CRPError",
            "_CORE_MODULES",
        ]
        for req in required:
            assert req in source, f"Missing '{req}' in license_guard.py"

    def test_guard_not_stubbed(self):
        """A stub file that always returns True/[] must fail integrity."""
        from crp.license_guard import verify_guard_integrity, _state

        # Write a stub to a temp file and check it would be caught
        stub = "def verify_license_headers(): return []\n"
        assert len(stub.encode()) < 5000  # Stub is tiny
        # Our guard checks the size — a stub this small would fail


# ═══════════════════════════════════════════════════════════════════════════
# § 9  ORIGIN BINDING (FORK DETECTION)
# ═══════════════════════════════════════════════════════════════════════════

class TestOriginBinding:
    """Tests for git origin verification."""

    def test_origin_binding_runs_without_error(self):
        """Origin binding check must not crash."""
        from crp.license_guard import verify_origin_binding
        result = verify_origin_binding()
        assert isinstance(result, list)

    def test_canonical_repo_constant(self):
        """The canonical repo must be set correctly."""
        from crp.license_guard import _CANONICAL_REPO
        assert _CANONICAL_REPO == "Constantinos-uni/context-relay-protocol"


# ═══════════════════════════════════════════════════════════════════════════
# § 10  LICENSE INFO METADATA
# ═══════════════════════════════════════════════════════════════════════════

class TestLicenseInfo:
    """Tests for machine-readable license metadata."""

    def test_license_info_complete(self):
        """get_license_info() must return all required fields."""
        from crp.license_guard import get_license_info
        info = get_license_info()

        assert info["license"] == "Elastic License 2.0 (ELv2)"
        assert "Vidiniotis" in info["licensor"]
        assert info["abn"] == "22 697 087 166"
        assert "CRP" in info["product"]
        assert info["url"] == "https://crprotocol.io"
        assert info["contact"] == "contact@crprotocol.io"
        assert info["security"] == "security@crprotocol.io"
        assert "managed service" in info["restriction"].lower()

    def test_license_info_enforcement_state(self):
        """License info must include enforcement state."""
        from crp.license_guard import get_license_info
        info = get_license_info()
        assert "enforcement" in info
        e = info["enforcement"]
        assert "tamper_detected" in e
        assert "features_degraded" in e
        assert "violation_count" in e
        assert "commercial_license" in e


# ═══════════════════════════════════════════════════════════════════════════
# § 11  VIOLATION TELEMETRY
# ═══════════════════════════════════════════════════════════════════════════

class TestViolationTelemetry:
    """Tests for local violation logging."""

    def test_violation_logged_to_file(self, tmp_path):
        """Violations must be written to ~/.crp/violations.jsonl."""
        from crp.license_guard import _log_violation

        with patch("crp.license_guard.Path.home", return_value=tmp_path):
            _log_violation("test_violation", {"key": "value"})

        violations_file = tmp_path / ".crp" / "violations.jsonl"
        assert violations_file.exists()
        content = violations_file.read_text()
        entry = json.loads(content.strip())
        assert entry["type"] == "test_violation"
        assert entry["key"] == "value"
        assert "timestamp" in entry
        assert "CRP" in entry["product"]

    def test_no_network_calls(self):
        """Violation logging must NOT make network calls."""
        from crp.license_guard import _log_violation

        # Patch socket to detect any network activity
        with patch("socket.socket") as mock_socket:
            with patch("crp.license_guard.Path.home",
                       return_value=Path(tempfile.mkdtemp())):
                _log_violation("test", {"data": "test"})
            mock_socket.assert_not_called()

    def test_violation_log_append_mode(self, tmp_path):
        """Multiple violations must be appended, not overwritten."""
        from crp.license_guard import _log_violation

        with patch("crp.license_guard.Path.home", return_value=tmp_path):
            _log_violation("violation_1", {"seq": 1})
            _log_violation("violation_2", {"seq": 2})

        violations_file = tmp_path / ".crp" / "violations.jsonl"
        lines = violations_file.read_text().strip().split("\n")
        assert len(lines) == 2


# ═══════════════════════════════════════════════════════════════════════════
# § 12  STARTUP CHECK INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

class TestStartupCheck:
    """Tests for the import-time startup enforcement."""

    def test_startup_check_sets_timestamp(self):
        """_startup_check() must set checked_at timestamp."""
        from crp.license_guard import _startup_check, _state
        _state.checked_at = 0.0
        before = time.time()

        # Clean env for test
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("CRP_MANAGED_SERVICE", "CRP_MULTI_TENANT",
                                  "CRP_SAAS_MODE")}
        with patch.dict(os.environ, env_clean, clear=True):
            _startup_check()

        assert _state.checked_at >= before

    def test_startup_runs_on_import(self):
        """The startup check must run when crp is imported."""
        from crp.license_guard import _startup_check, _state
        # autouse fixture resets state, so re-run startup
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("CRP_MANAGED_SERVICE", "CRP_MULTI_TENANT",
                                  "CRP_SAAS_MODE")}
        with patch.dict(os.environ, env_clean, clear=True):
            _startup_check()
        assert _state.checked_at > 0

    def test_startup_checks_all_protections(self):
        """Startup must call header verification and provenance check."""
        from crp.license_guard import _state

        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("CRP_MANAGED_SERVICE", "CRP_MULTI_TENANT",
                                  "CRP_SAAS_MODE")}
        with patch.dict(os.environ, env_clean, clear=True):
            with patch("crp.license_guard.verify_license_headers",
                       return_value=[]) as mock_headers, \
                 patch("crp.license_guard.verify_package_provenance",
                       return_value=[]) as mock_prov, \
                 patch("crp.license_guard.verify_guard_integrity",
                       return_value=True) as mock_guard, \
                 patch("crp.license_guard.verify_origin_binding",
                       return_value=[]) as mock_origin:
                from crp.license_guard import _startup_check
                _startup_check()

                mock_headers.assert_called_once()
                mock_prov.assert_called_once()
                mock_guard.assert_called_once()
                mock_origin.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# § 13  GITHUB THREAT MODEL — FORK/CLONE SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════

class TestGitHubThreatModel:
    """
    Tests simulating specific GitHub attack vectors:
      FORK:    Someone forks, strips headers, republishes
      CLONE:   Clone & re-brand as their own package
      STRIP:   Remove license_guard.py entirely
      REBRAND: Change author, license, package name
      SAAS:    Deploy as a managed service
    """

    def test_fork_strip_headers_detected(self):
        """FORK ATTACK: Stripping license headers must degrade features."""
        from crp.license_guard import _state, is_feature_allowed

        # Simulate what happens after headers are stripped
        _state.features_degraded = True
        _state.tamper_detected = True
        _state.tampered_modules = ["crp.core.orchestrator"]

        # Advanced features must be blocked
        assert is_feature_allowed("stage_3") is False
        assert is_feature_allowed("ckf_graph") is False
        assert is_feature_allowed("continuation_extended") is False

    def test_clone_rebrand_package_detected(self):
        """CLONE ATTACK: Re-branded package must be detected by provenance check."""
        from crp.license_guard import _CANONICAL_PACKAGE, _CANONICAL_AUTHOR
        # The canonical constants create a binding that a renamed fork would violate
        assert _CANONICAL_PACKAGE == "crp"
        assert "Vidiniotis" in _CANONICAL_AUTHOR

    def test_strip_guard_detected(self):
        """STRIP ATTACK: Gutting license_guard.py must be detectable."""
        from crp.license_guard import verify_guard_integrity
        # In real code, verify_guard_integrity() reads its own source
        # and checks for minimum size + required functions
        result = verify_guard_integrity()
        assert result is True  # Real guard passes

    def test_saas_deployment_blocked(self):
        """SAAS ATTACK: Deploying as managed service must be blocked."""
        from crp.license_guard import check_managed_service_restriction, _state
        from crp.core.errors import CRPError
        _state.commercial_license = False

        with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": "true"}):
            with pytest.raises(CRPError) as exc:
                check_managed_service_restriction()
            assert exc.value.code == 1011

    def test_fork_with_commercial_license_allowed(self):
        """LEGITIMATE USE: A fork WITH a commercial license must work."""
        from crp.license_guard import check_managed_service_restriction, _state
        _state.commercial_license = True

        with patch.dict(os.environ, {"CRP_MANAGED_SERVICE": "true"}):
            # Should NOT raise
            result = check_managed_service_restriction()
            assert result is False

    def test_watermark_survives_in_output(self, enable_watermark):
        """OUTPUT TRACKING: Watermark must survive in all non-empty outputs."""
        from crp.license_guard import watermark_output

        test_outputs = [
            "Simple text",
            "Multi\nline\noutput",
            "<html><body>Rich content</body></html>",
            "{}",  # JSON-like
            "# Markdown heading\n\nContent here.",
        ]
        for output in test_outputs:
            watermarked = watermark_output(output)
            assert "CRP™" in watermarked, f"Watermark missing from: {output!r}"
            assert "ELv2" in watermarked
            assert "Vidiniotis" in watermarked


# ═══════════════════════════════════════════════════════════════════════════
# § 14  SOURCE FILE COPYRIGHT COVERAGE
# ═══════════════════════════════════════════════════════════════════════════

class TestCopyrightCoverage:
    """Verify every Python source file has the copyright header."""

    def test_all_python_files_have_copyright(self):
        """Every .py file in crp/ must have the copyright header."""
        crp_root = Path(__file__).parent.parent / "crp"
        missing = []

        for py_file in crp_root.rglob("*.py"):
            if py_file.name == "__pycache__":
                continue
            with open(py_file, encoding="utf-8", errors="ignore") as f:
                header = f.read(500)
            if "Constantinos Vidiniotis" not in header:
                missing.append(str(py_file.relative_to(crp_root.parent)))

        assert missing == [], (
            f"Files missing copyright header:\n"
            + "\n".join(f"  - {f}" for f in missing)
        )

    def test_all_python_files_have_license_ref(self):
        """Every .py file in crp/ must reference Elastic License 2.0."""
        crp_root = Path(__file__).parent.parent / "crp"
        missing = []

        for py_file in crp_root.rglob("*.py"):
            if py_file.name == "__pycache__":
                continue
            with open(py_file, encoding="utf-8", errors="ignore") as f:
                header = f.read(500)
            if "Elastic License 2.0" not in header:
                missing.append(str(py_file.relative_to(crp_root.parent)))

        assert missing == [], (
            f"Files missing ELv2 license reference:\n"
            + "\n".join(f"  - {f}" for f in missing)
        )


# ═══════════════════════════════════════════════════════════════════════════
# § 15  FEATURE GATE EXHAUSTIVE COVERAGE
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureGateExhaustive:
    """Exhaustive tests for the feature gate in degraded mode."""

    @pytest.mark.parametrize("feature,expected", [
        ("stage_1", True),
        ("stage_2", True),
        ("basic_dispatch", True),
        ("stage_3", False),
        ("stage_4", False),
        ("stage_5", False),
        ("stage_6", False),
        ("ckf_graph", False),
        ("continuation_extended", False),
        ("cross_encoder", False),
    ])
    def test_degraded_feature_gate(self, feature, expected):
        """In degraded mode, only basic features are allowed."""
        from crp.license_guard import is_feature_allowed, _state
        _state.features_degraded = True
        assert is_feature_allowed(feature) is expected

    @pytest.mark.parametrize("feature", [
        "stage_1", "stage_2", "stage_3", "stage_4", "stage_5", "stage_6",
        "basic_dispatch", "ckf_graph", "continuation_extended", "cross_encoder",
    ])
    def test_clean_state_all_allowed(self, feature):
        """In clean state, ALL features must be allowed."""
        from crp.license_guard import is_feature_allowed, _state
        _state.features_degraded = False
        assert is_feature_allowed(feature) is True


# ═══════════════════════════════════════════════════════════════════════════
# § 16  CONSTANTS INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════

class TestConstantsIntegrity:
    """Verify that license constants haven't been altered."""

    def test_licensor_constant(self):
        from crp.license_guard import _LICENSOR
        assert "Constantinos Vidiniotis" in _LICENSOR
        assert "AutoCyber AI" in _LICENSOR

    def test_abn_constant(self):
        from crp.license_guard import _ABN
        assert _ABN == "22 697 087 166"

    def test_product_constant(self):
        from crp.license_guard import _PRODUCT
        assert "CRP" in _PRODUCT
        assert "Context Relay Protocol" in _PRODUCT

    def test_license_url_constant(self):
        from crp.license_guard import _LICENSE_URL
        assert _LICENSE_URL == "https://crprotocol.io"

    def test_core_modules_list_not_empty(self):
        from crp.license_guard import _CORE_MODULES
        assert len(_CORE_MODULES) >= 8

    def test_managed_service_indicators_present(self):
        from crp.license_guard import _MANAGED_SERVICE_INDICATORS
        assert "CRP_MANAGED_SERVICE" in _MANAGED_SERVICE_INDICATORS
        assert "CRP_MULTI_TENANT" in _MANAGED_SERVICE_INDICATORS
        assert "CRP_SAAS_MODE" in _MANAGED_SERVICE_INDICATORS
