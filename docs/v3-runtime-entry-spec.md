# V3 Runtime Entry Spec

Status: implemented entry runtime
Date: 2026-06-15

## Purpose

V3 starts the multi-slice runtime path without claiming full autonomous workflow
execution. It consumes trusted V2.5 terminal packet states, writes a runtime
journal, and prepares the next phase candidate from the original V1 plan.

The entry runtime is the first bridge from "one packet was reviewed" to "the
workflow can decide what packet should come next."

## Command Contract

```bash
python scripts/run_workflow.py --start out/v2/<run_id> --out out/v3/<run_id>
python scripts/run_workflow.py --resume out/v3/<run_id>
python scripts/run_workflow.py --manifest fixtures/v3/manifest.json --out out/v3/final
python scripts/run_workflow.py --self-test
```

Public manifest execution is limited to `fixtures/v3/manifest.json`.

## Accepted Inputs

V3 accepts only trusted V2.5 terminal states with reviewed automatic
verification evidence:

- `review-approved`
- `repair-verified`

V3 rejects:

- `failed`
- `invalid`
- `review-pending`
- `changes-requested`
- `repair-prepared`
- `needs-human`, even with `--human-approved`, until a later slice defines a
  stronger human override contract
- unsupported status values

Rejected entry writes `status.json` and `resume.md` with
`ERR_RUNTIME_ENTRY_REJECTED`. Stale V2.5 evidence writes `ERR_RUNTIME_STALE_V25`.

## Output Model

Accepted entry writes:

```text
out/v3/<run_id>/
├── .run_workflow-owned.json
├── run.json
├── next/
│   ├── 0001.packet.json
│   └── 0001.prompt.md
├── journal/
│   └── 0000.json
├── status.json
└── resume.md
```

`next/0001.packet.json` is deterministic and hash-bound to:

- V2.5 status,
- V1 plan snapshot,
- V1 run metadata,
- accepted V2.5 state,
- selected first ready phase,
- referenced workers,
- stop conditions.

The V3 entry runtime does not execute `next/0001.packet.json`.

## Resume Behavior

`--resume` recomputes trusted V2.5 state, the V1 plan snapshot, the next packet,
the prompt, and journal hashes. It writes only `status.json` and `resume.md`.

Resume returns:

- `advanced` with `resume_state: resumable` when artifacts still match,
- `invalid` with `ERR_RUNTIME_STALE_V25` when the V2.5 source state changed,
- `invalid` with `ERR_RUNTIME_ARTIFACT_MALFORMED` when packet, prompt, or
  journal artifacts were tampered.

`--resume` also requires a matching `.run_workflow-owned.json` ownership sentinel
and a boolean `human_approved` value in `run.json`.

## Release Fixtures

`fixtures/v3/manifest.json` must cover:

- approved V2.5 state advances,
- accepted runs select the next phase after the reviewed first slice,
- manual-only `review-approved` evidence is rejected without automatic
  verification,
- unmatched first-slice output is rejected instead of guessing a completed phase,
- `changes-requested` is rejected,
- `repair-prepared` is rejected,
- `needs-human` is rejected without `--human-approved`,
- `needs-human` with `--human-approved` is still rejected until a later human
  override contract exists,
- clean resume remains resumable,
- stale V2.5 state invalidates V3 resume,
- tampered next packet invalidates V3 resume,
- tampered journal invalidates V3 resume,
- non-owned runtime directories are refused on resume,
- malformed `human_approved` values invalidate resume.

## Non-Goals

- Do not execute later packets.
- Do not spawn subagents.
- Do not merge worktrees.
- Do not claim full large-task automation.
- Do not continue through risky or ambiguous packet states without a human gate.
