from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.seal import _self_test as seal_self_test
from depone.agent_fabric.seal import seal_capture


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        seal_self_test()
        return

    capture_path = str(getattr(args, "capture", "") or "")
    key_path = str(getattr(args, "seal_key_file", "") or "")
    key_id = str(getattr(args, "seal_key_id", "") or "")
    out_path = str(getattr(args, "out", "") or "")
    if not capture_path or not key_path or not key_id or not out_path:
        print(
            "Usage: depone agent-fabric-seal --capture <observer-capture.json> "
            "--seal-key-file <key> --seal-key-id <label> --out <seal.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        capture = json.loads(Path(capture_path).read_text(encoding="utf-8"))
        key = Path(key_path).read_bytes()
        seal = seal_capture(capture, key, key_id=key_id)
        out_abs = Path(out_path).expanduser().resolve(strict=False)
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        out_abs.write_text(
            f"{json.dumps(seal, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Observer capture seal written to {out_path}")
    print(f"  seal_value: {seal['value']}")
