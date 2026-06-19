# V92 Decision

Decision: keep.

Commands used to verify the read-only evidence oracle:

- `python scripts/dwm_evidence_oracle.py --self-test`
- `python scripts/dwm_evidence_oracle.py --manifest fixtures/v92/manifest.json --out out/evidence-oracles/v92-final`

Fixture evidence:

- `suite_id`: `v92-evidence-oracle`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

Covered blockers:

- JSON value mismatch blocks.
- Source-hash drift blocks.
- Missing artifacts block.
- Text evidence must be present when claimed.

V92 does not execute commands, create worktrees, call live adapters, fetch
network evidence, or publish benchmark claims.
