# V5 Controlled Worker Result Spec

Status: first slice implemented
Date: 2026-06-15

## Purpose

V5 is the first controlled worker-result slice. It consumes a trusted V4.5
dispatch bundle and executes one allowlisted fixture worker command in an owned
`out/v5/` work directory. The result is evidence, not workflow completion.

This slice proves the path:

```text
V4 scheduled packet -> V4.5 dispatch bundle -> V5 worker result evidence
```

## Command Contract

```bash
python scripts/run_worker_result.py --dispatch out/v4.5/<run_id> --out out/v5/<run_id> --fixture semantic-review
python scripts/run_worker_result.py --resume out/v5/<run_id>
python scripts/run_worker_result.py --self-test
```

## Accepted Inputs

V5 accepts only an owned V4.5 dispatch directory with:

- `.dispatch_worker-owned.json`,
- `status.json` with `status: prepared`,
- `dispatch.json`,
- `packet.json`,
- `prompt.md`,
- `hashes.json`,
- source hashes matching the dispatch bundle.

## Execution Model

The first slice supports only `--fixture semantic-review`.

The fixture command is an allowlisted Python snippet. It runs with cwd set to
`out/v5/<run_id>/work/` and writes `verification.md`. V5 captures stdout,
stderr, exit code, output metadata, and hashes.

No command from a workflow plan, prompt, packet, or dispatch bundle is executed.

## Output Model

Accepted execution writes:

```text
out/v5/<run_id>/
├── .run_worker_result-owned.json
├── run.json
├── work/
│   └── verification.md
├── result.json
├── stdout.txt
├── stderr.txt
├── hashes.json
├── status.json
└── resume.md
```

`result.json` records fixture ID, dispatch ID, packet ID, phase ID, expected
outputs, produced outputs, exit code, and status.

## Non-Goals

- Do not execute arbitrary shell.
- Do not execute Codex CLI or OMX.
- Do not spawn subagents.
- Do not write outside owned `out/v5/`.
- Do not merge worktrees.
- Do not advance V3/V4 runtime.
- Do not commit, push, install dependencies, deploy, access secrets, delete
  files, rewrite history, or send external messages.

## Resume Behavior

`--resume` recomputes source dispatch hashes, result hashes, stdout/stderr
hashes, and produced output hashes. It writes only `status.json` and
`resume.md`.

Resume returns:

- `executed` with `resume_state: resumable` when artifacts still match,
- `invalid` with `ERR_WORKER_ARTIFACT_MALFORMED` when result evidence was
  tampered,
- `blocked` when the source dispatch is no longer trusted.

## Release Criteria

The slice is `keep` only if:

- `python scripts/run_worker_result.py --self-test` passes,
- V5 dogfood over `out/v4.5/v32-semantic-dogfood` produces `verification.md`,
- clean resume is resumable,
- tampered output invalidates resume,
- execution remains fixture-only and owned-output-only.
