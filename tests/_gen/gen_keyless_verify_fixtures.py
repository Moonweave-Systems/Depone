#!/usr/bin/env python3
"""Generate the pinned synthetic Sigstore keyless verification fixtures."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID, ObjectIdentifier


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "depone/fixtures/agent_fabric/keyless/verify"
ISSUER = "https://oauth2.sigstore.dev/auth"
SUBJECT = "octocat@example.com"
INTEGRATED_TIME = 1_735_689_600  # 2025-01-01T00:00:00Z
LOG_ORIGIN = "rekor.synthetic.depone.invalid"
GLOBAL_LOG_INDEX = 17
PROOF_LOG_INDEX = 0
PAYLOAD_TYPE = "application/vnd.in-toto+json"


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


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


def _der_utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) >= 128:
        raise ValueError("fixture issuer is too long for the simple DER encoder")
    return b"\x0c" + bytes((len(encoded),)) + encoded


def _leaf_hash(body: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + body).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _certificate(
    *,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_cert: x509.Certificate,
    leaf_key: ec.EllipticCurvePrivateKey,
    not_before: datetime,
    not_after: datetime,
    serial: int,
    legacy_issuer_oid: bool = False,
) -> x509.Certificate:
    issuer_oid = (
        "1.3.6.1.4.1.57264.1.1"
        if legacy_issuer_oid
        else "1.3.6.1.4.1.57264.1.8"
    )
    issuer_value = ISSUER.encode("utf-8") if legacy_issuer_oid else _der_utf8(ISSUER)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, SUBJECT)]))
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(serial)
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.RFC822Name(SUBJECT)]), critical=True)
        .add_extension(
            x509.UnrecognizedExtension(
                ObjectIdentifier(issuer_oid), issuer_value
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )


def _verification_material(
    *,
    certificate: x509.Certificate,
    envelope: dict[str, object],
    payload: bytes,
    log_key: ed25519.Ed25519PrivateKey,
    log_id: bytes,
) -> dict[str, object]:
    certificate_der = certificate.public_bytes(serialization.Encoding.DER)
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    rekor_body = {
        "apiVersion": "0.0.1",
        "kind": "dsse",
        "spec": {
            "envelopeHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(_canonical_json(envelope)).hexdigest(),
            },
            "payloadHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(payload).hexdigest(),
            },
            "signatures": [
                {
                    "signature": envelope["signatures"][0]["sig"],
                    "verifier": _b64(certificate_pem),
                }
            ],
        },
    }
    canonicalized_body = _canonical_json(rekor_body)
    set_payload = _canonical_json(
        {
            "body": _b64(canonicalized_body),
            "integratedTime": INTEGRATED_TIME,
            "logID": log_id.hex(),
            "logIndex": GLOBAL_LOG_INDEX,
        }
    )
    set_signature = log_key.sign(set_payload)
    decoy_leaf = _leaf_hash(b"depone synthetic second log leaf")
    root_hash = _node_hash(_leaf_hash(canonicalized_body), decoy_leaf)
    checkpoint_body = f"{LOG_ORIGIN} - 123456789\n2\n{_b64(root_hash)}\n".encode(
        "utf-8"
    )
    checkpoint_signature = log_id[:4] + log_key.sign(checkpoint_body)
    checkpoint = (
        checkpoint_body
        + b"\n\xe2\x80\x94 "
        + LOG_ORIGIN.encode("utf-8")
        + b" "
        + base64.b64encode(checkpoint_signature)
        + b"\n"
    ).decode("utf-8")
    return {
        "certificate": {"rawBytes": _b64(certificate_der)},
        "tlogEntries": [
            {
                "logIndex": str(GLOBAL_LOG_INDEX),
                "logId": {"keyId": _b64(log_id)},
                "kindVersion": {"kind": "dsse", "version": "0.0.1"},
                "integratedTime": str(INTEGRATED_TIME),
                "inclusionPromise": {"signedEntryTimestamp": _b64(set_signature)},
                "inclusionProof": {
                    "logIndex": str(PROOF_LOG_INDEX),
                    "rootHash": _b64(root_hash),
                    "treeSize": "2",
                    "hashes": [_b64(decoy_leaf)],
                    "checkpoint": {"envelope": checkpoint},
                },
                "canonicalizedBody": _b64(canonicalized_body),
            }
        ],
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    integrated = datetime.fromtimestamp(INTEGRATED_TIME, tz=timezone.utc)

    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Depone Synthetic Fulcio"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Depone Synthetic Fulcio Root"),
        ]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(1000)
        .not_valid_before(integrated - timedelta(days=365))
        .not_valid_after(integrated + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_cert = _certificate(
        ca_key=ca_key,
        ca_cert=ca_cert,
        leaf_key=leaf_key,
        not_before=integrated - timedelta(minutes=5),
        not_after=integrated + timedelta(minutes=5),
        serial=2000,
    )
    expired_leaf = _certificate(
        ca_key=ca_key,
        ca_cert=ca_cert,
        leaf_key=leaf_key,
        not_before=integrated - timedelta(hours=2),
        not_after=integrated - timedelta(hours=1),
        serial=2001,
    )
    legacy_leaf = _certificate(
        ca_key=ca_key,
        ca_cert=ca_cert,
        leaf_key=leaf_key,
        not_before=integrated - timedelta(minutes=5),
        not_after=integrated + timedelta(minutes=5),
        serial=2002,
        legacy_issuer_oid=True,
    )

    evidence = b"depone synthetic observed evidence\n"
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "evidence.bin",
                "digest": {"sha256": hashlib.sha256(evidence).hexdigest()},
            }
        ],
        "predicateType": "https://depone.dev/attestations/evidence/v1",
        "predicate": {"fixture": "synthetic-keyless-verification"},
    }
    payload = _canonical_json(statement)
    signature = leaf_key.sign(_pae(PAYLOAD_TYPE, payload), ec.ECDSA(hashes.SHA256()))
    envelope = {
        "payload": _b64(payload),
        "payloadType": PAYLOAD_TYPE,
        "signatures": [{"sig": _b64(signature)}],
    }

    log_key = ed25519.Ed25519PrivateKey.generate()
    log_public_der = log_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    log_id = hashlib.sha256(log_public_der).digest()
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "verificationMaterial": _verification_material(
            certificate=leaf_cert,
            envelope=envelope,
            payload=payload,
            log_key=log_key,
            log_id=log_id,
        ),
        "dsseEnvelope": envelope,
    }
    expired_bundle = {
        "mediaType": bundle["mediaType"],
        "verificationMaterial": _verification_material(
            certificate=expired_leaf,
            envelope=envelope,
            payload=payload,
            log_key=log_key,
            log_id=log_id,
        ),
        "dsseEnvelope": envelope,
    }
    legacy_bundle = {
        "mediaType": bundle["mediaType"],
        "verificationMaterial": _verification_material(
            certificate=legacy_leaf,
            envelope=envelope,
            payload=payload,
            log_key=log_key,
            log_id=log_id,
        ),
        "dsseEnvelope": envelope,
    }
    ca_der = ca_cert.public_bytes(serialization.Encoding.DER)
    trusted_root = {
        "mediaType": "application/vnd.dev.sigstore.trustedroot.v0.2+json",
        "tlogs": [
            {
                "baseUrl": f"https://{LOG_ORIGIN}",
                "hashAlgorithm": "SHA2_256",
                "publicKey": {
                    "rawBytes": _b64(log_public_der),
                    "keyDetails": "PKIX_ED25519",
                    "validFor": {
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2026-01-01T00:00:00Z",
                    },
                },
                "logId": {"keyId": _b64(log_id)},
                "operator": "depone.invalid",
            }
        ],
        "certificateAuthorities": [
            {
                "subject": {
                    "organization": "Depone Synthetic Fulcio",
                    "commonName": "Depone Synthetic Fulcio Root",
                },
                "uri": "https://fulcio.synthetic.depone.invalid",
                "certChain": {"certificates": [{"rawBytes": _b64(ca_der)}]},
                "validFor": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2026-01-01T00:00:00Z",
                },
                "operator": "depone.invalid",
            }
        ],
    }

    (OUTPUT / "valid-bundle.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "expired-certificate-bundle.json").write_text(
        json.dumps(expired_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "legacy-issuer-bundle.json").write_text(
        json.dumps(legacy_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "trusted-root.json").write_text(
        json.dumps(trusted_root, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "evidence.bin").write_bytes(evidence)


if __name__ == "__main__":
    main()
