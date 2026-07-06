#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "orro-engine-contract-v0.md"
MANIFEST = ROOT / "docs" / "orro-conformance" / "manifest.json"

REQUIRED_ARTIFACTS = [
    "repo-profile.json",
    "context-pack.json",
    "sealed-plan.json",
    "workflow-plan.json",
    "workflow-plan-binding.json",
    "role-lane-plan.json",
    "role-lane-plan-binding.json",
    "workflow-role-dispatch.json",
    "team-ledger.json",
    "team-ledger-verdict.json",
    "verification-recipe.json",
    "verification-receipt.json",
    "proofcheck-verdict.json",
    "orro-continuation-decision.json",
    "orro-auto-plan.json",
    "orro-auto-receipt.json",
    "orro-auto-session.json",
    "orro-report.json",
    "orro-handoff.json",
    "orro-engine-lock.json",
]

REQUIRED_TEXT = [
    "Depone verifies; witnessd executes; ORRO exposes the workflow.",
    "This is the verifier-authoritative contract",
    "Workflow plan is intent, not proof.",
    "Role-lane plan is executable intent, not proof.",
    "Role dispatch is context, not proof.",
    "Auto artifacts are orchestration metadata, not proof.",
    "Report is summary, not proof.",
    "Handoff is review package, not approval.",
    "Engine-lock is distribution metadata, not proof.",
    "Existing proofcheck verdict is not an input trust root.",
    "Verification recipe is intent.",
    "Verification receipt is execution evidence only if valid.",
    "MCP/tool output is observed fact, not trust root.",
    "Scout-only directories must not proofcheck-pass.",
    "Proofrun evidence must exist before proofcheck can pass.",
    "Handoff requires a passing bound `proofcheck-verdict.json`.",
    "Auto may not bypass proofcheck or handoff gates.",
    "Report may not upgrade status beyond observed artifacts.",
    "Superflow",
    "historical compatibility only",
]

REQUIRED_FIXTURES = {
    "valid-team-ledger-run": "positive",
    "scout-only": "negative",
    "workflow-plan-only": "negative",
    "wrapper-artifacts-only": "negative",
    "stale-proofcheck-verdict": "negative",
}


def _read_contract(errors: list[str]) -> str:
    if not CONTRACT.is_file():
        errors.append(f"missing contract doc: {CONTRACT.relative_to(ROOT)}")
        return ""
    return CONTRACT.read_text(encoding="utf-8")


def _read_manifest(errors: list[str]) -> dict:
    if not MANIFEST.is_file():
        errors.append(f"missing conformance manifest: {MANIFEST.relative_to(ROOT)}")
        return {}
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"manifest is not valid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("manifest root must be a JSON object")
        return {}
    return payload


def check() -> list[str]:
    errors: list[str] = []
    contract = _read_contract(errors)
    manifest = _read_manifest(errors)

    for artifact in REQUIRED_ARTIFACTS:
        if artifact not in contract:
            errors.append(f"contract missing artifact: {artifact}")

    for text in REQUIRED_TEXT:
        if text not in contract:
            errors.append(f"contract missing required text: {text}")

    if manifest:
        if manifest.get("kind") != "orro-conformance-manifest":
            errors.append("manifest kind must be orro-conformance-manifest")
        if manifest.get("schema_version") != "0.1":
            errors.append("manifest schema_version must be 0.1")

        fixtures = manifest.get("fixtures")
        if not isinstance(fixtures, list):
            errors.append("manifest fixtures must be a list")
        else:
            by_name = {
                item.get("name"): item
                for item in fixtures
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            for name, expected_class in REQUIRED_FIXTURES.items():
                fixture = by_name.get(name)
                if fixture is None:
                    errors.append(f"manifest missing fixture: {name}")
                    continue
                if fixture.get("class") != expected_class:
                    errors.append(
                        f"manifest fixture {name} class must be {expected_class}"
                    )
            if not any(item.get("class") == "positive" for item in by_name.values()):
                errors.append("manifest must include at least one positive fixture")
            if not any(item.get("class") == "negative" for item in by_name.values()):
                errors.append("manifest must include at least one negative fixture")

    return errors


def main() -> int:
    errors = check()
    if errors:
        for error in errors:
            print(f"check_orro_engine_contract: {error}", file=sys.stderr)
        return 1
    print("check_orro_engine_contract: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
