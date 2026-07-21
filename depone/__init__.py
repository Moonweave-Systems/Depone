"""Depone — workflow designer + cross-platform evidence verifier.

Depone designs multi-agent workflows and verifies their execution evidence.
It does not execute agents. It makes runs from other frameworks trustworthy.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure existing scripts/ are importable during migration phase.
_PKG_ROOT = Path(__file__).resolve().parent  # depone/
_REPO_ROOT = _PKG_ROOT.parent  # repo root
_SCRIPTS = _REPO_ROOT / "scripts"
if _SCRIPTS.is_dir() and str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# Single source of truth is the installed package metadata (pyproject version).
# Fall back to a source-tree read of pyproject.toml so an uninstalled checkout
# still reports the real version instead of a hardcoded value that drifts.
def _resolve_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("depone")
    except PackageNotFoundError:
        pyproject = _REPO_ROOT / "pyproject.toml"
        try:
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version"):
                    return stripped.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return "0+unknown"


__version__ = _resolve_version()
