# V32 Live Score Verifier Decision

Decision: keep

Command used to regenerate the V32 summary:

```bash
python scripts/dwm_live_score.py --manifest fixtures/v32/manifest.json --out out/live-scores/v32-final
```

Generated summary values:

- `suite_id`: `v32-final`
- `fixture_count`: 7
- `required_fixture_count`: 7
- `required_passed`: 7
- `passed`: 7
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V32 suite covers `score.json`, `ERR_LIVE_SCORE_ARTIFACT_MISSING`,
`ERR_LIVE_SCORE_STALE_JUDGMENT`, `ERR_LIVE_SCORE_TASK_MISMATCH`,
`ERR_LIVE_SCORE_HASH_MISMATCH`, and
`ERR_LIVE_SCORE_VERIFICATION_INVALID`.

This decision covers live score verification only. It does not claim live model
execution, live Codex task success, Claude execution, OpenCode/OMO execution,
hosted evaluation, aggregate benchmark scoring, or benchmark success.
