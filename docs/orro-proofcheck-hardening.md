# ORRO Proofcheck Hardening

Depone verifies persisted evidence bytes. It does not execute workers, run
verification recipes, call live MCP/tools, call models, mutate worktrees, approve
merge, or raise assurance from prose.

```text
Depone verifies; witnessd executes; ORRO exposes the workflow.
```

The standalone ORRO product/distribution repository is
<https://github.com/Moonweave-Systems/ORRO>. Its docs and examples are product
guidance, not verifier contract authority. Depone remains the verifier engine
and must not be duplicated there.

## Fail-Closed Rule

`depone proofcheck` must fail closed on missing, malformed, incomplete, copied,
stale, scout-only, planning-only, or wrapper-only evidence directories. A
passing result requires verifier-recognized execution evidence, not a convincing
collection of ORRO wrapper artifacts.

These inputs must not produce `pass` by themselves:

- scout-only repo-profile or context-pack artifacts,
- workflow plans,
- role-lane plans,
- workflow role dispatch,
- continuation decisions,
- auto plans, receipts, or sessions,
- reports,
- handoff packages or handoff prose,
- copied `proofcheck-verdict.json` files,
- verification recipes without valid receipts,
- MCP/tool observations without verifier-recognized execution evidence,
- model transcripts, session logs, role names, or model confidence.

## Artifact Classification

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

Depone may ignore wrapper artifacts that it does not need to verify. Ignoring
them is safe only because they are not counted as proof or assurance. If the
actual execution evidence is missing, malformed, or refuted, wrapper artifacts do
not repair it.

## Non-Execution Contract

Proofcheck reads artifacts and re-derives a verdict. It must not:

- execute a `verification-recipe`,
- launch workers,
- call MCP or live APIs,
- call models,
- repair evidence,
- write handoff packages,
- mutate the evidence directory except an explicit `--out` verdict path,
- trust a previously written verdict as input truth.

Verification recipes are intent. Verification receipts are evidence only when
they satisfy the receipt contract: non-placeholder runner receipt hash, command
result records, exit codes, output hashes, recipe binding, and no assurance
claim.

## Compatibility

New public proofcheck errors should use `ERR_ORRO_*` primary codes. Historical
`ERR_SUPERFLOW_*` names may remain as `legacy_code` metadata or compatibility
fixtures, but Superflow is not the primary ORRO-era verifier surface.

The committed negative corpus in `tests/test_orro_proofcheck_hardening.py`
guards this contract.
