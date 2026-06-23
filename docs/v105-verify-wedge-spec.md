# V105 Verify Wedge Spec

Status: implemented deterministic verifier wedge
Date: 2026-06-23

## Purpose

V105 proves that Keelplane verification can refute false success from
harness-captured evidence, not from an agent final message. The wedge adds an
`evidence-contract.json` control file that names required evidence, command exit
expectations, allowed touched files, forbidden touched files, and test-weakening
rules.

## Contract

`keelplane.verify.evidence_contract` consumes generic evidence bundles and emits
structured errors for:

- `ERR_EVIDENCE_CONTRACT_MISSING`
- `ERR_EVIDENCE_CONTRACT_INVALID`
- `ERR_EVIDENCE_CONTRACT_SHADOWED`
- `ERR_REQUIRED_TEST_EVIDENCE_MISSING`
- `ERR_TEST_EXIT_CODE_MISMATCH`
- `ERR_FORBIDDEN_FILE_TOUCHED`
- `ERR_TEST_WEAKENED`

Root control files are exact-path controls. Nested files named
`evidence-contract.json`, `git-diff-name-only.txt`, or `git-diff.patch` are
blocked as shadow attempts.

## Command Contract

```bash
python scripts/v105_verify_wedge.py --self-test
```

The deterministic fixture suite lives under `fixtures/v105-verify-wedge/` and
covers missing test logs, forbidden file touches, test weakening, missing root
contracts, nested control-file shadows, empty contracts, wrong-schema contracts,
and a clean verified case.

## Boundaries

V105 does not execute agents, install dependencies, or trust model prose. The
verdict comes from logs, diffs, exit-code files, and root-relative control files.
