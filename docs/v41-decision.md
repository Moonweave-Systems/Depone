# V41 Benchmark Series Decision

Decision: keep

Command used to regenerate the V41 summary:

```bash
python scripts/dwm_benchmark_series.py --manifest fixtures/v41/manifest.json --out out/benchmark-series/v41-final
```

Generated summary values:

- `suite_id`: `v41-final`
- `fixture_count`: 7
- `required_fixture_count`: 7
- `required_passed`: 7
- `passed`: 7
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V41 suite covers `series.json`, V38 history generation,
`ERR_BENCHMARK_SERIES_INSUFFICIENT_SNAPSHOTS`,
`ERR_BENCHMARK_SERIES_DUPLICATE_RELEASE`,
`ERR_BENCHMARK_SERIES_DUPLICATE_REPORT`,
`ERR_BENCHMARK_SERIES_STALE_SNAPSHOT`, and
`ERR_BENCHMARK_SERIES_SOURCE_NOT_RELEASE`.

This decision covers release snapshot series construction only. It does not
claim public benchmark promotion, README publication, external benchmark
authority, model superiority, hosted evaluation, or autonomous completion.
