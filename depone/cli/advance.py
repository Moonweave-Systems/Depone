from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from depone.cli import evidence_next, evidence_run
from depone.cli._response import EXIT_FAILED, emit_error, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    try:
        payload = advance_once(args)
    except (OSError, json.JSONDecodeError, ValueError, NotADirectoryError) as exc:
        emit_error(
            args,
            code="ERR_ADVANCE_INPUT",
            message=str(exc),
        )

    emit_result(
        args,
        payload,
        human=[
            f"Advance decision: {payload['decision']}",
            f"Gate decision: {payload['gate']['decision']}",
            f"Executed continuations: {payload['executed_continuations']}",
            f"Advance artifact: {payload['advance_out']}",
        ],
    )
    exit_code = exit_code_for_decision(str(payload["decision"]))
    if exit_code:
        sys.exit(exit_code)


def advance_once(args: argparse.Namespace) -> dict[str, Any]:
    evidence_dir_arg = str(getattr(args, "evidence_dir", "") or "")
    if not evidence_dir_arg:
        raise ValueError("--evidence-dir is required")
    evidence_dir = Path(evidence_dir_arg)
    source_fixture_arg = str(getattr(args, "source_fixture", "") or "")
    gate = evidence_next.evaluate_evidence_dir(
        evidence_dir,
        source_fixture=Path(source_fixture_arg) if source_fixture_arg else None,
    )

    out_arg = str(getattr(args, "advance_out", "") or "advance-decision.json")
    advance_out = Path(out_arg)
    payload: dict[str, Any] = {
        "command": "advance",
        "schema_version": "1.0",
        "evidence_dir": str(evidence_dir),
        "advance_out": str(advance_out),
        "gate": {
            "command": gate.get("command"),
            "decision": gate.get("decision"),
            "next_action": gate.get("next_action"),
            "blocking_reasons": gate.get("blocking_reasons", []),
            "assurance": gate.get("assurance"),
        },
        "executed_continuations": 0,
        "automation_boundary": {
            "executes_at_most_one_existing_evidence_run": True,
            "scheduler": False,
            "agent_runtime": False,
        },
    }

    blocking_reasons = gate.get("blocking_reasons", [])
    if gate.get("decision") != "continue" or blocking_reasons:
        payload["decision"] = "blocked"
        payload["reason"] = "evidence-next gate did not allow continuation"
        _write_decision(advance_out, payload)
        return payload

    continuation = evidence_run.run_evidence_loop(args)
    payload["executed_continuations"] = 1
    payload["continuation"] = {
        "command": continuation.get("command"),
        "decision": continuation.get("decision"),
        "out": continuation.get("out"),
        "observe": continuation.get("observe"),
        "evidence_ingest": continuation.get("evidence_ingest"),
        "verify": continuation.get("verify"),
    }
    payload["decision"] = continuation.get("decision", "blocked")
    _write_decision(advance_out, payload)
    return payload


def _write_decision(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="depone-advance-self-test-") as tmp:
        root = Path(tmp)
        sandbox = root / "sandbox"
        sandbox.mkdir()
        advance_out = root / "advance-decision.json"
        run_out = root / "evidence-run"
        args = argparse.Namespace(
            evidence_dir="docs/depone-run-receipt-frontdoor",
            advance_out=str(advance_out),
            runner_sandbox=str(sandbox),
            source_fixture="depone/fixtures/agent_fabric/reference_adapter_shell.json",
            runner_uid=None,
            runner_user="",
            runner_command="",
            runner_container_id="",
            runner_container_image="",
            runner_container_command="",
            runner_container_hold_seconds=1,
            out=str(run_out),
            timeout_seconds=30,
            allow_touched_file=[],
            verify_plan="",
            verify_evidence="",
            verify_adapter="generic",
            operator_view_out="",
            sign_private_key="",
            sign_key_id="",
            sign_public_key="",
            verification_command=[sys.executable, "-c", "print('advance self-test')"],
        )
        payload = advance_once(args)
        if payload.get("executed_continuations") != 1:
            raise SystemExit("advance self-test did not execute exactly one continuation")
        if not advance_out.is_file():
            raise SystemExit("advance self-test did not write decision artifact")
        recorded = json.loads(advance_out.read_text(encoding="utf-8"))
        if recorded.get("command") != "advance":
            raise SystemExit("advance self-test wrote malformed decision artifact")
