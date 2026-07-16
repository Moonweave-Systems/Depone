from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import wrap_statement_in_dsse
from depone.agent_fabric.paired_run import build_runner_receipt
from depone.agent_fabric.sign import _generate_ed25519_keypair, sign_dsse_envelope
from depone.verify import evidence_contract
from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify.adapters.generic import read_evidence
from depone.verify.engine import run_verification
from depone.verify.operator_view import render_operator_view


_ADVISORY_FIXTURE_ROOT = Path("depone/fixtures/advisory")


def _file(path: str, value: object) -> EvidenceFile:
    content = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    return EvidenceFile(
        path=path,
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _sketch() -> dict[str, Any]:
    return {
        "kind": "orro-sketch",
        "frame": "Choose a small verifier seam.",
        "criteria": ["sealed", "non-executing"],
        "candidates": [
            {"axis": "separate-validator", "summary": "Independent track"},
            {"axis": "execution-verdict", "summary": "Fold into proofcheck"},
        ],
        "chosen": {
            "direction": "separate-validator",
            "reason": "Preserves the honesty boundary.",
            "confidence": "high",
            "what_would_change_it": "A contract requirement to aggregate tracks.",
        },
        "rejected": [
            {"option": "execution-verdict", "why_lost": "Would conflate tracks."}
        ],
        "no_gos": ["claim correctness"],
        "rabbit_holes": [],
        "decision_record": "Select the separate advisory validator.",
    }


def _receipt(output: str) -> dict[str, Any]:
    return {
        "kind": "orro-trace-reproduction",
        "command": "python3 -m unittest tests.test_widget.WidgetTests.test_regression",
        "exit_status": 1,
        "output": output,
    }


def _execution_receipt(transcript: str) -> dict[str, Any]:
    command = "python3 -m unittest tests.test_widget.WidgetTests.test_regression"
    receipt = build_runner_receipt(
        runner_kind="manual",
        arm="governed",
        task_id="trace-red",
        worktree="/tmp/trace-red",
        invocation=command.split(),
        transcript_path="orro-trace-execution.log",
        exit_code=1,
        touched_files=[],
        started_at="2026-07-14T00:00:00Z",
        ended_at="2026-07-14T00:00:01Z",
    )
    receipt.update(
        {
            "command": command,
            "transcript": transcript,
            "transcript_sha256": hashlib.sha256(
                transcript.encode("utf-8")
            ).hexdigest(),
        }
    )
    receipt["source_hashes"] = {
        "receipt": canonical_hash(
            {key: value for key, value in receipt.items() if key != "source_hashes"}
        )
    }
    return receipt


def _trace(receipt: dict[str, Any], *, tier: str = "confirmed") -> dict[str, Any]:
    return {
        "kind": "orro-trace",
        "reproduction": {
            "red_observed": True,
            "non_reproducible_reason": "",
            "receipt_sha256": canonical_hash(receipt),
            "symptom": "Widget total was 7, expected 9",
        },
        "localization": "widget/totals.py:42",
        "hypotheses": [
            {
                "mechanism": "Discount is applied twice.",
                "prediction": "The total is lower by one discount.",
                "discriminating_probe": "discount application count=2",
                "confidence": "high",
            },
            {
                "mechanism": "Tax rounding changed.",
                "prediction": "Only fractional totals differ.",
                "discriminating_probe": "fractional-only mismatch",
                "confidence": "low",
            },
        ],
        "confirmation": {"rival_hypotheses_ruled_out": [1]},
        "logbook": ["Reproduced the symptom and inspected the discount count."],
        "root_cause": {
            "tier": tier,
            "hypothesis_index": 0,
            "summary": "Discount is applied twice.",
        },
        "fix_scope": {"cause_site": "widget/totals.py:42"},
    }


def _signed_evidence(
    decision: dict[str, Any],
    *,
    private_key: Path,
    public_key: Path,
    receipt: dict[str, Any] | None = None,
    signed_decision: dict[str, Any] | None = None,
    signed_receipt: dict[str, Any] | None = None,
    execution_receipt: dict[str, Any] | None = None,
    signed_execution_receipt: dict[str, Any] | None = None,
    schema_version: str = "v108.advisory_provenance",
) -> tuple[EvidenceContext, dict[str, Any]]:
    decision_path = f"{decision['kind']}.json"
    subjects = [
        {
            "name": decision_path,
            "digest": {
                "sha256": canonical_hash(signed_decision or decision),
            },
        }
    ]
    files = [_file(decision_path, decision)]
    if receipt is not None:
        subjects.append(
            {
                "name": "orro-trace-reproduction.json",
                "digest": {
                    "sha256": canonical_hash(signed_receipt or receipt),
                },
            }
        )
        files.append(_file("orro-trace-reproduction.json", receipt))
    if execution_receipt is not None:
        subjects.append(
            {
                "name": "orro-trace-execution.json",
                "digest": {
                    "sha256": canonical_hash(
                        signed_execution_receipt or execution_receipt
                    ),
                },
            }
        )
        files.append(_file("orro-trace-execution.json", execution_receipt))
    schema_number = schema_version.split(".", 1)[0]
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": (
            "https://depone.dev/attestations/advisory-provenance/"
            f"{schema_number}"
        ),
        "predicate": {"schema_version": schema_version},
    }
    envelope = sign_dsse_envelope(
        wrap_statement_in_dsse(statement),
        str(private_key),
        key_id="advisory-test-key",
    )
    files.append(_file("advisory-provenance-bundle.json", envelope))
    contract = {
        "schema_version": schema_version,
        "advisory_provenance": {
            "decision_path": decision_path,
            "bundle_path": "advisory-provenance-bundle.json",
        },
    }
    files.append(_file("evidence-contract.json", contract))
    return (
        EvidenceContext(
            run_id="advisory-test",
            files=files,
            raw={"trusted_observer_public_key_file": str(public_key)},
        ),
        contract,
    )


def _validate(
    evidence: EvidenceContext,
    contract: dict[str, Any],
) -> list[evidence_contract.EvidenceContractEntry]:
    validator = getattr(evidence_contract, "validate_advisory_provenance", None)
    if validator is None:
        raise AssertionError("validate_advisory_provenance is not implemented")
    return validator(evidence, contract)


def _plan() -> dict[str, Any]:
    return {
        "schema_version": "0.5",
        "plan_id": "advisory-provenance-pipeline-test",
        "created_by": "depone",
        "source_prompt": "test isolated advisory provenance",
        "activation": {"decision": "activate", "matched_thresholds": []},
        "phases": [{"id": "phase-1", "title": "Phase 1"}],
        "handoffs": [],
        "risk_gates": [],
        "verification": [],
        "budget": {},
    }


def _without_advisory_directive(evidence: EvidenceContext) -> EvidenceContext:
    baseline_contract = {
        "schema_version": "v105.verify_wedge",
        "required_evidence": ["orro-sketch.json"],
    }
    return EvidenceContext(
        run_id=evidence.run_id,
        files=[
            _file("evidence-contract.json", baseline_contract)
            if entry.path == "evidence-contract.json"
            else entry
            for entry in evidence.files
        ],
        raw=dict(evidence.raw),
    )


def _fixture_evidence(name: str) -> EvidenceContext:
    evidence = read_evidence(str(_ADVISORY_FIXTURE_ROOT / name))
    evidence.raw["trusted_observer_public_key_file"] = str(
        (_ADVISORY_FIXTURE_ROOT / "advisory-public-key.pem").resolve()
    )
    return evidence


class AdvisoryProvenanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.private_key, self.public_key = _generate_ed25519_keypair(
            Path(self.temp_dir.name)
        )

    def assert_error_code(
        self,
        errors: list[evidence_contract.EvidenceContractEntry],
        code: str,
    ) -> None:
        self.assertIn(code, [error.code for error in errors], errors)
        matching = next(error for error in errors if error.code == code)
        self.assertIn("not re-derivable from sealed bytes", matching.message)

    def test_sketch_passes_when_choice_and_rejections_are_consistent(self) -> None:
        evidence, contract = _signed_evidence(
            _sketch(), private_key=self.private_key, public_key=self.public_key
        )

        self.assertEqual(_validate(evidence, contract), [])

    def test_sketch_refutes_choice_outside_candidates(self) -> None:
        sketch = _sketch()
        sketch["chosen"]["direction"] = "invented-direction"
        evidence, contract = _signed_evidence(
            sketch, private_key=self.private_key, public_key=self.public_key
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES",
        )

    def test_sketch_refutes_choice_also_listed_as_rejected(self) -> None:
        sketch = _sketch()
        sketch["rejected"][0]["option"] = sketch["chosen"]["direction"]
        evidence, contract = _signed_evidence(
            sketch, private_key=self.private_key, public_key=self.public_key
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_SKETCH_CHOSEN_ALSO_REJECTED",
        )

    def test_sketch_refutes_rejection_without_reason(self) -> None:
        sketch = _sketch()
        sketch["rejected"][0]["why_lost"] = ""
        evidence, contract = _signed_evidence(
            sketch, private_key=self.private_key, public_key=self.public_key
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_SKETCH_REJECTED_REASON_MISSING",
        )

    def test_sketch_refutes_tampered_decision(self) -> None:
        signed_sketch = _sketch()
        tampered_sketch = json.loads(json.dumps(signed_sketch))
        tampered_sketch["decision_record"] = "Altered after sealing."
        evidence, contract = _signed_evidence(
            tampered_sketch,
            signed_decision=signed_sketch,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract), "ERR_ADVISORY_SKETCH_TAMPER"
        )

    def test_confirmed_trace_passes_when_receipt_backs_claim(self) -> None:
        receipt = _receipt(
            "Widget total was 7, expected 9\ndiscount application count=2\nFAILED"
        )
        trace = _trace(receipt)
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assertEqual(_validate(evidence, contract), [])

    def test_v110_confirmed_trace_passes_with_bound_executed_red(self) -> None:
        output = (
            "Widget total was 7, expected 9\n"
            "discount application count=2\nFAILED"
        )
        receipt = _receipt(output)
        execution_receipt = _execution_receipt(output)
        trace = _trace(receipt)
        trace["reproduction"]["execution_receipt_sha256"] = canonical_hash(
            execution_receipt
        )
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            execution_receipt=execution_receipt,
            schema_version="v110.advisory_provenance",
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assertEqual(_validate(evidence, contract), [])

    def test_v110_confirmed_trace_refutes_freetext_only_red(self) -> None:
        receipt = _receipt(
            "Widget total was 7, expected 9\n"
            "discount application count=2\nFAILED"
        )
        trace = _trace(receipt)
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            schema_version="v110.advisory_provenance",
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_TRACE_RED_NOT_EXECUTED",
        )

    def test_v110_confirmed_trace_refutes_execution_receipt_hash_mismatch(
        self,
    ) -> None:
        output = (
            "Widget total was 7, expected 9\n"
            "discount application count=2\nFAILED"
        )
        receipt = _receipt(output)
        execution_receipt = _execution_receipt(output)
        trace = _trace(receipt)
        trace["reproduction"]["execution_receipt_sha256"] = "f" * 64
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            execution_receipt=execution_receipt,
            schema_version="v110.advisory_provenance",
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_TRACE_RED_NOT_EXECUTED",
        )

    def test_confirmed_trace_refutes_missing_backing_receipt(self) -> None:
        receipt = _receipt("Widget total was 7, expected 9")
        trace = _trace(receipt)
        evidence, contract = _signed_evidence(
            trace, private_key=self.private_key, public_key=self.public_key
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_TRACE_CONFIRMED_UNBACKED",
        )

    def test_confirmed_trace_refutes_unrelated_red(self) -> None:
        receipt = _receipt("UnrelatedNetworkTests.test_timeout FAILED")
        trace = _trace(receipt)
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract), "ERR_ADVISORY_TRACE_UNRELATED_RED"
        )

    def test_confirmed_trace_refutes_when_no_rival_is_ruled_out(self) -> None:
        receipt = _receipt(
            "Widget total was 7, expected 9\ndiscount application count=2\nFAILED"
        )
        trace = _trace(receipt)
        trace["confirmation"]["rival_hypotheses_ruled_out"] = []
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_TRACE_RIVAL_NOT_RULED_OUT",
        )

    def test_suspected_trace_refutes_fabricated_receipt_reference(self) -> None:
        receipt = _receipt("Optional observation")
        trace = _trace(receipt, tier="suspected")
        trace["reproduction"]["receipt_sha256"] = "f" * 64
        evidence, contract = _signed_evidence(
            trace,
            receipt=receipt,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_TRACE_RECEIPT_HASH_MISMATCH",
        )

    def test_trace_refutes_tampered_receipt(self) -> None:
        signed_receipt = _receipt(
            "Widget total was 7, expected 9\ndiscount application count=2\nFAILED"
        )
        tampered_receipt = json.loads(json.dumps(signed_receipt))
        tampered_receipt["output"] = "Altered after sealing."
        trace = _trace(tampered_receipt)
        evidence, contract = _signed_evidence(
            trace,
            receipt=tampered_receipt,
            signed_receipt=signed_receipt,
            private_key=self.private_key,
            public_key=self.public_key,
        )

        self.assert_error_code(
            _validate(evidence, contract), "ERR_ADVISORY_TRACE_TAMPER"
        )

    def test_advisory_errors_do_not_enter_execution_evidence_verdict(self) -> None:
        sketch = _sketch()
        sketch["chosen"]["direction"] = "invented-direction"
        evidence, contract = _signed_evidence(
            sketch, private_key=self.private_key, public_key=self.public_key
        )

        self.assert_error_code(
            _validate(evidence, contract),
            "ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES",
        )
        self.assertEqual(evidence_contract.validate_evidence_contract(evidence), [])

    def test_pipeline_surfaces_invalid_advisory_without_changing_verdict(self) -> None:
        evidence = _fixture_evidence("sketch_fail_chosen_not_in_candidates")

        baseline = run_verification(_plan(), _without_advisory_directive(evidence))
        report = run_verification(_plan(), evidence)

        self.assertEqual(
            [finding.code for finding in report.advisory_findings],
            ["ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES"],
        )
        self.assertEqual(report.evidence_contract, [])
        self.assertEqual(
            (report.decision, report.verdict, report.assurance),
            (baseline.decision, baseline.verdict, baseline.assurance),
        )
        self.assertEqual(
            (report.decision, report.verdict, report.assurance),
            ("pass", "verified", "A0-claims-only"),
        )

    def test_pipeline_valid_advisory_has_no_findings(self) -> None:
        evidence = _fixture_evidence("sketch_pass")

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.advisory_findings, [])
        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.assurance, "A0-claims-only")

    def test_advisory_findings_are_machine_readable_and_operator_labeled(self) -> None:
        evidence = _fixture_evidence("sketch_fail_chosen_not_in_candidates")

        report = run_verification(_plan(), evidence)

        report_data = asdict(report)
        self.assertEqual(
            report_data["advisory_findings"][0]["code"],
            "ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES",
        )
        operator_view = render_operator_view(report)
        self.assertIn(
            "## Advisory findings — does not affect the verdict",
            operator_view,
        )
        self.assertIn("ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES", operator_view)


if __name__ == "__main__":
    unittest.main()
