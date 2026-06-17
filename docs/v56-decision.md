# V56 Decision

Decision: keep.

Command used to verify the measured local dogfood sample runner:

```bash
python scripts/dwm_dogfood_measure.py --manifest fixtures/v56/manifest.json --out out/dogfood-measurements/v56-final
```

The accepted suite covers `measurement.json`, `attempts.json`, evidence
records, linked `dogfood-attempts.json`, linked `comparison-ledger.json`,
direct codex gate blocking, unknown task blocking, and unsafe command blocking.

This decision does not claim live adapter execution, direct Codex comparison,
direct-agent superiority, README graph promotion, or generated `out/`
directories as source truth.
