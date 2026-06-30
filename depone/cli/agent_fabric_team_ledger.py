from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from depone.agent_fabric.team_ledger import load_team_ledger, validate_team_ledger
from depone.cli._response import emit_error, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    ledger_path_text = str(getattr(args, "ledger", "") or "")
    if not ledger_path_text:
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_REQUIRED",
            message="provide --ledger path",
        )
    ledger_path = Path(ledger_path_text)
    try:
        ledger = load_team_ledger(ledger_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_READ_FAILED",
            message=str(exc),
        )

    verdict = validate_team_ledger(ledger, base_dir=ledger_path.parent)
    out_path = Path(str(getattr(args, "out", "team-ledger-verdict.json")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    emit_result(
        args,
        {
            "command": "team-ledger",
            "decision": verdict["decision"],
            "out": str(out_path),
            "lane_count": verdict["lane_count"],
            "passed_lane_count": verdict["passed_lane_count"],
            "blocked_lane_count": verdict["blocked_lane_count"],
        },
        human=[
            f"Team ledger decision: {verdict['decision']}",
            f"Team ledger verdict written to {out_path}",
        ],
    )
    sys.exit(exit_code_for_decision(str(verdict["decision"])))


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        evidence_dir = temp_dir / "lane-1-evidence"
        evidence_dir.mkdir()
        valid = {
            "kind": "depone-team-ledger",
            "schema_version": "1.0",
            "objective": "verify a two-lane team",
            "leader": "leader-fixed",
            "lanes": [
                {
                    "lane_id": "lane-1",
                    "environment_kind": "local",
                    "adapter_kind": "omx",
                    "start_commit": "a" * 40,
                    "end_commit": "b" * 40,
                    "evidence_dir": str(evidence_dir),
                    "verification_state": "pass",
                    "pr_url": "https://example.invalid/pr/1",
                }
            ],
        }
        if validate_team_ledger(valid, base_dir=temp_dir)["decision"] != "pass":
            raise AssertionError("valid ledger must pass")

        missing_evidence = json.loads(json.dumps(valid))
        missing_evidence["lanes"][0]["evidence_dir"] = "missing"
        if validate_team_ledger(missing_evidence, base_dir=temp_dir)["decision"] != "blocked":
            raise AssertionError("pass lane with missing evidence must block")

        blocked = json.loads(json.dumps(valid))
        blocked["lanes"][0]["verification_state"] = "blocked"
        blocked["lanes"][0].pop("evidence_dir")
        blocked["lanes"][0]["blocked_reason"] = "merge conflict needs leader fan-in"
        if validate_team_ledger(blocked, base_dir=temp_dir)["decision"] != "blocked":
            raise AssertionError("explicitly blocked lane must block fan-in")

    print("depone team-ledger --self-test: pass")
