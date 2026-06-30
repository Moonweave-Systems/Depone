"""depone team-dry-run - plan team lanes without launching workers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from depone.agent_fabric.team_dry_run import (
    TeamDryRunError,
    _self_test as team_dry_run_self_test,
    build_team_dry_run,
)
from depone.cli._response import emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        team_dry_run_self_test()
        print("depone team-dry-run --self-test: pass")
        return

    plan_arg = str(getattr(args, "plan", "") or "")
    if not plan_arg:
        emit_error(
            args,
            code="ERR_TEAM_DRY_RUN_PLAN_REQUIRED",
            message="--plan is required",
        )
    plan_path = Path(plan_arg)
    try:
        plan = _read_json_object(plan_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_DRY_RUN_READ_FAILED",
            message=str(exc),
            path=plan_path,
        )

    out_dir = Path(str(getattr(args, "out_dir", "") or "out/team-dry-run"))
    try:
        dry_run = build_team_dry_run(plan, out_dir=out_dir)
    except TeamDryRunError as exc:
        emit_error(args, code=exc.code, message=exc.message)

    out_dir.mkdir(parents=True, exist_ok=True)
    dry_run_path = out_dir / "team-dry-run.json"
    ledger_path = out_dir / "team-ledger.json"
    verdict_path = out_dir / "team-ledger-verdict.json"
    commands_path = out_dir / "next-commands.json"

    _write_json(dry_run_path, dry_run)
    _write_json(ledger_path, dry_run["team_ledger"])
    _write_json(verdict_path, dry_run["team_ledger_verdict"])
    _write_json(commands_path, dry_run["next_commands"])

    verdict = dry_run["team_ledger_verdict"]
    error_count = len(verdict["errors"])
    emit_result(
        args,
        {
            "command": "team-dry-run",
            "decision": verdict["decision"],
            "lane_count": verdict["lane_count"],
            "error_count": error_count,
            "out_dir": out_dir.as_posix(),
            "files": {
                "team_dry_run": dry_run_path.as_posix(),
                "team_ledger": ledger_path.as_posix(),
                "team_ledger_verdict": verdict_path.as_posix(),
                "next_commands": commands_path.as_posix(),
            },
        },
        human=[
            f"Team dry-run decision: {verdict['decision']}",
            f"  Lanes: {verdict['lane_count']}",
            f"  Errors: {error_count}",
            f"  Artifacts: {out_dir.as_posix()}",
        ],
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan JSON must be an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
