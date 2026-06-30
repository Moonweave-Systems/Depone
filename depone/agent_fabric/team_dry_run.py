"""Planning-only dry-run for Depone-observed team lanes."""

from __future__ import annotations

import shlex
from pathlib import Path, PurePosixPath
from typing import Any

from depone.agent_fabric.team_ledger import (
    VALID_ADAPTER_KINDS,
    VALID_ENV_KINDS,
    build_team_ledger_verdict,
)

TEAM_DRY_RUN_KIND = "depone-team-dry-run"
TEAM_DRY_RUN_SCHEMA_VERSION = "0.1"


class TeamDryRunError(ValueError):
    """Structured team dry-run planning error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def build_team_dry_run(plan: dict[str, Any], *, out_dir: Path) -> dict[str, Any]:
    """Return a deterministic planning-only Team Ledger dry-run bundle."""

    if not isinstance(plan, dict):
        raise TeamDryRunError("ERR_TEAM_DRY_RUN_PLAN_INVALID", "plan root must be an object")
    base_commit = _required_string(plan, "base_commit", "ERR_TEAM_DRY_RUN_BASE_COMMIT_REQUIRED")
    leader_objective = _required_string(
        plan,
        "leader_objective",
        "ERR_TEAM_DRY_RUN_LEADER_OBJECTIVE_REQUIRED",
    )
    leader_id = str(plan.get("leader_id") or "leader-fixed")
    lanes = plan.get("lanes")
    if not isinstance(lanes, list) or not lanes or not all(isinstance(item, dict) for item in lanes):
        raise TeamDryRunError(
            "ERR_TEAM_DRY_RUN_LANES_INVALID",
            "lanes must be a non-empty list of objects",
        )

    out_dir_text = _normalize_optional_relative_path(out_dir, "out_dir")
    ledger_lanes: list[dict[str, Any]] = []
    dry_run_lanes: list[dict[str, Any]] = []
    next_commands: list[dict[str, Any]] = []
    seen_lane_ids: set[str] = set()
    for index, lane in enumerate(lanes, start=1):
        lane_id = _lane_id(lane, index, seen_lane_ids)
        objective = _required_string(lane, "objective", "ERR_TEAM_DRY_RUN_LANE_OBJECTIVE_REQUIRED")
        env_kind = _choice(lane.get("env_kind") or "local", VALID_ENV_KINDS, "env_kind")
        runner_adapter_kind = _choice(
            lane.get("runner_adapter_kind") or "codex",
            VALID_ADAPTER_KINDS,
            "runner_adapter_kind",
        )
        team_adapter_kind = _choice(
            lane.get("team_adapter_kind") or "depone-native",
            VALID_ADAPTER_KINDS,
            "team_adapter_kind",
        )
        evidence_dir = _evidence_dir(lane_id)
        receipt_path = f"{evidence_dir}/worktree-receipt.json"
        planned_worktree = _planned_worktree(lane, out_dir_text, lane_id)
        touched_files = _repo_relative_list(lane.get("touched_files"), "touched_files")
        blocked_reason = (
            "dry-run plan only; no lane evidence has been captured and no worker was launched"
        )

        ledger_lane: dict[str, Any] = {
            "lane_id": lane_id,
            "objective": objective,
            "env_kind": env_kind,
            "runner_adapter_kind": runner_adapter_kind,
            "team_adapter_kind": team_adapter_kind,
            "start_commit": base_commit,
            "end_commit": base_commit,
            "evidence_dir": evidence_dir,
            "verification_state": "blocked",
            "blocked_reason": blocked_reason,
            "verification_artifacts": [],
            "worktree_receipt": receipt_path,
        }
        if touched_files:
            ledger_lane["touched_files"] = touched_files
        ledger_lanes.append(ledger_lane)

        dry_run_lanes.append(
            {
                "lane_id": lane_id,
                "objective": objective,
                "planned_worktree": planned_worktree,
                "evidence_dir": evidence_dir,
                "blocked_reason": blocked_reason,
            }
        )
        next_commands.append(
            {
                "lane_id": lane_id,
                "commands": [
                    (
                        "git worktree add "
                        f"{_shell_quote(planned_worktree)} {_shell_quote(base_commit)}"
                    ),
                    (
                        "python3 -m depone worktree-lane-receipt "
                        f"--worktree {_shell_quote(planned_worktree)} "
                        f"--base-commit {_shell_quote(base_commit)} "
                        f"--evidence-dir {_shell_quote(evidence_dir)} "
                        f"--out {_shell_quote(_artifact_path(out_dir_text, receipt_path))} --json"
                    ),
                ],
            }
        )

    ledger = {
        "kind": "depone-team-ledger",
        "schema_version": "0.1",
        "leader_objective": leader_objective,
        "leader_id": leader_id,
        "start_commit": base_commit,
        "end_commit": base_commit,
        "stop_rule": "dry-run only; fan-in remains blocked until lane evidence exists",
        "lanes": ledger_lanes,
    }
    verdict = build_team_ledger_verdict(ledger)
    return {
        "kind": TEAM_DRY_RUN_KIND,
        "schema_version": TEAM_DRY_RUN_SCHEMA_VERSION,
        "leader_objective": leader_objective,
        "base_commit": base_commit,
        "out_dir": out_dir.as_posix(),
        "lanes": dry_run_lanes,
        "team_ledger": ledger,
        "team_ledger_verdict": verdict,
        "next_commands": next_commands,
        "boundary": {
            "launches_agents": False,
            "executes_commands": False,
            "mutates_worktree": False,
            "raises_assurance": False,
        },
    }


def _required_string(value: dict[str, Any], field: str, code: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise TeamDryRunError(code, f"{field} must be a non-empty string")
    return raw.strip()


def _lane_id(lane: dict[str, Any], index: int, seen_lane_ids: set[str]) -> str:
    raw = lane.get("lane_id")
    lane_id = raw.strip() if isinstance(raw, str) and raw.strip() else f"lane-{index}"
    normalized = _normalize_relative_path(Path(lane_id), "lane_id")
    if "/" in normalized:
        raise TeamDryRunError(
            "ERR_TEAM_DRY_RUN_LANE_ID_INVALID",
            "lane_id must be a simple relative path segment",
        )
    if normalized in seen_lane_ids:
        raise TeamDryRunError("ERR_TEAM_DRY_RUN_LANE_ID_DUPLICATE", "lane_id must be unique")
    seen_lane_ids.add(normalized)
    return normalized


def _choice(value: object, valid: frozenset[str], field: str) -> str:
    if isinstance(value, str) and value in valid:
        return value
    raise TeamDryRunError(
        "ERR_TEAM_DRY_RUN_CHOICE_INVALID",
        f"{field} must be one of {sorted(valid)}",
    )


def _evidence_dir(lane_id: str) -> str:
    return _normalize_relative_path(Path(lane_id), "evidence_dir")


def _planned_worktree(lane: dict[str, Any], out_dir_text: str, lane_id: str) -> str:
    raw = lane.get("planned_worktree")
    if isinstance(raw, str) and raw.strip():
        return _normalize_relative_path(Path(raw), "planned_worktree")
    if out_dir_text:
        return _normalize_relative_path(Path(out_dir_text) / "worktrees" / lane_id, "planned_worktree")
    return _normalize_relative_path(Path("worktrees") / lane_id, "planned_worktree")


def _artifact_path(out_dir_text: str, relative_path: str) -> str:
    return _normalize_relative_path(Path(out_dir_text) / relative_path, "artifact path")


def _repo_relative_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TeamDryRunError(
            "ERR_TEAM_DRY_RUN_PATH_INVALID",
            f"{field} must be a list of repo-relative paths",
        )
    normalized = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TeamDryRunError(
                "ERR_TEAM_DRY_RUN_PATH_INVALID",
                f"{field} entries must be non-empty repo-relative strings",
            )
        normalized.append(_normalize_relative_path(Path(item), field))
    return normalized


def _normalize_optional_relative_path(path: Path, label: str) -> str:
    text = path.as_posix()
    if path.is_absolute():
        raise TeamDryRunError(
            "ERR_TEAM_DRY_RUN_PATH_INVALID",
            f"{label} must be a repo-relative path",
        )
    return _normalize_relative_path(path, label) if text else ""


def _normalize_relative_path(path: Path, label: str) -> str:
    text = path.as_posix()
    posix = PurePosixPath(text)
    if not text or posix.is_absolute() or ".." in posix.parts:
        raise TeamDryRunError(
            "ERR_TEAM_DRY_RUN_PATH_INVALID",
            f"{label} must be a non-empty repo-relative path",
        )
    return posix.as_posix()


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def _self_test() -> None:
    plan = {
        "leader_objective": "Plan a local lane without launching workers",
        "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "lanes": [{"objective": "Run focused tests"}],
    }
    dry_run = build_team_dry_run(plan, out_dir=Path("out/team-dry-run"))
    if dry_run["boundary"]["launches_agents"] is not False:
        raise AssertionError("dry-run must not launch agents")
    if dry_run["team_ledger_verdict"]["decision"] != "blocked-explicit":
        raise AssertionError("dry-run ledger must remain explicitly blocked")
