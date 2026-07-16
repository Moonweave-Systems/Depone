"""Trusted observer provenance records for report-level assurance.

Capture manifests are content-addressed evidence, but a manifest in a generic
evidence directory is still runner-controlled input. Report-level A1/A2
therefore requires a separate trusted record created by the observer/operator
after verifying an observer-held seal.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from depone.agent_fabric import sign
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.seal import ALG, verify_capture_seal

PROVENANCE_KIND = "trusted-observer-provenance"
PROVENANCE_SCHEMA_VERSION = "1.0"
PROVENANCE_BINDING_KIND = "trusted-observer-provenance-binding"
DSSE_PROVENANCE_PAYLOAD_TYPE = (
    "application/vnd.depone.trusted-observer-provenance.v1+json"
)
DSSE_PROVENANCE_SCHEME = "DSSE-Ed25519-openssl-cli"
ERR_TRUSTED_PROVENANCE_MISSING = "trusted observer provenance missing"
ERR_TRUSTED_PROVENANCE_MISMATCH = "trusted observer provenance mismatch"
ERR_TRUSTED_PROVENANCE_SIGNATURE_FAILED = (
    "trusted observer provenance signature verification failed"
)


def build_trusted_observer_provenance(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    seal: dict[str, Any],
    key: bytes,
) -> dict[str, Any]:
    """Build a trusted side-channel record for an exact capture manifest."""

    observer_capture = manifest.get("observer_capture")
    verified = verify_capture_seal(
        observer_capture if isinstance(observer_capture, dict) else {},
        seal,
        key,
    )
    return {
        "kind": PROVENANCE_KIND,
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "evidence_path": evidence_path,
        "manifest_hash": canonical_hash(manifest),
        "observer_capture_hash": manifest.get("observer_capture_hash"),
        "scheme": seal.get("alg"),
        "key_id": seal.get("key_id"),
        "seal": dict(seal),
        "verified": verified,
    }


def build_signed_trusted_observer_provenance(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    private_key_path: str,
    key_id: str,
) -> dict[str, Any]:
    """Build an Ed25519 DSSE provenance record for an exact capture manifest."""

    binding = _binding(manifest, evidence_path=evidence_path)
    envelope = _unsigned_dsse_envelope(binding)
    signed_envelope = sign.sign_dsse_envelope(
        envelope,
        private_key_path,
        key_id=key_id,
    )
    return {
        "kind": PROVENANCE_KIND,
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "evidence_path": binding["evidence_path"],
        "manifest_hash": binding["manifest_hash"],
        "observer_capture_hash": binding["observer_capture_hash"],
        "scheme": DSSE_PROVENANCE_SCHEME,
        "key_id": key_id,
        "dsse_envelope": signed_envelope,
    }


def validate_trusted_observer_provenance(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    provenance: Any,
    key: bytes | None = None,
    public_key_path: str | None = None,
    verified_signature_anchors: set[str] | None = None,
) -> list[str]:
    """Return errors unless trusted provenance matches this manifest exactly."""

    records = _records(provenance)
    if not records:
        return [ERR_TRUSTED_PROVENANCE_MISSING]

    saw_candidate = False
    candidate_errors: list[str] | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("evidence_path") != evidence_path:
            continue
        saw_candidate = True
        errors = _record_errors(
            manifest,
            evidence_path=evidence_path,
            record=record,
            key=key,
            public_key_path=public_key_path,
        )
        if not errors:
            if (
                record.get("scheme") == DSSE_PROVENANCE_SCHEME
                and isinstance(public_key_path, str)
                and verified_signature_anchors is not None
            ):
                verified_signature_anchors.add(public_key_path)
            return []
        if candidate_errors is None:
            candidate_errors = errors

    if saw_candidate:
        return candidate_errors or [ERR_TRUSTED_PROVENANCE_MISMATCH]
    return [ERR_TRUSTED_PROVENANCE_MISSING]


def _records(provenance: Any) -> list[Any]:
    if isinstance(provenance, list):
        return provenance
    if isinstance(provenance, dict):
        nested = provenance.get("trusted_observer_provenance")
        if isinstance(nested, list):
            return nested
        return [provenance]
    return []


def _record_errors(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    record: dict[str, Any],
    key: bytes | None,
    public_key_path: str | None,
) -> list[str]:
    if record.get("scheme") == DSSE_PROVENANCE_SCHEME:
        return _signed_record_errors(
            manifest,
            evidence_path=evidence_path,
            record=record,
            public_key_path=public_key_path,
        )
    return _sealed_record_errors(
        manifest,
        evidence_path=evidence_path,
        record=record,
        key=key,
    )


def _sealed_record_errors(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    record: dict[str, Any],
    key: bytes | None,
) -> list[str]:
    errors: list[str] = []
    if record.get("kind") != PROVENANCE_KIND:
        errors.append("trusted observer provenance kind mismatch")
    if record.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("trusted observer provenance schema_version mismatch")
    if record.get("evidence_path") != evidence_path:
        errors.append("trusted observer provenance evidence_path mismatch")
    if record.get("manifest_hash") != canonical_hash(manifest):
        errors.append("trusted observer provenance manifest_hash mismatch")
    if record.get("observer_capture_hash") != manifest.get("observer_capture_hash"):
        errors.append("trusted observer provenance observer_capture_hash mismatch")
    if record.get("scheme") != ALG:
        errors.append("trusted observer provenance scheme mismatch")
    if record.get("verified") is not True:
        errors.append("trusted observer provenance not verified")
    seal = record.get("seal")
    if not isinstance(seal, dict):
        errors.append("trusted observer provenance seal missing")
    if not isinstance(key, bytes) or not key:
        errors.append("trusted observer provenance key missing")
    elif isinstance(seal, dict):
        observer_capture = manifest.get("observer_capture")
        if not isinstance(observer_capture, dict) or not verify_capture_seal(
            observer_capture,
            seal,
            key,
        ):
            errors.append("trusted observer provenance seal verification failed")
    return errors


def _signed_record_errors(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    record: dict[str, Any],
    public_key_path: str | None,
) -> list[str]:
    errors = _binding_record_errors(manifest, evidence_path=evidence_path, record=record)
    if record.get("scheme") != DSSE_PROVENANCE_SCHEME:
        errors.append("trusted observer provenance scheme mismatch")
    envelope = record.get("dsse_envelope")
    if not isinstance(envelope, dict):
        errors.append("trusted observer provenance dsse_envelope missing")
    if not isinstance(public_key_path, str) or not public_key_path:
        errors.append("trusted observer provenance public key missing")
    elif sign.openssl_path() is None:
        errors.append(sign.ERR_OPENSSL_UNAVAILABLE)
    elif isinstance(envelope, dict) and not sign.verify_dsse_envelope(
        envelope,
        public_key_path,
    ):
        errors.append(ERR_TRUSTED_PROVENANCE_SIGNATURE_FAILED)

    if isinstance(envelope, dict):
        binding, binding_errors = _decode_signed_binding(envelope)
        errors.extend(binding_errors)
        if binding is not None:
            expected = _binding(manifest, evidence_path=evidence_path)
            if binding != expected:
                errors.append("trusted observer provenance signed binding mismatch")
    return errors


def _binding_record_errors(
    manifest: dict[str, Any],
    *,
    evidence_path: str,
    record: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if record.get("kind") != PROVENANCE_KIND:
        errors.append("trusted observer provenance kind mismatch")
    if record.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        errors.append("trusted observer provenance schema_version mismatch")
    if record.get("evidence_path") != evidence_path:
        errors.append("trusted observer provenance evidence_path mismatch")
    if record.get("manifest_hash") != canonical_hash(manifest):
        errors.append("trusted observer provenance manifest_hash mismatch")
    if record.get("observer_capture_hash") != manifest.get("observer_capture_hash"):
        errors.append("trusted observer provenance observer_capture_hash mismatch")
    return errors


def _binding(manifest: dict[str, Any], *, evidence_path: str) -> dict[str, Any]:
    return {
        "kind": PROVENANCE_BINDING_KIND,
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "evidence_path": evidence_path,
        "manifest_hash": canonical_hash(manifest),
        "observer_capture_hash": manifest.get("observer_capture_hash"),
    }


def _unsigned_dsse_envelope(binding: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "payloadType": DSSE_PROVENANCE_PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [],
    }


def _decode_signed_binding(envelope: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if envelope.get("payloadType") != DSSE_PROVENANCE_PAYLOAD_TYPE:
        return None, ["trusted observer provenance payloadType mismatch"]
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        return None, ["trusted observer provenance payload missing"]
    try:
        payload_bytes = base64.b64decode(payload.encode("ascii"), validate=True)
        parsed = json.loads(payload_bytes)
    except (UnicodeEncodeError, binascii.Error, json.JSONDecodeError):
        return None, ["trusted observer provenance payload malformed"]
    if not isinstance(parsed, dict):
        return None, ["trusted observer provenance payload malformed"]
    return parsed, []
