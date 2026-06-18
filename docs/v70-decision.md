# V70 Decision

Decision: keep.

Command used to verify contract timeout behavior:

```bash
python scripts/check_contract.py --self-test
```

The accepted gate covers timed-out child command failure, command name reporting, contract step progress reporting, fail-closed step timeout wiring, longer bounded timeout selection for known long self-tests, and the existing contract self-test suite.

This decision does not claim the full contract is fast, skip any release
command, or treat timeout as success.
