from __future__ import annotations

import unittest
from depone.agent_fabric.paired_run import (
    build_paired_run_report,
    build_runner_receipt,
    now_utc,
    validate_runner_receipt,
)


class AgentFabricPairedRunTests(unittest.TestCase):
    def test_runner_receipt_requires_transcript_and_valid_arm(self) -> None:
        receipt = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="worktree",
            invocation=["codex", "run"],
            transcript_path="transcript.log",
            exit_code=0,
            touched_files=["task.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )

        self.assertEqual(validate_runner_receipt(receipt), [])

        receipt["transcript_path"] = ""
        receipt["arm"] = "other"
        errors = validate_runner_receipt(receipt)
        self.assertIn("transcript_path must be a non-empty string", errors)
        self.assertIn("arm must be one of ['direct', 'governed']", errors)

    def test_runner_receipt_rejects_source_hash_mismatch(self) -> None:
        receipt = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="worktree",
            invocation=["codex", "run"],
            transcript_path="transcript.log",
            exit_code=0,
            touched_files=["task.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        receipt["source_hashes"]["receipt"] = "0" * 64

        errors = validate_runner_receipt(receipt)

        self.assertIn("source_hashes.receipt mismatch", errors)

    def test_paired_run_report_blocks_failed_governed_verification(self) -> None:
        direct_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="direct",
            task_id="task",
            worktree="direct",
            invocation=["codex", "exec"],
            transcript_path="direct.log",
            exit_code=0,
            touched_files=["result.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        governed_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="governed",
            invocation=["codex", "exec"],
            transcript_path="governed.log",
            exit_code=0,
            touched_files=[],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        direct_observer = {
            "test_output": {"status": "passed"},
            "touched_files": ["result.txt"],
        }
        governed_observer = {
            "test_output": {"status": "failed"},
            "touched_files": [],
        }

        report = build_paired_run_report(
            task_id="task",
            direct_runner=direct_runner,
            direct_observer=direct_observer,
            governed_runner=governed_runner,
            governed_observer=governed_observer,
        )

        self.assertEqual(report["decision"], "blocked-paired-run-not-ready")
        self.assertEqual(
            report["blockers"][0]["code"],
            "ERR_PAIRED_RUN_VERIFICATION_NOT_PASSED",
        )

        governed_observer["test_output"]["status"] = "passed"
        governed_observer["touched_files"] = ["result.txt"]
        governed_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="governed",
            invocation=["codex", "exec"],
            transcript_path="governed.log",
            exit_code=0,
            touched_files=["result.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        ready = build_paired_run_report(
            task_id="task",
            direct_runner=direct_runner,
            direct_observer=direct_observer,
            governed_runner=governed_runner,
            governed_observer=governed_observer,
        )
        self.assertEqual(ready["decision"], "paired-run-observed")


if __name__ == "__main__":
    unittest.main()
