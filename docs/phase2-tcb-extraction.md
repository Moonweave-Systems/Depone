# Phase 2 TCB Extraction

Depone's trusted boundary is offline verification over existing evidence. Runtime
preflight, local worktree mutation, and lane command execution are migrating to
witnessd, which owns provider adapters and role-lane execution.

Deprecated compatibility surfaces retained in Depone:

- `depone.agent_fabric.codex_local_capability`: delegates to
  `witnessd.codex_capability` when that canonical module is importable; otherwise
  keeps a stdlib fallback for old fixtures.
- `team-launch-preflight`: compatibility artifact builder only; new launch
  readiness checks belong in witnessd.
- `team-worktree-prep`: compatibility worktree receipt helper only; new worktree
  mutation belongs in witnessd.
- `team-shell-lane-launch`: compatibility shell-lane receipt helper only; new
  lane execution belongs in witnessd.

Depone verifier paths must not import these execution/preflight helpers while
loading the CLI or running `proofcheck`. They may verify artifacts those helpers
previously produced, but they must not launch workers, mutate worktrees, probe
provider CLIs, or execute lane commands.
