# Depone — Agent Context

Depone is the **non-executing verifier and evidence-contract engine** inside
Moonweave Superflow. It re-derives what signed/hash-bound evidence bytes actually
support. It must not become the runtime that launched the workers it is judging.

The source of truth for this repository is [`docs/spec.md`](docs/spec.md). This
file is a short agent orientation derived from that spec. If there is a conflict,
`docs/spec.md` wins.

```text
Depone verifies; witnessd executes; Moonweave Superflow exposes the workflow.
```

## Public surfaces

| Name | Meaning |
| --- | --- |
| `superflow` | flagship goal -> plan -> run -> evidence -> verifier summary |
| `flowplan` | plan-only workflow design |
| `proofrun` | precise evidence-backed execution alias |
| `proofcheck` | offline evidence verification alias |
| `superflow auto` | continuation loop behind evidence gates |
| `superflow ultra` | future high-autonomy profile with stricter policies |
| `depone` | verifier engine CLI / compatibility surface |

## Current direction

Depone should stay narrow and valuable:

- own the evidence contract,
- validate plans/contracts when no execution is required,
- verify capture manifests, receipts, isolation facts, DSSE bundles, evidence
  contracts, schedules, and team ledgers,
- emit honest `pass`, `blocked`, `refuted`, `inconclusive`, A0, A1, or A2 results
  from bytes,
- avoid presenting compatibility/demo execution helpers as the flagship product
  surface.

## Boundary rules

| Work type | Belongs here? | Rule |
| --- | --- | --- |
| Evidence schema and verifier error code | yes | Depone is the source of truth. |
| Offline evidence re-derivation | yes | Bytes in, verdict out. |
| Plan/contract validation | yes | No worker launch. |
| Next-action gate | yes, if non-executing | Gate from verified evidence only. |
| Worker spawn / retry / session / worktree runtime | no | Belongs in witnessd. |
| End-user plugin packaging | no | Belongs in future Moonweave wrapper. |

If a change needs to launch Codex, Claude, OpenCode, shell workers, own durable
sessions, retry work, or mutate active worktrees, put it in witnessd or the
Moonweave wrapper. If a change decides what assurance evidence bytes support, put
it here.

## Verify after any change

Run before claiming work is ready or opening a PR:

```bash
python scripts/check_contract.py --tier changed
python scripts/dwm.py doctor
python scripts/check_readme_quality.py README.md
```

Full contract sweep:

```bash
python scripts/check_contract.py
```

Many scripts also carry a `--self-test`; run the one for any script you touch.

## Invariants

- No external runtime dependencies for verifier core.
- Artifacts and source hashes are the source of truth.
- Keep planned work and executed work separate.
- Do not upgrade assurance from prose, model confidence, or operator intent.
- Do not add a new witnessd-facing schema field unless the Depone contract and
  tests define it first.

## Commit style

Imperative subject focused on why, not what. One commit per logical change. Do
not amend existing commits.
