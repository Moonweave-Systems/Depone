"""Deprecated shim for witnessd-owned team worktree preparation."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from depone.agent_fabric._witnessd_shim import (
    WitnessdUnavailableError,
    load_witnessd_module,
)

TEAM_WORKTREE_PREP_KIND = "depone-team-worktree-prep"
TEAM_WORKTREE_PREP_SCHEMA_VERSION = "0.1"
TEAM_WORKTREE_PREP_DEPRECATION = {
    "status": "deprecated",
    "migration_target": "witnessd",
    "reason": "local worktree preparation mutates runtime state and belongs to witnessd",
}


class TeamWorktreePrepError(ValueError):
    """Structured team worktree preparation error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def build_team_worktree_prep(
    preflight: dict[str, object],
    *,
    repo_root: Path,
    worktree_root: Path,
    create_worktree: bool = False,
) -> dict[str, object]:
    """Delegate worktree preparation to witnessd."""

    try:
        return _canonical().build_team_worktree_prep(
            preflight,
            repo_root=repo_root,
            worktree_root=worktree_root,
            create_worktree=create_worktree,
        )
    except WitnessdUnavailableError as exc:
        raise TeamWorktreePrepError(exc.code, str(exc)) from exc
    except Exception as exc:
        if hasattr(exc, "code") and hasattr(exc, "message"):
            raise TeamWorktreePrepError(str(exc.code), str(exc.message)) from exc
        raise


def validate_team_worktree_prep(payload: dict[str, object]) -> list[dict[str, str]]:
    """Delegate worktree prep receipt validation to witnessd."""

    return _canonical().validate_team_worktree_prep(payload)


def _canonical() -> ModuleType:
    return load_witnessd_module("witnessd.team_worktree_prep")


def _self_test() -> None:
    try:
        _canonical()._self_test()
    except WitnessdUnavailableError as exc:
        raise TeamWorktreePrepError(exc.code, str(exc)) from exc
