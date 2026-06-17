# V56 Dogfood Measure Spec

Status: implemented first measured local dogfood sample runner in
`scripts/dwm_dogfood_measure.py`.

## Research and Prior Art

V54 made it possible to record measured dogfood receipts, but it still required
an external receipt file. V56 adds the first local measurement runner so the
project can produce real evidence without inventing benchmark points.

The first sample is intentionally narrow: it records a DWM-controlled local
verification command and feeds that receipt into the V54 comparison ledger.

## Product Position and Non-Goals

V56 is a local measurement runner. It measures safe repo-local verification
commands and records them as dogfood attempt receipts.

Non-goals:

- do not run live Codex, Claude, or OpenCode task prompts,
- do not fill `direct-codex` comparison slots without a human-gated live
  attempt,
- do not publish README benchmark graphs,
- do not claim DWM beats direct agents,
- do not execute shell control syntax or arbitrary commands.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_dogfood_measure.py sample --out out/dogfood-measurements/<measurement_id>
```

It writes:

- `measurement.json`,
- `attempts.json`,
- `status.json`,
- `README.md`,
- `evidence/<task_id>-<mode>.md`,
- a linked V54 `dogfood-attempts.json` and `comparison-ledger.json`.

The default task is `release-contract-count-sync`; the default mode is
`dwm-controlled`.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_MEASURE_DIRECT_REQUIRES_GATE` when `direct-codex` is requested
  without a human-gated live attempt,
- `ERR_DOGFOOD_MEASURE_UNKNOWN_TASK` for task ids outside the dogfood corpus,
- `ERR_DOGFOOD_MEASURE_COMMAND_UNSAFE` for shell control syntax or non-local
  commands,
- `ERR_DOGFOOD_MEASURE_PATH_UNSAFE` for output path escapes.

## Evaluation Fixtures

`fixtures/v56/manifest.json` covers:

- positive: one DWM-controlled local measurement is recorded,
- negative: direct Codex mode is blocked until gated,
- negative: unknown tasks are blocked,
- negative: unsafe commands are blocked.

## Release Plan

V56 is the first real measured point, not a graph. Future slices can collect
more DWM-controlled samples and then add explicitly gated direct Codex samples
before any public comparison chart is promoted.
