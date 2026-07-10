from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from depone.agent_fabric import codex_local_capability as capability
from depone.agent_fabric.codex_local_capability import (
    ALLOWED_APPROVAL_POLICIES,
    build_codex_local_capability,
    validate_codex_local_capability,
)


def _seed_repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
    fake_codex = root / "codex"
    fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.test\\n'\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    subprocess.run(["git", "add", "codex"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
    return fake_codex


class Phase0CodexLocalCapabilityQaTests(unittest.TestCase):
    def test_qa03_instruction_symlink_escape_blocks_without_hashing_target(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as outside_dir:
            repo = Path(repo_dir)
            fake_codex = _seed_repo(repo)
            outside = Path(outside_dir) / "outside.md"
            outside.write_text("outside secret instructions", encoding="utf-8")
            (repo / "AGENTS.md").symlink_to(outside)

            with (
                patch("shutil.which", return_value=fake_codex.as_posix()),
                patch("depone.agent_fabric.codex_local_capability.importlib.import_module", side_effect=ImportError),
            ):
                receipt = build_codex_local_capability(
                    repo=repo,
                    instruction_files=[Path("AGENTS.md")],
                )

        self.assertEqual(receipt["decision"], "blocked")
        blocked_reasons = cast(list[str], receipt["blocked_reasons"])
        self.assertIn(
            "instruction file path outside repo boundary",
            blocked_reasons,
        )
        instruction_files = cast(list[dict[str, object]], receipt["instruction_files"])
        instruction = instruction_files[0]
        self.assertFalse(instruction["present"])
        self.assertIsNone(instruction["sha256"])
        self.assertIn("blocked_reason", instruction)
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_qa04_git_probe_unknown_never_reports_clean(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)

            def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
                if argv[-2:] == ["rev-parse", "--show-toplevel"]:
                    return SimpleNamespace(
                        returncode=0,
                        stdout=str(repo) + "\n",
                        stderr="",
                    )
                return SimpleNamespace(returncode=128, stdout="", stderr="fatal")

            with patch.object(capability.subprocess, "run", side_effect=fake_run):
                facts = capability._git_facts(repo)

        self.assertTrue(facts["is_git_worktree"])
        self.assertNotEqual(facts.get("dirty"), False)
        self.assertIn("error", facts)

    def test_git_probe_timeout_never_reports_clean(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)

            with patch.object(
                capability.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["git", "status"], 10),
            ):
                facts = capability._git_facts(repo)

        self.assertFalse(facts["is_git_worktree"])
        self.assertNotEqual(facts.get("dirty"), False)
        probe_errors = cast(list[str], facts["probe_errors"])
        self.assertIn("git status unknown", probe_errors)

    def test_qa06_current_codex_approval_policy_untrusted_is_supported(self) -> None:
        self.assertIn("untrusted", ALLOWED_APPROVAL_POLICIES)


if __name__ == "__main__":
    unittest.main()
