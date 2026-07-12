from __future__ import annotations

import base64
import hashlib
import json
import unittest
from pathlib import Path

from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify.adapters.generic import read_evidence
from depone.verify.engine import run_verification
from depone.verify.evidence_contract import validate_evidence_contract
from depone.agent_fabric.evidence_substrate import build_evidence_bundle


FIXTURE_ROOT = Path("depone/fixtures/role_capability")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(path: str, value: object) -> EvidenceFile:
    content = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    return EvidenceFile(path=path, content=content, sha256=_sha(content))


def _run_intent(write_scope: list[str]) -> dict[str, object]:
    intent = {
        "schema_version": "1.1",
        "run_id": "role-capability-test",
        "allowed_paths": list(write_scope),
        "approval": {"policy": "never"},
        "sandbox": {"mode": "workspace-write"},
        "provider": {"name": "codex", "adapter_version": "test"},
        "instruction_hashes": {},
        "budgets": {},
        "capture_profile": "full",
        "role_capability": {
            "schema_version": "1.0",
            "role_id": "runner",
            "capability": "execute",
            "declared_write_scope": list(write_scope),
        },
    }
    payload = json.dumps(
        intent,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "kind": "moonweave-run-intent-artifact",
        "schema_version": "1.1",
        "intent": intent,
        "dsse_envelope": {
            "payloadType": "application/vnd.moonweave.run-intent+json",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [{"keyid": "test", "sig": "not-verified-here"}],
        },
    }


def _bundle_for(run_intent_artifact: dict[str, object]) -> dict[str, object]:
    run_intent_text = json.dumps(
        run_intent_artifact,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "kind": "depone-evidence-substrate-bundle",
        "schema_version": "1.0",
        "statement": {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [
                {
                    "name": "run-intent",
                    "digest": {"sha256": hashlib.sha256(run_intent_text.encode("utf-8")).hexdigest()},
                }
            ],
            "predicateType": "https://depone.dev/attestations/evidence/v1",
            "predicate": {"schema_version": "1.0"},
        },
    }


def _tool_bundle_for(
    run_intent_artifact: dict[str, object],
    receipts_artifact: dict[str, object],
) -> dict[str, object]:
    run_intent_text = json.dumps(
        run_intent_artifact,
        sort_keys=True,
        separators=(",", ":"),
    )
    receipts_text = json.dumps(
        receipts_artifact,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "kind": "depone-evidence-substrate-bundle",
        "schema_version": "1.0",
        "statement": {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [
                {
                    "name": "run-intent",
                    "digest": {
                        "sha256": hashlib.sha256(
                            run_intent_text.encode("utf-8")
                        ).hexdigest()
                    },
                },
                {
                    "name": "tool-call-decision-receipts",
                    "digest": {
                        "sha256": hashlib.sha256(
                            receipts_text.encode("utf-8")
                        ).hexdigest()
                    },
                },
            ],
            "predicateType": "https://depone.dev/attestations/evidence/v1",
            "predicate": {"schema_version": "1.0"},
        },
    }


def _tool_run_intent(allow: list[str]) -> dict[str, object]:
    intent = {
        "schema_version": "1.2",
        "run_id": "role-capability-tool-test",
        "allowed_paths": ["pkg/**"],
        "approval": {"policy": "never"},
        "sandbox": {"mode": "workspace-write"},
        "provider": {"name": "claude", "adapter_version": "test"},
        "instruction_hashes": {},
        "budgets": {},
        "capture_profile": "full",
        "role_capability": {
            "schema_version": "1.1",
            "role_id": "runner",
            "capability": "execute",
            "declared_write_scope": ["pkg/**"],
            "declared_tools": {
                "mcp": ["neutral_probe"],
                "allow": list(allow),
            },
        },
    }
    payload = json.dumps(
        intent,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "kind": "moonweave-run-intent-artifact",
        "schema_version": "1.2",
        "intent": intent,
        "dsse_envelope": {
            "payloadType": "application/vnd.moonweave.run-intent+json",
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [{"keyid": "test", "sig": "not-verified-here"}],
        },
    }


def _decision_sha(decision: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(decision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _tool_receipts(
    decisions: list[dict[str, object]],
    observed_calls: list[dict[str, object]],
) -> dict[str, object]:
    previous: str | None = None
    linked_decisions: list[dict[str, object]] = []
    for decision in decisions:
        current = dict(decision)
        current.setdefault("previous_decision_sha256", previous)
        linked_decisions.append(current)
        previous = _decision_sha(current)
    return {
        "kind": "moonweave-tool-call-decision-receipts",
        "schema_version": "1.0",
        "adapter": "claude",
        "role_id": "runner",
        "capability": "execute",
        "decisions": linked_decisions,
        "observed_mcp_tool_calls": list(observed_calls),
    }


def _tool_decision(
    sequence: int,
    canonical_tool_name: str,
    request_sha256: str,
    decision: str,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "canonical_tool_name": canonical_tool_name,
        "canonical_request_sha256": request_sha256,
        "decision": decision,
        "reason_code": "ROLE_CAPABILITY_TOOL_GRANTED"
        if decision == "allow"
        else "ROLE_CAPABILITY_TOOL_DENIED",
    }


def _observed_tool_call(
    canonical_tool_name: str,
    request_sha256: str,
    result_status: str = "success",
) -> dict[str, object]:
    return {
        "canonical_tool_name": canonical_tool_name,
        "canonical_request_sha256": request_sha256,
        "result_status": result_status,
    }


def _canonical_bundle_for(run_intent_artifact: dict[str, object]) -> dict[str, object]:
    intent = run_intent_artifact["intent"]
    if not isinstance(intent, dict):
        raise AssertionError("test run-intent must contain an intent object")
    return build_evidence_bundle(
        {
            "kind": "agent-fabric-capture-manifest",
            "assurance": "A1-local-observed",
            "decision": "observed-local-capture",
            "source_fixture_hash": "fixture-hash",
            "observer_capture": {
                "observed_by": "depone-observer",
                "source_fixture_hash": "fixture-hash",
                "touched_files": ["pkg/a.py"],
                "test_output": {"status": "passed"},
                "command_receipts": [],
            },
            "observer_capture_hash": "observer-hash",
            "allowed_touched_files": ["pkg/a.py"],
            "schema_version": "1.0",
        },
        run_intent=intent,
    )


def _evidence(write_scope: list[str], touched_files: list[str]) -> EvidenceContext:
    run_intent = _run_intent(write_scope)
    contract = {
        "schema_version": "v106.role_capability_write_scope",
        "role_capability_write_scope": {"run_intent_path": "run-intent.json"},
        "expected_exit_code": 0,
    }
    return EvidenceContext(
        run_id="role-capability-test",
        files=[
            _file("evidence-contract.json", contract),
            _file("run-intent.json", run_intent),
            _file("bundle.json", _bundle_for(run_intent)),
            _file("git-diff-name-only.txt", "".join(f"{path}\n" for path in touched_files)),
            _file("exit-code.txt", "0\n"),
        ],
        raw={},
    )


def _evidence_with_contract(contract: dict[str, object]) -> EvidenceContext:
    return EvidenceContext(
        run_id="role-capability-test",
        files=[
            _file("evidence-contract.json", contract),
            _file("git-diff-name-only.txt", "pkg/a.py\n"),
            _file("exit-code.txt", "0\n"),
        ],
        raw={},
    )


def _tool_evidence(
    *,
    allow: list[str],
    decisions: list[dict[str, object]],
    observed_calls: list[dict[str, object]],
    bundle_override: dict[str, object] | None = None,
) -> EvidenceContext:
    run_intent = _tool_run_intent(allow)
    receipts = _tool_receipts(decisions, observed_calls)
    return EvidenceContext(
        run_id="role-capability-tool-test",
        files=[
            _file(
                "evidence-contract.json",
                {
                    "schema_version": "v107.role_capability_tool_calls",
                    "role_capability_tool_calls": {
                        "run_intent_path": "run-intent.json",
                        "bundle_path": "bundle.json",
                        "decision_receipts_path": "tool-call-decision-receipts.json",
                    },
                    "expected_exit_code": 0,
                },
            ),
            _file("run-intent.json", run_intent),
            _file("bundle.json", bundle_override or _tool_bundle_for(run_intent, receipts)),
            _file("tool-call-decision-receipts.json", receipts),
            _file("git-diff-name-only.txt", "pkg/a.py\n"),
            _file("exit-code.txt", "0\n"),
        ],
        raw={},
    )


class RoleCapabilityWriteScopeContractTests(unittest.TestCase):
    def test_v106_write_scope_violation_refutes_from_run_intent(self) -> None:
        errors = validate_evidence_contract(_evidence(["pkg/**"], ["secrets.txt"]))

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION"
                and error.evidence_path == "secrets.txt"
                for error in errors
            ),
            errors,
        )

    def test_v106_write_scope_allows_declared_globs(self) -> None:
        errors = validate_evidence_contract(_evidence(["pkg/**"], ["pkg/a.py"]))

        self.assertEqual(errors, [])

    def test_v106_accepts_existing_canonical_run_intent_subject_digest(self) -> None:
        run_intent = _run_intent(["pkg/**"])
        evidence = EvidenceContext(
            run_id="role-capability-test",
            files=[
                _file(
                    "evidence-contract.json",
                    {
                        "schema_version": "v106.role_capability_write_scope",
                        "role_capability_write_scope": {
                            "run_intent_path": "run-intent.json"
                        },
                        "expected_exit_code": 0,
                    },
                ),
                _file("run-intent.json", run_intent),
                _file("bundle.json", _canonical_bundle_for(run_intent)),
                _file("git-diff-name-only.txt", "pkg/a.py\n"),
                _file("exit-code.txt", "0\n"),
            ],
            raw={},
        )

        self.assertEqual(validate_evidence_contract(evidence), [])

    def test_v106_write_scope_violation_refutes_verification_report(self) -> None:
        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-plan",
                "phases": [{"id": "phase-1"}],
            },
            _evidence(["pkg/**"], ["secrets.txt"]),
        )

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.role_capability_conformance[0].axis, "write_scope")
        self.assertEqual(report.role_capability_conformance[0].status, "fail")
        self.assertEqual(
            report.role_capability_conformance[0].error_code,
            "ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION",
        )

    def test_v106_write_scope_pass_surfaces_verdict_axis(self) -> None:
        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-plan",
                "phases": [{"id": "phase-1"}],
            },
            _evidence(["pkg/**"], ["pkg/a.py"]),
        )

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.role_capability_conformance[0].axis, "write_scope")
        self.assertEqual(report.role_capability_conformance[0].status, "pass")
        self.assertIsNone(report.role_capability_conformance[0].error_code)

    def test_invalid_directive_contract_does_not_surface_pass_axis(self) -> None:
        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-plan",
                "phases": [{"id": "phase-1"}],
            },
            _evidence_with_contract(
                {
                    "schema_version": "v105.verify_wedge",
                    "role_capability_write_scope": {
                        "run_intent_path": "run-intent.json"
                    },
                }
            ),
        )

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.role_capability_conformance[0].axis, "write_scope")
        self.assertEqual(report.role_capability_conformance[0].status, "fail")
        self.assertEqual(
            report.role_capability_conformance[0].error_code,
            "ERR_EVIDENCE_CONTRACT_INVALID",
        )

    def test_committed_write_scope_fixtures_capture_pass_and_fail(self) -> None:
        pass_errors = validate_evidence_contract(
            read_evidence(str(FIXTURE_ROOT / "write_scope_pass"))
        )
        fail_errors = validate_evidence_contract(
            read_evidence(str(FIXTURE_ROOT / "write_scope_fail"))
        )

        self.assertEqual(pass_errors, [])
        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION"
                for error in fail_errors
            ),
            fail_errors,
        )

    def test_committed_tool_call_fixtures_capture_pass_and_fail(self) -> None:
        pass_errors = validate_evidence_contract(
            read_evidence(str(FIXTURE_ROOT / "tool_calls_pass"))
        )
        fail_errors = validate_evidence_contract(
            read_evidence(str(FIXTURE_ROOT / "tool_calls_fail_allow_outside_grant"))
        )

        self.assertEqual(pass_errors, [])
        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT"
                for error in fail_errors
            ),
            fail_errors,
        )

    def test_v107_tool_calls_allow_declared_mcp_tool(self) -> None:
        request_sha = "a" * 64
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        1,
                        "mcp__neutral_probe__allowed_echo",
                        request_sha,
                        "allow",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__allowed_echo",
                        request_sha,
                    )
                ],
            )
        )

        self.assertEqual(errors, [])

    def test_v107_tool_calls_reject_allow_outside_grant(self) -> None:
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        1,
                        "mcp__neutral_probe__unlisted_echo",
                        "b" * 64,
                        "allow",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__unlisted_echo",
                        "b" * 64,
                    )
                ],
            )
        )

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT"
                for error in errors
            ),
            errors,
        )

    def test_v107_tool_calls_reject_observed_call_without_receipt(self) -> None:
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__allowed_echo",
                        "c" * 64,
                    )
                ],
            )
        )

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_RECEIPT_MISSING"
                for error in errors
            ),
            errors,
        )

    def test_v107_tool_calls_reject_deny_followed_by_success(self) -> None:
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        1,
                        "mcp__neutral_probe__unlisted_echo",
                        "d" * 64,
                        "deny",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__unlisted_echo",
                        "d" * 64,
                        "success",
                    )
                ],
            )
        )

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_DENY_EXECUTED"
                for error in errors
            ),
            errors,
        )

    def test_v107_tool_calls_reject_request_hash_mismatch(self) -> None:
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        1,
                        "mcp__neutral_probe__allowed_echo",
                        "e" * 64,
                        "allow",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__allowed_echo",
                        "f" * 64,
                    )
                ],
            )
        )

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_REQUEST_HASH_MISMATCH"
                for error in errors
            ),
            errors,
        )

    def test_v107_tool_calls_reject_sequence_gap(self) -> None:
        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        2,
                        "mcp__neutral_probe__allowed_echo",
                        "1" * 64,
                        "allow",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__allowed_echo",
                        "1" * 64,
                    )
                ],
            )
        )

        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_SEQUENCE_GAP"
                for error in errors
            ),
            errors,
        )

    def test_v107_tool_calls_report_surfaces_verdict_axis(self) -> None:
        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-tool-plan",
                "phases": [{"id": "phase-1"}],
            },
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=[
                    _tool_decision(
                        1,
                        "mcp__neutral_probe__unlisted_echo",
                        "2" * 64,
                        "allow",
                    )
                ],
                observed_calls=[
                    _observed_tool_call(
                        "mcp__neutral_probe__unlisted_echo",
                        "2" * 64,
                    )
                ],
            ),
        )

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.role_capability_conformance[0].axis, "tool_calls")
        self.assertEqual(report.role_capability_conformance[0].status, "fail")
        self.assertEqual(
            report.role_capability_conformance[0].error_code,
            "ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT",
        )

    def test_v107_tool_calls_report_maps_shared_run_intent_errors_to_axis(self) -> None:
        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-tool-plan",
                "phases": [{"id": "phase-1"}],
            },
            EvidenceContext(
                run_id="role-capability-tool-test",
                files=[
                    _file(
                        "evidence-contract.json",
                        {
                            "schema_version": "v107.role_capability_tool_calls",
                            "role_capability_tool_calls": {
                                "run_intent_path": "run-intent.json",
                                "bundle_path": "bundle.json",
                                "decision_receipts_path": "tool-call-decision-receipts.json",
                            },
                            "expected_exit_code": 0,
                        },
                    ),
                    _file("exit-code.txt", "0\n"),
                ],
                raw={},
            ),
        )

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.role_capability_conformance[0].axis, "tool_calls")
        self.assertEqual(report.role_capability_conformance[0].status, "fail")
        self.assertEqual(
            report.role_capability_conformance[0].error_code,
            "ERR_ROLE_CAPABILITY_RUN_INTENT_MISSING",
        )


if __name__ == "__main__":
    unittest.main()
