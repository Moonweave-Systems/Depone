# V24 Live Benchmark Evidence Spec

Status: implemented first live benchmark evidence capture in
`scripts/dwm_live_benchmark.py`.

## Research and Prior Art

V23 created a deterministic benchmark corpus, but that is still only a scoring
contract. V24 adds the first evidence-capture layer so DWM can distinguish
captured, blocked, and skipped benchmark runs before making any live harness
claim.

## Product Position and Non-Goals

V24 is not a live model benchmark. It captures repo-local fixture-control
evidence and deterministic adapter availability results. Direct Codex, Claude,
OpenCode, OMO, networked model calls, and arbitrary shell tasks remain outside
this slice.

Non-goals:

- do not claim live model execution,
- do not run direct Codex benchmark tasks,
- do not auto-install adapters,
- do not convert skipped adapters into failures unless the manifest requires it,
- do not treat generated benchmark output as source truth.

## Workflow Architecture

The live benchmark tool reads the V23 corpus and emits run-local artifacts under
`out/benchmarks-live/`:

- `run.json`,
- `commands.json`,
- `evidence.json`,
- `score.json`,
- `status.json`,
- `summary.json` for manifest suites.

The first safe mode is `fixture-control`. It records benchmark corpus evidence
without live model execution. `adapter-availability` can check whether an
adapter command exists, but unavailable adapters are recorded as `skipped`.

## Execution Model

```bash
python scripts/dwm_live_benchmark.py capture --out out/benchmarks-live/<capture_id>
python scripts/dwm_live_benchmark.py adapter-check --mode codex-cli --adapter-command codex
python scripts/dwm_live_benchmark.py --manifest fixtures/v24/manifest.json --out out/benchmarks-live/v24-final
```

Every capture directory is protected by a live-benchmark ownership sentinel.
Existing non-owned directories are refused.

## Safety and Verification Gates

The gate blocks or skips:

- `ERR_LIVE_BENCHMARK_CORPUS_MISSING` when the benchmark corpus is absent,
- `ERR_LIVE_BENCHMARK_UNSAFE_MODE` when a requested mode would imply live model
  execution in V24,
- `ERR_LIVE_BENCHMARK_STALE_SCORE` when an expected corpus hash no longer
  matches,
- `ERR_LIVE_BENCHMARK_ADAPTER_UNAVAILABLE` as a structured skipped status when
  an optional adapter command is missing.

## Evaluation Fixtures

`fixtures/v24/manifest.json` covers:

- positive: `fixture-control` capture writes evidence artifacts,
- negative: missing corpus is blocked,
- negative: unsafe direct mode is blocked,
- negative: stale corpus hash is blocked,
- skip: unavailable adapter is recorded deterministically.

## Release Plan

V24 is the evidence-capture bridge between deterministic scoring and real
harness comparisons. Later versions can add isolated direct Codex or Claude
task runs only if they preserve the same corpus hashes, status semantics,
ownership sentinels, and blocked-claim defaults.
