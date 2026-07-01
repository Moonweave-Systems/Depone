"""Tests for surfacing Agent Fabric capture assurance in verification reports."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depone.agent_fabric.capture_bridge import build_capture_manifest
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.observer_provenance import (
    build_trusted_observer_provenance,
)
from depone.agent_fabric.reference_adapter import build_reference_adapter_fixture
from depone.agent_fabric.seal import seal_capture
from depone.agent_fabric.sign import (
    _generate_ed25519_keypair,
    openssl_path,
    sign_dsse_envelope,
)
from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify import run as run_verify
from depone.verify.engine import run_verification
from depone.verify.operator_view import render_operator_view


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(path: str, content: str) -> EvidenceFile:
    return EvidenceFile(path=path, content=content, sha256=_sha(content))


def _plan() -> dict:
    return {
        "schema_version": "0.5",
        "plan_id": "agent-fabric-assurance-test",
        "created_by": "depone",
        "source_prompt": "test",
        "activation": {"decision": "activate", "matched_thresholds": []},
        "phases": [{"id": "phase-1", "title": "Phase 1"}],
        "handoffs": [],
        "risk_gates": [],
        "verification": [],
        "budget": {},
    }


def _base_evidence_files(manifest: dict) -> list[EvidenceFile]:
    contract = json.dumps(
        {
            "schema_version": "v105.verify_wedge",
            "required_evidence": ["run-metadata.json"],
        },
        sort_keys=True,
    )
    metadata = json.dumps({"run_id": "assurance-test-run"}, sort_keys=True)
    manifest_text = json.dumps(manifest, sort_keys=True)
    return [
        _file("evidence-contract.json", contract),
        _file("run-metadata.json", metadata),
        _file("agent-fabric-capture-manifest.json", manifest_text),
    ]


def _fixture() -> dict:
    invocation = {
        "packet_version": "1.0",
        "target_harness": "shell",
        "profile": "self-test-profile",
        "role": "runner",
        "toolbelt": {
            "allowed_tools": ["cat", "python3"],
            "allowed_mcp": [],
            "forbidden_tools": ["write"],
            "context_policy": "local-code-only",
            "output_schema": "runner-result-v1",
            "evidence_obligations": ["command_receipt"],
        },
        "instructions": "Run local checks and report outputs.",
        "evidence_obligations": ["command_receipt"],
        "context_policy": "local-code-only",
    }
    result = {
        "result_version": "1.0",
        "agent_role": "runner",
        "profile": "self-test-profile",
        "status": "success",
        "output_files": ["out/agent/result.txt"],
        "self_reported_claims": ["checks completed"],
        "command_receipts": [],
    }
    return build_reference_adapter_fixture(invocation, self_report=result)


def _a1_manifest() -> dict:
    return build_capture_manifest(
        _fixture(),
        observer_capture={
            "observed_by": "depone-observer",
            "source_fixture_hash": "",
            "diff_summary": {"changed_files": ["depone/example.py"]},
            "touched_files": ["depone/example.py"],
            "test_output": {"status": "passed", "summary": "1 passed"},
            "command_receipts": [{"command": ["python3", "test.py"], "exit_code": 0}],
        },
        allowed_touched_files=["depone/example.py"],
    )


def _trusted_raw(manifest: dict) -> dict:
    key = b"trusted-observer-key"
    seal = seal_capture(
        manifest["observer_capture"],
        key,
        key_id="trusted-observer-key-1",
    )
    return {
        "metadata": {"run_id": "assurance-test-run"},
        "trusted_observer_provenance": [
            build_trusted_observer_provenance(
                manifest,
                evidence_path="agent-fabric-capture-manifest.json",
                seal=seal,
                key=key,
            )
        ],
        "trusted_observer_seal_key": key,
    }


def _trusted_provenance_file(root: Path, manifest: dict) -> Path:
    path = root / "trusted-observer-provenance.json"
    record = _trusted_raw(manifest)["trusted_observer_provenance"][0]
    path.write_text(json.dumps([record], sort_keys=True), encoding="utf-8")
    return path


def _signed_trusted_provenance_file(
    root: Path,
    manifest: dict,
    *,
    private_key_path: Path,
    public_key_path: Path,
) -> Path:
    path = root / "trusted-observer-provenance.dsse.json"
    record = _signed_trusted_raw(
        manifest,
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )["trusted_observer_provenance"][0]
    path.write_text(json.dumps([record], sort_keys=True), encoding="utf-8")
    return path


def _signed_binding(manifest: dict) -> dict:
    return {
        "kind": "trusted-observer-provenance-binding",
        "schema_version": "1.0",
        "evidence_path": "agent-fabric-capture-manifest.json",
        "manifest_hash": canonical_hash(manifest),
        "observer_capture_hash": manifest.get("observer_capture_hash"),
    }


def _unsigned_dsse_envelope(binding: dict) -> dict:
    payload = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "payloadType": "application/vnd.depone.trusted-observer-provenance.v1+json",
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [],
    }


def _signed_trusted_raw(
    manifest: dict,
    *,
    private_key_path: Path,
    public_key_path: Path,
) -> dict:
    binding = _signed_binding(manifest)
    envelope = sign_dsse_envelope(
        _unsigned_dsse_envelope(binding),
        str(private_key_path),
        key_id="operator-test-key",
    )
    return {
        "metadata": {"run_id": "assurance-test-run"},
        "trusted_observer_provenance": [
            {
                "kind": "trusted-observer-provenance",
                "schema_version": "1.0",
                "evidence_path": binding["evidence_path"],
                "manifest_hash": binding["manifest_hash"],
                "observer_capture_hash": binding["observer_capture_hash"],
                "scheme": "DSSE-Ed25519-openssl-cli",
                "key_id": "operator-test-key",
                "dsse_envelope": envelope,
            }
        ],
        "trusted_observer_public_key_file": str(public_key_path),
    }


def _fake_signed_trusted_raw(manifest: dict, public_key_path: Path) -> dict:
    binding = _signed_binding(manifest)
    return {
        "metadata": {"run_id": "assurance-test-run"},
        "trusted_observer_provenance": [
            {
                "kind": "trusted-observer-provenance",
                "schema_version": "1.0",
                "evidence_path": binding["evidence_path"],
                "manifest_hash": binding["manifest_hash"],
                "observer_capture_hash": binding["observer_capture_hash"],
                "scheme": "DSSE-Ed25519-openssl-cli",
                "key_id": "operator-test-key",
                "dsse_envelope": _unsigned_dsse_envelope(binding),
            }
        ],
        "trusted_observer_public_key_file": str(public_key_path),
    }


def _forged_isolated_manifest() -> dict:
    """A hand-forged capture claiming isolated-observed (A2) assurance backed by
    root-uid isolation facts. Root can override directory permission bits, so the
    boundary is not real; the manifest must fail closed when re-verified."""
    manifest = build_capture_manifest(
        _fixture(),
        observer_capture={
            "observed_by": "depone-observer",
            "source_fixture_hash": "",
            "diff_summary": {"changed_files": ["depone/example.py"]},
            "touched_files": ["depone/example.py"],
            "test_output": {"status": "passed", "summary": "1 passed"},
            "command_receipts": [{"command": ["python3", "test.py"], "exit_code": 0}],
        },
        allowed_touched_files=["depone/example.py"],
        isolation={
            "runner_uid": 1001,
            "observer_uid": 1002,
            "observer_dir_writable_by_runner": False,
        },
    )
    # Forge the recorded boundary onto a root runner and re-seal its hash, so the
    # only remaining defense is re-verifying the facts.
    manifest["isolation"]["runner_uid"] = 0
    manifest["isolation_hash"] = hashlib.sha256(
        json.dumps(manifest["isolation"], sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return manifest


class VerificationReportAssuranceTests(unittest.TestCase):
    def test_valid_a1_capture_surfaces_pass_decision_and_a1_assurance(self) -> None:
        manifest = _a1_manifest()
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw=_trusted_raw(manifest),
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.assurance, "A1-local-observed")
        self.assertEqual(report.agent_fabric_captures[0].valid, True)

    def test_signed_ed25519_provenance_surfaces_a1_assurance(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            manifest = _a1_manifest()
            evidence = EvidenceContext(
                run_id="assurance-test-run",
                files=_base_evidence_files(manifest),
                raw=_signed_trusted_raw(
                    manifest,
                    private_key_path=private_key,
                    public_key_path=public_key,
                ),
            )

            report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.assurance, "A1-local-observed")
        self.assertTrue(report.agent_fabric_captures[0].trusted_observer_provenance)

    def test_public_key_only_dsse_provenance_cannot_raise_assurance(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            _private_key, public_key = _generate_ed25519_keypair(temp_dir)
            manifest = _a1_manifest()
            evidence = EvidenceContext(
                run_id="assurance-test-run",
                files=_base_evidence_files(manifest),
                raw=_fake_signed_trusted_raw(manifest, public_key),
            )

            report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertIn(
            "trusted observer provenance signature verification failed",
            report.agent_fabric_captures[0].errors,
        )

    def test_signed_dsse_provenance_for_different_manifest_fails_closed(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            honest_manifest = _a1_manifest()
            raw = _signed_trusted_raw(
                honest_manifest,
                private_key_path=private_key,
                public_key_path=public_key,
            )
            forged_manifest = _a1_manifest()
            forged_manifest["observer_capture"]["test_output"]["summary"] = "forged"
            forged_manifest["observer_capture_hash"] = canonical_hash(
                forged_manifest["observer_capture"]
            )
            evidence = EvidenceContext(
                run_id="assurance-test-run",
                files=_base_evidence_files(forged_manifest),
                raw=raw,
            )

            report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertIn(
            "trusted observer provenance manifest_hash mismatch",
            report.agent_fabric_captures[0].errors,
        )

    def test_openssl_unavailable_dsse_provenance_fails_closed(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            manifest = _a1_manifest()
            evidence = EvidenceContext(
                run_id="assurance-test-run",
                files=_base_evidence_files(manifest),
                raw=_signed_trusted_raw(
                    manifest,
                    private_key_path=private_key,
                    public_key_path=public_key,
                ),
            )

            with patch("depone.agent_fabric.sign.openssl_path", return_value=None):
                report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertIn(
            "ERR_OPENSSL_UNAVAILABLE",
            report.agent_fabric_captures[0].errors,
        )

    def test_byte_copied_a1_capture_without_trusted_provenance_fails_closed(
        self,
    ) -> None:
        manifest = _a1_manifest()
        original = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw=_trusted_raw(manifest),
        )
        copied = EvidenceContext(
            run_id="assurance-test-run",
            files=list(original.files),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), copied)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertFalse(report.agent_fabric_captures[0].valid)
        self.assertIn(
            "trusted observer provenance missing",
            report.agent_fabric_captures[0].errors,
        )

    def test_fabricated_non_root_a1_capture_without_trusted_provenance_fails_closed(
        self,
    ) -> None:
        manifest = _a1_manifest()
        manifest["observer_capture"]["test_output"]["summary"] = "forged pass"
        manifest["observer_capture_hash"] = canonical_hash(manifest["observer_capture"])
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertFalse(report.agent_fabric_captures[0].valid)
        self.assertIn(
            "trusted observer provenance missing",
            report.agent_fabric_captures[0].errors,
        )

    def test_fabricated_non_root_a2_capture_without_trusted_provenance_fails_closed(
        self,
    ) -> None:
        manifest = build_capture_manifest(
            _fixture(),
            observer_capture={
                "observed_by": "depone-observer",
                "source_fixture_hash": "",
                "diff_summary": {"changed_files": ["depone/example.py"]},
                "touched_files": ["depone/example.py"],
                "test_output": {"status": "passed", "summary": "fabricated pass"},
                "command_receipts": [
                    {"command": ["python3", "fabricated.py"], "exit_code": 0}
                ],
            },
            allowed_touched_files=["depone/example.py"],
            isolation={
                "runner_uid": 1001,
                "observer_uid": 1002,
                "observer_dir_writable_by_runner": False,
            },
        )
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A0-claims-only")
        self.assertFalse(report.agent_fabric_captures[0].valid)
        self.assertEqual(report.agent_fabric_captures[0].assurance, "A2-isolated-observed")
        self.assertIn(
            "trusted observer provenance missing",
            report.agent_fabric_captures[0].errors,
        )

    def test_forged_isolated_capture_in_evidence_dir_refutes_report(self) -> None:
        # Forged evidence-dir PoC: a capture manifest hand-forged to claim
        # isolated-observed assurance via root-uid facts, plus a permissive
        # (satisfiable) evidence-contract. The forged boundary must fail closed
        # so the report refutes rather than granting an observed decision.
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(_forged_isolated_manifest()),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.agent_fabric_captures[0].valid, False)
        self.assertTrue(
            any(
                "does not establish a privilege boundary" in error
                for error in report.agent_fabric_captures[0].errors
            ),
            report.agent_fabric_captures[0].errors,
        )

    def test_self_report_only_capture_stays_a0(self) -> None:
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(build_capture_manifest(_fixture())),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.assurance, "A0-claims-only")

    def test_imported_byte_copy_capture_does_not_raise_report_assurance(
        self,
    ) -> None:
        manifest = json.loads(
            Path(
                "depone/fixtures/agent_fabric/capture_manifest_shell.json"
            ).read_text(encoding="utf-8")
        )
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.agent_fabric_captures[0].valid, False)
        self.assertIn(
            "trusted observer provenance missing",
            report.agent_fabric_captures[0].errors,
        )
        self.assertEqual(report.agent_fabric_captures[0].assurance, "A1-local-observed")
        self.assertEqual(report.assurance, "A0-claims-only")

    def test_fabricated_capture_with_recomputed_hashes_does_not_raise_report_assurance(
        self,
    ) -> None:
        manifest = _a1_manifest()
        manifest["observer_capture"]["command_receipts"] = [
            {"command": ["python3", "fabricated.py"], "exit_code": 0}
        ]
        manifest["observer_capture"]["test_output"] = {
            "status": "passed",
            "summary": "fabricated success",
        }
        manifest["observer_capture_hash"] = hashlib.sha256(
            json.dumps(
                manifest["observer_capture"],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.agent_fabric_captures[0].valid, False)
        self.assertIn(
            "trusted observer provenance missing",
            report.agent_fabric_captures[0].errors,
        )
        self.assertEqual(report.agent_fabric_captures[0].assurance, "A1-local-observed")
        self.assertEqual(report.assurance, "A0-claims-only")

    def test_a1_capture_cannot_bypass_missing_evidence_contract(self) -> None:
        manifest = _a1_manifest()
        files = [
            evidence_file
            for evidence_file in _base_evidence_files(manifest)
            if evidence_file.path != "evidence-contract.json"
        ]
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=files,
            raw=_trusted_raw(manifest),
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A1-local-observed")
        self.assertTrue(
            any(
                entry.code == "ERR_EVIDENCE_CONTRACT_MISSING"
                for entry in report.evidence_contract
            ),
            report.evidence_contract,
        )

    def test_a1_capture_cannot_bypass_invalid_evidence_contract(self) -> None:
        manifest = _a1_manifest()
        files = _base_evidence_files(manifest)
        files = [
            _file("evidence-contract.json", "{}")
            if evidence_file.path == "evidence-contract.json"
            else evidence_file
            for evidence_file in files
        ]
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=files,
            raw=_trusted_raw(manifest),
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.assurance, "A1-local-observed")
        self.assertTrue(
            any(
                entry.code == "ERR_EVIDENCE_CONTRACT_INVALID"
                for entry in report.evidence_contract
            ),
            report.evidence_contract,
        )

    def test_invalid_capture_manifest_refutes_report_without_hiding_errors(
        self,
    ) -> None:
        manifest = _a1_manifest()
        manifest["observer_capture"]["test_output"]["summary"] = "tampered"
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.agent_fabric_captures[0].valid, False)
        self.assertTrue(report.agent_fabric_captures[0].errors)

    def test_operator_view_renders_v110_report_fields(self) -> None:
        manifest = _a1_manifest()
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw=_trusted_raw(manifest),
        )

        view = render_operator_view(run_verification(_plan(), evidence))

        self.assertIn("- Decision: pass", view)
        self.assertIn("- Assurance: A1-local-observed", view)
        self.assertIn("- Agent Fabric captures: 1", view)
        self.assertIn("`agent-fabric-capture-manifest.json`", view)
        self.assertIn("   - Valid: yes", view)

    def test_operator_view_renders_empty_capture_list(self) -> None:
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files({}),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        view = render_operator_view(run_verification(_plan(), evidence))

        self.assertIn("- Decision: pass", view)
        self.assertIn("- Assurance: A0-claims-only", view)
        self.assertIn("- Agent Fabric captures: 0", view)
        self.assertIn("- None", view)

    def test_operator_view_renders_invalid_capture_errors(self) -> None:
        manifest = _a1_manifest()
        manifest["observer_capture"]["test_output"]["summary"] = "tampered"
        evidence = EvidenceContext(
            run_id="assurance-test-run",
            files=_base_evidence_files(manifest),
            raw={"metadata": {"run_id": "assurance-test-run"}},
        )

        view = render_operator_view(run_verification(_plan(), evidence))

        self.assertIn("- Decision: fail", view)
        self.assertIn("   - Valid: no", view)
        self.assertIn("   - Errors:", view)
        self.assertIn("observer_capture_hash mismatch", view)

    def test_verify_cli_writes_operator_view_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            evidence_dir = root / "evidence"
            report_path = root / "verification-report.json"
            view_path = root / "operator-view.md"
            evidence_dir.mkdir()
            plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
            manifest = _a1_manifest()
            provenance_path = _trusted_provenance_file(root, manifest)
            for evidence_file in _base_evidence_files(manifest):
                target = evidence_dir / evidence_file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(evidence_file.content, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DEPONE_TRUSTED_OBSERVER_PROVENANCE_FILE": str(
                        provenance_path
                    ),
                    "DEPONE_TRUSTED_OBSERVER_SEAL_KEY": "trusted-observer-key",
                },
            ):
                run_verify(
                    argparse.Namespace(
                        self_test=False,
                        plan=str(plan_path),
                        evidence=str(evidence_dir),
                        adapter="generic",
                        out=str(report_path),
                        operator_view_out=str(view_path),
                    )
                )

            self.assertTrue(report_path.is_file())
            view = view_path.read_text(encoding="utf-8")
            self.assertIn("# Verification Operator View", view)
            self.assertIn("- Decision: pass", view)
            self.assertIn("- Assurance: A1-local-observed", view)

    def test_verify_cli_loads_signed_provenance_and_public_key_outside_evidence_dir(
        self,
    ) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            evidence_dir = root / "evidence"
            report_path = root / "verification-report.json"
            view_path = root / "operator-view.md"
            key_dir = root / "operator-keys"
            evidence_dir.mkdir()
            key_dir.mkdir()
            private_key, public_key = _generate_ed25519_keypair(key_dir)
            plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
            manifest = _a1_manifest()
            provenance_path = _signed_trusted_provenance_file(
                root,
                manifest,
                private_key_path=private_key,
                public_key_path=public_key,
            )
            for evidence_file in _base_evidence_files(manifest):
                target = evidence_dir / evidence_file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(evidence_file.content, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DEPONE_TRUSTED_OBSERVER_PROVENANCE_FILE": str(
                        provenance_path
                    ),
                    "DEPONE_TRUSTED_OBSERVER_PUBLIC_KEY_FILE": str(public_key),
                },
            ):
                run_verify(
                    argparse.Namespace(
                        self_test=False,
                        plan=str(plan_path),
                        evidence=str(evidence_dir),
                        adapter="generic",
                        out=str(report_path),
                        operator_view_out=str(view_path),
                    )
                )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["decision"], "pass")
            self.assertEqual(report["assurance"], "A1-local-observed")
            view = view_path.read_text(encoding="utf-8")
            self.assertIn("- Assurance: A1-local-observed", view)

    def test_verify_cli_ignores_public_key_file_inside_evidence_dir(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            evidence_dir = root / "evidence"
            report_path = root / "verification-report.json"
            view_path = root / "operator-view.md"
            key_dir = root / "operator-keys"
            evidence_dir.mkdir()
            key_dir.mkdir()
            private_key, public_key = _generate_ed25519_keypair(key_dir)
            inside_public_key = evidence_dir / "operator.pub"
            inside_public_key.write_text(public_key.read_text(encoding="utf-8"))
            plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
            manifest = _a1_manifest()
            provenance_path = _signed_trusted_provenance_file(
                root,
                manifest,
                private_key_path=private_key,
                public_key_path=public_key,
            )
            for evidence_file in _base_evidence_files(manifest):
                target = evidence_dir / evidence_file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(evidence_file.content, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DEPONE_TRUSTED_OBSERVER_PROVENANCE_FILE": str(
                        provenance_path
                    ),
                    "DEPONE_TRUSTED_OBSERVER_PUBLIC_KEY_FILE": str(inside_public_key),
                },
            ):
                with self.assertRaises(SystemExit) as caught:
                    run_verify(
                        argparse.Namespace(
                            self_test=False,
                            plan=str(plan_path),
                            evidence=str(evidence_dir),
                            adapter="generic",
                            out=str(report_path),
                            operator_view_out=str(view_path),
                        )
                    )

            self.assertEqual(caught.exception.code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["decision"], "fail")
            self.assertEqual(report["assurance"], "A0-claims-only")
            errors = report["agent_fabric_captures"][0]["errors"]
            self.assertIn("trusted observer provenance public key missing", errors)

    def test_verify_cli_ignores_provenance_file_inside_evidence_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            evidence_dir = root / "evidence"
            report_path = root / "verification-report.json"
            view_path = root / "operator-view.md"
            evidence_dir.mkdir()
            plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
            manifest = _a1_manifest()
            provenance_path = evidence_dir / "trusted-observer-provenance.json"
            record = _trusted_raw(manifest)["trusted_observer_provenance"][0]
            provenance_path.write_text(json.dumps([record]), encoding="utf-8")
            for evidence_file in _base_evidence_files(manifest):
                target = evidence_dir / evidence_file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(evidence_file.content, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DEPONE_TRUSTED_OBSERVER_PROVENANCE_FILE": str(
                        provenance_path
                    ),
                    "DEPONE_TRUSTED_OBSERVER_SEAL_KEY": "trusted-observer-key",
                },
            ):
                with self.assertRaises(SystemExit) as caught:
                    run_verify(
                        argparse.Namespace(
                            self_test=False,
                            plan=str(plan_path),
                            evidence=str(evidence_dir),
                            adapter="generic",
                            out=str(report_path),
                            operator_view_out=str(view_path),
                        )
                    )

            self.assertEqual(caught.exception.code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["decision"], "fail")
            self.assertEqual(report["assurance"], "A0-claims-only")


if __name__ == "__main__":
    unittest.main()
