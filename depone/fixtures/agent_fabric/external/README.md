# External Evidence Fixtures

These fixtures prove V128 ingest can handle evidence Depone did not emit.
They are committed so tests remain hermetic and never fetch the network.

## `external_intoto_statement_real.json`

- Upstream source URL: https://github.com/slsa-framework/slsa-github-generator/blob/main/internal/builders/docker/README.md
- Retrieved: 2026-06-28
- License: Apache-2.0, per https://github.com/slsa-framework/slsa-github-generator/blob/main/LICENSE
- Notes: Verbatim JSON from the README "Provenance Example" block. Depone treats
  its SLSA predicate as foreign and opaque. Because this repository does not
  commit the referenced `example.js` artifact, ingest should be `inconclusive`,
  not blocked only because the predicate is foreign.

## `external_artifact.bin`

- Upstream source URL: local Depone test fixture, committed in this repository.
- Retrieved: 2026-06-28
- License: project license for this repository.
- Raw SHA-256: `fd9532f6eddd9fbefc0f854b997adbf90c36f8e4f90062a6b83109439f242ac8`
- Newline-free content + `*.bin binary` in `.gitattributes` so git never
  line-ending-normalizes it; the raw digest is identical on every clone.
- Notes: Small binary fixture used to prove vendor-neutral subject verification
  with the in-toto convention: SHA-256 over raw file bytes.

## `external_slsa_statement_bound.json`

- Upstream source URL: local Depone test fixture, committed in this repository.
- Retrieved: 2026-06-28
- License: project license for this repository.
- Notes: SLSA-provenance-shaped in-toto Statement whose subject digest is derived
  from the raw bytes of `external_artifact.bin`. Depone verifies only the subject
  artifact binding and treats the foreign SLSA predicate as opaque.

## `external_signed_dsse_nonempty.json`

- Upstream source URL: local DSSE-shaped fixture, committed in this repository.
- Retrieved: 2026-06-28
- License: project license for this repository.
- Notes: Contains a non-empty `signatures` array to prove V128 blocks claimed
  signatures it cannot verify. It is not treated as proof of a valid signature;
  A3 signature verification remains deferred.
