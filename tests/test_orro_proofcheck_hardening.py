from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from depone.agent_fabric.superflow_artifacts import (
    build_superflow_artifact_verdict,
    load_superflow_artifacts,
)
from depone.cli import proofcheck


class OrroProofcheckHardeningTests(unittest.TestCase):
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

    def _copy_positive_fixture(self, name: str = "positive") -> Path:
        target = self.root / name
        shutil.copytree(self.FIXTURE_ROOT / "positive", target)
        return target

    def _write_json(self, directory: Path, filename: str, value: object) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _verdict_for(self, directory: Path) -> dict[str, Any]:
        return build_superflow_artifact_verdict(
            load_superflow_artifacts(directory),
            base_dir=directory,
        )

    def _assert_not_pass(self, verdict: dict[str, Any]) -> set[str]:
        self.assertIn(verdict["decision"], {"blocked", "refuted"})
        self.assertNotEqual(verdict["decision"], "pass")
        self.assertFalse(verdict["boundary"]["executes_commands"])
        self.assertFalse(verdict["boundary"]["calls_live_mcp"])
        self.assertFalse(verdict["boundary"]["calls_live_models"])
        self.assertFalse(verdict["boundary"]["mutates_worktree"])
        self.assertFalse(verdict["boundary"]["approves_merge"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])
        errors = verdict["errors"]
        self.assertIsInstance(errors, list)
        self.assertGreater(len(errors), 0)
        codes = {error["code"] for error in errors}
        self.assertTrue(all(code.startswith("ERR_ORRO_") for code in codes))
        for error in errors:
            legacy_code = error.get("legacy_code")
            if legacy_code is not None:
                self.assertTrue(legacy_code.startswith("ERR_SUPERFLOW_"))
        return codes

    def _wrapper_artifact(self, kind: str, **extra: object) -> dict[str, object]:
        return {
            "kind": kind,
            "schema_version": "0.1",
            "goal": "prove wrapper context is not proof",
            "raises_assurance": False,
            **extra,
        }

    def test_positive_control_valid_fixture_still_passes(self) -> None:
        fixture = self.FIXTURE_ROOT / "positive"

        verdict = self._verdict_for(fixture)

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["errors"], [])

    def test_scout_only_artifacts_do_not_pass_proofcheck(self) -> None:
        fixture = self.root / "scout-only"
        self._write_json(
            fixture,
            "repo-profile.json",
            {
                "kind": "orro-repo-profile",
                "schema_version": "1.0",
                "repo_root": ".",
                "branch": "main",
                "head_commit": "a" * 40,
                "files": ["README.md"],
            },
        )
        self._write_json(
            fixture,
            "context-pack.json",
            {
                "kind": "orro-context-pack",
                "schema_version": "1.0",
                "repo_profile_hash": "0" * 64,
                "selected_paths": ["README.md"],
            },
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_REQUIRED_MISSING", codes)

    def test_workflow_plan_only_is_intent_not_proof(self) -> None:
        fixture = self.root / "workflow-plan-only"
        self._write_json(
            fixture,
            "workflow-plan.json",
            self._wrapper_artifact(
                "orro-workflow-plan",
                profile="code-change",
                boundary={
                    "orro_is_third_engine": False,
                    "raises_assurance": False,
                },
            ),
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)

    def test_role_lane_plan_only_is_executable_intent_not_proof(self) -> None:
        fixture = self.root / "role-lane-plan-only"
        self._write_json(
            fixture,
            "role-lane-plan.json",
            self._wrapper_artifact(
                "orro-role-lane-plan",
                execution_allowed=True,
                lanes=[
                    {
                        "lane_id": "implementer-1",
                        "may_execute": True,
                        "may_verify": False,
                        "raises_assurance": False,
                    }
                ],
            ),
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)

    def test_workflow_role_dispatch_claim_is_not_execution_proof(self) -> None:
        fixture = self.root / "role-dispatch-only"
        self._write_json(
            fixture,
            "workflow-role-dispatch.json",
            self._wrapper_artifact(
                "orro-workflow-role-dispatch",
                roles=[
                    {
                        "role_id": "runner",
                        "status": "executed",
                        "evidence_refs": ["team-ledger.json"],
                        "raises_assurance": False,
                    }
                ],
            ),
        )

        self._assert_not_pass(self._verdict_for(fixture))

    def test_auto_artifacts_are_orchestration_metadata_not_proof(self) -> None:
        for filename, kind in [
            ("orro-auto-plan.json", "orro-auto-plan"),
            ("orro-auto-receipt.json", "orro-auto-receipt"),
            ("orro-auto-session.json", "orro-auto-session"),
        ]:
            with self.subTest(filename=filename):
                fixture = self.root / filename.removesuffix(".json")
                self._write_json(
                    fixture,
                    filename,
                    self._wrapper_artifact(kind, mode="dry-run", executed=True),
                )

                self._assert_not_pass(self._verdict_for(fixture))

    def test_handoff_artifact_only_is_review_package_not_proof(self) -> None:
        fixture = self.root / "handoff-only"
        self._write_json(
            fixture,
            "orro-handoff.json",
            self._wrapper_artifact(
                "orro-handoff",
                summary="proofcheck passed",
                approves_merge=False,
            ),
        )

        self._assert_not_pass(self._verdict_for(fixture))

    def test_existing_proofcheck_verdict_is_not_input_trust_root(self) -> None:
        fixture = self.root / "copied-proofcheck-verdict"
        self._write_json(
            fixture,
            "proofcheck-verdict.json",
            {
                "kind": "depone-team-ledger-verdict",
                "schema_version": "1.0",
                "decision": "pass",
                "errors": [],
                "boundary": {"raises_assurance": False},
            },
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)

    def test_verification_recipe_without_receipt_is_intent_only(self) -> None:
        fixture = self._copy_positive_fixture("recipe-without-receipt")
        (fixture / "verification-receipt.json").unlink()

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_REQUIRED_MISSING", codes)

    def test_malformed_verification_receipt_blocks(self) -> None:
        fixture = self._copy_positive_fixture("malformed-receipt")
        receipt = json.loads((fixture / "verification-receipt.json").read_text())
        receipt.pop("command_results", None)
        receipt.pop("runner_receipt_hash", None)
        self._write_json(fixture, "verification-receipt.json", receipt)

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_HASH_INVALID", codes)
        self.assertIn("ERR_ORRO_RECEIPT_RESULTS_INVALID", codes)

    def test_failed_verification_receipt_refutes_not_passes(self) -> None:
        fixture = self._copy_positive_fixture("failed-receipt")
        shutil.copy2(
            self.FIXTURE_ROOT
            / "negative-failed-receipt"
            / "verification-receipt.json",
            fixture / "verification-receipt.json",
        )

        verdict = self._verdict_for(fixture)
        codes = self._assert_not_pass(verdict)

        self.assertEqual(verdict["decision"], "refuted")
        self.assertIn("ERR_ORRO_RECEIPT_EXIT_CODE_MISMATCH", codes)

    def test_mcp_tool_receipt_only_is_observed_fact_not_trust_root(self) -> None:
        fixture = self.root / "mcp-only"
        fixture.mkdir(parents=True)
        shutil.copy2(
            self.FIXTURE_ROOT / "positive" / "mcp-tool-receipt-fake.json",
            fixture / "mcp-tool-receipt-fake.json",
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_REQUIRED_MISSING", codes)

    def test_model_transcript_only_is_not_machine_evidence(self) -> None:
        fixture = self.root / "transcript-only"
        self._write_json(
            fixture,
            "session-transcript.json",
            {
                "kind": "model-session-transcript",
                "schema_version": "0.1",
                "claim": "all tests passed",
                "model_confidence": "high",
            },
        )

        self._assert_not_pass(self._verdict_for(fixture))

    def test_wrapper_assurance_claim_does_not_raise_assurance_or_pass(self) -> None:
        fixture = self.root / "assurance-claim"
        self._write_json(
            fixture,
            "workflow-plan.json",
            self._wrapper_artifact(
                "orro-workflow-plan",
                raises_assurance=True,
                boundary={"raises_assurance": True},
            ),
        )

        self._assert_not_pass(self._verdict_for(fixture))

    def test_non_object_known_artifact_blocks_with_orro_primary_error(self) -> None:
        fixture = self._copy_positive_fixture("non-object-receipt")
        (fixture / "verification-receipt.json").write_text(
            "[\"not\", \"an\", \"object\"]\n",
            encoding="utf-8",
        )

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_MALFORMED", codes)

    def test_mixed_wrapper_artifacts_missing_runner_receipt_do_not_pass(self) -> None:
        fixture = self.root / "mixed-wrapper-artifacts"
        for filename, kind in [
            ("workflow-plan.json", "orro-workflow-plan"),
            ("workflow-plan-binding.json", "orro-workflow-plan-binding"),
            ("role-lane-plan.json", "orro-role-lane-plan"),
            ("role-lane-plan-binding.json", "orro-role-lane-plan-binding"),
            ("workflow-role-dispatch.json", "orro-workflow-role-dispatch"),
            ("orro-auto-receipt.json", "orro-auto-receipt"),
            ("orro-handoff.json", "orro-handoff"),
            ("orro-report.json", "orro-report"),
        ]:
            self._write_json(fixture, filename, self._wrapper_artifact(kind))

        codes = self._assert_not_pass(self._verdict_for(fixture))

        self.assertIn("ERR_ORRO_ARTIFACT_SET_EMPTY", codes)

    def test_proofcheck_does_not_execute_recipes_or_mutate_without_out(self) -> None:
        fixture = self._copy_positive_fixture("non-executing-proofcheck")
        before = sorted(path.relative_to(fixture) for path in fixture.rglob("*"))
        args = argparse.Namespace(
            evidence_dir=str(fixture),
            out="",
            json=True,
        )

        with patch("subprocess.run", side_effect=AssertionError("recipe executed")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                proofcheck.run(args)

        payload = json.loads(stdout.getvalue())
        after = sorted(path.relative_to(fixture) for path in fixture.rglob("*"))
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
