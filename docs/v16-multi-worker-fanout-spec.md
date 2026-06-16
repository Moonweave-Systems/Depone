# V16 Multi-Worker Fanout Spec

Status: implemented in `scripts/dwm_runner.py fanout` and `fanin`.

## Research And Prior Art

Claude Dynamic Workflows and OMX both show that large tasks benefit from
parallel workers. DWM should add fanout only after sessions and worktrees are
durable enough to preserve evidence per worker.

## Product Position And Non-Goals

V16 adds bounded parallel worker execution. It is not an unrestricted team
launcher.

Non-goals:

- do not exceed the workflow concurrency cap,
- do not merge worker outputs automatically,
- do not launch workers without compiled packets,
- do not hide failures behind a synthesized success message.

## Workflow Architecture

Add:

```bash
python scripts/dwm_runner.py fanout --run out/v1/<run> --out out/fanout/<id> --cap <n> --workers-json '<json>'
python scripts/dwm_runner.py fanin --run out/fanout/<id>
```

Fanout artifacts:

- `workers/<worker_id>/attempt.json`,
- `workers/<worker_id>/status.json`,
- `fanin.json`,
- `conflicts.json`,
- `review-queue.json`.

## Execution Model

Each worker gets one packet reference, one attempt ledger, and one status
bundle. Fan-in never trusts a worker directly; it produces review inputs for
DWM Core. Live multi-Codex launch remains deferred.

## Safety And Verification Gates

Concurrency must obey plan budget. File ownership conflicts require review.
Any worker that requests risky actions stops at a human gate.

## Evaluation Fixtures

- positive: two independent read-only workers fan out and fan in,
- positive: one worker failure preserves other worker evidence,
- negative: concurrency cap exceeded,
- negative: overlapping file ownership requires review.

## Release Plan

1. Add fanout planner that reads explicit worker definitions.
2. Add fixture worker backend for deterministic tests.
3. Add fan-in summary and review queue artifacts.
4. Defer live multi-Codex fanout until fixture behavior is stable.
