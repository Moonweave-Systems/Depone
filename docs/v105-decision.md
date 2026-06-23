# V105 Decision

Decision: keep for deterministic evidence-contract verification.

Command used to verify the wedge:

```bash
python scripts/v105_verify_wedge.py --self-test
```

Recorded deterministic suite:

- `suite_id`: `v105-verify-wedge`
- `fixture_count`: 8
- `required_passed`: 8
- `decision`: `keep`

V105 proves that verification can refute missing evidence, forbidden touches,
test weakening, missing root contracts, nested control-file shadows, invalid
contracts, and wrong-schema contracts without trusting an agent final message.
