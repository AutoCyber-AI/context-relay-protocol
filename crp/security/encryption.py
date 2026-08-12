# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Encryption at rest — AES-256-GCM for cold state and event log (§7.3).

Uses HKDF key diversification so different data classes (cold_storage,
event_log) use different derived keys from the same session key.

Requires the `cryptography` package for production use (AES-256-GCM).
A fallback XOR cipher is available for dep-free environments but logs
a loud warning — it provides only obfuscation, not real encryption.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import logging
import secrets
import warnings
from dataclasses import dataclass

logger = logging.getLogger("crp.security.encryption")


@dataclass
class EncryptedBlob:
    """Encrypted data container."""

    ciphertext: bytes
    nonce: bytes  # 12 bytes for AES-GCM
    salt: bytes  # HKDF salt
    tag: bytes  # GCM authentication tag (empty if using fallback)
    key_purpose: str  # "cold_storage" or "event_log"

    def to_dict(self) -> dict[str, str]:
        """Serialize the encrypted blob to a base64-encoded dict."""
        import base64
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "tag": base64.b64encode(self.tag).decode(),
            "key_purpose": self.key_purpose,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> EncryptedBlob:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, str]): The data value.
        
            Returns:
                ``EncryptedBlob``.
        """
        import base64
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            salt=base64.b64decode(data["salt"]),
            tag=base64.b64decode(data.get("tag", "")),
            key_purpose=data.get("key_purpose", ""),
        )


# ---------------------------------------------------------------------------
# HKDF key diversification (§6C.4)
# ---------------------------------------------------------------------------


def _hkdf_derive(
    master_key: bytes,
    salt: bytes,
    info: bytes,
    length: int = 32,
) -> bytes:
    """HKDF-SHA256 key derivation (§6C.4).

    Uses cryptography library if available, otherwise HMAC-based fallback.
    """
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            info=info,
        )
        return kdf.derive(master_key)
    except ImportError:
        # HMAC-based HKDF extract + expand fallback
        # Extract
        prk = _hmac.new(salt or b"\x00" * 32, master_key, hashlib.sha256).digest()
        # Expand (single block is enough for 32 bytes)
        okm = _hmac.new(prk, info + b"\x01", hashlib.sha256).digest()
        return okm[:length]


# ---------------------------------------------------------------------------
# StateEncryptor
# ---------------------------------------------------------------------------


class StateEncryptor:
    """AES-256-GCM encryption for cold state and event logs (§7.3).

    Usage:
        enc = StateEncryptor(session_key)
        blob = enc.encrypt_cold_state(data_bytes)
        plaintext = enc.decrypt_cold_state(blob)
    """

    COLD_STORAGE_PURPOSE = "cold_storage"
    EVENT_LOG_PURPOSE = "event_log"

    def __init__(self, session_key: bytes) -> None:
        if len(session_key) < 32:
            raise ValueError(
                f"Session key must be at least 32 bytes for AES-256, got {len(session_key)}"
            )
        self._session_key = session_key

    def _derive_key(self, salt: bytes, purpose: str) -> bytes:
        """Derive purpose-specific key via HKDF (§6C.4)."""
        return _hkdf_derive(
            self._session_key,
            salt=salt,
            info=purpose.encode("utf-8"),
            length=32,
        )

    def _encrypt(self, plaintext: bytes, purpose: str) -> EncryptedBlob:
        """Encrypt with AES-256-GCM (§6C.1)."""
        salt = secrets.token_bytes(16)
        key = self._derive_key(salt, purpose)
        nonce = secrets.token_bytes(12)

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aes = AESGCM(key)
            ct = aes.encrypt(nonce, plaintext, purpose.encode("utf-8"))
            # AESGCM appends 16-byte tag to ciphertext
            return EncryptedBlob(
                ciphertext=ct,
                nonce=nonce,
                salt=salt,
                tag=b"",  # tag is embedded in ciphertext for AESGCM
                key_purpose=purpose,
            )
        except ImportError:
            raise ImportError(
                "CRP requires the 'cryptography' package for AES-256-GCM encryption. "
                "The XOR fallback has been removed for production safety. "
                "Install it with: pip install cryptography"
            ) from None

    def _decrypt(self, blob: EncryptedBlob, purpose: str) -> bytes:
        """Decrypt AES-256-GCM ciphertext."""
        key = self._derive_key(blob.salt, purpose)

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aes = AESGCM(key)
            return aes.decrypt(blob.nonce, blob.ciphertext, purpose.encode("utf-8"))
        except ImportError:
            raise ImportError(
                "CRP requires the 'cryptography' package for AES-256-GCM decryption. "
                "Install it with: pip install cryptography"
            ) from None

    # ── Public API (§6C.2, §6C.3) ─────────────────────────────

    def encrypt_cold_state(self, data: bytes) -> EncryptedBlob:
        """Encrypt cold state data (§6C.2)."""
        return self._encrypt(data, self.COLD_STORAGE_PURPOSE)

    def decrypt_cold_state(self, blob: EncryptedBlob) -> bytes:
        """Decrypt cold state data (§6C.2)."""
        return self._decrypt(blob, self.COLD_STORAGE_PURPOSE)

    def encrypt_event_log(self, data: bytes) -> EncryptedBlob:
        """Encrypt event log data (§6C.3)."""
        return self._encrypt(data, self.EVENT_LOG_PURPOSE)

    def decrypt_event_log(self, blob: EncryptedBlob) -> bytes:
        """Decrypt event log data (§6C.3)."""
        return self._decrypt(blob, self.EVENT_LOG_PURPOSE)

    # ── Fallback XOR cipher (no deps) ─────────────────────────

    def _fallback_encrypt(
        self,
        plaintext: bytes,
        key: bytes,
        nonce: bytes,
        salt: bytes,
        purpose: str,
    ) -> EncryptedBlob:
        """XOR fallback removed for production safety (§audit3 SEC-H2)."""
        raise NotImplementedError(
            "XOR fallback cipher removed. Install the 'cryptography' package."
        )

    def _fallback_decrypt(
        self, ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes
    ) -> bytes:
        """XOR fallback removed for production safety (§audit3 SEC-H2)."""
        raise NotImplementedError(
            "XOR fallback cipher removed. Install the 'cryptography' package."
        )
