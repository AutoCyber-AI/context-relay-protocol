# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""5-Primitive Storage Engine — public API (SPEC-035).

Exports:
    StorageRouter      — unified access router (the main entry point)
    AccessPattern      — access pattern enum
    RollingContextLog  — Primitive 2: sequential recency
    LogEntry           — rolling log entry
    HotCache           — Primitive 3: repeat-access acceleration
    InvertedIndex      — Primitive 4: exact-match lookup
    EphemeralStore     — Primitive 5: pointer-based large working data
    EphemeralEntry     — ephemeral store entry
    DataStructure      — structure type constants
"""

from __future__ import annotations

from .ephemeral_store import DataStructure, EphemeralEntry, EphemeralStore
from .hot_cache import HotCache
from .inverted_index import InvertedIndex
from .rolling_log import LogEntry, RollingContextLog
from .router import AccessPattern, StorageRouter

__all__ = [
    "StorageRouter",
    "AccessPattern",
    "RollingContextLog",
    "LogEntry",
    "HotCache",
    "InvertedIndex",
    "EphemeralStore",
    "EphemeralEntry",
    "DataStructure",
]
