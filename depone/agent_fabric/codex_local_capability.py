"""Deprecated shim for witnessd-owned Codex local capability detection."""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

from depone.agent_fabric._witnessd_shim import load_witnessd_module

CODEX_LOCAL_CAPABILITY_KIND = "depone-codex-local-capability"
CODEX_LOCAL_CAPABILITY_SCHEMA_VERSION = "0.1"
DEFAULT_CODEX_ROLE_ID = "worker"
ALLOWED_SANDBOX_MODES = frozenset({"read-only", "workspace-write"})
ALLOWED_APPROVAL_POLICIES = frozenset(
    {"never", "on-request", "on-failure", "untrusted"}
)
DEPONE_CODEX_LOCAL_CAPABILITY_DEPRECATION = {
    "status": "deprecated",
    "canonical_module": "witnessd.codex_capability",
    "migration_target": "witnessd",
    "removal": "next Depone major after witnessd adoption",
}


def build_codex_local_capability(
    *,
    repo: Path,
    codex_binary: str = "codex",
    sandbox_mode: str = "workspace-write",
    approval_policy: str = "on-request",
    version_timeout_seconds: float = 10,
    instruction_files: list[Path] | None = None,
    role_id: str = DEFAULT_CODEX_ROLE_ID,
) -> dict[str, object]:
    """Delegate capability probing to the witnessd canonical implementation."""

    return _canonical().build_codex_local_capability(
        repo=repo,
        codex_binary=codex_binary,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        version_timeout_seconds=version_timeout_seconds,
        instruction_files=instruction_files,
        role_id=role_id,
    )


def validate_codex_local_capability(receipt: dict[str, object]) -> list[str]:
    """Delegate receipt validation to the witnessd canonical implementation."""

    return _canonical().validate_codex_local_capability(receipt)


def write_codex_local_capability(path: Path, receipt: dict[str, object]) -> None:
    """Write a Codex local capability receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _canonical() -> ModuleType:
    return load_witnessd_module("witnessd.codex_capability")


def _self_test() -> None:
    canonical = _canonical()
    if hasattr(canonical, "_self_test"):
        canonical._self_test()
