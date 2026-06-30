# Codex Local Capability Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stdlib-only `codex-local-capability` command that records whether a local Codex adapter can be launched safely, without launching a live coding task.

**Architecture:** Mirror the `team-shell-lane-launch` receipt pattern: core logic in `depone/agent_fabric/`, thin CLI in `depone/cli/`, command registration in `depone/__main__.py`, focused unittest coverage, and docs fixtures that revalidate through `scripts/check_contract.py`. The receipt must degrade to `decision: blocked` for missing or unproven prerequisites.

**Tech Stack:** Python standard library only, `subprocess` for `codex --version`, `shutil.which` for binary detection, `git` via subprocess for repo facts, JSON receipts, `unittest`.

---

## File Structure

- Create: `depone/agent_fabric/codex_local_capability.py`
  - Owns detection, receipt construction, hash helpers, fixture validation, and `_self_test()`.
- Create: `depone/cli/codex_local_capability.py`
  - Parses already-registered CLI args from `depone/__main__.py`, calls the core module, writes JSON, and emits human/JSON output.
- Modify: `depone/__main__.py`
  - Imports the CLI module, registers `codex-local-capability`, and dispatches it.
- Create: `tests/test_agent_fabric_codex_local_capability.py`
  - Unit tests for pass, missing binary, dirty repo, instruction hashes, contract binding, and validation failures.
- Create: `tests/test_codex_local_capability_cli.py`
  - CLI self-test and JSON output tests.
- Create: `docs/codex-local-capability/README.md`
  - Honest capability statement and exact regeneration command.
- Create: `docs/codex-local-capability/capability.json`
  - Committed fixture. It may be `blocked` if the server cannot prove live Codex readiness without interactive auth.
- Modify: `docs/command-reference.md`
  - Add command entry.
- Modify: `scripts/check_contract.py`
  - Add a docs contract that validates the committed capability fixture and runs `python3 -m depone codex-local-capability --self-test`.

### Task 1: Core Receipt Tests

**Files:**
- Create: `tests/test_agent_fabric_codex_local_capability.py`
- Create: `depone/agent_fabric/codex_local_capability.py`

- [ ] **Step 1: Write tests for blocked missing binary**

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depone.agent_fabric.codex_local_capability import (
    CODEX_LOCAL_CAPABILITY_KIND,
    build_codex_local_capability,
    validate_codex_local_capability,
)


class CodexLocalCapabilityTests(unittest.TestCase):
    def test_missing_codex_binary_blocks_without_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with patch("shutil.which", return_value=None):
                receipt = build_codex_local_capability(
                    repo=root,
                    codex_binary="codex",
                    sandbox_mode="workspace-write",
                    approval_policy="on-request",
                    instruction_files=[],
                )

        self.assertEqual(receipt["kind"], CODEX_LOCAL_CAPABILITY_KIND)
        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("codex binary not found", receipt["blocked_reasons"])
        self.assertFalse(receipt["boundary"]["launches_live_model"])
        self.assertFalse(receipt["boundary"]["executes_coding_task"])
        self.assertFalse(receipt["boundary"]["raises_assurance"])
        self.assertEqual(validate_codex_local_capability(receipt), [])
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_codex_local_capability.CodexLocalCapabilityTests.test_missing_codex_binary_blocks_without_launch -v
```

Expected: import failure because `depone.agent_fabric.codex_local_capability` does not exist.

- [ ] **Step 3: Add the minimal core module**

```python
"""Codex local adapter capability detection without launching a coding task."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from depone.agent_fabric.agent_operating_contract import (
    AGENT_OPERATING_CONTRACT_PATH,
    DWM_ROLES_PATH,
    V22_WORKER_ROLE_ID,
    build_agent_contract_facts,
    load_agent_operating_contract,
    load_v22_role_registry,
)

CODEX_LOCAL_CAPABILITY_KIND = "depone-codex-local-capability"
CODEX_LOCAL_CAPABILITY_SCHEMA_VERSION = "0.1"
DEFAULT_CODEX_ROLE_ID = V22_WORKER_ROLE_ID
ALLOWED_SANDBOX_MODES = frozenset({"read-only", "workspace-write"})
ALLOWED_APPROVAL_POLICIES = frozenset({"on-request", "on-failure", "never"})


def build_codex_local_capability(
    *,
    repo: Path,
    codex_binary: str = "codex",
    sandbox_mode: str = "workspace-write",
    approval_policy: str = "on-request",
    instruction_files: list[Path] | None = None,
    role_id: str = DEFAULT_CODEX_ROLE_ID,
) -> dict[str, object]:
    resolved_repo = repo.resolve()
    blocked_reasons: list[str] = []
    binary_path = shutil.which(codex_binary)
    version = _codex_version(binary_path) if binary_path else None
    if binary_path is None:
        blocked_reasons.append("codex binary not found")
    if sandbox_mode not in ALLOWED_SANDBOX_MODES:
        blocked_reasons.append("unsupported sandbox mode")
    if approval_policy not in ALLOWED_APPROVAL_POLICIES:
        blocked_reasons.append("unsupported approval policy")
    git_facts = _git_facts(resolved_repo)
    if git_facts.get("is_git_worktree") is not True:
        blocked_reasons.append("repo is not a git worktree")
    contract = build_agent_contract_facts(
        load_agent_operating_contract(AGENT_OPERATING_CONTRACT_PATH),
        load_v22_role_registry(DWM_ROLES_PATH),
        role_id,
    )
    instructions = _instruction_facts(resolved_repo, instruction_files or [])
    receipt = {
        "kind": CODEX_LOCAL_CAPABILITY_KIND,
        "schema_version": CODEX_LOCAL_CAPABILITY_SCHEMA_VERSION,
        "decision": "blocked" if blocked_reasons else "pass",
        "blocked_reasons": blocked_reasons,
        "adapter": {
            "id": "codex-local",
            "codex_binary": codex_binary,
            "binary_path": binary_path,
            "version": version,
        },
        "repo": git_facts,
        "requested_runtime": {
            "sandbox_mode": sandbox_mode,
            "approval_policy": approval_policy,
        },
        "instruction_files": instructions,
        "agent_contract_hash": contract["agent_contract_hash"],
        "agent_contract": contract,
        "boundary": {
            "launches_live_model": False,
            "executes_coding_task": False,
            "captures_capability_only": True,
            "raises_assurance": False,
        },
    }
    return receipt


def validate_codex_local_capability(receipt: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if receipt.get("kind") != CODEX_LOCAL_CAPABILITY_KIND:
        errors.append("kind must be depone-codex-local-capability")
    if receipt.get("schema_version") != CODEX_LOCAL_CAPABILITY_SCHEMA_VERSION:
        errors.append("schema_version must be 0.1")
    if receipt.get("decision") not in {"pass", "blocked"}:
        errors.append("decision must be pass or blocked")
    if receipt.get("decision") == "blocked" and not receipt.get("blocked_reasons"):
        errors.append("blocked decision requires blocked_reasons")
    boundary = receipt.get("boundary")
    if not isinstance(boundary, dict):
        errors.append("boundary must be an object")
    else:
        for key in ("launches_live_model", "executes_coding_task", "raises_assurance"):
            if boundary.get(key) is not False:
                errors.append(f"boundary.{key} must be false")
        if boundary.get("captures_capability_only") is not True:
            errors.append("boundary.captures_capability_only must be true")
    agent_contract = receipt.get("agent_contract")
    if not isinstance(agent_contract, dict):
        errors.append("agent_contract must be an object")
    elif receipt.get("agent_contract_hash") != agent_contract.get("agent_contract_hash"):
        errors.append("agent_contract_hash mismatch")
    return errors


def write_codex_local_capability(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _codex_version(binary_path: str | None) -> str | None:
    if binary_path is None:
        return None
    completed = subprocess.run(
        [binary_path, "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or completed.stderr.strip() or None


def _git_facts(repo: Path) -> dict[str, object]:
    root = _git(repo, ["rev-parse", "--show-toplevel"])
    head = _git(repo, ["rev-parse", "HEAD"])
    branch = _git(repo, ["branch", "--show-current"])
    status = _git(repo, ["status", "--porcelain"])
    return {
        "path": repo.as_posix(),
        "is_git_worktree": root is not None,
        "root": root,
        "head": head,
        "branch": branch,
        "dirty": bool(status),
    }


def _git(repo: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", repo.as_posix(), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _instruction_facts(repo: Path, instruction_files: list[Path]) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    for path in instruction_files:
        resolved = path if path.is_absolute() else repo / path
        if not resolved.exists() or not resolved.is_file():
            facts.append({"path": path.as_posix(), "present": False, "sha256": None})
            continue
        facts.append(
            {
                "path": path.as_posix(),
                "present": True,
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            }
        )
    return facts


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        with open(root / "AGENTS.md", "w", encoding="utf-8") as handle:
            handle.write("# test\n")
        receipt = build_codex_local_capability(
            repo=root,
            codex_binary="definitely-missing-codex-for-depone-self-test",
            instruction_files=[Path("AGENTS.md")],
        )
        errors = validate_codex_local_capability(receipt)
        if errors:
            raise AssertionError(errors)
        if receipt["decision"] != "blocked":
            raise AssertionError("missing codex binary self-test must block")
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_codex_local_capability.CodexLocalCapabilityTests.test_missing_codex_binary_blocks_without_launch -v
```

Expected: `OK`.

### Task 2: Pass-Path And Validation Tests

**Files:**
- Modify: `tests/test_agent_fabric_codex_local_capability.py`
- Modify: `depone/agent_fabric/codex_local_capability.py`

- [ ] **Step 1: Add tests for pass path, instruction hashes, and invalid receipt validation**

```python
    def test_pass_receipt_records_version_repo_and_instruction_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            (root / "AGENTS.md").write_text("# contract\n", encoding="utf-8")
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.test\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(
                    repo=root,
                    codex_binary="codex",
                    sandbox_mode="workspace-write",
                    approval_policy="on-request",
                    instruction_files=[Path("AGENTS.md")],
                )

        self.assertEqual(receipt["decision"], "pass")
        self.assertEqual(receipt["adapter"]["version"], "codex 0.test")
        self.assertEqual(receipt["repo"]["dirty"], False)
        self.assertEqual(receipt["instruction_files"][0]["present"], True)
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_invalid_receipt_validation_reports_hash_mismatch(self) -> None:
        receipt = {
            "kind": CODEX_LOCAL_CAPABILITY_KIND,
            "schema_version": "0.1",
            "decision": "pass",
            "blocked_reasons": [],
            "boundary": {
                "launches_live_model": False,
                "executes_coding_task": False,
                "captures_capability_only": True,
                "raises_assurance": False,
            },
            "agent_contract_hash": "wrong",
            "agent_contract": {"agent_contract_hash": "right"},
        }

        self.assertIn("agent_contract_hash mismatch", validate_codex_local_capability(receipt))
```

- [ ] **Step 2: Run the full core test file**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_codex_local_capability -v
```

Expected: `OK`.

### Task 3: CLI Registration

**Files:**
- Create: `depone/cli/codex_local_capability.py`
- Modify: `depone/__main__.py`
- Create: `tests/test_codex_local_capability_cli.py`

- [ ] **Step 1: Add CLI tests**

```python
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class CodexLocalCapabilityCliTests(unittest.TestCase):
    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "codex-local-capability", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("codex-local-capability --self-test: pass", completed.stdout)

    def test_cli_writes_blocked_receipt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            out = root / "capability.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "codex-local-capability",
                    "--repo",
                    str(root),
                    "--codex-binary",
                    "definitely-missing-codex-for-test",
                    "--instruction-file",
                    "AGENTS.md",
                    "--out",
                    str(out),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["decision"], "blocked")
        self.assertEqual(receipt["decision"], "blocked")

    def test_main_dispatches_codex_local_capability(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "codex-local-capability", "--self-test"]):
            with patch.object(depone_main.codex_local_capability, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "codex-local-capability")
```

- [ ] **Step 2: Implement the CLI module**

```python
"""depone codex-local-capability - detect local Codex adapter readiness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depone.agent_fabric.codex_local_capability import (
    _self_test,
    build_codex_local_capability,
    write_codex_local_capability,
)
from depone.cli._response import emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone codex-local-capability --self-test: pass")
        return

    receipt = build_codex_local_capability(
        repo=Path(str(getattr(args, "repo", "") or ".")),
        codex_binary=str(getattr(args, "codex_binary", "") or "codex"),
        sandbox_mode=str(getattr(args, "sandbox_mode", "") or "workspace-write"),
        approval_policy=str(getattr(args, "approval_policy", "") or "on-request"),
        instruction_files=[Path(value) for value in getattr(args, "instruction_file", [])],
    )
    out_arg = str(getattr(args, "out", "") or "codex-local-capability.json")
    write_codex_local_capability(Path(out_arg), receipt)
    emit_result(
        args,
        {
            "command": "codex-local-capability",
            "decision": receipt["decision"],
            "blocked_reasons": receipt["blocked_reasons"],
            "out": out_arg,
        },
        human=[
            f"Codex local capability decision: {receipt['decision']}",
            f"  Receipt: {out_arg}",
        ],
    )
    sys.exit(exit_code_for_decision(str(receipt["decision"])))
```

- [ ] **Step 3: Register command in `depone/__main__.py`**

Add `codex_local_capability` to the `from depone.cli import (...)` list.

Add:

```python
def _add_codex_local_capability_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Repository root or worktree to inspect")
    parser.add_argument("--codex-binary", default="codex", help="Codex executable name or path")
    parser.add_argument("--sandbox-mode", default="workspace-write", help="Requested Codex sandbox mode")
    parser.add_argument("--approval-policy", default="on-request", help="Requested Codex approval policy")
    parser.add_argument(
        "--instruction-file",
        action="append",
        default=[],
        help="Instruction file path, relative to --repo; repeatable",
    )
    parser.add_argument("--out", default="codex-local-capability.json", help="Output receipt JSON")
    parser.add_argument("--self-test", action="store_true", help="Run self-test and exit")
    _add_json_arg(parser)
```

Register the parser near the other team/adapter commands:

```python
    codex_local_capability_parser = sub.add_parser(
        "codex-local-capability",
        help="Detect local Codex adapter capability without launching a task",
    )
    _add_codex_local_capability_args(codex_local_capability_parser)
```

Dispatch:

```python
        elif args.command == "codex-local-capability":
            codex_local_capability.run(args)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python3 -m unittest tests.test_codex_local_capability_cli -v
```

Expected: `OK`.

### Task 4: Docs Fixture And Contract Check

**Files:**
- Create: `docs/codex-local-capability/README.md`
- Create: `docs/codex-local-capability/capability.json`
- Modify: `docs/command-reference.md`
- Modify: `scripts/check_contract.py`

- [ ] **Step 1: Generate the fixture**

Run:

```bash
mkdir -p docs/codex-local-capability
python3 -m depone codex-local-capability \
  --repo . \
  --codex-binary definitely-missing-codex-for-committed-fixture \
  --instruction-file AGENTS.md \
  --instruction-file CLAUDE.md \
  --out docs/codex-local-capability/capability.json \
  --json
```

Expected: JSON stdout with `decision` equal to `blocked` and a committed receipt at `docs/codex-local-capability/capability.json`.

- [ ] **Step 2: Add README text**

````markdown
# Codex Local Capability

This fixture records Codex local adapter capability detection without launching
a live Codex task.

The committed fixture is allowed to be `blocked`. A blocked fixture is useful
when it proves the adapter fails closed for missing binary, missing auth/config,
or unsupported runtime conditions.

Regenerate:

```bash
python3 -m depone codex-local-capability \
  --repo . \
  --codex-binary definitely-missing-codex-for-committed-fixture \
  --instruction-file AGENTS.md \
  --instruction-file CLAUDE.md \
  --out docs/codex-local-capability/capability.json \
  --json
```

Honest limit: this is capability evidence only. It does not launch a model,
execute a coding task, prove sandbox isolation, or raise assurance.
````

- [ ] **Step 3: Add contract validation helper**

In `scripts/check_contract.py`, add a helper that:

- loads `docs/codex-local-capability/capability.json`;
- imports `validate_codex_local_capability`;
- requires validation errors to be `[]`;
- recomputes `sha256` for present instruction files;
- requires `boundary.launches_live_model == False`;
- runs `python3 -m depone codex-local-capability --self-test` in the changed tier.

- [ ] **Step 4: Run contract checks**

Run:

```bash
python3 -m depone codex-local-capability --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected:

```text
depone codex-local-capability --self-test: pass
contract changed: pass
DWM doctor: ok
```

### Task 5: Final Review And PR

**Files:**
- Review all files changed in Tasks 1-4.

- [ ] **Step 1: Run full focused verification**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_codex_local_capability tests.test_codex_local_capability_cli -v
python3 -m depone codex-local-capability --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected:

```text
OK
depone codex-local-capability --self-test: pass
contract changed: pass
DWM doctor: ok
```

- [ ] **Step 2: Review diff for overclaim**

Run:

```bash
git diff -- docs/codex-local-capability docs/command-reference.md depone tests scripts/check_contract.py
```

Confirm that docs and receipt text say capability-only and do not claim live Codex launch, A2, container isolation, scheduler ownership, or model execution.

- [ ] **Step 3: Commit**

```bash
git add depone/__main__.py depone/agent_fabric/codex_local_capability.py depone/cli/codex_local_capability.py tests/test_agent_fabric_codex_local_capability.py tests/test_codex_local_capability_cli.py docs/codex-local-capability docs/command-reference.md scripts/check_contract.py
git commit -m "Add Codex local capability receipt"
```

- [ ] **Step 4: Open a draft PR**

```bash
git push -u origin codex/codex-local-capability
gh pr create --draft --title "Add Codex local capability receipt" --body "Adds a stdlib-only Codex local capability detector that writes blocked/pass receipts without launching a live coding task.

Verification:
- python3 -m unittest tests.test_agent_fabric_codex_local_capability tests.test_codex_local_capability_cli -v
- python3 -m depone codex-local-capability --self-test
- python3 scripts/check_contract.py --tier changed
- python3 scripts/dwm.py doctor
- git diff --check

Honest residual: capability-only evidence; no live model launch, coding task execution, scheduler ownership, A2/container claim, or assurance upgrade."
```

## Self-Review

- Spec coverage: this plan covers capability detection, blocked-safe behavior, contract hash binding, fixture validation, docs, tests, and PR flow.
- Placeholder scan: no steps depend on unspecified values or deferred behavior.
- Type consistency: the planned command name is consistently `codex-local-capability`; the core functions are consistently `build_codex_local_capability`, `validate_codex_local_capability`, and `write_codex_local_capability`.
