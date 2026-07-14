# Depone Spec - ORRO Verifier Contract

Status: source-of-truth spec, 2026-07-04.

One-line decision: **Depone is the non-executing verifier and evidence-contract
engine for ORRO. It is not the flagship user-facing automation skill and not the
runtime that launched the workers it judges.** Moonweave is the publisher/account
name, not the product surface.

This file is the authoritative Depone repo spec. README, CLAUDE.md, AGENTS.md,
SKILL.md, command references, release notes, and historical DWM documents are
derived or compatibility documents. If they conflict with this file, this file
wins.

The cross-engine ORRO boundary is frozen in
[`docs/orro-engine-contract-v0.md`](orro-engine-contract-v0.md). That document is
derived from this verifier contract and makes the witnessd/Depone/ORRO artifact
classes explicit.

The standalone ORRO product/distribution repository lives at
<https://github.com/Moonweave-Systems/ORRO>. It owns onboarding, examples,
distribution drafts, product doctrine, and e2e smoke contracts. It does not
redefine verifier truth; this `docs/spec.md` remains authoritative for Depone
proofcheck semantics.

---

## 1. Product boundary

ORRO has two engines and one product surface:

```text
witnessd  = executing runtime and evidence emitter
Depone    = non-executing verifier and evidence-contract authority
ORRO      = user-facing product/workflow surface, published by Moonweave
ORRO Flow = scout -> flowplan -> proofrun -> proofcheck -> handoff
```

`ORRO` means **Observed Run & Review Orchestrator**. `Superflow` is the previous
product-surface name and is now historical/compatibility naming. New public docs
should use ORRO. Existing `superflow-*` schema kinds, fixture paths, or commands
may remain accepted during migration, but they are not the canonical product
name.

User-facing names:

| Name | User intent | Depone role |
| --- | --- | --- |
| `orro` | scout -> plan -> run -> evidence -> verifier summary -> handoff | Re-derive the evidence result after witnessd emits bytes. |
| `orro scout` | read-only repo exploration | Validate any produced planning artifacts when bound into evidence. |
| `flowplan` | plan-only workflow design | Validate plan/contract shape and gates. |
| `proofrun` | precise evidence-backed execution alias | Verify the emitted evidence when called after runtime. |
| `proofcheck` | offline evidence verification | Primary Depone-facing public alias. |
| `orro handoff` | maintainer review package | Validate handoff evidence; never approve merge. |
| `orro skillpack` | knowledge-as-code support | Validate skillpack-lock hashes when part of evidence. |
| `orro doctor` | readiness check | Validate declared proof artifacts only; no runtime readiness ownership. |
| `orro auto` | continuation behind evidence gates | Revalidate current state and gate next action. |
| `orro ultra` | future high-autonomy profile | Same verifier rules; stricter policy requirements. |

Direct `depone` CLI and `SKILL.md` usage remains a developer, verifier, CI, and
compatibility surface. It is not the final flagship user experience beside a
separate `witnessd` skill.

### 1.1 Repository and install strategy

The engine repositories stay separate:

```text
Depone   = verifier engine and evidence contract
witnessd = execution engine and evidence emitter
ORRO     = product/distribution/wrapper repository
```

The user-facing install surface is still one product: ORRO. Normal users should
not be told to install a Depone skill and a witnessd skill separately for a single
workflow.

In the near term, the thin `orro` command/skill may live in the witnessd repo
because ORRO starts execution and witnessd owns execution. Depone is then consumed
as a pinned verifier dependency.

The standalone `Moonweave-Systems/ORRO` repository now exists for distribution
needs: marketplace manifests, host-specific plugin bundles, examples, product
docs, engine version locks, and end-to-end integration tests. That repo is a
wrapper/distribution repo, not a third engine. It must not duplicate Depone
verifier logic or witnessd runtime logic, and its docs/examples are product
guidance rather than verifier contract authority.

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
- role-capability write-scope conformance validation,
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
If a feature needs to bundle both engines for end users, it belongs in the ORRO
wrapper.

---

## 4. Command taxonomy

All Depone commands must be classified as one of these surfaces:

| Class | Meaning | Examples |
| --- | --- | --- |
| Verifier | Stable engine calls for `proofcheck`; bytes in, verdict out. | `proofcheck`, `evidence-ingest`, `evidence-chain`, `team-ledger`, verification-receipt validation, capture/receipt validation library calls |
| Contract | Plan or evidence-contract validation without worker launch. | `validate`, `compile`, evidence-contract validators, verification-recipe schema checks |
| Gate | Non-executing next-action or preflight decisions. | `next`, non-executing preflight checks |
| Fixture/demo | Deterministic, non-executing local fixture generation. | `demo`, `evidence-substrate`, source-only internal `agent-fabric-*` surfaces |

Fixture/demo commands may remain only when they do not launch workers or run
verification commands. Runtime compatibility commands belong in witnessd, not
the Depone command table.

---

## 5. Verification recipes and knowledge artifacts

Depone verifies whether declared checks were actually run and whether their
receipts match the evidence. Depone does not run the checks.

Canonical object families:

```text
orro-verification-recipe
orro-verification-receipt
orro-repo-profile
orro-context-pack
orro-skillpack-lock
orro-mcp-tool-receipt
orro-pr-handoff
```

Compatibility aliases accepted during migration:

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
- A verification receipt is evidence only when bound to a non-placeholder runner
  receipt, transcript/output hashes, and expected exit codes.
- A complete executable ORRO proofcheck pass requires the required artifact set:
  repo-profile, context-pack, skillpack-lock, verification-recipe,
  verification-receipt, and pr-handoff. MCP/tool receipts are validated when
  present.
- `proofcheck` is fail-closed for missing, non-directory, empty, incomplete, or
  malformed evidence directories.
- A missing verification receipt blocks proofcheck. A scout-only directory is
  planning evidence and must not become execution proof.
- An all-zero runner receipt hash is a placeholder and blocks proofcheck.
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
- Existing `proofcheck-verdict.json` files are verifier outputs. They are not
  input trust roots for a new proofcheck run and must not make missing or
  malformed evidence pass.

### 5.1 Role-capability write-scope conformance

`evidence-contract.json` schema versions `v106.role_capability_write_scope` and
`v109.role_capability_write_scope` add one verdict-bearing axis:
role-capability write-scope conformance. Version `v109` strengthens that axis by
binding the git-diff observation into the signed evidence bundle. The prior
`v106` behavior, including its use in a combined `v107` contract, remains
unchanged for compatibility while witnessd adopts the new subject.

The declared write scope is read from the pre-execution `run-intent.json`
artifact, not from witnessd advisory artifacts. The contract directive is:

```json
{
  "schema_version": "v109.role_capability_write_scope",
  "role_capability_write_scope": {
    "run_intent_path": "run-intent.json",
    "bundle_path": "bundle.json"
  }
}
```

Depone re-derives conformance by checking:

- `bundle.json` carries a well-formed DSSE envelope whose signature verifies
  under the out-of-band `trusted_observer_public_key_file`; without that trust
  anchor, or when the signature is missing or invalid, Depone does not trust
  any declared subject digest.
- `bundle.json` binds the `run-intent` subject digest either to the observed
  `run-intent.json` bytes (witnessd bundle mode) or to the canonical run-intent
  object (Depone evidence-substrate compatibility mode).
- The run-intent DSSE payload decodes to the same object as the artifact
  `intent`.
- Under `v109.role_capability_write_scope`, `bundle.json` names
  `git-diff-name-only.txt` as a subject and its declared SHA-256 digest matches
  the observed file bytes. The observation is tamper-evident only when this
  digest binding is present and the bundle signature verifies under the M1
  signature gate.
- `intent.role_capability.declared_write_scope` is a non-empty list of glob
  strings.
- Every path in `git-diff-name-only.txt` is allowed by that write scope.

Write-scope matching is deterministic: a path conforms when it exactly equals a
declared pattern or `fnmatchcase(path, pattern)` is true. This glob axis does not
change the older exact-match meaning of `allowed_touched_files`.

Violations refute the verdict with Depone-owned error codes:

- `ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING`
- `ERR_ROLE_CAPABILITY_SIGNATURE_MISSING`
- `ERR_ROLE_CAPABILITY_SIGNATURE_INVALID`
- `ERR_ROLE_CAPABILITY_RUN_INTENT_MISSING`
- `ERR_ROLE_CAPABILITY_RUN_INTENT_INVALID`
- `ERR_ROLE_CAPABILITY_OBSERVATION_UNBOUND`
- `ERR_ROLE_CAPABILITY_OBSERVATION_DIGEST_MISMATCH`
- `ERR_ROLE_CAPABILITY_WRITE_SCOPE_VIOLATION`

witnessd-local `write-scope-declaration.json` remains advisory; it must not be
trusted as this verdict input.

### 5.2 Role-capability tool-call conformance

`evidence-contract.json` schema version `v107.role_capability_tool_calls`
adds a verdict-bearing MCP tool-call conformance axis.

The declared MCP tool grant is read from the pre-execution `run-intent.json`
artifact. Tool-call decision receipts are read from a verifier-recognized
bundle subject, not from witnessd-local advisory artifacts. The contract
directive is:

```json
{
  "schema_version": "v107.role_capability_tool_calls",
  "role_capability_tool_calls": {
    "run_intent_path": "run-intent.json",
    "bundle_path": "bundle.json",
    "decision_receipts_path": "tool-call-decision-receipts.json"
  }
}
```

Depone re-derives conformance by checking:

- `bundle.json` carries a well-formed DSSE envelope whose signature verifies
  under the out-of-band `trusted_observer_public_key_file`; subject digests are
  read from the verified DSSE payload rather than an unsigned duplicate.
- `bundle.json` binds the `run-intent` subject digest and the
  `tool-call-decision-receipts` subject digest.
- The run-intent DSSE payload decodes to the same object as the artifact
  `intent`.
- `intent.role_capability.declared_tools.allow` declares the exact MCP tool
  names that may be allowed.
- Every decision receipt is for an MCP canonical tool name, has contiguous
  sequence linkage, and matches the declared grant: granted MCP tools must be
  allowed, non-granted MCP tools must be denied.
- Every observed MCP tool-call has a matching sealed receipt and request hash.
- A denied MCP tool-call must not have a successful observed result.

This axis verifies sealed policy/decision/observation consistency. It does not
claim host-wide omniscience outside the signed evidence bytes, and it does not
govern Claude built-in tools or other non-MCP tool surfaces. Its trust upgrade
over write-scope is that the decision receipt represents a pre-call PEP decision
at the runtime boundary; Depone still verifies the sealed evidence, not live
runtime state.

Violations refute the verdict with Depone-owned error codes including:

- `ERR_ROLE_CAPABILITY_TRUST_ANCHOR_MISSING`
- `ERR_ROLE_CAPABILITY_SIGNATURE_MISSING`
- `ERR_ROLE_CAPABILITY_SIGNATURE_INVALID`
- `ERR_ROLE_CAPABILITY_TOOL_RECEIPTS_MISSING`
- `ERR_ROLE_CAPABILITY_TOOL_RECEIPTS_INVALID`
- `ERR_ROLE_CAPABILITY_TOOL_GRANT_MISSING`
- `ERR_ROLE_CAPABILITY_TOOL_DECISION_MISMATCH`
- `ERR_ROLE_CAPABILITY_TOOL_ALLOW_OUTSIDE_GRANT`
- `ERR_ROLE_CAPABILITY_TOOL_RECEIPT_MISSING`
- `ERR_ROLE_CAPABILITY_TOOL_DENY_EXECUTED`
- `ERR_ROLE_CAPABILITY_TOOL_REQUEST_HASH_MISMATCH`
- `ERR_ROLE_CAPABILITY_TOOL_SEQUENCE_GAP`
- `ERR_ROLE_CAPABILITY_TOOL_BUNDLE_DIGEST_MISMATCH`

witnessd-local `moonweave-tool-call-decision-advisory` remains advisory; it must
not be trusted as this verdict input.

The v106/v107 signature gate closes audit finding M1: Depone no longer accepts
role-capability subject digests without checking a signature. It establishes a
valid signature under the configured trust anchor only. It does not establish
that the anchor is independent of the executor; closing that separate M7
boundary requires an operator-provided key plus real observer/runner separation.

### 5.3 Advisory provenance consistency

`evidence-contract.json` schema version `v108.advisory_provenance` adds a
separate advisory-provenance verdict track for sealed `orro-sketch` and
`orro-trace` records. It does not add an execution-evidence axis and is never
aggregated by `validate_evidence_contract`. Its execution-verdict semantics are
`can_change_evidence_verdict=false`.

This track re-derives consistency and tamper-evidence only. A PASS means the
record's strongest advisory claim is supported by the sealed bytes and the
record matches its signed canonical digest. It does not mean a sketch chose the
right approach, a confirmed-tier root cause is correct, or the proposed fix is
sound. This is the same sealed-declaration versus sealed-observation boundary
used for role-capability conformance: Depone checks agreement, not ground truth.

The contract directive is:

```json
{
  "schema_version": "v108.advisory_provenance",
  "advisory_provenance": {
    "decision_path": "orro-trace.json",
    "bundle_path": "advisory-provenance-bundle.json"
  }
}
```

The bundle is a DSSE-signed in-toto statement with predicate type
`https://depone.dev/attestations/advisory-provenance/v108`. It binds the
decision path to the canonical SHA-256 of the decision object. A trace that
references `orro-trace-reproduction.json` also binds that fixed subject name to
the receipt's canonical SHA-256. Signature verification uses Depone's existing
out-of-band trusted observer public-key path; an evidence directory cannot
supply its own trust root.

For `orro-sketch`, Depone re-derives:

- `chosen.direction` exactly matches one `candidates[].axis` value.
- `chosen.direction` does not also appear in `rejected[].option`.
- Every `rejected[]` entry has a non-empty `why_lost`.
- The signed subject digest matches the canonical decision bytes.

For `orro-trace`, `reproduction.receipt_sha256` is the canonical hash reference
to `orro-trace-reproduction.json`. A `confirmed` root cause additionally uses
`root_cause.hypothesis_index` to select the hypothesis whose
`discriminating_probe` must appear verbatim in the receipt output, while
`reproduction.symptom` must also appear verbatim in that output. This exact
binding is the unrelated-red guard. `confirmation.rival_hypotheses_ruled_out`
must contain at least one valid hypothesis index other than the confirmed
hypothesis.

A confirmed trace requires `reproduction.red_observed=true`, a present and
hash-matching sealed reproduction receipt, output bound to both the symptom and
the confirmed probe, and at least one actively ruled-out rival. Suspected,
speculative, and `unconfirmed` traces do not require red-to-green backing, but
any non-empty receipt reference must match a present sealed receipt. The receipt
records the prior-run command, exit status, and output verbatim; Depone does not
execute that command.

Schema version `v110.advisory_provenance` strengthens only the confirmed trace
path. In addition to the v108 checks, `reproduction.execution_receipt_sha256`
must reference a signed `orro-trace-execution.json` subject shaped as a valid
runner receipt. The execution receipt binds a non-empty `command`, an
`exit_code` or failed status that records the red, and a `transcript` whose
`transcript_sha256` matches its bytes. The symptom and confirmed hypothesis's
discriminating probe must occur in that bound execution transcript, not merely
in the reproduction receipt's self-authored free-text output. Missing, invalid,
or digest-mismatched execution evidence REFUTES with
`ERR_ADVISORY_TRACE_RED_NOT_EXECUTED`. Suspected, speculative, and unconfirmed
tiers retain the v108 rules and do not require an execution receipt.

This requirement establishes only that a failing execution was recorded and
bound consistently into the signed evidence. Depone still does not re-execute
the command and does not establish that the claimed root cause is correct. The
prior `v108.advisory_provenance` behavior remains available unchanged until
producers emit the v110 execution binding.

Violations REFUTE only the advisory-provenance track with Depone-owned codes:

- `ERR_ADVISORY_PROVENANCE_CONTRACT_INVALID`
- `ERR_ADVISORY_SKETCH_CHOSEN_NOT_IN_CANDIDATES`
- `ERR_ADVISORY_SKETCH_CHOSEN_ALSO_REJECTED`
- `ERR_ADVISORY_SKETCH_REJECTED_REASON_MISSING`
- `ERR_ADVISORY_SKETCH_TAMPER`
- `ERR_ADVISORY_TRACE_CONFIRMED_UNBACKED`
- `ERR_ADVISORY_TRACE_UNRELATED_RED`
- `ERR_ADVISORY_TRACE_RIVAL_NOT_RULED_OUT`
- `ERR_ADVISORY_TRACE_RECEIPT_HASH_MISMATCH`
- `ERR_ADVISORY_TRACE_RED_NOT_EXECUTED`
- `ERR_ADVISORY_TRACE_TAMPER`

Every REFUTE message states that the claim is not re-derivable from sealed
bytes; it does not state that the approach or root cause is wrong. Committed
fixtures live under `depone/fixtures/advisory/` and are re-derived by
`scripts/revalidate_v108_advisory_provenance.py`.

### 5.4 ORRO wrapper artifact classification

ORRO wrapper artifacts may be useful context for humans, ORRO reports, and
handoff packaging, but Depone proofcheck must not count them as execution proof
or assurance by themselves.

| Artifact | Depone interpretation |
| --- | --- |
| `orro-workflow-plan` | Intent. |
| `orro-workflow-plan-binding` | Wrapper binding/context. |
| `orro-role-lane-plan` | Executable intent, not proof. |
| `orro-role-lane-plan-binding` | Wrapper binding/context. |
| `orro-role-dispatch` | Context, not proof. |
| `orro-continuation-decision` | Continuation advice, not proof. |
| `orro-auto-plan` | Recommendation context, not proof. |
| `orro-auto-receipt` | Orchestration metadata, not task success. |
| `orro-auto-session` | Orchestration metadata, not task success. |
| `orro-report` | Human-facing summary, not proof. |
| `orro-handoff` | Review package, not approval. |
| `proofcheck-verdict` | Verifier output, not an input trust root. |
| `team-ledger` | Candidate execution evidence to verify. |
| `verification-receipt` | Observed command execution evidence when valid. |
| `verification-recipe` | Intent. |

Depone does not need to deeply validate every wrapper artifact to remain safe.
It only needs to avoid treating wrapper, prose, role, transcript, model, auto, or
handoff artifacts as proof. A directory containing only scout, planning,
workflow, role-lane, auto, report, handoff, or copied verdict artifacts must fail
closed.

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
- Missing, stale, mismatched, malformed, unverifiable, or incomplete subjects fail
  closed.
- Empty evidence directories, missing required ORRO artifacts, scout-only planning
  artifacts, and placeholder runner receipt hashes are blocked, not successful
  proof.
- Out-of-region touched files, forbidden edits, failed verification receipts, and
  required merge evidence failures are refuted/blocked according to the validating
  contract.
- Depone verdict boundaries must keep `raises_assurance=false` unless a future
  contract explicitly defines a new verifier-recognized model.

---

## 7. Source-of-truth hierarchy

This repo uses this hierarchy:

1. `docs/spec.md` - this file; Depone repo source of truth.
2. Code constants and validators under `depone/agent_fabric/*` and
   `depone/verify/*` - executable contract implementation.
3. Committed fixtures and tests - revalidation evidence for the contract.
4. `docs/README.md` - documentation map and legacy policy.
5. `README.md`, `CLAUDE.md`, `AGENTS.md`, `SKILL.md` - short derived orientation
   documents.
6. `docs/command-reference.md` - command inventory and compatibility reference.
7. Historical DWM roadmap, release, benchmark, automation, and Superflow naming
   documents - context and implementation history only, not current
   product-boundary authority.

When editing docs, do not introduce a second competing product source of truth.
Update this file first, then derive summaries elsewhere.

---

## 8. Integration with witnessd and ORRO

The flagship product path is:

```text
ORRO
  -> scout creates repo-profile/context-pack/discovery-notes when useful
  -> flowplan creates/validates plan gates and verification recipes
  -> witnessd executes and emits evidence
  -> proofcheck/Depone verifies the emitted bytes
  -> ORRO prepares handoff without upgrading the verdict
```

Scout alone is intentionally planning-only. A scout artifact directory may be
useful input for planning, but `proofcheck` must block it until a later witnessd
execution step emits a verifier-recognized verification receipt and other required
execution evidence.

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
orro auto
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
10. PR handoff evidence validation,
11. ORRO object-kind migration from legacy `superflow-*` aliases.

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
- Do not create a third engine repo for the ORRO user surface.
- Do not expose separate end-user Depone and witnessd skills as the final UX.
- Do not duplicate witnessd runtime logic here.
- Do not duplicate Depone verifier logic in the future wrapper.
- Do not call MCP servers, SaaS systems, databases, or live monitoring APIs from
  verifier core.
- Do not treat skill text, CLAUDE.md, AGENTS.md, or MCP output as final truth
  unless it is bound into a verifier-recognized receipt.
- Do not claim keyless transparency-log trust until implemented and verified.
- Do not revive DWM Product Shell or Superflow language as the current public
  product surface.

---

## 11. Final invariant

```text
Depone verifies; witnessd executes; ORRO exposes the workflow.
```
