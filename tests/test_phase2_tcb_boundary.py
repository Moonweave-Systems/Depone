from __future__ import annotations

import unittest
from pathlib import Path


class Phase2TcbBoundaryTests(unittest.TestCase):
    def test_migrated_execution_modules_are_absent(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        removed_modules = (
            "depone/agent_fabric/codex_local_capability.py",
            "depone/agent_fabric/team_launch_preflight.py",
            "depone/agent_fabric/team_shell_lane_launch.py",
            "depone/agent_fabric/team_worktree_prep.py",
            "depone/cli/codex_local_capability.py",
            "depone/cli/team_launch_preflight.py",
            "depone/cli/team_shell_lane_launch.py",
            "depone/cli/team_worktree_prep.py",
        )

        self.assertEqual(
            [path for path in removed_modules if (repo / path).exists()],
            [],
        )


if __name__ == "__main__":
    unittest.main()
