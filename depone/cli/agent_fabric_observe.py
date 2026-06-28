from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.observe import (
    build_separated_observer_capture,
    canonical_json_pretty,
    enforce_path_outside_runner_sandbox,
    write_observer_capture,
)
from depone.agent_fabric.paired_run import PairedRunError
from depone.agent_fabric.seal import seal_capture


DEFAULT_SEAL_KEY_ID = "observer-held-key"


def _seal_path_for_capture(out_path: Path) -> Path:
    return out_path.expanduser().resolve(strict=False).with_suffix(".seal.json")


def _observer_seal_config(args: argparse.Namespace) -> tuple[bytes, str] | None:
    key_file = str(getattr(args, "seal_key_file", "") or "")
    env_key = os.environ.get("DEPONE_OBSERVER_SEAL_KEY")
    key_id = (
        str(getattr(args, "seal_key_id", "") or "")
        or os.environ.get("DEPONE_OBSERVER_SEAL_KEY_ID", "")
        or DEFAULT_SEAL_KEY_ID
    )
    if key_file:
        key_path = enforce_path_outside_runner_sandbox(
            runner_sandbox=Path(str(getattr(args, "runner_sandbox", ""))),
            path=Path(key_file),
            label="--seal-key-file",
        )
        return key_path.read_bytes(), key_id
    if env_key is not None:
        return env_key.encode("utf-8"), key_id
    return None


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
        seal_config = _observer_seal_config(args)
        capture = build_separated_observer_capture(
            runner_sandbox=Path(str(getattr(args, "runner_sandbox", ""))),
            source_fixture_hash=str(getattr(args, "source_fixture_hash", "")),
            verification_command=command,
            out_path=Path(str(getattr(args, "out", ""))),
            log_path=Path(str(getattr(args, "log", ""))),
            timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
        )
        out_path = Path(str(getattr(args, "out")))
        capture_hash = write_observer_capture(out_path, capture)
        seal: dict[str, object] | None = None
        seal_path: Path | None = None
        if seal_config is not None:
            key, key_id = seal_config
            seal = seal_capture(capture, key, key_id=key_id)
            seal_path = _seal_path_for_capture(out_path)
            seal_path.write_text(canonical_json_pretty(seal), encoding="utf-8")
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
    if seal is not None and seal_path is not None:
        print(f"  observer_capture_seal: {seal_path}")
        print(f"  seal_value: {seal['value']}")


def _self_test() -> None:
    from depone.agent_fabric.observe import _self_test as observe_self_test

    observe_self_test()
