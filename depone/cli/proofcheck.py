"""depone proofcheck -- offline ORRO artifact verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
)
from depone.agent_fabric.team_ledger import build_team_ledger_verdict, read_team_ledger
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    evidence_dir_arg = str(getattr(args, "evidence_dir", "") or "")
    if not evidence_dir_arg:
        emit_error(
            args,
            code="ERR_ORRO_PROOFCHECK_INPUT_REQUIRED",
            message="--evidence-dir is required",
            legacy_code="ERR_SUPERFLOW_PROOFCHECK_INPUT_REQUIRED",
        )

    evidence_dir = Path(evidence_dir_arg)
    try:
        team_ledger_path = evidence_dir / "team-ledger.json"
        if team_ledger_path.is_file():
            ledger = read_team_ledger(team_ledger_path)
            verdict = build_team_ledger_verdict(ledger, base_dir=evidence_dir)
            verifier_command = "team-ledger"
        else:
            artifacts = load_superflow_artifacts(evidence_dir)
            verdict = build_superflow_artifact_verdict(artifacts, base_dir=evidence_dir)
            verifier_command = "proofcheck"
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_ORRO_PROOFCHECK_LOAD_FAILED",
            message=str(exc),
            path=evidence_dir,
            legacy_code="ERR_SUPERFLOW_PROOFCHECK_LOAD_FAILED",
        )

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg:
        out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(verdict, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    error_count = len(verdict["errors"])

    emit_result(
        args,
        {
            "command": "proofcheck",
            "verifier_command": verifier_command,
            "decision": verdict["decision"],
            "error_count": error_count,
            "evidence_dir": str(evidence_dir),
            **({"out": out_arg} if out_arg else {}),
            **({"errors": verdict["errors"]} if verdict["errors"] else {}),
        },
        human=[
            f"Proofcheck decision: {verdict['decision']}",
            f"  Evidence dir: {evidence_dir}",
            f"  Errors: {error_count}",
            *([f"Proofcheck verdict written to {out_arg}"] if out_arg else []),
        ],
    )
    if verdict["decision"] != "pass":
        sys.exit(EXIT_FAILED)
