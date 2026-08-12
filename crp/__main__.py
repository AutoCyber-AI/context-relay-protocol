# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Allow ``python -m crp`` to invoke the CLI."""

from crp.cli.main import cli

if __name__ == "__main__":
    cli()
