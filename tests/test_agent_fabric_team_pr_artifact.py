from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_pr_artifact import (
    TEAM_PR_ARTIFACT_KIND,
    TEAM_PR_ARTIFACT_SCHEMA_VERSION,
    TeamPrArtifactError,
    build_team_pr_artifact,
    read_json_object,
    validate_team_pr_artifact,
    write_team_pr_artifact,
)


EXPECTED_HEAD = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


class AgentFabricTeamPrArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _source(self) -> dict[str, object]:
        return {
            "number": 42,
            "url": "https://github.com/Moonweave-Systems/Depone/pull/42",
            "baseRefOid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "headRefOid": EXPECTED_HEAD,
            "state": "OPEN",
            "mergeStateStatus": "CLEAN",
            "check_summary": {
                "status": "pass",
                "total_count": 2,
                "failed_count": 0,
                "pending_count": 0,
            },
        }

    def _artifact(self, **overrides: object) -> dict[str, object]:
        artifact = build_team_pr_artifact(
            self._source(),
            expected_head_sha=EXPECTED_HEAD,
            captured_at="2026-06-30T15:00:00Z",
        )
        artifact.update(overrides)
        return artifact

    def _codes(self, artifact: dict[str, object], *, expected_head_sha: str | None = EXPECTED_HEAD) -> set[str]:
        return {error["code"] for error in validate_team_pr_artifact(artifact, expected_head_sha=expected_head_sha)}

    def test_build_successful_fixture_shape(self) -> None:
        artifact = self._artifact()

        self.assertEqual(artifact["kind"], TEAM_PR_ARTIFACT_KIND)
        self.assertEqual(artifact["schema_version"], TEAM_PR_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(artifact["provider"], "github")
        self.assertEqual(artifact["pr_number"], 42)
        self.assertEqual(artifact["head_sha"], EXPECTED_HEAD)
        self.assertEqual(artifact["check_summary"]["status"], "pass")
        self.assertIs(artifact["stale"], False)
        self.assertEqual(validate_team_pr_artifact(artifact, expected_head_sha=EXPECTED_HEAD), [])
        self.assertFalse(artifact["boundary"]["executes_commands"])
        self.assertFalse(artifact["boundary"]["launches_agents"])
        self.assertFalse(artifact["boundary"]["calls_live_models"])
        self.assertFalse(artifact["boundary"]["raises_assurance"])

    def test_write_round_trips_deterministic_json(self) -> None:
        artifact = self._artifact()
        out = self.root / "nested" / "pr-artifact.json"

        write_team_pr_artifact(artifact, out)

        text = out.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), artifact)
        self.assertEqual(read_json_object(out), artifact)

    def test_malformed_input_blocks_build(self) -> None:
        with self.assertRaises(TeamPrArtifactError) as caught:
            build_team_pr_artifact(["not", "object"], captured_at="2026-06-30T15:00:00Z")  # type: ignore[arg-type]

        self.assertEqual(caught.exception.code, "ERR_TEAM_PR_ARTIFACT_INPUT_INVALID")

    def test_malformed_artifact_root_blocks_validation(self) -> None:
        errors = validate_team_pr_artifact(["not", "object"])  # type: ignore[arg-type]

        self.assertEqual(errors[0]["code"], "ERR_TEAM_PR_ARTIFACT_INVALID")

    def test_head_sha_mismatch_blocks_validation_and_marks_build_stale(self) -> None:
        stale_source = self._source()
        stale_source["headRefOid"] = "cccccccccccccccccccccccccccccccccccccccc"

        with self.assertRaises(TeamPrArtifactError) as caught:
            build_team_pr_artifact(
                stale_source,
                expected_head_sha=EXPECTED_HEAD,
                captured_at="2026-06-30T15:00:00Z",
            )

        self.assertEqual(caught.exception.code, "ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH")
        artifact = self._artifact(head_sha="cccccccccccccccccccccccccccccccccccccccc")
        self.assertIn("ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH", self._codes(artifact))

    def test_failed_checks_block(self) -> None:
        artifact = self._artifact(
            check_summary={"status": "fail", "total_count": 2, "failed_count": 1, "pending_count": 0}
        )

        self.assertIn("ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING", self._codes(artifact))

    def test_pending_checks_block(self) -> None:
        artifact = self._artifact(
            check_summary={"status": "pending", "total_count": 2, "failed_count": 0, "pending_count": 1}
        )

        self.assertIn("ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING", self._codes(artifact))

    def test_status_check_rollup_is_normalized(self) -> None:
        source = self._source()
        source.pop("check_summary")
        source["statusCheckRollup"] = [
            {"conclusion": "SUCCESS", "status": "COMPLETED"},
            {"conclusion": None, "status": "QUEUED"},
        ]

        with self.assertRaises(TeamPrArtifactError) as caught:
            build_team_pr_artifact(source, expected_head_sha=EXPECTED_HEAD, captured_at="2026-06-30T15:00:00Z")

        self.assertEqual(caught.exception.code, "ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING")

    def test_stale_artifact_blocks(self) -> None:
        artifact = self._artifact(stale=True)

        self.assertIn("ERR_TEAM_PR_ARTIFACT_STALE", self._codes(artifact))

    def test_bad_url_blocks(self) -> None:
        artifact = self._artifact(pr_url="http://example.invalid/pull/42")

        self.assertIn("ERR_TEAM_PR_ARTIFACT_URL_INVALID", self._codes(artifact))

    def test_bad_state_blocks(self) -> None:
        artifact = self._artifact(state="DRAFT")

        self.assertIn("ERR_TEAM_PR_ARTIFACT_STATE_INVALID", self._codes(artifact))

    def test_unmergeable_status_blocks(self) -> None:
        artifact = self._artifact(merge_state_status="DIRTY")

        self.assertIn("ERR_TEAM_PR_ARTIFACT_NOT_MERGEABLE", self._codes(artifact))

    def test_invalid_boundary_blocks(self) -> None:
        artifact = self._artifact(boundary={"observed_external_facts_only": True, "executes_commands": True})

        self.assertIn("ERR_TEAM_PR_ARTIFACT_BOUNDARY_INVALID", self._codes(artifact))

    def test_write_refuses_invalid_artifact(self) -> None:
        with self.assertRaises(TeamPrArtifactError) as caught:
            write_team_pr_artifact(self._artifact(stale=True), self.root / "pr-artifact.json")

        self.assertEqual(caught.exception.code, "ERR_TEAM_PR_ARTIFACT_STALE")
