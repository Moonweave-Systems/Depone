#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from depone.verify.adapters.generic import read_evidence
from depone.verify.evidence_contract import validate_advisory_provenance


FIXTURE_ROOT = Path("depone/fixtures/advisory")
CASES = (
    "sketch_pass",
    "sketch_fail_chosen_not_in_candidates",
    "trace_confirmed_backed_pass",
    "trace_confirmed_unbacked_fail",
    "trace_unrelated_red_fail",
)


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    public_key = (FIXTURE_ROOT / "advisory-public-key.pem").resolve()
    for name in CASES:
        case_root = FIXTURE_ROOT / name
        evidence = read_evidence(str(case_root))
        evidence.raw["trusted_observer_public_key_file"] = str(public_key)
        contract = _read_object(case_root / "evidence-contract.json")
        expected = _read_object(case_root / "expected-verdict.json")

        errors = validate_advisory_provenance(evidence, contract)
        actual_verdict = "REFUTE" if errors else "PASS"
        actual_codes = [error.code for error in errors]
        if actual_verdict != expected.get("verdict"):
            raise AssertionError(
                f"{name}: expected verdict {expected.get('verdict')!r}, "
                f"got {actual_verdict!r}: {errors}"
            )
        if actual_codes != expected.get("error_codes"):
            raise AssertionError(
                f"{name}: expected codes {expected.get('error_codes')!r}, "
                f"got {actual_codes!r}"
            )
        print(f"{name}: {actual_verdict} {actual_codes}")

    print("v108 advisory provenance fixtures: pass")


if __name__ == "__main__":
    main()
