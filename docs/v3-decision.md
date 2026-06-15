# V3 Runtime Entry Decision

Decision: keep

Command used to regenerate the V3 summary:

```bash
python scripts/run_workflow.py --manifest fixtures/v3/manifest.json --out out/v3/final
```

Generated summary values:

- `suite_id`: `final`
- `fixture_count`: 13
- `required_fixture_count`: 13
- `required_passed`: 13
- `passed`: 13
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

This decision covers V3 runtime entry only. It proves that trusted V2.5 terminal
states can advance into a deterministic runtime journal and next packet
candidate. The next phase candidate advances past the reviewed first slice only
when reviewed V2 evidence has automatic verification pass output. The
needs-human approval is not sufficient gate is covered. Stale V2.5 state,
tampered V3 artifacts, non-owned runtime directories, and malformed
`human_approved` values invalidate resume. Manual-only `review-approved`
evidence is rejected without automatic verification. An unmatched first-slice
fixture proves V3 rejects entry instead of guessing a completed phase.

This decision does not claim execution of later packets, parallel orchestration,
backend repair execution, merge or push behavior, production deployment,
external messaging, dependency installation, or fully autonomous large-task
completion.
