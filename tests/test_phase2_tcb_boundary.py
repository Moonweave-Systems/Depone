from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import unittest


class Phase2TcbBoundaryTests(unittest.TestCase):
    def test_depone_cli_import_does_not_load_execution_surfaces(self) -> None:
        script = textwrap.dedent(
            """
            import json
            import sys

            import depone.__main__  # noqa: F401

            forbidden = [
                "depone.agent_fabric.codex_local_capability",
                "depone.agent_fabric.team_launch_preflight",
                "depone.agent_fabric.team_shell_lane_launch",
                "depone.agent_fabric.team_worktree_prep",
                "depone.cli.codex_local_capability",
                "depone.cli.team_launch_preflight",
                "depone.cli.team_shell_lane_launch",
                "depone.cli.team_worktree_prep",
            ]
            loaded = [name for name in forbidden if name in sys.modules]
            print(json.dumps({"loaded": loaded}, sort_keys=True))
            raise SystemExit(1 if loaded else 0)
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"loaded": []})


if __name__ == "__main__":
    unittest.main()
