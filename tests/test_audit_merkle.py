# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the audit Merkle tree (crp/security/audit_merkle.py).

Includes a hand-computed known-answer test for a 4-leaf tree, inclusion-proof
roundtrips at every index, and tamper detection (flipped leaf, wrong root,
malformed proofs). Stdlib only — no optional dependencies.
"""

from __future__ import annotations

import hashlib

import pytest

from crp.security.audit_merkle import MerkleTree


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _pair(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hexdigest()


LEAVES4 = [_sha(f"leaf-{i}") for i in range(4)]


class TestKnownAnswer:
    def test_four_leaf_root_hand_computed(self) -> None:
        # Hand computation following the documented scheme:
        # internal node = sha256(bytes.fromhex(left) + bytes.fromhex(right)).
        n01 = _pair(LEAVES4[0], LEAVES4[1])
        n23 = _pair(LEAVES4[2], LEAVES4[3])
        expected_root = _pair(n01, n23)
        tree = MerkleTree(LEAVES4)
        assert tree.root() == expected_root
        # Pinned literal so the scheme can never drift silently.
        assert tree.root() == (
            "476c4a255bbaa3fa397182c77cb1bc85"
            "be71aa10349349f67e5c2bdd0453bfa0"
        )

    def test_root_stable_across_instances(self) -> None:
        assert MerkleTree(LEAVES4).root() == MerkleTree(list(LEAVES4)).root()


class TestInclusionProofs:
    def test_every_leaf_verifies(self) -> None:
        tree = MerkleTree(LEAVES4)
        for i, leaf in enumerate(LEAVES4):
            proof = tree.inclusion_proof(i)
            assert MerkleTree.verify_inclusion(leaf, proof, tree.root())

    def test_odd_leaf_count_promotes(self) -> None:
        leaves = [_sha(f"odd-{i}") for i in range(5)]
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            assert MerkleTree.verify_inclusion(leaf, tree.inclusion_proof(i), tree.root())

    def test_single_leaf_empty_proof(self) -> None:
        tree = MerkleTree([LEAVES4[0]])
        assert tree.root() == LEAVES4[0]
        assert tree.inclusion_proof(0) == []
        assert MerkleTree.verify_inclusion(LEAVES4[0], [], tree.root())

    def test_proof_out_of_range_raises(self) -> None:
        tree = MerkleTree(LEAVES4)
        with pytest.raises(IndexError):
            tree.inclusion_proof(4)


class TestTamperDetection:
    def test_flipped_leaf_fails(self) -> None:
        tree = MerkleTree(LEAVES4)
        proof = tree.inclusion_proof(2)
        forged = _sha("leaf-FORGED")
        assert not MerkleTree.verify_inclusion(forged, proof, tree.root())

    def test_wrong_root_fails(self) -> None:
        tree = MerkleTree(LEAVES4)
        other = MerkleTree([_sha("a"), _sha("b")])
        proof = tree.inclusion_proof(0)
        assert not MerkleTree.verify_inclusion(LEAVES4[0], proof, other.root())

    def test_swapped_proof_fails(self) -> None:
        tree = MerkleTree(LEAVES4)
        proof_a = tree.inclusion_proof(0)
        proof_b = tree.inclusion_proof(1)
        assert not MerkleTree.verify_inclusion(LEAVES4[0], proof_b, tree.root())
        assert not MerkleTree.verify_inclusion(LEAVES4[1], proof_a, tree.root())

    def test_malformed_proof_elements_fail(self) -> None:
        tree = MerkleTree(LEAVES4)
        assert not MerkleTree.verify_inclusion(LEAVES4[0], ["bogus"], tree.root())
        assert not MerkleTree.verify_inclusion(
            LEAVES4[0], [f"middle:{LEAVES4[1]}"], tree.root()
        )
        assert not MerkleTree.verify_inclusion(
            LEAVES4[0], ["right:not-hex"], tree.root()
        )

    def test_empty_tree_has_empty_root_and_no_proofs(self) -> None:
        tree = MerkleTree([])
        assert tree.root() == ""
        assert tree.leaf_count == 0
        with pytest.raises(IndexError):
            tree.inclusion_proof(0)
        assert not MerkleTree.verify_inclusion(LEAVES4[0], [], "")

    def test_invalid_leaf_rejected(self) -> None:
        with pytest.raises(ValueError):
            MerkleTree(["not-a-hash"])
        with pytest.raises(ValueError):
            MerkleTree(["ab" * 16])  # 64 hex chars? no — 32; must fail


class TestAuditTrailIntegration:
    def test_tree_over_real_trail_entries(self) -> None:
        from crp.security.audit_trail import ComplianceAuditTrail

        trail = ComplianceAuditTrail()
        for i in range(6):
            trail.record("compliance.data_accessed", session_id="s", data={"i": i})
        entries = trail.query()
        tree = MerkleTree([e.entry_hash for e in entries])
        for i, e in enumerate(entries):
            assert MerkleTree.verify_inclusion(
                e.entry_hash, tree.inclusion_proof(i), tree.root()
            )
