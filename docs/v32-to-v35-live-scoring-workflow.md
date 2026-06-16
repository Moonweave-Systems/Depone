# V32-V35 Live Scoring Workflow

## Objective

Turn V31 live receipt judgments into benchmark-scoring evidence without
collapsing runner returncode evidence into unsupported success claims.

## Workflow

Pattern: pipeline with adversarial verification and resumable cache keys.

1. V32 task verifier reads a V31 `judgment.json`, the matching V30
   `receipt.json`, and a task-specific verification spec.
2. V33 aggregate scorer combines V32 score artifacts only after required task
   evidence exists.
3. V34 adversarial review tries to refute aggregate score claims.
4. V35 report emits a publishable benchmark report with evidence limits.

## Workers

- `score_bridge`: owns V32 script and fixtures; writes only
  `out/live-scores/`.
- `score_aggregator`: future V33 worker; writes only aggregate score artifacts.
- `score_reviewer`: future V34 worker; separates confirmed, refuted, and
  unverified claims.
- `release_reporter`: future V35 worker; writes release-ready reports.

## Handoffs

- V31 `judgment.json` -> V32 `score.json`
- V32 `score.json` -> V33 `aggregate-score.json`
- V33 `aggregate-score.json` -> V34 `reviewed-score.json`
- V34 `reviewed-score.json` -> V35 report

## Risk Gates

- No live model execution in V32-V35.
- No benchmark success claim from returncode alone.
- Any missing, stale, or hash-drifted evidence blocks scoring.

## First Slice

V32 implements the verifier bridge. It requires expected task id, adapter,
returncode, stdout hash, and stderr hash before recording a score candidate.
