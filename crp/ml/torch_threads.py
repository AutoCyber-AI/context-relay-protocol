# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Sanctioned torch intra-op thread-pool guard for model loading (U-C1).

``torch.set_num_threads`` mutates a *process-global* intra-op thread pool.
Library code must NEVER call it directly: a host application that has
deliberately capped torch threads (e.g. WASA throttling threads under RAM
pressure) would have that cap silently reset, and concurrent in-flight
inference in other threads would be re-throttled mid-flight. Production
audit U-C1 (wasa_crp_production_audit) classifies any bare
``torch.set_num_threads(cpu_count())`` in library code as a HIGH-severity
wedge mechanism.

All CRP model loaders route through :func:`single_threaded_load`, which:

  * saves the host's prior setting,
  * caps the pool to ``CRP_TORCH_THREADS`` (default ``1``, win32 only)
    during the load-time OpenMP duplicate-runtime race window described in
    ``crp/__init__.py``, and
  * restores the prior value in a ``finally`` block — even on load failure.

``CRP_TORCH_THREADS`` semantics:

  * unset        → cap to 1 on win32 during load, restore after (default,
                   preserves the load-time crash guard),
  * ``off`` / ``never`` / ``0`` → never touch torch threads at all,
  * positive int → use that value as the load-time cap.

NOTE: the setting is process-global, so two threads loading simultaneously
can still observe each other's cap for the duration of the load. The window
is short (model weight loading only) and the prior value is always restored;
a per-process loader lock is deliberately NOT taken here to avoid serialising
independent loads.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("crp.ml.torch_threads")


def load_thread_cap() -> int | None:
    """Resolve the load-time thread cap from ``CRP_TORCH_THREADS``.

    Returns the cap (>=1) to apply while loading a model, or ``None`` when
    torch's thread pool must be left untouched entirely.
    """
    raw = os.environ.get("CRP_TORCH_THREADS", "").strip().lower()
    if raw in {"off", "never", "none", "0"}:
        return None
    if raw:
        try:
            cap = int(raw)
        except ValueError:
            logger.warning("CRP_TORCH_THREADS=%r not an integer — ignoring", raw)
            return 1
        return max(1, cap)
    return 1


@contextmanager
def single_threaded_load() -> Iterator[None]:
    """Cap torch intra-op threads for the duration of a model load, then restore.

    No-op on non-Windows platforms and when ``CRP_TORCH_THREADS`` opts out.
    The host's prior value is restored in a ``finally`` block even if the
    load raises. This is the ONLY sanctioned place in the library that may
    call ``torch.set_num_threads`` — the conformance test
    ``tests/test_torch_thread_guard.py::test_no_bare_set_num_threads_in_library``
    greps the tree and fails on any other call site.
    """
    if sys.platform != "win32":
        yield
        return
    cap = load_thread_cap()
    if cap is None:
        yield
        return
    try:
        import torch  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        yield
        return
    try:
        prior = torch.get_num_threads()
    except Exception:  # noqa: BLE001
        yield
        return
    try:
        torch.set_num_threads(cap)
    except Exception:  # noqa: BLE001
        yield
        return
    try:
        yield
    finally:
        try:
            torch.set_num_threads(prior)
        except Exception:  # noqa: BLE001
            logger.warning("failed to restore torch thread count to %s", prior)
