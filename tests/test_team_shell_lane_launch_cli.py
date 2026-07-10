from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import depone.__main__ as depone_main


class TeamShellLaneLaunchCliTests(unittest.TestCase):
    def test_main_dispatches_team_shell_lane_launch_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(
            sys, "argv", ["depone", "team-shell-lane-launch", "--self-test"]
        ):
            with patch.object(
                depone_main.team_shell_lane_launch, "run", side_effect=fake_run
            ):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-shell-lane-launch")
        self.assertTrue(getattr(seen[0], "self_test"))


if __name__ == "__main__":
    unittest.main()
