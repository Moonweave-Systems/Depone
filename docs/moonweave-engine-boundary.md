# Depone Role in the Moonweave Product Boundary

Status: product-boundary design note, 2026-07-04.

One-line decision: **Depone is the verifier and evidence-contract engine inside
Moonweave. It is not the flagship user-facing automation skill.** Users should
meet Moonweave skills such as `ProofRun`, `ProofPlan`, and `ProofVerify`; Depone
should remain the authority that re-derives verdicts from bytes.

---

## 1. Why this boundary exists

Moonweave has two engines:

```text
witnessd  = executes work and emits signed evidence
Depone    = verifies evidence bytes and owns the evidence contract
```

Those engines are intentionally separate. The separation is what lets Moonweave
say that the executor is not the same component that grants assurance. The user
experience, however, should be a single Moonweave install surface. The engine
split is an audit boundary, not a demand that end users manually operate two
repos.

---

## 2. Final product surface

The planned user-facing surface is:

| Skill | User intent | Depone role |
| --- | --- | --- |
| `ProofPlan` | Design a workflow without running workers. | Validate plan/contract shape; do not execute. |
| `ProofRun` | Run through witnessd, emit evidence, then verify when possible. | Re-derive verdict after evidence exists. |
| `ProofVerify` | Re-check existing evidence offline. | Primary engine. |
| `ProofFlow` | Continue long-running work behind evidence gates. | Revalidate current state and gate the next action. |

Direct `depone` commands remain developer, verifier, CI, and compatibility
surfaces. They should not be positioned as the main end-user skill beside a
separate `witnessd` skill.

---

## 3. Depone owns the contract

Depone remains source of truth for:

- canonical hash convention,
- capture-manifest schema,
- observer-capture shape,
- isolation boundary rules,
- runner receipts,
- signed evidence bundles,
- trusted-observer provenance,
- evidence contracts,
- team ledgers,
- verifier error codes,
- offline verdict derivation.

witnessd and the future Moonweave wrapper consume these contracts. They must not
invent verifier fields or silently reinterpret Depone verdicts.

---

## 4. Depone must not become the runtime

Verifier-core paths must not launch agent workers, call live models, mutate user
worktrees, or present execution as completed work. Depone may keep compatibility
and demo commands, but new product work should classify surfaces explicitly:

| Surface type | Allowed in Depone? | Rule |
| --- | --- | --- |
| Verifier core | yes | Bytes in, verdict out. No execution. |
| Schema/compiler helper | yes | Produces or validates contracts. No worker launch. |
| Fixture generator | yes, isolated | May create deterministic local fixtures; must be labeled as fixture/demo. |
| Runtime execution | no | Belongs in witnessd. |
| User-facing product wrapper | no | Belongs in future `moonweave-plugin`. |

If a feature needs to spawn, retry, own sessions, create worktrees for active
lanes, or call Codex/Claude/OpenCode, it belongs in witnessd or in the wrapper
calling witnessd. If a feature needs to decide whether bytes support A0/A1/A2,
blocked, or refuted, it belongs in Depone.

---

## 5. Command taxonomy

Depone commands should be documented as one of four classes:

1. **Verifier commands**: stable product engines, safe for `ProofVerify`.
   Examples: `evidence-ingest`, `evidence-chain`, `team-ledger`, verifier library
   calls over capture manifests and receipts.
2. **Contract commands**: stable planning/contract helpers, safe for `ProofPlan`.
   Examples: `validate`, `compile`, evidence-contract validation.
3. **Gate commands**: non-executing next-action or preflight gates, safe only when
   they do not launch workers.
4. **Compatibility/demo commands**: retained for existing automation or fixtures,
   not the final Moonweave user surface.

Documentation must not imply that compatibility/demo commands are the flagship
product UX.

---

## 6. Integration contract with Moonweave wrapper

The wrapper may call Depone by CLI or library, but it must preserve these rules:

- provide evidence paths and public keys explicitly,
- keep private keys out of verifier inputs,
- record the Depone version/ref in the Moonweave run summary,
- pass through Depone verdicts without renaming them into success-theater labels,
- treat verifier failure as `blocked`, `refuted`, or `evidence-pending`, not as
  runtime success.

Minimum wrapper calls:

```bash
depone evidence-ingest ...
depone evidence-chain ...
depone team-ledger ...
depone validate ...
depone next ...
```

The exact command envelope can evolve, but the rule does not: Depone consumes
bytes and emits verifier results.

---

## 7. Migration implications for this repo

1. README and agent context should describe Depone as the verifier/contract engine
   inside Moonweave, not the main automation product shell.
2. Historical DWM control-plane wording should be treated as implementation
   history unless it maps directly to contract validation or offline gates.
3. Execution-like commands should be labeled compatibility/demo unless they are
   moved to witnessd.
4. New schema capabilities still start here. witnessd cannot depend on local-only
   contract changes.
5. The future `moonweave-plugin` repository should pin a compatible Depone ref and
   call Depone for verification.

---

## 8. Final decision

Depone's strongest product value is not being another agent orchestrator. Its
strongest value is that it can say, from bytes alone, what assurance the evidence
actually supports. Moonweave should expose that value through a single product
surface while keeping Depone narrow and trustworthy.

Engineering sentence:

```text
Depone verifies; witnessd executes; Moonweave exposes the workflow.
```
