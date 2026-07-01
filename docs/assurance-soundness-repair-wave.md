# Assurance Soundness Repair Wave

Status: implementation wave, 2026-07-01.

## Goal

Close the next trust-ladder holes before adding more launch automation. Depone's
core product claim is evidence verification without executing the agent under
test. This wave prevents self-authored evidence from being mistaken for stronger
observer assurance, and fixes nearby boundaries where declarations currently
outrun observed facts.

## Non-Goals

- Do not add a new assurance level.
- Do not launch Codex, Claude, OpenCode, or other live model agents.
- Do not add Python dependencies.
- Do not merge PRs or change GitHub workflow state.
- Do not rewrite the DWM harness or broad docs.
- Do not modify unrelated local dirty files.

## Findings To Close

1. UID A2 root fail-open: root runner facts must not establish the uid-boundary
   model, because root can override normal directory permission bits.
2. Imported capture overclaim: a hand-written capture manifest in an evidence
   directory must not be enough to make a verification report claim observed
   assurance.
3. Handoff disappearance: handoffs whose `to_phase` is unknown or mismatched
   must not disappear from the verdict.
4. Tool mapping contradiction: a concrete tool must never be both allowed and
   forbidden in the same resolved toolbelt.
5. Shell lane trampoline: an allowlisted `bash -c`, `sh -c`, `python -c`, `env`,
   `npx`, or similar wrapper must not bypass prohibited agent executable checks,
   and receipts must not claim `uses_shell=false` for shell execution.
6. Team ledger under-reporting: passed lanes with worktree receipts must not be
   able to hide changed files by under-reporting `touched_files`.

## Implementation Slices

### Slice A: Assurance and Handoff Soundness

Owner lane: verification/core.

Tasks:
- Add failing tests for a forged A1 capture manifest plus permissive
  `evidence-contract.json`.
- Add failing tests for A2 root uid facts.
- Add failing tests for a handoff whose `to_phase` is not in `phases`.
- Patch `depone/agent_fabric/isolation.py` so uid-model root runner facts fail
  closed. Keep container model behavior separate.
- Patch `depone/verify/engine.py` so imported capture manifests do not raise
  report-level assurance unless they carry a trusted observer provenance marker
  that this wave can verify. Until that marker exists, cap report assurance at
  A0 for generic imported captures.
- Patch `depone/verify/engine.py` so unknown or orphan handoffs refute the
  report instead of vanishing.

Acceptance:
- Forged evidence-dir PoC returns `decision=fail` or `assurance=A0-claims-only`.
- Root uid facts return `boundary=False`.
- Unknown handoff phase returns `verdict=refuted`.

### Slice B: Tool and Shell Boundary Soundness

Owner lane: adapter/compile.

Tasks:
- Add tests that `resolve_toolbelt` returns disjoint concrete allowed/forbidden
  sets for Codex, Claude Code, OpenCode, and shell harnesses.
- Patch `depone/compile/tool_mappings.py` to compute forbidden concrete tools
  from the concrete tool universe minus the concrete allowed set.
- Add tests that shell-lane allowlists reject `bash -c codex ...`, `sh -c`,
  `python -c`, `env codex`, and `npx codex`.
- Patch `depone/agent_fabric/team_shell_lane_launch.py` to reject interpreter
  trampolines and prohibited executable tokens in argv.

Acceptance:
- No allowed/forbidden overlap for resolved toolbelts.
- Shell-lane prohibited-agent bypass examples raise
  `ERR_TEAM_SHELL_LANE_AGENT_EXECUTABLE_BLOCKED`.

### Slice C: Team Ledger Changed-File Soundness

Owner lane: orchestration.

Tasks:
- Add a regression test where two passed lanes have worktree receipts that both
  changed the same file but one lane under-reports `touched_files`.
- Patch `depone/agent_fabric/team_ledger.py` so passed lanes require worktree
  receipt coverage when present and enforce `changed_files` as the observed
  source for overlap detection.
- Keep the result fail-closed: if a passed lane has a worktree receipt, its
  normalized `touched_files` must equal the receipt's normalized
  `changed_files`, or the verdict blocks.

Acceptance:
- Under-reported changed files block with a specific team-ledger error.
- Overlaps derived from changed files require a merge receipt.

## Review Lane

Owner lane: reviewer/verifier.

Tasks:
- Check all changed code for overclaiming: no docs or receipts should say a
  generic imported capture is independently observed.
- Run targeted tests for the changed surfaces.
- Run `python3 scripts/check_contract.py --tier changed`.
- Run `python3 scripts/dwm.py doctor` if changed-tier passes or if failure
  needs environment separation.

## Suggested Targeted Tests

```bash
python3 -m unittest \
  tests.test_agent_fabric_capture_bridge \
  tests.test_agent_fabric_report_assurance \
  tests.test_agent_fabric_tool_mappings \
  tests.test_agent_fabric_team_shell_lane_launch \
  tests.test_agent_fabric_team_ledger \
  -v

python3 -m depone agent-fabric-observe --self-test
python3 -m depone team-shell-lane-launch --self-test
python3 -m depone team-ledger --self-test
python3 scripts/check_contract.py --tier changed
```

## Stop Condition

Stop when all accepted slices are implemented, tests pass, changed-tier contract
passes, and the final report lists any intentionally deferred issues. If a
slice requires a larger trust-model migration than this wave can safely absorb,
record a blocked finding and keep the implemented fixes narrow.
