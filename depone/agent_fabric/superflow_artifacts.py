"""Offline validators for Superflow planning and receipt artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash

SCHEMA_VERSION = "1.0"

VERIFICATION_RECIPE_KIND = "superflow-verification-recipe"
VERIFICATION_RECEIPT_KIND = "superflow-verification-receipt"
REPO_PROFILE_KIND = "superflow-repo-profile"
CONTEXT_PACK_KIND = "superflow-context-pack"
SKILLPACK_LOCK_KIND = "superflow-skillpack-lock"
MCP_TOOL_RECEIPT_KIND = "superflow-mcp-tool-receipt"
PR_HANDOFF_KIND = "superflow-pr-handoff"

PASS_DECISION = "pass"
BLOCKED_DECISION = "blocked"
REFUTED_DECISION = "refuted"


def build_superflow_artifact_verdict(
    artifacts: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a fail-closed verdict over persisted Superflow artifact objects."""

    errors = validate_superflow_artifacts(artifacts, base_dir=base_dir)
    decision = _decision_from_errors(errors)
    return {
        "kind": "superflow-artifact-verdict",
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "error_count": len(errors),
        "errors": errors,
        "artifact_hashes": {
            name: canonical_hash(value)
            for name, value in sorted(artifacts.items())
            if isinstance(value, (dict, list))
        },
        "boundary": {
            "executes_commands": False,
            "launches_agents": False,
            "calls_live_mcp": False,
            "calls_live_models": False,
            "mutates_worktree": False,
            "approves_merge": False,
            "raises_assurance": False,
        },
    }


def validate_superflow_artifacts(
    artifacts: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> list[dict[str, str]]:
    """Validate all known Superflow artifacts supplied by a runtime."""

    errors: list[dict[str, str]] = []
    recipe = _object_or_none(artifacts.get("verification_recipe"))
    receipt = _object_or_none(artifacts.get("verification_receipt"))
    repo_profile = _object_or_none(artifacts.get("repo_profile"))
    context_pack = _object_or_none(artifacts.get("context_pack"))
    skillpack_lock = _object_or_none(artifacts.get("skillpack_lock"))
    pr_handoff = _object_or_none(artifacts.get("pr_handoff"))
    mcp_receipts = _objects_list(artifacts.get("mcp_tool_receipts"))

    if recipe is not None:
        errors.extend(validate_verification_recipe(recipe))
    if receipt is not None:
        errors.extend(validate_verification_receipt(receipt, recipe=recipe))
    if repo_profile is not None:
        errors.extend(validate_repo_profile(repo_profile))
    if context_pack is not None:
        errors.extend(validate_context_pack(context_pack, repo_profile=repo_profile))
    if skillpack_lock is not None:
        errors.extend(validate_skillpack_lock(skillpack_lock, base_dir=base_dir))
    for index, mcp_receipt in enumerate(mcp_receipts):
        errors.extend(validate_mcp_tool_receipt(mcp_receipt, index=index))
    if pr_handoff is not None:
        errors.extend(
            validate_pr_handoff(
                pr_handoff,
                verification_receipt=receipt,
                mcp_tool_receipts=mcp_receipts,
            )
        )
    return errors


def validate_verification_recipe(recipe: dict[str, Any]) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(recipe, VERIFICATION_RECIPE_KIND)
    commands = recipe.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append(_error("ERR_SUPERFLOW_RECIPE_COMMANDS_INVALID", "commands must be a non-empty list"))
        return errors
    seen: set[str] = set()
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            errors.append(_error("ERR_SUPERFLOW_RECIPE_COMMAND_INVALID", f"commands[{index}] must be an object"))
            continue
        command_id = command.get("id")
        if not isinstance(command_id, str) or not command_id:
            errors.append(_error("ERR_SUPERFLOW_RECIPE_COMMAND_ID_INVALID", f"commands[{index}].id is required"))
        elif command_id in seen:
            errors.append(_error("ERR_SUPERFLOW_RECIPE_COMMAND_ID_DUPLICATE", f"duplicate command id: {command_id}"))
        else:
            seen.add(command_id)
        _validate_argv(command.get("argv"), f"commands[{index}].argv", errors)
        if not isinstance(command.get("expected_exit_code"), int):
            errors.append(
                _error(
                    "ERR_SUPERFLOW_RECIPE_EXPECTED_EXIT_CODE_INVALID",
                    f"commands[{index}].expected_exit_code must be an integer",
                )
            )
        if not isinstance(command.get("required"), bool):
            errors.append(_error("ERR_SUPERFLOW_RECIPE_REQUIRED_INVALID", f"commands[{index}].required must be boolean"))
    return errors


def validate_verification_receipt(
    receipt: dict[str, Any],
    *,
    recipe: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(receipt, VERIFICATION_RECEIPT_KIND)
    _validate_hex(receipt.get("runner_receipt_hash"), "runner_receipt_hash", errors)
    _validate_hex(receipt.get("transcript_sha256"), "transcript_sha256", errors)
    if receipt.get("raises_assurance") is not False:
        errors.append(_error("ERR_SUPERFLOW_RECEIPT_ASSURANCE_INVALID", "verification receipt must not raise assurance"))

    if recipe is not None:
        expected_recipe_hash = canonical_hash(recipe)
        if receipt.get("recipe_hash") != expected_recipe_hash:
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_RECIPE_HASH_MISMATCH", "recipe_hash must match recipe canonical hash"))
    else:
        _validate_hex(receipt.get("recipe_hash"), "recipe_hash", errors)

    command_results = receipt.get("command_results")
    if not isinstance(command_results, list) or not command_results:
        errors.append(_error("ERR_SUPERFLOW_RECEIPT_RESULTS_INVALID", "command_results must be a non-empty list"))
        return errors

    recipe_commands = _recipe_commands_by_id(recipe)
    seen: set[str] = set()
    for index, result in enumerate(command_results):
        if not isinstance(result, dict):
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_RESULT_INVALID", f"command_results[{index}] must be an object"))
            continue
        result_id = result.get("id")
        if not isinstance(result_id, str) or not result_id:
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_RESULT_ID_INVALID", f"command_results[{index}].id is required"))
            continue
        if result_id in seen:
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_RESULT_ID_DUPLICATE", f"duplicate result id: {result_id}"))
        seen.add(result_id)
        _validate_argv(result.get("argv"), f"command_results[{index}].argv", errors)
        if not isinstance(result.get("expected_exit_code"), int):
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_EXPECTED_EXIT_CODE_INVALID", f"{result_id}.expected_exit_code must be an integer"))
        if not isinstance(result.get("exit_code"), int):
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_EXIT_CODE_INVALID", f"{result_id}.exit_code must be an integer"))
        for field in ("stdout_sha256", "stderr_sha256"):
            _validate_hex(result.get(field), f"{result_id}.{field}", errors)
        required = result.get("required")
        if not isinstance(required, bool):
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_REQUIRED_INVALID", f"{result_id}.required must be boolean"))

        expected_exit = result.get("expected_exit_code")
        actual_exit = result.get("exit_code")
        if isinstance(expected_exit, int) and isinstance(actual_exit, int) and actual_exit != expected_exit:
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_EXIT_CODE_MISMATCH", f"{result_id} exit_code does not match expected_exit_code"))
        recipe_command = recipe_commands.get(result_id)
        if recipe_command is not None:
            if result.get("argv") != recipe_command.get("argv"):
                errors.append(_error("ERR_SUPERFLOW_RECEIPT_ARGV_MISMATCH", f"{result_id} argv must match recipe"))
            if result.get("expected_exit_code") != recipe_command.get("expected_exit_code"):
                errors.append(_error("ERR_SUPERFLOW_RECEIPT_EXPECTED_EXIT_CODE_MISMATCH", f"{result_id} expected_exit_code must match recipe"))
            if result.get("required") != recipe_command.get("required"):
                errors.append(_error("ERR_SUPERFLOW_RECEIPT_REQUIRED_MISMATCH", f"{result_id} required flag must match recipe"))

    for command_id, command in recipe_commands.items():
        if command.get("required") is True and command_id not in seen:
            errors.append(_error("ERR_SUPERFLOW_RECEIPT_REQUIRED_RESULT_MISSING", f"missing required command result: {command_id}"))
    return errors


def validate_repo_profile(profile: dict[str, Any]) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(profile, REPO_PROFILE_KIND)
    for field in ("repo_root", "branch", "head_commit"):
        _validate_non_empty_string(profile.get(field), field, errors)
    files = profile.get("files")
    if not isinstance(files, list) or not all(isinstance(item, str) and item for item in files):
        errors.append(_error("ERR_SUPERFLOW_REPO_PROFILE_FILES_INVALID", "files must be a list of non-empty strings"))
    return errors


def validate_context_pack(
    context_pack: dict[str, Any],
    *,
    repo_profile: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(context_pack, CONTEXT_PACK_KIND)
    selected_paths = context_pack.get("selected_paths")
    if not isinstance(selected_paths, list) or not all(isinstance(item, str) and item for item in selected_paths):
        errors.append(_error("ERR_SUPERFLOW_CONTEXT_PACK_PATHS_INVALID", "selected_paths must be a list of non-empty strings"))
    if repo_profile is not None:
        if context_pack.get("repo_profile_hash") != canonical_hash(repo_profile):
            errors.append(_error("ERR_SUPERFLOW_CONTEXT_PACK_REPO_PROFILE_HASH_MISMATCH", "repo_profile_hash must match repo profile"))
        profile_files = set(repo_profile.get("files") if isinstance(repo_profile.get("files"), list) else [])
        if isinstance(selected_paths, list):
            missing = [path for path in selected_paths if isinstance(path, str) and path not in profile_files]
            if missing:
                errors.append(_error("ERR_SUPERFLOW_CONTEXT_PACK_PATH_NOT_PROFILED", f"selected paths not in repo profile: {', '.join(missing)}"))
    else:
        _validate_hex(context_pack.get("repo_profile_hash"), "repo_profile_hash", errors)
    return errors


def validate_skillpack_lock(
    lock: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(lock, SKILLPACK_LOCK_KIND)
    entries = lock.get("entries")
    if not isinstance(entries, list):
        errors.append(_error("ERR_SUPERFLOW_SKILLPACK_LOCK_ENTRIES_INVALID", "entries must be a list"))
        return errors
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(_error("ERR_SUPERFLOW_SKILLPACK_LOCK_ENTRY_INVALID", f"entries[{index}] must be an object"))
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append(_error("ERR_SUPERFLOW_SKILLPACK_LOCK_PATH_INVALID", f"entries[{index}].path is required"))
            continue
        _validate_hex(entry.get("sha256"), f"entries[{index}].sha256", errors)
        if base_dir is not None:
            path = (base_dir / path_value).resolve(strict=False)
            try:
                expected = path.read_bytes()
            except OSError:
                errors.append(_error("ERR_SUPERFLOW_SKILLPACK_LOCK_FILE_MISSING", f"skillpack file is missing: {path_value}"))
                continue
            import hashlib

            actual_hash = hashlib.sha256(expected).hexdigest()
            if entry.get("sha256") != actual_hash:
                errors.append(_error("ERR_SUPERFLOW_SKILLPACK_LOCK_HASH_MISMATCH", f"sha256 mismatch for {path_value}"))
    return errors


def validate_mcp_tool_receipt(receipt: dict[str, Any], *, index: int = 0) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(receipt, MCP_TOOL_RECEIPT_KIND)
    prefix = f"mcp_tool_receipts[{index}]"
    for field in ("tool_name", "server_id", "captured_at"):
        _validate_non_empty_string(receipt.get(field), f"{prefix}.{field}", errors)
    for field in ("invocation_hash", "redacted_input_hash", "output_hash"):
        _validate_hex(receipt.get(field), f"{prefix}.{field}", errors)
    policy_flags = receipt.get("policy_flags")
    if not isinstance(policy_flags, dict):
        errors.append(_error("ERR_SUPERFLOW_MCP_RECEIPT_POLICY_FLAGS_INVALID", f"{prefix}.policy_flags must be an object"))
    elif policy_flags.get("raises_assurance") is not False:
        errors.append(_error("ERR_SUPERFLOW_MCP_RECEIPT_ASSURANCE_INVALID", f"{prefix} must not raise assurance"))
    if "invocation" in receipt and receipt.get("invocation_hash") != canonical_hash(receipt["invocation"]):
        errors.append(_error("ERR_SUPERFLOW_MCP_RECEIPT_INVOCATION_HASH_MISMATCH", f"{prefix}.invocation_hash must match invocation"))
    if "redacted_input" in receipt and receipt.get("redacted_input_hash") != canonical_hash(receipt["redacted_input"]):
        errors.append(_error("ERR_SUPERFLOW_MCP_RECEIPT_INPUT_HASH_MISMATCH", f"{prefix}.redacted_input_hash must match redacted_input"))
    if "observed_output" in receipt and receipt.get("output_hash") != canonical_hash(receipt["observed_output"]):
        errors.append(_error("ERR_SUPERFLOW_MCP_RECEIPT_OUTPUT_HASH_MISMATCH", f"{prefix}.output_hash must match observed_output"))
    return errors


def validate_pr_handoff(
    handoff: dict[str, Any],
    *,
    verification_receipt: dict[str, Any] | None = None,
    mcp_tool_receipts: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    errors = _validate_kind_and_version(handoff, PR_HANDOFF_KIND)
    for field in ("run_id", "evidence_dir"):
        _validate_non_empty_string(handoff.get(field), field, errors)
    for field in ("changed_files", "verification_receipt_hashes", "mcp_tool_receipt_hashes", "unresolved_risks", "human_required_actions"):
        values = handoff.get(field)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            errors.append(_error("ERR_SUPERFLOW_PR_HANDOFF_LIST_INVALID", f"{field} must be a list of strings"))
    if handoff.get("approves_merge") is not False:
        errors.append(_error("ERR_SUPERFLOW_PR_HANDOFF_APPROVAL_INVALID", "pr-handoff must not approve merge"))
    boundary = handoff.get("boundary")
    if not isinstance(boundary, dict) or boundary.get("raises_assurance") is not False:
        errors.append(_error("ERR_SUPERFLOW_PR_HANDOFF_BOUNDARY_INVALID", "pr-handoff boundary must not raise assurance"))
    if verification_receipt is not None:
        expected_hash = canonical_hash(verification_receipt)
        hashes = handoff.get("verification_receipt_hashes")
        if isinstance(hashes, list) and expected_hash not in hashes:
            errors.append(_error("ERR_SUPERFLOW_PR_HANDOFF_VERIFICATION_RECEIPT_HASH_MISSING", "pr-handoff must bind verification receipt hash"))
    for receipt in mcp_tool_receipts or []:
        expected_hash = canonical_hash(receipt)
        hashes = handoff.get("mcp_tool_receipt_hashes")
        if isinstance(hashes, list) and expected_hash not in hashes:
            errors.append(_error("ERR_SUPERFLOW_PR_HANDOFF_MCP_RECEIPT_HASH_MISSING", "pr-handoff must bind MCP/tool receipt hash"))
    return errors


def load_superflow_artifacts(evidence_dir: Path) -> dict[str, Any]:
    """Load known Superflow artifact filenames from an evidence directory."""

    mapping = {
        "repo_profile": "repo-profile.json",
        "context_pack": "context-pack.json",
        "skillpack_lock": "skillpack-lock.json",
        "verification_recipe": "verification-recipe.json",
        "verification_receipt": "verification-receipt.json",
        "pr_handoff": "pr-handoff.json",
    }
    artifacts: dict[str, Any] = {}
    for key, filename in mapping.items():
        path = evidence_dir / filename
        if path.is_file():
            artifacts[key] = _read_json_object(path)
    artifacts["mcp_tool_receipts"] = [
        _read_json_object(path)
        for path in sorted(evidence_dir.glob("mcp-tool-receipt-*.json"))
    ]
    return artifacts


def _validate_kind_and_version(artifact: dict[str, Any], kind: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(artifact, dict):
        return [_error("ERR_SUPERFLOW_ARTIFACT_INVALID", "artifact root must be an object")]
    if artifact.get("kind") != kind:
        errors.append(_error("ERR_SUPERFLOW_ARTIFACT_KIND_INVALID", f"kind must be {kind}"))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append(_error("ERR_SUPERFLOW_ARTIFACT_SCHEMA_INVALID", f"schema_version must be {SCHEMA_VERSION}"))
    return errors


def _validate_argv(value: object, field: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        errors.append(_error("ERR_SUPERFLOW_ARGV_INVALID", f"{field} must be a non-empty list of strings"))


def _validate_non_empty_string(value: object, field: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(_error("ERR_SUPERFLOW_STRING_INVALID", f"{field} must be a non-empty string"))


def _validate_hex(value: object, field: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        errors.append(_error("ERR_SUPERFLOW_HASH_INVALID", f"{field} must be a lowercase sha256 hex string"))


def _recipe_commands_by_id(recipe: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(recipe, dict) or not isinstance(recipe.get("commands"), list):
        return {}
    commands: dict[str, dict[str, Any]] = {}
    for command in recipe["commands"]:
        if isinstance(command, dict) and isinstance(command.get("id"), str):
            commands[command["id"]] = command
    return commands


def _object_or_none(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _objects_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _decision_from_errors(errors: list[dict[str, str]]) -> str:
    if not errors:
        return PASS_DECISION
    refuting_codes = {
        "ERR_SUPERFLOW_RECEIPT_EXIT_CODE_MISMATCH",
        "ERR_SUPERFLOW_RECEIPT_RECIPE_HASH_MISMATCH",
        "ERR_SUPERFLOW_MCP_RECEIPT_INVOCATION_HASH_MISMATCH",
        "ERR_SUPERFLOW_MCP_RECEIPT_INPUT_HASH_MISMATCH",
        "ERR_SUPERFLOW_MCP_RECEIPT_OUTPUT_HASH_MISMATCH",
        "ERR_SUPERFLOW_SKILLPACK_LOCK_HASH_MISMATCH",
        "ERR_SUPERFLOW_CONTEXT_PACK_REPO_PROFILE_HASH_MISMATCH",
    }
    if any(error.get("code") in refuting_codes for error in errors):
        return REFUTED_DECISION
    return BLOCKED_DECISION


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}
