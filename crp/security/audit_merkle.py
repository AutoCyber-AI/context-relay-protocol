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

Domain separation (§6.4.2, opt-in): pass ``domain=b"my-app"`` to hash
leaves as ``sha256(domain + b"\\x00" + leaf)`` and internal nodes as
``sha256(domain + b"\\x01" + left + right)``. This closes the
second-preimage gap between leaf pre-images and internal nodes; verifiers
must pass the same ``domain``. The default (``None``) preserves the
original scheme for backward compatibility with already-anchored roots.

Consistency proofs (§6.4.2): :meth:`MerkleTree.consistency_proof` proves
that a previously anchored root over ``m`` leaves is a prefix commitment
of the current tree over ``n`` leaves — i.e. the log only ever *appended*.
This is what makes tail truncation (delete the last N entries and present
the remainder) detectable between two successive anchors; a verifier calls
:meth:`MerkleTree.verify_consistency` with the old root/count, the new
root/count, and the proof.

Proof encoding: a proof is a list of ``"<side>:<sibling_hex>"`` strings,
ordered leaf-to-root, where ``side`` is ``"left"`` or ``"right"`` — the
position of the *sibling* relative to the running hash. The encoding is
self-contained: :func:`MerkleTree.verify_inclusion` needs no index or leaf
count, which makes proofs safe to ship as standalone receipts. Consistency
proofs are plain sibling-hash lists consumed from the end.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac


def _hash_pair(left_hex: str, right_hex: str, domain: bytes | None = None) -> str:
    """Internal node hash: SHA-256 over the concatenated raw child digests.

    With *domain* set, the node is domain-separated:
    ``sha256(domain + b"\\x01" + left + right)`` (§6.4.2).
    """
    if domain is None:
        return hashlib.sha256(
            bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
        ).hexdigest()
    return hashlib.sha256(
        domain + b"\x01" + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    ).hexdigest()


def _hash_leaf(leaf_hex: str, domain: bytes | None = None) -> str:
    """Leaf digest under *domain* (identity when domain is None)."""
    if domain is None:
        return leaf_hex
    return hashlib.sha256(domain + b"\x00" + bytes.fromhex(leaf_hex)).hexdigest()


def _largest_pow2_below(n: int) -> int:
    """Largest power of two strictly smaller than *n* (n >= 2)."""
    return 1 << ((n - 1).bit_length() - 1)


class MerkleTree:
    """Binary Merkle tree over hex-encoded SHA-256 leaf hashes.

    Args:
        leaf_hashes: Leaf digests (64-char hex, e.g. audit ``entry_hash``
            values) in trail order.
        domain: Optional domain-separation tag (§6.4.2). When set, leaves
            and internal nodes are re-hashed under the domain; verifiers
            must pass the same tag. Default preserves the legacy scheme.

    Raises:
        ValueError: If any leaf is not a 64-char hex string.
    """

    def __init__(self, leaf_hashes: list[str], *, domain: bytes | None = None) -> None:
        for leaf in leaf_hashes:
            if not isinstance(leaf, str) or len(leaf) != 64:
                raise ValueError(f"leaf hash must be 64-char hex, got {leaf!r:.80}")
            bytes.fromhex(leaf)  # raises ValueError on non-hex input
        self._domain = domain
        self._leaves = [_hash_leaf(leaf, domain) for leaf in leaf_hashes]
        # levels[0] = leaves, levels[-1] = [root]; odd nodes promoted unchanged
        self._levels: list[list[str]] = [self._leaves]
        while len(self._levels[-1]) > 1:
            level = self._levels[-1]
            nxt = [
                _hash_pair(level[i], level[i + 1], domain)
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
    def verify_inclusion(
        leaf_hash: str,
        proof: list[str],
        root: str,
        *,
        domain: bytes | None = None,
    ) -> bool:
        """Verify that ``leaf_hash`` is included under ``root`` given ``proof``.

        Args:
            leaf_hash: The claimed leaf digest (64-char hex).
            proof: Sibling list as produced by :meth:`inclusion_proof`.
            root: The Merkle root to check against.
            domain: Domain-separation tag used to build the tree (§6.4.2);
                must match the tree's tag.

        Returns:
            True iff replaying the proof from the leaf reproduces ``root``.
            Any malformed element, bad hex, or mismatch returns False.
        """
        if not root or len(leaf_hash) != 64:
            return False
        try:
            running = _hash_leaf(leaf_hash, domain)
            for element in proof:
                side, sep, sibling = element.partition(":")
                if not sep or side not in ("left", "right") or len(sibling) != 64:
                    return False
                running = (
                    _hash_pair(sibling, running, domain)
                    if side == "left"
                    else _hash_pair(running, sibling, domain)
                )
        except ValueError:  # non-hex input anywhere in the proof
            return False
        return _hmac.compare_digest(running, root)

    # ------------------------------------------------------------- consistency

    def consistency_proof(self, old_count: int) -> list[str]:
        """Proof that the first ``old_count`` leaves commit to a tree whose
        root an auditor already holds — i.e. this tree is a pure *extension*
        of the anchored one (append-only evolution, §6.4.2, RFC 6962 §2.1.2).

        Combined with :meth:`verify_consistency`, this detects tail
        truncation: an anchor at ``old_count`` leaves plus the current root
        at ``n`` leaves can only be bridged by a valid proof if every entry
        up to the anchor is still present, untouched, in order.

        The proof is a flat list of subtree-root hashes (the RFC 6962
        ``PROOF(m, D[n])``); :meth:`verify_consistency` consumes it from the
        END (each recursion level appends its commitment last).

        Raises:
            IndexError: If ``old_count`` is out of range.
        """
        n = len(self._leaves)
        if not 1 <= old_count <= n:
            raise IndexError(f"subtree size {old_count} out of range (1..{n})")
        if old_count == n:
            return []
        proof: list[str] = []
        self._consistency(old_count, n, proof, 0, True)
        return proof

    def _consistency(
        self, m: int, n: int, proof: list[str], start: int, b: bool
    ) -> None:
        """Append the RFC 6962 SUBPROOF(m, D[start:start+n], b) hashes.

        ``b`` mirrors the RFC flag: ``True`` for the originally requested
        subtree (its root is known to the verifier — nothing appended at the
        base case); ``False`` for subtrees split off below an old/new
        boundary (their old-part root must be supplied — appended at the
        base case).
        """
        if m == n:
            if not b:
                proof.append(self._range_root(start, m))
            return
        k = _largest_pow2_below(n)
        if m <= k:
            self._consistency(m, k, proof, start, b)
            proof.append(self._range_root(start + k, n - k))
        else:
            self._consistency(m - k, n - k, proof, start + k, False)
            proof.append(self._range_root(start, k))

    def _range_root(self, start: int, count: int) -> str:
        """Root of the subtree over leaves[start:start+count] (must align to
        the pairwise construction — guaranteed for the ranges produced by
        :meth:`_consistency`)."""
        if count == 1:
            return self._leaves[start]
        k = _largest_pow2_below(count)
        left = self._range_root(start, k)
        right = self._range_root(start + k, count - k)
        return _hash_pair(left, right, self._domain)

    @staticmethod
    def verify_consistency(
        old_root: str,
        old_count: int,
        new_root: str,
        new_count: int,
        proof: list[str],
        *,
        domain: bytes | None = None,
    ) -> bool:
        """Verify that ``old_root`` commits to the first ``old_count`` leaves
        of the tree whose root is ``new_root`` over ``new_count`` leaves.

        Replays *proof* (consumed from the end, as produced by
        :meth:`consistency_proof`), recomputing both the old portion's root
        and the full root. Verification succeeds only when every proof
        element is consumed, the recomputed full root equals ``new_root``,
        AND the recomputed old-portion root equals ``old_root`` — so a
        truncated, extended, reordered, or substituted chain fails closed.
        """
        if not (1 <= old_count <= new_count):
            return False
        if old_count == new_count:
            return not proof and _hmac.compare_digest(old_root, new_root)
        remaining = list(proof)
        try:
            result = MerkleTree._recompute_consistency(
                old_count, new_count, remaining, old_root, domain
            )
        except ValueError:  # non-hex proof element
            return False
        if result is None or remaining:
            return False
        old_part, full = result
        return (
            _hmac.compare_digest(old_part, old_root)
            and _hmac.compare_digest(full, new_root)
        )

    @staticmethod
    def _recompute_consistency(
        m: int,
        n: int,
        proof: list[str],
        bind: str | None,
        domain: bytes | None,
    ) -> tuple[str, str] | None:
        """Recompute (old-part root, full root) of D[0:n) from proof tail.

        *bind* is the anchored root when the old portion of this range is
        known (the RFC ``b=true`` case); ``None`` when the old-part root
        must be supplied by the proof (``b=false``). Returns None when the
        proof is malformed or exhausted early.
        """
        if m == n:
            if bind is not None:
                return (bind, bind)
            if not proof:
                return None
            sub = proof.pop()
            return (sub, sub)
        if not proof:
            return None
        k = _largest_pow2_below(n)
        if m <= k:
            right = proof.pop()
            left = MerkleTree._recompute_consistency(m, k, proof, bind, domain)
            if left is None:
                return None
            old_l, full_l = left
            return (old_l, _hash_pair(full_l, right, domain))
        left = proof.pop()
        right = MerkleTree._recompute_consistency(m - k, n - k, proof, None, domain)
        if right is None:
            return None
        old_r, full_r = right
        return (
            _hash_pair(left, old_r, domain),
            _hash_pair(left, full_r, domain),
        )
