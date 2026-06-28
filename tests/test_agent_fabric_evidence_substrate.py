from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    decode_dsse_payload,
    evaluate_external_statement_subjects,
    validate_statement_for_capture,
)


class AgentFabricEvidenceSubstrateTests(unittest.TestCase):
    def _capture(self) -> dict[str, object]:
        return json.loads(
            Path(
                "depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
            ).read_text(encoding="utf-8")
        )

    def test_bundle_round_trips_unsigned_statement_and_spans(self) -> None:
        capture = self._capture()
        bundle = build_evidence_bundle(capture)

        self.assertEqual(bundle["signing_status"], "unsigned-content-addressed")
        self.assertEqual(bundle["dsse_envelope"]["signatures"], [])
        self.assertEqual(decode_dsse_payload(bundle["dsse_envelope"]), bundle["statement"])
        self.assertEqual(validate_statement_for_capture(bundle["statement"], capture), [])

        operations = {
            span["attributes"]["gen_ai.operation.name"]
            for span in bundle["otel_spans"]
        }
        self.assertIn("invoke_agent", operations)
        self.assertIn("execute_tool", operations)
        usage_keys = [
            key
            for span in bundle["otel_spans"]
            for key in span["attributes"]
            if key.startswith("gen_ai.usage.")
        ]
        self.assertEqual(usage_keys, [])

    def test_tampered_statement_and_external_mismatch_do_not_pass(self) -> None:
        capture = self._capture()
        statement = build_evidence_bundle(capture)["statement"]
        tampered = deepcopy(statement)
        tampered["subject"][0]["digest"]["sha256"] = "0" * 64

        self.assertTrue(validate_statement_for_capture(tampered, capture))
        external = evaluate_external_statement_subjects(
            tampered,
            {"depone-capture-manifest": canonical_hash(capture)},
        )
        self.assertEqual(external["decision"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
