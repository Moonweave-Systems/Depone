from __future__ import annotations

import subprocess
import sys
import unittest


class TeamLocalCliTests(unittest.TestCase):
    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-local", "--self-test"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("team-local --self-test: pass", completed.stdout)

    def test_missing_plan_json_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-local", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 3)
        self.assertIn("ERR_TEAM_LOCAL_PLAN_REQUIRED", completed.stdout)


if __name__ == "__main__":
    unittest.main()
