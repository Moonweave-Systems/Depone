# V28 Live Attempt Planner Spec

Status: implemented first live attempt planner in
`scripts/dwm_live_attempt_plan.py`.

## Research and Prior Art

V27 proves that an adapter command can be found and bound to a benchmark task.
V28 converts that smoke evidence into a command plan without executing the
adapter. This keeps the control-plane deterministic before any live model run.

## Product Position and Non-Goals

V28 is a planning gate. It prepares prompt and command artifacts only when
adapter smoke is captured. Missing adapters become structured `skipped`
evidence.

Non-goals:

- do not execute live model attempts,
- do not claim live Codex task execution,
- do not send prompts to adapters,
- do not accept shell fragments as commands,
- do not treat planned commands as completed benchmark attempts.

## Workflow Architecture

`scripts/dwm_live_attempt_plan.py` writes:

- `prompt.md`,
- `command-plan.json`,
- `status.json`,
- nested smoke evidence under `smoke/`,
- `summary.json` for manifest suites.

The command plan includes source hashes for templates, prompt text, and smoke
status.

## Execution Model

```bash
python scripts/dwm_live_attempt_plan.py plan --adapter-command codex --task-id failing-test-fix --out out/live-attempt-plans/<plan_id>
python scripts/dwm_live_attempt_plan.py --manifest fixtures/v28/manifest.json --out out/live-attempt-plans/v28-final
```

Every output directory is guarded by a live-attempt-plan ownership sentinel.

## Safety and Verification Gates

The gate blocks or skips:

- `ERR_LIVE_ATTEMPT_ADAPTER_UNAVAILABLE` when adapter smoke records an
  unavailable adapter,
- `ERR_LIVE_ATTEMPT_STALE_SMOKE` when expected template hashes no longer match,
- `ERR_LIVE_ATTEMPT_UNKNOWN_TASK` when the task is outside the benchmark
  corpus,
- `ERR_LIVE_ATTEMPT_UNSAFE_COMMAND` when the adapter command is not a bare
  executable name.

## Evaluation Fixtures

`fixtures/v28/manifest.json` covers:

- positive: captured smoke produces a planned command,
- skip: missing adapter produces skipped evidence,
- negative: stale smoke/template hash is blocked,
- negative: unknown task is blocked,
- negative: unsafe command is blocked.

## Release Plan

V28 is the last planned-only gate before optional live execution. A later runner
can consume `command-plan.json`, execute it in an isolated workspace, and feed
the result back into the V26-style attempt ledger.
