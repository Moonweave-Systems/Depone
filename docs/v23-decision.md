# V23 Harness Benchmark Decision

Decision: keep

Command used to regenerate the V23 summary:

```bash
python scripts/dwm_benchmark.py --manifest fixtures/v23/manifest.json --out out/benchmarks/v23-final
```

Generated summary values:

- `suite_id`: `v23-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted benchmark corpus covers `failing-test-fix`, `small-refactor`,
`auth-permission-audit`, `ui-render-regression`, `docs-code-consistency`, and
`multi-file-migration`.

This decision covers deterministic benchmark scoring only. It does not claim
live harness execution, live model superiority, production execution, hosted
evaluation, or autonomous completion.
