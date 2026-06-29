# V127 Decision

Status: accepted. Date: 2026-06-28.

V127 closes the false-pass path in the verify engine.

Decision:

- A required claim with a present ground-truth path but no deterministic
  evaluator now resolves to `decision: "inconclusive"`, never `pass`.
- A required claim is `supported` only when a declared deterministic evaluator
  succeeds.
- A required deterministic refutation resolves to `decision: "fail"`.
- Unknown evaluators resolve to `unsupported-evaluator` and keep the report
  inconclusive.
- The legacy adversarial view remains only as an advisory rendering of claim
  evaluation state; ground-truth presence is not proof.
- Budget `max_agents` is counted from invocation records or explicit metadata,
  not filenames containing "agent".

User-facing claim corrections:

- README now describes verify as three deterministic checks plus an advisory
  ground-truth presence signal.
- README and V104 product direction now say content-addressed reports rather
  than "hash-signed" reports.
- V104 regulatory positioning no longer treats EU AI Act high-risk rules or
  Colorado's first AI Act path as 2026 forcing functions; 2026 demand is framed
  as procurement and diligence driven.

Verification:

- `python -m depone verify --self-test` covers the required unevaluated,
  supported, refuted, unsupported-evaluator, and budget invocation-count cases.
- `python scripts/check_contract.py --tier changed` remains the release
  contract gate before completion.

Boundary:

This milestone does not add a semantic adversarial verifier or cryptographic
signing. It makes the current engine honest about what it can and cannot prove.
