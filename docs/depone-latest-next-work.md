# Depone Latest Next Work

Status: current agent-facing execution note after PR #51 merge.
Date: 2026-06-30
Base: `origin/main` at `7d28e02` (`Add shell lane launch receipt (#51)`)

## Current Truth

Depone has reached the first non-model launch receipt rung:

- PR #51 merged the canonical agent operating contract under
  `packaging/depone-agent-operating-contract.json`.
- `team-shell-lane-launch` can run exactly one allowlisted argv command and
  write a receipt plus transcript under `docs/team-shell-lane-launch/`.
- The shell-lane receipt records `agent_contract_hash`, the resolved
  `agent_contract` facts, transcript hash, stdout/stderr hashes, and boundary
  flags.
- The committed shell-lane artifact revalidates through
  `scripts/check_contract.py --tier changed`.
- This is still local A1-style shell evidence. It is not a live model launch,
  not a scheduler, not A2/container evidence, and not an assurance upgrade.

## Next Slice

The next implementation slice is **Codex local capability detection**.

Do not launch a coding task yet. The first Codex adapter PR should only detect
whether a local Codex lane can be launched safely and write a blocked/pass
capability artifact. Missing binary, missing auth/config, unsupported repo
state, denied sandbox/approval mode, or unobservable instruction state must be
recorded as `blocked`, not as a human gate and not as a best-effort launch.

## Why This Comes Next

The shell lane proved that Depone can bind a local command receipt to a shared
agent contract. The next missing layer is not more prose about teams; it is a
machine-readable adapter capability receipt for the first real coding adapter.

This keeps the direction aligned with the broader agent-tool market:

- agents run through adapter surfaces such as Codex, Claude Code, OpenCode,
  cloud agents, or team runtimes;
- Depone should control and verify launch facts, receipts, changed files,
  transcripts, and continuation gates;
- adapter claims must degrade honestly when the local environment is not ready.

## Proposed PR

- Branch: `codex/codex-local-capability`
- Title: `Add Codex local capability receipt`
- Scope:
  - add `depone.agent_fabric.codex_local_capability`;
  - add CLI `python3 -m depone codex-local-capability`;
  - detect `codex` binary path, version command result, repo root, branch/head,
    working tree dirtiness, allowed sandbox mode, allowed approval mode, and
    loaded instruction file hashes when observable;
  - emit a deterministic receipt with `decision: pass` or `decision: blocked`;
  - bind the receipt to the same `agent_contract_hash` pattern used by
    `team-shell-lane-launch`;
  - commit a blocked-safe fixture if the current server cannot prove a pass
    capability without interactive auth assumptions.
- Anti-scope:
  - no live Codex prompt execution;
  - no model call;
  - no background worker;
  - no worktree deletion;
  - no PR/check ingestion;
  - no assurance upgrade.

## Acceptance Evidence

Required before opening the PR:

```bash
python3 -m unittest tests.test_agent_fabric_codex_local_capability tests.test_codex_local_capability_cli -v
python3 -m depone codex-local-capability --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

If a fixture is committed, it must be revalidated by the changed-tier contract
or by a focused validation helper that recomputes every hash in the receipt.

## Stop Conditions

Stop and report blocked when:

- detecting Codex readiness would require reading secrets or interactive auth;
- the local `codex` executable is absent or returns an unparseable version;
- the repo is not a git worktree;
- the adapter cannot record the instruction files it claims to have used;
- the implementation would need non-stdlib Python dependencies;
- the next step would launch a live model instead of writing only capability
  evidence.

## Follow-On Order

After the Codex capability slice lands:

1. Codex local launch receipt for one bounded packet.
2. Reviewer/verifier receipt over the changed files and deterministic tests.
3. PR/check artifact fan-in.
4. Claude Code/OpenCode capability adapters only after the Codex pattern is
   stable.
5. Owned cloud launch only after observed cloud artifacts and local adapters are
   boring.
