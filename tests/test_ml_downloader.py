# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the CRPv6 Phase A model manifest and downloader (no network)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from crp.ml.downloader import (
    download_all,
    download_model,
    load_manifest,
    model_location,
)

EXPECTED_KEYS = {
    "crp.isa.intent",
    "crp.vr.prm",
    "crp.security.safety",
    "crp.embeddings.default",
}


def test_manifest_loads_with_all_keys() -> None:
    manifest = load_manifest()
    assert manifest["schema_version"] == "v6-phaseA-1"
    assert set(manifest["models"]) == EXPECTED_KEYS
    for entry in manifest["models"].values():
        assert entry["repo_id"]
        assert entry["revision"] == "main"
        assert entry["local_name"]
        assert "sha256" in entry
        assert isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64


def test_download_model_calls_snapshot_download(monkeypatch, tmp_path) -> None:
    fake_hub = MagicMock()
    fake_hub.snapshot_download.return_value = str(tmp_path / "crp-intent-setfit")
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    result = download_model("crp.isa.intent", model_dir=str(tmp_path))

    fake_hub.snapshot_download.assert_called_once_with(
        repo_id="AutoCyberAI/crp-intent-setfit",
        revision="main",
        local_dir=str(tmp_path / "crp-intent-setfit"),
    )
    assert result == str(tmp_path / "crp-intent-setfit")


def test_download_all_covers_manifest(monkeypatch, tmp_path) -> None:
    fake_hub = MagicMock()
    fake_hub.snapshot_download.side_effect = lambda repo_id, revision, local_dir: local_dir
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    results = download_all(model_dir=str(tmp_path))

    assert set(results) == EXPECTED_KEYS
    assert fake_hub.snapshot_download.call_count == len(EXPECTED_KEYS)


def test_model_location_falls_back_to_repo_id(tmp_path) -> None:
    location = model_location("crp.security.safety", model_dir=str(tmp_path))
    assert location == "AutoCyberAI/crp-safety-deberta-v1"


def test_model_location_returns_local_path_when_present(tmp_path) -> None:
    local = tmp_path / "crp-safety-deberta-v1"
    local.mkdir()
    (local / "config.json").write_text("{}", encoding="utf-8")

    location = model_location("crp.security.safety", model_dir=str(tmp_path))
    assert location == str(local)


def test_model_location_empty_dir_falls_back(tmp_path) -> None:
    (tmp_path / "crp-intent-setfit").mkdir()
    location = model_location("crp.isa.intent", model_dir=str(tmp_path))
    assert location == "AutoCyberAI/crp-intent-setfit"


def test_unknown_key_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        model_location("crp.does.not.exist")
