# V46 Long-Run Workflow Queue Spec

Status: implemented first long-run workflow queue in
`scripts/dwm_workflow_queue.py`.

## Research and Prior Art

After V45, DWM can protect benchmark publication, but the operator still has to
keep saying "continue" for every roadmap step. The next product need is a queue
artifact that records ordered work packets and deterministically selects the
next safe action or a blocked reason.

## Product Position and Non-Goals

V46 is a queue planner and resume gate. It does not execute work. It turns an
ordered packet list into `queue.json`, `status.json`, and `next-action.md`.

Non-goals:

- do not run adapter commands,
- do not create worktrees,
- do not bypass human gates,
- do not continue after unsafe, missing, or failed evidence,
- do not infer success from a prior assistant message.

## Workflow Architecture

`scripts/dwm_workflow_queue.py` writes:

- `queue.json`,
- `status.json`,
- `next-action.md`,
- `summary.json` for manifest suites.

Packets can be `pending`, `ready`, `blocked`, `done`, or `superseded`. The queue
selects only the first non-terminal packet. Later packets remain `pending`
until the selected packet is handled.

## Execution Model

```bash
python scripts/dwm_workflow_queue.py create --packets packets.json --out out/workflow-queues/<queue_id>
python scripts/dwm_workflow_queue.py resume --queue out/workflow-queues/<queue_id>
python scripts/dwm_workflow_queue.py --manifest fixtures/v46/manifest.json --out out/workflow-queues/v46-final
```

Every output directory is guarded by a workflow-queue ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_DWM_QUEUE_EVIDENCE_MISSING` when required evidence paths are absent,
- `ERR_DWM_QUEUE_UNSAFE_ACTION` when risk codes include write, delete, network,
  deploy, secret, dependency, database, history rewrite, or external message,
- `ERR_DWM_QUEUE_VERIFICATION_FAILED` when verification failed,
- `ERR_DWM_QUEUE_VERIFICATION_MISSING` when verification is missing,
- `ERR_DWM_QUEUE_HUMAN_GATE_REQUIRED` when a packet requires human approval,
- `ERR_DWM_QUEUE_STALE_STATUS` when queue and status artifacts drift.

## Evaluation Fixtures

`fixtures/v46/manifest.json` covers:

- positive: first safe packet becomes `ready`,
- positive: all terminal packets produce `complete`,
- negative: missing evidence is blocked,
- negative: unsafe action is blocked,
- negative: failed verification is blocked,
- negative: human gate is blocked,
- negative: stale status is blocked.

## Release Plan

V46 lets DWM resume from a queue artifact and report the next safe action. V47
can use this queue to run real dogfood task corpora without relying on repeated
manual nudges.
