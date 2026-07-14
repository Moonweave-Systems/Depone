# Depone Command Reference

This page is a command inventory and compatibility reference. It is not the
source of truth for product direction. The authoritative Depone spec is
[`docs/spec.md`](spec.md).
The cross-engine ORRO artifact boundary is summarized in
[`docs/orro-engine-contract-v0.md`](orro-engine-contract-v0.md).

Depone commands are grouped by boundary class. New user-facing work should prefer
ORRO surfaces (`orro`, `orro scout`, `flowplan`, `proofrun`, `proofcheck`,
`orro handoff`) instead of teaching users this full engine surface. Moonweave is
the publisher/account namespace; ORRO is the product/tool name. `Superflow` is
historical compatibility naming.

---

## 1. Verifier commands

Stable engine calls for proofcheck-style workflows. These commands consume
existing artifacts and emit verifier results. They must not launch workers, call
MCP servers, inspect live SaaS state, or mutate worktrees.

```bash
python -m depone doctor --json
python -m depone proofcheck --evidence-dir ./evidence --json
python -m depone evidence-ingest ...
python -m depone evidence-chain ...
python -m depone team-ledger --ledger team-ledger.json --json
python -m depone verify plan.json --evidence ./evidence --out report.json --operator-view-out operator-view.md --json
```

Verifier commands may return `pass`, `blocked`, `refuted`, `inconclusive`, A0,
A1, or A2 according to the evidence contract. They must not upgrade assurance
from prose, model claims, skill text, MCP output, or operator intent.

`proofcheck` is fail-closed. Missing directories, non-directory evidence paths,
empty evidence directories, malformed artifacts, missing required ORRO artifacts,
scout-only planning artifacts without a verification receipt, and all-zero runner
receipt hashes produce `blocked`, not `pass`.

`proofcheck` does not trust wrapper outputs as input truth. Existing
`proofcheck-verdict.json` files, workflow plans, role-lane plans, role dispatch,
auto artifacts, reports, transcripts, model claims, and handoff prose are
context or outputs, not execution proof.

Verifier artifact families now include:

| Artifact family | Depone interpretation |
| --- | --- |
| capture/observer/runner receipts | Observed execution evidence when bound correctly. |
| verification recipes | Intended checks; not evidence by themselves. |
| verification receipts | Evidence that declared commands ran, with exit codes and output hashes. |
| repo-profile/context-pack | Planning/context-selection evidence, not proof of correctness. |
| skillpack-lock | Knowledge selection evidence, not proof of correctness. |
| MCP/tool receipts | Hash-bound external observations, not remote truth. |
| PR handoff | Human review package, not approval or merge evidence. |
| ORRO workflow/role-lane/auto/report artifacts | Wrapper context; not proof or assurance. |
| proofcheck verdict files | Verifier output; not an input trust root. |

New artifact kinds should use `orro-*`. Existing `superflow-*` kinds may remain
accepted as compatibility aliases until fixtures and code migrate.

---

## 2. Contract commands

Plan and contract helpers. These commands validate or transform declared plans;
they do not prove that work was completed.

```bash
python -m depone validate plan.json --json
python -m depone compile plan.json --target conductor --out workflow.yaml --json
```

`design` remains available as a compatibility planning helper when installed, but
ORRO's final plan-only user surface should be `flowplan`.

---

## 3. Non-executing gate commands

Gate commands inspect existing artifacts and recommend safe next action. They are
allowed only while non-executing.

```bash
python -m depone next --evidence-dir ../observer/evidence-run --previous-capture ../observer/previous/capture-manifest.json --out evidence-next.json --json
```

A gate that would spawn, retry, mutate worktrees, call MCP servers, or call a live
model belongs in witnessd or the future ORRO wrapper, not in Depone verifier-core
paths.

---

## 4. Receipt and artifact helper commands

These commands produce or inspect local artifacts without launching workers or
running verification commands.

```bash
python -m depone evidence-substrate --capture-manifest capture-manifest.json --out evidence-bundle.json --json
python -m depone team-pr-artifact --input saved-pr.json --expected-head-sha <head_sha> --out docs/team-pr-artifact/pr-artifact.json --json
python -m depone team-merge-attempt --repo . --base <base_sha> --head <head_sha> --out docs/team-merge-attempt/merge-attempt.json --json
python -m depone team-ledger-merge-receipt --lane worker-1 --lane worker-2 --file depone/agent_fabric/team_ledger.py --out team-merge-receipt.json --json
python -m depone worktree-lane-receipt --worktree ./worker-1 --base-commit <sha> --evidence-dir out/team/worker-1 --out out/team/worker-1/worktree-receipt.json --json
```

The migrated `team-launch-preflight`, `team-worktree-prep`,
`team-shell-lane-launch`, and `codex-local-capability` commands are no longer
registered by Depone. Their runtime implementations belong to witnessd.

---

## 5. Compatibility/demo commands

These are retained for existing automation, fixtures, and developer inspection.
They are not the canonical product UX.

```bash
python -m depone demo --out out/depone-quickstart --json
python -m depone mcp
```

The former `observe`, `run`/`evidence-run`, and `advance` compatibility loops
executed caller-provided verification commands. They are removed from the
Depone CLI; witnessd owns execution and emits the bytes Depone verifies.

---

## 6. Internal release and historical DWM commands

The older `scripts/dwm*.py`, benchmark, dogfood, and release-history commands are
internal process artifacts unless a current release note explicitly promotes a
narrow verifier contract. They may be useful for maintainers, but they are below
`docs/spec.md` in the source-of-truth hierarchy.

Examples:

```bash
python scripts/check_contract.py --tier changed
python scripts/dwm.py doctor
python scripts/check_readme_quality.py README.md
python scripts/dwm_demo.py run --out out/demo/quickstart
python scripts/dwm_benchmark.py corpus
python scripts/dwm_live_benchmark.py capture --out out/benchmarks-live/<capture_id>
```

Public superiority, trend, benchmark, or autonomous-runtime claims are blocked
unless the current spec and release evidence explicitly support them.

---

## 7. JSON and exit-code convention

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | pass/success |
| `1` | fail/refuted |
| `2` | inconclusive, insufficient evidence, or blocked-safe readiness |
| `3` | usage/config/input error |
| `4` | internal/runtime error |

JSON errors use this shape:

```json
{"error":{"code":"ERR_EXAMPLE","message":"what failed","path":null}}
```

When `--json` is present, stdout is a single JSON object and human-readable logs
belong on stderr. A result of `2` is an honest evidence verdict, not an internal
runtime failure.
