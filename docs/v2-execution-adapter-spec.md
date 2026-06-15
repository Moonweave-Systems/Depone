# V2 First-Slice Execution Adapter Spec

Status: release candidate; fixture gate keep
Date: 2026-06-14

## Purpose

V1 compiles an activated `workflow.plan.json` into one deterministic
first-slice packet. V2 should make that packet useful for real automation by
executing exactly one trusted first slice through a controlled backend and
recording evidence.

V2 is an execution adapter, not a full workflow runtime. It does not advance to
later phases, coordinate teams, merge parallel work, or decide that the whole
workflow is complete.

## Product Position

| Layer | Responsibility | V2 stance |
| --- | --- | --- |
| V0.5 evaluator | validate source plan contract | dependency |
| V1 compiler | create packet, prompt, gates, resume state | required input |
| V2 adapter | execute one trusted packet and collect evidence | implement now |
| V2.5 loop | review and repair one failed or incomplete execution | defer |
| V3 runtime | advance through multiple packets | defer |
| External runtimes | Codex CLI, OMX, or future workers | optional backends |

V2 should be able to use external runtimes without inheriting their state model.
The adapter remains responsible for checking packet trust, risk gates, worktree
isolation, evidence capture, and resume behavior.

## Goals

- Accept only a V1 run directory that passes `compile_workflow.py --resume`.
- Refuse execution when the packet is blocked by risk gates.
- Execute only `packets/001-first-slice.prompt.md`.
- Support a dry evidence mode that prepares execution artifacts without running
  a backend.
- Support at least one real local backend for smoke testing.
- Isolate write-capable execution in a git worktree.
- Preserve every execution attempt as append-only evidence.
- Record backend command, prompt hash, packet hash, stdout/stderr or
  transcript, exit status, started/ended timestamps, git status, diff summary,
  and verification outputs.
- Derive status from evidence and verification, not from model claims.
- Provide deterministic self-tests and a fixture manifest.

## Non-Goals

- Do not execute a packet whose V1 resume state is stale.
- Do not bypass V1 risk gates.
- Do not execute shell snippets extracted from the plan as a separate command
  language.
- Do not compile or execute later workflow phases.
- Do not merge worktree changes into the source branch.
- Do not push, publish, deploy, install dependencies, access secrets, run paid
  APIs, rewrite history, delete files, or send external messages without an
  explicit human gate.
- Do not require OMX for V2 to pass core tests.
- Do not build a daemon, dashboard, or persistent service.

## Command Contract

V2 should add one stdlib-only script unless a later implementation decision
splits backend-specific adapters:

```bash
python scripts/execute_packet.py --run out/v1/<run_id> --mode dry-run
python scripts/execute_packet.py --run out/v1/<run_id> --backend codex-cli --worktree <name>
python scripts/execute_packet.py --run out/v1/<run_id> --backend codex-cli --worktree <name> --timeout-seconds 120
python scripts/execute_packet.py --run out/v1/<run_id> --backend omx --worktree <name> --emit-only
python scripts/execute_packet.py --resume out/v1/<run_id>
python scripts/execute_packet.py --manifest fixtures/v2/manifest.json --out out/v2/<suite_id>
python scripts/execute_packet.py --self-test
```

Mode semantics:

- `--mode dry-run`: validate packet trust and gates, then write an execution
  brief and attempt metadata without launching a backend.
- `local-shell`: manifest-only fixture backend. It is not a public `--run`
  backend in V2 and must not be used to interpret arbitrary plan commands.
- `--backend codex-cli`: launch the local `codex` command with the first-slice
  prompt as input, writing the last message transcript when available.
- `--backend omx --emit-only`: emit an OMX launch brief and exact command, but
  do not execute it in V2 unless a later fixture proves the environment contract.
- `--resume`: recompute V1 trust, inspect existing attempts, update only V2
  status/resume files, and never rewrite prior attempts.
- `--manifest`: run only the trusted `fixtures/v2/manifest.json` public fixture
  suite and write a deterministic summary.
- `--self-test`: run positive and negative in-memory cases.

The fixture gate uses deterministic local-shell and Codex fixture commands so CI
does not depend on a live model. Live Codex execution is supported as an
optional smoke path, while OMX remains emit-only until a later slice proves that
environment contract.

## Trust Preconditions

Before any backend launch, V2 must:

1. resolve the V1 run directory under repo-local `out/v1/`,
2. reject symlinked run paths and symlinked leaf files it will read or write,
3. run the same resume checks as `compile_workflow.py --resume`,
4. require V1 status to be resumable and not stale,
5. require packet status to be `ready`,
6. require approval state to contain no blocked risk gates,
7. require `packets/001-first-slice.packet.json` and `.prompt.md` hashes to
   match `run.json`, and
8. write V2 evidence only under repo-local `out/v2/` or a V1-owned run
   subdirectory reserved by the spec.

If any precondition fails, the adapter must write no attempt record. It may
write only a V2 status file that names the invalidator code.

## Worktree Policy

Write-capable execution must happen outside the source checkout.

Rules:

- `--worktree <name>` is required for write-capable backends.
- the adapter creates or reuses a deterministic worktree root under
  `../<repo>.dwf-worktrees/<name>` unless the user supplies an explicit
  approved path in a future version.
- the adapter creates detached worktrees so reruns do not reset named branch
  refs.
- any dirty existing worktree blocks execution in V2.
- V2 never merges, rebases, pushes, force-pushes, or deletes worktrees.
- read-only plans may run in dry mode without a worktree.

## Attempt Artifacts

Each execution attempt gets a zero-based 4-digit ID:

```text
out/v2/<run_id>/
├── .execute_packet-owned.json
├── attempt-contracts.json
├── status.json
├── resume.md
└── attempts/
    └── 0000/
        ├── attempt.json
        ├── execution-brief.md
        ├── prompt.md
        ├── backend-command.json
        ├── stdout.txt
        ├── stderr.txt
        ├── transcript.md
        ├── git-status.txt
        ├── git-diff-summary.txt
        ├── verification.json
        └── hashes.json
```

`stdout.txt`, `stderr.txt`, and `transcript.md` are backend-dependent. Missing
files must be represented as explicit `null` paths in `attempt.json`, not
silently omitted.

`attempt-contracts.json` is the parent-level resume trust anchor for each
attempt. It records the attempt identity, status contract, command digest,
verification digest, and `hashes.json` digest so coherent rewrites inside an
attempt directory invalidate resume.

## Status Model

V2 status values:

- `not-started`: no attempt exists.
- `prepared`: dry-run evidence exists.
- `running`: reserved for future long-running execution; V2 should avoid
  leaving this status after process exit.
- `executed`: backend exited successfully, but verification has not passed.
- `verified`: backend exited successfully and all required verification passed.
- `blocked`: risk gate, stale packet, dirty worktree, missing backend, or human
  approval requirement prevents execution.
- `failed`: backend ran and exited unsuccessfully, or verification failed.
- `invalid`: evidence or trust metadata is malformed.

`verified` applies only to the first slice, never to the whole workflow.

## Verification

V2 verification is packet-scoped.

The adapter may run verification commands only when they are explicitly listed
in the V1 handoff schema and are allowed by risk gates. The first implementation
may instead run only manifest-scoped verification commands for deterministic
fixtures and record plan-derived checks as pending manual checks.

Verification records must include:

- command or check ID,
- whether it ran automatically or was recorded as manual,
- stdout/stderr paths when run,
- exit code,
- hash of the checked diff or artifact,
- final result: `pass`, `fail`, `skipped`, or `manual-required`.

At least one falsifiable verification record is required before status can be
`verified`.

## Backend Contracts

### Dry Run

Dry run writes:

- execution brief,
- prompt copy,
- backend command preview,
- trust precondition report,
- pending verification records.

It must not create a worktree, run Codex, or mutate source files.

### Local Shell

The local-shell backend is for deterministic fixtures.

It may run only commands defined inside the V2 fixture manifest, not commands
from arbitrary workflow plans. This prevents V2 tests from accidentally
becoming a general shell execution layer.

### Codex CLI

The Codex backend launches the installed `codex` command with the prompt text.

Current release-candidate evidence:

- exact command argv,
- transcript or stdout/stderr,
- exit code,
- post-run git status and diff summary.

If Codex authentication fails, V2 records `blocked` with a backend-auth
invalidator rather than treating the workflow as failed.

Slice 4 supports deterministic fixture commands for Codex backend tests. Those
fixture commands are allowed only through `fixtures/v2/manifest.json`; ordinary
CLI use resolves and launches the installed `codex` binary.

### OMX

The OMX backend starts as emit-only.

V2 should write:

- the recommended `omx` command,
- worktree name,
- prompt handoff path,
- risk and gate summary,
- exact manual launch instructions.

Actual OMX execution belongs to a later adapter fixture once the repo can prove
that installed OMX, Codex authentication, tmux/worktree behavior, and output
capture are deterministic enough.

## Error Codes

V2 must use structured error records. Required initial codes:

- `ERR_EXEC_OUTSIDE_REPO`
- `ERR_EXEC_UNTRUSTED_V1_RUN`
- `ERR_EXEC_STALE_PACKET`
- `ERR_EXEC_BLOCKED_RISK`
- `ERR_EXEC_DIR_SYMLINK`
- `ERR_EXEC_LEAF_SYMLINK`
- `ERR_EXEC_WORKTREE_REQUIRED`
- `ERR_EXEC_WORKTREE_DIRTY`
- `ERR_EXEC_BACKEND_UNAVAILABLE`
- `ERR_EXEC_BACKEND_AUTH`
- `ERR_EXEC_BACKEND_FAILED`
- `ERR_EXEC_VERIFY_FAILED`
- `ERR_EXEC_ATTEMPT_MALFORMED`
- `ERR_EXEC_MANIFEST_REQUIRED_FAILED`

## Fixtures

Add `fixtures/v2/manifest.json` plus fixture plans or run fixtures.

V2 manifest schema:

- each fixture has `id`, `type`, `plan`, expected status fields, and optional
  backend-specific config.
- `required` defaults to true; required defaults to true is the manifest
  default even when the field is omitted.
- optional fixture failures increment `failed` but may leave the suite
  `decision: "keep"` when all required fixtures pass and none are skipped.
- `local-shell`, Codex fixture commands, and manifest-scoped verification
  commands are test-fixture inputs, not public command-runner inputs. Public
  `--manifest` is limited to `fixtures/v2/manifest.json`, and fixture command
  execution is limited to approved release-fixture snippets.

Implemented release fixture IDs:

- `dry-run-ready-readonly`
- `dry-run-blocked-risk`
- `dry-run-stale-v1-prompt`
- `dry-run-stale-v1-source`
- `resume-clean`
- `resume-malformed-attempt`
- `local-shell-success`
- `local-shell-failure`
- `local-shell-verification-pass`
- `local-shell-verification-fail`
- `codex-cli-fixture-success`
- `codex-cli-auth-blocked`
- `codex-cli-worktree-required`
- `missing-backend-blocked`
- `worktree-required-for-write`
- `dirty-worktree-blocked`
- `dangerous-fixture-command-blocked`
- `dangerous-verification-command-blocked`
- `attempts-append-only`
- `manifest-required-failure`
- `required-default-omitted`
- `optional-failing-fixture`

The manifest summary may record `decision: "keep"` only when every required
fixture passes and none are skipped.

## Release Criteria

V2 is releasable when:

- `python scripts/compile_workflow.py --self-test` still passes.
- `python scripts/compile_workflow.py --manifest fixtures/v1/manifest.json --out
  out/v1/final` still records `decision: "keep"`.
- `python scripts/execute_packet.py --self-test` passes.
- `python scripts/execute_packet.py --manifest fixtures/v2/manifest.json --out
  out/v2/final` records `decision: "keep"`.
- a manual smoke reuses the ready V1 run generated by the V2 manifest command,
  performs a V2 dry run, and records no source checkout mutation.
- a manual smoke reuses the blocked V1 run generated by the V2 manifest command
  and proves a blocked V1 packet cannot execute.
- release text and whitespace checks pass.
- `docs/v2-decision.md` records the exact manifest command and generated
  summary values.

V2 release candidate is checkable with:

- `python scripts/execute_packet.py --self-test`
- `python scripts/execute_packet.py --manifest fixtures/v2/manifest.json --out
  out/v2/final`
- ready manual smoke:
  `python scripts/execute_packet.py --run
  out/v1/v2-final-dry-run-ready-readonly --out out/v2/v2-ready-smoke`; the
  attempt must record `repo_tracked_diff_unchanged: true`.
- blocked smoke reuses the V1 run generated by the V2 manifest command:
  `python scripts/execute_packet.py --run
  out/v1/v2-final-dry-run-blocked-risk --out
  out/v2/v2-blocked-smoke-risk`; it must refuse with `ERR_EXEC_BLOCKED_RISK`
  and create no attempt.
- optional live smoke:
  `python scripts/compile_workflow.py --plan
  fixtures/v1/plans/ready-readonly.workflow.plan.json --out
  out/v1/codex-live-smoke` then
  `python scripts/execute_packet.py --run out/v1/codex-live-smoke --backend
  codex-cli --worktree codex-live-smoke --out out/v2/codex-live-smoke
  --timeout-seconds 120`

The V2 fixture keep gate uses Codex `fixture-command` mode and does not exercise the installed-codex path.
Installed Codex path coverage remains optional live smoke evidence until a later
release gate can depend on local auth.

## Implementation Slices

1. Add V2 script skeleton, structured errors, canonical hashing, output
   sentinels, and dry-run self-tests. Done in slice 1.
2. Implement V1 trust preconditions by invoking or sharing V1 resume logic.
   Done in slice 1.
3. Implement V2 output tree and append-only attempt records. Done in slice 1.
4. Add local-shell fixture backend for deterministic success/failure evidence.
   Done in slice 2.
5. Add worktree policy checks without merge/push/delete behavior. Done in
   slice 2.
6. Add verification records and status derivation. Done in slice 3 for
   manifest-scoped verification commands.
7. Add Codex CLI backend with transcript capture, backend auth detection,
   configurable timeout, fixture coverage, and optional live smoke command
   support. Done in slice 4.
8. Add release-hardening fixture manifest and decision doc. Done in release
   candidate.
9. Add emit-only OMX launch brief.

## Open Questions

- Should V2 evidence live under `out/v2/<run_id>` or inside the V1 run
  directory? The default is `out/v2/<run_id>` to keep compiler artifacts
  immutable.
- Should Codex CLI execution be part of the release gate, or a manual smoke
  only? The default is manual smoke until authentication is stable.
- Should OMX remain emit-only permanently, or become an executable backend after
  a separate environment contract is proven?
- Should V2 create worktrees itself, or require the caller to provide one? The
  default is adapter-created worktrees with no merge or cleanup.
