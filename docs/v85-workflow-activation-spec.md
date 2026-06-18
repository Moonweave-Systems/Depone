# V85 Workflow Activation Spec

Status: implemented next workflow activation gate in
`scripts/dwm_workflow_activation.py`.

V85 decides whether DWM can safely move from the completed current workflow
into designing the next large workflow. It combines the V84 installed surface
audit, the V83 runner receipt dry-run, and the current completed run status.

## Inputs

The canonical activation consumes:

- `out/installed-surface-audits/v84-canonical/installed-surface-audit.json`;
- `out/runner-receipt-dry-runs/v83-canonical/runner-receipt.json`;
- `out/v9/v32-semantic-dogfood/status.json`.

## Outputs

The gate writes `workflow-activation.json`, `workflow-activation.md`,
`status.json`, and manifest `summary.json` under
`out/workflow-activations/`.

The JSON decision is one of:

- `ready_for_next_workflow_design`: the installed skill surface is ready, the
  receipt is a non-executing dry-run, and the current workflow is complete;
- `blocked`: install drift, receipt execution, receipt blockers, incomplete run
  state, or missing human-gate evidence prevents activation.

## Safety

V85 is activation-only. It does not execute queued commands, create worktrees,
attach sessions, run live adapters, use network, deploy, delete files, read
secrets, or rewrite history. It only decides whether the next safe action is
`design_next_workflow`; live execution remains behind a human gate.

## Release Commands

```bash
python scripts/dwm_workflow_activation.py --self-test
python scripts/dwm_workflow_activation.py --manifest fixtures/v85/manifest.json --out out/workflow-activations/v85-final
python scripts/dwm_workflow_activation.py activate --audit out/installed-surface-audits/v84-canonical/installed-surface-audit.json --receipt out/runner-receipt-dry-runs/v83-canonical/runner-receipt.json --status out/v9/v32-semantic-dogfood/status.json --out out/workflow-activations/v85-canonical
```
