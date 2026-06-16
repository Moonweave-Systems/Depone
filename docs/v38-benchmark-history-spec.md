# V38 Benchmark History Spec

Status: implemented first benchmark history ledger and trend graph in
`scripts/dwm_benchmark_history.py`.

## Research and Prior Art

README trend charts are only useful when they summarize repeated measurements.
V35 produces one report, V36 turns one report into a graph artifact, and V37
publishes one graph snapshot. V38 adds the missing history layer: multiple
hash-bound `report.json.graph_metrics` snapshots can be collected into a ledger
before any README trend claim is promoted.

## Product Position and Non-Goals

V38 records DWM's own benchmark history. It is not an external benchmark, not a
model leaderboard, and not a claim that DWM is improving unless the ledger shows
that trend.

Non-goals:

- do not invent historical points,
- do not read benchmark values from markdown prose,
- do not accept stale report hashes,
- do not allow duplicate report hashes to inflate history,
- do not publish the trend graph into README automatically.

## Workflow Architecture

`scripts/dwm_benchmark_history.py` reads one or more V35 report directories and
writes:

- `history.json`,
- `status.json`,
- `trend.svg`,
- `README-snippet.md`,
- `summary.json` for manifest suites.

Each entry records the report path, report hash, label, graph metrics,
benchmark claim state, and `score_bps`.

## Execution Model

```bash
python scripts/dwm_benchmark_history.py build --report out/live-reports/<report_id> --out out/benchmark-history/<history_id>
python scripts/dwm_benchmark_history.py build --report out/live-reports/<old_id> --report out/live-reports/<new_id> --label baseline --label current --out out/benchmark-history/<history_id>
python scripts/dwm_benchmark_history.py --manifest fixtures/v38/manifest.json --out out/benchmark-history/v38-final
```

Every output directory is guarded by a benchmark-history ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_HISTORY_ARTIFACT_MISSING` when report artifacts are missing,
- `ERR_BENCHMARK_HISTORY_STALE_REPORT` when status/report files drift or an
  expected report hash does not match,
- `ERR_BENCHMARK_HISTORY_METRICS_INVALID` when graph metrics are incomplete or
  internally inconsistent,
- `ERR_BENCHMARK_HISTORY_DUPLICATE_REPORT` when a history reuses the same report
  hash,
- `ERR_BENCHMARK_HISTORY_LABEL_MISMATCH` when explicit labels do not match the
  report list.

## Evaluation Fixtures

`fixtures/v38/manifest.json` covers:

- positive: one report creates a history ledger,
- positive: two reports create a trend graph,
- negative: stale report hash is blocked,
- negative: invalid metrics are blocked,
- negative: duplicate report hashes are blocked,
- negative: missing report artifact is blocked.

## Release Plan

V38 makes the future README growth chart honest. A later slice can promote a
specific `trend.svg` into `assets/` only after enough distinct report snapshots
exist to support a meaningful trend.
