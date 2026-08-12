# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Embedding defense — SQ8 quantization, XOR salting, no export (§7.11).

Protects stored embeddings from extraction:
- SQ8 quantization: float32 → int8 (reduces precision, saves memory)
- XOR salting: 4-byte salt per embedding (masks raw values)
- No embedding export: export_state() exports text only
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ProtectedEmbedding:
    """Embedding with SQ8 quantization and XOR salt applied."""

    quantized: bytes  # SQ8 int8 values
    salt: bytes  # 4-byte XOR salt
    dimensions: int
    scale: float  # quantization scale factor
    zero_point: float  # quantization zero point

    def to_dict(self) -> dict[str, Any]:
        """Serialize the protected embedding to a base64-encoded dict."""
        import base64
        return {
            "quantized": base64.b64encode(self.quantized).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "dimensions": self.dimensions,
            "scale": self.scale,
            "zero_point": self.zero_point,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProtectedEmbedding:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``ProtectedEmbedding``.
        """
        import base64
        return cls(
            quantized=base64.b64decode(data["quantized"]),
            salt=base64.b64decode(data["salt"]),
            dimensions=data["dimensions"],
            scale=data.get("scale", 1.0),
            zero_point=data.get("zero_point", 0.0),
        )


class EmbeddingDefense:
    """SQ8 quantization + XOR salting for embedding protection (§7.11).

    Usage:
        defense = EmbeddingDefense()
        protected = defense.protect([0.1, 0.2, -0.3, ...])
        recovered = defense.recover(protected)
        # recovered ≈ original (within quantization error)

        # export_state: embeddings are stripped
        safe_data = defense.strip_embeddings_for_export(state_dict)
    """

    def __init__(self, salt: bytes | None = None) -> None:
        # Default: random 4-byte salt (§6H.2)
        self._default_salt = salt or os.urandom(4)

    def protect(
        self,
        embedding: list[float],
        salt: bytes | None = None,
    ) -> ProtectedEmbedding:
        """Apply SQ8 quantization + XOR salting (§6H.1, §6H.2).

        SQ8: Maps float32 range [min, max] → int8 [-128, 127].
        XOR: Applies 4-byte repeating XOR mask to quantized bytes.
        """
        if not embedding:
            return ProtectedEmbedding(
                quantized=b"", salt=salt or self._default_salt,
                dimensions=0, scale=1.0, zero_point=0.0,
            )

        use_salt = salt or self._default_salt

        # SQ8 quantization (§6H.1)
        min_val = min(embedding)
        max_val = max(embedding)
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1.0  # avoid division by zero

        scale = val_range / 255.0  # map to uint8 range, then shift to int8
        zero_point = min_val

        quantized = bytearray(len(embedding))
        for i, v in enumerate(embedding):
            # Quantize to int8 [-128, 127]
            q = round((v - zero_point) / scale) - 128
            q = max(-128, min(127, q))
            quantized[i] = q & 0xFF  # store as unsigned byte

        # XOR salting (§6H.2)
        salted = bytearray(len(quantized))
        salt_len = len(use_salt)
        for i, b in enumerate(quantized):
            salted[i] = b ^ use_salt[i % salt_len]

        return ProtectedEmbedding(
            quantized=bytes(salted),
            salt=use_salt,
            dimensions=len(embedding),
            scale=scale,
            zero_point=zero_point,
        )

    def recover(self, protected: ProtectedEmbedding) -> list[float]:
        """Recover embedding from SQ8 + XOR protected form.

        Returns approximate original values (quantization introduces error).
        """
        if protected.dimensions == 0:
            return []

        # Remove XOR salt
        salt_len = len(protected.salt)
        desalted = bytearray(len(protected.quantized))
        for i, b in enumerate(protected.quantized):
            desalted[i] = b ^ protected.salt[i % salt_len]

        # Dequantize from int8
        result: list[float] = []
        for b in desalted:
            # Convert unsigned byte back to signed int8
            q = b if b < 128 else b - 256
            # Reverse quantization
            v = (q + 128) * protected.scale + protected.zero_point
            result.append(v)

        return result

    @staticmethod
    def strip_embeddings_for_export(state_dict: dict[str, Any]) -> dict[str, Any]:
        """Strip all embeddings from state dict for export (§6H.3).

        export_state() must export text only — no embeddings.
        """
        import copy
        safe = copy.deepcopy(state_dict)

        # Strip from facts
        facts = safe.get("warm_store", {}).get("facts", {})
        for _fid, fdata in facts.items():
            fdata.pop("embedding", None)
            fdata.pop("protected_embedding", None)
            fdata["has_embedding"] = False

        # Strip any top-level embedding data
        safe.pop("embeddings", None)
        safe.pop("ann_index", None)

        return safe
