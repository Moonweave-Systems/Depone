"""V126 paired-run receipt and report verification helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash

RUNNER_RECEIPT_KIND = "agent-fabric-runner-receipt"
RUNNER_RECEIPT_VERSION = "1.0"
PAIRED_RUN_REPORT_KIND = "agent-fabric-paired-run-report"
PAIRED_RUN_REPORT_VERSION = "1.0"
PAIRED_RUN_READY_DECISION = "paired-run-observed"
VALID_ARMS = frozenset({"direct", "governed"})
VALID_RUNNERS = frozenset({"codex-cli", "manual"})


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _require_string(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty string")


def build_runner_receipt(
    *,
    runner_kind: str,
    arm: str,
    task_id: str,
    worktree: str,
    invocation: list[str],
    transcript_path: str,
    exit_code: int,
    touched_files: list[str],
    started_at: str,
    ended_at: str,
    human_intervened: bool = False,
) -> dict[str, Any]:
    receipt = {
        "kind": RUNNER_RECEIPT_KIND,
        "schema_version": RUNNER_RECEIPT_VERSION,
        "runner_kind": runner_kind,
        "arm": arm,
        "task_id": task_id,
        "worktree": worktree,
        "invocation": invocation,
        "transcript_path": transcript_path,
        "exit_code": exit_code,
        "touched_files": touched_files,
        "started_at": started_at,
        "ended_at": ended_at,
        "human_intervened": human_intervened,
    }
    receipt["source_hashes"] = {"receipt": canonical_hash(receipt)}
    return receipt


def validate_runner_receipt(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if receipt.get("kind") != RUNNER_RECEIPT_KIND:
        errors.append(f"kind must be {RUNNER_RECEIPT_KIND!r}")
    if receipt.get("schema_version") != RUNNER_RECEIPT_VERSION:
        errors.append(f"schema_version must be {RUNNER_RECEIPT_VERSION!r}")
    if receipt.get("runner_kind") not in VALID_RUNNERS:
        errors.append(f"runner_kind must be one of {sorted(VALID_RUNNERS)}")
    if receipt.get("arm") not in VALID_ARMS:
        errors.append(f"arm must be one of {sorted(VALID_ARMS)}")
    for field in ("task_id", "worktree", "transcript_path", "started_at", "ended_at"):
        _require_string(receipt.get(field), field, errors)
    if not isinstance(receipt.get("exit_code"), int):
        errors.append("exit_code must be an int")
    if not isinstance(receipt.get("human_intervened"), bool):
        errors.append("human_intervened must be a bool")
    if not _string_list(receipt.get("invocation")):
        errors.append("invocation must be a non-empty list of strings")
    if not isinstance(receipt.get("touched_files"), list) or not all(
        isinstance(item, str) for item in receipt.get("touched_files", [])
    ):
        errors.append("touched_files must be a list of strings")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict):
        errors.append("source_hashes must be an object")
    elif source_hashes.get("receipt") != canonical_hash(
        {key: value for key, value in receipt.items() if key != "source_hashes"}
    ):
        errors.append("source_hashes.receipt mismatch")
    return errors


def _observer_test_status(observer_capture: dict[str, Any]) -> object:
    test_output = observer_capture.get("test_output")
    if isinstance(test_output, dict):
        return test_output.get("status")
    return None


def _observer_touched_files(observer_capture: dict[str, Any]) -> list[str]:
    return _string_list(observer_capture.get("touched_files"))


def build_paired_run_report(
    *,
    task_id: str,
    direct_runner: dict[str, Any],
    direct_observer: dict[str, Any],
    governed_runner: dict[str, Any],
    governed_observer: dict[str, Any],
) -> dict[str, Any]:
    """Summarize existing direct-vs-governed evidence without executing it."""

    blockers: list[dict[str, Any]] = []
    arms = [
        ("direct", direct_runner, direct_observer),
        ("governed", governed_runner, governed_observer),
    ]
    arm_reports: list[dict[str, Any]] = []
    for arm, runner, observer in arms:
        runner_errors = validate_runner_receipt(runner)
        test_status = _observer_test_status(observer)
        runner_exit_code = runner.get("exit_code")
        arm_report = {
            "arm": arm,
            "runner_kind": runner.get("runner_kind"),
            "runner_exit_code": runner_exit_code,
            "verification_status": test_status,
            "runner_touched_files": _string_list(runner.get("touched_files")),
            "observer_touched_files": _observer_touched_files(observer),
            "transcript_path": runner.get("transcript_path"),
            "runner_validation_errors": runner_errors,
        }
        arm_reports.append(arm_report)
        if runner.get("arm") != arm:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_ARM_MISMATCH",
                    "message": "runner receipt arm does not match report slot",
                    "arm": arm,
                    "actual": runner.get("arm"),
                }
            )
        if runner_errors:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_RUNNER_RECEIPT_INVALID",
                    "message": "runner receipt failed validation",
                    "arm": arm,
                    "validation_errors": runner_errors,
                }
            )
        if runner_exit_code != 0:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_RUNNER_FAILED",
                    "message": "runner did not exit cleanly",
                    "arm": arm,
                    "exit_code": runner_exit_code,
                }
            )
        if test_status != "passed":
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_VERIFICATION_NOT_PASSED",
                    "message": "observer verification did not pass",
                    "arm": arm,
                    "test_status": test_status,
                }
            )

    return {
        "kind": PAIRED_RUN_REPORT_KIND,
        "schema_version": PAIRED_RUN_REPORT_VERSION,
        "decision": PAIRED_RUN_READY_DECISION
        if not blockers
        else "blocked-paired-run-not-ready",
        "task_id": task_id,
        "arms": arm_reports,
        "blockers": blockers,
        "claim_policy": "observed run only; no direct-agent superiority claim",
        "source_hashes": {
            "direct_runner": canonical_hash(direct_runner),
            "direct_observer": canonical_hash(direct_observer),
            "governed_runner": canonical_hash(governed_runner),
            "governed_observer": canonical_hash(governed_observer),
        },
        "boundary": {
            "approves_public_claim": False,
            "trust_upgrade": False,
        },
    }
