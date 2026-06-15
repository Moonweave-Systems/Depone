# V9 Human Gate Resolution Spec

Status: first slice implemented
Date: 2026-06-15

## Purpose

V9 consumes a V8 `human_gate` frontier and a structured human approval artifact.
It is the first slice where an explicit human gate can complete a runtime
workflow without pretending that a model message alone is approval.

The workflow is:

```text
V8 human_gate frontier
-> tracked human approval artifact
-> V9 resolved runtime state
```

V9 does not execute workers, merge worktrees, deploy, publish, call Codex CLI,
call OMX, or perform external actions. It only records the approval and
recomputes the next runtime frontier.

V9 writes only under owned `out/v9/` directories. It treats V8/V4/V3/V1 lineage
as read-only evidence and validates existing status snapshots, ownership
sentinels, and hashes without calling upstream resume writers.

## Workflow Design

Source plan: `docs/v9-human-gate-resolution.workflow.plan.json`.

Patterns:

- Sequential
- Resume And Cache
- Adversarial Verify

Phases:

1. Approval validation: require a tracked approval artifact under
   `fixtures/v9/approvals`.
2. Frontier validation: require an owned V8 run with read-only status/hash
   evidence reporting `frontier-ready` and `selected_phase_ids: human_gate`.
3. Human gate resolution: append `human_gate` to `completed_phase_ids`, record
   `human_approved_phase_ids`, and confirm the recomputed frontier is terminal.
4. Resume verification: recompute state, approval markdown, journal, and
   hashes.

## Command Contract

```bash
python scripts/resolve_human_gate.py --frontier out/v8/<run_id> --approval fixtures/v9/approvals/<approval>.json --out out/v9/<run_id>
python scripts/resolve_human_gate.py --resume out/v9/<run_id>
python scripts/resolve_human_gate.py --self-test
```

## Accepted Inputs

V9 accepts only:

- an owned V8 frontier directory,
- V8 status `frontier-ready`,
- V8 resume state `resumable`,
- exactly one selected phase: `human_gate`,
- a matching tracked approval JSON under `fixtures/v9/approvals`,
- approval file tracked by git,
- approval `decision: approve`,
- approval `phase_id: human_gate`,
- approval `source_v8_run_path` and `source_packet_id` matching the V8 source,
- approval `approved_outputs: human-approval.md`,
- non-empty approval attestations,
- V8, V7.5, V4, V3, and V1 ownership sentinels whose `tool`, `run_id`,
  source-path, and plan-hash metadata match the artifacts being trusted,
- V8 `review_path` provenance matching the V7.5 review and V8 source hashes,
- V4 run, V4 schedule, V3 status, and V1 plan snapshot hashes matching the V8
  frontier source hashes.

The first slice uses a narrow approval vocabulary. A valid approval must include
the exact attestation:

`no worker execution, merge, deployment, external message, secret access, or dependency installation is approved by this artifact`

Any additional attestation that contains a forbidden action term or an
authorization verb is rejected. This intentionally conservative rule keeps V9
scoped to human-gate resolution instead of broad runtime authorization.

V9 rejects:

- stale or malformed V8 artifacts,
- mismatched approval artifacts,
- rejected or deferred approval decisions,
- non-`human_gate` selected phases,
- duplicate completion of `human_gate`,
- nonterminal workflows that would require V9 to emit additional frontier
  packets,
- missing V4/V3/V1 lineage needed to recompute the final frontier,
- missing or mismatched V8/V7.5/V4/V3/V1 ownership sentinels,
- V8 frontier drift from the V7.5 reviewed source,
- V4/V3/V1 lineage drift from the hashes already recorded by V8,
- symlinked or outside-`out/v9` output paths.

## Output Model

```text
out/v9/<run_id>/
├── .resolve_human_gate-owned.json
├── run.json
├── state.json
├── hashes.json
├── human-approval.md
├── journal/0000.json
├── status.json
└── resume.md
```

`state.json` records:

- `completed_phase_ids`,
- `reviewed_phase_ids`,
- `human_approved_phase_ids`,
- `ready_phase_ids`,
- `selected_phase_ids`,
- `blocked_phases`,
- `approval_records`.

## First Slice Rules

For the dogfood result, V9 should mark `human_gate` complete and report
`workflow-complete`. This is the first point where the dogfood workflow can
honestly say no ready or blocked phase remains. The first slice rejects
nonterminal human-gate completions because it does not yet emit the next
frontier packet.

Approve path requires:

1. V8 status is `frontier-ready`.
2. V8 resume is `resumable`.
3. V8 selected frontier is exactly `human_gate`.
4. The approval artifact matches the V8 run and packet.
5. The approval decision is `approve`.
6. The approval does not authorize execution, merge, deploy, external message,
   secret access, or dependency installation.
7. V8/V7.5/V4/V3/V1 ownership sentinels exist and match the trusted artifacts.
8. V8 review provenance matches the V7.5 review.
9. V4/V3/V1 lineage hashes match the V8 frontier source hashes.
10. Generated state, approval markdown, journal, and hashes match resume
   recomputation.

## Non-Goals

- Do not execute the next packet or any worker.
- Do not call Codex CLI, OMX, subagents, network APIs, or paid APIs.
- Do not merge worktrees or modify product source files.
- Do not implement arbitrary multi-gate fan-in yet.
- Do not emit post-human-gate frontier packets yet.
- Do not accept ad hoc chat approval as runtime evidence.

## Release Criteria

The slice is `keep` only if:

- `python scripts/resolve_human_gate.py --self-test` passes,
- dogfood resolution over `out/v8/v32-semantic-dogfood` and
  `fixtures/v9/approvals/dogfood-human-approval.json` returns
  `workflow-complete`,
- clean resume returns `resume_state: resumable`,
- dogfood `human_approved_phase_ids` is `human_gate`,
- V9 requires matching V8/V7.5/V4/V3/V1 ownership sentinels before trusting
  lineage artifacts,
- V9 requires V8 review provenance to match the reviewed V7.5 source,
- V9 source hashes bind V4 run, V4 schedule, V3 status, and V1 plan snapshot,
- tampered generated state invalidates resume,
- no worker execution or runtime backend execution is introduced.

## Next Slice

After V9, the next slice can return to product packaging because the current
dogfood workflow now has an explicit, hash-bound completion path.
