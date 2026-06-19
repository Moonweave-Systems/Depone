# V75 Large Workflow Next Spec

Status: implemented control-bound next-action selection in
`scripts/dwm_large_workflow_next.py`.

## Research and Prior Art

V73 defined the six-axis large-workflow control evaluator. V74 applied that
control to canonical dogfood state. V75 connects the control receipt to the
next operational decision: whether DWM can name the next large workflow command,
must stop for a human gate, or must block because the evidence is stale or
unsafe.

This keeps the project moving beyond passive scoring. A graph or benchmark can
be useful later, but only if the tool first records which work it selected,
which evidence allowed the selection, and which risks prevented execution.

## Product Position and Non-Goals

V75 is a deterministic next-action selector over local control evidence. It
does not run adapters, create worktrees, push changes, edit README graphs, or
claim external benchmark superiority.

Non-goals:

- do not execute the selected command,
- do not bypass write, delete, network, deploy, secret, or external-message
  gates,
- do not select work from blocked dogfood control receipts,
- do not treat generated `out/` artifacts as source truth,
- do not publish upward trend or external superiority claims.

## Workflow Architecture

`scripts/dwm_large_workflow_next.py` reads a V74 `dogfood-control.json`,
validates the embedded V73 control result, checks source hashes, ranks
candidate next actions by priority and id, evaluates command safety with
`scripts/dwm_command_safety.py`, and writes:

- `large-workflow-next.json`,
- `large-workflow-next.md`,
- `status.json`,
- manifest `summary.json`.

The output has one of three decisions:

- `command_ready`: a read-only or evidence-only command is safe to present,
- `human_gate_required`: the selected candidate is valid but carries gated
  risk,
- `blocked`: the control receipt, source hash, candidate contract, or claim
  policy failed.

The selector does not trust candidate-declared `risk_codes` alone. It parses
the selected command, checks a supported `python scripts/*.py` entrypoint, and
adds inferred gated risks before deciding whether a command may be emitted.

## Execution Model

Select the next action from canonical dogfood control:

```bash
python scripts/dwm_large_workflow_next.py select --control out/large-workflow-dogfood/v74-canonical/dogfood-control.json --out out/large-workflow-next/<next_id>
```

Run fixture coverage:

```bash
python scripts/dwm_large_workflow_next.py --manifest fixtures/v75/manifest.json --out out/large-workflow-next/v75-final
```

## Safety and Verification Gates

The selector blocks if:

- the dogfood receipt is not `dogfood-control-recorded`,
- the embedded V73 control is not `large-workflow-controlled`,
- the control score is incomplete,
- control source hashes are missing,
- an expected control hash mismatches the current receipt,
- a candidate is malformed or duplicated,
- a candidate command is unsupported or not allowlisted,
- a candidate makes a forbidden public overclaim.

The selector returns `human_gate_required` and emits no command if the selected
candidate declares or infers write, delete, network, deploy, secret,
dependency, database, history-rewrite, or external-message risk.
The legacy V75 gate phrase remains: write, delete, network, deploy, secret, or
external-message work is never surfaced as an automatic command.

Safe default: stop before command execution and preserve the receipt.

## Evaluation Fixtures

`fixtures/v75/manifest.json` covers:

- ready control selecting a read-only/evidence command,
- blocked dogfood control blocking next selection,
- source hash drift blocking next selection,
- write-risk candidate requiring a human gate,
- undeclared runner command risk requiring a human gate,
- overclaim candidate blocking next selection.

## Release Plan

V75 adds the next-action selector to the release command corpus and command
reference. Later slices can feed its `large-workflow-next.json` into queue
construction, live runner preflight, or public benchmark promotion gates, but
those steps remain separate and explicitly verified.
