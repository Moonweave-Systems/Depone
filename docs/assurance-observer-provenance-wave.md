# Assurance Observer Provenance Wave

Status: implementation wave, 2026-07-01.

## Goal

Close the remaining P0 in the Assurance Soundness Repair work: imported capture
overclaim. A generic evidence directory must not be able to raise report
assurance to `A1-local-observed` or `A2-isolated-observed` by containing only a
hand-written or byte-copied Agent Fabric capture manifest.

This wave makes report-level observed assurance depend on trusted observer
provenance outside the runner-controlled evidence directory. The trusted signal
is rooted in the existing observer-held seal/signing infrastructure, not in the
plain `observed_by` string inside the manifest.

## Non-Goals

- Do not add a new assurance level.
- Do not add Python dependencies.
- Do not add requirements or root `pyproject.toml` entries.
- Do not hand-edit generated `out/` artifacts or fixtures.
- Do not launch live model agents.
- Do not push, open a PR, merge, or change GitHub workflow state.
- Do not rewrite the capture manifest model beyond the provenance gate needed
  for report assurance.

## Findings To Close

1. Imported capture overclaim: a valid-looking capture manifest imported through
   generic evidence must not raise report assurance unless Depone can verify a
   trusted observer provenance signal for that exact manifest.
2. Byte-copy overclaim: a byte-identical copy of a legitimate capture manifest
   in a runner-controlled evidence directory must not carry observed assurance
   by itself. The trust root must live outside that directory.
3. Fabricated non-root facts: a hand-written A1 or A2 manifest with internally
   consistent observer payloads and non-root isolation facts must not raise
   report assurance without trusted provenance.
4. Producer regression risk: the legitimate separated-observer path and the
   compile-to-report A1 smoke path must continue to produce A1 reports by
   carrying verifiable trusted provenance through a non-runner channel.

## Implementation Slices

### Slice A: Provenance Spec And RED Tests

Owner lane: verification/core.

Tasks:
- Add failing tests for an imported byte-copy of an otherwise valid A1 manifest.
- Add failing tests for a fabricated non-root A1/A2 manifest with internally
  consistent capture fields.
- Assert the report explains why the capture cannot raise assurance.
- Keep the existing valid A1 report test present, but make it depend on trusted
  side-channel provenance rather than the manifest alone.

Acceptance:
- Imported byte-copy returns `assurance=A0-claims-only` or `decision=fail`.
- Fabricated non-root facts return `assurance=A0-claims-only` or
  `decision=fail`.
- Capture errors include a concrete missing/unverified provenance reason.

### Slice B: Trusted Observer Provenance Gate

Owner lane: verification/core.

Tasks:
- Reuse `depone/agent_fabric/seal.py` HMAC seal verification or
  `depone/agent_fabric/sign.py` DSSE verification; do not create a new crypto
  primitive.
- Treat `observed_by == "depone-observer"` as descriptive metadata only, never
  as identity proof.
- Bind trusted provenance to the exact capture manifest and observer capture
  hash. A valid seal over a different capture or a record for a different
  evidence path must fail closed.
- Store or pass trusted provenance through a channel outside the generic
  evidence directory, for example `EvidenceContext.raw`, so a runner-controlled
  file copy cannot reproduce it.

Acceptance:
- `_assurance_for_report` raises assurance only for valid captures with verified
  trusted provenance.
- Missing, malformed, mismatched, or unverified provenance does not raise
  assurance and records the reason in the report.

### Slice C: Legitimate Producer Wiring

Owner lane: producer integration.

Tasks:
- Wire the separated observer path to emit/consume the existing observer seal
  marker when a seal key is provided.
- Wire the compile-to-report smoke path to pass trusted provenance through its
  in-memory evidence context.
- Preserve the existing capture manifest validation behavior: manifest validity
  is necessary but not sufficient for report-level A1/A2.

Acceptance:
- `test_valid_a1_capture_surfaces_pass_decision_and_a1_assurance` remains A1 via
  trusted provenance.
- `test_exact_compile_flows_to_a1_report_and_a1` remains A1 via trusted
  provenance.
- `python3 -m depone agent-fabric-observe --self-test` remains green.

## Review Lane

Owner lane: reviewer/verifier.

Tasks:
- Check that no report or operator-view path describes generic imported
  manifests as independently observed.
- Check that the trusted provenance key or value is never read from the
  runner-controlled evidence directory.
- Run the targeted test bundle from this wave.
- Run `python3 scripts/check_contract.py --tier changed`.
- Run `python3 scripts/dwm.py doctor`.

## Acceptance

- A hand-written capture manifest in an evidence directory cannot raise report
  assurance above `A0-claims-only` unless trusted observer provenance verifies.
- A byte-copy of a legitimate capture manifest in an evidence directory cannot
  raise report assurance without the out-of-band trusted provenance record.
- A fabricated non-root A1/A2 manifest cannot raise report assurance without
  trusted provenance.
- Legitimate observe-produced and compile-flow A1 paths still report
  `A1-local-observed`.
- The report/operator view exposes the reason an untrusted imported capture was
  capped or refuted.

## Stop Condition

Stop when the provenance gate is implemented, all legitimate producer paths are
wired, the targeted unittest bundle passes, `agent-fabric-observe --self-test`
passes, changed-tier contract passes, `dwm doctor` passes, and the final report
lists any deferred trust work. If a stronger public-signature or custody model
is needed beyond the existing seal/sign infrastructure, record it as deferred
instead of widening this wave.

