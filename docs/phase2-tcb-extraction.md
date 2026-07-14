# Phase 2 TCB Extraction

Depone's trusted boundary is offline verification over existing evidence. Runtime
preflight, local worktree mutation, and lane command execution live in witnessd,
which owns provider adapters and role-lane execution.

The following migrated compatibility surfaces are removed from Depone:

- `codex-local-capability`
- `team-launch-preflight`
- `team-worktree-prep`
- `team-shell-lane-launch`

Depone may verify artifacts those witnessd helpers produce, but it must not
launch workers, mutate worktrees, probe provider CLIs, or execute lane commands.
