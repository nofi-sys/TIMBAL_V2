"""Helpers to locate bundled resources both in dev and in PyInstaller builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def runtime_base_dir() -> Path:
    """Return the base directory where resources live."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Join the runtime base dir with the provided relative parts."""
    return runtime_base_dir().joinpath(*parts)


def ensure_on_path(directory: Path) -> None:
    """Prepend a directory to PATH and DLL search paths if possible."""
    dir_path = directory.resolve()
    current = os.environ.get("PATH", "")
    if str(dir_path) not in current.split(os.pathsep):
        os.environ["PATH"] = str(dir_path) + os.pathsep + current
    try:
        os.add_dll_directory(str(dir_path))
    except (AttributeError, FileNotFoundError, OSError):
        # Older Python or non-Windows; best effort.
        pass
