# Team Local Pass Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one re-validatable `team-local` lane that can reach Team Ledger `pass` from real local evidence-run artifacts.

**Architecture:** Extend `team-local` narrowly instead of adding a new runner. A lane may declare `command_ids` as an ordered list of argv-allowlisted commands; `team-local` substitutes a small set of safe runtime tokens, runs each command in the prepared worktree, evaluates the lane evidence directory with `evidence-next`, writes a read-only `worktree-lane-receipt`, and then lets Team Ledger decide pass or blocked. The command remains fail-closed and never launches live coding agents or raises assurance.

**Tech Stack:** Python stdlib, existing `team_shell_lane_launch`, `evidence_next`, `worktree_receipt`, `team_ledger`, `unittest`, committed JSON artifacts under `docs/team-local-pass/`, and `scripts/check_contract.py --tier changed`.

---

## Scope Lock

This slice implements only local shell/evidence fan-in for one or more lanes.
It does not launch Codex, Claude, OpenCode, OMX workers, cloud jobs, or live
models. It does not approve merges, sign bundles, create a new assurance rung,
or claim autonomous coding completion beyond the machine evidence present in
the committed artifacts.

## File Ownership

- Modify: `depone/agent_fabric/team_local.py`
  - Add ordered `command_ids` support.
  - Add allowlist argv runtime token substitution.
  - Write per-command receipts/transcripts.
  - Build `worktree-receipt.json` after successful evidence validation.
- Modify: `depone/cli/team_local.py`
  - Keep CLI stable; only expose new behavior through plan JSON.
- Modify: `tests/test_agent_fabric_team_local.py`
  - Add pass-lane unit coverage and runtime token safety coverage.
- Modify: `tests/test_team_local_cli.py`
  - Add a CLI smoke for a plan containing `command_ids`.
- Create: `docs/team-local-pass/`
  - Machine artifacts from a real pass-lane run.
- Modify: `docs/command-reference.md`
  - Document `command_ids` and runtime token behavior.
- Modify: `scripts/check_contract.py`
  - Add a docs contract that revalidates `docs/team-local-pass/team-run-ledger.json`.

## Agent Wave Split

### Wave A: Plan Review

- [ ] Read this plan plus `docs/team-local/README.md`.
- [ ] Confirm there is no claim that `team-local` launches coding agents.
- [ ] Confirm the pass condition is delegated to `evidence-next` and Team Ledger.
- [ ] Confirm every generated artifact path is repo-relative in the run ledger.
- [ ] Report one of:
  - `PLAN_OK: no changes needed`
  - `PLAN_FIX_REQUIRED: <specific issue and file>`

### Wave B: Core Implementation

- [ ] **Step 1: Add failing test for ordered commands reaching pass**

Add a test in `tests/test_agent_fabric_team_local.py` named
`test_ordered_commands_can_produce_passed_lane`.

The test should:
- create or reuse a real git worktree from the repository under test;
- run `run_team_local` with a plan lane containing:
  - `command_ids`: `["write-marker", "evidence-run", "git-add", "git-commit"]`;
  - `touched_files`: `["team-local-marker.txt"]`;
- use an allowlist with argv commands only;
- assert:
  - `ledger["decision"] == "pass"`;
  - `ledger["passed_lane_count"] == 1`;
  - lane record has at least four command receipts;
  - `validate_team_local_run_ledger(...) == []`;
  - `team-ledger-verdict.json` decision is `pass`.

Use runtime tokens in the allowlist:

```json
{
  "commands": [
    {
      "id": "write-marker",
      "argv": [
        "python3",
        "-c",
        "from pathlib import Path; Path('team-local-marker.txt').write_text('ok\\n', encoding='utf-8')"
      ]
    },
    {
      "id": "evidence-run",
      "argv": [
        "python3",
        "-m",
        "depone",
        "evidence-run",
        "--runner-sandbox",
        ".",
        "--source-fixture",
        "{repo_root}/depone/fixtures/agent_fabric/reference_adapter_shell.json",
        "--out",
        "{evidence_dir_abs}",
        "--allow-touched-file",
        "team-local-marker.txt",
        "--json",
        "--",
        "python3",
        "-c",
        "from pathlib import Path; assert Path('team-local-marker.txt').exists()"
      ]
    },
    {
      "id": "git-add",
      "argv": ["git", "add", "team-local-marker.txt"]
    },
    {
      "id": "git-commit",
      "argv": [
        "git",
        "-c",
        "user.name=Depone",
        "-c",
        "user.email=depone@example.invalid",
        "commit",
        "-m",
        "team local marker"
      ]
    }
  ]
}
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_local.AgentFabricTeamLocalTests.test_ordered_commands_can_produce_passed_lane -v
```

Expected before implementation: failure because `command_ids` is ignored or
unsupported.

- [ ] **Step 3: Implement ordered `command_ids`**

In `depone/agent_fabric/team_local.py`:
- keep existing `command_id` behavior as a single-command compatibility path;
- accept `command_ids` when it is a non-empty list of non-empty strings;
- block if both `command_id` and `command_ids` are present;
- run command ids in order;
- write each receipt to `lane-id/commands/<command-id>-receipt.json`;
- write each transcript to `lane-id/commands/<command-id>-transcript.json`;
- preserve legacy `shell_receipt` and `shell_transcript` as the first command paths for backward compatibility;
- add `shell_receipts` and `shell_transcripts` lists to lane records.

- [ ] **Step 4: Implement safe runtime token expansion**

Allow only these runtime tokens inside allowlist argv strings:

```text
{repo_root}
{worktree_path}
{evidence_dir}
{evidence_dir_abs}
{lane_id}
```

Block unknown runtime tokens with `ERR_TEAM_LOCAL_TOKEN_INVALID`. Substitute
values before passing the allowlist to `run_shell_lane_command`. Do not invoke a
shell and do not concatenate command strings.

- [ ] **Step 5: Build the worktree receipt**

After all shell commands pass and after `evidence-next` returns `continue`, call:

```python
build_worktree_lane_receipt(
    worktree=Path(worktree_path),
    base_commit=effective_base_commit,
    evidence_dir=Path(lane_id),
    commands=command_receipts,
)
```

Write the result to `lane-id/worktree-receipt.json`, set
`lane["worktree_receipt"] = f"{lane_id}/worktree-receipt.json"`, set
`lane["end_commit"]` to the receipt head commit, and set `lane["touched_files"]`
from the plan or from receipt `changed_files`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_local tests.test_team_local_cli -v
```

Expected: all tests pass.

### Wave C: Docs Artifact And Contract

- [ ] **Step 1: Generate `docs/team-local-pass/` fixture**

Use the implemented command with a plan equivalent to the test plan. The fixture
must produce:

```text
docs/team-local-pass/team-run-ledger.json
docs/team-local-pass/team-ledger.json
docs/team-local-pass/team-ledger-verdict.json
docs/team-local-pass/lane-1/evidence-next-verdict.json
docs/team-local-pass/lane-1/worktree-receipt.json
docs/team-local-pass/lane-1/commands/*.json
docs/team-local-pass/lane-1/capture-manifest.json
docs/team-local-pass/lane-1/observer-capture.json
docs/team-local-pass/lane-1/evidence-bundle.json
docs/team-local-pass/lane-1/evidence-run-summary.json
```

The committed `team-run-ledger.json` must have:

```json
{
  "decision": "pass",
  "passed_lane_count": 1,
  "blocked_lane_count": 0
}
```

- [ ] **Step 2: Add docs contract**

In `scripts/check_contract.py`, add `require_team_local_pass_docs_contract`.
It must:
- require all fixture files above;
- load `team-run-ledger.json`;
- call `validate_team_local_run_ledger(..., base_dir=ROOT)`;
- require `decision == "pass"`;
- require `boundary.launches_agents is False`;
- require `boundary.calls_live_models is False`;
- require `boundary.executes_unlisted_shell_commands is False`;
- require `boundary.raises_assurance is False`;
- require `team-ledger-verdict.json` decision `pass`.

- [ ] **Step 3: Update command docs**

Update `docs/command-reference.md` with a short note:
- `command_id` runs one allowlisted command;
- `command_ids` runs an ordered allowlisted sequence;
- runtime token expansion is limited to the five documented runtime tokens;
- the command still does not launch live coding agents.

- [ ] **Step 4: Revalidate committed pass artifact**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from depone.agent_fabric.team_local import validate_team_local_run_ledger
m=json.load(open("docs/team-local-pass/team-run-ledger.json"))
print("team-local-pass decision:", m.get("decision"))
print("validate errors:", validate_team_local_run_ledger(m, base_dir=Path(".")))
print("passed lanes:", m.get("passed_lane_count"))
print("boundary:", m.get("boundary"))
PY
```

Expected:

```text
team-local-pass decision: pass
validate errors: []
passed lanes: 1
boundary: {'approves_merge': False, 'calls_live_models': False, 'creates_worktrees': True, 'executes_allowlisted_shell_commands': True, 'executes_unlisted_shell_commands': False, 'launches_agents': False, 'raises_assurance': False}
```

### Wave D: Final Verification And PR Update

- [ ] Run related tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_local tests.test_team_local_cli tests.test_agent_fabric_team_dry_run tests.test_agent_fabric_team_launch_preflight tests.test_agent_fabric_team_worktree_prep tests.test_agent_fabric_team_shell_lane_launch tests.test_agent_fabric_team_ledger tests.test_agent_fabric_worktree_receipt tests.test_evidence_next tests.test_evidence_run_uid_launch -v
```

- [ ] Run self-tests:

```bash
python3 -m depone team-local --self-test
python3 -m depone evidence-next --self-test
python3 -m depone team-ledger --self-test
python3 -m depone worktree-lane-receipt --self-test
```

- [ ] Run contract and repo checks:

```bash
git diff --check
python3 scripts/dwm.py doctor
python3 scripts/check_contract.py --tier changed
```

- [ ] Commit:

```bash
git add depone/agent_fabric/team_local.py depone/cli/team_local.py tests/test_agent_fabric_team_local.py tests/test_team_local_cli.py docs/team-local-pass docs/command-reference.md scripts/check_contract.py docs/superpowers/plans/2026-07-01-team-local-pass-lane.md
git commit -m "Add passing team-local evidence lane"
```

- [ ] Push and update PR #61:

```bash
git push
gh pr comment 61 --body "Added team-local pass-lane slice with re-validatable docs/team-local-pass artifacts. Verification: related tests pass, validate_team_local_run_ledger returns [], check_contract changed passes."
```

## Self-Review

- Spec coverage: the plan covers ordered local commands, evidence-run artifact
  generation, evidence-next revalidation, worktree receipt generation, Team
  Ledger fan-in, docs artifacts, and contract verification.
- Red-flag scan: no task uses incomplete-marker instructions.
- Type consistency: `command_ids`, `shell_receipts`, `shell_transcripts`,
  `worktree_receipt`, and `evidence_next_verdict` are named consistently across
  implementation, tests, artifacts, and docs.
- Scope check: this is one PR-sized slice stacked on PR #61 and does not add
  native agent scheduling or cloud/runtime provisioning.
