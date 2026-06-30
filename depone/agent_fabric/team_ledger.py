"""Team Ledger v0 validation for Depone-observed agent teams.

The ledger is a small evidence model, not a scheduler. It records a leader
objective plus lane receipts from external team adapters or future Depone-native
lanes, then fails closed unless every lane is either verified with evidence or
explicitly blocked with a reason.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LEDGER_KIND = "depone-team-ledger"
SCHEMA_VERSION = "1.0"
ALLOWED_ENVIRONMENT_KINDS = {"local", "container", "cloud"}
ALLOWED_ADAPTER_KINDS = {
    "codex",
    "claude-code",
    "cursor",
    "depone-native",
    "github-copilot",
    "lazycodex",
    "omx",
    "opencode",
    "shell",
    "other",
}
ALLOWED_LANE_STATES = {"pass", "blocked"}


def load_team_ledger(path: Path) -> dict[str, Any]:
    """Load a Team Ledger JSON object from disk."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Team ledger JSON root must be an object: {path}")
    return value


def validate_team_ledger(ledger: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    """Validate a Team Ledger v0 object and return a pass/blocked verdict."""

    root = base_dir or Path.cwd()
    errors: list[str] = []
    warnings: list[str] = []
    lane_results: list[dict[str, Any]] = []

    _require_string(ledger, "kind", errors)
    if ledger.get("kind") != LEDGER_KIND:
        errors.append(f"kind must be {LEDGER_KIND!r}")
    _require_string(ledger, "schema_version", errors)
    if ledger.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    _require_string(ledger, "objective", errors)
    _require_string(ledger, "leader", errors)
    lanes = ledger.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("lanes must be a non-empty list")
        lanes = []

    for index, raw_lane in enumerate(lanes):
        if not isinstance(raw_lane, dict):
            errors.append(f"lanes[{index}] must be an object")
            continue
        lane_errors = _validate_lane(raw_lane, index, root)
        state = str(raw_lane.get("verification_state", ""))
        lane_result = {
            "lane_id": str(raw_lane.get("lane_id", f"lanes[{index}]")),
            "verification_state": state,
            "decision": "blocked" if lane_errors or state == "blocked" else "pass",
            "errors": lane_errors,
        }
        lane_results.append(lane_result)
        errors.extend(lane_errors)

    passed_lanes = sum(1 for lane in lane_results if lane["decision"] == "pass")
    blocked_lanes = sum(1 for lane in lane_results if lane["decision"] == "blocked")
    decision = "pass" if not errors and blocked_lanes == 0 and lane_results else "blocked"
    return {
        "kind": "depone-team-ledger-verdict",
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "lane_count": len(lane_results),
        "passed_lane_count": passed_lanes,
        "blocked_lane_count": blocked_lanes,
        "lane_results": lane_results,
        "errors": errors,
        "warnings": warnings,
    }


def _validate_lane(lane: dict[str, Any], index: int, base_dir: Path) -> list[str]:
    errors: list[str] = []
    prefix = f"lanes[{index}]"
    for field in (
        "lane_id",
        "environment_kind",
        "adapter_kind",
        "start_commit",
        "end_commit",
        "verification_state",
    ):
        _require_string(lane, field, errors, prefix=prefix)

    environment_kind = lane.get("environment_kind")
    if isinstance(environment_kind, str) and environment_kind not in ALLOWED_ENVIRONMENT_KINDS:
        errors.append(
            f"{prefix}.environment_kind must be one of "
            f"{sorted(ALLOWED_ENVIRONMENT_KINDS)}"
        )
    adapter_kind = lane.get("adapter_kind")
    if isinstance(adapter_kind, str) and adapter_kind not in ALLOWED_ADAPTER_KINDS:
        errors.append(
            f"{prefix}.adapter_kind must be one of {sorted(ALLOWED_ADAPTER_KINDS)}"
        )
    state = lane.get("verification_state")
    if isinstance(state, str) and state not in ALLOWED_LANE_STATES:
        errors.append(f"{prefix}.verification_state must be one of {sorted(ALLOWED_LANE_STATES)}")

    if state == "pass":
        evidence_dir = lane.get("evidence_dir")
        if not isinstance(evidence_dir, str) or not evidence_dir:
            errors.append(f"{prefix}.evidence_dir is required for pass lanes")
        else:
            evidence_path = Path(evidence_dir)
            if not evidence_path.is_absolute():
                evidence_path = base_dir / evidence_path
            if not evidence_path.is_dir():
                errors.append(f"{prefix}.evidence_dir must exist and be a directory: {evidence_dir}")
    elif state == "blocked":
        reason = lane.get("blocked_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}.blocked_reason is required for blocked lanes")

    pr_url = lane.get("pr_url")
    if pr_url is not None and not isinstance(pr_url, str):
        errors.append(f"{prefix}.pr_url must be a string when present")
    return errors


def _require_string(
    value: dict[str, Any],
    field: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    label = f"{prefix}.{field}" if prefix else field
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        errors.append(f"{label} is required")
