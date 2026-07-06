from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
)
from depone.agent_fabric.team_ledger import build_sample_team_ledger
from depone.cli import proofcheck


class OrroEngineContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write_json(self, directory: Path, filename: str, payload: object) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _artifact_verdict(self, directory: Path) -> dict:
        return build_superflow_artifact_verdict(
            load_superflow_artifacts(directory),
            base_dir=directory,
        )

    def test_contract_doc_and_manifest_define_required_artifacts(self) -> None:
        contract = (self.ROOT / "docs" / "orro-engine-contract-v0.md").read_text(
            encoding="utf-8"
        )
        manifest = json.loads(
            (self.ROOT / "docs" / "orro-conformance" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("Depone verifies; witnessd executes; ORRO exposes the workflow.", contract)
        for artifact in [
            "repo-profile.json",
            "context-pack.json",
            "sealed-plan.json",
            "workflow-plan.json",
            "workflow-plan-binding.json",
            "role-lane-plan.json",
            "role-lane-plan-binding.json",
            "workflow-role-dispatch.json",
            "team-ledger.json",
            "team-ledger-verdict.json",
            "verification-recipe.json",
            "verification-receipt.json",
            "proofcheck-verdict.json",
            "orro-continuation-decision.json",
            "orro-auto-plan.json",
            "orro-auto-receipt.json",
            "orro-auto-session.json",
            "orro-report.json",
            "orro-handoff.json",
            "orro-engine-lock.json",
        ]:
            self.assertIn(artifact, contract)
        self.assertEqual(manifest["kind"], "orro-conformance-manifest")
        self.assertEqual(manifest["schema_version"], "0.1")
        self.assertGreaterEqual(len(manifest["fixtures"]), 5)

    def test_valid_team_ledger_evidence_dir_passes_proofcheck(self) -> None:
        evidence_dir = self.root / "valid-team-ledger-run"
        lane_dir = evidence_dir / "lane-evidence"
        lane_dir.mkdir(parents=True)
        self._write_json(
            lane_dir,
            "evidence-next-verdict.json",
            {
                "command": "evidence-next",
                "schema_version": "1.0",
                "decision": "continue",
                "blocking_reasons": [],
            },
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        self._write_json(evidence_dir, "team-ledger.json", ledger)

        args = argparse.Namespace(evidence_dir=str(evidence_dir), out="", json=True)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            proofcheck.run(args)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["verifier_command"], "team-ledger")

    def test_wrapper_and_planning_only_dirs_block_with_orro_primary_errors(self) -> None:
        cases = {
            "scout-only": {
                "repo-profile.json": {
                    "kind": "orro-repo-profile",
                    "schema_version": "1.0",
                    "repo_root": ".",
                    "branch": "main",
                    "head_commit": "a" * 40,
                    "files": ["README.md"],
                }
            },
            "workflow-plan-only": {
                "workflow-plan.json": {
                    "kind": "orro-workflow-plan",
                    "schema_version": "0.1",
                }
            },
            "wrapper-artifacts-only": {
                "workflow-role-dispatch.json": {
                    "kind": "orro-role-dispatch",
                    "schema_version": "0.1",
                    "roles": [{"role_id": "runner", "status": "executed"}],
                },
                "orro-auto-session.json": {
                    "kind": "orro-auto-session",
                    "schema_version": "0.1",
                    "complete": True,
                },
                "orro-report.json": {
                    "kind": "orro-report",
                    "schema_version": "0.1",
                    "summary": {"state": "complete"},
                },
            },
            "copied-proofcheck-verdict": {
                "proofcheck-verdict.json": {
                    "kind": "depone-team-ledger-verdict",
                    "schema_version": "1.0",
                    "decision": "pass",
                    "errors": [],
                }
            },
        }

        for name, files in cases.items():
            with self.subTest(name=name):
                evidence_dir = self.root / name
                for filename, payload in files.items():
                    self._write_json(evidence_dir, filename, payload)

                verdict = self._artifact_verdict(evidence_dir)
                codes = {error["code"] for error in verdict["errors"]}

                self.assertEqual(verdict["decision"], "blocked")
                self.assertNotEqual(verdict["decision"], "pass")
                self.assertTrue(all(code.startswith("ERR_ORRO_") for code in codes))
                self.assertFalse(verdict["boundary"]["executes_commands"])
                self.assertFalse(verdict["boundary"]["raises_assurance"])

    def test_proofcheck_path_does_not_execute_recipes_or_workers(self) -> None:
        evidence_dir = self.root / "recipe-only"
        self._write_json(
            evidence_dir,
            "verification-recipe.json",
            {
                "kind": "orro-verification-recipe",
                "schema_version": "1.0",
                "commands": [
                    {
                        "id": "would-run",
                        "argv": ["sh", "-c", "exit 1"],
                        "expected_exit_code": 0,
                        "required": True,
                    }
                ],
            },
        )
        args = argparse.Namespace(evidence_dir=str(evidence_dir), out="", json=True)

        with patch("subprocess.run", side_effect=AssertionError("recipe executed")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                with self.assertRaises(SystemExit):
                    proofcheck.run(args)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["decision"], "blocked")
        self.assertFalse((evidence_dir / "proofcheck-verdict.json").exists())


if __name__ == "__main__":
    unittest.main()
