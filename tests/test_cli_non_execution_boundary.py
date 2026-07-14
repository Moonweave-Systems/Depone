from __future__ import annotations

import re
import subprocess
import sys
import unittest

from depone.agent_fabric import paired_run


REMOVED_EXECUTION_COMMANDS = (
    "agent-fabric-paired-run",
    "agent-fabric-observe",
    "observe",
    "evidence-run",
    "run",
    "advance",
    "team-launch-preflight",
    "team-worktree-prep",
    "team-shell-lane-launch",
    "codex-local-capability",
)


class CliNonExecutionBoundaryTests(unittest.TestCase):
    def test_paired_run_module_has_no_execution_helpers(self) -> None:
        self.assertFalse(hasattr(paired_run, "run_codex_exec"))
        self.assertFalse(hasattr(paired_run, "run_verification_command"))

    def test_help_does_not_register_execution_commands(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        match = re.search(r"usage: depone .*?\{([^}]+)\}", completed.stdout, re.DOTALL)
        self.assertIsNotNone(match, completed.stdout)
        commands = set(match.group(1).replace("\n", "").replace(" ", "").split(","))
        self.assertEqual(commands.intersection(REMOVED_EXECUTION_COMMANDS), set())

    def test_removed_execution_commands_are_unknown(self) -> None:
        for command in REMOVED_EXECUTION_COMMANDS:
            with self.subTest(command=command):
                completed = subprocess.run(
                    [sys.executable, "-m", "depone", command],
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 3)
                self.assertIn("invalid choice", completed.stderr)


if __name__ == "__main__":
    unittest.main()
