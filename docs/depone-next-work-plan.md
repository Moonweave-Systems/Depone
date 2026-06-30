# Depone Next Work Plan

Status: post-worktree-lane-receipt planning note
Date: 2026-06-30
Base: `origin/main` at `89948b7` (`Add Team Ledger merge receipt producer`)

## Purpose

This note records the next work order after the first A2 captures, signed
evidence bundle path, `evidence-next`/`advance`, and Team Ledger v0 fan-in
slice. It is intentionally not a public benchmark claim. The goal is to keep
Depone pointed at the missing product layers while preserving its current
evidence-first discipline.

## Benchmark Read

The current external direction is clear enough to plan against:

- cloud-first coding agents run work away from the user's local machine;
- useful outputs are PRs, commits, logs, run records, and reviewable artifacts;
- teams need isolated workspaces, permissions, setup hooks, secrets boundaries,
  and resumable state;
- operators want less manual prompting between safe steps, but still need hard
  stops for destructive, credentialed, or unverified actions.

Depone should not try to beat those systems as a raw execution harness first.
Codex cloud, GitHub Copilot coding agent sessions, Claude Code, Cursor Cloud
Agents, OpenCode, OMX, and LazyCodex-style teams are adapter surfaces. Depone's
defensible role is the control and evidence layer that can say what happened,
what artifacts prove it, whether the next step is allowed, and where the claim
must stop.

## Current Position

### Strong Layers

- A0/A1/A2 assurance is implemented around capture manifests, observer capture,
  isolation facts, and fail-closed validation.
- Real A2 artifacts exist for uid isolation and container isolation. The
  container path records observer-launched Docker facts and revalidatable
  machine JSON under `docs/container-isolated-a2/`.
- Evidence bundles can be represented as in-toto/DSSE-shaped artifacts, and the
  key-based signing path has tests and a committed signed evidence example under
  `docs/evidence-run-signing/`.
- `evidence-next` and `advance` prevent continuation until previous evidence is
  revalidated. `advance` runs exactly one continuation and stops.
- Team Ledger v0 validates externally run lanes. A passed lane needs
  machine-verifiable evidence, a passing `evidence-next` verdict, non-empty
  touched files, and a merge receipt when passed lanes overlap.

### Weak Or Missing Layers

- Depone can produce a planning-only native team dry-run artifact, but does not
  yet launch and manage a durable multi-agent team by itself.
- Depone does not yet create per-lane worktrees, assign tasks, run workers, and
  collect lane evidence end-to-end.
- Depone does not yet own a cloud runner backend or remote workspace lifecycle.
- Depone does not yet ingest GitHub PR/check status as first-class evidence for
  Team Ledger lanes.
- Merge receipts are produced by command input, but not yet derived from actual
  git merge/rebase/conflict evidence.
- Signing is key-based and useful, but not yet a keyless identity or
  transparency-log assurance rung.

## Product Ladder

This is the honest ordering from here:

1. Make external PR lanes revalidatable.
2. Make local worktree lanes launchable.
3. Make a small Depone-native team command over local lanes.
4. Add cloud lanes as observed external adapters before owning cloud execution.
5. Add stronger signing and identity only after the evidence and team flow are
   useful enough to sign.

The reason for this order is practical: PR-oriented cloud systems are already
where the market is going, but Depone's first missing seam is not cloud
provisioning. It is binding a lane's code changes, evidence directory, touched
files, merge receipt, and PR/check state into one deterministic verdict.

## Next PR Slices

### Slice 1: Team Ledger PR Artifact Checks

Goal: let a Team Ledger lane point at a PR/check artifact that can be
revalidated without trusting prose.

Small implementation shape:

- add optional lane fields for `pr_url` plus a local `pr_artifact` JSON path;
- validate that the artifact contains PR number, head SHA, base SHA, state,
  mergeability/check summary, and captured time;
- require the artifact head SHA to match the lane's `end_commit` when present;
- fail closed on missing, malformed, stale, or contradictory PR artifacts;
- add a CLI producer only if it can run from `gh pr view` output and write
  deterministic JSON;
- keep network access optional by validating committed/local JSON artifacts.

Non-goals:

- no GitHub App;
- no automatic PR merge;
- no cloud runner;
- no public benchmark claim.

Acceptance evidence:

- unit tests for pass, missing artifact, head SHA mismatch, failed checks, and
  blocked lane behavior;
- `python3 -m depone team-ledger --self-test`;
- `python3 scripts/check_contract.py --tier changed`;
- `python3 scripts/dwm.py doctor`;
- a committed sample PR artifact fixture or docs example that validates without
  live network.

### Slice 2: Local Worktree Lane Receipt

Goal: record a lane's local workspace boundary before Depone launches any team.

Small implementation shape:

- add a receipt producer for repo-relative worktree path, branch, base commit,
  head commit, dirty state, changed files, command receipts, and evidence dir;
- require dirty or untracked files to be explicit, never silently ignored;
- connect the receipt to Team Ledger as an optional artifact for local lanes;
- keep the command non-destructive and read-only unless an explicit future
  launcher uses it.

Non-goals:

- no worker spawning;
- no branch deletion or cleanup;
- no automatic merge.

Acceptance evidence:

- unit tests for clean worktree, dirty worktree, path traversal, missing repo,
  and changed-file extraction;
- CLI self-test;
- changed-tier contract and DWM doctor.

### Slice 3: Minimal `depone team-dry-run`

Goal: convert a leader objective and lane specs into planned local worktree lane
receipts without launching workers yet.

Small implementation shape:

- accept a small team plan JSON through `python3 -m depone team-dry-run`;
- allocate deterministic lane ids and planned worktree paths;
- emit a Team Ledger skeleton with blocked lanes until evidence exists;
- write exact next commands for an operator or external team runtime.

Non-goals:

- no Codex/Claude/OpenCode execution;
- no automatic worktree mutation beyond dry-run planning;
- no cloud backend.

Acceptance evidence:

- deterministic fixture;
- no destructive git operations;
- command reference update;
- changed-tier contract and DWM doctor.

### Slice 4: Observed Cloud Lane Fixture

Goal: prove that Depone can represent a cloud-run lane honestly before owning
cloud execution.

Small implementation shape:

- define a cloud lane artifact schema with adapter kind, external run id, source
  repo, base/head commit, PR URL, captured logs/checks, and evidence hash;
- validate it through Team Ledger as an external lane artifact;
- document honest residuals: Depone observes cloud facts but does not attest the
  cloud provider's runtime boundary.

Non-goals:

- no secrets;
- no cloud provisioning;
- no provider-specific SDK dependency.

Acceptance evidence:

- fixture-only validation;
- source links in docs;
- changed-tier contract and DWM doctor.

## GitFlow Rules For The Next Work

- Do not repair the diverged local `/home/ubuntu/depone` `main` with reset or
  force operations.
- Create clean worktrees from `origin/main` for each PR branch.
- Keep one PR to one slice.
- For code slices, commit only source, tests, docs, and intentionally committed
  revalidatable artifacts. Do not stage ignored `out/` repair copies.
- Use draft PRs until unit tests, CLI self-tests, `check_contract.py --tier
  changed`, and `scripts/dwm.py doctor` have fresh passing output.
- Merge only after the PR's machine evidence can be revalidated from a clean
  checkout.

## Recommended Immediate Next Step

Implement Slice 3: Minimal `depone team-dry-run`.

This is the best next step now that PR artifacts and local worktree receipts
exist. It creates a native Depone planning surface without launching workers,
mutating worktrees, or claiming runtime evidence. The next slice after this
should either make those planned lanes launchable locally, or add observed cloud
lane artifacts before Depone owns cloud execution.
