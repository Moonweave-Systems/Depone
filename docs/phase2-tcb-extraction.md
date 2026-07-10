# Phase 2 TCB Extraction

Depone's trusted boundary is offline verification over existing evidence. Runtime
preflight, local worktree mutation, and lane command execution are migrating to
witnessd, which owns provider adapters and role-lane execution.

Deprecated compatibility surfaces retained in Depone:

- `depone.agent_fabric.codex_local_capability`: delegates to
  `witnessd.codex_capability`; Depone no longer keeps a provider-probe fallback.
- `team-launch-preflight`: compatibility artifact builder only; new launch
  readiness checks belong in witnessd.
- `team-worktree-prep`: compatibility shim only; worktree mutation is delegated
  to witnessd.
- `team-shell-lane-launch`: compatibility shim only; lane command execution is
  delegated to witnessd.

Depone verifier paths must not import these execution/preflight helpers while
loading the CLI or running `proofcheck`. They may verify artifacts those helpers
previously produced, but they must not launch workers, mutate worktrees, probe
provider CLIs, or execute lane commands. Deprecated shims may locate a sibling
witnessd checkout for compatibility, but Depone itself must not retain
`subprocess`-based execution or provider-probe implementations in those
surfaces.
