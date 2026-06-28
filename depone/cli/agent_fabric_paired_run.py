from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.paired_run import (
    PairedRunError,
    build_observer_capture,
    build_paired_run_report,
    build_runner_receipt,
    changed_files,
    now_utc,
    run_codex_exec,
    validate_runner_receipt,
)


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    report_out = getattr(args, "report_out", None)
    if report_out:
        for field in (
            "direct_runner",
            "direct_observer",
            "governed_runner",
            "governed_observer",
        ):
            if not getattr(args, field, ""):
                print(f"Error: --{field.replace('_', '-')} is required with --report-out", file=sys.stderr)
                sys.exit(1)
        report = build_paired_run_report(
            task_id=str(getattr(args, "task_id", "manual-task")),
            direct_runner=_read_json(Path(str(getattr(args, "direct_runner")))),
            direct_observer=_read_json(Path(str(getattr(args, "direct_observer")))),
            governed_runner=_read_json(Path(str(getattr(args, "governed_runner")))),
            governed_observer=_read_json(Path(str(getattr(args, "governed_observer")))),
        )
        out_path = Path(report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Paired-run report written to {out_path}")
        print(f"  Decision: {report['decision']}")
        return

    command = list(getattr(args, "verification_command", []) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(
            "Usage: depone agent-fabric-paired-run --source-fixture-hash <hash> -- <verification command>",
            file=sys.stderr,
        )
        sys.exit(1)
    source_fixture_hash = getattr(args, "source_fixture_hash", None)
    if not source_fixture_hash:
        print("Error: --source-fixture-hash is required", file=sys.stderr)
        sys.exit(1)

    repo = Path(getattr(args, "repo", "."))
    out_path = Path(getattr(args, "out", "observer-capture.json"))
    log_path = Path(getattr(args, "log", str(out_path.with_suffix(".log.json"))))
    receipt_out = getattr(args, "runner_receipt_out", None)
    codex_prompt = _codex_prompt_from_args(args)

    try:
        if codex_prompt:
            if not receipt_out:
                print(
                    "Error: --runner-receipt-out is required with Codex execution",
                    file=sys.stderr,
                )
                sys.exit(1)
            receipt_path = Path(receipt_out)
            transcript_path = Path(str(getattr(args, "transcript_path", "")))
            if not str(transcript_path):
                transcript_path = receipt_path.with_suffix(".transcript.md")
            runner_log_path = Path(str(getattr(args, "runner_log", "")))
            if not str(runner_log_path):
                runner_log_path = receipt_path.with_suffix(".codex-log.json")
            receipt = run_codex_exec(
                repo,
                arm=str(getattr(args, "arm", "direct")),
                task_id=str(getattr(args, "task_id", "manual-task")),
                prompt=codex_prompt,
                transcript_path=transcript_path,
                log_path=runner_log_path,
                timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
                sandbox=str(getattr(args, "codex_sandbox", "workspace-write")),
            )
            _write_runner_receipt(receipt_path, receipt)
        capture = build_observer_capture(
            repo,
            source_fixture_hash=str(source_fixture_hash),
            verification_command=command,
            log_path=log_path,
            timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
        )
    except PairedRunError as exc:
        print(json.dumps({"error": exc.to_record()}, sort_keys=True), file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if receipt_out and not codex_prompt:
        receipt = build_runner_receipt(
            runner_kind=str(getattr(args, "runner_kind", "manual")),
            arm=str(getattr(args, "arm", "direct")),
            task_id=str(getattr(args, "task_id", "manual-task")),
            worktree=str(repo.resolve(strict=False)),
            invocation=[str(item) for item in getattr(args, "runner_invocation", [])],
            transcript_path=str(getattr(args, "transcript_path", "")),
            exit_code=int(getattr(args, "runner_exit_code", 0)),
            touched_files=changed_files(repo),
            started_at=str(getattr(args, "started_at", "")) or now_utc(),
            ended_at=str(getattr(args, "ended_at", "")) or now_utc(),
            human_intervened=bool(getattr(args, "human_intervened", False)),
        )
        _write_runner_receipt(Path(receipt_out), receipt)

    print(f"Observer capture written to {out_path}")


def _codex_prompt_from_args(args: argparse.Namespace) -> str | None:
    prompt = getattr(args, "codex_prompt", None)
    prompt_file = getattr(args, "codex_prompt_file", None)
    if prompt and prompt_file:
        print("Error: use only one of --codex-prompt or --codex-prompt-file", file=sys.stderr)
        sys.exit(1)
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    return str(prompt) if prompt else None


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read JSON {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(value, dict):
        print(f"Error: JSON root must be an object: {path}", file=sys.stderr)
        sys.exit(1)
    return value


def _write_runner_receipt(path: Path, receipt: dict[str, object]) -> None:
    errors = validate_runner_receipt(receipt)
    if errors:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "ERR_RUNNER_RECEIPT_INVALID",
                        "validation_errors": errors,
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    from depone.agent_fabric.paired_run import _self_test as paired_run_self_test

    paired_run_self_test()
    print("depone agent-fabric-paired-run --self-test: pass")
