# Assurance Observer Provenance A3 Wave

Status: implementation wave, 2026-07-01.

## Goal

Harden trusted observer provenance from symmetric HMAC custody to
public-key-verifiable Ed25519 DSSE signatures. A runner that can write the
generic evidence directory, and can see the operator public key, must still be
unable to raise report assurance to `A1-local-observed` or
`A2-isolated-observed` without the operator private key.

This wave builds on the existing finding #2 repair: report-level observed
assurance still requires trusted provenance outside the runner-controlled
evidence directory, but the preferred trust root becomes an operator-held
Ed25519 private key verified by a public key outside the evidence directory.

## Non-Goals

- Do not add a new assurance level.
- Do not add Python crypto dependencies.
- Do not add requirements or root `pyproject.toml` entries.
- Do not hand-edit generated `out/` artifacts or fixtures.
- Do not remove the already-landed HMAC provenance compatibility path unless a
  narrow migration requires it.
- Do not implement Rekor transparency logs, Fulcio keyless identity, or
  A3-full. Those remain deferred.
- Do not push, open a PR, merge, or change GitHub workflow state.

## Findings To Close

1. Symmetric-key exposure risk: the current HMAC provenance path is sound only
   while the runner cannot obtain the shared secret. If that secret is exposed,
   public verification cannot distinguish operator provenance from runner
   forgery.
2. Public-key-only attacker: a runner that can write evidence and can read the
   operator public key must not be able to create trusted observer provenance.
3. Binding drift: a valid signature for one manifest, observer capture hash, or
   evidence path must not validate for a different binding.
4. OpenSSL availability: if Ed25519 DSSE verification cannot run, report
   assurance must fail closed to `A0-claims-only` or `decision=fail` with a
   visible reason.
5. Producer regression risk: legitimate observe-produced and compile-flow A1
   paths must keep emitting verifiable trusted provenance.

## Implementation Slices

### Slice A: Spec And RED Tests

Owner lane: verification/core.

Tasks:
- Add tests for a signed Ed25519 DSSE provenance record that preserves A1.
- Add tests for public-key-only forged DSSE provenance with no private-key
  signature.
- Add tests for a valid signature bound to a different manifest.
- Add tests for OpenSSL unavailable during verification.

Acceptance:
- The valid signed record is initially RED on the HMAC-only implementation.
- Forged, mismatched, and OpenSSL-unavailable records fail closed and expose a
  concrete provenance reason.

### Slice B: DSSE Trusted Provenance Model

Owner lane: verification/core.

Tasks:
- Reuse `depone/agent_fabric/sign.py` Ed25519 DSSE helpers:
  `sign_dsse_envelope(...)` and `verify_dsse_envelope(...)`.
- Canonically sign a provenance binding containing
  `manifest_hash`, `observer_capture_hash`, and `evidence_path`.
- Treat `observed_by == "depone-observer"` as descriptive metadata only, never
  as identity proof.
- Keep verification fail-closed for missing public key, invalid signature,
  binding mismatch, malformed payload, and missing OpenSSL.

Acceptance:
- `_assurance_for_report` raises assurance only for valid captures with
  verified trusted provenance.
- DSSE verification uses only the operator public key; the private key is never
  loaded on the verification path.

### Slice C: Generic Adapter Public-Key Channel

Owner lane: verification integration.

Tasks:
- Load `DEPONE_TRUSTED_OBSERVER_PUBLIC_KEY_FILE` from outside the evidence
  directory.
- Store only the public key path in `EvidenceContext.raw` for verifier use.
- Ignore a configured public key path if it resolves inside the evidence
  directory.
- Preserve the existing out-of-band provenance-file loading behavior.

Acceptance:
- CLI verification can consume DSSE provenance plus an outside public key file.
- Public keys stored inside evidence do not enable A1/A2 promotion.

### Slice D: Legitimate Producer Wiring

Owner lane: producer integration.

Tasks:
- Wire the separated observer self-test to sign trusted provenance with an
  operator private key and verify with the corresponding public key.
- Wire the compile-to-report smoke path to pass signed trusted provenance and a
  public key path through its in-memory evidence context.
- Preserve HMAC regression behavior where existing tests still depend on it.

Acceptance:
- `test_valid_a1_capture_surfaces_pass_decision_and_a1_assurance` remains green.
- `test_exact_compile_flows_to_a1_report_and_a1` remains green.
- `python3 -m depone agent-fabric-observe --self-test` remains green.

## Review Lane

Owner lane: reviewer/verifier.

Tasks:
- Check that verification never loads an operator private key.
- Check that public-key file loading rejects paths inside the evidence
  directory.
- Check that signature validation binds the DSSE payload and top-level
  provenance record to the same manifest hash, observer capture hash, and
  evidence path.
- Run the targeted unittest bundle, `agent-fabric-observe --self-test`,
  changed-tier contract, and `dwm doctor`.

## Acceptance

- A public-key-only attacker with evidence write access cannot forge A1/A2 by
  byte-copying, recomputing hashes, or inventing a DSSE record.
- A valid operator private-key signature over the exact provenance binding
  preserves legitimate A1/A2 promotion.
- Missing or mismatched signature and OpenSSL unavailable fail closed to
  `A0-claims-only` or `decision=fail`.
- The report/operator view exposes why the attempted promotion was rejected.

## Stop Condition

Stop when the Ed25519 DSSE provenance gate is implemented, legitimate producer
paths are wired, the required unittest bundle passes,
`python3 -m depone agent-fabric-observe --self-test` passes, changed-tier
contract passes, `dwm doctor` passes, and the final report lists deferred
Rekor/Fulcio A3-full work. If OpenSSL-backed DSSE cannot safely anchor this
provenance in the current codebase, record a blocked finding and keep the
implementation narrow.
