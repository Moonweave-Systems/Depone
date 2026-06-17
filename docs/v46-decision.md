# V46 Long-Run Workflow Queue Decision

Decision: keep

Command used to regenerate the V46 summary:

```bash
python scripts/dwm_workflow_queue.py --manifest fixtures/v46/manifest.json --out out/workflow-queues/v46-final
```

Generated summary values:

- `suite_id`: `v46-final`
- `fixture_count`: 7
- `required_fixture_count`: 7
- `required_passed`: 7
- `passed`: 7
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V46 suite covers `queue.json`, `next-action.md`,
`ERR_DWM_QUEUE_EVIDENCE_MISSING`, `ERR_DWM_QUEUE_UNSAFE_ACTION`,
`ERR_DWM_QUEUE_VERIFICATION_FAILED`, `ERR_DWM_QUEUE_HUMAN_GATE_REQUIRED`, and
`ERR_DWM_QUEUE_STALE_STATUS`.

This decision covers queue planning and resume validation only. It does not
execute adapter commands, create worktrees, bypass human gates, or claim
autonomous completion.
