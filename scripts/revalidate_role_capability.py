#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from depone.verify.adapters.generic import read_evidence
from depone.verify.evidence_contract import validate_evidence_contract


FIXTURE_ROOT = Path("depone/fixtures/role_capability")
CASES = {
    "write_scope_pass": ("PASS", []),
    "write_scope_fail": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION"],
    ),
    "tool_calls_pass": ("PASS", []),
    "tool_calls_fail_allow_outside_grant": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT"],
    ),
    "write_scope_fail_unsigned": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_SIGNATURE_MISSING"],
    ),
    "write_scope_fail_bad_signature": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_SIGNATURE_INVALID"],
    ),
    "write_scope_fail_no_trust_anchor": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING"],
    ),
}


def main() -> None:
    # The committed test key is a sibling of every fixture evidence directory,
    # matching the v108 harness pattern. Production loading separately enforces
    # this out-of-band boundary in the generic adapter.
    public_key = (FIXTURE_ROOT / "advisory-public-key.pem").resolve()
    for name, (expected_verdict, expected_codes) in CASES.items():
        evidence = read_evidence(str(FIXTURE_ROOT / name))
        if name != "write_scope_fail_no_trust_anchor":
            evidence.raw["trusted_observer_public_key_file"] = str(public_key)

        errors = validate_evidence_contract(evidence)
        actual_verdict = "REFUTE" if errors else "PASS"
        actual_codes = [error.code for error in errors]
        if actual_verdict != expected_verdict:
            raise AssertionError(
                f"{name}: expected verdict {expected_verdict!r}, "
                f"got {actual_verdict!r}: {errors}"
            )
        if actual_codes != expected_codes:
            raise AssertionError(
                f"{name}: expected codes {expected_codes!r}, "
                f"got {actual_codes!r}"
            )
        print(f"{name}: {actual_verdict} {actual_codes}")

    print("role capability fixtures: pass")


if __name__ == "__main__":
    main()
