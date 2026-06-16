# V15 Runtime Review And Repair Spec

Status: implemented in `scripts/dwm_runner.py review` and `repair`.

## Research And Prior Art

DWM already has review and repair concepts for earlier slices. Once Runner can
execute real attempts, the review loop must consume runner evidence rather than
model claims.

## Product Position And Non-Goals

V15 adds runner-backed review and bounded repair.

Non-goals:

- do not run unlimited repair loops,
- do not overwrite failed attempts,
- do not accept self-review as final approval,
- do not advance unverified repairs.

## Workflow Architecture

Add:

```bash
python scripts/dwm_runner.py review --run out/v13/<runner-id> --out out/reviews/<id>
python scripts/dwm_runner.py repair --review out/reviews/<id> --out out/repairs/<id>
```

Artifacts:

- `review.json`,
- `review.md`,
- `repair-plan.json`,
- `repair-attempt.json`,
- `retry-budget.json`,
- `status.json`.

## Execution Model

Reviewers read runner evidence, git diffs, verification output, and packet
contracts. V15 verifies runner evidence hashes before producing review output.
Repairs create new repair attempt ledgers and never mutate prior evidence.

## Safety And Verification Gates

Retry budgets are hard caps. Repairs that change public API, secrets,
dependencies, database state, production deploy, history, deletion, or external
messages require human gates.

## Evaluation Fixtures

- positive: review-approved runner evidence advances to reviewed,
- positive: repair-prepared attempt stays bounded,
- negative: repeated failure stops at retry cap,
- negative: stale evidence invalidates repair.

## Release Plan

1. Connect runner evidence to review vocabulary.
2. Add repair attempt ledgers.
3. Add retry-cap fixtures.
4. Require independent reviewer approval before ingestion.
