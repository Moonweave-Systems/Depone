# V77 Large Workflow Queue Preflight Spec

Status: implemented queue-packet preflight gate in
`scripts/dwm_large_workflow_queue_preflight.py`.

## Research and Prior Art

V75 selected a next large-workflow command from control evidence. V76 converted
that selection into a V46 queue packet. V77 adds the missing execution boundary:
before any runner or operator uses the queued command, DWM verifies that the
queue is still recorded, the selected packet is still ready, evidence files are
present, the command shape is supported, and no declared or inferred gated risk
is present.

This keeps the product aligned with modern agent runtime direction without
becoming a harness clone. DWM can cooperate with Codex, Claude Code, OpenCode,
or another runner later, but the queue preflight remains a local artifact gate.

## Product Position and Non-Goals

V77 is a preflight gate over a queued large-workflow packet. It is not a runner.

Non-goals:

- do not execute the queued command,
- do not create worktrees or sessions,
- do not bypass human gates,
- do not allow write, delete, network, deploy, secret, dependency, database,
  history-rewrite, or external-message risk,
- do not treat a ready preflight as benchmark proof.

## Workflow Architecture

`scripts/dwm_large_workflow_queue_preflight.py` reads a queue `queue.json`,
checks the selected `next_action`, resolves the selected packet, evaluates
command safety with `scripts/dwm_command_safety.py`, and writes:

- `queue-preflight.json`,
- `queue-preflight.md`,
- `status.json`,
- manifest `summary.json`.

The output is either `queue-preflight-ready` or `queue-preflight-blocked`.

## Execution Model

Preflight the canonical V76 queue:

```bash
python scripts/dwm_large_workflow_queue_preflight.py preflight --queue out/workflow-queues/v76-canonical/queue.json --out out/large-workflow-queue-preflight/<preflight_id>
```

Run fixture coverage:

```bash
python scripts/dwm_large_workflow_queue_preflight.py --manifest fixtures/v77/manifest.json --out out/large-workflow-queue-preflight/v77-final
```

## Safety and Verification Gates

The preflight blocks if:

- the queue is not `queue-recorded`,
- `next_action` is missing or not `ready`,
- the selected packet is missing or not `ready`,
- packet verification is not `pass`,
- the packet requires human approval,
- risk codes include write, delete, network, deploy, secret, dependency,
  database, history-rewrite, or external-message,
- the command is missing, unsupported, not allowlisted, or infers a gated risk
  omitted from packet `risk_codes`,
- evidence paths are missing,
- the expected queue hash mismatches.

Safe default: preserve the preflight receipt and emit no command for execution.

## Evaluation Fixtures

`fixtures/v77/manifest.json` covers:

- ready queue packet passing preflight,
- unsafe risk blocking,
- missing evidence blocking,
- complete queue blocking,
- queue hash drift blocking,
- unsupported command blocking.

## Release Plan

V77 adds the queue preflight gate to the release command corpus. The next slice
can decide whether to connect this ready preflight to a bounded runner plan, but
actual command execution remains a separate gated step.
