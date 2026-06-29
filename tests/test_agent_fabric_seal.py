from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone._resources import resource_text
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.seal import seal_capture, verify_capture_seal


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
    _run_git(sandbox, ["config", "user.email", "seal@example.invalid"])
    _run_git(sandbox, ["config", "user.name", "Seal Test"])
    (sandbox / "sample.txt").write_text("before\n", encoding="utf-8")
    _run_git(sandbox, ["add", "sample.txt"])
    _run_git(sandbox, ["commit", "-m", "seed"])
    (sandbox / "sample.txt").write_text("after\n", encoding="utf-8")
    return sandbox


class AgentFabricSealTest(unittest.TestCase):
    def test_round_trip_verifies_with_same_key(self) -> None:
        capture = {"observed_by": "observer", "touched_files": ["sample.txt"]}
        key = b"observer-held-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        self.assertTrue(verify_capture_seal(capture, seal, key))

    def test_wrong_key_tamper_and_malformed_seal_fail_closed(self) -> None:
        capture = {"observed_by": "observer", "touched_files": ["sample.txt"]}
        key = b"observer-held-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        self.assertFalse(verify_capture_seal(capture, seal, b"wrong-key"))
        tampered = dict(capture)
        tampered["touched_files"] = ["other.txt"]
        self.assertFalse(verify_capture_seal(tampered, seal, key))
        malformed = dict(seal)
        malformed["alg"] = "HMAC-SHA1"
        self.assertFalse(verify_capture_seal(capture, malformed, key))
        self.assertFalse(verify_capture_seal(capture, {"alg": "HMAC-SHA256"}, key))

    def test_key_id_is_non_secret_label_not_key_material(self) -> None:
        capture = {"observed_by": "observer"}
        key = b"super-secret-observer-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        seal_json = json.dumps(seal, sort_keys=True)
        self.assertNotEqual(seal["key_id"], key.decode("utf-8"))
        self.assertNotIn(key.decode("utf-8"), seal_json)

    def test_observe_rejects_seal_key_inside_runner_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sandbox = _make_runner_sandbox(root)
            key_path = sandbox / "observer.key"
            key_path.write_bytes(b"runner-visible-key")
            observer_dir = root / "observer-owned"
            out_path = observer_dir / "observer-capture.json"
            log_path = observer_dir / "verify-log.json"
            fixture = json.loads(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json")
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-observe",
                    "--runner-sandbox",
                    str(sandbox),
                    "--source-fixture-hash",
                    canonical_hash(fixture),
                    "--out",
                    str(out_path),
                    "--log",
                    str(log_path),
                    "--seal-key-file",
                    str(key_path),
                    "--",
                    sys.executable,
                    "-c",
                    "print('should not run')",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERR_OBSERVER_NOT_SEPARATED", result.stderr)
            self.assertFalse(out_path.exists())
            self.assertFalse(out_path.with_suffix(".seal.json").exists())

    def test_observe_writes_seal_outside_sandbox_and_verify_cli_confirms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sandbox = _make_runner_sandbox(root)
            observer_dir = root / "observer-owned"
            observer_dir.mkdir()
            key_path = observer_dir / "observer.key"
            key_path.write_bytes(b"observer-held-key")
            out_path = observer_dir / "observer-capture.json"
            log_path = observer_dir / "verify-log.json"
            fixture = json.loads(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json")
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-observe",
                    "--runner-sandbox",
                    str(sandbox),
                    "--source-fixture-hash",
                    canonical_hash(fixture),
                    "--out",
                    str(out_path),
                    "--log",
                    str(log_path),
                    "--seal-key-file",
                    str(key_path),
                    "--seal-key-id",
                    "observer-key-1",
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
            seal_path = out_path.with_suffix(".seal.json")
            self.assertTrue(out_path.exists())
            self.assertTrue(seal_path.exists())
            self.assertIn("seal_value:", result.stdout)
            verify = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-verify-seal",
                    "--capture",
                    str(out_path),
                    "--seal",
                    str(seal_path),
                    "--seal-key-file",
                    str(key_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertIn("verified: true", verify.stdout)


if __name__ == "__main__":
    unittest.main()
