"""CLI entry point for AI Career Agent.

Defines the career-agent console script referenced in pyproject.toml.
"""
from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Entry point for career-agent CLI command.

    No subcommands are implemented in the alpha release.
    """
    import sys

    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("--help", "-h"):
        print("career-agent - local-first desktop assistant for job tracking", file=sys.stdout)
        print("Version 0.1.0 - alpha release", file=sys.stdout)
        print("No subcommands implemented yet.", file=sys.stdout)
        print("Run career-agent --help for available options.", file=sys.stdout)
        return 0

    print("career-agent - no subcommand implemented in alpha build", file=sys.stdout)
    return 0
