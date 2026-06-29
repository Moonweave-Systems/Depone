from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from depone.cli.evidence_run import _launch_runner_user


class EvidenceRunUidLaunchTests(unittest.TestCase):
    def test_launch_runner_user_records_uid_and_receipt(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> object:
            if command == ["id", "-u", "deponerun"]:
                return type(
                    "Completed",
                    (),
                    {"returncode": 0, "stdout": "1001\n", "stderr": ""},
                )()
            if command[:4] == ["sudo", "-u", "deponerun", "bash"]:
                return type(
                    "Completed",
                    (),
                    {
                        "returncode": 0,
                        "stdout": "__DEPONE_RUNNER_UID=1001\nrunner-ok\n",
                        "stderr": "",
                    },
                )()
            raise AssertionError(f"unexpected command: {command}")

        with patch("depone.cli.evidence_run.shutil.which", return_value="sudo"):
            with patch("depone.cli.evidence_run.subprocess.run", side_effect=fake_run):
                receipt = _launch_runner_user(
                    Path("/srv/depone/sandbox"),
                    user="deponerun",
                    shell_command="printf runner-ok",
                )

        self.assertEqual(receipt["user"], "deponerun")
        self.assertEqual(receipt["uid"], 1001)
        self.assertEqual(receipt["observed_uid"], 1001)
        self.assertEqual(receipt["command"], "printf runner-ok")
        self.assertEqual(receipt["cwd"], "/srv/depone/sandbox")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["stdout"], "runner-ok\n")

    def test_launch_runner_user_fails_closed_when_command_fails(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> object:
            if command == ["id", "-u", "deponerun"]:
                return type(
                    "Completed",
                    (),
                    {"returncode": 0, "stdout": "1001\n", "stderr": ""},
                )()
            return type(
                "Completed",
                (),
                {"returncode": 17, "stdout": "", "stderr": "runner failed\n"},
            )()

        with patch("depone.cli.evidence_run.shutil.which", return_value="sudo"):
            with patch("depone.cli.evidence_run.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ValueError):
                    _launch_runner_user(
                        Path("/srv/depone/sandbox"),
                        user="deponerun",
                        shell_command="exit 17",
                    )


if __name__ == "__main__":
    unittest.main()
