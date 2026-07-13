from __future__ import annotations

import atexit
import base64
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    wrap_statement_in_dsse,
)
from depone.agent_fabric.sign import (
    _generate_ed25519_keypair,
    sign_dsse_envelope,
)
from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify.adapters.generic import read_evidence
from depone.verify.engine import run_verification
from depone.verify.evidence_contract import validate_evidence_contract


FIXTURE_ROOT = Path("depone/fixtures/role_capability")
_TEST_KEY_DIRECTORY = Path(tempfile.mkdtemp())
atexit.register(shutil.rmtree, _TEST_KEY_DIRECTORY, ignore_errors=True)
_TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY = _generate_ed25519_keypair(
    _TEST_KEY_DIRECTORY
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(path: str, value: object) -> EvidenceFile:
    content = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    return EvidenceFile(path=path, content=content, sha256=_sha(content))


def _sign_bundle(bundle: dict[str, object]) -> dict[str, object]:
    statement = bundle.get("statement")
    if not isinstance(statement, dict):
        raise AssertionError("test bundle must contain a statement object")
    signed = dict(bundle)
    signed["dsse_envelope"] = sign_dsse_envelope(
        wrap_statement_in_dsse(statement),
        str(_TEST_PRIVATE_KEY),
        key_id="role-capability-test-key",
    )
    return signed


def _fixture_evidence(
    name: str,
    *,
    include_trust_anchor: bool = True,
) -> EvidenceContext:
    evidence = read_evidence(str(FIXTURE_ROOT / name))
    if include_trust_anchor:
        evidence.raw["trusted_observer_public_key_file"] = str(
            (FIXTURE_ROOT / "advisory-public-key.pem").resolve()
        )
    return evidence


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
    return _sign_bundle(
        {
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
                    }
                ],
                "predicateType": "https://depone.dev/attestations/evidence/v1",
                "predicate": {"schema_version": "1.0"},
            },
        }
    )


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
    return _sign_bundle(
        {
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
    )


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
    return _sign_bundle(
        build_evidence_bundle(
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
        raw={"trusted_observer_public_key_file": str(_TEST_PUBLIC_KEY)},
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
    include_write_scope: bool = False,
) -> EvidenceContext:
    run_intent = _tool_run_intent(allow)
    receipts = _tool_receipts(decisions, observed_calls)
    contract: dict[str, object] = {
        "schema_version": "v107.role_capability_tool_calls",
        "role_capability_tool_calls": {
            "run_intent_path": "run-intent.json",
            "bundle_path": "bundle.json",
            "decision_receipts_path": "tool-call-decision-receipts.json",
        },
        "expected_exit_code": 0,
    }
    if include_write_scope:
        contract["role_capability_write_scope"] = {
            "run_intent_path": "run-intent.json",
            "bundle_path": "bundle.json",
        }
    return EvidenceContext(
        run_id="role-capability-tool-test",
        files=[
            _file("evidence-contract.json", contract),
            _file("run-intent.json", run_intent),
            _file("bundle.json", bundle_override or _tool_bundle_for(run_intent, receipts)),
            _file("tool-call-decision-receipts.json", receipts),
            _file("git-diff-name-only.txt", "pkg/a.py\n"),
            _file("exit-code.txt", "0\n"),
        ],
        raw={"trusted_observer_public_key_file": str(_TEST_PUBLIC_KEY)},
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
            raw={"trusted_observer_public_key_file": str(_TEST_PUBLIC_KEY)},
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
        pass_errors = validate_evidence_contract(_fixture_evidence("write_scope_pass"))
        fail_errors = validate_evidence_contract(_fixture_evidence("write_scope_fail"))

        self.assertEqual(pass_errors, [])
        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION"
                for error in fail_errors
            ),
            fail_errors,
        )

    def test_committed_tool_call_fixtures_capture_pass_and_fail(self) -> None:
        pass_errors = validate_evidence_contract(_fixture_evidence("tool_calls_pass"))
        fail_errors = validate_evidence_contract(
            _fixture_evidence("tool_calls_fail_allow_outside_grant")
        )

        self.assertEqual(pass_errors, [])
        self.assertTrue(
            any(
                error.code == "ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT"
                for error in fail_errors
            ),
            fail_errors,
        )

    def test_v106_unsigned_bundle_refutes_before_subject_digest(self) -> None:
        errors = validate_evidence_contract(
            _fixture_evidence("write_scope_fail_unsigned")
        )

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_SIGNATURE_MISSING"],
        )
        self.assertIn("not re-derivable from a trusted anchor", errors[0].message)

    def test_v106_bad_signature_refutes_before_subject_digest(self) -> None:
        errors = validate_evidence_contract(
            _fixture_evidence("write_scope_fail_bad_signature")
        )

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_SIGNATURE_INVALID"],
        )
        self.assertIn("not verifiable", errors[0].message)

    def test_v106_malformed_signature_refutes_as_missing(self) -> None:
        run_intent = _run_intent(["pkg/**"])
        malformed_bundle = _bundle_for(run_intent)
        envelope = malformed_bundle["dsse_envelope"]
        if not isinstance(envelope, dict):
            raise AssertionError("test bundle must contain a DSSE envelope")
        envelope["signatures"] = [{"keyid": "malformed", "sig": "%%%"}]
        evidence = _evidence(["pkg/**"], ["pkg/a.py"])
        evidence.files = [
            _file("bundle.json", malformed_bundle)
            if entry.path == "bundle.json"
            else entry
            for entry in evidence.files
        ]

        errors = validate_evidence_contract(evidence)

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_SIGNATURE_MISSING"],
        )

    def test_v106_subject_digest_comes_from_signed_statement(self) -> None:
        run_intent = _run_intent(["pkg/**"])
        bundle = _bundle_for(run_intent)
        statement = bundle["statement"]
        if not isinstance(statement, dict):
            raise AssertionError("test bundle must contain a statement")
        subjects = statement["subject"]
        if not isinstance(subjects, list) or not isinstance(subjects[0], dict):
            raise AssertionError("test statement must contain a subject")
        subjects[0]["digest"] = {"sha256": "0" * 64}
        evidence = _evidence(["pkg/**"], ["pkg/a.py"])
        evidence.files = [
            _file("bundle.json", bundle)
            if entry.path == "bundle.json"
            else entry
            for entry in evidence.files
        ]

        errors = validate_evidence_contract(evidence)

        self.assertEqual(errors, [])

    def test_v106_missing_trust_anchor_refutes_before_subject_digest(self) -> None:
        errors = validate_evidence_contract(
            _fixture_evidence(
                "write_scope_fail_no_trust_anchor",
                include_trust_anchor=False,
            )
        )

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING"],
        )
        self.assertIn("trusted anchor", errors[0].message)

    def test_v107_unsigned_bundle_refutes_before_subject_digest(self) -> None:
        request_sha = "a" * 64
        run_intent = _tool_run_intent(["mcp__neutral_probe__allowed_echo"])
        receipts = _tool_receipts(
            [
                _tool_decision(
                    1,
                    "mcp__neutral_probe__allowed_echo",
                    request_sha,
                    "allow",
                )
            ],
            [
                _observed_tool_call(
                    "mcp__neutral_probe__allowed_echo",
                    request_sha,
                )
            ],
        )
        unsigned_bundle = _tool_bundle_for(run_intent, receipts)
        unsigned_bundle.pop("dsse_envelope")

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
                bundle_override=unsigned_bundle,
            )
        )

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_SIGNATURE_MISSING"],
        )

    def test_v107_bad_signature_refutes_before_subject_digest(self) -> None:
        request_sha = "a" * 64
        run_intent = _tool_run_intent(["mcp__neutral_probe__allowed_echo"])
        decisions = [
            _tool_decision(
                1,
                "mcp__neutral_probe__allowed_echo",
                request_sha,
                "allow",
            )
        ]
        observed_calls = [
            _observed_tool_call(
                "mcp__neutral_probe__allowed_echo",
                request_sha,
            )
        ]
        receipts = _tool_receipts(decisions, observed_calls)
        bad_bundle = _tool_bundle_for(run_intent, receipts)
        envelope = bad_bundle["dsse_envelope"]
        if not isinstance(envelope, dict):
            raise AssertionError("test bundle must contain a DSSE envelope")
        signatures = envelope["signatures"]
        if not isinstance(signatures, list) or not isinstance(signatures[0], dict):
            raise AssertionError("test DSSE envelope must contain a signature")
        signatures[0]["sig"] = base64.b64encode(b"invalid signature").decode(
            "ascii"
        )

        errors = validate_evidence_contract(
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=decisions,
                observed_calls=observed_calls,
                bundle_override=bad_bundle,
            )
        )

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_SIGNATURE_INVALID"],
        )

    def test_v107_missing_trust_anchor_refutes_before_subject_digest(self) -> None:
        request_sha = "a" * 64
        evidence = _tool_evidence(
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
        evidence.raw = {}

        errors = validate_evidence_contract(evidence)

        self.assertEqual(
            [error.code for error in errors],
            ["ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING"],
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

    def test_v107_tool_calls_can_coexist_with_write_scope_axis(self) -> None:
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
                include_write_scope=True,
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

    def test_signature_failure_maps_to_both_role_capability_axes(self) -> None:
        request_sha = "a" * 64
        decisions = [
            _tool_decision(
                1,
                "mcp__neutral_probe__allowed_echo",
                request_sha,
                "allow",
            )
        ]
        observed_calls = [
            _observed_tool_call(
                "mcp__neutral_probe__allowed_echo",
                request_sha,
            )
        ]
        run_intent = _tool_run_intent(["mcp__neutral_probe__allowed_echo"])
        unsigned_bundle = _tool_bundle_for(
            run_intent,
            _tool_receipts(decisions, observed_calls),
        )
        unsigned_bundle.pop("dsse_envelope")

        report = run_verification(
            {
                "schema_version": "0.5",
                "plan_id": "role-capability-shared-signature-plan",
                "phases": [{"id": "phase-1"}],
            },
            _tool_evidence(
                allow=["mcp__neutral_probe__allowed_echo"],
                decisions=decisions,
                observed_calls=observed_calls,
                bundle_override=unsigned_bundle,
                include_write_scope=True,
            ),
        )

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(
            [
                (entry.axis, entry.status, entry.error_code)
                for entry in report.role_capability_conformance
            ],
            [
                (
                    "tool_calls",
                    "fail",
                    "ERR_ROLE_CAPABILITY_SIGNATURE_MISSING",
                ),
                (
                    "write_scope",
                    "fail",
                    "ERR_ROLE_CAPABILITY_SIGNATURE_MISSING",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
