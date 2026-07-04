from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
    validate_mcp_tool_receipt,
    validate_verification_receipt,
)


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

    def test_positive_fixture_passes(self) -> None:
        fixture = self.FIXTURE_ROOT / "positive"

        verdict = build_superflow_artifact_verdict(
            load_superflow_artifacts(fixture),
            base_dir=fixture,
        )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["errors"], [])
        self.assertFalse(verdict["boundary"]["executes_commands"])
        self.assertFalse(verdict["boundary"]["calls_live_mcp"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])

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
        self.assertIn("ERR_SUPERFLOW_RECEIPT_EXIT_CODE_MISMATCH", codes)
        self.assertIn(
            "ERR_SUPERFLOW_PR_HANDOFF_VERIFICATION_RECEIPT_HASH_MISSING",
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
        self.assertIn("ERR_SUPERFLOW_MCP_RECEIPT_OUTPUT_HASH_MISMATCH", codes)
        self.assertIn("ERR_SUPERFLOW_PR_HANDOFF_MCP_RECEIPT_HASH_MISSING", codes)

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
            {"ERR_SUPERFLOW_MCP_RECEIPT_OUTPUT_HASH_MISMATCH"},
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
