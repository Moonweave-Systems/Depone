# Depone Spec — Superflow Verifier Contract

Status: source-of-truth spec, 2026-07-04.

One-line decision: **Depone is the non-executing verifier and evidence-contract
engine for Superflow. It is not the flagship user-facing automation skill and not
the runtime that launched the workers it judges.** Moonweave is the
publisher/account name, not the product surface.

This file is the authoritative Depone repo spec. README, CLAUDE.md, AGENTS.md,
SKILL.md, command references, release notes, and historical DWM documents are
derived or compatibility documents. If they conflict with this file, this file
wins.

---

## 1. Product boundary

Superflow has two engines and one product surface:

```text
witnessd  = executing runtime and evidence emitter
Depone    = non-executing verifier and evidence-contract authority
Superflow = user-facing product/workflow surface, published by Moonweave
```

User-facing names:

| Name | User intent | Depone role |
| --- | --- | --- |
| `superflow` | scout -> plan -> run -> evidence -> verifier summary -> handoff | Re-derive the evidence result after witnessd emits bytes. |
| `superflow scout` | read-only repo exploration | Validate any produced planning artifacts when bound into evidence. |
| `flowplan` | plan-only workflow design | Validate plan/contract shape and gates. |
| `proofrun` | precise evidence-backed execution alias | Verify the emitted evidence when called after runtime. |
| `proofcheck` | offline evidence verification | Primary Depone-facing public alias. |
| `superflow handoff` | maintainer review package | Validate handoff evidence; never approve merge. |
| `superflow skillpack` | knowledge-as-code support | Validate skillpack-lock hashes when part of evidence. |
| `superflow doctor` | readiness check | Validate declared proof artifacts only; no runtime readiness ownership. |
| `superflow auto` | continuation behind evidence gates | Revalidate current state and gate next action. |
| `superflow ultra` | future high-autonomy profile | Same verifier rules; stricter policy requirements. |

Direct `depone` CLI and `SKILL.md` usage remains a developer, verifier, CI, and
compatibility surface. It is not the final flagship user experience beside a
separate `witnessd` skill.

### 1.1 Repository and install strategy

The engine repositories stay separate:

```text
Depone   = verifier engine and evidence contract
witnessd = execution engine and evidence emitter
```

The user-facing install surface is still one product: Superflow. Normal users
should not be told to install a Depone skill and a witnessd skill separately for a
single workflow.

In the near term, the thin `superflow` command/skill may live in the witnessd
repo because Superflow starts execution and witnessd owns execution. Depone is
then consumed as a pinned verifier dependency.

A future standalone `Superflow` repository is justified only when distribution
needs it: marketplace manifests, host-specific plugin bundles, examples, product
docs, engine version locks, and end-to-end integration tests. That repo must be a
wrapper/distribution repo, not a third engine. It must not duplicate Depone
verifier logic or witnessd runtime logic.

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
- schedule and concurrency receipt validation,
- team-ledger validation,
- verification-recipe schema and receipt validation,
- repo-profile and context-pack hash binding,
- skillpack-lock validation,
- MCP/tool receipt validation as observed external facts,
- PR handoff evidence validation,
- declarative verifier policies,
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
- execute verification recipes,
- call MCP servers, SaaS systems, databases, or live monitoring APIs,
- approve merges or deployments,
- upgrade assurance from prose, model confidence, skill text, MCP output, or
  operator intent,
- present compatibility/demo execution helpers as the product UX.

If a feature needs to spawn, supervise, retry, route adapters, create active lane
worktrees, call external tools, or emit runtime evidence, it belongs in witnessd.
If a feature needs to bundle both engines for end users, it belongs in the future
Superflow wrapper.

---

## 4. Command taxonomy

All Depone commands must be classified as one of these surfaces:

| Class | Meaning | Examples |
| --- | --- | --- |
| Verifier | Stable engine calls for `proofcheck`; bytes in, verdict out. | `evidence-ingest`, `evidence-chain`, `team-ledger`, verification-receipt validation, capture/receipt validation library calls |
| Contract | Plan or evidence-contract validation without worker launch. | `validate`, `compile`, evidence-contract validators, verification-recipe schema checks |
| Gate | Non-executing next-action or preflight decisions. | `next`, non-executing preflight checks |
| Fixture/demo | Deterministic local fixture generation or compatibility workflows. | `demo`, `observe`, `evidence-substrate`, `run`/`evidence-run`, `advance`, internal `agent-fabric-*` surfaces |

Fixture/demo and compatibility commands may remain for existing automation, but
docs must label them as such. They are not the canonical Superflow user surface.

---

## 5. Verification recipes and knowledge artifacts

Depone verifies whether declared checks were actually run and whether their
receipts match the evidence. Depone does not run the checks.

Required object families:

```text
superflow-verification-recipe
superflow-verification-receipt
superflow-repo-profile
superflow-context-pack
superflow-skillpack-lock
superflow-mcp-tool-receipt
superflow-pr-handoff
```

Rules:

- A verification recipe is intent, not evidence.
- A verification receipt is evidence only when bound to a runner receipt,
  transcript/output hashes, and expected exit codes.
- A skillpack can explain domain rules but cannot raise assurance by itself.
- A skillpack-lock can prove which knowledge files were selected, not that the
  work is correct.
- Repo-profile and context-pack artifacts can prove what context was selected,
  not that the selected context was sufficient.
- MCP output is an observed external fact; Depone verifies hashes and policy
  flags, not remote truth.
- PR handoff records what evidence should accompany human review; it is not merge
  approval.
- Skill text, CLAUDE.md, AGENTS.md, MCP output, IDE terminal views, tmux panes,
  and session transcripts are not final truth unless bound into a
  verifier-recognized receipt.

---

## 6. Evidence verdict contract

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
- Out-of-region touched files, forbidden edits, failed verification receipts, and
  required merge evidence failures are refuted/blocked according to the validating
  contract.
- Depone verdict boundaries must keep `raises_assurance=false` unless a future
  contract explicitly defines a new verifier-recognized model.

---

## 7. Source-of-truth hierarchy

This repo uses this hierarchy:

1. `docs/spec.md` — this file; Depone repo source of truth.
2. Code constants and validators under `depone/agent_fabric/*` and
   `depone/verify/*` — executable contract implementation.
3. Committed fixtures and tests — revalidation evidence for the contract.
4. `docs/README.md` — documentation map and legacy policy.
5. `README.md`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md` — short derived orientation
   documents.
6. `docs/command-reference.md` — command inventory and compatibility reference.
7. Historical DWM roadmap, release, benchmark, and automation documents — context
   and implementation history only, not current product-boundary authority.

When editing docs, do not introduce a second competing product source of truth.
Update this file first, then derive summaries elsewhere.

---

## 8. Integration with witnessd and Superflow

The flagship product path is:

```text
Superflow
  -> scout creates repo-profile/context-pack/discovery-notes when useful
  -> flowplan creates/validates plan gates and verification recipes
  -> witnessd executes and emits evidence
  -> proofcheck/Depone verifies the emitted bytes
  -> Superflow prepares handoff without upgrading the verdict
```

The offline verification path is:

```text
proofcheck or depone CLI
  -> read existing evidence bytes and public key
  -> Depone re-derives the verdict
```

The plan-only path is:

```text
flowplan
  -> produce or validate a plan/contract
  -> no worker launch
```

The automation path is:

```text
superflow auto
  -> proofcheck current evidence
  -> gate the next action
  -> witnessd executes one approved step
  -> repeat only while gates pass
```

---

## 9. Development plan

Depone development should follow witnessd `SPEC3.md` when runtime waves need new
contract capability. Contract work lands here first, then witnessd consumes it.

Near-term verifier work:

1. schedule/concurrency receipt validation for W15,
2. merge-lane and conflict evidence validation for W16,
3. resume receipt validation for W17,
4. workflow-plan conformance validation for W17.5,
5. policy layer and keyless anchor validation for W20/W21,
6. published conformance kit for W22,
7. verification-recipe and verification-receipt validation,
8. skillpack-lock and repo-profile/context-pack binding,
9. MCP/tool receipt validation,
10. PR handoff evidence validation.

Every new verifier capability needs:

- schema or contract text in this file or a referenced versioned schema,
- validator implementation,
- positive fixture,
- negative fixture,
- revalidator script or test,
- witnessd integration only after the Depone contract is merged.

---

## 10. Non-goals

- Do not merge Depone and witnessd just for installation convenience.
- Do not create a third engine repo for the Superflow user surface.
- Do not expose separate end-user Depone and witnessd skills as the final UX.
- Do not duplicate witnessd runtime logic here.
- Do not duplicate Depone verifier logic in the future wrapper.
- Do not call MCP servers, SaaS systems, databases, or live monitoring APIs from
  verifier core.
- Do not treat skill text, CLAUDE.md, AGENTS.md, or MCP output as final truth
  unless it is bound into a verifier-recognized receipt.
- Do not claim keyless transparency-log trust until implemented and verified.
- Do not revive DWM Product Shell language as the current public product surface.

---

## 11. Final invariant

```text
Depone verifies; witnessd executes; Superflow exposes the workflow.
```
