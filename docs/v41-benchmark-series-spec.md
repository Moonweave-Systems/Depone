# V41 Benchmark Series Spec

Status: implemented first benchmark snapshot series builder in
`scripts/dwm_benchmark_series.py`.

## Research and Prior Art

Release snapshots become useful only when they are collected into a stable,
ordered series. V40 records one snapshot. V41 scans or accepts multiple
release-grade snapshots, validates their identity, and builds the V38 history
ledger that later feeds V39 promotion.

## Product Position and Non-Goals

V41 is the release snapshot collection layer. It does not decide whether the
series is a public benchmark claim; V39 still owns promotion.

Non-goals:

- do not create benchmark reports,
- do not invent release ordering beyond release id sorting,
- do not accept duplicate release ids,
- do not accept duplicate report hashes,
- do not accept fixture or ad-hoc source kinds,
- do not publish README assets.

## Workflow Architecture

`scripts/dwm_benchmark_series.py` accepts either explicit snapshot directories
or a snapshot root. It writes:

- `series.json`,
- `status.json`,
- `README-snippet.md`,
- a V38 history directory under `out/benchmark-history/`,
- `summary.json` for manifest suites.

The series output records the ordered snapshot paths, release ids, generated
history path, trend metrics, and source hashes.

## Execution Model

```bash
python scripts/dwm_benchmark_series.py build --snapshot out/benchmark-snapshots/<snapshot_id> --snapshot out/benchmark-snapshots/<snapshot_id_2> --snapshot out/benchmark-snapshots/<snapshot_id_3> --out out/benchmark-series/<series_id>
python scripts/dwm_benchmark_series.py build --snapshot-root out/benchmark-snapshots --out out/benchmark-series/<series_id>
python scripts/dwm_benchmark_series.py --manifest fixtures/v41/manifest.json --out out/benchmark-series/v41-final
```

Every output directory is guarded by a benchmark-series ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_SERIES_INSUFFICIENT_SNAPSHOTS` when fewer than three snapshots
  are available,
- `ERR_BENCHMARK_SERIES_DUPLICATE_RELEASE` when release ids repeat,
- `ERR_BENCHMARK_SERIES_DUPLICATE_REPORT` when report hashes repeat,
- `ERR_BENCHMARK_SERIES_STALE_SNAPSHOT` when snapshot/status artifacts drift,
- `ERR_BENCHMARK_SERIES_SOURCE_NOT_RELEASE` when a snapshot is not
  release-grade.

## Evaluation Fixtures

`fixtures/v41/manifest.json` covers:

- positive: explicit snapshots produce a series and V38 history,
- positive: snapshot-root discovery produces a series,
- negative: insufficient snapshots are blocked,
- negative: duplicate release ids are blocked,
- negative: duplicate report hashes are blocked,
- negative: stale snapshots are blocked,
- negative: non-release source kind is blocked.

## Release Plan

V41 lets DWM accumulate real release snapshots into a history ledger without a
human manually selecting points. A later workflow can use V41 output as the
input to V39 promotion.
