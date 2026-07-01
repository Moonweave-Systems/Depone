"""Git merge-attempt receipt producer for Team Ledger fan-in evidence.

This module derives merge/conflict facts from git in a disposable worktree by
default. It does not approve merges, launch agents, call live models, or raise
assurance.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEAM_MERGE_ATTEMPT_KIND = "depone-team-merge-attempt"
TEAM_MERGE_ATTEMPT_SCHEMA_VERSION = "0.1"


class TeamMergeAttemptError(ValueError):
    """Structured team merge-attempt error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def to_record(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def build_team_merge_attempt_receipt(
    *,
    repo: Path,
    base: str,
    heads: list[str],
    disposable: bool = True,
    attempt_worktree: Path | None = None,
    allow_dirty_target: bool = False,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Run a no-commit merge attempt and return a deterministic receipt."""

    repo = repo.resolve(strict=False)
    source_command = [
        "git",
        "-C",
        str(repo),
        "merge",
        "--no-commit",
        "--no-ff",
        *heads,
    ]
    base_commit = _resolve_commit(repo, base)
    head_commits = [_resolve_commit(repo, head) for head in heads]
    if not heads:
        return _blocked_receipt(
            repo=repo,
            base_commit=base_commit,
            head_commits=[],
            attempt_worktree=attempt_worktree or repo,
            dirty_target_refused=False,
            exit_code=1,
            errors=[_error("ERR_TEAM_MERGE_ATTEMPT_HEAD_REQUIRED", "at least one --head is required")],
            source_command=source_command,
            captured_at=captured_at,
        )

    if base_commit is None:
        return _blocked_receipt(
            repo=repo,
            base_commit=base,
            head_commits=[head for head in head_commits if head is not None],
            attempt_worktree=attempt_worktree or repo,
            dirty_target_refused=False,
            exit_code=128,
            errors=[_error("ERR_TEAM_MERGE_ATTEMPT_BASE_MISSING", "base commit could not be resolved")],
            source_command=source_command,
            captured_at=captured_at,
        )
    missing_heads = [heads[index] for index, commit in enumerate(head_commits) if commit is None]
    if missing_heads:
        return _blocked_receipt(
            repo=repo,
            base_commit=base_commit,
            head_commits=[head for head in head_commits if head is not None],
            attempt_worktree=attempt_worktree or repo,
            dirty_target_refused=False,
            exit_code=128,
            errors=[_error("ERR_TEAM_MERGE_ATTEMPT_HEAD_MISSING", f"head commit could not be resolved: {missing_heads[0]}")],
            source_command=source_command,
            captured_at=captured_at,
        )

    if not disposable and not allow_dirty_target and _is_dirty(repo):
        return _blocked_receipt(
            repo=repo,
            base_commit=base_commit,
            head_commits=[str(head) for head in head_commits],
            attempt_worktree=repo,
            dirty_target_refused=True,
            exit_code=1,
            errors=[
                _error(
                    "ERR_TEAM_MERGE_ATTEMPT_DIRTY_TARGET",
                    "target worktree is dirty; use disposable mode or clean the worktree",
                )
            ],
            source_command=source_command,
            captured_at=captured_at,
        )

    cleanup = {"attempt_worktree_removed": False}
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if disposable:
        temp_dir = tempfile.TemporaryDirectory(prefix="depone-merge-attempt-")
        worktree = Path(temp_dir.name) / "worktree"
        add_result = _run_git(repo, ["worktree", "add", "--detach", str(worktree), base_commit])
        if add_result.returncode != 0:
            temp_dir.cleanup()
            return _blocked_receipt(
                repo=repo,
                base_commit=base_commit,
                head_commits=[str(head) for head in head_commits],
                attempt_worktree=worktree,
                dirty_target_refused=False,
                exit_code=add_result.returncode,
                errors=[_error("ERR_TEAM_MERGE_ATTEMPT_WORKTREE_FAILED", _stderr_or_stdout(add_result))],
                source_command=source_command,
                captured_at=captured_at,
            )
    else:
        worktree = repo
        checkout_result = _run_git(worktree, ["checkout", "--detach", base_commit])
        if checkout_result.returncode != 0:
            return _blocked_receipt(
                repo=repo,
                base_commit=base_commit,
                head_commits=[str(head) for head in head_commits],
                attempt_worktree=worktree,
                dirty_target_refused=False,
                exit_code=checkout_result.returncode,
                errors=[_error("ERR_TEAM_MERGE_ATTEMPT_CHECKOUT_FAILED", _stderr_or_stdout(checkout_result))],
                source_command=source_command,
                captured_at=captured_at,
            )

    merge_result = _run_git(worktree, ["merge", "--no-commit", "--no-ff", *[str(head) for head in head_commits]])
    conflict_files = _git_lines(worktree, ["diff", "--name-only", "--diff-filter=U"])
    merged_files = sorted(set(_git_lines(worktree, ["diff", "--name-only", "HEAD"]) + conflict_files))
    if merge_result.returncode != 0:
        decision = "blocked"
        errors = [_error("ERR_TEAM_MERGE_ATTEMPT_CONFLICT", _stderr_or_stdout(merge_result) or "merge blocked")]
    else:
        decision = "pass"
        errors = []

    _run_git(worktree, ["merge", "--abort"])
    if disposable:
        remove_result = _run_git(repo, ["worktree", "remove", "--force", str(worktree)])
        if temp_dir is not None:
            temp_dir.cleanup()
        cleanup["attempt_worktree_removed"] = not worktree.exists() and remove_result.returncode == 0
    else:
        cleanup["attempt_worktree_removed"] = False

    receipt = {
        "kind": TEAM_MERGE_ATTEMPT_KIND,
        "schema_version": TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
        "decision": decision,
        "base_commit": base_commit,
        "head_commits": [str(head) for head in head_commits],
        "attempt_worktree": str(worktree),
        "dirty_target_refused": False,
        "exit_code": merge_result.returncode,
        "merged_files": merged_files,
        "conflict_files": conflict_files,
        "cleanup": cleanup,
        "captured_at": captured_at or _utc_now(),
        "source_command": source_command,
        "errors": errors,
        "boundary": _boundary(),
    }
    return receipt


def validate_team_merge_attempt_receipt(receipt: dict[str, Any]) -> list[dict[str, str]]:
    """Return fail-closed validation errors for a merge-attempt receipt."""

    errors: list[dict[str, str]] = []
    if not isinstance(receipt, dict):
        return [_error("ERR_TEAM_MERGE_ATTEMPT_INVALID", "receipt root must be an object")]
    if receipt.get("kind") != TEAM_MERGE_ATTEMPT_KIND:
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_INVALID", f"kind must be {TEAM_MERGE_ATTEMPT_KIND}"))
    if receipt.get("schema_version") != TEAM_MERGE_ATTEMPT_SCHEMA_VERSION:
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_INVALID", f"schema_version must be {TEAM_MERGE_ATTEMPT_SCHEMA_VERSION}"))
    if receipt.get("decision") not in {"pass", "blocked"}:
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_DECISION_INVALID", "decision must be pass or blocked"))
    _validate_sha_field(receipt, "base_commit", errors)
    heads = receipt.get("head_commits")
    if not isinstance(heads, list) or not heads:
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_HEADS_INVALID", "head_commits must be a non-empty list"))
    else:
        for head in heads:
            if not _is_sha(str(head)):
                errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_HEADS_INVALID", "head_commits must contain 40-character hex SHAs"))
                break
    if not isinstance(receipt.get("attempt_worktree"), str) or not receipt.get("attempt_worktree"):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_WORKTREE_INVALID", "attempt_worktree must be a non-empty string"))
    if not isinstance(receipt.get("dirty_target_refused"), bool):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_DIRTY_FLAG_INVALID", "dirty_target_refused must be a boolean"))
    if not isinstance(receipt.get("exit_code"), int):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_EXIT_CODE_INVALID", "exit_code must be an integer"))
    if not _is_string_list(receipt.get("merged_files")) or not _is_string_list(receipt.get("conflict_files")):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_FILES_INVALID", "merged_files and conflict_files must be string lists"))
    cleanup = receipt.get("cleanup")
    if not isinstance(cleanup, dict) or not isinstance(cleanup.get("attempt_worktree_removed"), bool):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_CLEANUP_INVALID", "cleanup.attempt_worktree_removed must be a boolean"))
    if receipt.get("decision") == "pass":
        if receipt.get("exit_code") != 0:
            errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_PASS_INVALID", "passing receipt must have exit_code 0"))
        if receipt.get("conflict_files"):
            errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_PASS_INVALID", "passing receipt must not list conflicts"))
        if isinstance(cleanup, dict) and cleanup.get("attempt_worktree_removed") is not True:
            errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_CLEANUP_INVALID", "passing disposable receipt must remove attempt worktree"))
    boundary = receipt.get("boundary")
    if not isinstance(boundary, dict) or boundary.get("approves_merge") is not False or boundary.get("raises_assurance") is not False:
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_BOUNDARY_INVALID", "boundary must not approve merges or raise assurance"))
    return errors


def write_team_merge_attempt_receipt(receipt: dict[str, Any], out_path: Path) -> None:
    errors = validate_team_merge_attempt_receipt(receipt)
    if errors:
        first = errors[0]
        raise TeamMergeAttemptError(first["code"], first["message"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TeamMergeAttemptError("ERR_TEAM_MERGE_ATTEMPT_INPUT_INVALID", f"input must be readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TeamMergeAttemptError("ERR_TEAM_MERGE_ATTEMPT_INPUT_INVALID", "input root must be an object")
    return value


def _blocked_receipt(
    *,
    repo: Path,
    base_commit: str | None,
    head_commits: list[str],
    attempt_worktree: Path,
    dirty_target_refused: bool,
    exit_code: int,
    errors: list[dict[str, str]],
    source_command: list[str],
    captured_at: str | None,
) -> dict[str, Any]:
    return {
        "kind": TEAM_MERGE_ATTEMPT_KIND,
        "schema_version": TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
        "decision": "blocked",
        "base_commit": base_commit or "0" * 40,
        "head_commits": head_commits,
        "attempt_worktree": str(attempt_worktree),
        "dirty_target_refused": dirty_target_refused,
        "exit_code": exit_code,
        "merged_files": [],
        "conflict_files": [],
        "cleanup": {"attempt_worktree_removed": True},
        "captured_at": captured_at or _utc_now(),
        "source_command": source_command,
        "errors": errors,
        "boundary": _boundary(),
    }


def _resolve_commit(repo: Path, rev: str) -> str | None:
    if not rev:
        return None
    result = _run_git(repo, ["rev-parse", "--verify", f"{rev}^{{commit}}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_dirty(repo: Path) -> bool:
    result = _run_git(repo, ["status", "--porcelain"])
    return bool(result.stdout.strip()) or result.returncode != 0


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    result = _run_git(repo, args)
    if result.returncode != 0 and not result.stdout:
        return []
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def _stderr_or_stdout(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip()


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _validate_sha_field(receipt: dict[str, Any], key: str, errors: list[dict[str, str]]) -> None:
    if not _is_sha(str(receipt.get(key, ""))):
        errors.append(_error("ERR_TEAM_MERGE_ATTEMPT_SHA_INVALID", f"{key} must be a 40-character hex SHA"))


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _boundary() -> dict[str, bool]:
    return {
        "executes_git_merge_attempt": True,
        "launches_agents": False,
        "calls_live_models": False,
        "approves_merge": False,
        "raises_assurance": False,
    }


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _self_test() -> None:
    receipt = {
        "kind": TEAM_MERGE_ATTEMPT_KIND,
        "schema_version": TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
        "decision": "pass",
        "base_commit": "a" * 40,
        "head_commits": ["b" * 40],
        "attempt_worktree": "/tmp/depone-merge-attempt",
        "dirty_target_refused": False,
        "exit_code": 0,
        "merged_files": ["depone/agent_fabric/team_ledger.py"],
        "conflict_files": [],
        "cleanup": {"attempt_worktree_removed": True},
        "captured_at": "2026-07-01T00:00:00Z",
        "source_command": ["git", "merge", "--no-commit"],
        "errors": [],
        "boundary": _boundary(),
    }
    errors = validate_team_merge_attempt_receipt(receipt)
    if errors:
        raise AssertionError(errors)
    missing_cleanup = dict(receipt)
    missing_cleanup.pop("cleanup")
    if "ERR_TEAM_MERGE_ATTEMPT_CLEANUP_INVALID" not in {e["code"] for e in validate_team_merge_attempt_receipt(missing_cleanup)}:
        raise AssertionError("missing cleanup must block")
