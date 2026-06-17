# V52 README UX Spec

Status: implemented README UX consolidation in `README.md`.

## Research and Prior Art

V51 created a canonical local demo, but the README still opened into a long
implementation ledger. That was accurate for maintainers, but not optimal for a
new user deciding what DWM does today.

V52 makes the first README pass product-facing:

- define DWM as a deterministic control-plane,
- put the canonical demo first,
- explain the normal operator loop,
- separate implemented surfaces from honest non-claims,
- keep benchmark graph language tied to source-bound evidence.

## Product Position and Non-Goals

V52 is a public-page and onboarding cleanup. It does not add runtime behavior.

Non-goals:

- do not add a fake benchmark trend,
- do not claim direct-agent superiority,
- do not claim live adapter execution parity,
- do not hide the V-numbered implementation ledger,
- do not treat generated `out/` directories as source truth.

## README Contract

The README must keep these reader-facing anchors near the top:

- one-command local demo,
- normal loop for status, next action, doctor, and product commands,
- release contract command,
- current capability table,
- explicit honesty table for benchmark graph and autonomy claims.

The long command corpus and implementation history can remain lower on the
page, but the first screen should answer what DWM is, why it exists, and what a
new user should run first.

## Safety and Verification Gates

The release contract checks that README still includes the V52 anchors and keeps
the existing command corpus required by release verification.

docs/spec.md remains outside this slice unless a later spec update explicitly
changes the product contract.

## Evaluation

V52 is verified by documentation and release-contract checks:

```bash
python scripts/check_release_text.py .
python scripts/check_whitespace.py .
python scripts/quick_validate_skill.py .
python scripts/check_contract.py
```

## Release Plan

V52 should land before V53 demo inspection and V54 measured dogfood comparison,
because those later slices need a README that clearly distinguishes proof,
planned work, and public claims.
