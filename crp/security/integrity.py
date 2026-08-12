# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Fact integrity — BLAKE3/SHA-256 hash chain + HMAC verification (§7.2, §7.7).

Provides a tamper-evident chain of fact hashes:
- Per-fact hash: BLAKE3 (~1μs) with SHA-256 fallback
- Hash chain: ordered sequence of fact hashes
- Chain signature: HMAC(session_key, hash_N ‖ ... ‖ hash_0)
- Spot-check verification: 10% sample on cold load
- Full verification on envelope construction
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import random
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Per-fact hashing
# ---------------------------------------------------------------------------

_USE_BLAKE3: bool | None = None


def _has_blake3() -> bool:
    global _USE_BLAKE3  # noqa: PLW0603
    if _USE_BLAKE3 is None:
        try:
            import blake3  # type: ignore[import-untyped]  # noqa: F401
            _USE_BLAKE3 = True
        except ImportError:
            _USE_BLAKE3 = False
    return _USE_BLAKE3


def compute_fact_hash(text: str) -> str:
    """Compute integrity hash for a fact's text (§6B.2).

    Uses BLAKE3 (~1μs) when available, SHA-256 fallback.
    """
    data = text.encode("utf-8")
    if _has_blake3():
        import blake3  # type: ignore[import-untyped]
        return blake3.blake3(data).hexdigest()
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Fact Integrity Chain
# ---------------------------------------------------------------------------


@dataclass
class ChainEntry:
    """Single entry in the fact integrity chain."""

    fact_id: str
    fact_hash: str
    index: int  # position in chain


class FactIntegrityChain:
    """Tamper-evident chain of fact hashes (§7.7).

    Maintains an ordered hash chain. Chain signature is computed via
    HMAC(session_key, hash_N ‖ ... ‖ hash_0).

    Usage:
        chain = FactIntegrityChain(session_key)
        chain.add_fact("f1", "capital of France is Paris")
        sig = chain.chain_signature()
        assert chain.verify_chain(sig)
    """

    def __init__(self, session_key: bytes | None = None) -> None:
        self._session_key = session_key or b""
        self._entries: list[ChainEntry] = []
        self._hash_by_id: dict[str, str] = {}

    @property
    def size(self) -> int:
        """Return the current size count."""
        return len(self._entries)

    def add_fact(self, fact_id: str, text: str) -> ChainEntry:
        """Hash a fact and append to the chain."""
        h = compute_fact_hash(text)
        entry = ChainEntry(
            fact_id=fact_id,
            fact_hash=h,
            index=len(self._entries),
        )
        self._entries.append(entry)
        self._hash_by_id[fact_id] = h
        return entry

    def get_hash(self, fact_id: str) -> str | None:
        """Get stored hash for a fact by ID."""
        return self._hash_by_id.get(fact_id)

    def verify_fact(self, fact_id: str, text: str) -> bool:
        """Verify a single fact's hash matches the chain."""
        stored = self._hash_by_id.get(fact_id)
        if stored is None:
            return False
        return _hmac.compare_digest(stored, compute_fact_hash(text))

    # ── Chain signature (§6B.3) ────────────────────────────────

    def chain_signature(self) -> str:
        """Compute HMAC(session_key, hash_N ‖ ... ‖ hash_0) (§6B.3).

        Hash chain is concatenated in reverse order (newest first).
        """
        if not self._session_key:
            raise ValueError("No session key set — cannot compute chain signature")
        # Concatenate hashes in reverse order
        chain_data = "".join(e.fact_hash for e in reversed(self._entries))
        return _hmac.new(
            self._session_key, chain_data.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify_chain(self, expected_signature: str) -> bool:
        """Verify the full chain signature matches."""
        if not self._session_key:
            return False
        actual = self.chain_signature()
        return _hmac.compare_digest(actual, expected_signature)

    # ── Spot-check verification (§6B.4) ───────────────────────

    def verify_spot_check(
        self,
        fact_texts: dict[str, str],
        sample_ratio: float = 0.10,
    ) -> tuple[int, int, list[str]]:
        """Spot-check 10% of facts on cold load (§6B.4).

        Args:
            fact_texts: {fact_id: current_text} for verification
            sample_ratio: fraction of chain to sample (default 10%)

        Returns:
            (checked, failures, failed_ids)
        """
        if not self._entries:
            return 0, 0, []

        sample_size = max(1, int(len(self._entries) * sample_ratio))
        sample = random.sample(self._entries, min(sample_size, len(self._entries)))

        failures: list[str] = []
        for entry in sample:
            text = fact_texts.get(entry.fact_id)
            if text is None:
                failures.append(entry.fact_id)
                continue
            if not self.verify_fact(entry.fact_id, text):
                failures.append(entry.fact_id)

        return len(sample), len(failures), failures

    # ── Envelope verification (§6B.5) ─────────────────────────

    def verify_for_envelope(
        self, fact_ids: list[str], fact_texts: dict[str, str]
    ) -> tuple[bool, list[str]]:
        """Verify all facts before including in envelope (§6B.5).

        Returns (all_valid, failed_ids).
        """
        failed: list[str] = []
        for fid in fact_ids:
            text = fact_texts.get(fid)
            if text is None:
                failed.append(fid)
                continue
            if not self.verify_fact(fid, text):
                failed.append(fid)
        return len(failed) == 0, failed

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the integrity chain entries to a dict."""
        return {
            "entries": [
                {"fact_id": e.fact_id, "fact_hash": e.fact_hash, "index": e.index}
                for e in self._entries
            ],
        }

    def export_for_verification(self) -> dict[str, Any]:
        """Export chain data for external verification (§audit M13).

        Returns a dict containing all chain entries and (if session key is set)
        the chain signature, suitable for independent audit.
        """
        export: dict[str, Any] = {
            "chain_length": len(self._entries),
            "hash_algorithm": "blake3" if _has_blake3() else "sha256",
            "entries": [
                {
                    "fact_id": e.fact_id,
                    "fact_hash": e.fact_hash,
                    "index": e.index,
                }
                for e in self._entries
            ],
        }
        if self._session_key:
            export["chain_signature"] = self.chain_signature()
        return export

    @staticmethod
    def verify_external(
        export_data: dict[str, Any],
        fact_texts: dict[str, str],
    ) -> tuple[bool, list[str]]:
        """Verify an exported chain against provided fact texts (§audit M13).

        This is a static method usable without access to the session key —
        it re-hashes each fact and compares to the stored hash.

        Returns (all_valid, failed_fact_ids).
        """
        # Use the algorithm recorded at export time to avoid mismatch
        algo = export_data.get("hash_algorithm", "sha256")
        if algo == "blake3" and not _has_blake3():
            raise RuntimeError(
                "Exported chain uses blake3 but blake3 is not installed. "
                "Install blake3 to verify this chain."
            )

        def _hash_text(text: str) -> str:
            data = text.encode("utf-8")
            if algo == "blake3":
                import blake3 as _b3  # type: ignore[import-untyped]
                return _b3.blake3(data).hexdigest()
            return hashlib.sha256(data).hexdigest()

        failures: list[str] = []
        for entry in export_data.get("entries", []):
            fid = entry["fact_id"]
            expected_hash = entry["fact_hash"]
            text = fact_texts.get(fid)
            if text is None:
                failures.append(fid)
                continue
            actual_hash = _hash_text(text)
            if not _hmac.compare_digest(actual_hash, expected_hash):
                failures.append(fid)
        return len(failures) == 0, failures

    @classmethod
    def from_dict(cls, data: dict[str, Any], session_key: bytes | None = None) -> FactIntegrityChain:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
                session_key (bytes | None): The session key value.
        
            Returns:
                ``FactIntegrityChain``.
        """
        chain = cls(session_key=session_key)
        for edata in data.get("entries", []):
            entry = ChainEntry(
                fact_id=edata["fact_id"],
                fact_hash=edata["fact_hash"],
                index=edata.get("index", len(chain._entries)),
            )
            chain._entries.append(entry)
            chain._hash_by_id[entry.fact_id] = entry.fact_hash
        return chain
