# Depone Documentation Map

This file exists to prevent doc drift. It is a map, not a second spec.

## Canonical docs

| Role | Document |
| --- | --- |
| Depone verifier/evidence-contract source of truth | [`spec.md`](spec.md) |
| Executable contract implementation | `../depone/agent_fabric/*`, `../depone/verify/*` |
| Human quickstart | [`../README.md`](../README.md) |
| Command inventory and compatibility reference | [`command-reference.md`](command-reference.md) |
| ORRO proofcheck hardening policy | [`orro-proofcheck-hardening.md`](orro-proofcheck-hardening.md) |
| Claude/session orientation | [`../CLAUDE.md`](../CLAUDE.md) |
| Codex/session orientation | [`../AGENTS.md`](../AGENTS.md) |
| Compatibility skill text | [`../SKILL.md`](../SKILL.md) |

When these conflict, `docs/spec.md` wins for Depone verifier-contract decisions.
witnessd `SPEC3.md` wins for witnessd runtime/product decisions.

## Public naming

Use these names in new user-facing docs:

| Name | Meaning |
| --- | --- |
| Moonweave / Moonweave Systems | publisher/account namespace |
| ORRO | flagship product/tool, published by Moonweave |
| Observed Run & Review Orchestrator | ORRO full name |
| ORRO Flow | scout -> flowplan -> proofrun -> proofcheck -> handoff |
| `orro` | primary command/skill surface |
| `orro scout` | read-only repo exploration and context packaging |
| `flowplan` | plan-only workflow design |
| `proofrun` | evidence-backed execution alias |
| `proofcheck` | offline evidence verification alias |
| `orro handoff` | maintainer review package bound to evidence |
| `orro auto` | continuation mode behind evidence gates |
| `orro ultra` | future high-autonomy profile |
| Superflow | historical/compatibility name, superseded by ORRO |

Use `Depone` or `depone` only when discussing the verifier engine, CLI, package,
or compatibility skill. Use `Moonweave` only when discussing the publisher/account
namespace.

## Legacy docs

The following categories are historical or compatibility material unless
`docs/spec.md` explicitly promotes them:

- historical DWM roadmap and product-shell documents,
- benchmark, trend, score, and promotion docs,
- old release-history and wave-planning docs,
- generated `out/` artifacts,
- fixture notes that explain a committed evidence case,
- compatibility command docs for older automation,
- Superflow naming, schema kinds, and fixture paths during ORRO migration.

Do not start new work from a legacy doc. Start from `docs/spec.md`; if runtime
changes are needed, check witnessd `SPEC3.md`.

## Edit rule

When Depone's product boundary, contract, command taxonomy, naming, or verifier
roadmap changes:

1. update `docs/spec.md`,
2. update this map if the canonical set changed,
3. update README / SKILL / AGENTS / CLAUDE / command reference as derived
   summaries,
4. leave legacy docs as historical unless they actively mislead current work.
