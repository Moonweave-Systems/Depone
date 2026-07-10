"""Helpers for deprecated Agent Fabric runtime shims."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


class WitnessdUnavailableError(RuntimeError):
    """Raised when a deprecated runtime surface cannot reach witnessd."""

    code = "ERR_DEPONE_EXECUTION_SURFACE_MOVED_TO_WITNESSD"


def load_witnessd_module(module_name: str) -> ModuleType:
    """Load a witnessd canonical module, including the sibling source checkout."""

    _prefer_sibling_checkout(module_name)
    try:
        return importlib.import_module(module_name)
    except ImportError:
        _prefer_sibling_checkout(module_name)
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            raise WitnessdUnavailableError(
                f"{module_name} is required; this Depone runtime surface moved to witnessd"
            ) from exc


def _prefer_sibling_checkout(module_name: str) -> None:
    workspace = Path(__file__).resolve().parents[3]
    sibling = workspace / "witnessd"
    package_dir = sibling / "witnessd"
    if not package_dir.is_dir():
        return
    sibling_text = str(sibling)
    if sibling_text not in sys.path:
        sys.path.insert(0, sibling_text)
    package = sys.modules.get("witnessd")
    if package is not None and hasattr(package, "__path__"):
        package_path = getattr(package, "__path__")
        package_dir_text = str(package_dir)
        if package_dir_text not in package_path:
            package_path.insert(0, package_dir_text)
    loaded = sys.modules.get(module_name)
    if loaded is not None and not getattr(loaded, "__file__", None):
        return
    loaded_file = Path(str(getattr(loaded, "__file__", ""))) if loaded else None
    if loaded_file is not None:
        try:
            loaded_file.resolve().relative_to(sibling.resolve())
        except ValueError:
            sys.modules.pop(module_name, None)
