#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 - see LICENSE.md for details.
"""Generate changelog entries from git log (§audit L10).

Usage:
    python scripts/gen_changelog.py              # since last tag
    python scripts/gen_changelog.py v1.0.0       # since specific tag
    python scripts/gen_changelog.py v1.0.0 HEAD  # between two refs
"""

from __future__ import annotations

import re
import subprocess
import sys


def git_log(since: str = "", until: str = "HEAD") -> list[str]:
    """Return list of commit subject lines between *since* and *until*."""
    range_spec = f"{since}..{until}" if since else until
    result = subprocess.run(
        ["git", "log", "--pretty=format:%s", range_spec],
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def last_tag() -> str:
    """Return the most recent git tag, or empty string."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


# Conventional-commit-style categorization
_CATEGORIES = {
    "Added": re.compile(r"^(feat|add|new)\b", re.IGNORECASE),
    "Changed": re.compile(r"^(change|refactor|update|improve)\b", re.IGNORECASE),
    "Fixed": re.compile(r"^(fix|bug|patch|hotfix)\b", re.IGNORECASE),
    "Removed": re.compile(r"^(remove|delete|drop)\b", re.IGNORECASE),
    "Security": re.compile(r"^(security|vuln)\b", re.IGNORECASE),
}


def categorize(messages: list[str]) -> dict[str, list[str]]:
    """Group commit messages into Keep-a-Changelog categories."""
    groups: dict[str, list[str]] = {k: [] for k in _CATEGORIES}
    groups["Other"] = []
    for msg in messages:
        matched = False
        for cat, pattern in _CATEGORIES.items():
            if pattern.search(msg):
                groups[cat].append(msg)
                matched = True
                break
        if not matched:
            groups["Other"].append(msg)
    return {k: v for k, v in groups.items() if v}


def main() -> None:
    since = sys.argv[1] if len(sys.argv) > 1 else last_tag()
    until = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    messages = git_log(since, until)
    if not messages:
        print("No commits found.")
        return

    groups = categorize(messages)
    ref = f"since {since}" if since else "all commits"
    print(f"## [Unreleased] - {ref}\n")
    for category, items in groups.items():
        print(f"### {category}\n")
        for item in items:
            print(f"- {item}")
        print()


if __name__ == "__main__":
    main()
