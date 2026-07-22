from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import asdict
from pathlib import Path

from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify.adapters.generic import read_evidence
from depone.verify.engine import _health_conformance, run_verification
from depone.verify.evidence_contract import validate_evidence_contract


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(path: str, value: object) -> EvidenceFile:
    content = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    return EvidenceFile(path=path, content=content, sha256=_sha(content))


def _gate(
    gate: str,
    tool: str,
    enforcement: str,
    *,
    expected_exit_code: object = 0,
) -> dict[str, object]:
    return {
        "gate": gate,
        "tool": tool,
        "enforcement": enforcement,
        "expected_exit_code": expected_exit_code,
        "exit_code_path": f"health/{gate}.exit",
        "log_path": f"health/{gate}.log",
    }


def _evidence(
    gates: object,
    exit_codes: dict[str, int] | None = None,
    *,
    schema_version: str = "v111.code_health",
) -> EvidenceContext:
    contract = {
        "schema_version": schema_version,
        "code_health": {"gates": gates},
    }
    files = [_file("evidence-contract.json", contract)]
    if isinstance(gates, list):
        for gate in gates:
            if not isinstance(gate, dict):
                continue
            exit_code_path = gate.get("exit_code_path")
            log_path = gate.get("log_path")
            gate_id = gate.get("gate")
            if isinstance(exit_code_path, str) and isinstance(gate_id, str):
                actual = (exit_codes or {}).get(gate_id, 0)
                files.append(_file(exit_code_path, f"{actual}\n"))
            if isinstance(log_path, str):
                files.append(_file(log_path, "recorded gate output\n"))
    return EvidenceContext(run_id="code-health-test", files=files, raw={})


def _plan() -> dict[str, object]:
    return {
        "schema_version": "0.5",
        "plan_id": "code-health-plan",
        "phases": [{"id": "phase-1"}],
    }


class CodeHealthContractTests(unittest.TestCase):
    def test_block_gate_passes_when_recorded_exit_code_matches(self) -> None:
        errors = validate_evidence_contract(
            _evidence([_gate("format", "black", "block")])
        )

        self.assertEqual(errors, [])

    def test_advisory_gate_failure_records_health_violation_details(self) -> None:
        errors = validate_evidence_contract(
            _evidence(
                [_gate("complexity", "ruff-c901", "advisory")],
                {"complexity": 1},
            )
        )

        self.assertEqual([entry.code for entry in errors], ["ERR_HEALTH_GATE_VIOLATION"])
        self.assertEqual(errors[0].evidence_path, "health/complexity.exit")
        self.assertIn("gate='complexity'", errors[0].message)
        self.assertIn("tool='ruff-c901'", errors[0].message)
        self.assertIn("enforcement='advisory'", errors[0].message)

    def test_block_gate_failure_records_health_violation(self) -> None:
        errors = validate_evidence_contract(
            _evidence(
                [_gate("architecture", "import-linter", "block")],
                {"architecture": 2},
            )
        )

        self.assertEqual([entry.code for entry in errors], ["ERR_HEALTH_GATE_VIOLATION"])
        self.assertEqual(errors[0].evidence_path, "health/architecture.exit")

    def test_malformed_code_health_directive_is_refused(self) -> None:
        cases = {
            "missing gates": ({}, "code_health.gates must be a non-empty list"),
            "invalid gates": ("not-a-list", "code_health.gates must be a non-empty list"),
            "invalid gate entry": (["not-an-object"], "code_health.gates[0] must be an object"),
            "bad enforcement": (
                [_gate("lint", "ruff", "warn")],
                "code_health.gates[0].enforcement must be 'block' or 'advisory'",
            ),
            "non-int exit": (
                [_gate("lint", "ruff", "block", expected_exit_code="0")],
                "code_health.gates[0].expected_exit_code must be an integer",
            ),
            "bool exit": (
                [_gate("lint", "ruff", "block", expected_exit_code=True)],
                "code_health.gates[0].expected_exit_code must be an integer",
            ),
        }
        for name, (gates, expected_message) in cases.items():
            with self.subTest(name=name):
                if gates == {}:
                    evidence = _evidence([])
                    contract = json.loads(evidence.files[0].content)
                    contract["code_health"] = {}
                    evidence.files[0] = _file("evidence-contract.json", contract)
                else:
                    evidence = _evidence(gates)
                errors = validate_evidence_contract(evidence)

                self.assertEqual(
                    [entry.code for entry in errors],
                    ["ERR_EVIDENCE_CONTRACT_INVALID"],
                )
                self.assertIn(expected_message, errors[0].message)

    def test_code_health_requires_v111_schema(self) -> None:
        errors = validate_evidence_contract(
            _evidence(
                [_gate("format", "black", "block")],
                schema_version="v110.role_capability_skill_routing",
            )
        )

        self.assertEqual(
            [entry.code for entry in errors],
            ["ERR_EVIDENCE_CONTRACT_INVALID"],
        )
        self.assertIn("code_health requires schema_version 'v111.code_health'", errors[0].message)

    def test_health_conformance_rolls_up_three_declared_gates(self) -> None:
        gates = [
            _gate("format", "black", "block"),
            _gate("complexity", "ruff-c901", "advisory"),
            _gate("architecture", "import-linter", "block"),
        ]
        evidence = _evidence(gates, {"format": 0, "complexity": 1, "architecture": 2})
        contract = json.loads(evidence.files[0].content)
        entries = validate_evidence_contract(evidence)

        conformance = _health_conformance(contract, entries)

        self.assertEqual(
            asdict(conformance),
            {
                "overall": "fail",
                "axes": [
                    {
                        "gate": "format",
                        "tool": "black",
                        "status": "pass",
                        "enforcement": "block",
                        "blocks_handoff": False,
                        "error_code": None,
                        "evidence_path": None,
                    },
                    {
                        "gate": "complexity",
                        "tool": "ruff-c901",
                        "status": "fail",
                        "enforcement": "advisory",
                        "blocks_handoff": False,
                        "error_code": "ERR_HEALTH_GATE_VIOLATION",
                        "evidence_path": "health/complexity.exit",
                    },
                    {
                        "gate": "architecture",
                        "tool": "import-linter",
                        "status": "fail",
                        "enforcement": "block",
                        "blocks_handoff": True,
                        "error_code": "ERR_HEALTH_GATE_VIOLATION",
                        "evidence_path": "health/architecture.exit",
                    },
                ],
            },
        )

    def test_advisory_health_failure_is_reported_without_blocking_decision(self) -> None:
        report = run_verification(
            _plan(),
            _evidence(
                [_gate("complexity", "ruff-c901", "advisory")],
                {"complexity": 1},
            ),
        )

        self.assertEqual(report.decision, "pass")
        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.health_conformance.overall, "fail")
        self.assertFalse(report.health_conformance.axes[0].blocks_handoff)

    def test_block_health_failure_refutes_decision(self) -> None:
        report = run_verification(
            _plan(),
            _evidence(
                [_gate("architecture", "import-linter", "block")],
                {"architecture": 1},
            ),
        )

        self.assertEqual(report.decision, "fail")
        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.health_conformance.overall, "fail")
        self.assertTrue(report.health_conformance.axes[0].blocks_handoff)

    def test_health_conformance_is_none_without_code_health_directive(self) -> None:
        evidence = _evidence([_gate("format", "black", "block")])
        contract = json.loads(evidence.files[0].content)
        contract.pop("code_health")

        self.assertIsNone(_health_conformance(contract, []))

    def test_committed_tiered_fixture_rederives_mixed_health_result(self) -> None:
        evidence = read_evidence(
            str(Path("depone/fixtures/code_health/tiered_mixed"))
        )

        report = run_verification(_plan(), evidence)

        self.assertEqual(report.decision, "fail")
        self.assertEqual(
            [entry.code for entry in report.evidence_contract],
            ["ERR_HEALTH_GATE_VIOLATION", "ERR_HEALTH_GATE_VIOLATION"],
        )
        self.assertEqual(
            [
                (axis.gate, axis.status, axis.enforcement, axis.blocks_handoff)
                for axis in report.health_conformance.axes
            ],
            [
                ("format", "pass", "block", False),
                ("complexity", "fail", "advisory", False),
                ("architecture", "fail", "block", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
