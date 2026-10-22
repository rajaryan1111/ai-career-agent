"""Filesystem locations shared by the CLI, diagnostics, and the desktop UI.

Kept free of any UI toolkit import so ``--help``, ``--version``, and
``--diagnostics`` work on interpreters without Tkinter.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path


def default_database_path(*, create: bool = True) -> Path:
    """Return the per-user application-data database path.

    ``create=False`` never touches the filesystem, so diagnostics and argument
    parsing cannot create the user's real database or its folder.
    """
    system = platform.system()
    if system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    folder = root / ("AI Career Agent" if system in {"Darwin", "Windows"} else "ai-career-agent")
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder / "career_agent.sqlite3"
