# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests for the dynamic SDK accessors (client.orchestrator, client.modules)."""

from __future__ import annotations

import pytest

import crp
from crp.core.orchestrator import CRPOrchestrator


@pytest.fixture(scope="module")
def client():
    """Re-use one SDK client across dynamic-accessor tests."""
    return crp.SDKClient()


def test_orchestrator_returns_orchestrator_instance(client):
    """client.orchestrator exposes the live CRPOrchestrator."""
    orch = client.orchestrator._orchestrator
    assert isinstance(orch, CRPOrchestrator)


def test_orchestrator_ckf_subsystem(client):
    """Subsystems on the orchestrator are reachable lazily."""
    ckf = client.orchestrator.ckf
    assert ckf is not None
    assert callable(ckf.retrieve)


def test_orchestrator_private_name_blocked(client):
    """Private attributes are blocked on the orchestrator proxy."""
    with pytest.raises(AttributeError):
        _ = client.orchestrator._private_nonexistent


def test_modules_reaches_classes(client):
    """client.modules.<module>.<Class> returns the class."""
    cls = client.modules.security.consent.ConsentManager
    assert isinstance(cls, type)
    assert cls.__name__ == "ConsentManager"


def test_modules_reaches_functions(client):
    """client.modules.<module>.<function> returns a callable."""
    fn = client.modules.envelope.cdr.cdr_rank
    assert callable(fn)


def test_modules_nested_subpackages(client):
    """Deeply nested submodules are navigable."""
    mod = client.modules.ckf.fabric
    assert callable(mod.ContextualKnowledgeFabric)


def test_modules_private_name_blocked(client):
    """Private attributes are blocked on the modules proxy."""
    with pytest.raises(AttributeError):
        _ = client.modules._private


def test_modules_unknown_name_raises(client):
    """Unknown attributes raise AttributeError with a helpful message."""
    with pytest.raises(AttributeError) as exc_info:
        _ = client.modules.core.nonexistent_xyz
    assert "has no public attribute" in str(exc_info.value)


def test_modules_dir_includes_public_names(client):
    """dir(client.modules.<pkg>) is useful for discovery."""
    names = dir(client.modules.ckf)
    assert "ContextualKnowledgeFabric" in names


def test_context_manager_still_works():
    """The new accessors do not break the sync context manager."""
    with crp.SDKClient() as c:
        assert c.orchestrator is not None
        assert c.modules.core is not None
