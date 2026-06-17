# V44 Candidate Review Gate Decision

Decision: keep

Command used to regenerate the V44 summary:

```bash
python scripts/dwm_benchmark_candidate_review.py --manifest fixtures/v44/manifest.json --out out/benchmark-candidate-reviews/v44-final
```

Generated summary values:

- `suite_id`: `v44-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V44 suite covers `candidate-review.json`,
`publish-checklist.md`, `ERR_BENCHMARK_CANDIDATE_REVIEW_STALE_CANDIDATE`,
`ERR_BENCHMARK_CANDIDATE_REVIEW_PROMOTION_MISSING`,
`ERR_BENCHMARK_CANDIDATE_REVIEW_HASH_MISMATCH`, and
`ERR_BENCHMARK_CANDIDATE_REVIEW_OVERCLAIM`.

This decision covers benchmark candidate review only. It does not edit README,
publish tracked assets, claim external benchmark authority, claim model
superiority, or perform autonomous release.
