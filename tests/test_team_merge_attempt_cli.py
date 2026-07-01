from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class TeamMergeAttemptCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "depone@example.invalid")
        self._git("config", "user.name", "Depone Tests")
        (self.repo / "shared.txt").write_text("base\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "base")
        self.common = self._rev("HEAD")

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        return completed

    def _rev(self, rev: str) -> str:
        return self._git("rev-parse", rev).stdout.strip()

    def _branch_with_file(self, branch: str, path: str, content: str) -> str:
        self._git("checkout", "-B", branch, self.common)
        (self.repo / path).write_text(content, encoding="utf-8")
        self._git("add", path)
        self._git("commit", "-m", f"{branch} change")
        return self._rev("HEAD")

    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-merge-attempt", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("team-merge-attempt --self-test: pass", completed.stdout)

    def test_cli_writes_merge_attempt_receipt(self) -> None:
        base = self._branch_with_file("base-lane", "base-only.txt", "base lane\n")
        head = self._branch_with_file("head-lane", "head-only.txt", "head lane\n")
        out = self.root / "merge-attempt.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-merge-attempt",
                "--repo",
                str(self.repo),
                "--base",
                base,
                "--head",
                head,
                "--captured-at",
                "2026-07-01T00:00:00Z",
                "--out",
                str(out),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["command"], "team-merge-attempt")
        self.assertEqual(stdout["decision"], "pass")
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(receipt["kind"], "depone-team-merge-attempt")
        self.assertEqual(receipt["base_commit"], base)
        self.assertEqual(receipt["head_commits"], [head])
        self.assertIn("head-only.txt", receipt["merged_files"])
        self.assertTrue(receipt["cleanup"]["attempt_worktree_removed"])

    def test_main_dispatches_team_merge_attempt_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "team-merge-attempt", "--self-test"]):
            with patch.object(depone_main.team_merge_attempt, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-merge-attempt")
        self.assertTrue(getattr(seen[0], "self_test"))


if __name__ == "__main__":
    unittest.main()
