# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Session file TTL cleanup — automatic expiry of persisted sessions (§audit H11).

Production deployments accumulate session JSON files indefinitely.
This module provides automatic cleanup based on file age.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger("crp.state.session_cleanup")

# Default TTL: 7 days
DEFAULT_TTL_SECONDS = 7 * 24 * 3600


def cleanup_expired_sessions(
    sessions_dir: str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    dry_run: bool = False,
) -> list[str]:
    """Remove session files older than *ttl_seconds*.

    Args:
        sessions_dir: Path to the session storage directory.
                      Defaults to ``./crp_sessions``.
        ttl_seconds:  Maximum age in seconds (default 7 days).
        dry_run:      If True, list but do not delete files.

    Returns:
        List of removed (or would-be-removed) file paths.
    """
    if sessions_dir is None:
        data_dir = os.environ.get("CRP_DATA_DIR", ".")
        sessions_dir = os.path.join(data_dir, "crp_sessions")

    if not os.path.isdir(sessions_dir):
        return []

    now = time.time()
    cutoff = now - ttl_seconds
    removed: list[str] = []

    for entry in os.scandir(sessions_dir):
        if not entry.is_file():
            continue
        # Only clean CRP-generated files (.json, .events.bin, .audit.jsonl)
        if not (entry.name.endswith(".json") or entry.name.endswith(".events.bin")
                or entry.name.endswith(".audit.jsonl")):
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            path = entry.path
            if dry_run:
                logger.info("Would remove expired session file: %s (age %.0f h)",
                            path, (now - mtime) / 3600)
            else:
                try:
                    os.remove(path)
                    logger.info("Removed expired session file: %s (age %.0f h)",
                                path, (now - mtime) / 3600)
                except OSError as exc:
                    logger.warning("Failed to remove %s: %s", path, exc)
                    continue
            removed.append(path)

    if removed:
        logger.info("Session cleanup: %d file(s) %s",
                     len(removed), "would be removed" if dry_run else "removed")
    return removed
