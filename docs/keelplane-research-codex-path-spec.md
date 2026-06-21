# Keelplane Research-Orchestration — Codex Execution Path (spec v2, DRAFT)

Status: DRAFT for adversarial review + human gate. Not implemented. v2 resolves the
two blockers found in the v1 self-review using the real `codex-cli 0.141.0` contract.

Goal: make the research-orchestration pattern (Scope → fan-out research → barrier
synthesis → adversarial-verify-against-source → compose) runnable on the **Codex**
substrate, so the against-source discipline is cross-platform — not Claude-Workflow-
only. (D-B is confirmed on Claude at n=1/2/3; this closes the platform gap.)

## 0. Thesis (one line)

The portable asset is the **discipline** — the research-pattern *plan contract* plus
the *verdict-integrity post-processing* — NOT a new concurrent runner. Keelplane
provides the discipline as model-agnostic core; the substrate (Claude Workflow, or a
thin Codex driver) does the fan-out. "runner + Keelplane > runner alone."

## 1. Research and prior art (what already exists in-repo)

- Claude path: `templates/research-orchestration.workflow.mjs` — DONE + hardened
  (null guards, verdict integrity, partially-supported, doc-drift fixed). Live-proven
  n=1/2 (code), n=3 (prose). This spec mirrors its phases/prompts on Codex.
- Codex execution (REUSE): `scripts/execute_packet.py:execute_codex_cli()` /
  `parse_codex_cli()` / `run_process()` — one prompt → one result via
  `codex exec --skip-git-repo-check --cd <wt> --sandbox workspace-write
  --output-last-message <transcript> -` (prompt on stdin); normalized evidence
  (`REQUIRED_EVIDENCE_KEYS` in `dwm_adapters.py`).
- Plan/compile/validate (REUSE): `references/workflow-plan-schema.md`,
  `scripts/evaluate_plan.py`, `scripts/compile_workflow.py` (V1 packet, `--plan-command`
  V12 deterministic codex command, hashing, worktree).
- Scheduling (REUSE shape): `scripts/orchestrate_workflow.py:build_schedule()` emits
  N packets under a concurrency cap (files, not live runs); `scripts/dwm_runner.py
  fanout/fanin` (V16) — fixture backend only.
- Adapter registry (REUSE): `packaging/dwm-adapters.json` — `codex` = planned,
  first-party; `fixture` = supported.
- DELIBERATE prior decisions to honor (do not silently overturn):
  - V13: runner "is still not a multi-agent runtime"; V16: "defer live multi-Codex
    fanout until fixture behavior is stable"; dispatch is "emit-only", human-gated.
  - `docs/github-research.md`: "DWM should not copy that full [Workflow] surface
    first; position above/beside, compile safe packets, hand to Codex CLI through a
    narrow adapter."
  - [[keelplane-product-positioning]]: don't build a rival swarm runner; multi-agent
    fan-out is **orthogonal** to the value; depend on the adapter interface, not a
    vendor; OMO/OMX optional only.

## 2. Product position and non-goals

In scope: the two model-agnostic assets (plan template + verdict-integrity module) and
a THIN Codex driver that reuses `execute_codex_cli` to run the phases.

Non-goals (explicit):
- NOT a concurrent swarm runner. Live multi-Codex fan-out stays DEFERRED (per V16);
  the driver runs phases sequentially / bounded. Parallelism is orthogonal to value.
- NOT an OMO/OMX dependency.
- NOT a new evidence/transcript format — reuse the normalized ledger.
- NOT removing the human-review/emit-only gates where the repo already requires them.

## 3. Architecture — two portable assets + one thin driver

(A) **Research-pattern plan** `samples/.../research-orchestration.workflow.plan.json`
    (V0.5 schema): phases scope → research (fan-out) → synthesize (barrier) → verify
    (fan-out) → compose; handoffs angles→findings→draft→verdicts→doc. **DEFERRED for
    v1** (over-build risk flagged in self-review): the driver (C) runs the phases
    directly; the formal plan.json only earns its place if/when the plan needs to be
    inspected or routed by other Keelplane tooling. Not required to ship B.

(B) **`scripts/keelplane_verdict_integrity.py`** — model-agnostic core (ZERO model
    dependency, runs on fixtures). A direct Python port of the hardened .mjs integrity
    pass: given draft `claims` + raw `verdicts`, it (1) drops verdicts whose claim_id
    ∉ claims, (2) downgrades confirmed/partially-supported lacking evidence
    locator+excerpt → unverified, (3) normalizes unknown/missing verdict → unverified,
    (4) dedupes to one verdict/claim (conservative: refuted>unverified>partial>confirmed),
    (5) computes `uncovered`. Invariant: every claim is in exactly one bucket OR
    uncovered. Ships with `--self-test`. THIS is the discipline; it is identical across
    Claude and Codex paths.

(C) **`scripts/keelplane_research_codex.py`** — thin driver. Per phase: build the
    prompt (same text as the .mjs), call `execute_codex_cli` (one packet/worker),
    capture normalized evidence, validate the worker's JSON output against the phase
    schema (NEW: in-process JSON-schema check) and retry once on mismatch/failure;
    at verify, run (B); at compose, emit the doc. Fan-out = sequential or bounded via
    the EXISTING V16 fanout path when stable — no new concurrency primitive.

## 4. Execution model (blockers resolved against codex-cli 0.141.0)

- Substrate adapter = `codex` (reuse `execute_codex_cli`); `fixture` adapter for tests.
- **Structured output (resolves v1 blocker H2):** each worker call passes
  `codex exec --output-schema <phase.schema.json>` — codex's documented flag for "a
  JSON Schema describing the model's final response shape", the direct analog of the
  Workflow tool's `schema` option. The driver reads the schema-constrained final
  message (`--output-last-message`), with a tolerant JSON extract + one retry as a
  backstop; a worker that still yields no valid object is surfaced (its claims become
  `uncovered`), never silently confirmed. → `parse_codex_cli` gains `--output-schema`.
- **Source accessibility (resolves v1 blocker H1):** research/verify workers are
  READ-ONLY over sources, which usually live OUTSIDE the worktree (e.g. the vault).
  Run them with `--sandbox read-only` (no writes; reads allowed) — or
  `--sandbox workspace-write -c 'sandbox_permissions=["disk-full-read-access"]'` if a
  worker ever needs to write — so codex can open out-of-worktree source paths. No
  worker writes files (output is the structured response). → `parse_codex_cli` gains a
  read-only/disk-read mode for this driver (the existing default stays workspace-write
  for the loop). RESIDUAL to confirm at first slice: that `read-only` permits reads
  outside `--cd`; the explicit `disk-full-read-access` permission is the fallback.
- Each worker: prompt on stdin → schema-constrained message out → validate → retry
  once → record normalized evidence (reuse `REQUIRED_EVIDENCE_KEYS`).
- Verify: chunk claims (verifyBatchSize), one verifier packet per batch, then run (B).
- Fan-out is sequential/bounded (no new concurrency); wall-time is the cost (a ~15-call
  run is minutes-scale) — acceptable for v1, concurrency deferred per V16.
- Determinism/resume: reuse packet/run hashing + trust checks; no Date/random.

## 5. Safety and verification gates

- Evidence-required-for-confirmed is enforced in code (B), not prompt — same as .mjs.
- Coverage gaps disclosed (uncovered surfaced), never silent-confirmed.
- Risk gates from the plan schema (write/network/secret/etc.) keep emit-only + human
  approval where the existing contract requires it; the research pattern is read-only
  over sources, so the default safe path needs no destructive gate.
- The driver must NOT claim success on a failed/partial run; it reports the ledger.

## 6. Evaluation fixtures

- `keelplane_verdict_integrity.py --self-test`: ports the unit cases already proven for
  the .mjs (hallucinated drop / evidence-less downgrade / unknown-verdict normalize /
  conservative dedupe / uncovered / invariant).
- Fixture-adapter end-to-end: run the full plan with a deterministic fixture backend
  (no live codex) → assert phase handoffs + integrity invariant. Mirrors how the repo
  stabilizes adapters on fixtures before live.
- ONE bounded live-codex proof (n=1) on a small real question, honestly scored
  (matches V102's bounded-live-proof discipline). No superiority/autonomy claim.

## 7. Release / implementation plan (first slice = smallest, highest-value)

1. **First slice:** `keelplane_verdict_integrity.py` + `--self-test` (model-agnostic
   core; zero model dependency; ports the proven .mjs logic). **Drift mitigation
   (H4):** the self-test loads SHARED JSON test vectors from `fixtures/verdict-
   integrity/*.json`; the .mjs validator is updated to run the same vectors, so the
   two implementations cannot silently diverge (one set of cases, both must pass).
2. Extend `parse_codex_cli` with `--output-schema` + a read-only/disk-read mode (small
   reuse-extension, not a rewrite); fixture-adapter e2e of the full phase chain.
3. Thin Codex driver (sequential) reusing `execute_codex_cli`; threads phase outputs
   (angles→findings→draft→verdicts) like the .mjs; runs (B) at verify.
4. One bounded live-codex proof (n=1) on a small real question; honest scoring; this
   also confirms the H1 residual (read-only read scope outside `--cd`). No
   superiority/autonomy claim.
5. (Deferred, NOT this spec) formal `workflow.plan.json` template; live concurrent
   fan-out — only if/when a measured need arises and V16 fixture path is stable.

Each step is human-gated; main pushes go through the user (`!git push`).

## Status of the v1 self-review findings

- H1 (source access) — RESOLVED via `--sandbox read-only` / `disk-full-read-access`
  (one residual to confirm empirically at first-slice live proof).
- H2 (structured JSON) — RESOLVED via `codex exec --output-schema`.
- H4 (dual-implementation drift) — MITIGATED via shared test vectors (step 1).
- H6 (plan-template over-build) — RESOLVED by deferring the plan.json (driver-direct).
- Scope — chosen: discipline-first + thin sequential driver, concurrency deferred.

## Remaining open decision for the human gate

The blockers are resolved on paper. The one honest open question (raised by my own
review) is **worth-it / sequencing**: B's net-new code is `verdict_integrity.py`
(a port of proven logic) + a `parse_codex_cli` extension + a thin driver. Proceed to
the first slice (`verdict_integrity.py` + shared test vectors — smallest, model-
agnostic, useful even alone), or hold B for a concrete Codex research need? The case
FOR: you run codex in other terminals and would get the against-source discipline
there. The case AGAINST: upkeep + it largely re-expresses the Claude path.
