# Team shell lane launch fixture

This directory contains the first machine fixture for
`python3 -m depone team-shell-lane-launch`.

The command is selected by `command_id` from `allowlist.json` and executed as an
argv list with `subprocess.run(..., shell=False)`. The adapter does not accept or
concatenate arbitrary shell command strings. `receipt.json` records the resolved
`cwd`, argv, exit code, stdout/stderr SHA-256 hashes, transcript path/hash, `agent_contract_hash`, and `agent_contract` facts;
`transcript.json` contains the captured stdout/stderr text.
`agent-operating-contract.json` is the minimal machine-readable agent operating
contract bound to this shell lane receipt. The committed `receipt.json` records
`agent_contract_hash` plus `agent_contract` facts: contract path, contract id,
version, SHA-256, and V22 `worker` role binding.

Contract terms: `subprocess.run(..., shell=False)`; does not accept or concatenate arbitrary shell command strings; does not launch Codex, Claude, OpenCode; does not raise assurance; does not claim A2/container isolation; records `agent_contract_hash`; validates V22 role binding.

Regenerate the fixture with:

```bash
python3 -m depone team-shell-lane-launch \
  --allowlist docs/team-shell-lane-launch/allowlist.json \
  --command-id fixture-echo \
  --cwd . \
  --out docs/team-shell-lane-launch/receipt.json \
  --transcript docs/team-shell-lane-launch/transcript.json \
  --agent-role-id operator \
  --json
```

Generated files:

- `allowlist.json` — explicit argv allowlist for this fixture.
- `agent-operating-contract.json` — minimal common engineering contract and V22
  base-role binding used by this fixture.
- `receipt.json` — machine receipt for the selected command, including the
  contract hash and role binding facts.
- `transcript.json` — captured stdout/stderr text for the selected command.

## Honest boundary

This is shell-only A1-style local evidence. It executes the allowlisted local
argv command, but it does not launch Codex, Claude, OpenCode, live models, team
workers, or a scheduler. It does not raise assurance, does not claim
A2/container isolation, and does not prove lane task completion.

Residual: the committed receipt records the absolute `cwd` of the capture host.
A fresh clone can revalidate the JSON shape, boundary fields, contract hash,
and V22 role binding, but should re-run the command to recreate host-local
receipt paths and hashes.
