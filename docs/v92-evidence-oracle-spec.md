# V92 Evidence Oracle Spec

Status: implemented read-only evidence oracle in `scripts/dwm_evidence_oracle.py`.

## Research and Prior Art

V88 reconciled roadmap surfaces, V89 inferred command risk, V90 activated the
next workflow from product evidence, and V91 made verification practical with
contract tiers. Those gates still relied on each tool's own status output.
V92 adds an independent oracle that reads existing artifacts and checks explicit
claims against their contents.

## Product Position and Non-Goals

V92 is an artifact verifier. It is designed to support future scoring and graph
promotion with claim-level evidence rather than decorative progress signals.

Non-goals:

- do not execute commands,
- do not create worktrees or sessions,
- do not call live adapters,
- do not fetch network evidence,
- do not publish benchmark claims,
- do not treat generated `out/` evidence as source truth.

## Workflow Architecture

`scripts/dwm_evidence_oracle.py` reads a claims manifest and artifact inputs.
Artifacts can be inline JSON data, inline text, or repo-local file paths. The
oracle supports these assertion types:

- `json_equals`
- `json_empty`
- `json_contains`
- `json_field_exists`
- `json_hash_equals`
- `text_contains`

It emits `evidence-oracle.json`, `status.json`, and `evidence-oracle.md`.

## Execution Model

Run fixture coverage:

```bash
python scripts/dwm_evidence_oracle.py --self-test
python scripts/dwm_evidence_oracle.py --manifest fixtures/v92/manifest.json --out out/evidence-oracles/v92-final
```

Run canonical product-evidence verification after V88/V89/V90 artifacts exist:

```bash
python scripts/dwm_evidence_oracle.py verify --claims fixtures/v92/canonical-claims.json --out out/evidence-oracles/v92-canonical
```

## Safety and Verification Gates

V92 is read-only. It blocks on missing artifacts, missing JSON fields, value
mismatches, missing text, and source-hash drift. Safe default: preserve
artifacts and fix the upstream evidence producer before scoring or graphing.

## Evaluation Fixtures

`fixtures/v92/manifest.json` covers:

- verified activation evidence,
- blocked JSON mismatch,
- blocked source-hash drift,
- blocked missing artifact.

## Release Plan

V92 adds claim-level artifact verification to the changed-surface contract tier
and makes future scoring work consume falsifiable evidence.
