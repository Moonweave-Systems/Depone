# V128 Decision

Status: accepted as first evidence-substrate slice. Date: 2026-06-28.

V128 now emits Depone's existing observed capture evidence in consensus-shaped
JSON without changing the trust model.

Implemented substrate:

- in-toto Statement v1:
  - `_type`: `https://in-toto.io/Statement/v1`
  - `predicateType`: `https://depone.dev/attestations/evidence/v1`
  - subjects bind the capture manifest, source fixture, and observer capture
    SHA-256 digests.
- DSSE envelope:
  - `payloadType`: `application/vnd.in-toto+json`
  - `payload`: base64 canonical in-toto Statement JSON
  - `signatures`: `[]`
- Static OTel GenAI-shaped spans:
  - `gen_ai.operation.name: invoke_agent`
  - `gen_ai.operation.name: execute_tool`
  - `gen_ai.usage.*` is omitted unless observed.

Boundary:

- The DSSE envelope is unsigned and content-addressed. Empty `signatures` means
  no cryptographic signature exists.
- Emitting in-toto/DSSE or OTel-shaped evidence does not raise assurance.
- A3 remains deferred to a later Sigstore/Rekor signing milestone.
- External statement ingest is inconclusive on digest mismatch, never pass.

Evidence:

- `depone agent-fabric-evidence-substrate --self-test` validates statement
  digest round-trip, unsigned DSSE decoding, OTel span shape, tamper rejection,
  and external statement mismatch handling.
- A V126 governed capture can be exported to
  `out/v128-evidence-substrate/bundle.json`.
