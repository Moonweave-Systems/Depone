# V75 Decision

Decision: keep.

Command used to verify large workflow next-action selection:

```bash
python scripts/dwm_large_workflow_next.py --manifest fixtures/v75/manifest.json --out out/large-workflow-next/v75-final
```

Generated values:

- `suite_id`: `v75-large-workflow-next`
- `fixture_count`: 6
- `required_passed`: 6
- `decision`: `keep`
- `artifacts`: `large-workflow-next.json`, `large-workflow-next.md`, `status.json`, `summary.json`

This decision covers control-bound next-action selection, command-ready output
for read-only/evidence work, blocked dogfood control handling, source hash drift blocking, human gate handling for write-risk candidates, and overclaim blocking.
It also covers inferred command risk when a runner command incorrectly declares
only read-only/evidence risk.
It does not execute selected commands or claim external benchmark superiority.
