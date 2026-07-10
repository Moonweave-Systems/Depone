"""Deprecated shim for witnessd-owned shell lane command execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import ModuleType

from depone.agent_fabric._witnessd_shim import (
    WitnessdUnavailableError,
    load_witnessd_module,
)

TEAM_SHELL_LANE_LAUNCH_KIND = "depone-team-shell-lane-launch"
TEAM_SHELL_LANE_LAUNCH_SCHEMA_VERSION = "0.1"
TEAM_SHELL_LANE_LAUNCH_DEPRECATION = {
    "status": "deprecated",
    "migration_target": "witnessd",
    "reason": "lane command execution belongs to the witnessd runtime boundary",
}
DEFAULT_AGENT_ROLE_ID = "worker"


class TeamShellLaneLaunchError(Exception):
    """Structured shell lane launch failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def run_shell_lane_command(
    *,
    allowlist: dict[str, object],
    command_id: str,
    cwd: Path,
    transcript_path: Path,
    timeout_seconds: int = 120,
    agent_role_id: str = DEFAULT_AGENT_ROLE_ID,
    agent_contract_path: Path | None = None,
    role_registry_path: Path | None = None,
) -> dict[str, object]:
    """Delegate allowlisted command execution to witnessd."""

    try:
        return _canonical().run_shell_lane_command(
            allowlist=allowlist,
            command_id=command_id,
            cwd=cwd,
            transcript_path=transcript_path,
            timeout_seconds=timeout_seconds,
            agent_role_id=agent_role_id,
            agent_contract_path=agent_contract_path,
            role_registry_path=role_registry_path,
        )
    except WitnessdUnavailableError as exc:
        raise TeamShellLaneLaunchError(exc.code, str(exc)) from exc
    except Exception as exc:
        if hasattr(exc, "code") and hasattr(exc, "message"):
            raise TeamShellLaneLaunchError(str(exc.code), str(exc.message)) from exc
        raise


def load_allowlist(path: Path) -> dict[str, object]:
    """Load a JSON allowlist object from disk."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_READ_FAILED",
            str(exc),
        ) from exc
    except json.JSONDecodeError as exc:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_JSON_INVALID",
            str(exc),
        ) from exc
    if not isinstance(value, dict):
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_INVALID",
            "allowlist must be a JSON object",
        )
    return value


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    """Write a shell lane launch receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical() -> ModuleType:
    return load_witnessd_module("witnessd.team_shell_lane_launch")


def _self_test() -> None:
    try:
        _canonical()._self_test()
    except WitnessdUnavailableError as exc:
        raise TeamShellLaneLaunchError(exc.code, str(exc)) from exc
