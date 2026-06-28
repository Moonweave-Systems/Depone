from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.observe import (
    build_separated_observer_capture,
    write_observer_capture,
)
from depone.agent_fabric.paired_run import PairedRunError


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    command = list(getattr(args, "verification_command", []) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(
            "Usage: depone agent-fabric-observe --runner-sandbox <dir> "
            "--source-fixture-hash <hash> --out <observer-capture.json> "
            "--log <verify-log.json> -- <verification command>",
            file=sys.stderr,
        )
        sys.exit(1)
    if not str(getattr(args, "runner_sandbox", "")):
        print("Error: --runner-sandbox is required", file=sys.stderr)
        sys.exit(1)
    if not str(getattr(args, "source_fixture_hash", "")):
        print("Error: --source-fixture-hash is required", file=sys.stderr)
        sys.exit(1)

    try:
        capture = build_separated_observer_capture(
            runner_sandbox=Path(str(getattr(args, "runner_sandbox", ""))),
            source_fixture_hash=str(getattr(args, "source_fixture_hash", "")),
            verification_command=command,
            out_path=Path(str(getattr(args, "out", ""))),
            log_path=Path(str(getattr(args, "log", ""))),
            timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
        )
        capture_hash = write_observer_capture(Path(str(getattr(args, "out"))), capture)
    except PairedRunError as exc:
        print(json.dumps({"error": exc.to_record()}, sort_keys=True), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "ERR_OBSERVER_CAPTURE_FAILED",
                        "message": str(exc),
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Observer capture written to {Path(str(getattr(args, 'out')))}")
    print(f"  observer_capture_hash: {capture_hash}")
    print(f"  canonical_hash: {canonical_hash(capture)}")


def _self_test() -> None:
    from depone.agent_fabric.observe import _self_test as observe_self_test

    observe_self_test()
