# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unified Configuration — one optional ``crp.config.yaml`` governs everything (SPEC-037).

Implements the 5-layer configuration hierarchy required by SPEC-037 §3:
  Layer 1: Hardcoded defaults (this file)
  Layer 2: Environment variables (``CRP_*`` prefix)
  Layer 3: Config file (``crp.config.yaml``)
  Layer 4: ``Client()`` init kwargs
  Layer 5: Runtime ``configure()`` call

The entire config is optional — every field has a default. The config hash
(``CRP-Config-Hash``) is emitted when a config file is loaded.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crp.config_schema import validate_config

logger = logging.getLogger("crp.config")


# ── Defaults (Layer 1) ─────────────────────────────────────────────────────


_DEFAULT_CONFIG: dict[str, Any] = {
    "version": "4",
    "model": {
        "default": "",
        "fallback": "",
        "providers": {},
    },
    "safety": {
        "profile": "balanced",
        "settings": {},
        "coverage": {},
        "checkpoints": [],
        "custom_rules": [],
    },
    "context": {
        "mode": "auto",
        "depth": "auto",
        "windows": {
            "max": 10,
            "token_budget": 1200,
        },
        "retrieval": {
            "min_relevance": 0.55,
            "graph_retrieval": True,
            "max_hops": 2,
            "recency_weighting": True,
        },
        "storage": {
            "rolling_log_size": 50,
            "hot_cache_size": 1000,
            "backend": "memory",
        },
    },
    "knowledge": {
        "sources": [],
        "embedding_model": "all-MiniLM-L6-v2",
        "auto_ingest": False,
    },
    "audit": {
        "enabled": True,
        "retention_days": 90,
        "forward_url": "",
    },
    "gateway": {
        "url": "",
        "api_key": "",
    },
    "infrastructure": {
        "audit_sink": "memory",          # memory | file | http | none
        "audit_endpoint": "",
        "audit_path": "",
        "database_url": "",
        "storage_backend": "memory",     # memory | sqlite | redis | s3
        "storage_path": "",
        "redis_url": "",
        "s3_bucket": "",
        "s3_prefix": "crp/",
        "model_cache_dir": "",
        "model_device": "auto",
        "telemetry_endpoint": "",
    },
}


# ── CRPConfig dataclass ────────────────────────────────────────────────────


@dataclass
class CRPConfig:
    """Unified CRP configuration — one object governs everything (SPEC-037).

    Load from file::

        config = CRPConfig.load("crp.config.yaml")

    Or build programmatically::

        config = CRPConfig()
        config.set("safety.profile", "strict")
    """

    _data: dict[str, Any] = field(default_factory=lambda: _deep_copy(_DEFAULT_CONFIG))
    _source_path: str = ""

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str = "crp.config.yaml") -> CRPConfig:
        """Load from a YAML or JSON file. Falls back to defaults if file missing.

        Args:
            path: Path to the config file (YAML or JSON).

        Returns:
            A ``CRPConfig`` instance with defaults merged and validated.
        """
        p = Path(path)
        if not p.exists():
            logger.debug("Config file not found at %s — using defaults", path)
            return cls()

        text = p.read_text(encoding="utf-8")
        try:
            import yaml
            data = yaml.safe_load(text) or {}
        except Exception:
            # Fallback to JSON if yaml not available or parse fails
            data = json.loads(text)

        # Merge with defaults (shallow-merge top level, deep-merge nested)
        merged = _deep_merge(_deep_copy(_DEFAULT_CONFIG), data)

        # Validate
        errors = validate_config(merged)
        if errors:
            for err in errors:
                logger.warning("Config validation: %s", err)

        inst = cls(_data=merged, _source_path=str(p.resolve()))
        logger.info("Loaded CRP config from %s", path)
        return inst

    def save(self, path: str | None = None) -> None:
        """Persist current config to disk.

        Args:
            path: Destination path. Defaults to the loaded source path or
                ``crp.config.yaml``.
        """
        target = path or self._source_path or "crp.config.yaml"
        p = Path(target)
        p.write_text(self.to_yaml(), encoding="utf-8")
        logger.info("Saved CRP config to %s", target)

    # ------------------------------------------------------------------
    # Get / set with dotted paths
    # ------------------------------------------------------------------

    def get(self, dotted_path: str, default: Any = None) -> Any:
        """Read a value by dotted path.

        Args:
            dotted_path: Dot-separated path such as ``context.retrieval.min_relevance``.
            default: Value returned if the path does not exist.

        Returns:
            The stored value or ``default``.
        """
        parts = dotted_path.split(".")
        node: Any = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, dotted_path: str, value: Any) -> None:
        """Write a value by dotted path, creating intermediate dicts as needed.

        Args:
            dotted_path: Dot-separated path such as ``safety.profile``.
            value: Value to store.
        """
        parts = dotted_path.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    # ------------------------------------------------------------------
    # Layer override (Layer 5: runtime)
    # ------------------------------------------------------------------

    def layer_override(self, overrides: dict[str, Any]) -> CRPConfig:
        """Return a new ``CRPConfig`` with runtime overrides applied (Layer 5).

        Args:
            overrides: Mapping of dotted paths to override values.

        Returns:
            A new immutable-style config instance.
        """
        clone = CRPConfig(_data=_deep_copy(self._data), _source_path=self._source_path)
        for key, value in overrides.items():
            clone.set(key, value)
        return clone

    # ------------------------------------------------------------------
    # Hash for header emission (SPEC-037 §5)
    # ------------------------------------------------------------------

    def get_config_hash(self) -> str:
        """Return deterministic hash for the ``CRP-Config-Hash`` header.

        Returns:
            A 32-character BLAKE2b hex digest of the canonical JSON config.
        """
        canonical = json.dumps(self._data, sort_keys=True, separators=(",", ":"))
        return hashlib.blake2b(canonical.encode(), digest_size=16).hexdigest()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Export as a plain deep-copied dict."""
        return _deep_copy(self._data)

    def to_yaml(self) -> str:
        """Export as a YAML string (JSON fallback if PyYAML is unavailable)."""
        try:
            import yaml
            return yaml.safe_dump(self._data, sort_keys=False, default_flow_style=False)
        except Exception:
            # Fallback to JSON-with-comments if yaml missing
            return f"# crp.config.yaml (JSON fallback)\n{json.dumps(self._data, indent=2)}"

    def to_json(self) -> str:
        """Export as a pretty-printed JSON string."""
        return json.dumps(self._data, indent=2)


# ── Deep-copy / deep-merge helpers ─────────────────────────────────────────


def _deep_copy(obj: Any) -> Any:
    """Recursively copy dicts and lists; return primitives unchanged."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj


def _deep_merge(base: Any, override: Any) -> Any:
    """Recursively merge ``override`` into ``base`` without mutating ``base``.

    Args:
        base: Base value (typically a dict from defaults).
        override: Override value (typically parsed from a config file).

    Returns:
        A deep-merged copy.
    """
    if isinstance(base, dict) and isinstance(override, dict):
        result = _deep_copy(base)
        for k, v in override.items():
            result[k] = _deep_merge(result.get(k), v) if k in result and isinstance(result[k], dict) else v
        return result
    return override if override is not None else base
