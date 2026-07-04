# Depone Spec

Status: source-of-truth spec, 2026-07-04.

One-line decision: **Depone is the non-executing verifier and evidence-contract
engine for Moonweave. It is not the flagship user-facing automation skill and not
the runtime that launched the workers it judges.**

This file is the authoritative Depone repo spec. README, CLAUDE.md, AGENTS.md,
SKILL.md, command references, release notes, and historical DWM documents are
derived or compatibility documents. If they conflict with this file, this file
wins.

---

## 1. Product boundary

Moonweave has two engines and one product surface:

```text
witnessd  = executing runtime and evidence emitter
Depone    = non-executing verifier and evidence-contract authority
Moonweave = user-facing product/plugin surface
```

The planned Moonweave skills are purpose-named:

| Skill | User intent | Depone role |
| --- | --- | --- |
| `ProofPlan` | Plan a workflow without running workers. | Validate plan/contract shape and evidence gates. |
| `ProofRun` | Run through witnessd, emit evidence, then verify when possible. | Re-derive the verdict after evidence exists. |
| `ProofVerify` | Re-check existing evidence offline. | Primary engine. |
| `ProofFlow` | Continue long-running work behind evidence gates. | Revalidate state and gate the next action. |

Direct `depone` CLI and `SKILL.md` usage remains a developer, verifier, CI, and
compatibility surface. It is not the final flagship user experience beside a
separate `witnessd` skill.

---

## 2. What Depone owns

Depone owns the evidence contract:

- canonical hash convention,
- capture-manifest schema,
- observer-capture shape,
- isolation boundary rules,
- runner receipt validation,
- trusted-observer provenance validation,
- DSSE/in-toto-shaped evidence bundle validation,
- evidence-contract validation,
- team-ledger validation,
- verifier error codes,
- offline verdict derivation.

Runtimes and wrappers consume this contract. They must not invent verifier fields
or reinterpret verdicts.

---

## 3. What Depone must not own

Depone verifier-core paths must not:

- launch agent workers,
- call live models,
- own durable runtime sessions,
- retry work,
- mutate active user worktrees,
- approve merges or deployments,
- upgrade assurance from prose, model confidence, or operator intent,
- present compatibility/demo execution helpers as the product UX.

If a feature needs to spawn, supervise, retry, route adapters, create active lane
worktrees, or emit runtime evidence, it belongs in witnessd. If a feature needs
to bundle both engines for end users, it belongs in the future `moonweave-plugin`
wrapper.

---

## 4. Command taxonomy

All Depone commands must be classified as one of these surfaces:

| Class | Meaning | Examples |
| --- | --- | --- |
| Verifier | Stable engine calls for `ProofVerify`; bytes in, verdict out. | `evidence-ingest`, `evidence-chain`, `team-ledger`, capture/receipt validation library calls |
| Contract | Plan or evidence-contract validation without worker launch. | `validate`, `compile`, evidence-contract validators |
| Gate | Non-executing next-action or preflight decisions. | `next`, non-executing preflight checks |
| Fixture/demo | Deterministic local fixture generation or compatibility workflows. | `demo`, `observe`, `evidence-substrate`, `run`/`evidence-run`, `advance`, internal `agent-fabric-*` surfaces |

Fixture/demo and compatibility commands may remain for existing automation, but
docs must label them as such. They are not the canonical Moonweave user surface.

---

## 5. Evidence verdict contract

Depone re-derives a verdict from bytes. It cannot make weak evidence stronger.

Allowed assurance/verdict concepts:

```text
A0-claims-only
A1-local-observed
A2-isolated-observed
blocked
refuted
inconclusive
pass
```

Rules:

- A1 requires observer capture that satisfies the contract.
- A2 requires A1 plus a re-derived isolation boundary.
- Operator DSSE signing is report-level provenance; it does not create A3.
- Missing, stale, mismatched, or unverifiable subjects fail closed.
- Out-of-region touched files, forbidden edits, and required merge evidence
  failures are refuted/blocked according to the validating contract.
- Depone verdict boundaries must keep `raises_assurance=false` unless a future
  contract explicitly defines a new verifier-recognized model.

---

## 6. Source-of-truth hierarchy

This repo uses this hierarchy:

1. `docs/spec.md` — this file; Depone repo source of truth.
2. Code constants and validators under `depone/agent_fabric/*` and
   `depone/verify/*` — executable contract implementation.
3. Committed fixtures and tests — revalidation evidence for the contract.
4. `README.md`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md` — short derived orientation
   documents.
5. `docs/command-reference.md` — command inventory and compatibility reference.
6. Historical DWM roadmap, release, benchmark, and automation documents — context
   and implementation history only, not current product-boundary authority.

When editing docs, do not introduce a second competing product source of truth.
Update this file first, then derive summaries elsewhere.

---

## 7. Integration with witnessd and Moonweave

The final product path is:

```text
Moonweave ProofRun
  -> witnessd executes and emits evidence
  -> Depone verifies the emitted bytes
  -> Moonweave summarizes without upgrading the verdict
```

The offline verification path is:

```text
Moonweave ProofVerify or depone CLI
  -> read existing evidence bytes and public key
  -> Depone re-derives the verdict
```

The plan-only path is:

```text
Moonweave ProofPlan
  -> produce or validate a plan/contract
  -> no worker launch
```

---

## 8. Non-goals

- Do not merge Depone and witnessd just for installation convenience.
- Do not expose separate end-user Depone and witnessd skills as the final UX.
- Do not duplicate witnessd runtime logic here.
- Do not duplicate Depone verifier logic in the future wrapper.
- Do not claim keyless transparency-log trust until implemented and verified.
- Do not revive DWM Product Shell language as the current public product surface.

---

## 9. Final sentence

```text
Depone verifies; witnessd executes; Moonweave exposes the workflow.
```
