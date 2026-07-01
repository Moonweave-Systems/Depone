"""depone team-merge-attempt — derive git merge-attempt evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.team_merge_attempt import (
    TeamMergeAttemptError,
    _self_test as merge_attempt_self_test,
    build_team_merge_attempt_receipt,
    read_json_object,
    validate_team_merge_attempt_receipt,
    write_team_merge_attempt_receipt,
)
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        merge_attempt_self_test()
        print("depone team-merge-attempt --self-test: pass")
        return

    try:
        if str(getattr(args, "artifact", "") or ""):
            artifact = read_json_object(Path(str(args.artifact)))
        else:
            artifact = build_team_merge_attempt_receipt(
                repo=Path(str(getattr(args, "repo", ".") or ".")),
                base=str(getattr(args, "base", "") or ""),
                heads=list(getattr(args, "head", []) or []),
                disposable=not bool(getattr(args, "in_place", False)),
                allow_dirty_target=bool(getattr(args, "allow_dirty_target", False)),
                captured_at=str(getattr(args, "captured_at", "") or "") or None,
            )
        errors = validate_team_merge_attempt_receipt(artifact)
    except TeamMergeAttemptError as exc:
        emit_error(args, code=exc.code, message=exc.message)
    except OSError as exc:
        emit_error(args, code="ERR_TEAM_MERGE_ATTEMPT_FAILED", message=str(exc))

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg and not errors:
        write_team_merge_attempt_receipt(artifact, Path(out_arg))

    decision = "pass" if artifact.get("decision") == "pass" and not errors else "blocked"
    result = {
        "command": "team-merge-attempt",
        "decision": decision,
        "error_count": len(errors) + len(artifact.get("errors", []) if isinstance(artifact.get("errors"), list) else []),
        "base_commit": artifact.get("base_commit"),
        "head_commits": artifact.get("head_commits"),
        "merged_file_count": len(artifact.get("merged_files", []) if isinstance(artifact.get("merged_files"), list) else []),
        "conflict_file_count": len(artifact.get("conflict_files", []) if isinstance(artifact.get("conflict_files"), list) else []),
        **({"out": out_arg} if out_arg and not errors else {}),
        **({"errors": [*artifact.get("errors", []), *errors]} if errors or artifact.get("errors") else {}),
    }
    emit_result(
        args,
        result,
        human=[
            f"Team merge attempt decision: {decision}",
            f"  Base: {artifact.get('base_commit')}",
            f"  Heads: {len(artifact.get('head_commits', []) if isinstance(artifact.get('head_commits'), list) else [])}",
            f"  Conflicts: {len(artifact.get('conflict_files', []) if isinstance(artifact.get('conflict_files'), list) else [])}",
            *([f"Team merge attempt written to {out_arg}"] if out_arg and not errors else []),
        ],
    )
    if decision != "pass":
        sys.exit(EXIT_FAILED)
