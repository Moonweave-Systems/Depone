from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


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

    def test_deprecated_execution_surfaces_are_shims_without_process_primitives(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        relative_modules = [
            Path("depone/agent_fabric/codex_local_capability.py"),
            Path("depone/agent_fabric/team_shell_lane_launch.py"),
            Path("depone/agent_fabric/team_worktree_prep.py"),
            Path("depone/cli/codex_local_capability.py"),
            Path("depone/cli/team_shell_lane_launch.py"),
            Path("depone/cli/team_worktree_prep.py"),
        ]
        violations: list[str] = []
        for relative in relative_modules:
            path = repo / relative
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in {"subprocess", "shutil"}:
                            violations.append(f"{relative}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module in {"subprocess", "shutil"}:
                        violations.append(f"{relative}: imports from {node.module}")
                elif isinstance(node, ast.Attribute):
                    if (
                        isinstance(node.value, ast.Name)
                        and node.value.id in {"subprocess", "shutil"}
                    ):
                        violations.append(f"{relative}: uses {node.value.id}.{node.attr}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
