# V23 Harness Benchmark Spec

Status: implemented first harness benchmark gate in `scripts/dwm_benchmark.py`.

## Research and Prior Art

DWM should not claim superiority over direct Codex, Claude Code, OpenCode/OMO,
or any other harness through architecture narrative alone. The next product
gate is a benchmark corpus that scores evidence quality, safety, recovery,
verification, and operator clarity before any live harness claim is allowed.

## Product Position and Non-Goals

V23 is a deterministic benchmark gate. It does not run live Codex, Claude,
OpenCode, OMO, or shell adapters. It establishes the task corpus and scoring
contract that later live harness adapters must satisfy.

Non-goals:

- do not claim live harness execution,
- do not claim model quality superiority,
- do not use speed, parallelism, or role count as a proxy for safety,
- do not hide failed baselines behind synthesized success.

## Workflow Architecture

`packaging/dwm-benchmarks.json` defines:

- metrics,
- modes,
- six benchmark tasks,
- per-mode score vectors.

Required tasks:

- `failing-test-fix`,
- `small-refactor`,
- `auth-permission-audit`,
- `ui-render-regression`,
- `docs-code-consistency`,
- `multi-file-migration`.

Required metrics:

- evidence completeness,
- unreviewed change control,
- recovery quality,
- gate correctness,
- verification strength,
- operator clarity.

## Execution Model

The benchmark validator supports:

```bash
python scripts/dwm_benchmark.py corpus
python scripts/dwm_benchmark.py claim --min-margin 8
python scripts/dwm_benchmark.py --manifest fixtures/v23/manifest.json --out out/benchmarks/v23-final
```

Generated output under `out/benchmarks/` is evidence, not source truth.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_BASELINE_MISSING` when the direct baseline is absent,
- `ERR_BENCHMARK_SAFETY_REGRESSION` when DWM safety score falls below baseline,
- `ERR_BENCHMARK_UNSUPPORTED_CLAIM` when a superiority claim lacks sufficient
  margin.

## Evaluation Fixtures

`fixtures/v23/manifest.json` covers:

- positive: corpus is valid,
- positive: DWM margin is above the minimum claim threshold,
- negative: missing direct baseline is blocked,
- negative: DWM safety regression is blocked,
- negative: unsupported superiority claim is blocked.

## Release Plan

V23 is the benchmark-contract slice. Later slices can replace fixture scores
with live direct Codex, Claude Code, OpenCode/OMO, or DWM-over-adapter runs only
if they preserve the same task corpus, scoring schema, and blocked-claim rules.
