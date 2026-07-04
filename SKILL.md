---
name: depone
description: Compatibility entrypoint for the Depone verifier and evidence-contract engine. Use for ProofVerify-style evidence revalidation, contract/schema inspection, and plan-only gates. Do not use as the flagship Moonweave automation runner or as proof that a model verified its own work.
---

# Depone Compatibility Skill

Depone is the non-executing verifier and evidence-contract engine inside
Moonweave. The source of truth for this repository is `docs/spec.md`; this skill
text is a compatibility surface derived from that spec.

Use this skill when the user or host agent needs to:

- inspect or validate a workflow/evidence contract,
- re-check existing evidence bytes,
- explain why evidence is A0, A1, A2, blocked, refuted, or inconclusive,
- prepare a plan-only gate before execution,
- call the `depone` CLI for verifier/developer workflows.

Do **not** use this skill as the final Moonweave product surface. The planned
user-facing Moonweave skills are:

| Skill | User intent |
| --- | --- |
| `ProofPlan` | Plan a workflow without running workers. |
| `ProofRun` | Run through witnessd, emit evidence, then verify when possible. |
| `ProofVerify` | Re-check existing evidence offline. |
| `ProofFlow` | Continue long-running work behind evidence gates. |

## Core rule

```text
Depone verifies; witnessd executes; Moonweave exposes the workflow.
```

If the task needs worker spawn, retry, session ownership, active worktree
mutation, Codex/Claude/OpenCode execution, or team orchestration, hand it to
witnessd or the Moonweave wrapper. If the task needs to decide what evidence
bytes support, use Depone.

## Safe Depone tasks

1. Restate the evidence or contract being checked.
2. Identify the exact files or byte artifacts involved.
3. Validate schema and canonical hashes.
4. Re-derive the verdict from the artifacts.
5. Report the exact status without upgrading it.

Allowed status language:

```text
A0-claims-only
A1-local-observed
A2-isolated-observed
blocked
refuted
inconclusive
pass
```

Do not print standalone success-theater labels such as `VERIFIED`, `DONE`, or
`COMPLETE` as the source of truth. If verification has not run, say
`evidence-pending`.

## Common commands

```bash
python -m depone doctor --json
python -m depone validate plan.json --json
python -m depone evidence-ingest ...
python -m depone evidence-chain ...
python -m depone team-ledger ...
python -m depone next --evidence-dir <dir> --out evidence-next.json --json
```

Compatibility/demo commands such as `demo`, `observe`, `run`/`evidence-run`,
`advance`, and internal `agent-fabric-*` surfaces may exist for fixtures and
legacy automation. They are not the canonical Moonweave end-user skill surface.
