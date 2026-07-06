---
name: depone
description: Compatibility entrypoint for the Depone verifier and evidence-contract engine. Use for proofcheck-style evidence revalidation, contract/schema inspection, and plan-only gates. Do not use as the flagship ORRO runner or as proof that a model verified its own work.
---

# Depone Compatibility Skill

Depone is the non-executing verifier and evidence-contract engine inside ORRO.
The source of truth for this repository is `docs/spec.md`; this skill text is a
compatibility surface derived from that spec.
The cross-engine artifact boundary is summarized in
`docs/orro-engine-contract-v0.md`.

Moonweave is the publisher/account namespace. ORRO is the product/tool name.
`Superflow` is historical compatibility naming.

Use this skill when the user or host agent needs to:

- inspect or validate a workflow/evidence contract,
- re-check existing evidence bytes,
- explain why evidence is A0, A1, A2, blocked, refuted, or inconclusive,
- prepare a plan-only gate before execution,
- call the `depone` CLI for verifier/developer workflows.

Do **not** use this skill as the final product surface. Normal users should not
be asked to install both a Depone skill and a witnessd skill for one workflow. The
public ORRO surface should be one install and one primary skill; Depone is
consumed behind that surface as the pinned verifier engine.

The public ORRO surfaces are:

| Name | User intent |
| --- | --- |
| ORRO | Observed Run & Review Orchestrator |
| ORRO Flow | scout -> flowplan -> proofrun -> proofcheck -> handoff |
| `orro` | scout -> plan -> run -> evidence -> verifier summary -> handoff |
| `orro scout` | read-only repo exploration |
| `flowplan` | plan-only workflow design |
| `proofrun` | precise evidence-backed execution alias |
| `proofcheck` | offline evidence verification alias |
| `orro handoff` | maintainer review package bound to evidence |
| `orro skillpack` | knowledge-as-code support |
| `orro doctor` | engine/verifier/adapter/key/MCP/policy readiness check |
| `orro auto` | continuation loop behind evidence gates |
| `orro ultra` | future high-autonomy profile with stricter policies |

## Repository boundary

The engines stay in two repositories:

```text
Depone   = verifier engine and evidence contract
witnessd = execution engine and evidence emitter
```

The thin `orro` command/skill may live in the witnessd repo while the product
surface is small, because ORRO starts execution and witnessd owns execution. A
future standalone `ORRO` repo is only a wrapper/distribution repo for plugin
manifests, examples, version locks, and product docs. It must not duplicate
Depone verifier logic or witnessd runtime logic.

## Core rule

```text
Depone verifies; witnessd executes; ORRO exposes the workflow.
```

If the task needs worker spawn, retry, session ownership, active worktree
mutation, Codex/Claude/OpenCode execution, MCP calls, or team orchestration, hand
it to witnessd or the ORRO wrapper. If the task needs to decide what evidence
bytes support, use Depone.

## What proofcheck may verify

proofcheck may verify:

- capture manifests,
- observer captures,
- runner receipts,
- verification recipes and receipts,
- skillpack-lock hashes,
- repo-profile/context-pack bindings,
- MCP/tool receipts,
- team ledger and schedule receipts,
- PR handoff evidence,
- declarative policy requirements.

proofcheck must not execute worker commands, call MCP servers, inspect live SaaS
state, mutate worktrees, retry work, or infer success from skill text.

proofcheck is fail-closed. Missing directories, non-directory paths, empty
evidence directories, malformed artifacts, missing required artifacts, scout-only
planning artifacts without a verification receipt, and all-zero runner receipt
hash placeholders must be reported as `blocked`, not `pass`.

ORRO wrapper artifacts are not proof by themselves. Workflow plans, role-lane
plans, role dispatch, continuation decisions, auto plans/receipts/sessions,
reports, handoff prose, copied proofcheck verdict files, transcripts, model
confidence, and role names must not raise assurance or make proofcheck pass.

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

If verification has not run, say `evidence-pending`.

## Common commands

```bash
python -m depone doctor --json
python -m depone validate plan.json --json
python -m depone proofcheck --evidence-dir <dir> --json
python -m depone evidence-ingest ...
python -m depone evidence-chain ...
python -m depone team-ledger ...
python -m depone next --evidence-dir <dir> --out evidence-next.json --json
```

Compatibility/demo commands such as `demo`, `observe`, `run`/`evidence-run`,
`advance`, and internal `agent-fabric-*` surfaces may exist for fixtures and
legacy automation. They are not the canonical ORRO user surface.
