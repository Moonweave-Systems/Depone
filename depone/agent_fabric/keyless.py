"""Non-trusting keyless fixture linter for W6a readiness.

This module is deliberately not a Fulcio/Rekor verifier. It only checks that an
offline fixture has the expected shape and pinned bytes while reporting no
trusted keyless identity, transparency log proof, or signature verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from depone.agent_fabric.capture_bridge import validate_capture_manifest

SIGNING_STATUS_KEYLESS_FULCIO_REKOR = "keyless-fulcio-rekor-fixture-untrusted"
KEYLESS_FIXTURE_SCHEME = "DSSE-Sigstore-Fulcio-Rekor-offline-fixture-untrusted"
_ASSURANCE_CEILING = {"A0-claims-only", "A1-local-observed", "A2-isolated-observed"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def keyless_fixture_boundary() -> dict[str, Any]:
    return {
        "scheme": KEYLESS_FIXTURE_SCHEME,
        "operator_key": False,
        "public_verifiable": False,
        "keyless_identity": False,
        "transparency_logged": False,
        "claimed_keyless_identity": True,
        "claimed_rekor_metadata": True,
        "raises_assurance": False,
        "fixture_only": True,
        "trusts_external_signature": False,
        "note": (
            "Offline shape lint only. This is not Fulcio chain verification, "
            "Rekor inclusion verification, or a trusted signature result."
        ),
    }


def _base_report(decision: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "decision": decision,
        "reasons": reasons,
        "signing_status": SIGNING_STATUS_KEYLESS_FULCIO_REKOR,
        "signature_verified": False,
        "trusts_external_signature": False,
        "keyless_identity": False,
        "transparency_logged": False,
        "boundary": {
            "raises_assurance": False,
            "trusts_external_signature": False,
        },
    }


def _capture_subject_digest(statement: dict[str, Any]) -> str | None:
    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        return None
    for item in subjects:
        if not isinstance(item, dict) or item.get("name") != "depone-capture-manifest":
            continue
        digest = item.get("digest")
        if isinstance(digest, dict) and isinstance(digest.get("sha256"), str):
            return digest["sha256"]
    return None


def lint_keyless_bundle_fixture(
    bundle: dict[str, Any],
    *,
    expected_bundle_sha256: str | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(bundle, dict):
        return _base_report("blocked", ["bundle must be an object"])
    if expected_bundle_sha256 is not None and _sha256_json(bundle) != expected_bundle_sha256:
        reasons.append("fixture hash mismatch")
    if bundle.get("signing_status") != SIGNING_STATUS_KEYLESS_FULCIO_REKOR:
        reasons.append("signing_status mismatch")
    if bundle.get("signature_boundary") != keyless_fixture_boundary():
        reasons.append("signature_boundary mismatch")
    if bundle.get("assurance") not in _ASSURANCE_CEILING:
        reasons.append("assurance exceeds A2")

    statement = bundle.get("statement")
    envelope = bundle.get("dsse_envelope")
    if not isinstance(statement, dict) or not isinstance(envelope, dict):
        reasons.append("statement and dsse_envelope must be objects")
    else:
        expected_payload = base64.b64encode(
            _canonical_json(statement).encode("utf-8")
        ).decode("ascii")
        if envelope.get("payloadType") != "application/vnd.in-toto+json":
            reasons.append("unsupported payloadType")
        if envelope.get("payload") != expected_payload:
            reasons.append("payload does not match statement")
        predicate = statement.get("predicate")
        if not isinstance(predicate, dict):
            reasons.append("predicate must be an object")
        else:
            if bundle.get("assurance") != predicate.get("assurance"):
                reasons.append("top-level assurance mismatch")
            if predicate.get("assurance") not in _ASSURANCE_CEILING:
                reasons.append("assurance exceeds A2")
            boundary = predicate.get("boundary")
            if not isinstance(boundary, dict):
                reasons.append("predicate boundary must be an object")
            elif boundary.get("raises_assurance") is not False:
                reasons.append("predicate raises assurance")
        signatures = envelope.get("signatures")
        if not isinstance(signatures, list) or len(signatures) != 1:
            reasons.append("fixture must contain exactly one keyless metadata record")
        elif not isinstance(signatures[0], dict):
            reasons.append("signature metadata must be an object")
        else:
            metadata = signatures[0]
            if metadata.get("sig") != "fixture-metadata-not-a-cryptographic-signature":
                reasons.append("fixture signature marker mismatch")
            rekor = metadata.get("rekor")
            if not isinstance(rekor, dict) or not rekor.get("uuid"):
                reasons.append("rekor metadata missing uuid")

    subject_capture = bundle.get("subject_capture_manifest")
    if not isinstance(subject_capture, dict):
        reasons.append("subject_capture_manifest must be embedded for fixture lint")
    else:
        if validate_capture_manifest(subject_capture) != []:
            reasons.append("subject capture manifest invalid")
        if isinstance(statement, dict):
            actual_subject_digest = _capture_subject_digest(statement)
            expected_subject_digest = _sha256_json(subject_capture)
            if actual_subject_digest != expected_subject_digest:
                reasons.append("subject digest mismatch")

    return _base_report("blocked" if reasons else "lint_passed", reasons)
