from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import (
    ASSURANCE_A1,
    build_capture_manifest,
    validate_capture_manifest,
)
from depone.agent_fabric.claim_gate import canonical_hash


def _run_git(repo: Path, args: list[str]) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())


def _make_runner_sandbox(root: Path) -> Path:
    sandbox = root / "runner-sandbox"
    sandbox.mkdir()
    _run_git(sandbox, ["init"])
    _run_git(sandbox, ["config", "user.email", "observer@example.invalid"])
    _run_git(sandbox, ["config", "user.name", "Observer Test"])
    (sandbox / "sample.txt").write_text("before\n", encoding="utf-8")
    _run_git(sandbox, ["add", "sample.txt"])
    _run_git(sandbox, ["commit", "-m", "seed"])
    (sandbox / "sample.txt").write_text("after\n", encoding="utf-8")
    return sandbox


class AgentFabricObserveTest(unittest.TestCase):
    def test_separation_enforced_for_out_inside_runner_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sandbox = _make_runner_sandbox(root)
            out_path = sandbox / "observer-capture.json"
            command = [
                sys.executable,
                "-m",
                "depone",
                "agent-fabric-observe",
                "--runner-sandbox",
                str(sandbox),
                "--source-fixture-hash",
                "fixture-hash",
                "--out",
                str(out_path),
                "--log",
                str(sandbox / "verify-log.json"),
                "--",
                sys.executable,
                "-c",
                "print('should not run')",
            ]
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERR_OBSERVER_NOT_SEPARATED", result.stderr)
            self.assertFalse(out_path.exists())
            self.assertFalse((sandbox / "verify-log.json").exists())

    def test_happy_path_records_independence_and_validates_a1_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sandbox = _make_runner_sandbox(root)
            observer_dir = root / "observer-owned"
            out_path = observer_dir / "observer-capture.json"
            log_path = observer_dir / "verify-log.json"
            fixture = json.loads(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json")
            )
            fixture_hash = canonical_hash(fixture)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-observe",
                    "--runner-sandbox",
                    str(sandbox),
                    "--source-fixture-hash",
                    fixture_hash,
                    "--out",
                    str(out_path),
                    "--log",
                    str(log_path),
                    "--",
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('sample.txt').exists()",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out_path.exists())
            self.assertTrue(log_path.exists())
            capture = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn(canonical_hash(capture), result.stdout)
            independence = capture["observer_independence"]
            self.assertEqual(
                independence["model"],
                "separate-process-observer-owned-dir",
            )
            self.assertTrue(independence["out_is_outside_sandbox"])
            self.assertFalse(independence["privilege_boundary"])
            self.assertFalse(independence["tamper_resistant_same_uid"])
            self.assertIn("sample.txt", capture["touched_files"])

            manifest = build_capture_manifest(
                fixture,
                observer_capture=capture,
                allowed_touched_files=["sample.txt"],
            )
            self.assertEqual(manifest["assurance"], ASSURANCE_A1)
            self.assertEqual(manifest["observer_capture_hash"], canonical_hash(capture))
            self.assertEqual(validate_capture_manifest(manifest), [])


if __name__ == "__main__":
    unittest.main()
