#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from depone.verify.adapters.generic import read_evidence
from depone.verify.evidence_contract import validate_evidence_contract


FIXTURE_ROOT = ROOT / "depone/fixtures/role_capability"
CASES = {
    "write_scope_pass": (
        "REFUTE",
        ["ERR_EVIDENCE_CONTRACT_INVALID"],
    ),
    "write_scope_fail": (
        "REFUTE",
        ["ERR_EVIDENCE_CONTRACT_INVALID"],
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
    "write_scope_pass_bound_observation": ("PASS", []),
    "write_scope_fail_observation_unbound": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_OBSERVATION_UNBOUND"],
    ),
    "write_scope_fail_observation_tampered": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_OBSERVATION_DIGEST_MISMATCH"],
    ),
    "skill_routing_pass": ("PASS", []),
    "skill_routing_pass_bound_observation": ("PASS", []),
    "skill_routing_fail": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_SKILL_ROUTING_VIOLATION"],
    ),
    "skill_routing_fail_observation_unbound": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_OBSERVATION_UNBOUND"],
    ),
    "skill_routing_fail_observation_tampered": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_OBSERVATION_DIGEST_MISMATCH"],
    ),
    "skill_routing_fail_unsigned": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_SIGNATURE_MISSING"],
    ),
    "skill_routing_fail_bad_signature": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_SIGNATURE_INVALID"],
    ),
    "skill_routing_fail_no_trust_anchor": (
        "REFUTE",
        ["ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING"],
    ),
}


def main() -> None:
    # The committed test key is a sibling of every fixture evidence directory,
    # matching the v108 harness pattern. Production loading separately enforces
    # this out-of-band boundary in the generic adapter.
    for name, (expected_verdict, expected_codes) in CASES.items():
        evidence = read_evidence(str(FIXTURE_ROOT / name))
        if not name.endswith("_no_trust_anchor"):
            if name.startswith("skill_routing_"):
                public_key_name = "skill-routing-public-key.pem"
            elif "observation" in name:
                public_key_name = "observation-public-key.pem"
            else:
                public_key_name = "advisory-public-key.pem"
            public_key = (FIXTURE_ROOT / public_key_name).resolve()
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
                f"{name}: expected codes {expected_codes!r}, got {actual_codes!r}"
            )
        print(f"{name}: {actual_verdict} {actual_codes}")

    print("role capability fixtures: pass")


if __name__ == "__main__":
    main()
