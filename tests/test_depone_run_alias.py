from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import depone.__main__ as depone_main


class DeponeRunAliasTests(unittest.TestCase):
    def test_run_alias_dispatches_to_evidence_run(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "run", "--self-test"]):
            with patch.object(depone_main.evidence_run, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "run")
        self.assertTrue(getattr(seen[0], "self_test"))

    def test_run_alias_preserves_evidence_run_arguments(self) -> None:
        seen = []
        argv = [
            "depone",
            "run",
            "--runner-sandbox",
            "/tmp/runner",
            "--source-fixture",
            "/tmp/source.json",
            "--out",
            "/tmp/out",
            "--allow-touched-file",
            "sample.txt",
            "--allow-touched-file",
            "notes.md",
            "--json",
            "--",
            sys.executable,
            "-m",
            "unittest",
        ]

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", argv):
            with patch.object(depone_main.evidence_run, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        args = seen[0]
        self.assertEqual(getattr(args, "runner_sandbox"), "/tmp/runner")
        self.assertEqual(getattr(args, "source_fixture"), "/tmp/source.json")
        self.assertEqual(getattr(args, "out"), "/tmp/out")
        self.assertEqual(getattr(args, "allow_touched_file"), ["sample.txt", "notes.md"])
        self.assertTrue(getattr(args, "json"))
        self.assertEqual(
            getattr(args, "verification_command"),
            ["--", sys.executable, "-m", "unittest"],
        )


if __name__ == "__main__":
    unittest.main()
