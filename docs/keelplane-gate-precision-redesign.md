# Keelplane Gate-Precision Redesign + Diet (direction spec, draft)

Status: draft for human review. No code change yet — implementation is gated on
the author's approval. This is a direction document, not a new V-slice.

## Governing philosophy (settled 2026-06-22, after three adversarial reviews)

> Error is unavoidable. So spend effort, verification, and human attention where
> **probability × cost-if-wrong** is highest — not where checking is cheap.
> Automation is the tactic of carrying the cheaply- and safely-refutable part all
> the way; irreversible, high-loss decisions are where a human stops.

Routing is by **loss structure**, not by camp (autonomy / verification / hybrid)
and not by how cheap a check is. The cheapest-to-check work is almost never the
highest-stakes work; optimizing for cheap checks makes you efficiently wrong
about the things that decide whether any of the rigor mattered.

## Where keelplane's value actually is

The user's one-line vision: "everything runs along on its own except the genuine
human gates, and it produces good results." Under the philosophy above, the hard
and valuable part is **not** "runs along on its own" — off-the-shelf loops
(Codex/Claude/OMO) already do that, and it is cheap to undo (`git revert`). The
hard part is **knowing exactly where the genuine gate is**: stop too often and
automation is pointless; stop too rarely and an irreversible accident ships under
a green check. Autonomy tools collect stars yet aren't trusted precisely because
their gate is weak (model self-claim + post-hoc PR review).

So keelplane's only defensible wedge is **gate precision**, not automation. Today
that wedge is under-built: risk classification in `scripts/dwm_command_safety.py`
is substring matching (`marker in joined`), which misses `git push -f`, misses a
`DROP TABLE` issued through an ORM in plain Python, and false-positives on
`api.py`. keelplane *claims* precise gating and *implements* keyword guessing.

## A. Gate precision: reversibility-by-environment

The blocking problem (named by adversarial review): **reversibility is not a
static property of an action.** It is a function of action × world-state × time
(a migration is reversible until traffic writes a row; a refactor is "reversible"
until it breaks an untested consumer). You cannot deterministically classify it
at plan time, and a keyword list is a guess wearing a determinism costume.

The redesign does not try to classify reversibility better. It **stops
classifying and starts enforcing it.**

1. **Sandbox is the default carrier of reversibility.** Every automated step runs
   inside an isolated, throwaway environment (git worktree / container /
   read-only or copy-on-write FS). Inside that boundary every effect is reversible
   by construction — discard the worktree, drop the container. So *inside the
   boundary, nothing needs a risk verdict; it is all auto.* keelplane already has
   pieces of this (V14 worktree isolation; Codex `--sandbox read-only`).

2. **The gate becomes boundary-crossing detection, not risk guessing.** The only
   thing that needs a human is an effect that **escapes the reversible boundary**:
   `git push` / deploy, outbound network writes, writes outside the sandbox tree,
   processes touching shared production state, credential use. These are
   detectable *at the system level* (network syscalls, out-of-tree FS writes,
   the literal push/deploy invocation) — deterministically, not by substring
   inference. Boundary-crossing is a far smaller, far better-defined set than
   "all risky actions," and it is the set that actually maps to irreversibility.

3. **Result = the user's vision, made precise.** Inside the sandbox the agent
   "runs along on its own" with each step gated only by deterministic checks the
   domain really has (test / compile / typecheck / hash). At the boundary —
   exactly the genuine-gate points — it stops, every time, by detection rather
   than by a guess.

### Honest limits (this is not perfect)

Sandboxing makes *most* effects reversible, not all. Things a sandbox cannot
un-happen: wall-clock time spent, token/money cost, and side effects that aren't
actually isolated (e.g. the sandbox holds credentials to a shared DB the agent
can reach). Those need their own explicit, non-substring gates: a cost/time
budget that halts the run, and credential/network scoping so the sandbox simply
*cannot* reach irreversible external state. Covert channels remain a theoretical
hole. This is materially more deterministic than keyword matching, not a proof of
total safety. It should itself be put through adversarial review before build.

## B. Diet: shift the center of mass

Apply the routing rule to keelplane's own parts (off-the-shelf alternative in
parens; "net" = value over that alternative for a solo dev):

- **Delegate (net ≤ 0, reinventing):**
  - hashed execution-packet content-addressing → use git commit/tree SHAs (the
    repo already shells out to git). Stop hand-rolling `canonical_hash` as the
    trust root.
  - "runs-along" automation loop → lean on an off-the-shelf agent loop /
    worktree runner rather than growing a bespoke one.
- **Freeze (net ≤ 0, self-referential):**
  - V94–V101 meta layer (control-deck-score / history / ladder / readiness /
    wave / promotion) — already flagged ~86% bookkeeping, nothing outside the
    chain consumes the output. Keep frozen and quarantined; do not extend.
  - autonomous-loop deepening — measured niche; do not silently revive.
- **Strengthen (net > 0, where wrong-is-expensive):**
  - boundary-crossing gate (Section A) + per-step deterministic verification.
    This is the thin core keelplane should *be*; everything above is optional.

Direction: keelplane shrinks toward a **thin layer that sits over an existing
automation loop and contributes precise, deterministic, environment-enforced
gating + per-step verification** — not a 64k-line control-plane that re-derives
git, tests, and CI.

## Validation target (the expensive, important question — do this, not more slices)

Measure the one belief everything rests on: **does keelplane's gate catch
irreversible points more precisely than an off-the-shelf Codex/Claude loop?**
On a real multi-step dev task, count both error types:
- **false-pass**: an irreversible/boundary-crossing action that ran without a
  human stop (the dangerous failure), and
- **false-stop**: a fully-reversible in-sandbox action that needlessly halted
  (the friction failure).
keelplane earns its existence only if it strictly dominates the off-the-shelf
loop on false-pass without paying too much false-stop. Until that is measured,
treat keelplane's value as unproven.

## Next (human gate)

Implementation — actually rebuilding the gate as boundary-detection, and
performing the deletions in Section B — is irreversible-ish and high-stakes, so
by this document's own philosophy it waits for the author's explicit approval.
This file is the reversible artifact; the build is the gated action.
