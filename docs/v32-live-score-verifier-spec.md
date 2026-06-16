# V32 Live Score Verifier Spec

Status: implemented first live score verifier bridge in
`scripts/dwm_live_score.py`.

## Research and Prior Art

V31 records receipt judgments but deliberately does not score benchmark success.
V32 adds a task-specific verification bridge. It compares a V31 judgment, a V30
receipt, and an explicit verification spec before writing score evidence.

## Product Position and Non-Goals

V32 records live score evidence. It does not execute adapters, aggregate suite
scores, or claim benchmark success. A zero returncode is insufficient unless the
verification spec also matches the receipt hashes and task identity.

Non-goals:

- do not execute live model attempts,
- do not aggregate benchmark scores,
- do not infer task success from returncode alone,
- do not accept stale judgment or receipt artifacts,
- do not publish model-quality claims.

## Workflow Architecture

`scripts/dwm_live_score.py` reads:

- V31 `judgment.json`,
- V30 `receipt.json`,
- a verification spec with expected task id, adapter, returncode, stdout hash,
  and stderr hash.

It writes:

- `score.json`,
- `status.json`,
- `summary.json` for manifest suites.

## Execution Model

```bash
python scripts/dwm_live_score.py score --judgment-dir out/live-receipt-judgments/<judgment_id> --receipt-dir out/live-receipts/<receipt_id> --verification verification.json --out out/live-scores/<score_id>
python scripts/dwm_live_score.py --manifest fixtures/v32/manifest.json --out out/live-scores/v32-final
```

Every output directory is guarded by a live-score ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_LIVE_SCORE_ARTIFACT_MISSING` when judgment or receipt artifacts are
  missing,
- `ERR_LIVE_SCORE_STALE_JUDGMENT` when expected judgment hash does not match,
- `ERR_LIVE_SCORE_TASK_MISMATCH` when verification task or adapter does not
  match the judgment,
- `ERR_LIVE_SCORE_HASH_MISMATCH` when judgment and receipt hashes drift,
- `ERR_LIVE_SCORE_VERIFICATION_INVALID` when the verification spec is malformed.

## Evaluation Fixtures

`fixtures/v32/manifest.json` covers:

- positive: matching verification spec records a passed score,
- positive: mismatched returncode records a failed score without blocking,
- negative: stale judgment hash is blocked,
- negative: task mismatch is blocked,
- negative: receipt hash mismatch is blocked,
- negative: missing judgment artifact is blocked,
- negative: malformed verification spec is blocked.

## Release Plan

V32 is the first scoring bridge. V33 can aggregate multiple V32 `score.json`
artifacts only after each score carries judgment, receipt, and verification-spec
hashes.
