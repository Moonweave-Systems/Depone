# V24 Live Benchmark Evidence Decision

Decision: keep

Command used to regenerate the V24 summary:

```bash
python scripts/dwm_live_benchmark.py --manifest fixtures/v24/manifest.json --out out/benchmarks-live/v24-final
```

Generated summary values:

- `suite_id`: `v24-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 1
- `decision`: `keep`

The accepted V24 suite covers `fixture-control` evidence capture,
`adapter-availability` skip semantics, `ERR_LIVE_BENCHMARK_CORPUS_MISSING`,
`ERR_LIVE_BENCHMARK_UNSAFE_MODE`, `ERR_LIVE_BENCHMARK_STALE_SCORE`, and
`ERR_LIVE_BENCHMARK_ADAPTER_UNAVAILABLE`.

This decision covers local live benchmark evidence capture only. It does not
claim live model execution, live Codex task execution, Claude execution,
OpenCode/OMO execution, hosted evaluation, or model quality superiority.
