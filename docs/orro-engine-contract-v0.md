# ORRO Engine Contract v0

This is the verifier-authoritative contract for ORRO engine boundaries.

```text
Depone verifies; witnessd executes; ORRO exposes the workflow.
```

## Engine Responsibilities

| Engine/surface | Responsibility | Forbidden |
| --- | --- | --- |
| Depone | Verify persisted evidence bytes and emit verdicts. | Execute workers, run recipes, call MCP/live APIs, approve merge, or raise assurance from prose. |
| witnessd | Execute `proofrun` and team lanes, emit evidence artifacts, delegate `proofcheck` to Depone. | Issue final trust or duplicate Depone verifier logic. |
| ORRO | Expose the workflow, package wrapper context, guide users through gates. | Become a third engine or make wrapper artifacts proof. |

## Artifact Classes

| Artifact | Class | Trust rule |
| --- | --- | --- |
| `repo-profile.json` | intent/wrapper context | Scout/context selection, not execution proof. |
| `context-pack.json` | intent/wrapper context | Selected context, not proof of sufficiency. |
| `sealed-plan.json` | intent | Runtime plan context, not proof. |
| `workflow-plan.json` | intent | Workflow plan is not proof. |
| `workflow-plan-binding.json` | wrapper context | Binding/context, not proof. |
| `role-lane-plan.json` | intent | Executable intent, not proof. |
| `role-lane-plan-binding.json` | wrapper context | Binding/context, not proof. |
| `workflow-role-dispatch.json` | wrapper context | Role dispatch is context, not proof. |
| `team-ledger.json` | execution evidence | Candidate execution evidence Depone may verify. |
| `team-ledger-verdict.json` | verifier output | Local runtime verdict; not a substitute for explicit proofcheck handoff gate. |
| `verification-recipe.json` | intent | Recipe is intent; Depone must not execute it. |
| `verification-receipt.json` | execution evidence | Evidence only when valid and bound to observed command results. |
| `proofcheck-verdict.json` | verifier output | Output, not an input trust root for a new proofcheck. |
| `orro-continuation-decision.json` | wrapper context | Continuation advice, not proof. |
| `orro-auto-plan.json` | wrapper context | Recommendation context, not proof. |
| `orro-auto-receipt.json` | wrapper context | Orchestration metadata, not task success. |
| `orro-auto-session.json` | wrapper context | Orchestration metadata, not task success. |
| `orro-report.json` | wrapper context | Human summary, not proof. |
| `orro-handoff.json` | human review package | Review package, not approval. |
| `orro-engine-lock.json` | readiness/distribution metadata | Version alignment metadata, not proof. |

## Trust Rules

- Workflow plan is intent, not proof.
- Role-lane plan is executable intent, not proof.
- Role dispatch is context, not proof.
- Auto artifacts are orchestration metadata, not proof.
- Report is summary, not proof.
- Handoff is review package, not approval.
- Engine-lock is distribution metadata, not proof.
- Existing proofcheck verdict is not an input trust root.
- Verification recipe is intent.
- Verification receipt is execution evidence only if valid.
- MCP/tool output is observed fact, not trust root.
- Skill text, transcripts, prose, role names, and model confidence never raise
  assurance.

## Required Gates

- Scout-only directories must not proofcheck-pass.
- Proofrun evidence must exist before proofcheck can pass.
- Handoff requires a passing bound `proofcheck-verdict.json`.
- Auto may not bypass proofcheck or handoff gates.
- Report may not upgrade status beyond observed artifacts.

## Compatibility

`Superflow`/`superflow` remains historical compatibility only:

- fixture paths,
- schema aliases,
- legacy error metadata,
- compatibility commands.

New primary public naming is ORRO/`orro`.
