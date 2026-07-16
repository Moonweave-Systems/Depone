from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
    validate_mcp_tool_receipt,
    validate_verification_receipt,
)
from depone.agent_fabric.team_ledger import build_sample_team_ledger


class SuperflowArtifactTests(unittest.TestCase):
    FIXTURE_ROOT = (
        Path(__file__).resolve().parents[1]
        / "depone"
        / "fixtures"
        / "superflow"
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _copy_positive_fixture(self) -> Path:
        target = self.root / "positive"
        shutil.copytree(self.FIXTURE_ROOT / "positive", target)
        return target

    def _overlay(self, target: Path, fixture_dir: str, filename: str) -> None:
        shutil.copy2(self.FIXTURE_ROOT / fixture_dir / filename, target / filename)

    def _rewrite_fixture_kinds(self, fixture: Path, old: str, new: str) -> None:
        json_paths = [
            "repo-profile.json",
            "context-pack.json",
            "skillpack-lock.json",
            "verification-recipe.json",
            "verification-receipt.json",
            "mcp-tool-receipt-fake.json",
            "pr-handoff.json",
        ]
        objects = {
            name: json.loads((fixture / name).read_text(encoding="utf-8"))
            for name in json_paths
        }
        for value in objects.values():
            if isinstance(value.get("kind"), str):
                value["kind"] = value["kind"].replace(old, new, 1)

        objects["context-pack.json"]["repo_profile_hash"] = canonical_hash(
            objects["repo-profile.json"]
        )
        objects["verification-receipt.json"]["recipe_hash"] = canonical_hash(
            objects["verification-recipe.json"]
        )
        objects["pr-handoff.json"]["verification_receipt_hashes"] = [
            canonical_hash(objects["verification-receipt.json"])
        ]
        objects["pr-handoff.json"]["mcp_tool_receipt_hashes"] = [
            canonical_hash(objects["mcp-tool-receipt-fake.json"])
        ]

        for name, value in objects.items():
            (fixture / name).write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def test_positive_fixture_passes(self) -> None:
        fixture = self.FIXTURE_ROOT / "positive"

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["errors"], [])
        self.assertIs(verdict["signature_checked"], False)
        self.assertFalse(verdict["boundary"]["executes_commands"])
        self.assertFalse(verdict["boundary"]["calls_live_mcp"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])

    def test_orro_kind_fixture_passes(self) -> None:
        fixture = self._copy_positive_fixture()
        self._rewrite_fixture_kinds(fixture, "superflow-", "orro-")

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["kind"], "orro-artifact-verdict")
        self.assertEqual(verdict["errors"], [])

    def test_proofcheck_cli_verifies_team_ledger_evidence_dir(self) -> None:
        evidence_dir = self.root / "team-ledger-evidence"
        lane_dir = evidence_dir / "lane-evidence"
        lane_dir.mkdir(parents=True)
        (lane_dir / "evidence-next-verdict.json").write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": "continue",
                    "blocking_reasons": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        (evidence_dir / "team-ledger.json").write_text(
            json.dumps(ledger, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verdict_path = evidence_dir / "proofcheck-verdict.json"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--evidence-dir",
                str(evidence_dir),
                "--out",
                str(verdict_path),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["command"], "proofcheck")
        self.assertEqual(summary["verifier_command"], "team-ledger")
        self.assertEqual(summary["decision"], "pass")
        self.assertIs(summary["signature_checked"], False)
        self.assertEqual(verdict["kind"], "depone-team-ledger-verdict")
        self.assertEqual(verdict["decision"], "pass")
        self.assertIs(verdict["signature_checked"], False)

    def test_missing_evidence_dir_blocks(self) -> None:
        fixture = self.root / "missing"

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_EVIDENCE_DIR_MISSING", codes)
        self.assertEqual(
            verdict["errors"][0]["legacy_code"],
            "ERR_SUPERFLOW_EVIDENCE_DIR_MISSING",
        )

    def test_non_directory_evidence_path_blocks(self) -> None:
        fixture = self.root / "not-a-dir"
        fixture.write_text("not a directory\n", encoding="utf-8")

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_EVIDENCE_DIR_NOT_DIRECTORY", codes)

    def test_empty_evidence_dir_blocks(self) -> None:
        fixture = self.root / "empty"
        fixture.mkdir()

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)
        self.assertIn("ERR_ORRO_ARTIFACT_REQUIRED_MISSING", codes)

    def test_missing_required_artifact_blocks(self) -> None:
        fixture = self._copy_positive_fixture()
        (fixture / "context-pack.json").unlink()

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_ARTIFACT_REQUIRED_MISSING", codes)

    def test_malformed_artifact_blocks(self) -> None:
        fixture = self._copy_positive_fixture()
        (fixture / "context-pack.json").write_text("{not json\n", encoding="utf-8")

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_ARTIFACT_MALFORMED", codes)

    def test_placeholder_runner_receipt_hash_blocks(self) -> None:
        fixture = self._copy_positive_fixture()
        receipt_path = fixture / "verification-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["runner_receipt_hash"] = "0" * 64
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("ERR_ORRO_RECEIPT_RUNNER_HASH_PLACEHOLDER", codes)

    def test_failed_verification_receipt_refutes_fixture(self) -> None:
        fixture = self._copy_positive_fixture()
        self._overlay(
            fixture,
            "negative-failed-receipt",
            "verification-receipt.json",
        )

        artifacts = load_superflow_artifacts(fixture)
        verdict = build_superflow_artifact_verdict(artifacts, base_dir=fixture)
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "refuted")
        self.assertIn("ERR_ORRO_RECEIPT_EXIT_CODE_MISMATCH", codes)
        self.assertIn(
            "ERR_ORRO_PR_HANDOFF_VERIFICATION_RECEIPT_HASH_MISSING",
            codes,
        )

    def test_forged_mcp_output_hash_refutes_fixture(self) -> None:
        fixture = self._copy_positive_fixture()
        self._overlay(
            fixture,
            "negative-forged-mcp",
            "mcp-tool-receipt-fake.json",
        )

        artifacts = load_superflow_artifacts(fixture)
        verdict = build_superflow_artifact_verdict(artifacts, base_dir=fixture)
        codes = {error["code"] for error in verdict["errors"]}

        self.assertEqual(verdict["decision"], "refuted")
        self.assertIn("ERR_ORRO_MCP_RECEIPT_OUTPUT_HASH_MISMATCH", codes)
        self.assertIn("ERR_ORRO_PR_HANDOFF_MCP_RECEIPT_HASH_MISSING", codes)

    def test_direct_validators_report_focused_errors(self) -> None:
        fixture = self._copy_positive_fixture()
        self._overlay(
            fixture,
            "negative-failed-receipt",
            "verification-receipt.json",
        )
        recipe = json.loads((fixture / "verification-recipe.json").read_text())
        receipt = json.loads((fixture / "verification-receipt.json").read_text())

        receipt_codes = {
            error["code"]
            for error in validate_verification_receipt(receipt, recipe=recipe)
        }

        self.assertEqual(
            receipt_codes,
            {"ERR_ORRO_RECEIPT_EXIT_CODE_MISMATCH"},
        )
        receipt_legacy_codes = {
            error["legacy_code"]
            for error in validate_verification_receipt(receipt, recipe=recipe)
        }
        self.assertEqual(
            receipt_legacy_codes,
            {"ERR_SUPERFLOW_RECEIPT_EXIT_CODE_MISMATCH"},
        )

        forged_mcp = json.loads(
            (
                self.FIXTURE_ROOT
                / "negative-forged-mcp"
                / "mcp-tool-receipt-fake.json"
            ).read_text()
        )
        mcp_codes = {error["code"] for error in validate_mcp_tool_receipt(forged_mcp)}
        self.assertEqual(
            mcp_codes,
            {"ERR_ORRO_MCP_RECEIPT_OUTPUT_HASH_MISMATCH"},
        )

    def test_proofcheck_cli_passes_positive_fixture(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--evidence-dir",
                str(self.FIXTURE_ROOT / "positive"),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["error_count"], 0)

    def test_proofcheck_cli_input_error_uses_orro_primary_code(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["error"]["code"], "ERR_ORRO_PROOFCHECK_INPUT_REQUIRED")
        self.assertEqual(
            payload["error"]["legacy_code"],
            "ERR_SUPERFLOW_PROOFCHECK_INPUT_REQUIRED",
        )

    def test_proofcheck_cli_blocks_missing_evidence_dir(self) -> None:
        fixture = self.root / "missing"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--evidence-dir",
                str(fixture),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "blocked")
        self.assertEqual(
            payload["errors"][0]["code"],
            "ERR_ORRO_EVIDENCE_DIR_MISSING",
        )
        self.assertEqual(
            payload["errors"][0]["legacy_code"],
            "ERR_SUPERFLOW_EVIDENCE_DIR_MISSING",
        )

    def test_proofcheck_cli_blocks_empty_evidence_dir(self) -> None:
        fixture = self.root / "empty"
        fixture.mkdir()

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--evidence-dir",
                str(fixture),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "blocked")
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)

    def test_proofcheck_cli_blocks_failed_receipt(self) -> None:
        fixture = self._copy_positive_fixture()
        self._overlay(
            fixture,
            "negative-failed-receipt",
            "verification-receipt.json",
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "proofcheck",
                "--evidence-dir",
                str(fixture),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "refuted")
        self.assertGreater(payload["error_count"], 0)
