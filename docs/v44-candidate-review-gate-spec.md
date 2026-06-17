# V44 Candidate Review Gate Spec

Status: implemented first benchmark candidate review gate in
`scripts/dwm_benchmark_candidate_review.py`.

## Research and Prior Art

V42 creates a promotion-ready candidate, but it still should not directly edit
README assets. The missing product step is an explicit review gate that checks
the candidate against its source artifacts and blocks unsupported public claims
before V45 promotion changes tracked files.

## Product Position and Non-Goals

V44 is a pre-publish review gate. It consumes a V42 candidate and writes a
review artifact that a later README promotion workflow can trust.

Non-goals:

- do not edit README,
- do not copy or regenerate tracked assets,
- do not claim external benchmark authority,
- do not compare models or tools,
- do not bypass candidate, promotion, series, or history hashes.

## Workflow Architecture

`scripts/dwm_benchmark_candidate_review.py` reads a candidate directory and
writes:

- `candidate-review.json`,
- `status.json`,
- `publish-checklist.md`,
- `summary.json` for manifest suites.

The review checks `candidate.json` and `status.json`, reloads the referenced
promotion, series, and history artifacts, recomputes source hashes, checks the
candidate README embed against the promotion, and rejects unsupported benchmark
or model-superiority language.

## Execution Model

```bash
python scripts/dwm_benchmark_candidate_review.py review --candidate out/benchmark-candidates/<candidate_id> --out out/benchmark-candidate-reviews/<review_id>
python scripts/dwm_benchmark_candidate_review.py --manifest fixtures/v44/manifest.json --out out/benchmark-candidate-reviews/v44-final
```

Every output directory is guarded by a candidate-review ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_CANDIDATE_REVIEW_ARTIFACT_MISSING` when candidate artifacts are missing,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_STALE_CANDIDATE` when candidate/status drift,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_PROMOTION_MISSING` when promotion evidence is missing,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_SERIES_MISSING` when series evidence is missing,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_HISTORY_MISSING` when history evidence is missing,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_HASH_MISMATCH` when source hashes drift,
- `ERR_BENCHMARK_CANDIDATE_REVIEW_OVERCLAIM` when proposed README text makes unsupported public claims.

## Evaluation Fixtures

`fixtures/v44/manifest.json` covers:

- positive: reviewed candidate writes `candidate-review.json`,
- negative: stale candidate is blocked,
- negative: missing promotion evidence is blocked,
- negative: hash drift is blocked,
- negative: overclaim text is blocked.

## Release Plan

V44 creates the review artifact required before README asset promotion. V45 can
consume `candidate-review.json`, but must still produce a human-readable diff
before changing tracked README assets.
