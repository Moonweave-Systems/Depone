"""Offline verification of Fulcio/Rekor-backed Sigstore DSSE bundles."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from typing import Any


ANCHOR_CLASS_KEYLESS_TRANSPARENCY_LOGGED = "keyless-transparency-logged"

_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
_TRUSTED_ROOT_MEDIA_TYPE = "application/vnd.dev.sigstore.trustedroot.v0.2+json"
_DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
_OIDC_ISSUER_V2_OID = "1.3.6.1.4.1.57264.1.8"
_OIDC_ISSUER_LEGACY_OID = "1.3.6.1.4.1.57264.1.1"


class _VerificationFailure(Exception):
    pass


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "decision": "blocked",
        "anchor_class": None,
        "keyless_identity": False,
        "transparency_logged": False,
        "signature_verified": False,
        "raises_assurance": False,
        "reasons": [reason],
    }


def _passed() -> dict[str, Any]:
    return {
        "decision": "pass",
        "anchor_class": ANCHOR_CLASS_KEYLESS_TRANSPARENCY_LOGGED,
        "keyless_identity": True,
        "transparency_logged": True,
        "signature_verified": True,
        "raises_assurance": False,
        "reasons": [],
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _decode_base64(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise _VerificationFailure(f"bundle structure invalid: {field} must be base64")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise _VerificationFailure(
            f"bundle structure invalid: {field} must be base64"
        ) from exc


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise _VerificationFailure(f"bundle structure invalid: {field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise _VerificationFailure(
            f"bundle structure invalid: {field} must be an integer"
        ) from exc
    if result < 0 or str(result) != str(value):
        raise _VerificationFailure(f"bundle structure invalid: {field} must be an integer")
    return result


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise _VerificationFailure(f"trusted root invalid: {field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _VerificationFailure(
            f"trusted root invalid: {field} must be a timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise _VerificationFailure(f"trusted root invalid: {field} must be a timestamp")
    return parsed.astimezone(timezone.utc)


def _within_time_range(value: datetime, time_range: Any) -> bool:
    if not isinstance(time_range, dict):
        return False
    start = _parse_time(time_range.get("start"), "validFor.start")
    end_value = time_range.get("end")
    end = _parse_time(end_value, "validFor.end") if end_value is not None else None
    return start <= value and (end is None or value <= end)


def _parse_structure(bundle: dict[str, Any], trusted_root: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("mediaType") != _BUNDLE_MEDIA_TYPE:
        raise _VerificationFailure("bundle structure invalid: unsupported mediaType")
    material = bundle.get("verificationMaterial")
    if not isinstance(material, dict):
        raise _VerificationFailure(
            "bundle structure invalid: verificationMaterial must be an object"
        )
    certificate = material.get("certificate")
    if not isinstance(certificate, dict):
        chain = material.get("x509CertificateChain")
        certificates = chain.get("certificates") if isinstance(chain, dict) else None
        if not isinstance(certificates, list) or not certificates or not isinstance(
            certificates[0], dict
        ):
            raise _VerificationFailure(
                "bundle structure invalid: leaf certificate is required"
            )
        certificate = certificates[0]
    leaf_der = _decode_base64(certificate.get("rawBytes"), "certificate.rawBytes")

    envelope = bundle.get("dsseEnvelope", bundle.get("dsse_envelope"))
    if not isinstance(envelope, dict):
        raise _VerificationFailure("bundle structure invalid: dsseEnvelope must be an object")
    if envelope.get("payloadType") != _DSSE_PAYLOAD_TYPE:
        raise _VerificationFailure("bundle structure invalid: unsupported DSSE payloadType")
    payload = _decode_base64(envelope.get("payload"), "dsseEnvelope.payload")
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1 or not isinstance(
        signatures[0], dict
    ):
        raise _VerificationFailure(
            "bundle structure invalid: DSSE envelope must contain exactly one signature"
        )
    dsse_signature = _decode_base64(
        signatures[0].get("sig"), "dsseEnvelope.signatures[0].sig"
    )

    entries = material.get("tlogEntries")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise _VerificationFailure(
            "bundle structure invalid: exactly one transparency log entry is required"
        )
    entry = entries[0]
    kind_version = entry.get("kindVersion")
    if kind_version != {"kind": "dsse", "version": "0.0.1"}:
        raise _VerificationFailure("bundle structure invalid: unsupported Rekor entry kind")
    log_id_record = entry.get("logId")
    if not isinstance(log_id_record, dict):
        raise _VerificationFailure("bundle structure invalid: Rekor logId is required")
    log_id = _decode_base64(log_id_record.get("keyId"), "tlogEntries[0].logId.keyId")
    integrated_time = _integer(entry.get("integratedTime"), "integratedTime")
    log_index = _integer(entry.get("logIndex"), "logIndex")
    promise = entry.get("inclusionPromise")
    if not isinstance(promise, dict):
        raise _VerificationFailure("bundle structure invalid: inclusionPromise is required")
    set_signature = _decode_base64(
        promise.get("signedEntryTimestamp"), "signedEntryTimestamp"
    )
    proof = entry.get("inclusionProof")
    if not isinstance(proof, dict):
        raise _VerificationFailure("bundle structure invalid: inclusionProof is required")
    proof_index = _integer(proof.get("logIndex"), "inclusionProof.logIndex")
    tree_size = _integer(proof.get("treeSize"), "inclusionProof.treeSize")
    root_hash = _decode_base64(proof.get("rootHash"), "inclusionProof.rootHash")
    hashes_value = proof.get("hashes")
    if not isinstance(hashes_value, list):
        raise _VerificationFailure("bundle structure invalid: inclusionProof.hashes must be a list")
    proof_hashes = [
        _decode_base64(item, f"inclusionProof.hashes[{index}]")
        for index, item in enumerate(hashes_value)
    ]
    checkpoint = proof.get("checkpoint")
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("envelope"), str):
        raise _VerificationFailure("bundle structure invalid: signed checkpoint is required")
    canonicalized_body = _decode_base64(
        entry.get("canonicalizedBody"), "canonicalizedBody"
    )
    if proof_index != log_index:
        raise _VerificationFailure("bundle structure invalid: Rekor log indexes disagree")
    if tree_size <= 0 or log_index >= tree_size:
        raise _VerificationFailure("bundle structure invalid: Rekor log index is out of range")
    if len(root_hash) != hashlib.sha256().digest_size or any(
        len(item) != hashlib.sha256().digest_size for item in proof_hashes
    ):
        raise _VerificationFailure("bundle structure invalid: Rekor hashes must be SHA-256")

    if trusted_root.get("mediaType") != _TRUSTED_ROOT_MEDIA_TYPE:
        raise _VerificationFailure("trusted root invalid: unsupported mediaType")
    if not isinstance(trusted_root.get("tlogs"), list):
        raise _VerificationFailure("trusted root invalid: tlogs must be a list")
    if not isinstance(trusted_root.get("certificateAuthorities"), list):
        raise _VerificationFailure(
            "trusted root invalid: certificateAuthorities must be a list"
        )

    return {
        "leaf_der": leaf_der,
        "envelope": envelope,
        "payload": payload,
        "dsse_signature": dsse_signature,
        "entry": entry,
        "log_id": log_id,
        "integrated_time": integrated_time,
        "log_index": log_index,
        "set_signature": set_signature,
        "tree_size": tree_size,
        "root_hash": root_hash,
        "proof_hashes": proof_hashes,
        "checkpoint": checkpoint["envelope"],
        "canonicalized_body": canonicalized_body,
    }


def _leaf_hash(body: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + body).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _root_from_inclusion_proof(
    leaf: bytes, log_index: int, tree_size: int, proof: list[bytes]
) -> bytes:
    node = leaf
    index = log_index
    last = tree_size - 1
    consumed = 0
    while last > 0:
        if consumed >= len(proof):
            raise _VerificationFailure("Rekor inclusion proof invalid")
        sibling = proof[consumed]
        consumed += 1
        if index & 1 or index == last:
            node = _node_hash(sibling, node)
            while index != 0 and not (index & 1):
                index >>= 1
                last >>= 1
        else:
            node = _node_hash(node, sibling)
        index >>= 1
        last >>= 1
    if consumed != len(proof):
        raise _VerificationFailure("Rekor inclusion proof invalid")
    return node


def _trusted_log(
    trusted_root: dict[str, Any],
    log_id: bytes,
    trusted_time: datetime,
    *,
    serialization: Any,
) -> dict[str, Any]:
    for candidate in trusted_root["tlogs"]:
        if not isinstance(candidate, dict) or candidate.get("hashAlgorithm") != "SHA2_256":
            continue
        candidate_id = candidate.get("logId")
        public_key = candidate.get("publicKey")
        if not isinstance(candidate_id, dict) or not isinstance(public_key, dict):
            continue
        try:
            key_id = _decode_base64(candidate_id.get("keyId"), "trusted log keyId")
            key_bytes = _decode_base64(public_key.get("rawBytes"), "trusted log public key")
            try:
                loaded_key = serialization.load_der_public_key(key_bytes)
            except ValueError:
                loaded_key = serialization.load_pem_public_key(key_bytes)
            normalized_key = loaded_key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            valid = _within_time_range(trusted_time, public_key.get("validFor"))
        except _VerificationFailure:
            continue
        except Exception:
            continue
        if key_id == log_id == hashlib.sha256(normalized_key).digest() and valid:
            return candidate
    raise _VerificationFailure("Rekor log key not trusted")


def _verify_checkpoint(
    checkpoint: str,
    *,
    trusted_log: dict[str, Any],
    tree_size: int,
    root_hash: bytes,
    serialization: Any,
    ed25519: Any,
) -> Any:
    try:
        body_text, signatures_text = checkpoint.split("\n\n", 1)
        body = (body_text + "\n").encode("utf-8")
        lines = body_text.splitlines()
        if len(lines) < 3:
            raise ValueError("checkpoint body")
        origin = lines[0]
        checkpoint_size = int(lines[1])
        checkpoint_root = base64.b64decode(lines[2].encode("ascii"), validate=True)
        if origin != trusted_log.get("baseUrl"):
            raise ValueError("checkpoint origin")
        if checkpoint_size != tree_size or checkpoint_root != root_hash:
            raise ValueError("checkpoint root")
        public_key_record = trusted_log["publicKey"]
        if public_key_record.get("keyDetails") != "PKIX_ED25519":
            raise ValueError("checkpoint algorithm")
        public_key_bytes = _decode_base64(
            public_key_record.get("rawBytes"), "trusted log public key"
        )
        try:
            public_key = serialization.load_der_public_key(public_key_bytes)
        except ValueError:
            public_key = serialization.load_pem_public_key(public_key_bytes)
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise ValueError("checkpoint key")
        expected_hint_record = trusted_log.get("checkpointKeyId")
        if not isinstance(expected_hint_record, dict):
            raise ValueError("checkpoint key hint")
        expected_hint = _decode_base64(
            expected_hint_record.get("keyId"), "checkpointKeyId.keyId"
        )
        actual_hint = hashlib.sha256(
            origin.encode("utf-8")
            + b"\n\x01"
            + public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        ).digest()[:4]
        if expected_hint != actual_hint:
            raise ValueError("checkpoint key hint")
        for line in signatures_text.splitlines():
            prefix = f"— {origin} "
            if not line.startswith(prefix):
                continue
            signature = base64.b64decode(line[len(prefix) :].encode("ascii"), validate=True)
            if len(signature) != 68 or signature[:4] != expected_hint:
                continue
            public_key.verify(signature[4:], body)
            return public_key
    except Exception as exc:
        raise _VerificationFailure("Rekor checkpoint signature invalid") from exc
    raise _VerificationFailure("Rekor checkpoint signature invalid")


def _verify_rekor(
    parsed: dict[str, Any],
    trusted_root: dict[str, Any],
    *,
    x509: Any,
    serialization: Any,
    ed25519: Any,
) -> datetime:
    calculated_root = _root_from_inclusion_proof(
        _leaf_hash(parsed["canonicalized_body"]),
        parsed["log_index"],
        parsed["tree_size"],
        parsed["proof_hashes"],
    )
    if calculated_root != parsed["root_hash"]:
        raise _VerificationFailure("Rekor inclusion proof invalid")

    trusted_time = datetime.fromtimestamp(parsed["integrated_time"], tz=timezone.utc)
    log = _trusted_log(
        trusted_root,
        parsed["log_id"],
        trusted_time,
        serialization=serialization,
    )
    public_key = _verify_checkpoint(
        parsed["checkpoint"],
        trusted_log=log,
        tree_size=parsed["tree_size"],
        root_hash=parsed["root_hash"],
        serialization=serialization,
        ed25519=ed25519,
    )
    set_payload = _canonical_json(
        {
            "body": base64.b64encode(parsed["canonicalized_body"]).decode("ascii"),
            "integratedTime": parsed["integrated_time"],
            "logID": parsed["log_id"].hex(),
            "logIndex": parsed["log_index"],
        }
    )
    try:
        public_key.verify(parsed["set_signature"], set_payload)
    except Exception as exc:
        raise _VerificationFailure("Rekor signed entry timestamp invalid") from exc

    try:
        body = json.loads(parsed["canonicalized_body"])
        spec = body["spec"]
        signatures = spec["signatures"]
        if body.get("kind") != "dsse" or body.get("apiVersion") != "0.0.1":
            raise ValueError("kind")
        if spec.get("envelopeHash") != {
            "algorithm": "sha256",
            "value": hashlib.sha256(_canonical_json(parsed["envelope"])).hexdigest(),
        }:
            raise ValueError("envelope hash")
        if spec.get("payloadHash") != {
            "algorithm": "sha256",
            "value": hashlib.sha256(parsed["payload"]).hexdigest(),
        }:
            raise ValueError("payload hash")
        if not isinstance(signatures, list) or len(signatures) != 1:
            raise ValueError("signatures")
        if signatures[0].get("signature") != parsed["envelope"]["signatures"][0].get(
            "sig"
        ):
            raise ValueError("signature")
        verifier_pem = _decode_base64(signatures[0].get("verifier"), "Rekor verifier")
        logged_cert = x509.load_pem_x509_certificate(verifier_pem)
        try:
            leaf_cert = x509.load_der_x509_certificate(parsed["leaf_der"])
        except ValueError:
            leaf_cert = x509.load_pem_x509_certificate(parsed["leaf_der"])
        if logged_cert.public_bytes(serialization.Encoding.DER) != leaf_cert.public_bytes(
            serialization.Encoding.DER
        ):
            raise ValueError("certificate")
    except Exception as exc:
        raise _VerificationFailure(
            "Rekor entry does not bind DSSE envelope and leaf certificate"
        ) from exc
    return trusted_time


def _certificate_time(certificate: Any, field: str) -> datetime:
    value = getattr(certificate, field)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _verify_certificate_signature(certificate: Any, issuer: Any, ec: Any) -> None:
    public_key = issuer.public_key()
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("issuer key algorithm")
    public_key.verify(
        certificate.signature,
        certificate.tbs_certificate_bytes,
        ec.ECDSA(certificate.signature_hash_algorithm),
    )


def _verify_fulcio_chain(
    leaf_der: bytes,
    trusted_root: dict[str, Any],
    trusted_time: datetime,
    *,
    x509: Any,
    ec: Any,
) -> Any:
    try:
        try:
            leaf = x509.load_der_x509_certificate(leaf_der)
        except ValueError:
            leaf = x509.load_pem_x509_certificate(leaf_der)
    except Exception as exc:
        raise _VerificationFailure("Fulcio leaf certificate invalid") from exc
    if not (
        _certificate_time(leaf, "not_valid_before")
        <= trusted_time
        <= _certificate_time(leaf, "not_valid_after")
    ):
        raise _VerificationFailure("Fulcio certificate not valid at trusted signing time")

    for authority in trusted_root["certificateAuthorities"]:
        if not isinstance(authority, dict):
            continue
        try:
            if not _within_time_range(trusted_time, authority.get("validFor")):
                continue
            chain_record = authority.get("certChain")
            records = chain_record.get("certificates") if isinstance(chain_record, dict) else None
            if not isinstance(records, list) or not records:
                continue
            chain = []
            for record in records:
                if not isinstance(record, dict):
                    continue
                certificate_bytes = _decode_base64(
                    record.get("rawBytes"), "trusted CA certificate"
                )
                try:
                    certificate = x509.load_der_x509_certificate(certificate_bytes)
                except ValueError:
                    certificate = x509.load_pem_x509_certificate(certificate_bytes)
                chain.append(certificate)
            if len(chain) != len(records):
                continue
            current = leaf
            for issuer in chain:
                if current.issuer != issuer.subject:
                    raise ValueError("issuer name")
                if not (
                    _certificate_time(issuer, "not_valid_before")
                    <= trusted_time
                    <= _certificate_time(issuer, "not_valid_after")
                ):
                    raise ValueError("issuer validity")
                constraints = issuer.extensions.get_extension_for_class(
                    x509.BasicConstraints
                ).value
                if not constraints.ca:
                    raise ValueError("issuer constraints")
                try:
                    usage = issuer.extensions.get_extension_for_class(x509.KeyUsage).value
                    if not usage.key_cert_sign:
                        raise ValueError("issuer key usage")
                except x509.ExtensionNotFound:
                    pass
                _verify_certificate_signature(current, issuer, ec)
                current = issuer
            leaf_key = leaf.public_key()
            if not isinstance(leaf_key, ec.EllipticCurvePublicKey) or not isinstance(
                leaf_key.curve, ec.SECP256R1
            ):
                raise ValueError("leaf key algorithm")
            constraints = leaf.extensions.get_extension_for_class(x509.BasicConstraints).value
            if constraints.ca:
                raise ValueError("leaf constraints")
            try:
                usage = leaf.extensions.get_extension_for_class(x509.KeyUsage).value
                if not usage.digital_signature:
                    raise ValueError("leaf key usage")
            except x509.ExtensionNotFound:
                pass
            return leaf
        except Exception:
            continue
    raise _VerificationFailure("Fulcio certificate chain invalid")


def _pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"".join(
        (
            b"DSSEv1 ",
            str(len(type_bytes)).encode("ascii"),
            b" ",
            type_bytes,
            b" ",
            str(len(payload)).encode("ascii"),
            b" ",
            payload,
        )
    )


def _verify_dsse_and_subject(
    parsed: dict[str, Any], evidence_bytes: bytes, leaf: Any, *, ec: Any, hashes: Any
) -> None:
    try:
        leaf.public_key().verify(
            parsed["dsse_signature"],
            _pae(_DSSE_PAYLOAD_TYPE, parsed["payload"]),
            ec.ECDSA(hashes.SHA256()),
        )
    except Exception as exc:
        raise _VerificationFailure("DSSE signature invalid") from exc
    try:
        statement = json.loads(parsed["payload"])
        subjects = statement.get("subject")
        expected = hashlib.sha256(evidence_bytes).hexdigest()
        if not isinstance(subjects, list) or not any(
            isinstance(subject, dict)
            and isinstance(subject.get("digest"), dict)
            and subject["digest"].get("sha256") == expected
            for subject in subjects
        ):
            raise ValueError("digest")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError) as exc:
        raise _VerificationFailure("evidence subject digest mismatch") from exc


def _decode_der_utf8(value: bytes) -> str:
    if len(value) < 2 or value[0] != 0x0C:
        raise ValueError("not a DER UTF8String")
    first_length = value[1]
    offset = 2
    if first_length & 0x80:
        length_bytes = first_length & 0x7F
        if length_bytes == 0 or length_bytes > 4 or len(value) < offset + length_bytes:
            raise ValueError("invalid DER length")
        length = int.from_bytes(value[offset : offset + length_bytes], "big")
        offset += length_bytes
    else:
        length = first_length
    if offset + length != len(value):
        raise ValueError("invalid DER value length")
    return value[offset:].decode("utf-8")


def _verify_identity(leaf: Any, identity_policy: dict[str, str], *, x509: Any) -> None:
    try:
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        subjects = list(san.get_values_for_type(x509.RFC822Name))
        subjects += list(san.get_values_for_type(x509.UniformResourceIdentifier))
        if len(subjects) != 1:
            raise ValueError("ambiguous SAN")
        issuer = None
        try:
            extension = leaf.extensions.get_extension_for_oid(
                x509.ObjectIdentifier(_OIDC_ISSUER_V2_OID)
            )
            issuer = _decode_der_utf8(extension.value.value)
        except x509.ExtensionNotFound:
            extension = leaf.extensions.get_extension_for_oid(
                x509.ObjectIdentifier(_OIDC_ISSUER_LEGACY_OID)
            )
            issuer = extension.value.value.decode("utf-8")
    except Exception as exc:
        raise _VerificationFailure("OIDC identity extension invalid") from exc
    if issuer != identity_policy["issuer"]:
        raise _VerificationFailure("OIDC issuer mismatch")
    if subjects[0] != identity_policy["subject"]:
        raise _VerificationFailure("OIDC subject mismatch")


def verify_keyless_bundle(
    bundle: dict,
    evidence_bytes: bytes,
    identity_policy: dict,
    trusted_root: dict,
) -> dict:
    """Re-derive a keyless signing anchor from a pinned Sigstore bundle offline."""

    if not isinstance(bundle, dict):
        raise TypeError("bundle must be a dict")
    if not isinstance(evidence_bytes, bytes):
        raise TypeError("evidence_bytes must be bytes")
    if not isinstance(identity_policy, dict) or set(identity_policy) != {"issuer", "subject"}:
        raise ValueError("identity_policy must contain exactly issuer and subject")
    if not all(isinstance(identity_policy[key], str) and identity_policy[key] for key in identity_policy):
        raise ValueError("identity_policy issuer and subject must be non-empty strings")
    if not isinstance(trusted_root, dict):
        raise TypeError("trusted_root must be a dict")

    try:
        parsed = _parse_structure(bundle, trusted_root)
    except _VerificationFailure as exc:
        return _blocked(str(exc))

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519
    except ImportError:
        return _blocked("keyless verification unavailable (install depone[keyless])")

    try:
        trusted_time = _verify_rekor(
            parsed,
            trusted_root,
            x509=x509,
            serialization=serialization,
            ed25519=ed25519,
        )
        leaf = _verify_fulcio_chain(
            parsed["leaf_der"], trusted_root, trusted_time, x509=x509, ec=ec
        )
        _verify_dsse_and_subject(parsed, evidence_bytes, leaf, ec=ec, hashes=hashes)
        _verify_identity(leaf, identity_policy, x509=x509)
    except _VerificationFailure as exc:
        return _blocked(str(exc))
    except Exception:
        return _blocked("keyless verification failed")
    return _passed()
