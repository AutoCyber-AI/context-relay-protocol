# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""ConfigurationResolver — 5-layer hierarchy, feature flags (§06 §6.12).

Resolution order (later overrides prior):
  Layer 1: Hardcoded defaults (this file)
  Layer 2: Environment variables (CRP_* prefix)
  Layer 3: Config file (YAML/.env) — future
  Layer 4: Client() init kwargs
  Layer 5: Runtime configure() call
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("crp.core.config")

# ---------------------------------------------------------------------------
# Defaults (Layer 1)
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    # Master switch — True by default for standalone SDK usage.
    # Set CRP_ENABLED=false to disable when embedded in a host framework.
    "enabled": True,
    # Limits
    "max_continuations": 50,
    "max_dispatch_rate": 60,
    "session_timeout": 86400,
    "ingest_quarantine": 1,
    # Resource
    "max_ram_mb": 512,
    "max_model_ram_mb": 300,
    "max_threads": 2,
    "process_priority": "below_normal",
    "memory_budget_mb": 512,
    "idle_model_timeout_s": 300.0,
    # Behaviour
    "log_envelopes": False,
    "encrypt_cold_state": True,
    "default_role": "OPERATOR",
    # Security
    "binding_secret": "",
    # Budget caps (immutable) — 0 means unlimited
    "max_windows_per_session": 0,
    "max_total_input_tokens": 0,
    "max_total_output_tokens": 0,
    # Latency
    "max_envelope_latency_ms": 500,
    "max_extraction_latency_ms": 200,
    "max_windows_per_minute": 0,
    # Observability
    "telemetry_path": "",
    # Overhead & parallelism
    "overhead_cap_pct": 15.0,
    "parallel_max_concurrent": 4,
    # Extraction stages — which stages are enabled at init
    "enable_stage_3": True,   # GLiNER zero-shot NER
    "enable_stage_4": True,   # UIE relation extraction
    "enable_stage_5": True,   # Discourse markers
    "enable_stage_6": False,  # LLM-assisted (costly, rare)
    # Model loading — eager loads all ML models at init (faster first call,
    # slower startup).  Default False = lazy load on first use (<1s startup).
    "eager_load_models": False,
    # Dispatch timeout (seconds) — wall-time cap per continuation loop
    "dispatch_timeout": 3600,
    # Pause (seconds) between continuation windows — gives slow local
    # inference servers (LM Studio, llama.cpp) time to reset between
    # completions. 0.0 disables the pause (recommended for tests and
    # hosted providers). Set to ~2.0 when dispatching against a local
    # LM Studio / Ollama endpoint that exhibits request-overlap issues.
    "continuation_pause_s": 0.0,
    # Input-side continuation strategy (§4.6).
    #   "auto_ingest"  — legacy: chunk input externally, extract facts, replace
    #                    task with a synthesized summary (default, preserves
    #                    existing behaviour).
    #   "multi_window" — use full LLM windows to process each input chunk and
    #                    relay extracted facts between windows.
    "input_continuation_mode": "auto_ingest",
}

# Fields set at init that CANNOT change after session start
_IMMUTABLE_FIELDS: frozenset[str] = frozenset({
    "max_windows_per_session",
    "max_total_input_tokens",
    "max_total_output_tokens",
    "binding_secret",
    "session_timeout",
})

# Environment variable prefix
_ENV_PREFIX = "CRP_"

# Mapping from env-var suffix to config key
_ENV_MAP: dict[str, str] = {
    "ENABLED": "enabled",
    "LOG_ENVELOPES": "log_envelopes",
    "MAX_CONTINUATIONS": "max_continuations",
    "MAX_RAM_MB": "max_ram_mb",
    "MAX_MODEL_RAM_MB": "max_model_ram_mb",
    "MAX_THREADS": "max_threads",
    "PROCESS_PRIORITY": "process_priority",
    "BINDING_SECRET": "binding_secret",
    "SESSION_TIMEOUT": "session_timeout",
    "DEFAULT_ROLE": "default_role",
    "ENCRYPT_COLD_STATE": "encrypt_cold_state",
    "MAX_DISPATCH_RATE": "max_dispatch_rate",
    "INGEST_QUARANTINE": "ingest_quarantine",
    "ENABLE_STAGE_3": "enable_stage_3",
    "ENABLE_STAGE_4": "enable_stage_4",
    "ENABLE_STAGE_5": "enable_stage_5",
    "ENABLE_STAGE_6": "enable_stage_6",
    "EAGER_LOAD_MODELS": "eager_load_models",
    "DISPATCH_TIMEOUT": "dispatch_timeout",
    "INPUT_CONTINUATION_MODE": "input_continuation_mode",
}

_BOOL_KEYS = frozenset({"enabled", "log_envelopes", "encrypt_cold_state",
                         "enable_stage_3", "enable_stage_4", "enable_stage_5",
                         "enable_stage_6", "eager_load_models"})
_INT_KEYS = frozenset({
    "max_continuations", "max_dispatch_rate", "session_timeout",
    "ingest_quarantine", "max_ram_mb", "max_model_ram_mb", "max_threads",
    "max_windows_per_session", "max_total_input_tokens",
    "max_total_output_tokens", "max_envelope_latency_ms",
    "max_extraction_latency_ms", "max_windows_per_minute",
    "dispatch_timeout",
})


def _parse_env_value(key: str, raw: str) -> Any:
    """Parse a raw environment variable string to the correct type."""
    if key in _BOOL_KEYS:
        return raw.lower() in ("1", "true", "yes")
    if key in _INT_KEYS:
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid integer for %s: %r — using default", key, raw)
            return None  # Will be filtered out, falling through to default
    return raw


@dataclass
class CRPConfig:
    """Resolved CRP configuration.

    Constructed via :class:`ConfigurationResolver`.
    """

    _values: dict[str, Any] = field(default_factory=dict)
    _locked: bool = False

    def get(self, key: str, default: Any = None) -> Any:
        """Return the resolved config value for *key*, or *default* if absent."""
        return self._values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    # Convenience typed accessors for common flags
    @property
    def enabled(self) -> bool:
        """Return the enabled."""
        return bool(self._values.get("enabled", False))

    @property
    def max_continuations(self) -> int:
        """Return the max continuations."""
        return int(self._values.get("max_continuations", 50))

    @property
    def log_envelopes(self) -> bool:
        """Return the log envelopes."""
        return bool(self._values.get("log_envelopes", False))

    @property
    def max_dispatch_rate(self) -> int:
        """Return the max dispatch rate."""
        return int(self._values.get("max_dispatch_rate", 60))

    @property
    def session_timeout(self) -> int:
        """Return the session timeout."""
        return int(self._values.get("session_timeout", 86400))

    @property
    def max_windows_per_session(self) -> int:
        """Return the max windows per session."""
        return int(self._values.get("max_windows_per_session", 0))

    @property
    def max_total_input_tokens(self) -> int:
        """Return the max total input tokens."""
        return int(self._values.get("max_total_input_tokens", 0))

    @property
    def max_total_output_tokens(self) -> int:
        """Return the max total output tokens."""
        return int(self._values.get("max_total_output_tokens", 0))

    def lock(self) -> None:
        """Lock immutable fields — called after session starts."""
        self._locked = True

    def update(self, overrides: dict[str, Any]) -> None:
        """Apply mutable-only overrides (Layer 5: runtime configure).

        Raises ValueError if attempting to change an immutable field
        after lock().
        """
        for key, value in overrides.items():
            if self._locked and key in _IMMUTABLE_FIELDS:
                msg = f"Cannot change immutable config '{key}' after session start"
                raise ValueError(msg)
            self._values[key] = value


_VALID_PROCESS_PRIORITIES = frozenset({
    "idle", "below_normal", "normal", "above_normal", "high",
})
_VALID_ROLES = frozenset({
    "OBSERVER", "OPERATOR", "ADMIN",
})

# Validation bounds: (min, max) inclusive.  None means unbounded.
_INT_BOUNDS: dict[str, tuple[int | None, int | None]] = {
    "max_continuations": (0, 10_000),
    "max_dispatch_rate": (1, 10_000),
    "session_timeout": (0, 604_800),       # 0 s – 7 days (0 = immediate expiry)
    "ingest_quarantine": (0, 60),
    "max_ram_mb": (1, 65_536),
    "max_model_ram_mb": (1, 65_536),
    "max_threads": (1, 64),
    "max_windows_per_session": (0, 1_000_000),  # 0 = unlimited
    "max_total_input_tokens": (0, 2**31),
    "max_total_output_tokens": (0, 2**31),
    "max_envelope_latency_ms": (0, 60_000),
    "max_extraction_latency_ms": (0, 60_000),
    "max_windows_per_minute": (0, 10_000),
    "parallel_max_concurrent": (1, 128),
    "dispatch_timeout": (10, 86_400),  # 10s – 24h
    "memory_budget_mb": (1, 65_536),
}
_FLOAT_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "overhead_cap_pct": (0.0, 100.0),
    "idle_model_timeout_s": (0.0, 86_400.0),
    "continuation_pause_s": (0.0, 60.0),
}


def _validate_config(values: dict[str, Any]) -> None:
    """Validate resolved configuration values.  Raises ValueError on bad input."""
    errors: list[str] = []
    for key, (lo, hi) in _INT_BOUNDS.items():
        val = values.get(key)
        if val is None:
            continue
        try:
            val = int(val)
        except (TypeError, ValueError):
            errors.append(f"{key}: expected int, got {type(val).__name__}")
            continue
        if lo is not None and val < lo:
            errors.append(f"{key}: {val} < minimum {lo}")
        if hi is not None and val > hi:
            errors.append(f"{key}: {val} > maximum {hi}")

    for key, (lo, hi) in _FLOAT_BOUNDS.items():
        val = values.get(key)
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            errors.append(f"{key}: expected number, got {type(val).__name__}")
            continue
        if lo is not None and val < lo:
            errors.append(f"{key}: {val} < minimum {lo}")
        if hi is not None and val > hi:
            errors.append(f"{key}: {val} > maximum {hi}")

    pp = values.get("process_priority")
    if pp is not None and pp not in _VALID_PROCESS_PRIORITIES:
        errors.append(
            f"process_priority: '{pp}' not in {sorted(_VALID_PROCESS_PRIORITIES)}"
        )

    role = values.get("default_role")
    if role is not None and role not in _VALID_ROLES:
        errors.append(f"default_role: '{role}' not in {sorted(_VALID_ROLES)}")

    if errors:
        raise ValueError(
            "CRP configuration validation failed:\n  - " + "\n  - ".join(errors)
        )


class ConfigurationResolver:
    """Resolve configuration through the 5-layer hierarchy."""

    @staticmethod
    def _read_config_file() -> dict[str, Any]:
        """Layer 3: Read config from file (YAML/JSON).

        Search order:
          1. ``CRP_CONFIG_FILE`` env var (explicit path)
          2. ``~/.crp/config.yaml`` / ``~/.crp/config.json``
          3. ``.crp.yaml`` / ``.crp.json`` in CWD
        """
        explicit = os.environ.get("CRP_CONFIG_FILE")
        if explicit:
            p = Path(explicit)
            if not p.is_file():
                logger.warning("CRP_CONFIG_FILE=%s does not exist — skipping", explicit)
                return {}
            return ConfigurationResolver._parse_config_path(p)

        candidates = [
            Path.home() / ".crp" / "config.yaml",
            Path.home() / ".crp" / "config.yml",
            Path.home() / ".crp" / "config.json",
            Path.cwd() / ".crp.yaml",
            Path.cwd() / ".crp.yml",
            Path.cwd() / ".crp.json",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return ConfigurationResolver._parse_config_path(candidate)
        return {}

    @staticmethod
    def _parse_config_path(path: Path) -> dict[str, Any]:
        """Parse a YAML or JSON config file, returning only known keys."""
        raw_text = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        try:
            if suffix in (".yaml", ".yml"):
                try:
                    import yaml  # type: ignore[import-untyped]
                    data = yaml.safe_load(raw_text) or {}
                except ImportError:
                    logger.warning("PyYAML not installed — cannot read %s", path)
                    return {}
            elif suffix == ".json":
                data = json.loads(raw_text)
            else:
                logger.warning("Unsupported config file format: %s", path)
                return {}
        except Exception:
            logger.exception("Failed to parse config file %s", path)
            return {}

        if not isinstance(data, dict):
            logger.warning("Config file %s did not parse as a dict — ignoring", path)
            return {}

        # Only accept known config keys to prevent injection of arbitrary values
        known_keys = set(_DEFAULTS)
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in known_keys:
                result[key] = _parse_env_value(key, str(value)) if isinstance(value, str) else value
        return result

    def resolve(self, **init_kwargs: Any) -> CRPConfig:
        """Build a CRPConfig from layers 1-4.

        Args:
            **init_kwargs: Layer 4 overrides from Client() constructor.

        Raises:
            ValueError: If any resolved value is out of bounds.
        """
        # Layer 1: Hardcoded defaults
        values = dict(_DEFAULTS)

        # Layer 2: Environment variables
        for env_suffix, config_key in _ENV_MAP.items():
            env_var = f"{_ENV_PREFIX}{env_suffix}"
            raw = os.environ.get(env_var)
            if raw is not None:
                values[config_key] = _parse_env_value(config_key, raw)

        # Layer 3: Config file (YAML/JSON)
        file_values = self._read_config_file()
        values.update(file_values)

        # Layer 4: Client() init kwargs
        unknown_keys = [k for k in init_kwargs if k not in values]
        if unknown_keys:
            logger.warning("Unknown config keys ignored (§audit L3): %s", unknown_keys)
        for key, value in init_kwargs.items():
            if key in values:
                values[key] = value

        _validate_config(values)

        return CRPConfig(_values=values)
