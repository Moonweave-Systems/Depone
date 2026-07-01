"""Tests that unknown/orphan handoffs cannot vanish from the verdict."""

from __future__ import annotations

import hashlib
import json
import unittest

from depone.verify.adapters.base import EvidenceContext, EvidenceFile
from depone.verify.engine import run_verification


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(path: str, content: str) -> EvidenceFile:
    return EvidenceFile(path=path, content=content, sha256=_sha(content))


def _evidence(handoff_content: str) -> EvidenceContext:
    contract = json.dumps(
        {
            "schema_version": "v105.verify_wedge",
            "required_evidence": ["run-metadata.json"],
        },
        sort_keys=True,
    )
    metadata = json.dumps({"run_id": "handoff-test-run"}, sort_keys=True)
    return EvidenceContext(
        run_id="handoff-test-run",
        files=[
            _file("evidence-contract.json", contract),
            _file("run-metadata.json", metadata),
            _file("handoff.txt", handoff_content),
        ],
        raw={"metadata": {"run_id": "handoff-test-run"}},
    )


def _plan(to_phase: str, artifact_content: str) -> dict:
    return {
        "schema_version": "0.5",
        "plan_id": "handoff-soundness-test",
        "created_by": "depone",
        "source_prompt": "test",
        "activation": {"decision": "activate", "matched_thresholds": []},
        "phases": [{"id": "phase-1", "title": "Phase 1"}],
        "handoffs": [
            {
                "artifact": "handoff.txt",
                "from_phase": "phase-1",
                "to_phase": to_phase,
                "expected_hash": _sha(artifact_content),
            }
        ],
        "risk_gates": [],
        "verification": [],
        "budget": {},
    }


class HandoffSoundnessTests(unittest.TestCase):
    def test_handoff_to_unknown_phase_refutes_report(self) -> None:
        content = "handoff artifact\n"
        report = run_verification(_plan("phase-99", content), _evidence(content))

        self.assertEqual(report.verdict, "refuted")
        self.assertEqual(report.decision, "fail")

    def test_handoff_to_known_phase_still_verifies(self) -> None:
        content = "handoff artifact\n"
        report = run_verification(_plan("phase-1", content), _evidence(content))

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")


if __name__ == "__main__":
    unittest.main()
