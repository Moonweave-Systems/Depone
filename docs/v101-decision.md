# V101 Decision

Decision: keep.

Command used to verify the promotion route planner:

```bash
python scripts/dwm_promotion_route.py --manifest fixtures/v101/manifest.json --out out/promotion-routes/v101-final
```

Canonical command:

```bash
python scripts/dwm_promotion_route.py route --evidence out/promotion-evidence/v100-canonical/promotion-evidence.json --out out/promotion-routes/v101-canonical
```

Generated suite values:

- `suite_id`: `v101-promotion-route`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

The accepted suite covers dogfood acquisition routing, README publication
human gate routing, blocked promotion evidence, and public benchmark overclaim
blocking.

The V101 promotion route planner does not execute commands, publish assets,
edit README graphs, or grant public benchmark publication approval.
