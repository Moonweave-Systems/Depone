from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    validate_statement_for_capture,
)


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    capture_path = Path(str(getattr(args, "capture_manifest", "")))
    if not str(capture_path):
        print("Error: --capture-manifest is required", file=sys.stderr)
        sys.exit(1)
    try:
        capture = _read_json(capture_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read capture manifest: {exc}", file=sys.stderr)
        sys.exit(1)

    runner_receipt = None
    runner_path = getattr(args, "runner_receipt", None)
    if runner_path:
        try:
            runner_receipt = _read_json(Path(str(runner_path)))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error: cannot read runner receipt: {exc}", file=sys.stderr)
            sys.exit(1)

    bundle = build_evidence_bundle(capture, runner_receipt=runner_receipt)
    errors = validate_statement_for_capture(bundle["statement"], capture)
    if errors:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "ERR_EVIDENCE_SUBSTRATE_INVALID",
                        "validation_errors": errors,
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    out_path = Path(str(getattr(args, "out", "evidence-substrate-bundle.json")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Evidence substrate bundle written to {out_path}")
    print(f"  Signing status: {bundle['signing_status']}")
    print(f"  Assurance: {bundle['assurance']}")


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _self_test() -> None:
    from depone.agent_fabric.evidence_substrate import _self_test as substrate_self_test

    substrate_self_test()
    print("depone agent-fabric-evidence-substrate --self-test: pass")
