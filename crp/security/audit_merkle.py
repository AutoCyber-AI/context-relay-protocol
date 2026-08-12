# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Merkle inclusion proofs for the compliance audit trail (§7.14, SPEC-011).

A :class:`MerkleTree` is built over the SHA-256 ``entry_hash`` values of a
:class:`~crp.security.audit_trail.ComplianceAuditTrail`, giving:

  - a single ``root()`` commitment over the whole trail (what gets externally
    anchored — see ``crp.security.audit_anchor``), and
  - O(log n) ``inclusion_proof(index)`` / ``verify_inclusion`` receipts that
    let an auditor confirm one entry is part of an anchored root without
    seeing the rest of the trail.

Hashing scheme (stdlib ``hashlib`` only, deterministic):

  - Leaves are the entry hashes themselves (64-char lowercase hex of SHA-256).
  - Internal node = ``sha256(bytes.fromhex(left) + bytes.fromhex(right))``.
  - An odd node at any level is **promoted** unchanged to the next level
    (never duplicated), so proof sides are unambiguous.
  - The empty tree has root ``""`` and no valid proofs.

Proof encoding: a proof is a list of ``"<side>:<sibling_hex>"`` strings,
ordered leaf-to-root, where ``side`` is ``"left"`` or ``"right"`` — the
position of the *sibling* relative to the running hash. The encoding is
self-contained: :func:`MerkleTree.verify_inclusion` needs no index or leaf
count, which makes proofs safe to ship as standalone receipts.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac


def _hash_pair(left_hex: str, right_hex: str) -> str:
    """Internal node hash: SHA-256 over the concatenated raw child digests."""
    return hashlib.sha256(
        bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    ).hexdigest()


class MerkleTree:
    """Binary Merkle tree over hex-encoded SHA-256 leaf hashes.

    Args:
        leaf_hashes: Leaf digests (64-char hex, e.g. audit ``entry_hash``
            values) in trail order.

    Raises:
        ValueError: If any leaf is not a 64-char hex string.
    """

    def __init__(self, leaf_hashes: list[str]) -> None:
        for leaf in leaf_hashes:
            if not isinstance(leaf, str) or len(leaf) != 64:
                raise ValueError(f"leaf hash must be 64-char hex, got {leaf!r:.80}")
            bytes.fromhex(leaf)  # raises ValueError on non-hex input
        self._leaves = list(leaf_hashes)
        # levels[0] = leaves, levels[-1] = [root]; odd nodes promoted unchanged
        self._levels: list[list[str]] = [self._leaves]
        while len(self._levels[-1]) > 1:
            level = self._levels[-1]
            nxt = [
                _hash_pair(level[i], level[i + 1])
                for i in range(0, len(level) - 1, 2)
            ]
            if len(level) % 2 == 1:
                nxt.append(level[-1])  # promote odd node unchanged
            self._levels.append(nxt)

    @property
    def leaf_count(self) -> int:
        """Number of leaves the tree was built from."""
        return len(self._leaves)

    def root(self) -> str:
        """Merkle root hex digest; ``""`` for an empty tree."""
        if not self._leaves:
            return ""
        return self._levels[-1][0]

    def inclusion_proof(self, index: int) -> list[str]:
        """Return the sibling-hash proof for the leaf at ``index``.

        The proof is ordered leaf-to-root; each element is
        ``"<side>:<sibling_hex>"`` where ``side`` is the sibling's position
        relative to the running hash.

        Raises:
            IndexError: If ``index`` is out of range or the tree is empty.
        """
        if not 0 <= index < len(self._leaves):
            raise IndexError(f"leaf index {index} out of range ({len(self._leaves)} leaves)")
        proof: list[str] = []
        i = index
        for level in self._levels[:-1]:
            if i % 2 == 0 and i + 1 < len(level):
                proof.append(f"right:{level[i + 1]}")
            elif i % 2 == 1:
                proof.append(f"left:{level[i - 1]}")
            # odd promoted node: no sibling at this level
            i //= 2
        return proof

    @staticmethod
    def verify_inclusion(leaf_hash: str, proof: list[str], root: str) -> bool:
        """Verify that ``leaf_hash`` is included under ``root`` given ``proof``.

        Args:
            leaf_hash: The claimed leaf digest (64-char hex).
            proof: Sibling list as produced by :meth:`inclusion_proof`.
            root: The Merkle root to check against.

        Returns:
            True iff replaying the proof from the leaf reproduces ``root``.
            Any malformed element, bad hex, or mismatch returns False.
        """
        if not root or len(leaf_hash) != 64:
            return False
        try:
            running = leaf_hash
            for element in proof:
                side, sep, sibling = element.partition(":")
                if not sep or side not in ("left", "right") or len(sibling) != 64:
                    return False
                running = (
                    _hash_pair(sibling, running)
                    if side == "left"
                    else _hash_pair(running, sibling)
                )
        except ValueError:  # non-hex input anywhere in the proof
            return False
        return _hmac.compare_digest(running, root)
