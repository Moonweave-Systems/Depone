# V48 Daily Operator Loop Spec

Status: implemented first daily operator loop in `scripts/dwm_daily_operator.py`.

## Research and Prior Art

V46 and V47 made long-run work resumable, but the user still needs a single
operator-facing view: what is safe to do next, what is blocked, and whether the
evidence is fresh. V48 records that daily view without executing commands.

## Product Position and Non-Goals

V48 is a read-only operator loop. It consumes dogfood corpus and queue artifacts,
then writes the next safe action and freshness summary.

Non-goals:

- do not run queued commands,
- do not create worktrees,
- do not change README assets,
- do not bypass blocked queues,
- do not infer success from stale status files.

## Workflow Architecture

`scripts/dwm_daily_operator.py` writes:

- `operator-loop.json`,
- `status.json`,
- `today.md`,
- `summary.json` for manifest suites.

The report can consume one or more V47 corpus directories and V46 queue
directories. It prefers a ready queue, otherwise reports the first blocked
queue, otherwise reports completion.

## Execution Model

```bash
python scripts/dwm_daily_operator.py today --corpus out/dogfood-corpus/<corpus_id> --out out/daily-operator/<operator_id>
python scripts/dwm_daily_operator.py today --queue out/workflow-queues/<queue_id> --out out/daily-operator/<operator_id>
python scripts/dwm_daily_operator.py --manifest fixtures/v48/manifest.json --out out/daily-operator/v48-final
```

Every output directory is guarded by a daily-operator ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_DAILY_OPERATOR_CORPUS_MISSING` when corpus artifacts are missing,
- `ERR_DAILY_OPERATOR_STALE_CORPUS` when corpus/status artifacts drift,
- `ERR_DAILY_OPERATOR_QUEUE_MISSING` when no queue can be found,
- `ERR_DAILY_OPERATOR_STALE_QUEUE` when queue artifacts are missing, stale, or
  invalid,
- `ERR_DAILY_OPERATOR_PATH_UNSAFE` when output paths are outside the owned root.

## Evaluation Fixtures

`fixtures/v48/manifest.json` covers:

- positive: ready corpus queue produces a ready daily action,
- positive: blocked queue produces a blocked daily action,
- negative: stale queue is blocked,
- negative: missing corpus is blocked,
- negative: missing linked queue is blocked.

## Release Plan

V48 makes `today.md` the operator-facing handoff for daily work. V49 can use the
same surface to expose adapter parity and auth/isolation assumptions before
attempt execution.
