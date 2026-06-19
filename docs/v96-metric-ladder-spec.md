# V96 Metric Ladder Spec

Status: implemented graph claim-level gate in `scripts/dwm_metric_ladder.py`.

## Research and Prior Art

V95 created internal readiness history. The next risk is that operators or
README copy treat that useful graph-like signal as a public benchmark. V96 adds
a Metric Ladder that says which graph level is currently supported.

## Product Position and Non-Goals

The Metric Ladder makes graph evidence useful without overclaiming. It separates:

- process progress graphs,
- operator readiness graphs,
- public benchmark graphs.

Non-goals:

- do not publish readiness history as benchmark evidence,
- do not infer public upward claims from V95 score movement,
- do not generate new README assets,
- do not run adapters, create worktrees, or use network access.

## Workflow Architecture

`scripts/dwm_metric_ladder.py` reads:

- V95 `control-deck-score-history.json`,
- optional V78 `graph-timing.json`,
- optional V39 `promotion.json`.

It emits:

- `metric-ladder.json`,
- `metric-ladder.md`,
- `status.json`.

The output names the current public level and the next benchmark gate. Public
benchmark claims remain blocked unless a benchmark promotion receipt exists.

## Execution Model

Run fixture coverage:

```bash
python scripts/dwm_metric_ladder.py --self-test
python scripts/dwm_metric_ladder.py --manifest fixtures/v96/manifest.json --out out/metric-ladders/v96-final
```

Run canonical assessment:

```bash
python scripts/dwm_metric_ladder.py assess --history out/control-deck-score-history/v95-canonical/control-deck-score-history.json --graph-timing out/graph-timing/v78-canonical/graph-timing.json --out out/metric-ladders/v96-canonical
```

## Safety and Verification Gates

V96 blocks operator readiness when V95 history is missing, stale, not ready, or
claims public benchmark status. It blocks public benchmark claims until a
promotion receipt exists.

## Evaluation Fixtures

`fixtures/v96/manifest.json` covers:

- operator readiness ready while public benchmark remains blocked,
- unsafe public claim in history,
- blocked history,
- explicit promotion receipt allowing public benchmark claim.

## Release Plan

V96 adds graph claim-level assessment to the changed-surface contract tier and
keeps README benchmark publication behind the benchmark promotion path.
