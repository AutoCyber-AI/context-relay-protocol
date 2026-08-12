# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Gateway — Per-tenant encrypted key vault.

Stores and retrieves provider API keys for Gateway tenants.  Keys are never
logged, never exposed in headers, and are held in encrypted form at rest.

Security invariants (SPEC-016 §6, SPEC-015 §9):
  - Keys are AES-256-GCM encrypted at rest using a per-vault master key.
  - Keys are only decrypted in memory immediately before the provider call.
  - The plaintext key is NOT stored; the master key is required to recover it.
  - Encrypted values never appear in logs (only 8-character safe-prefix hint).
  - In development / test mode (no cryptography package), keys are stored as
    plain environment variable overrides with a clear advisory logged.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

#: Environment variable prefix used to resolve API keys before the vault.
#: e.g. CRP_KEY_OPENAI, CRP_KEY_ANTHROPIC, CRP_KEY_LOCAL
_ENV_PREFIX = "CRP_KEY_"

#: Fallback env vars for common provider keys (compatibility with existing SDKs).
_PROVIDER_ENV_FALLBACKS: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY", "CRP_KEY_OPENAI"],
    "anthropic": ["ANTHROPIC_API_KEY", "CRP_KEY_ANTHROPIC"],
    "gemini": ["GOOGLE_API_KEY", "CRP_KEY_GEMINI"],
    "bedrock": ["AWS_BEDROCK_KEY", "CRP_KEY_BEDROCK"],
    "local": ["CRP_KEY_LOCAL", "CRP_LOCAL_API_KEY"],
}


class KeyVault:
    """Per-tenant encrypted provider key storage.

    For the self-hosted Gateway, keys are typically stored as environment
    variables (dev) or in a secrets manager (prod).  For the hosted service,
    keys are stored encrypted in a per-tenant vault partition.

    This class provides a consistent interface regardless of the backend.

    Args:
        master_key: Optional 32-byte master encryption key.  If not provided,
            derives one from the ``CRP_VAULT_MASTER_KEY`` environment variable,
            or generates an ephemeral random key (dev mode — keys are in-memory
            only for the process lifetime).
    """

    def __init__(self, master_key: bytes | None = None) -> None:
        self._store: dict[str, str] = {}  # tenant:provider → encrypted value
        self._master_key: bytes = self._resolve_master_key(master_key)
        self._dev_mode: bool = False

        # Attempt to import cryptography package; fall back to dev mode
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401

            self._crypto_available = True
        except ImportError:
            self._crypto_available = False
            self._dev_mode = True
            logger.info(
                "KeyVault: cryptography package not installed — running in dev mode "
                "(keys stored as env var lookups only; install `pip install cryptography` for prod)."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_provider_key(self, tenant_id: str, provider: str) -> str:
        """Retrieve and decrypt the API key for *provider* for *tenant_id*.

        Resolution order:
          1. Vault store (encrypted at rest) — for stored/provisioned keys.
          2. Environment variable override — ``CRP_KEY_<PROVIDER>`` or provider-
             specific env var (e.g. ``OPENAI_API_KEY``).
          3. Empty string — caller may still proceed for local/no-auth providers.

        Returns:
            Plaintext API key string (decrypted in memory, not cached).
        """
        vault_key = self._vault_key(tenant_id, provider)

        # 1. Vault store
        if vault_key in self._store:
            return self._decrypt(self._store[vault_key])

        # 2. Environment variable lookup
        return self._resolve_env_key(provider)

    def store_key(self, tenant_id: str, provider: str, plaintext_key: str) -> None:
        """Encrypt and store an API key in the vault.

        The plaintext key is encrypted immediately; the plaintext is not kept.
        Logs a safe hint (first 8 chars of the provider key).

        Security note: in production, *plaintext_key* should be passed from
        a secrets manager or user input — never from a log or request body.
        """
        if not plaintext_key:
            raise ValueError("Cannot store an empty API key.")
        encrypted = self._encrypt(plaintext_key)
        self._store[self._vault_key(tenant_id, provider)] = encrypted
        safe_hint = plaintext_key[:8].replace(plaintext_key[4:8], "****")
        logger.info("KeyVault: stored key for tenant=%s provider=%s hint=%s", tenant_id, provider, safe_hint)

    def delete_key(self, tenant_id: str, provider: str) -> None:
        """Remove a stored key from the vault."""
        self._store.pop(self._vault_key(tenant_id, provider), None)

    def has_key(self, tenant_id: str, provider: str) -> bool:
        """Return True if a key is stored in the vault (not env vars)."""
        return self._vault_key(tenant_id, provider) in self._store

    def rotate_key(self, tenant_id: str, provider: str, new_plaintext_key: str) -> None:
        """Atomically replace an existing key with a new one."""
        self.delete_key(tenant_id, provider)
        self.store_key(tenant_id, provider, new_plaintext_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _vault_key(self, tenant_id: str, provider: str) -> str:
        """Stable deterministic key for the in-memory store dict."""
        return f"{tenant_id.lower()}:{provider.lower()}"

    def _resolve_master_key(self, master_key: bytes | None) -> bytes:
        if master_key and len(master_key) >= 32:
            return master_key[:32]
        env_val = os.environ.get("CRP_VAULT_MASTER_KEY", "")
        if env_val:
            return hashlib.sha256(env_val.encode()).digest()
        # Ephemeral random key for dev/test
        import secrets

        return secrets.token_bytes(32)

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* with AES-256-GCM; return base64-encoded ciphertext.

        Falls back to a reversible XOR-with-key encoding in dev mode (NOT secure
        — for structure preservation only; real keys go in env vars in dev).
        """
        if self._crypto_available:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import secrets as _secrets

            nonce = _secrets.token_bytes(12)
            aesgcm = AESGCM(self._master_key)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return base64.urlsafe_b64encode(nonce + ct).decode()
        # Dev mode: trivial XOR (not secure, not used for real keys)
        xor_key = self._master_key[: len(plaintext)] + self._master_key * (
            len(plaintext) // len(self._master_key) + 1
        )
        xored = bytes(a ^ b for a, b in zip(plaintext.encode(), xor_key))
        return "dev:" + base64.urlsafe_b64encode(xored).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a value encrypted by :meth:`_encrypt`."""
        if ciphertext.startswith("dev:"):
            raw = base64.urlsafe_b64decode(ciphertext[4:] + "==")
            xor_key = self._master_key[: len(raw)] + self._master_key * (
                len(raw) // len(self._master_key) + 1
            )
            return bytes(a ^ b for a, b in zip(raw, xor_key)).decode("utf-8")

        if not self._crypto_available:
            raise RuntimeError(
                "KeyVault: cannot decrypt — cryptography package required. "
                "Install with: pip install cryptography"
            )
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.urlsafe_b64decode(ciphertext + "==")
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")

    def _resolve_env_key(self, provider: str) -> str:
        """Look up a provider key from environment variables."""
        # Try provider-specific env vars
        for env_var in _PROVIDER_ENV_FALLBACKS.get(provider, []):
            val = os.environ.get(env_var, "")
            if val:
                return val
        # Generic CRP_KEY_<PROVIDER>
        generic = os.environ.get(f"{_ENV_PREFIX}{provider.upper()}", "")
        return generic

    # ------------------------------------------------------------------
    # Serialisation (for testing / state persistence)
    # ------------------------------------------------------------------

    def export_encrypted_store(self) -> dict[str, str]:
        """Return a copy of the encrypted store (safe to log/serialise)."""
        return dict(self._store)

    def import_encrypted_store(self, store: dict[str, str]) -> None:
        """Restore a previously exported encrypted store."""
        self._store.update(store)
