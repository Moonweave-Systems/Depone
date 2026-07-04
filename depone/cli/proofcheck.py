"""depone proofcheck — offline Superflow artifact verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
)
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    evidence_dir_arg = str(getattr(args, "evidence_dir", "") or "")
    if not evidence_dir_arg:
        emit_error(
            args,
            code="ERR_SUPERFLOW_PROOFCHECK_INPUT_REQUIRED",
            message="--evidence-dir is required",
        )

    evidence_dir = Path(evidence_dir_arg)
    try:
        artifacts = load_superflow_artifacts(evidence_dir)
        verdict = build_superflow_artifact_verdict(artifacts, base_dir=evidence_dir)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_SUPERFLOW_PROOFCHECK_LOAD_FAILED",
            message=str(exc),
            path=evidence_dir,
        )

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg:
        out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(verdict, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    emit_result(
        args,
        {
            "command": "proofcheck",
            "decision": verdict["decision"],
            "error_count": verdict["error_count"],
            "evidence_dir": str(evidence_dir),
            **({"out": out_arg} if out_arg else {}),
            **({"errors": verdict["errors"]} if verdict["errors"] else {}),
        },
        human=[
            f"Proofcheck decision: {verdict['decision']}",
            f"  Evidence dir: {evidence_dir}",
            f"  Errors: {verdict['error_count']}",
            *([f"Proofcheck verdict written to {out_arg}"] if out_arg else []),
        ],
    )
    if verdict["decision"] != "pass":
        sys.exit(EXIT_FAILED)
