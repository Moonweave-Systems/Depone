from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main
from depone.agent_fabric.team_dry_run import build_team_dry_run
from depone.agent_fabric.team_ledger import build_team_ledger_verdict


class AgentFabricTeamDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _plan(self) -> dict[str, object]:
        return {
            "leader_objective": "Plan two local lanes without launching workers",
            "leader_id": "leader-fixed",
            "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "lanes": [
                {
                    "objective": "Update docs",
                    "runner_adapter_kind": "codex",
                    "team_adapter_kind": "depone-native",
                    "touched_files": ["docs/command-reference.md"],
                },
                {
                    "lane_id": "tests",
                    "objective": "Run focused tests",
                    "planned_worktree": "worktrees/tests",
                    "runner_adapter_kind": "codex",
                    "team_adapter_kind": "depone-native",
                },
            ],
        }

    def test_build_dry_run_allocates_blocked_team_ledger(self) -> None:
        dry_run = build_team_dry_run(self._plan(), out_dir=Path("out/team-dry-run"))

        ledger = dry_run["team_ledger"]
        self.assertEqual(dry_run["kind"], "depone-team-dry-run")
        self.assertEqual(dry_run["boundary"]["launches_agents"], False)
        self.assertEqual(ledger["leader_objective"], "Plan two local lanes without launching workers")
        self.assertEqual([lane["lane_id"] for lane in ledger["lanes"]], ["lane-1", "tests"])
        self.assertEqual(
            [lane["planned_worktree"] for lane in dry_run["lanes"]],
            ["out/team-dry-run/worktrees/lane-1", "worktrees/tests"],
        )
        self.assertEqual(
            [lane["evidence_dir"] for lane in ledger["lanes"]],
            ["lane-1", "tests"],
        )
        self.assertEqual(
            [lane["worktree_receipt"] for lane in ledger["lanes"]],
            ["lane-1/worktree-receipt.json", "tests/worktree-receipt.json"],
        )
        self.assertTrue(
            all(lane["verification_state"] == "blocked" for lane in ledger["lanes"])
        )

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root / "out" / "team-dry-run")

        self.assertEqual(verdict["decision"], "blocked-explicit")
        self.assertEqual(verdict["errors"], [])

    def test_build_dry_run_rejects_unsafe_lane_path(self) -> None:
        plan = self._plan()
        plan["lanes"][0]["planned_worktree"] = "../escape"

        with self.assertRaisesRegex(ValueError, "ERR_TEAM_DRY_RUN_PATH_INVALID"):
            build_team_dry_run(plan, out_dir=Path("out/team-dry-run"))

    def test_build_dry_run_requires_base_commit(self) -> None:
        plan = self._plan()
        plan["base_commit"] = "   "

        with self.assertRaisesRegex(ValueError, "ERR_TEAM_DRY_RUN_BASE_COMMIT_REQUIRED"):
            build_team_dry_run(plan, out_dir=Path("out/team-dry-run"))

    def test_build_dry_run_rejects_absolute_out_dir(self) -> None:
        with self.assertRaisesRegex(ValueError, "ERR_TEAM_DRY_RUN_PATH_INVALID"):
            build_team_dry_run(self._plan(), out_dir=Path("/tmp/team-dry-run"))

    def test_build_dry_run_quotes_next_commands(self) -> None:
        plan = self._plan()
        plan["lanes"][1]["lane_id"] = "docs copy"
        plan["lanes"][1]["planned_worktree"] = "worktrees/docs copy"

        dry_run = build_team_dry_run(plan, out_dir=Path("out/team-dry-run"))

        commands = dry_run["next_commands"][1]["commands"]
        self.assertIn("'worktrees/docs copy'", commands[0])
        self.assertIn("--worktree 'worktrees/docs copy'", commands[1])
        self.assertIn("--evidence-dir 'docs copy'", commands[1])
        self.assertIn("--out 'out/team-dry-run/docs copy/worktree-receipt.json'", commands[1])

    def test_cli_writes_dry_run_artifacts(self) -> None:
        plan_path = self.root / "team-plan.json"
        out_dir = Path("out") / f"team-dry-run-test-{Path(self.root).name}"
        self.addCleanup(lambda: shutil.rmtree(out_dir, ignore_errors=True))
        plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-dry-run",
                "--plan",
                str(plan_path),
                "--out-dir",
                str(out_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["command"], "team-dry-run")
        self.assertEqual(stdout["decision"], "blocked-explicit")
        self.assertEqual(stdout["lane_count"], 2)
        self.assertTrue((out_dir / "team-ledger.json").exists())
        self.assertTrue((out_dir / "team-dry-run.json").exists())
        self.assertTrue((out_dir / "next-commands.json").exists())

    def test_main_dispatches_team_dry_run_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "team-dry-run", "--self-test"]):
            with patch.object(depone_main.team_dry_run, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-dry-run")
        self.assertTrue(getattr(seen[0], "self_test"))


if __name__ == "__main__":
    unittest.main()
