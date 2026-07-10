from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import depone.__main__ as depone_main


class CodexLocalCapabilityCliTests(unittest.TestCase):
    def test_main_dispatches_codex_local_capability(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(
            sys, "argv", ["depone", "codex-local-capability", "--self-test"]
        ):
            with patch.object(
                depone_main.codex_local_capability, "run", side_effect=fake_run
            ):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "codex-local-capability")


if __name__ == "__main__":
    unittest.main()
