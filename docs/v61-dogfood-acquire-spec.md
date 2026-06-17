# V61 Dogfood Acquire Spec

Status: implemented first one-command dogfood evidence acquisition loop in
`scripts/dwm_dogfood_acquire.py`.

## Research and Prior Art

V54 through V60 built the evidence chain for real dogfood comparisons:
measurement, direct receipt pairing, pair series, chart candidate, and chart
review. The missing user-facing workflow was acquisition. V61 turns that chain
into one command that can either stop with a direct receipt template or continue
through pair and series generation once a human-gated direct receipt exists.

## Product Position and Non-Goals

V61 is an acquisition loop, not a live direct Codex runner. It reduces manual
script choreography while preserving the human gate for direct Codex evidence.

Non-goals:

- do not run live Codex,
- do not fabricate direct Codex receipts,
- do not publish README benchmark graphs,
- do not bypass pair, series, chart candidate, or review gates,
- do not treat generated `out/` as source truth.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_dogfood_acquire.py acquire --task-id <task_id> --out out/dogfood-acquisitions/<acquisition_id>
```

Without `--direct-receipt`, it runs the DWM-controlled measurement and writes a
receipt template.

With a receipt:

```bash
python scripts/dwm_dogfood_acquire.py acquire --task-id <task_id> --direct-receipt direct-receipt.json --out out/dogfood-acquisitions/<acquisition_id>
```

It writes:

- `acquisition.json`,
- `acquisition.md`,
- `status.json`,
- `direct-receipt-template.json` when blocked for receipt.

It may also update:

- `measurement.json`,
- `comparison-pair.json`,
- `pair-series.json`,
- `chart-candidate.json` only when the series is graph-ready.

## Execution Model

The loop runs local DWM-controlled verification through V56, then waits for or
consumes a human-gated direct Codex receipt. It then calls existing V57, V58,
and V59 code instead of duplicating comparison logic.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_ACQUIRE_DIRECT_RECEIPT_REQUIRED` as a recorded waiting state,
- `ERR_DOGFOOD_ACQUIRE_RECEIPT_MISSING` when the supplied receipt is absent,
- `ERR_DOGFOOD_PAIR_TASK_MISMATCH` when the receipt task differs,
- downstream V57/V58/V59 errors when evidence is stale, unsafe, or overclaimed.

## Evaluation Fixtures

`fixtures/v61/manifest.json` covers:

- positive: waiting direct receipt template,
- positive: one receipt records a pair and updates a blocked series,
- positive: enough pairs records a chart candidate,
- negative: missing receipt is blocked,
- negative: task mismatch is blocked.

## Release Plan

V61 shifts the project from gate construction toward usable data acquisition.
The next slice should make the operator surface recommend the exact acquisition
command for the next missing dogfood pair.
