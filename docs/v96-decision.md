# V96 Decision

Decision: keep.

Commands used to verify the Metric Ladder:

- `python scripts/dwm_metric_ladder.py --self-test`
- `python scripts/dwm_metric_ladder.py --manifest fixtures/v96/manifest.json --out out/metric-ladders/v96-final`

Fixture evidence:

- `suite_id`: `v96-metric-ladder`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

Covered blockers:

- Readiness history public overclaim blocks.
- Blocked readiness history blocks.
- Public benchmark claims require promotion evidence.

The V96 Metric Ladder treats readiness history as a real operator metric, not a public benchmark graph.
