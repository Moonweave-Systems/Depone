# V70 Contract Timeout Spec

Status: implemented release-contract command timeout and progress reporting in
`scripts/check_contract.py`.

## Research and Prior Art

V69 exposed that the full release contract can run for a long time without
showing which child command is responsible. Silent long-running verification is
bad operator UX because it makes a real blocker look like an agent stall.

## Product Position and Non-Goals

V70 makes contract failures more diagnosable. It does not shorten the release
contract by skipping commands and does not mark the full contract as fast.

Non-goals:

- do not remove release commands,
- do not hide stdout or stderr,
- do not treat timeout as success,
- do not change generated evidence semantics.

## Workflow Architecture

`run_contract_command()` now runs child commands with a default timeout:

```bash
python scripts/check_contract.py
```

If a child command times out, the error names the command and the timeout
duration. Full contract execution also reports the current contract step and release command index to stderr. Known long self-tests can receive a longer bounded timeout instead of disabling the timeout gate.

## Execution Model

The command runner still captures stdout and stderr. Normal non-zero exits are
reported as before. Timeout exits now produce an operator-readable message
instead of allowing the parent command to wait indefinitely. Internal contract
steps also have a fail-closed timeout.

## Safety and Verification Gates

The timeout gate is fail-closed. A timed-out child command or internal contract
step fails the contract.

## Evaluation Fixtures

`python scripts/check_contract.py --self-test` now covers:

- timeout failure for a sleeping child command,
- progress-safe self-test behavior,
- longer bounded timeout selection for known long self-tests,
- existing stale-decision and fixture-smoke checks.

## Release Plan

V70 keeps the existing release command corpus intact while making future full
contract hangs diagnosable.
