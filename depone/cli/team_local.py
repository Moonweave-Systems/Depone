"""depone team-local - run a minimal local team loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from depone.agent_fabric.team_local import TeamLocalError, _self_test, run_team_local
from depone.agent_fabric.team_shell_lane_launch import TeamShellLaneLaunchError, load_allowlist
from depone.cli._response import emit_error, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone team-local --self-test: pass")
        return

    plan_arg = str(getattr(args, "plan", "") or "")
    if not plan_arg:
        emit_error(args, code="ERR_TEAM_LOCAL_PLAN_REQUIRED", message="--plan is required")
    try:
        plan = _read_json_object(Path(plan_arg), "plan")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(args, code="ERR_TEAM_LOCAL_PLAN_READ_FAILED", message=str(exc), path=plan_arg)

    allowlist = None
    allowlist_arg = str(getattr(args, "allowlist", "") or "")
    if allowlist_arg:
        try:
            allowlist = load_allowlist(Path(allowlist_arg))
        except TeamShellLaneLaunchError as exc:
            emit_error(args, code=exc.code, message=exc.message, path=allowlist_arg)

    try:
        ledger = run_team_local(
            plan,
            allowlist=allowlist,
            repo_root=Path(str(getattr(args, "repo", "") or ".")),
            worktree_root=Path(str(getattr(args, "worktree_root", "") or ".")),
            out_dir=Path(str(getattr(args, "out_dir", "") or "out/team-local")),
            base_commit=str(getattr(args, "base_commit", "") or "") or None,
            create_worktree=bool(getattr(args, "create_worktree", False)),
            execute_lanes=bool(getattr(args, "execute_lanes", False)),
            timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
            agent_role_id=str(getattr(args, "agent_role_id", "") or "worker"),
        )
    except TeamLocalError as exc:
        emit_error(args, code=exc.code, message=exc.message)

    emit_result(
        args,
        {
            "command": "team-local",
            "decision": ledger["decision"],
            "lane_count": ledger["lane_count"],
            "passed_lane_count": ledger["passed_lane_count"],
            "blocked_lane_count": ledger["blocked_lane_count"],
            "out": ledger["artifacts"]["team_run_ledger"],
            "boundary": ledger["boundary"],
        },
        human=[
            f"Team local decision: {ledger['decision']}",
            f"  Lanes: {ledger['lane_count']}",
            f"  Passed: {ledger['passed_lane_count']}",
            f"  Blocked: {ledger['blocked_lane_count']}",
            f"  Run ledger: {ledger['artifacts']['team_run_ledger']}",
            "  Boundary: no live model or coding-agent launch",
        ],
    )
    sys.exit(exit_code_for_decision(str(ledger["decision"])))


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must be an object")
    return value
