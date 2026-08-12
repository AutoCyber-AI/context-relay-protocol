# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP CLI — crp init, dispatch, ingest, status, preview, serve."""

from crp.cli.startup import StartupResult, StartupStep, run_startup

__all__ = ["StartupResult", "StartupStep", "run_startup"]
