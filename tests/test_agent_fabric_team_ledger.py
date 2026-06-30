from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_ledger import validate_team_ledger


class AgentFabricTeamLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.evidence_dir = self.root / "lane-evidence"
        self.evidence_dir.mkdir()

    def _ledger(self) -> dict[str, object]:
        return {
            "kind": "depone-team-ledger",
            "schema_version": "1.0",
            "objective": "complete a reviewable team slice",
            "leader": "leader-fixed",
            "lanes": [
                {
                    "lane_id": "docs-lane",
                    "environment_kind": "local",
                    "adapter_kind": "omx",
                    "start_commit": "1" * 40,
                    "end_commit": "2" * 40,
                    "evidence_dir": "lane-evidence",
                    "verification_state": "pass",
                    "pr_url": "https://example.invalid/pull/1",
                }
            ],
        }

    def test_valid_ledger_passes(self) -> None:
        verdict = validate_team_ledger(self._ledger(), base_dir=self.root)

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["passed_lane_count"], 1)
        self.assertEqual(verdict["errors"], [])

    def test_pass_lane_blocks_when_evidence_dir_is_missing(self) -> None:
        ledger = self._ledger()
        ledger["lanes"][0]["evidence_dir"] = "missing-evidence"  # type: ignore[index]

        verdict = validate_team_ledger(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertTrue(
            any("evidence_dir must exist" in error for error in verdict["errors"])
        )

    def test_invalid_environment_and_adapter_block(self) -> None:
        ledger = self._ledger()
        lane = ledger["lanes"][0]  # type: ignore[index]
        lane["environment_kind"] = "bare-metal"
        lane["adapter_kind"] = "unknown-agent"

        verdict = validate_team_ledger(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertTrue(
            any("environment_kind" in error for error in verdict["errors"])
        )
        self.assertTrue(any("adapter_kind" in error for error in verdict["errors"]))

    def test_blocked_lane_requires_explicit_reason(self) -> None:
        ledger = self._ledger()
        lane = ledger["lanes"][0]  # type: ignore[index]
        lane["verification_state"] = "blocked"
        lane.pop("evidence_dir")

        missing_reason = validate_team_ledger(ledger, base_dir=self.root)
        self.assertEqual(missing_reason["decision"], "blocked")
        self.assertTrue(
            any("blocked_reason is required" in error for error in missing_reason["errors"])
        )

        lane["blocked_reason"] = "lane hit a merge conflict before fan-in"
        with_reason = validate_team_ledger(ledger, base_dir=self.root)
        self.assertEqual(with_reason["decision"], "blocked")
        self.assertFalse(
            any("blocked_reason is required" in error for error in with_reason["errors"])
        )

    def test_cli_self_test_and_validate(self) -> None:
        ledger_path = self.root / "team-ledger.json"
        verdict_path = self.root / "team-ledger-verdict.json"
        ledger_path.write_text(json.dumps(self._ledger()), encoding="utf-8")

        self_test = subprocess.run(
            [sys.executable, "-m", "depone", "team-ledger", "--self-test"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(self_test.returncode, 0, self_test.stderr)
        self.assertIn("pass", self_test.stdout)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-ledger",
                "--ledger",
                str(ledger_path),
                "--out",
                str(verdict_path),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "pass")
        self.assertEqual(json.loads(verdict_path.read_text(encoding="utf-8"))["decision"], "pass")


if __name__ == "__main__":
    unittest.main()
