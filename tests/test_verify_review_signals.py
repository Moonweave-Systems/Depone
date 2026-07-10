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


class ReviewSignalTests(unittest.TestCase):
    def test_review_receipt_is_advisory_and_does_not_change_evidence_verdict(self) -> None:
        review_receipt = json.dumps(
            {
                "kind": "moonweave-review-receipt",
                "schema_version": "1.0",
                "provider": "google-gemini",
                "axis": "review",
                "can_change_evidence_verdict": False,
                "findings": [
                    {
                        "severity": "high",
                        "file": "pkg/a.py",
                        "line": 3,
                        "summary": "possible regression",
                    }
                ],
                "raw_output_sha256": "a" * 64,
            },
            sort_keys=True,
        )
        evidence = EvidenceContext(
            run_id="review-test",
            files=[
                _file(
                    "evidence-contract.json",
                    json.dumps(
                        {
                            "schema_version": "v105.verify_wedge",
                            "required_evidence": ["run-metadata.json"],
                        },
                        sort_keys=True,
                    ),
                ),
                _file("run-metadata.json", json.dumps({"run_id": "review-test"})),
                _file("review-receipt.json", review_receipt),
            ],
            raw={"metadata": {"run_id": "review-test"}},
        )
        plan = {
            "schema_version": "0.5",
            "plan_id": "review-signal-test",
            "created_by": "depone",
            "source_prompt": "test",
            "activation": {"decision": "activate", "matched_thresholds": []},
            "phases": [{"id": "phase-1", "title": "Phase 1"}],
            "handoffs": [],
            "risk_gates": [],
            "verification": [],
            "budget": {},
        }

        report = run_verification(plan, evidence)

        self.assertEqual(report.verdict, "verified")
        self.assertEqual(report.decision, "pass")
        self.assertEqual(len(report.review_signals), 1)
        self.assertEqual(report.review_signals[0].provider, "google-gemini")
        self.assertEqual(report.review_signals[0].can_change_evidence_verdict, False)
        self.assertEqual(report.review_signals[0].finding_count, 1)


if __name__ == "__main__":
    unittest.main()
