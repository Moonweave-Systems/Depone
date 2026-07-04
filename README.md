# Depone

> Non-executing verifier and evidence-contract source of truth for Moonweave agent evidence.

[![License: MIT](https://img.shields.io/badge/License-MIT-4F46E5.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Moonweave-Systems/Depone?color=4F46E5)](https://github.com/Moonweave-Systems/Depone/releases)
[![Contract](https://img.shields.io/badge/contract-self--tested-059669.svg)](docs/command-reference.md)

![Depone hero](assets/dwm-hero.svg)

**Depone** is the verifier engine inside Moonweave. It re-derives A0/A1/A2,
blocked, or refuted from signed evidence bytes, offline, and cannot raise the
grade beyond what those bytes support.

Depone owns the evidence contract for capture manifests, observer captures,
isolation facts, runner receipts, DSSE envelopes, evidence contracts, team
ledgers, and verifier error codes. Runtimes such as
[`witnessd`](https://github.com/Moonweave-Systems/witnessd) execute work and emit
evidence; Depone re-derives the verdict from those bytes.

## Product surface decision

Depone and witnessd remain separate engines, but the end-user install surface
should be one product: **Moonweave**. The planned user-facing skills are:

| Skill | User intent | Depone role |
| --- | --- | --- |
| `ProofPlan` | Plan a workflow without running workers. | Validate plan and contract shape. |
| `ProofRun` | Run through witnessd, emit evidence, then verify when possible. | Re-derive verdict after evidence exists. |
| `ProofVerify` | Re-check existing evidence offline. | Primary engine. |
| `ProofFlow` | Continue long-running work behind evidence gates. | Revalidate state and gate the next action. |

The direct `depone` CLI and `SKILL.md` remain developer, verifier, CI, and
compatibility surfaces. They are not the final flagship user UX beside a separate
`witnessd` skill. See [`docs/moonweave-engine-boundary.md`](docs/moonweave-engine-boundary.md).

## Quickstart

```bash
# Installation from source. PyPI publishing is not active yet.
git clone https://github.com/Moonweave-Systems/Depone
cd Depone
python -m pip install --no-deps .

# Check the package-local verifier surface.
depone doctor --json

# Re-derive committed evidence/verifier fixtures.
depone evidence-ingest --self-test
depone evidence-chain --self-test
depone team-ledger --self-test
```

Source installation smoke is:

```bash
python scripts/install_smoke.py --json
```

It installs Depone from the local source tree with `--no-deps`, runs the
installed `depone doctor`, and re-validates a committed team-ledger artifact. It
does not publish a package or claim PyPI readiness.

## What exists today

Depone ships a stdlib verifier package, strict plan/contract validators,
evidence adapters, DSSE/in-toto-shaped substrate helpers, and offline gates for
agent-session evidence. It can re-derive assurance from:

- capture manifests and observer captures,
- runner receipts and local capability receipts,
- isolation facts,
- signed evidence bundles,
- evidence-contract artifacts,
- team-ledger and merge-attempt artifacts.

It cannot turn a weak capture into a stronger one. If the bytes only support A0,
the verifier must report A0. If observer capture or isolation evidence is
missing, the verifier must not infer it from prose, model claims, or operator
intent.

Historical DWM tooling was retired to git history. Compatibility commands remain
available where needed, but the release claim for this repo is the verifier and
evidence-contract role, not a new agent runtime.

## Command taxonomy

| Class | Examples | Product meaning |
| --- | --- | --- |
| Verifier commands | `evidence-ingest`, `evidence-chain`, `team-ledger` | Stable engine calls for `ProofVerify`. |
| Contract commands | `validate`, `compile`, evidence-contract validation | Planning/contract helpers for `ProofPlan`. |
| Gate commands | `next`, `team-launch-preflight` | Non-executing gates for wrapper workflows. |
| Compatibility/demo commands | `demo`, `observe`, `evidence-substrate`, internal `agent-fabric-*` surfaces | Useful for fixtures and development, not the final user surface. |

Commands that launch workers, own sessions, retry, or mutate active worktrees
belong in witnessd or in the future Moonweave wrapper calling witnessd. Commands
that consume bytes and emit verifier results belong in Depone.

## Normal Moonweave loop

```text
1. Moonweave ProofRun receives the user goal.
2. witnessd executes work and emits evidence bytes.
3. Depone reads the artifact bytes offline.
4. Depone re-derives the verdict and assurance grade.
5. Moonweave summarizes the result without upgrading the verdict.
```

For direct verifier use, steps 1 and 2 are skipped: `ProofVerify` or `depone`
reads existing evidence and reports what the bytes support.

## Safety model

Depone treats artifacts, not model claims, as the source of truth. Generated
`out/` directories are verification evidence, not source of truth. Destructive
actions, network access, dependency installation, secret access, production
deployment, and history rewrite require explicit gates and belong outside
verifier-core paths.

The verifier must not upgrade assurance from self-report alone. A1/A2 report
assurance depends on evidence that can be re-derived from signed or hash-bound
artifact bytes. A3/keyless transparency-log attestation is not implemented.

## Honest limits

- Depone claims **no direct-agent superiority**. It is a verification and
  evidence-contract engine, not a benchmark graph or agent runtime.
- HMAC-backed provenance remains dependent on operator policy. Ed25519-only
  deployments are preferred for report-level trusted-observer provenance.
- Transparency-log and Sigstore-style A3/keyless attestation are not implemented.
- Some historical DWM/skill wording remains in deeper docs and compatibility
  commands; [`docs/moonweave-engine-boundary.md`](docs/moonweave-engine-boundary.md)
  is the current boundary interpretation.

## Quality

Release readiness is checked with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m depone validate-contracts --self-test
python3 -m depone doctor --self-test
python scripts/check_readme_quality.py README.md
```

## Documentation

- [`docs/moonweave-engine-boundary.md`](docs/moonweave-engine-boundary.md) — Depone role in the final Moonweave product surface.
- [`docs/command-reference.md`](docs/command-reference.md) and [`docs/spec.md`](docs/spec.md) — command and product references.
- [`references/workflow-plan-schema.md`](references/workflow-plan-schema.md) and [`SKILL.md`](SKILL.md) — compatibility plan schema and installed skill surface.

## License

MIT. See [`LICENSE`](LICENSE).
