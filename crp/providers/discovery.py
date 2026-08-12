# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Local LLM discovery — detect running models and their capabilities (§6.2).

CRP can *introspect the inference layer it is about to govern*. Before a single
token is dispatched, :func:`discover_local_llms` probes the common local-LLM
runtimes (LM Studio, Ollama, llama.cpp / llama-server, and any other
OpenAI-compatible server) and reports, for every model it finds:

* the runtime serving it and the endpoint,
* whether the model is currently *loaded* into memory,
* its architecture, publisher and quantization,
* its **maximum** context length vs. the **currently loaded** context length,
* whether it advertises **tool / function calling** (MCP-compatible), and
* whether it is a **thinking / reasoning** model (extended chain-of-thought).

This matters because CRP's window budgeting, generation-reserve sizing and
tool-vs-envelope dispatch decisions all depend on the *real* capabilities of
the model actually answering — not on what a config file claims.

Everything here uses only the Python standard library (``urllib``); no runtime
needs to be installed for discovery to work.

Usage::

    from crp.providers.discovery import discover_local_llms

    report = discover_local_llms()
    for model in report.loaded_models:
        print(model.id, model.runtime, model.max_context_length,
              "tools" if model.supports_tools else "",
              "reasoning" if model.is_reasoning_model else "")
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.providers.discovery")

__all__ = [
    "RuntimeKind",
    "ModelState",
    "DetectedModel",
    "DetectedRuntime",
    "DiscoveryReport",
    "discover_local_llms",
    "DEFAULT_ENDPOINTS",
]


class RuntimeKind(str, Enum):
    """The local inference runtime serving a model."""

    LM_STUDIO = "lmstudio"
    OLLAMA = "ollama"
    LLAMA_CPP = "llamacpp"
    OPENAI_COMPATIBLE = "openai-compatible"
    UNKNOWN = "unknown"


class ModelState(str, Enum):
    """Whether the model is resident in memory and ready to serve."""

    LOADED = "loaded"
    NOT_LOADED = "not-loaded"
    UNKNOWN = "unknown"


# ── Endpoints probed by default ─────────────────────────────────────────────
# 127.0.0.1 (not "localhost") so we hit IPv4 directly — many local servers bind
# 0.0.0.0 (IPv4) while "localhost" resolves to ::1 (IPv6) and is refused.
@dataclass(frozen=True)
class _Endpoint:
    base_url: str
    runtime: RuntimeKind


DEFAULT_ENDPOINTS: tuple[_Endpoint, ...] = (
    _Endpoint("http://127.0.0.1:1234", RuntimeKind.LM_STUDIO),     # LM Studio
    _Endpoint("http://127.0.0.1:11434", RuntimeKind.OLLAMA),       # Ollama
    _Endpoint("http://127.0.0.1:8080", RuntimeKind.LLAMA_CPP),     # llama-server
    _Endpoint("http://127.0.0.1:8000", RuntimeKind.OPENAI_COMPATIBLE),  # vLLM/TGI
)


# ── Heuristics for capability inference ─────────────────────────────────────
# Architecture / id substrings that denote an extended-reasoning ("thinking")
# model. These spend a large share of tokens on internal chain-of-thought and
# therefore need a bigger generation reserve.
_REASONING_MARKERS: tuple[str, ...] = (
    "qwen3", "qwq", "deepseek-r1", "deepseek-reason", "r1-", "-r1",
    "o1", "o3", "o4-mini", "magistral", "exaone-deep", "phi-4-reasoning",
    "phi-reasoning", "gpt-oss", "glm-z1", "glm-4.6", "reasoning", "thinking",
    "smallthinker", "marco-o1", "skywork-o1", "deephermes",
)

# Substrings that denote tool / function calling support when a runtime does
# not explicitly advertise capabilities.
_TOOL_MARKERS: tuple[str, ...] = (
    "instruct", "llama-3", "llama3", "qwen2.5", "qwen3", "mistral",
    "command-r", "hermes", "functionary", "firefunction", "gpt-4", "gpt-4o",
)


def _looks_like_reasoning(*hints: str) -> bool:
    blob = " ".join(h.lower() for h in hints if h)
    return any(marker in blob for marker in _REASONING_MARKERS)


def _looks_tool_capable(*hints: str) -> bool:
    blob = " ".join(h.lower() for h in hints if h)
    return any(marker in blob for marker in _TOOL_MARKERS)


@dataclass
class DetectedModel:
    """A model discovered on a local runtime, with its capabilities."""

    id: str
    runtime: RuntimeKind
    endpoint: str
    model_type: str = "llm"                 # llm | embeddings | vlm | ...
    state: ModelState = ModelState.UNKNOWN
    publisher: str = ""
    architecture: str = ""
    quantization: str = ""
    max_context_length: int | None = None       # model's physical ceiling
    loaded_context_length: int | None = None     # currently allocated window
    capabilities: list[str] = field(default_factory=list)
    supports_tools: bool = False                  # function / MCP tool calling
    is_reasoning_model: bool = False              # extended chain-of-thought
    is_vision_model: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_loaded(self) -> bool:
        """Return whether this object is loaded."""
        return self.state is ModelState.LOADED

    @property
    def context_utilisation(self) -> float | None:
        """Loaded window as a fraction of the model's maximum (0.0–1.0).

        ``0.03`` here means the runtime allocated only 3 % of what the model
        can actually handle — a strong signal that aggressive context
        management (CKF, continuation, windowing) is required.
        """
        if self.max_context_length and self.loaded_context_length:
            return round(self.loaded_context_length / self.max_context_length, 4)
        return None

    def to_provider(self) -> "LLMProvider | None":
        """Return a CRP provider adapter configured for this detected model.

        Returns ``None`` if the runtime kind is not recognised or the model
        is not an LLM.
        """
        if self.model_type != "llm":
            return None

        ctx = self.loaded_context_length or self.max_context_length

        if self.runtime is RuntimeKind.OLLAMA:
            from crp.providers.ollama import OllamaAdapter
            return OllamaAdapter(
                model=self.id,
                base_url=self.endpoint,
                context_size=ctx or 4096,
            )

        if self.runtime is RuntimeKind.LLAMA_CPP:
            from crp.providers.llamacpp import LlamaCppAdapter
            return LlamaCppAdapter(
                server_url=self.endpoint,
                context_size=ctx or 4096,
            )

        if self.runtime in {RuntimeKind.LM_STUDIO, RuntimeKind.OPENAI_COMPATIBLE}:
            from crp.providers.openai import OpenAIAdapter
            return OpenAIAdapter(
                model=self.id,
                api_key="not-needed",
                base_url=self.endpoint,
                context_size=ctx or 8192,
            )

        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the detected model to a dict."""
        return {
            "id": self.id,
            "runtime": self.runtime.value,
            "endpoint": self.endpoint,
            "model_type": self.model_type,
            "state": self.state.value,
            "publisher": self.publisher,
            "architecture": self.architecture,
            "quantization": self.quantization,
            "max_context_length": self.max_context_length,
            "loaded_context_length": self.loaded_context_length,
            "context_utilisation": self.context_utilisation,
            "capabilities": list(self.capabilities),
            "supports_tools": self.supports_tools,
            "is_reasoning_model": self.is_reasoning_model,
            "is_vision_model": self.is_vision_model,
        }


@dataclass
class DetectedRuntime:
    """A local runtime endpoint and the models it serves."""

    runtime: RuntimeKind
    base_url: str
    reachable: bool = False
    error: str = ""
    models: list[DetectedModel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the detected runtime to a dict."""
        return {
            "runtime": self.runtime.value,
            "base_url": self.base_url,
            "reachable": self.reachable,
            "error": self.error,
            "models": [m.to_dict() for m in self.models],
        }


@dataclass
class DiscoveryReport:
    """The result of probing all local runtimes."""

    runtimes: list[DetectedRuntime] = field(default_factory=list)

    @property
    def reachable_runtimes(self) -> list[DetectedRuntime]:
        """Return the reachable runtimes."""
        return [r for r in self.runtimes if r.reachable]

    @property
    def models(self) -> list[DetectedModel]:
        """Return the models."""
        out: list[DetectedModel] = []
        for r in self.runtimes:
            out.extend(r.models)
        return out

    @property
    def loaded_models(self) -> list[DetectedModel]:
        """Return the loaded models."""
        return [m for m in self.models if m.is_loaded]

    @property
    def any_reachable(self) -> bool:
        """Return whether the any reachable condition holds."""
        return any(r.reachable for r in self.runtimes)

    def primary_model(self) -> DetectedModel | None:
        """Best candidate to dispatch to: a loaded LLM, else any LLM."""
        llms = [m for m in self.models if m.model_type == "llm"]
        loaded = [m for m in llms if m.is_loaded]
        if loaded:
            return loaded[0]
        return llms[0] if llms else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full discovery report to a dict."""
        return {
            "any_reachable": self.any_reachable,
            "runtimes": [r.to_dict() for r in self.runtimes],
            "model_count": len(self.models),
            "loaded_count": len(self.loaded_models),
        }


# ── HTTP helper ──────────────────────────────────────────────────────────────

def _get_json(url: str, *, timeout: float) -> Any | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.debug("discovery probe failed for %s: %s", url, exc)
        return None


# ── Per-runtime parsers ──────────────────────────────────────────────────────

def _parse_lmstudio_native(data: Any, endpoint: str) -> list[DetectedModel]:
    """Parse LM Studio's rich native ``/api/v0/models`` payload."""
    models: list[DetectedModel] = []
    for entry in (data or {}).get("data", []):
        if not isinstance(entry, dict):
            continue
        mid = str(entry.get("id", ""))
        arch = str(entry.get("arch", ""))
        caps = [str(c) for c in entry.get("capabilities", []) or []]
        state_raw = str(entry.get("state", "")).lower()
        state = (
            ModelState.LOADED if state_raw == "loaded"
            else ModelState.NOT_LOADED if state_raw == "not-loaded"
            else ModelState.UNKNOWN
        )
        mtype = str(entry.get("type", "llm")) or "llm"
        supports_tools = "tool_use" in caps or _looks_tool_capable(mid, arch)
        models.append(DetectedModel(
            id=mid,
            runtime=RuntimeKind.LM_STUDIO,
            endpoint=endpoint,
            model_type=mtype,
            state=state,
            publisher=str(entry.get("publisher", "")),
            architecture=arch,
            quantization=str(entry.get("quantization", "")),
            max_context_length=entry.get("max_context_length"),
            loaded_context_length=entry.get("loaded_context_length"),
            capabilities=caps,
            supports_tools=supports_tools and mtype == "llm",
            is_reasoning_model=_looks_like_reasoning(mid, arch) or "reasoning" in caps,
            is_vision_model="vision" in caps or mtype in ("vlm", "vision"),
            raw=entry,
        ))
    return models


def _parse_openai_models(
    data: Any, endpoint: str, runtime: RuntimeKind
) -> list[DetectedModel]:
    """Parse a generic OpenAI-compatible ``/v1/models`` payload."""
    models: list[DetectedModel] = []
    for entry in (data or {}).get("data", []):
        if not isinstance(entry, dict):
            continue
        mid = str(entry.get("id", ""))
        if not mid:
            continue
        models.append(DetectedModel(
            id=mid,
            runtime=runtime,
            endpoint=endpoint,
            model_type="llm",
            state=ModelState.UNKNOWN,
            supports_tools=_looks_tool_capable(mid),
            is_reasoning_model=_looks_like_reasoning(mid),
            raw=entry,
        ))
    return models


def _parse_ollama_tags(data: Any, endpoint: str, *, timeout: float) -> list[DetectedModel]:
    """Parse Ollama's ``/api/tags`` and enrich each model via ``/api/show``."""
    models: list[DetectedModel] = []
    for entry in (data or {}).get("models", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("model", ""))
        if not name:
            continue
        details = entry.get("details", {}) or {}
        arch = str(details.get("family", ""))
        quant = str(details.get("quantization_level", ""))
        model = DetectedModel(
            id=name,
            runtime=RuntimeKind.OLLAMA,
            endpoint=endpoint,
            model_type="llm",
            state=ModelState.UNKNOWN,
            architecture=arch,
            quantization=quant,
            supports_tools=_looks_tool_capable(name, arch),
            is_reasoning_model=_looks_like_reasoning(name, arch),
            raw=entry,
        )
        # Enrich with /api/show for context length + capabilities.
        show = _post_json(
            f"{endpoint}/api/show", {"model": name}, timeout=timeout
        )
        if isinstance(show, dict):
            caps = [str(c) for c in show.get("capabilities", []) or []]
            if caps:
                model.capabilities = caps
                model.supports_tools = "tools" in caps or model.supports_tools
                model.is_vision_model = "vision" in caps
                model.is_reasoning_model = (
                    "thinking" in caps or model.is_reasoning_model
                )
            info = show.get("model_info", {}) or {}
            for key, val in info.items():
                if key.endswith(".context_length") and isinstance(val, int):
                    model.max_context_length = val
                    break
        models.append(model)
    return models


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> Any | None:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.debug("discovery POST failed for %s: %s", url, exc)
        return None


# ── Per-runtime probers ──────────────────────────────────────────────────────

def _probe_lmstudio(endpoint: str, *, timeout: float) -> DetectedRuntime:
    rt = DetectedRuntime(runtime=RuntimeKind.LM_STUDIO, base_url=endpoint)
    # Prefer the native API (richest specs); fall back to OpenAI-compatible.
    native = _get_json(f"{endpoint}/api/v0/models", timeout=timeout)
    if native is not None:
        rt.reachable = True
        rt.models = _parse_lmstudio_native(native, endpoint)
        return rt
    oai = _get_json(f"{endpoint}/v1/models", timeout=timeout)
    if oai is not None:
        rt.reachable = True
        rt.models = _parse_openai_models(oai, endpoint, RuntimeKind.LM_STUDIO)
        return rt
    rt.error = "no response on /api/v0/models or /v1/models"
    return rt


def _probe_ollama(endpoint: str, *, timeout: float) -> DetectedRuntime:
    rt = DetectedRuntime(runtime=RuntimeKind.OLLAMA, base_url=endpoint)
    tags = _get_json(f"{endpoint}/api/tags", timeout=timeout)
    if tags is not None:
        rt.reachable = True
        rt.models = _parse_ollama_tags(tags, endpoint, timeout=timeout)
        # /api/ps tells us which models are currently loaded.
        ps = _get_json(f"{endpoint}/api/ps", timeout=timeout)
        if isinstance(ps, dict):
            loaded_names = {
                str(m.get("name") or m.get("model", ""))
                for m in ps.get("models", []) or []
            }
            for model in rt.models:
                model.state = (
                    ModelState.LOADED if model.id in loaded_names
                    else ModelState.NOT_LOADED
                )
        return rt
    rt.error = "no response on /api/tags"
    return rt


def _probe_openai_compatible(
    endpoint: str, runtime: RuntimeKind, *, timeout: float
) -> DetectedRuntime:
    rt = DetectedRuntime(runtime=runtime, base_url=endpoint)
    oai = _get_json(f"{endpoint}/v1/models", timeout=timeout)
    if oai is not None:
        rt.reachable = True
        rt.models = _parse_openai_models(oai, endpoint, runtime)
        # llama-server exposes /props with the loaded model's context size.
        props = _get_json(f"{endpoint}/props", timeout=timeout)
        if isinstance(props, dict):
            n_ctx = props.get("default_generation_settings", {}).get("n_ctx") \
                or props.get("n_ctx")
            for model in rt.models:
                model.state = ModelState.LOADED
                if isinstance(n_ctx, int):
                    model.loaded_context_length = n_ctx
        return rt
    rt.error = "no response on /v1/models"
    return rt


def _probe(endpoint: _Endpoint, *, timeout: float) -> DetectedRuntime:
    if endpoint.runtime is RuntimeKind.LM_STUDIO:
        return _probe_lmstudio(endpoint.base_url, timeout=timeout)
    if endpoint.runtime is RuntimeKind.OLLAMA:
        return _probe_ollama(endpoint.base_url, timeout=timeout)
    return _probe_openai_compatible(
        endpoint.base_url, endpoint.runtime, timeout=timeout
    )


def discover_local_llms(
    endpoints: tuple[_Endpoint, ...] | None = None,
    *,
    timeout: float = 2.0,
) -> DiscoveryReport:
    """Probe local LLM runtimes and report every model and its capabilities.

    Args:
        endpoints: Override the set of endpoints to probe. Defaults to the
            standard LM Studio / Ollama / llama.cpp / vLLM ports.
        timeout: Per-request timeout in seconds. Discovery is best-effort —
            unreachable runtimes are reported as ``reachable=False`` and never
            raise.

    Returns:
        A :class:`DiscoveryReport`.
    """
    report = DiscoveryReport()
    for endpoint in (endpoints or DEFAULT_ENDPOINTS):
        try:
            report.runtimes.append(_probe(endpoint, timeout=timeout))
        except Exception as exc:  # noqa: BLE001 — discovery must never raise
            logger.debug("discovery failed for %s: %s", endpoint.base_url, exc)
            report.runtimes.append(DetectedRuntime(
                runtime=endpoint.runtime,
                base_url=endpoint.base_url,
                error=str(exc),
            ))
    return report
