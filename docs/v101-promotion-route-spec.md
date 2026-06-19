# V101 Promotion Route Spec

Status: implemented promotion route planner in
`scripts/dwm_promotion_route.py`.

## Research And Prior Art

V100 records whether the current source evidence can enter human review for
README graph publication. The next useful step is a route planner: if the
evidence is not promotion-ready, continue dogfood acquisition; if it is
promotion-ready, stop at a human publication gate.

## Product Position And Non-Goals

V101 turns promotion evidence into the next safe operator action. It is not a
runner, publisher, or README graph editor.

Non-goals:

- do not execute dogfood acquisition commands,
- do not publish README assets,
- do not approve public benchmark graph publication,
- do not bypass human review.

## Workflow Architecture

`scripts/dwm_promotion_route.py` reads V100 `promotion-evidence.json` and
writes:

- `promotion-route.json`,
- `promotion-route.md`,
- `status.json`.

The route decision is:

- `route_ready` when more dogfood evidence should be acquired,
- `human_gate_required` when README graph publication needs human review,
- `blocked` when promotion evidence is stale, unsafe, or overclaiming.

## Execution Model

Canonical command:

```bash
python scripts/dwm_promotion_route.py route --evidence out/promotion-evidence/v100-canonical/promotion-evidence.json --out out/promotion-routes/v101-canonical
```

The V101 promotion route planner does not execute commands, create worktrees,
use the network, publish assets, or approve README graph publication. It does not approve README graph publication.

## Safety And Verification Gates

The planner blocks if:

- the evidence was not produced by V100,
- the evidence decision is not `promotion_evidence_recorded`,
- the evidence treats promotion evidence as a public benchmark,
- the evidence allows README public graph publication without human review.

When promotion evidence is ready, V101 emits `human_gate_required` and no
command. When promotion evidence is not ready, V101 emits a planned dogfood
acquisition command but does not execute it.

## Evaluation Fixtures

`fixtures/v101/manifest.json` covers:

- route-ready dogfood acquisition planning,
- promotion-ready evidence stopping at a human gate,
- blocked evidence blocking the route,
- overclaim evidence blocking the route.

## Release Plan

Add V101 to release commands, command reference, roadmap, release history, and
contract checks. The next workflow should use the route output to keep acquiring
real dogfood evidence until a human publication gate is justified.
