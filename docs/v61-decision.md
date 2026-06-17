# V61 Decision

Decision: keep.

Command used to verify the dogfood acquisition loop:

```bash
python scripts/dwm_dogfood_acquire.py --manifest fixtures/v61/manifest.json --out out/dogfood-acquisitions/v61-final
```

The accepted suite covers `acquisition.json`, `acquisition.md`,
`direct-receipt-template.json`, measurement creation, pair recording, series
updates, chart candidate creation when enough pairs exist, missing receipt
blocking, and task mismatch blocking.

This decision does not claim live Codex execution, fabricated direct receipts,
README graph promotion, external benchmark authority, direct-agent superiority,
or generated `out/` directories as source truth.
