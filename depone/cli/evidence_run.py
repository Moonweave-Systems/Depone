from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import (
    ASSURANCE_A2,
    build_capture_manifest,
    validate_capture_manifest,
)
from depone.agent_fabric.isolation import probe_isolation_facts
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import (
    DIGEST_MODE_CANONICAL_JSON,
    build_evidence_bundle,
    ingest_external_evidence,
    validate_statement_for_capture,
)
from depone.agent_fabric.observe import (
    build_separated_observer_capture,
    write_observer_capture,
)
from depone.agent_fabric.paired_run import PairedRunError
from depone.cli._response import (
    EXIT_FAILED,
    EXIT_INCONCLUSIVE,
    EXIT_INTERNAL,
    emit_error,
    emit_result,
    exit_code_for_decision,
)
from depone.core.plan_schema import load_plan
from depone.verify.adapters import resolve
from depone.verify.engine import run_verification
from depone.verify.operator_view import write_operator_view


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    try:
        payload = run_evidence_loop(args)
    except PairedRunError as exc:
        record = exc.to_record()
        emit_error(
            args,
            code=str(record.get("code", "ERR_EVIDENCE_RUN_OBSERVE")),
            message=str(record.get("message", exc)),
            path=record.get("path"),
        )
    except (OSError, json.JSONDecodeError, ValueError, NotADirectoryError) as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_RUN_INPUT",
            message=str(exc),
        )
    except Exception as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_RUN_INTERNAL",
            message=str(exc),
            exit_code=EXIT_INTERNAL,
        )

    emit_result(
        args,
        payload,
        human=[
            f"Evidence run decision: {payload['decision']}",
            f"Evidence run output: {payload['out']}",
            f"  observe: {payload['observe']['decision']}",
            f"  evidence-ingest: {payload['evidence_ingest']['decision']}",
            f"  verify: {payload['verify']['decision']}",
        ],
    )
    exit_code = exit_code_for_decision(str(payload["decision"]))
    if exit_code:
        sys.exit(exit_code)


def run_evidence_loop(args: argparse.Namespace) -> dict[str, Any]:
    command = list(getattr(args, "verification_command", []) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError(
            "verification command is required after --, for example -- python -m unittest"
        )
    runner_sandbox = Path(str(getattr(args, "runner_sandbox", "") or ""))
    if not str(runner_sandbox):
        raise ValueError("--runner-sandbox is required")
    source_fixture_path = Path(str(getattr(args, "source_fixture", "") or ""))
    if not str(source_fixture_path):
        raise ValueError("--source-fixture is required")

    verify_plan = str(getattr(args, "verify_plan", "") or "")
    verify_evidence = str(getattr(args, "verify_evidence", "") or "")
    if bool(verify_plan) != bool(verify_evidence):
        raise ValueError("--verify-plan and --verify-evidence must be provided together")

    out_dir = Path(str(getattr(args, "out", "evidence-run")))
    observer_dir = out_dir / "observer-owned"
    out_dir.mkdir(parents=True, exist_ok=True)
    observer_dir.mkdir(parents=True, exist_ok=True)

    source_fixture = _read_json(source_fixture_path)
    source_fixture_hash = canonical_hash(source_fixture)
    observer_path = observer_dir / "observer-capture.json"
    log_path = observer_dir / "verify-log.json"
    capture = build_separated_observer_capture(
        runner_sandbox=runner_sandbox,
        source_fixture_hash=source_fixture_hash,
        verification_command=command,
        out_path=observer_path,
        log_path=log_path,
        timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
    )
    observer_capture_hash = write_observer_capture(observer_path, capture)

    allowed_touched_files = list(getattr(args, "allow_touched_file", []) or [])
    # Isolation facts are observer-attested: the observer supplies the uid it
    # launched the runner under, and probe_isolation_facts measures whether its
    # own output dir is writable by a different uid. A2 is reached only when both
    # hold. Omitting --runner-uid (or a same-uid host) keeps the manifest at A1.
    runner_uid_arg = getattr(args, "runner_uid", None)
    isolation_facts = (
        probe_isolation_facts(observer_dir, runner_uid=int(runner_uid_arg))
        if runner_uid_arg is not None
        else None
    )
    capture_manifest = build_capture_manifest(
        source_fixture,
        observer_capture=capture,
        allowed_touched_files=allowed_touched_files,
        isolation=isolation_facts,
    )
    capture_errors = validate_capture_manifest(capture_manifest)
    capture_manifest_path = out_dir / "capture-manifest.json"
    _write_json(capture_manifest_path, capture_manifest)

    bundle = build_evidence_bundle(capture_manifest)
    substrate_errors = validate_statement_for_capture(
        bundle["statement"], capture_manifest
    )
    bundle_path = out_dir / "evidence-bundle.json"
    _write_json(bundle_path, bundle)

    ingest_verdict = ingest_external_evidence(
        bundle["dsse_envelope"],
        {
            "depone-capture-manifest": str(capture_manifest_path),
            "source_fixture": str(source_fixture_path),
            "observer_capture": str(observer_path),
        },
        artifact_digest_modes={
            "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
            "source_fixture": DIGEST_MODE_CANONICAL_JSON,
            "observer_capture": DIGEST_MODE_CANONICAL_JSON,
        },
        otel_spans=bundle["otel_spans"],
    )
    ingest_path = out_dir / "ingest-verdict.json"
    _write_json(ingest_path, ingest_verdict)

    verify_payload: dict[str, Any]
    if verify_plan and verify_evidence:
        verify_payload = _run_verify(args, out_dir, verify_plan, verify_evidence)
    else:
        verify_payload = {
            "decision": "skipped",
            "verdict": "skipped",
            "out": None,
            "operator_view_out": None,
        }

    observer_status = _observer_status(capture)
    observer_decision = "pass" if observer_status == "passed" else "blocked"
    decision = _aggregate_decision(
        [
            observer_decision,
            "blocked" if capture_errors or substrate_errors else "pass",
            str(ingest_verdict.get("decision", "blocked")),
            str(verify_payload["decision"]),
        ]
    )
    payload = {
        "command": "evidence-run",
        "decision": decision,
        "out": str(out_dir),
        "observe": {
            "decision": observer_decision,
            "status": observer_status,
            "out": str(observer_path),
            "log": str(log_path),
            "observer_capture_hash": observer_capture_hash,
        },
        "capture_manifest": {
            "path": str(capture_manifest_path),
            "assurance": capture_manifest.get("assurance"),
            "decision": capture_manifest.get("decision"),
            "error_count": len(capture_errors),
            "errors": capture_errors,
        },
        "evidence_substrate": {
            "decision": "blocked" if substrate_errors else "pass",
            "out": str(bundle_path),
            "assurance": bundle.get("assurance"),
            "signing_status": bundle.get("signing_status"),
            "subject_count": len(bundle["statement"].get("subject", [])),
            "otel_span_count": len(bundle["otel_spans"]),
            "error_count": len(substrate_errors),
            "errors": substrate_errors,
        },
        "evidence_ingest": {
            "decision": ingest_verdict.get("decision"),
            "out": str(ingest_path),
            "subject_count": len(ingest_verdict.get("subject_results", [])),
            "verified_subject_count": ingest_verdict.get("verified_subject_count", 0),
            "signing_status": ingest_verdict.get("signing_status"),
        },
        "verify": verify_payload,
        "boundary": {
            "observer_assurance": capture_manifest.get("assurance"),
            "privilege_isolated": capture_manifest.get("assurance") == ASSURANCE_A2,
            "isolation": capture_manifest.get("isolation"),
            "note": (
                "A2 isolated observed: runner ran under a different uid and could "
                "not write the observer output."
                if capture_manifest.get("assurance") == ASSURANCE_A2
                else "A1 local observed evidence; not A2 privilege isolation."
            ),
        },
    }
    _write_json(out_dir / "evidence-run-summary.json", payload)
    return payload


def _run_verify(
    args: argparse.Namespace,
    out_dir: Path,
    verify_plan: str,
    verify_evidence: str,
) -> dict[str, Any]:
    import importlib

    adapter = str(getattr(args, "verify_adapter", "generic"))
    plan = load_plan(verify_plan)
    adapter_mod = resolve(adapter)
    mod = importlib.import_module(adapter_mod)
    evidence = mod.read_evidence(verify_evidence)
    report = run_verification(plan, evidence, framework=adapter)
    report_dict = asdict(report)
    report_path = out_dir / "verify-report.json"
    _write_json(report_path, report_dict)

    operator_view_arg = str(getattr(args, "operator_view_out", "") or "")
    operator_view_path = (
        Path(operator_view_arg) if operator_view_arg else out_dir / "operator-view.md"
    )
    write_operator_view(report, str(operator_view_path))
    return {
        "decision": report_dict["decision"],
        "verdict": report_dict["verdict"],
        "assurance": report_dict["assurance"],
        "out": str(report_path),
        "operator_view_out": str(operator_view_path),
        "phase_count": len(report_dict["phases"]),
    }


def _aggregate_decision(decisions: list[str]) -> str:
    normalized = [decision.lower() for decision in decisions]
    if any(decision in {"fail", "blocked", "refuted"} for decision in normalized):
        return "blocked"
    if any(
        decision in {"inconclusive", "insufficient-evidence", "skipped"}
        for decision in normalized
    ):
        return "inconclusive"
    return "pass"


def _observer_status(capture: dict[str, Any]) -> str:
    test_output = capture.get("test_output")
    if isinstance(test_output, dict):
        return str(test_output.get("status", "unknown"))
    return "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    import subprocess

    def run_git(repo: Path, args: list[str]) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr.strip() or result.stdout.strip())

    with tempfile.TemporaryDirectory(prefix="depone-evidence-run-") as temp_dir:
        root = Path(temp_dir)
        runner = root / "runner-sandbox"
        runner.mkdir()
        run_git(runner, ["init"])
        run_git(runner, ["config", "user.email", "observer@example.invalid"])
        run_git(runner, ["config", "user.name", "Observer Test"])
        (runner / "sample.txt").write_text("before\n", encoding="utf-8")
        run_git(runner, ["add", "sample.txt"])
        run_git(runner, ["commit", "-m", "seed"])
        (runner / "sample.txt").write_text("after\n", encoding="utf-8")

        source_fixture = root / "reference_adapter_shell.json"
        source_fixture.write_text(
            resource_text("fixtures/agent_fabric/reference_adapter_shell.json"),
            encoding="utf-8",
        )
        repo_root = Path(__file__).resolve().parents[2]
        plan_path = repo_root / "fixtures" / "v105-verify-wedge" / "plan.json"
        evidence_path = repo_root / "fixtures" / "v105-verify-wedge" / "evidence" / "good"
        args = argparse.Namespace(
            runner_sandbox=str(runner),
            source_fixture=str(source_fixture),
            out=str(root / "evidence-run"),
            allow_touched_file=["sample.txt"],
            verify_plan=str(plan_path),
            verify_evidence=str(evidence_path),
            verify_adapter="generic",
            operator_view_out="",
            timeout_seconds=120,
            runner_uid=None,
            verification_command=[
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('sample.txt').exists()",
            ],
            json=False,
        )
        payload = run_evidence_loop(args)
        if payload["decision"] != "pass":
            raise AssertionError(f"expected evidence-run pass: {payload}")
        # Same-uid host (no --runner-uid): must stay honestly at A1, never A2.
        if payload["boundary"]["observer_assurance"] != "A1-local-observed":
            raise AssertionError(f"same-uid run must stay A1: {payload['boundary']}")
        if payload["boundary"]["privilege_isolated"] is not False:
            raise AssertionError("same-uid run must not claim privilege isolation")
        summary_path = Path(str(payload["out"])) / "evidence-run-summary.json"
        if not summary_path.is_file():
            raise AssertionError("expected evidence-run summary")
    print("depone evidence-run --self-test: pass")
