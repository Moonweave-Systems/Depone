# V89 Command Safety Spec

Status: implemented shared command safety inference in
`scripts/dwm_command_safety.py`.

## Research and Prior Art

V75 selected the next large-workflow command, V76 bridged it into a queue
packet, and V77 preflighted the queued packet. The design review found a core
gap: those stages could rely too much on candidate-declared `risk_codes`.

V89 makes command safety a shared control-plane contract instead of a local
check hidden in one stage.

## Product Position and Non-Goals

V89 is a deterministic command safety gate for DWM planning artifacts. It
classifies command shape, allowlisted script entrypoints, inferred gated risks,
and blocked command forms.

Non-goals:

- do not execute commands,
- do not approve runner, write, network, deploy, secret, dependency, database,
  history-rewrite, delete, or external-message work,
- do not infer task success from a safe command shape,
- do not treat candidate-declared `risk_codes` as authoritative.

## Workflow Architecture

`scripts/dwm_command_safety.py` exposes:

- `assess_command_safety(command, declared_risk_codes)`,
- shared `GATED_RISK_CODES`,
- `--self-test`,
- manifest fixture execution.

The safety record includes:

- `supported`,
- `declared_risk_codes`,
- `inferred_risk_codes`,
- `effective_risk_codes`,
- `gated_risk_codes`,
- `blocked_by`.

V75, V76, and V77 reuse this module so stale or hand-edited artifacts are
checked again at each boundary.

## Execution Model

Run the command safety self-test:

```bash
python scripts/dwm_command_safety.py --self-test
```

Run fixture coverage:

```bash
python scripts/dwm_command_safety.py --manifest fixtures/v89/manifest.json --out out/command-safety/v89-final
```

## Safety and Verification Gates

The gate blocks unsupported command shapes such as shell commands. It infers
gated risks from allowlisted risky scripts and risky command text. A command can
be supported but still gated; supported does not mean auto-executable.

Safe default: if blocked or gated, emit no execution command and preserve the
planning artifact.

## Evaluation Fixtures

`fixtures/v89/manifest.json` covers:

- safe evidence command,
- undeclared runner write risk,
- unsupported shell command,
- URL-inferring network risk.

## Release Plan

V89 adds shared command-safety inference to the release command corpus and
documents the safety contract that V75, V76, and V77 now share.
