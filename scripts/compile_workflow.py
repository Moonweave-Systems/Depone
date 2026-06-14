#!/usr/bin/env python3
"""Compile a V0.5 workflow plan into a deterministic V1 first-slice packet."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from evaluate_plan import EvaluationError, validate_plan  # noqa: E402


TOOL = "compile_workflow.py"
SCHEMA_VERSION = "1.0"
COMPILER_VERSION = "1.0.0"
OUT_ROOT = ROOT / "out" / "v1"
PACKET_ID = "001-first-slice"
SENTINEL = ".compile_workflow-owned.json"
PROMPT_HEADINGS = [
    "# Packet 001-first-slice",
    "## Objective",
    "## Inputs",
    "## Ownership",
    "## Allowed Tools",
    "## Forbidden Actions",
    "## Risk Gates",
    "## Required Output",
    "## Verification",
    "## Handoff Context",
    "## Stop Conditions",
]
RISK_CATEGORIES = [
    "write",
    "shell-process",
    "network",
    "dependency-install",
    "database-migration",
    "production-deploy",
    "public-api-change",
    "external-message",
    "paid-api",
    "secret-access",
    "history-rewrite",
    "delete",
]
RISK_ALIASES = {
    "write": ["write", "write-action", "source-edits"],
    "shell-process": ["shell-process", "shell", "shell-action", "process-execution"],
    "network": ["network", "network-action", "external-network-calls"],
    "dependency-install": [
        "dependency-install",
        "dependency-installs",
        "dependency-change",
        "dependency-changes",
    ],
    "database-migration": ["database-migration", "database-migrations"],
    "production-deploy": ["production-deploy", "production-deploys"],
    "public-api-change": ["public-api-change", "public-api-changes"],
    "external-message": ["external-message", "external-message-action", "external-messages"],
    "paid-api": ["paid-api", "paid-external-api-use"],
    "secret-access": ["secret-access", "secret"],
    "history-rewrite": ["history-rewrite", "force-push", "hard-reset"],
    "delete": ["delete", "deletion"],
}
RISK_SAFE_DEFAULTS = {
    "write": "stop before writing and ask for approval",
    "shell-process": "stop before shell use and ask for approval",
    "network": "stop before network use and ask for approval",
    "dependency-install": "stop before dependency installs and ask for approval",
    "database-migration": "stop before database migration and ask for approval",
    "production-deploy": "stop before production deploy and ask for approval",
    "public-api-change": "stop before public API change and ask for approval",
    "external-message": "stop before sending external messages and ask for approval",
    "paid-api": "stop before paid API use and ask for approval",
    "secret-access": "stop before secret access and ask for approval",
    "history-rewrite": "stop before history rewrite and ask for approval",
    "delete": "stop before deletion and ask for approval",
}
RESUME_CODES = {
    "plan": "ERR_RESUME_STALE_PLAN",
    "packet": "ERR_RESUME_STALE_PACKET",
    "prompt": "ERR_RESUME_STALE_PROMPT",
    "input": "ERR_RESUME_STALE_INPUT",
    "handoff": "ERR_RESUME_STALE_HANDOFF",
    "gate": "ERR_RESUME_STALE_GATE",
    "compiler": "ERR_RESUME_STALE_COMPILER",
    "missing": "ERR_RESUME_MISSING_ARTIFACT",
}
DIGEST_FIELDS = [
    "packet_id",
    "source_plan_id",
    "source_first_slice",
    "objective",
    "surface_refs",
    "phase_context",
    "worker_refs",
    "allowed_tools",
    "forbidden_actions",
    "risk_gate_refs",
    "handoff_refs",
    "verification",
    "completion_check",
    "input_snapshot_hash",
    "prompt_contract",
]


class CompileError(ValueError):
    """Structured V1 compiler failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: Path | str | None = None,
        fixture_id: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.path = str(path) if path is not None else None
        self.fixture_id = fixture_id

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.path is not None:
            record["path"] = self.path
        if self.fixture_id is not None:
            record["fixture_id"] = self.fixture_id
        return record


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_text(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json_text(data).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha8(data: Any) -> str:
    return canonical_hash(data)[:8]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CompileError("ERR_PLAN_INVALID", f"cannot read JSON: {exc}", path=path) from exc
    if not isinstance(data, dict):
        raise CompileError("ERR_PLAN_INVALID", "JSON root must be an object", path=path)
    return data


def normalize_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("_", " ").replace("-", " "))


def contains_token_sequence(text: str, needle: str) -> bool:
    haystack = normalize_tokens(text)
    tokens = normalize_tokens(needle)
    if not tokens:
        return False
    return any(haystack[index:index + len(tokens)] == tokens for index in range(len(haystack) - len(tokens) + 1))


def category_from_text(text: str) -> str | None:
    matches = [
        category
        for category in RISK_CATEGORIES
        if any(contains_token_sequence(text, alias) for alias in RISK_ALIASES[category])
    ]
    if not matches:
        return None
    return matches[0]


def check_path_components_not_symlink(path: Path) -> None:
    absolute = path if path.is_absolute() else ROOT / path
    current = Path(absolute.anchor) if absolute.is_absolute() else Path(".")
    for part in absolute.parts[1:] if absolute.is_absolute() else absolute.parts:
        current = current / part
        try:
            if current.is_symlink():
                raise CompileError("ERR_OUT_PATH_SYMLINK", "output path contains a symlink", path=current)
        except OSError as exc:
            raise CompileError("ERR_OUT_PATH_UNSAFE", f"cannot inspect output path: {exc}", path=current) from exc


def resolve_v1_out(value: str | Path) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else ROOT / raw
    resolved = candidate.resolve(strict=False)
    out_root = OUT_ROOT.resolve(strict=False)
    forbidden = {ROOT.resolve(), (ROOT / "out").resolve(strict=False), out_root}
    if resolved in forbidden:
        raise CompileError("ERR_OUT_PATH_UNSAFE", "output path must name a run directory under out/v1", path=value)
    try:
        resolved.relative_to(out_root)
    except ValueError as exc:
        raise CompileError("ERR_OUT_PATH_UNSAFE", "output path must resolve under repo-local out/v1", path=value) from exc
    if resolved == Path(".").resolve():
        raise CompileError("ERR_OUT_PATH_UNSAFE", "output path cannot be current directory", path=value)
    check_path_components_not_symlink(candidate)
    return resolved


def sentinel_matches(path: Path, run_id: str, mode: str) -> bool:
    sentinel = path / SENTINEL
    if not sentinel.is_file() or sentinel.is_symlink():
        return False
    try:
        data = json.loads(sentinel.read_text())
    except json.JSONDecodeError:
        return False
    return (
        data.get("tool") == TOOL
        and data.get("schema_version") == SCHEMA_VERSION
        and data.get("run_id") == run_id
        and data.get("mode") == mode
    )


def prepare_owned_dir(path: Path, run_id: str, mode: str, *, clear: bool) -> None:
    path = resolve_v1_out(path)
    if path.exists():
        if path.is_symlink():
            raise CompileError("ERR_OUT_PATH_SYMLINK", "run directory is a symlink", path=path)
        if not path.is_dir():
            raise CompileError("ERR_OUT_PATH_UNSAFE", "output path exists and is not a directory", path=path)
        if not sentinel_matches(path, run_id, mode):
            raise CompileError("ERR_OUT_PATH_NOT_OWNED", "existing run directory is not compiler-owned", path=path)
        if clear:
            shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        path / SENTINEL,
        {
            "tool": TOOL,
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "mode": mode,
            "created_at": now_utc(),
        },
    )


def ensure_safe_leaf(path: Path) -> None:
    if path.exists():
        if path.is_symlink():
            raise CompileError("ERR_OUT_PATH_SYMLINK", "refusing to overwrite symlinked file", path=path)
        if not path.is_file():
            raise CompileError("ERR_OUT_PATH_UNSAFE", "refusing to overwrite non-file leaf", path=path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_safe_leaf(path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, canonical_json_text(data))


def load_plan(plan_path: Path) -> tuple[dict[str, Any], str]:
    plan = read_json(plan_path)
    try:
        validate_plan(plan)
    except EvaluationError as exc:
        message = str(exc)
        if "first_slice.inputs must be unique" not in message and "missing risk gate for " not in message:
            raise CompileError("ERR_PLAN_INVALID", str(exc), path=plan_path) from exc
        validation_plan = copy.deepcopy(plan)
        if "first_slice.inputs must be unique" in message:
            inputs = validation_plan["execution_path"]["first_slice"]["inputs"]
            validation_plan["execution_path"]["first_slice"]["inputs"] = ordered_unique(inputs)
        risk_match = re.search(r"missing risk gate for ([a-z ]+)", message)
        if risk_match:
            term = risk_match.group(1)
            validation_plan["risk_gates"].append(
                {
                    "trigger": term,
                    "safe_default": f"stop before {term} use and ask for approval",
                    "requires_user_approval": True,
                }
            )
        try:
            validate_plan(validation_plan)
        except EvaluationError as retry_exc:
            raise CompileError("ERR_PLAN_INVALID", str(retry_exc), path=plan_path) from retry_exc
    if plan["activation"]["decision"] != "activate":
        raise CompileError("ERR_PLAN_DOWNGRADE", "V1 accepts only activated workflow plans", path=plan_path)
    return plan, canonical_hash(plan)


def ordered_unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = canonical_json_text(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def source_handoff_id(index: int, handoff: dict[str, Any]) -> str:
    return f"handoff-{index:04d}-{sha8(handoff)}"


def source_gate_id(index: int, gate: dict[str, Any]) -> str:
    return f"gate-{index:04d}-{sha8(gate)}"


def detect_risks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []

    def add(category: str | None, source_field: str, source_id: str, token: str) -> None:
        if category:
            detections.append(
                {
                    "risk_category": category,
                    "source_field": source_field,
                    "source_id": source_id,
                    "normalized_token": " ".join(normalize_tokens(token)),
                }
            )

    for surface in plan["surfaces"]:
        if surface["access_mode"] != "read-only":
            add("write", "surfaces.access_mode", surface["id"], surface["access_mode"])
    for worker in plan["workers"]:
        permissions = worker["tool_permissions"]
        if permissions["write"]:
            add("write", "workers.tool_permissions.write", worker["id"], "write")
        if permissions["shell"]:
            add("shell-process", "workers.tool_permissions.shell", worker["id"], "shell")
        if permissions["network"]:
            add("network", "workers.tool_permissions.network", worker["id"], "network")
        if permissions["mcp_connectors"]:
            add("external-message", "workers.tool_permissions.mcp_connectors", worker["id"], "external message")
    for index, gate in enumerate(plan["risk_gates"]):
        add(category_from_text(gate["trigger"]), "risk_gates.trigger", str(index), gate["trigger"])
    first_slice = plan["execution_path"]["first_slice"]
    for field in ["instruction", "expected_output", "completion_check"]:
        add(category_from_text(first_slice[field]), f"execution_path.first_slice.{field}", plan["plan_id"], first_slice[field])
    for index, action in enumerate(first_slice["forbidden_actions"]):
        add(category_from_text(action), "execution_path.first_slice.forbidden_actions", str(index), action)

    unique: dict[str, dict[str, Any]] = {}
    for detection in detections:
        key = canonical_json_text(detection)
        unique[key] = detection
    return sorted(unique.values(), key=lambda item: (item["risk_category"], item["source_field"], item["source_id"], item["normalized_token"]))


def source_gate_matches_category(gate: dict[str, Any], category: str) -> bool:
    return any(contains_token_sequence(gate["trigger"], alias) for alias in RISK_ALIASES[category])


def build_gates(plan: dict[str, Any], plan_hash: str, run_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detections = detect_risks(plan)
    detected_categories = {item["risk_category"] for item in detections}
    gates: list[dict[str, Any]] = []
    matched_categories: set[str] = set()
    for index, source_gate in enumerate(plan["risk_gates"]):
        category = category_from_text(source_gate["trigger"])
        if category and category in detected_categories:
            matched_categories.add(category)
        gates.append(
            {
                "gate_id": source_gate_id(index, source_gate),
                "trigger": source_gate["trigger"],
                "risk_category": category,
                "source": "plan",
                "source_index": index,
                "safe_default": source_gate["safe_default"],
                "requires_user_approval": source_gate["requires_user_approval"],
                "status": "blocked" if category in detected_categories else "not-required",
                "approved": False,
                "approval_source": None,
            }
        )
    for category in sorted(detected_categories - matched_categories):
        detection = next(item for item in detections if item["risk_category"] == category)
        gates.append(
            {
                "gate_id": f"gate-synthetic-{category}-{sha8(detection)}",
                "trigger": f"{category} detected by V1 compiler",
                "risk_category": category,
                "source": "compiler-synthetic",
                "source_index": None,
                "safe_default": RISK_SAFE_DEFAULTS[category],
                "requires_user_approval": True,
                "status": "blocked",
                "approved": False,
                "approval_source": None,
            }
        )
    approval_state = {"run_id": run_id, "plan_hash": plan_hash, "risk_policy": "block-all", "gates": gates}
    return gates, [approval_state]


def build_handoff_schemas(plan: dict[str, Any]) -> list[dict[str, Any]]:
    schemas = []
    for index, handoff in enumerate(plan["handoffs"]):
        schemas.append(
            {
                "schema_version": SCHEMA_VERSION,
                "handoff_id": source_handoff_id(index, handoff),
                "source_index": index,
                "from_phase": handoff["from_phase"],
                "to_phase": handoff["to_phase"],
                "artifact": handoff["artifact"],
                "artifact_schema": handoff["artifact_schema"],
            }
        )
    return schemas


def build_phase_context(plan: dict[str, Any], handoff_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phases = []
    for phase in plan["phases"]:
        phase_id = phase["id"]
        phases.append(
            {
                "phase_id": phase_id,
                "depends_on": phase["depends_on"],
                "worker_ids": phase["worker_ids"],
                "handoffs_in": [item["handoff_id"] for item in handoff_schemas if item["to_phase"] == phase_id],
                "handoffs_out": [item["handoff_id"] for item in handoff_schemas if item["from_phase"] == phase_id],
                "context_only": True,
            }
        )
    return phases


def build_worker_refs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "worker_id": worker["id"],
            "role": worker["role"],
            "ownership": worker["ownership"],
            "tool_permissions": worker["tool_permissions"],
            "forbidden_actions": worker["forbidden_actions"],
            "context_budget": worker["context_budget"],
            "prompt_contract": worker["prompt_contract"],
            "context_only": True,
        }
        for worker in plan["workers"]
    ]


def build_allowed_tools(plan: dict[str, Any]) -> dict[str, Any]:
    allowed = {"read": False, "write": False, "shell": False, "network": False, "mcp_connectors": [], "requires_escalation_for": []}
    connectors: set[str] = set()
    escalations: set[str] = set()
    for worker in plan["workers"]:
        permissions = worker["tool_permissions"]
        for key in ["read", "write", "shell", "network"]:
            allowed[key] = bool(allowed[key] or permissions[key])
        connectors.update(map(str, permissions["mcp_connectors"]))
        escalations.update(map(str, permissions["requires_escalation_for"]))
    allowed["mcp_connectors"] = sorted(connectors)
    allowed["requires_escalation_for"] = sorted(escalations)
    return allowed


def classify_input(label: str) -> str:
    stripped = label.strip()
    if stripped.startswith("path:"):
        return "path"
    if stripped.startswith("glob:"):
        return "glob"
    if re.match(r"https?://", stripped):
        return "url"
    return "literal"


def path_hash(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() and not path.is_symlink() else None


def snapshot_input(label: str, index: int, plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    kind = classify_input(label)
    normalized = label.strip()
    entries: list[dict[str, Any]]
    exists = False
    if label == "workflow.plan.json":
        kind = "path"
        target = plan_path.resolve()
        normalized = rel(target)
        exists = target.is_file()
        entries = [{"path": normalized, "exists": exists, "sha256": path_hash(target)}]
    elif label == "blueprint.md" and (plan_path.parent / "blueprint.md").exists():
        kind = "path"
        target = (plan_path.parent / "blueprint.md").resolve()
        normalized = rel(target) if target.is_relative_to(ROOT) else str(target)
        exists = target.exists()
        entries = [{"path": normalized, "exists": exists, "sha256": path_hash(target)}]
    elif label == "original prompt":
        kind = "literal"
        normalized = plan["source_prompt"]
        exists = True
        entries = [{"value": normalized, "sha256": sha256_text(normalized)}]
    elif label == "repository path":
        kind = "path"
        target = ROOT.resolve()
        normalized = rel(target)
        exists = True
        entries = [{"path": normalized, "exists": True, "sha256": None}]
    elif kind == "path":
        target = Path(label.removeprefix("path:").strip())
        target = target if target.is_absolute() else plan_path.parent / target
        normalized = rel(target.resolve()) if target.resolve(strict=False).is_relative_to(ROOT) else str(target.resolve(strict=False))
        exists = target.exists()
        entries = [{"path": normalized, "exists": exists, "sha256": path_hash(target)}]
    elif kind == "glob":
        pattern = label.removeprefix("glob:").strip()
        matches = sorted(plan_path.parent.glob(pattern))
        entries = []
        for match in matches:
            resolved = match.resolve(strict=False)
            entry_path = rel(resolved) if resolved.is_relative_to(ROOT) else str(resolved)
            entries.append({"path": entry_path, "exists": match.exists(), "sha256": path_hash(match)})
        exists = bool(entries)
        normalized = pattern
    else:
        exists = kind in {"literal", "url"}
        entries = [{"value": normalized, "sha256": sha256_text(normalized)}]
    record = {
        "source_index": index,
        "input_label": label,
        "input_kind": kind,
        "normalized_value": normalized,
        "exists_at_compile_time": exists,
        "snapshot_entries": entries,
    }
    input_id = f"input-{index:04d}-{sha8(record)}"
    return {"input_id": input_id, **record, "hash": canonical_hash(record)}


def input_snapshot_hash(input_snapshots: list[dict[str, Any]]) -> str:
    return canonical_hash(sorted(input_snapshots, key=lambda item: item["input_id"]))


def build_packet(
    plan: dict[str, Any],
    plan_path: Path,
    handoff_schemas: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    prompt_hash: str,
) -> dict[str, Any]:
    first_slice = plan["execution_path"]["first_slice"]
    input_snapshots = [snapshot_input(label, index, plan, plan_path) for index, label in enumerate(first_slice["inputs"])]
    blocked_gate_triggers = [gate["trigger"] for gate in gates if gate["status"] == "blocked"]
    forbidden = ordered_unique(first_slice["forbidden_actions"] + [item for worker in plan["workers"] for item in worker["forbidden_actions"]])
    phase_context = build_phase_context(plan, handoff_schemas)
    worker_refs = build_worker_refs(plan)
    packet = {
        "packet_id": PACKET_ID,
        "source_plan_id": plan["plan_id"],
        "source_first_slice": first_slice,
        "objective": plan["objective"],
        "surface_refs": [
            {
                "surface_id": surface["id"],
                "kind": surface["kind"],
                "locator": surface["locator"],
                "access_mode": surface["access_mode"],
            }
            for surface in plan["surfaces"]
        ],
        "phase_context": phase_context,
        "worker_refs": worker_refs,
        "allowed_tools": build_allowed_tools(plan),
        "forbidden_actions": forbidden,
        "risk_gate_refs": [gate["gate_id"] for gate in gates],
        "handoff_refs": [{"handoff_id": item["handoff_id"], "context_only": True} for item in handoff_schemas],
        "verification": plan["verification"],
        "completion_check": first_slice["completion_check"],
        "input_snapshots": input_snapshots,
        "input_snapshot_hash": input_snapshot_hash(input_snapshots),
        "prompt_contract": {
            "inputs": first_slice["inputs"],
            "required_output_schema": first_slice["expected_output"],
            "stop_conditions": ordered_unique(first_slice["forbidden_actions"] + blocked_gate_triggers),
        },
        "prompt_path": "packets/001-first-slice.prompt.md",
        "prompt_hash": prompt_hash,
    }
    return packet


def packet_digest(packet: dict[str, Any]) -> dict[str, Any]:
    return {field: packet[field] for field in DIGEST_FIELDS}


def render_prompt(packet: dict[str, Any], gates: list[dict[str, Any]]) -> str:
    digest = packet_digest(packet)
    lines = [
        "# Packet 001-first-slice",
        "",
        "Prompt SHA-256: {{PROMPT_SHA256}}",
        f"Source plan: {packet['source_plan_id']}",
        "",
        "## Objective",
        packet["objective"],
        "",
        "## Inputs",
    ]
    for item in packet["input_snapshots"]:
        lines.append(f"- `{item['input_id']}` {item['input_label']} ({item['input_kind']}): {item['normalized_value']}")
    lines.extend(["", "## Ownership"])
    for worker in packet["worker_refs"]:
        lines.append(f"- `{worker['worker_id']}`: {worker['role']}; ownership: {', '.join(worker['ownership'])}")
    lines.extend(["", "## Allowed Tools", f"```json\n{canonical_json_text(packet['allowed_tools'])}\n```", "", "## Forbidden Actions"])
    for action in packet["forbidden_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Risk Gates"])
    for gate in gates:
        lines.append(f"- `{gate['gate_id']}` [{gate['status']}]: {gate['trigger']}")
    lines.extend(["", "## Required Output", packet["prompt_contract"]["required_output_schema"], "", "## Verification"])
    for item in packet["verification"]:
        lines.append(f"- {item['claim_or_output']}: {item['falsifier']}")
    lines.extend(
        [
            "",
            "## Handoff Context",
            "```packet_contract_digest",
            canonical_json_text(digest),
            "```",
            "",
            "## Stop Conditions",
        ]
    )
    for condition in packet["prompt_contract"]["stop_conditions"]:
        lines.append(f"- {condition}")
    lines.append(f"- Completion check: {packet['completion_check']}")
    return "\n".join(lines) + "\n"


def parse_prompt_digest(prompt: str) -> dict[str, Any]:
    match = re.search(r"```packet_contract_digest\n(?P<body>.*?)\n```", prompt, re.DOTALL)
    if not match:
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt is missing packet_contract_digest block")
    try:
        data = json.loads(match.group("body"))
    except json.JSONDecodeError as exc:
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", f"prompt digest is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt digest must be an object")
    return data


def verify_prompt_packet(prompt: str, packet: dict[str, Any]) -> None:
    for heading in PROMPT_HEADINGS:
        if heading not in prompt:
            raise CompileError("ERR_PROMPT_PACKET_DRIFT", f"prompt missing heading: {heading}")
    digest = parse_prompt_digest(prompt)
    expected = packet_digest(packet)
    if canonical_json_text(digest) != canonical_json_text(expected):
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt digest does not match packet JSON")
    for gate_id in packet["risk_gate_refs"]:
        if f"`{gate_id}`" not in prompt:
            raise CompileError("ERR_PROMPT_PACKET_DRIFT", f"prompt missing gate ID: {gate_id}")
    if packet["packet_id"] not in prompt or packet["source_plan_id"] not in prompt:
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt missing packet or source plan ID")
    objective = section_body(prompt, "## Objective", "## Inputs")
    if objective != packet["objective"]:
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt objective section does not match packet JSON")
    required_output = section_body(prompt, "## Required Output", "## Verification")
    if required_output != packet["prompt_contract"]["required_output_schema"]:
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt required output section does not match packet JSON")
    if f"Completion check: {packet['completion_check']}" not in section_body(prompt, "## Stop Conditions", ""):
        raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt completion check does not match packet JSON")


def section_body(prompt: str, start: str, end: str) -> str:
    if start not in prompt:
        return ""
    after = prompt.split(start, 1)[1]
    if end and end in after:
        after = after.split(end, 1)[0]
    return after.strip()


def gate_snapshot_hash(gates: list[dict[str, Any]]) -> str:
    return canonical_hash([{"gate_id": gate["gate_id"], "approval_hash": canonical_hash(gate)} for gate in gates])


def build_status(
    run_id: str,
    plan_hash: str,
    source_plan_hash: str,
    packet: dict[str, Any],
    handoff_schemas: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    approval_state: dict[str, Any],
    *,
    resume_state: str = "fresh",
    invalidators: list[dict[str, Any]] | None = None,
    checked_at: str | None = None,
    resume_result: str | None = None,
) -> dict[str, Any]:
    packet_hash = canonical_hash(packet)
    packet_status = "blocked-risk-gate" if any(gate["status"] == "blocked" for gate in gates) else "ready"
    if invalidators:
        packet_status = "invalidated"
    gate_hashes = {gate["gate_id"]: canonical_hash(gate) for gate in gates}
    return {
        "run_id": run_id,
        "plan_hash": plan_hash,
        "source_plan_hash": source_plan_hash,
        "resume_state": resume_state,
        "packet_statuses": [
            {
                "packet_id": PACKET_ID,
                "status": packet_status,
                "reason": "blocked by V1 risk gates" if packet_status == "blocked-risk-gate" else ("resume invalidated" if invalidators else "not blocked by V1 checks"),
                "packet_hash": packet_hash,
                "prompt_hash": packet["prompt_hash"],
                "input_snapshot_hash": packet["input_snapshot_hash"],
                "gate_snapshot_hash": gate_snapshot_hash(gates),
            }
        ],
        "handoff_statuses": [
            {"handoff_id": item["handoff_id"], "schema_hash": canonical_hash(item), "source_index": item["source_index"]}
            for item in handoff_schemas
        ],
        "gate_statuses": [
            {
                "gate_id": gate["gate_id"],
                "trigger": gate["trigger"],
                "status": "invalidated" if invalidators else gate["status"],
                "approval_hash": gate_hashes[gate["gate_id"]],
                "source": gate["source"],
                "source_index": gate["source_index"],
                "risk_category": gate["risk_category"],
            }
            for gate in gates
        ],
        "snapshots": {
            "plan_hash": plan_hash,
            "packet_hashes": {PACKET_ID: packet_hash},
            "prompt_hashes": {packet["prompt_path"]: packet["prompt_hash"]},
            "input_snapshot_hashes": {PACKET_ID: packet["input_snapshot_hash"]},
            "handoff_schema_hashes": {item["handoff_id"]: canonical_hash(item) for item in handoff_schemas},
            "approval_state_hash": canonical_hash(approval_state),
            "gate_approval_hashes": gate_hashes,
            "compiler_version": COMPILER_VERSION,
        },
        "invalidators": invalidators or [],
        "last_resume_checked_at": checked_at,
        "last_resume_result": resume_result,
    }


def render_readme(status: dict[str, Any], gates: list[dict[str, Any]]) -> str:
    packet_status = status["packet_statuses"][0]["status"]
    blocked = [gate for gate in gates if gate["status"] == "blocked"]
    lines = [
        "# V1 First-Slice Run",
        "",
        "Read `packets/001-first-slice.prompt.md` first.",
        "",
        "V1 compiled this packet only; it did not execute the workflow, spawn agents, run commands, or mark work complete.",
        "",
        f"Packet status: `{packet_status}`.",
        "",
        "## Blocked Gates",
    ]
    if blocked:
        lines.extend(f"- `{gate['gate_id']}`: {gate['trigger']}" for gate in blocked)
        lines.extend(
            [
                "",
                "V1 has no machine approval path for blocked packets. Return to the user or wait for V2 tooling before treating this packet as actionable.",
            ]
        )
    else:
        lines.append("- none")
        lines.extend(["", "Allowed next manual action: inspect the packet prompt and decide whether to execute it outside V1."])
    return "\n".join(lines) + "\n"


def render_resume(status: dict[str, Any], packet: dict[str, Any] | None = None) -> str:
    lines = [
        "# V1 Resume Check",
        "",
        f"Run ID: `{status['run_id']}`",
        f"State: `{status['resume_state']}`",
        f"Last result: `{status['last_resume_result']}`",
        "",
        "V1 only checks whether compiled first-slice files are still trustworthy. It does not resume completed work.",
        "",
        "## Invalidators",
    ]
    if status["invalidators"]:
        for item in status["invalidators"]:
            lines.append(f"- `{item['code']}` {item['kind']} `{item['id']}`: {item['message']}")
    else:
        lines.append("- none")
    if packet:
        directory_inputs = [
            item["input_id"]
            for item in packet["input_snapshots"]
            if any(entry.get("exists") and entry.get("sha256") is None and "path" in entry for entry in item["snapshot_entries"])
        ]
        if directory_inputs:
            lines.extend(["", "## Directory Inputs", "Directories are recorded but not recursively hashed in V1."])
            lines.extend(f"- `{input_id}`" for input_id in directory_inputs)
    return "\n".join(lines) + "\n"


def compile_plan(plan_path: Path, out_dir: Path, *, run_id: str | None = None, mode: str = "compile") -> dict[str, Any]:
    run_id = run_id or out_dir.name
    out_dir = resolve_v1_out(out_dir)
    prepare_owned_dir(out_dir, run_id, mode, clear=True)
    plan, source_plan_hash = load_plan(plan_path)
    plan_hash = canonical_hash(plan)
    handoff_schemas = build_handoff_schemas(plan)
    gates, approval_wrappers = build_gates(plan, plan_hash, run_id)
    approval_state = approval_wrappers[0]
    prompt_hash_placeholder = "0" * 64
    packet = build_packet(plan, plan_path.resolve(), handoff_schemas, gates, prompt_hash_placeholder)
    prompt = render_prompt(packet, gates)
    prompt_hash = sha256_text(prompt)
    packet = build_packet(plan, plan_path.resolve(), handoff_schemas, gates, prompt_hash)
    prompt = render_prompt(packet, gates)
    verify_prompt_packet(prompt, packet)
    packet_hash = canonical_hash(packet)
    status = build_status(run_id, plan_hash, source_plan_hash, packet, handoff_schemas, gates, approval_state)
    run = {
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "source_plan_path": rel(plan_path.resolve()),
        "source_plan_hash": source_plan_hash,
        "plan_hash": plan_hash,
        "compiler_version": COMPILER_VERSION,
        "mode": "compile",
        "risk_policy": "block-all",
        "status_path": "status.json",
        "packet_paths": ["packets/001-first-slice.packet.json"],
        "approval_state_path": "gates/approval-state.json",
    }
    context_phases = {"schema_version": SCHEMA_VERSION, "source_plan_id": plan["plan_id"], "phases": build_phase_context(plan, handoff_schemas)}
    context_workers = {"schema_version": SCHEMA_VERSION, "source_plan_id": plan["plan_id"], "workers": build_worker_refs(plan)}
    context_parallelism = {"schema_version": SCHEMA_VERSION, "source_plan_id": plan["plan_id"], "parallelism": plan["parallelism"]}
    write_json_atomic(out_dir / "run.json", run)
    write_json_atomic(out_dir / "status.json", status)
    write_text_atomic(out_dir / "resume.md", render_resume(status, packet))
    write_text_atomic(out_dir / "README.md", render_readme(status, gates))
    write_json_atomic(out_dir / "plan.snapshot.json", plan)
    write_text_atomic(out_dir / "plan.sha256", plan_hash + "\n")
    write_json_atomic(out_dir / "packets" / "001-first-slice.packet.json", packet)
    write_text_atomic(out_dir / "packets" / "001-first-slice.prompt.md", prompt)
    for handoff in handoff_schemas:
        write_json_atomic(out_dir / "handoffs" / f"{handoff['handoff_id']}.schema.json", handoff)
    write_json_atomic(out_dir / "gates" / "approval-state.json", approval_state)
    for gate in gates:
        write_text_atomic(
            out_dir / "gates" / f"{gate['gate_id']}.approval.md",
            f"# Gate {gate['gate_id']}\n\nStatus: {gate['status']}\n\nTrigger: {gate['trigger']}\n\nV1 does not accept Markdown approval as machine approval.\n",
        )
    write_json_atomic(out_dir / "context" / "phases.json", context_phases)
    write_json_atomic(out_dir / "context" / "workers.json", context_workers)
    write_json_atomic(out_dir / "context" / "parallelism.json", context_parallelism)
    return {
        "run": run,
        "status": status,
        "packet": packet,
        "gates": gates,
        "handoffs": handoff_schemas,
        "packet_hash": packet_hash,
        "out_dir": out_dir,
    }


def missing_invalidator(kind: str, artifact_id: str, message: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": artifact_id,
        "code": RESUME_CODES["missing"],
        "expected_hash": None,
        "actual_hash": None,
        "message": message,
    }


def hash_invalidator(kind: str, artifact_id: str, expected: str | None, actual: str | None, message: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": artifact_id,
        "code": RESUME_CODES[kind],
        "expected_hash": expected,
        "actual_hash": actual,
        "message": message,
    }


def resume_run(run_dir: Path) -> dict[str, Any]:
    run_dir = resolve_v1_out(run_dir)
    sentinel_path = run_dir / SENTINEL
    if not sentinel_path.is_file() or sentinel_path.is_symlink():
        raise CompileError("ERR_OUT_PATH_NOT_OWNED", "resume path is not compiler-owned", path=run_dir)
    run_path = run_dir / "run.json"
    status_path = run_dir / "status.json"
    if not run_path.is_file() or not status_path.is_file():
        raise CompileError("ERR_RESUME_MISSING_ARTIFACT", "run.json or status.json is missing", path=run_dir)
    sentinel = json.loads(sentinel_path.read_text())
    run = json.loads(run_path.read_text())
    if (
        sentinel.get("tool") != TOOL
        or sentinel.get("schema_version") != SCHEMA_VERSION
        or sentinel.get("run_id") != run.get("run_id")
        or sentinel.get("mode") not in {"compile", "fixture"}
    ):
        raise CompileError("ERR_OUT_PATH_NOT_OWNED", "resume sentinel does not match run metadata", path=run_dir)
    old_status = json.loads(status_path.read_text())
    invalidators: list[dict[str, Any]] = []
    source_plan = ROOT / run["source_plan_path"]
    if not source_plan.is_file():
        invalidators.append(hash_invalidator("plan", str(source_plan), run.get("source_plan_hash"), None, "source plan is missing"))
        plan = None
    else:
        plan = read_json(source_plan)
        source_hash = canonical_hash(plan)
        if source_hash != run["source_plan_hash"]:
            invalidators.append(hash_invalidator("plan", run["source_plan_path"], run["source_plan_hash"], source_hash, "source plan hash changed"))
    snapshot_path = run_dir / "plan.snapshot.json"
    if not snapshot_path.is_file():
        invalidators.append(missing_invalidator("plan", "plan.snapshot.json", "plan snapshot is missing"))
        snapshot = None
    else:
        snapshot = json.loads(snapshot_path.read_text())
        actual = canonical_hash(snapshot)
        expected = old_status["snapshots"]["plan_hash"]
        if actual != expected:
            invalidators.append(hash_invalidator("plan", "plan.snapshot.json", expected, actual, "plan snapshot hash changed"))
    packet_path = run_dir / "packets" / "001-first-slice.packet.json"
    packet: dict[str, Any] | None = None
    if not packet_path.is_file():
        invalidators.append(missing_invalidator("packet", PACKET_ID, "packet JSON is missing"))
    else:
        packet = json.loads(packet_path.read_text())
        actual = canonical_hash(packet)
        expected = old_status["snapshots"]["packet_hashes"].get(PACKET_ID)
        if actual != expected:
            invalidators.append(hash_invalidator("packet", PACKET_ID, expected, actual, "packet hash changed"))
        input_actual = input_snapshot_hash(packet.get("input_snapshots", []))
        input_expected = old_status["snapshots"]["input_snapshot_hashes"].get(PACKET_ID)
        if input_actual != input_expected:
            invalidators.append(hash_invalidator("input", PACKET_ID, input_expected, input_actual, "input snapshot hash changed"))
    prompt_rel = "packets/001-first-slice.prompt.md"
    prompt_path = run_dir / prompt_rel
    if not prompt_path.is_file():
        invalidators.append(missing_invalidator("prompt", prompt_rel, "prompt Markdown is missing"))
    else:
        actual = sha256_text(prompt_path.read_text())
        expected = old_status["snapshots"]["prompt_hashes"].get(prompt_rel)
        if actual != expected:
            invalidators.append(hash_invalidator("prompt", prompt_rel, expected, actual, "prompt hash changed"))
    handoff_schemas = []
    for handoff_id, expected in old_status["snapshots"]["handoff_schema_hashes"].items():
        path = run_dir / "handoffs" / f"{handoff_id}.schema.json"
        if not path.is_file():
            invalidators.append(missing_invalidator("handoff", handoff_id, "handoff schema is missing"))
            continue
        item = json.loads(path.read_text())
        handoff_schemas.append(item)
        actual = canonical_hash(item)
        if actual != expected:
            invalidators.append(hash_invalidator("handoff", handoff_id, expected, actual, "handoff schema hash changed"))
    approval_path = run_dir / "gates" / "approval-state.json"
    gates = []
    approval_state = {"gates": []}
    if not approval_path.is_file():
        invalidators.append(missing_invalidator("gate", "approval-state.json", "approval state is missing"))
    else:
        approval_state = json.loads(approval_path.read_text())
        gates = approval_state.get("gates", [])
        actual = canonical_hash(approval_state)
        expected = old_status["snapshots"]["approval_state_hash"]
        if actual != expected:
            invalidators.append(hash_invalidator("gate", "approval-state.json", expected, actual, "approval state hash changed"))
        for gate in gates:
            gate_id = gate["gate_id"]
            actual_gate = canonical_hash(gate)
            expected_gate = old_status["snapshots"]["gate_approval_hashes"].get(gate_id)
            if actual_gate != expected_gate:
                invalidators.append(hash_invalidator("gate", gate_id, expected_gate, actual_gate, "gate approval hash changed"))
    if run.get("compiler_version") != COMPILER_VERSION:
        invalidators.append(hash_invalidator("compiler", TOOL, run.get("compiler_version"), COMPILER_VERSION, "compiler version changed"))
    resume_state = "invalidated" if invalidators else "resumable"
    status = build_status(
        run["run_id"],
        old_status["plan_hash"],
        old_status["source_plan_hash"],
        packet or {"prompt_hash": "", "input_snapshot_hash": "", "prompt_path": prompt_rel},
        handoff_schemas,
        gates,
        approval_state,
        resume_state=resume_state,
        invalidators=invalidators,
        checked_at=now_utc(),
        resume_result=resume_state,
    )
    write_json_atomic(status_path, status)
    write_text_atomic(run_dir / "resume.md", render_resume(status, packet))
    return status


def mutate_plan(base: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(base)
    plan["plan_id"] = mutation.get("plan_id", plan["plan_id"])
    risk = mutation.get("risk")
    if mutation.get("neutral_gate"):
        plan["risk_gates"] = [{"trigger": "manual approval boundary", "safe_default": "stop before writing and ask for approval", "requires_user_approval": True}]
    if risk:
        if not mutation.get("neutral_gate"):
            plan["risk_gates"] = [{"trigger": mutation.get("gate_trigger", risk), "safe_default": RISK_SAFE_DEFAULTS.get(risk, "stop before writing and ask for approval"), "requires_user_approval": True}]
        worker_permissions = plan["workers"][0]["tool_permissions"]
        if risk == "write":
            worker_permissions["write"] = True
        elif risk == "shell-process":
            worker_permissions["shell"] = True
        elif risk == "network":
            worker_permissions["network"] = True
        elif risk == "external-message":
            worker_permissions["mcp_connectors"] = ["github"]
        else:
            plan["execution_path"]["first_slice"]["forbidden_actions"] = [mutation.get("risk_token", risk)]
    if "gate_trigger" in mutation and not risk:
        plan["risk_gates"][0]["trigger"] = mutation["gate_trigger"]
    if "instruction" in mutation:
        plan["execution_path"]["first_slice"]["instruction"] = mutation["instruction"]
    if "forbidden_actions" in mutation:
        plan["execution_path"]["first_slice"]["forbidden_actions"] = mutation["forbidden_actions"]
    if "inputs" in mutation:
        plan["execution_path"]["first_slice"]["inputs"] = mutation["inputs"]
    if mutation.get("surface_write"):
        plan["surfaces"][0]["access_mode"] = "write-proposed"
    return plan


def write_fixture_plan(temp_root: Path, fixture: dict[str, Any]) -> Path:
    plan_path = ROOT / fixture["plan"]
    plan = read_json(plan_path)
    if fixture.get("mutation"):
        plan = mutate_plan(plan, fixture["mutation"])
        mutated_path = temp_root / f"{fixture['id']}.workflow.plan.json"
        write_json_atomic(mutated_path, plan)
        return mutated_path
    return plan_path


def check_fixture_result(fixture: dict[str, Any], result: dict[str, Any]) -> None:
    status = result["status"]["packet_statuses"][0]["status"]
    expected_status = fixture.get("expected_status")
    if expected_status and status != expected_status:
        raise CompileError("ERR_RISK_GATE_BLOCKED", f"expected packet status {expected_status}, got {status}", fixture_id=fixture["id"])
    expected_categories = fixture.get("expected_blocked_categories", [])
    actual_categories = [gate["risk_category"] for gate in result["gates"] if gate["status"] == "blocked"]
    if expected_categories and actual_categories != expected_categories:
        raise CompileError("ERR_RISK_GATE_BLOCKED", f"blocked categories mismatch: {actual_categories}", fixture_id=fixture["id"])
    synthetic = [gate for gate in result["gates"] if gate["source"] == "compiler-synthetic"]
    if "expected_synthetic_count" in fixture and len(synthetic) != fixture["expected_synthetic_count"]:
        raise CompileError("ERR_RISK_GATE_BLOCKED", f"synthetic gate count mismatch: {len(synthetic)}", fixture_id=fixture["id"])
    if fixture.get("check_duplicate_inputs"):
        ids = [item["input_id"] for item in result["packet"]["input_snapshots"]]
        if len(ids) != len(set(ids)):
            raise CompileError("ERR_SELF_TEST_WRONG_REASON", "duplicate input IDs were not distinct", fixture_id=fixture["id"])


def run_fixture(fixture: dict[str, Any], suite_dir: Path, temp_root: Path) -> dict[str, Any]:
    fixture_id = fixture["id"]
    try:
        fixture_type = fixture["type"]
        if fixture_type == "compile":
            plan_path = write_fixture_plan(temp_root, fixture)
            result = compile_plan(plan_path, suite_dir / fixture_id, run_id=f"{suite_dir.name}/{fixture_id}", mode="fixture")
            check_fixture_result(fixture, result)
        elif fixture_type == "error":
            plan_path = write_fixture_plan(temp_root, fixture)
            out = Path(fixture.get("out_override", suite_dir / fixture_id))
            if fixture.get("make_symlink"):
                target = suite_dir / f"{fixture_id}-target"
                target.mkdir(parents=True, exist_ok=True)
                link = suite_dir / f"{fixture_id}-link"
                if not link.exists():
                    link.symlink_to(target, target_is_directory=True)
                out = link / "run"
            try:
                compile_plan(plan_path, out, run_id=f"{suite_dir.name}/{fixture_id}", mode="fixture")
            except CompileError as exc:
                if exc.code != fixture["expected_error"]:
                    raise CompileError("ERR_SELF_TEST_WRONG_REASON", f"expected {fixture['expected_error']}, got {exc.code}", fixture_id=fixture_id) from exc
            else:
                raise CompileError(fixture["expected_error"], "expected fixture failure did not occur", fixture_id=fixture_id)
        elif fixture_type == "drift":
            plan_path = write_fixture_plan(temp_root, fixture)
            result = compile_plan(plan_path, suite_dir / fixture_id, run_id=f"{suite_dir.name}/{fixture_id}", mode="fixture")
            prompt = render_prompt(result["packet"], result["gates"]).replace(result["packet"]["objective"], "changed objective", 1)
            try:
                verify_prompt_packet(prompt, result["packet"])
            except CompileError as exc:
                if exc.code != fixture["expected_error"]:
                    raise
            else:
                raise CompileError("ERR_PROMPT_PACKET_DRIFT", "prompt drift was not detected", fixture_id=fixture_id)
        elif fixture_type == "resume":
            plan_path = write_fixture_plan(temp_root, fixture)
            result = compile_plan(plan_path, suite_dir / fixture_id, run_id=f"{suite_dir.name}/{fixture_id}", mode="fixture")
            run_dir = result["out_dir"]
            mutate_run_artifact(run_dir, plan_path, fixture["mutate_artifact"])
            status = resume_run(run_dir)
            if "expected_resume_state" in fixture:
                if status["resume_state"] != fixture["expected_resume_state"]:
                    raise CompileError("ERR_SELF_TEST_WRONG_REASON", f"expected resume state {fixture['expected_resume_state']}, got {status['resume_state']}", fixture_id=fixture_id)
                return {"id": fixture_id, "status": "passed"}
            codes = [item["code"] for item in status["invalidators"]]
            if fixture["expected_invalidator"] not in codes:
                raise CompileError(fixture["expected_invalidator"], f"resume invalidator not found: {codes}", fixture_id=fixture_id)
        else:
            raise CompileError("ERR_PLAN_INVALID", f"unknown fixture type: {fixture_type}", fixture_id=fixture_id)
    except CompileError as exc:
        exc.fixture_id = exc.fixture_id or fixture_id
        return {"id": fixture_id, "status": "failed", "error": exc.to_record()}
    return {"id": fixture_id, "status": "passed"}


def mutate_run_artifact(run_dir: Path, plan_path: Path, mutation: str) -> None:
    if mutation == "none":
        return
    if mutation == "source_plan":
        plan = read_json(plan_path)
        plan["objective"] += " changed"
        write_json_atomic(plan_path, plan)
    elif mutation == "plan_snapshot":
        path = run_dir / "plan.snapshot.json"
        data = json.loads(path.read_text())
        data["objective"] += " changed"
        write_json_atomic(path, data)
    elif mutation == "packet":
        path = run_dir / "packets" / "001-first-slice.packet.json"
        data = json.loads(path.read_text())
        data["objective"] += " changed"
        write_json_atomic(path, data)
    elif mutation == "prompt":
        path = run_dir / "packets" / "001-first-slice.prompt.md"
        write_text_atomic(path, path.read_text() + "\nchanged\n")
    elif mutation == "input":
        path = run_dir / "packets" / "001-first-slice.packet.json"
        data = json.loads(path.read_text())
        data["input_snapshots"][0]["normalized_value"] += " changed"
        write_json_atomic(path, data)
    elif mutation == "gate":
        path = run_dir / "gates" / "approval-state.json"
        data = json.loads(path.read_text())
        data["gates"][0]["approved"] = True
        write_json_atomic(path, data)
    elif mutation == "missing_handoff":
        handoffs = sorted((run_dir / "handoffs").glob("*.schema.json"))
        handoffs[0].unlink()


def evaluate_manifest(manifest_path: Path, out_dir: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    suite_id = Path(out_dir).name
    suite_dir = resolve_v1_out(out_dir)
    prepare_owned_dir(suite_dir, suite_id, "manifest", clear=True)
    required = manifest["required_fixture_ids"]
    fixtures = manifest["fixtures"]
    fixture_ids = [fixture["id"] for fixture in fixtures]
    failures = []
    passed = 0
    temp_root = suite_dir / "_fixture-plans"
    temp_root.mkdir(parents=True, exist_ok=True)
    for fixture in fixtures:
        result = run_fixture(fixture, suite_dir, temp_root)
        if result["status"] == "passed":
            passed += 1
        else:
            failures.append(result["error"])
    missing = sorted(set(required) - set(fixture_ids))
    duplicate = sorted({item for item in fixture_ids if fixture_ids.count(item) > 1})
    for fixture_id in missing:
        failures.append({"code": "ERR_PLAN_INVALID", "message": "required fixture missing", "fixture_id": fixture_id})
    for fixture_id in duplicate:
        failures.append({"code": "ERR_PLAN_INVALID", "message": "duplicate fixture ID", "fixture_id": fixture_id})
    skipped = len(set(required) - set(fixture_ids))
    failed = len(failures)
    summary = {
        "suite_id": suite_id,
        "fixture_count": len(required),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "decision": "keep" if failed == 0 and skipped == 0 and passed == len(required) else "kill",
        "failures": failures,
    }
    write_json_atomic(suite_dir / "summary.json", summary)
    if summary["decision"] != "keep":
        raise CompileError("ERR_PLAN_INVALID", "manifest decision is kill", path=manifest_path)
    return summary


def self_test() -> None:
    manifest = ROOT / "fixtures" / "v1" / "manifest.json"
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compile-workflow-self-test-", dir=OUT_ROOT) as tmp:
        out = Path(tmp) / "self-test"
        summary = evaluate_manifest(manifest, out)
    if summary["decision"] != "keep":
        raise CompileError("ERR_SELF_TEST_WRONG_REASON", "self-test manifest did not keep")
    print("compile_workflow self-test: pass")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan")
    parser.add_argument("--out")
    parser.add_argument("--mode", default="compile", choices=["compile"])
    parser.add_argument("--resume")
    parser.add_argument("--manifest")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        elif args.manifest:
            if not args.out:
                raise CompileError("ERR_OUT_PATH_UNSAFE", "--manifest requires --out")
            summary = evaluate_manifest(Path(args.manifest), Path(args.out))
            print(canonical_json_text(summary))
        elif args.resume:
            status = resume_run(Path(args.resume))
            print(canonical_json_text({"resume_state": status["resume_state"], "invalidators": status["invalidators"]}))
            return 0 if status["resume_state"] == "resumable" else 1
        elif args.plan and args.out:
            result = compile_plan(Path(args.plan), Path(args.out), mode=args.mode)
            print(canonical_json_text({"run_id": result["run"]["run_id"], "status": result["status"]["packet_statuses"][0]["status"]}))
        else:
            parser.error("expected --self-test, --manifest, --resume, or --plan with --out")
    except CompileError as exc:
        print(canonical_json_text(exc.to_record()), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
