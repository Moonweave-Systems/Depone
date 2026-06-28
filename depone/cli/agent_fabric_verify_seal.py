from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.seal import _self_test as seal_self_test
from depone.agent_fabric.seal import verify_capture_seal


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        seal_self_test()
        print("depone agent-fabric-verify-seal --self-test: pass")
        return

    capture_path = str(getattr(args, "capture", "") or "")
    seal_path = str(getattr(args, "seal", "") or "")
    key_path = str(getattr(args, "seal_key_file", "") or "")
    if not capture_path or not seal_path or not key_path:
        print(
            "Usage: depone agent-fabric-verify-seal --capture <capture.json> "
            "--seal <seal.json> --seal-key-file <key>",
            file=sys.stderr,
        )
        sys.exit(1)

    verified = False
    try:
        capture = json.loads(Path(capture_path).read_text(encoding="utf-8"))
        seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
        key = Path(key_path).read_bytes()
        verified = verify_capture_seal(capture, seal, key)
    except Exception:
        verified = False

    print(f"verified: {str(verified).lower()}")
    if not verified:
        sys.exit(1)
