from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from depone.agent_fabric.codex_local_capability import (
    CODEX_LOCAL_CAPABILITY_KIND,
    write_codex_local_capability,
)


class CodexLocalCapabilityShimTests(unittest.TestCase):
    def test_write_receipt_round_trips_json(self) -> None:
        receipt = {
            "kind": CODEX_LOCAL_CAPABILITY_KIND,
            "schema_version": "0.1",
            "decision": "blocked",
            "blocked_reasons": ["codex binary not found"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "capability.json"
            write_codex_local_capability(out, receipt)

            loaded = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(loaded["kind"], CODEX_LOCAL_CAPABILITY_KIND)
        self.assertEqual(loaded["decision"], "blocked")

    def test_deprecated_shim_delegates_to_witnessd_canonical_when_available(
        self,
    ) -> None:
        import depone.agent_fabric.codex_local_capability as capability

        fake_witnessd = types.ModuleType("witnessd")
        fake_canonical = types.ModuleType("witnessd.codex_capability")

        def fake_build(**kwargs: object) -> dict[str, object]:
            return {
                "kind": CODEX_LOCAL_CAPABILITY_KIND,
                "schema_version": "0.1",
                "decision": "blocked",
                "blocked_reasons": ["from witnessd canonical"],
                "readiness": {
                    "version_probe": {
                        "executed": False,
                        "timed_out": False,
                        "stdout_present": False,
                        "stderr_present": False,
                        "unexpected_output": False,
                        "argv": ["codex", "--version"],
                        "exit_code": None,
                        "sanitized_version_text": None,
                    }
                },
                "boundary": {
                    "launches_live_model": False,
                    "executes_coding_task": False,
                    "captures_capability_only": True,
                    "raises_assurance": False,
                },
                "agent_contract_hash": "same",
                "agent_contract": {"agent_contract_hash": "same"},
                "canonical_source": "witnessd.codex_capability",
            }

        fake_canonical.build_codex_local_capability = fake_build
        with patch.dict(
            sys.modules,
            {"witnessd": fake_witnessd, "witnessd.codex_capability": fake_canonical},
        ):
            receipt = capability.build_codex_local_capability(repo=Path("."))

        self.assertEqual(receipt["blocked_reasons"], ["from witnessd canonical"])
        self.assertEqual(receipt["canonical_source"], "witnessd.codex_capability")


if __name__ == "__main__":
    unittest.main()
