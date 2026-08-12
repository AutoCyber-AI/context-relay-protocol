# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Session binding — HMAC-SHA256 key derivation and request verification (§7.1).

Provides session-scoped cryptographic binding:
- 32-byte session nonce
- 256-bit HMAC-derived session key
- Constant-time request signature verification
- OS keyring storage with zero-config fallback
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass


@dataclass
class SessionBinding:
    """Cryptographic session binding parameters."""

    session_id: str
    session_nonce: bytes  # 32 bytes
    session_key: bytes  # 256-bit derived key
    created_at: float = 0.0


class SessionBindingManager:
    """HMAC-SHA256 session binding with OS keyring + zero-config fallback (§7.1).

    Usage:
        mgr = SessionBindingManager()
        binding = mgr.create_session("session-123")
        sig = mgr.sign_request(b"payload")
        assert mgr.verify_request_signature(b"payload", sig)
    """

    def __init__(self, master_secret: bytes | None = None) -> None:
        # Zero-config fallback: auto-generate binding secret (§6A.5)
        if master_secret is None:
            master_secret = self._load_or_generate_secret()
        self._master_secret = master_secret
        self._binding: SessionBinding | None = None
        # Key versioning for rotation support (§audit H2)
        self._key_version: int = 0
        self._previous_keys: list[tuple[int, bytes]] = []  # (version, key) pairs
        self._rotation_window: int = 2  # accept N previous key versions

    @property
    def binding(self) -> SessionBinding | None:
        """Return the binding."""
        return self._binding

    @property
    def session_key(self) -> bytes:
        """Return current session key (raises if no session)."""
        if self._binding is None:
            raise RuntimeError("No active session — call create_session() first")
        return self._binding.session_key

    def create_session(self, session_id: str = "") -> SessionBinding:
        """Create a new session with fresh nonce and derived key (§6A.1, §6A.2).

        - session_nonce: 32 bytes of cryptographic randomness
        - session_key: HMAC-SHA256(master_secret, nonce || session_id)
        """
        import time

        nonce = secrets.token_bytes(32)
        # Derive 256-bit session key via HMAC
        key_material = nonce + session_id.encode("utf-8")
        session_key = hmac.new(
            self._master_secret, key_material, hashlib.sha256
        ).digest()  # 32 bytes = 256 bits

        self._binding = SessionBinding(
            session_id=session_id or secrets.token_hex(16),
            session_nonce=nonce,
            session_key=session_key,
            created_at=time.time(),
        )
        return self._binding

    def sign_request(self, payload: bytes) -> str:
        """Compute HMAC-SHA256 signature over payload (§6A.3)."""
        key = self.session_key
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def verify_request_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """Constant-time HMAC verification (§6A.3).

        Uses hmac.compare_digest to prevent timing attacks.
        Also checks previous key versions during rotation window.
        """
        expected = self.sign_request(payload)
        if hmac.compare_digest(expected, signature):
            return True
        # Check previous keys during rotation window (§audit H2)
        for _ver, old_key in self._previous_keys:
            old_sig = hmac.new(old_key, payload, hashlib.sha256).hexdigest()
            if hmac.compare_digest(old_sig, signature):
                return True
        return False

    def rotate_secret(self) -> SessionBinding:
        """Rotate master secret with graceful rollover (§audit H2).

        Generates a fresh 256-bit master secret, re-derives the session key,
        and keeps the previous key(s) valid for verification during the
        rotation window.

        Returns:
            Updated SessionBinding with the new key material.

        Raises:
            RuntimeError: If no active session exists.
        """
        if self._binding is None:
            raise RuntimeError("No active session — call create_session() first")

        # Preserve current key for rollover
        self._previous_keys.append((self._key_version, self._binding.session_key))
        # Trim to rotation window size
        if len(self._previous_keys) > self._rotation_window:
            self._previous_keys = self._previous_keys[-self._rotation_window:]

        # Generate new master secret
        self._master_secret = secrets.token_bytes(32)
        self._key_version += 1

        # Re-derive session key with new master secret but same nonce/session_id
        key_material = self._binding.session_nonce + self._binding.session_id.encode("utf-8")
        new_session_key = hmac.new(
            self._master_secret, key_material, hashlib.sha256
        ).digest()

        import time
        self._binding = SessionBinding(
            session_id=self._binding.session_id,
            session_nonce=self._binding.session_nonce,
            session_key=new_session_key,
            created_at=time.time(),
        )
        return self._binding

    @property
    def key_version(self) -> int:
        """Current key version number."""
        return self._key_version

    # ── OS keyring storage (§6A.4) ────────────────────────────

    def store_to_keyring(self, service_name: str = "crp-sdk") -> bool:
        """Store master secret in OS keyring (DPAPI/Keychain/kernel).

        Returns True if stored, False if keyring unavailable.
        """
        try:
            import keyring  # type: ignore[import-untyped]
            keyring.set_password(
                service_name, "master_secret", self._master_secret.hex()
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    @classmethod
    def from_keyring(cls, service_name: str = "crp-sdk") -> SessionBindingManager | None:
        """Load master secret from OS keyring. Returns None if unavailable."""
        try:
            import keyring  # type: ignore[import-untyped]
            stored = keyring.get_password(service_name, "master_secret")
            if stored:
                return cls(master_secret=bytes.fromhex(stored))
        except Exception:  # noqa: BLE001
            pass
        return None

    def _load_or_generate_secret(self) -> bytes:
        """Zero-config fallback: try keyring, then generate fresh (§6A.5)."""
        try:
            import keyring  # type: ignore[import-untyped]
            stored = keyring.get_password("crp-sdk", "master_secret")
            if stored:
                return bytes.fromhex(stored)
        except Exception:  # noqa: BLE001
            pass
        # Auto-generate 256-bit secret
        return secrets.token_bytes(32)
