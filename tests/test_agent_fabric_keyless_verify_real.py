from __future__ import annotations

import base64
import hashlib
import json
import socket
import unittest
from datetime import timedelta, timezone
from unittest import mock

from depone._resources import resource_bytes, resource_text
from depone.agent_fabric.keyless_verify import (
    ANCHOR_CLASS_KEYLESS_TRANSPARENCY_LOGGED,
    verify_keyless_bundle,
)

try:
    import cryptography  # noqa: F401

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


FIXTURE_ROOT = "fixtures/agent_fabric/keyless/verify/real"


@unittest.skipUnless(
    HAS_CRYPTOGRAPHY, "requires the depone[keyless] extra (cryptography)"
)
class AgentFabricKeylessVerifyRealTest(unittest.TestCase):
    def _bundle(self) -> dict[str, object]:
        return json.loads(resource_text(f"{FIXTURE_ROOT}/real-bundle.json"))

    def _trusted_root(self) -> dict[str, object]:
        return json.loads(resource_text(f"{FIXTURE_ROOT}/prod-trusted-root.json"))

    def _evidence(self) -> bytes:
        return resource_bytes(f"{FIXTURE_ROOT}/evidence-sigstore-4.4.0.whl")

    def _policy(self) -> dict[str, str]:
        return json.loads(resource_text(f"{FIXTURE_ROOT}/identity-policy.json"))

    def _verify(
        self,
        bundle: dict[str, object] | None = None,
        *,
        evidence: bytes | None = None,
        policy: dict[str, str] | None = None,
        trusted_root: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return verify_keyless_bundle(
            bundle if bundle is not None else self._bundle(),
            evidence if evidence is not None else self._evidence(),
            policy if policy is not None else self._policy(),
            trusted_root if trusted_root is not None else self._trusted_root(),
        )

    def assertBlocked(self, report: dict[str, object], reason: str) -> None:  # noqa: N802
        self.assertEqual(report["decision"], "blocked")
        self.assertIsNone(report["anchor_class"])
        self.assertFalse(report["keyless_identity"])
        self.assertFalse(report["transparency_logged"])
        self.assertFalse(report["signature_verified"])
        self.assertFalse(report["raises_assurance"])
        self.assertIn(reason, report["reasons"])

    def test_real_sigstore_bundle_verifies(self) -> None:
        report = self._verify()

        self.assertEqual(report["decision"], "pass", report)
        self.assertEqual(
            report["anchor_class"], ANCHOR_CLASS_KEYLESS_TRANSPARENCY_LOGGED
        )
        self.assertTrue(report["keyless_identity"])
        self.assertTrue(report["transparency_logged"])
        self.assertTrue(report["signature_verified"])
        self.assertFalse(report["raises_assurance"])
        self.assertEqual(report["reasons"], [])

    def test_real_rekor_indices_are_distinct_and_verify_in_their_own_domains(self) -> None:
        bundle = self._bundle()
        entry = bundle["verificationMaterial"]["tlogEntries"][0]

        self.assertNotEqual(entry["logIndex"], entry["inclusionProof"]["logIndex"])
        self.assertGreaterEqual(int(entry["logIndex"]), int(entry["inclusionProof"]["treeSize"]))
        self.assertEqual(self._verify(bundle)["decision"], "pass")

    def test_real_checkpoint_uses_ecdsa_without_checkpoint_key_id(self) -> None:
        from cryptography.hazmat.primitives import serialization

        bundle = self._bundle()
        trusted_root = self._trusted_root()
        entry = bundle["verificationMaterial"]["tlogEntries"][0]
        log_id = base64.b64decode(entry["logId"]["keyId"])
        trusted_log = next(
            log
            for log in trusted_root["tlogs"]
            if base64.b64decode(log["logId"]["keyId"]) == log_id
        )
        checkpoint_signature = base64.b64decode(
            entry["inclusionProof"]["checkpoint"]["envelope"]
            .split("\n\n", 1)[1]
            .strip()
            .rsplit(" ", 1)[1]
        )
        public_key = serialization.load_der_public_key(
            base64.b64decode(trusted_log["publicKey"]["rawBytes"])
        )
        normalized_key = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        self.assertEqual(
            trusted_log["publicKey"]["keyDetails"], "PKIX_ECDSA_P256_SHA_256"
        )
        self.assertNotIn("checkpointKeyId", trusted_log)
        self.assertEqual(checkpoint_signature[:4], log_id[:4])
        self.assertEqual(
            checkpoint_signature[:4], hashlib.sha256(normalized_key).digest()[:4]
        )
        self.assertEqual(
            trusted_root["mediaType"],
            "application/vnd.dev.sigstore.trustedroot+json;version=0.1",
        )
        self.assertEqual(self._verify(bundle, trusted_root=trusted_root)["decision"], "pass")

    def test_unsupported_real_trusted_root_media_type_fails_closed(self) -> None:
        trusted_root = self._trusted_root()
        trusted_root["mediaType"] = "application/example"

        self.assertBlocked(
            self._verify(trusted_root=trusted_root),
            "trusted root invalid: unsupported mediaType",
        )

    def test_real_tree_local_index_is_range_checked(self) -> None:
        bundle = self._bundle()
        proof = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]
        proof["logIndex"] = proof["treeSize"]

        self.assertBlocked(
            self._verify(bundle),
            "bundle structure invalid: Rekor log index is out of range",
        )

    def test_real_bundle_verifies_without_network(self) -> None:
        with (
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(
                socket, "create_connection", side_effect=AssertionError("network")
            ),
        ):
            self.assertEqual(self._verify()["decision"], "pass")

    def test_tampered_real_leaf_certificate_fails_closed(self) -> None:
        bundle = self._bundle()
        certificate = bundle["verificationMaterial"]["certificate"]
        leaf = bytearray(base64.b64decode(certificate["rawBytes"]))
        leaf[-1] ^= 1
        certificate["rawBytes"] = base64.b64encode(leaf).decode("ascii")

        self.assertBlocked(
            self._verify(bundle),
            "Rekor entry does not bind DSSE envelope and leaf certificate",
        )

    def test_wrong_real_policy_issuer_fails_closed(self) -> None:
        policy = self._policy()
        policy["issuer"] = "https://issuer.example.invalid"

        self.assertBlocked(self._verify(policy=policy), "OIDC issuer mismatch")

    def test_wrong_real_policy_subject_fails_closed(self) -> None:
        policy = self._policy()
        policy["subject"] = "https://github.com/example/wrong-workflow.yml@refs/heads/main"

        self.assertBlocked(self._verify(policy=policy), "OIDC subject mismatch")

    def test_corrupted_real_merkle_inclusion_node_fails_closed(self) -> None:
        bundle = self._bundle()
        proof = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]
        node = bytearray(base64.b64decode(proof["hashes"][0]))
        node[0] ^= 1
        proof["hashes"][0] = base64.b64encode(node).decode("ascii")

        self.assertBlocked(self._verify(bundle), "Rekor inclusion proof invalid")

    def test_bad_real_checkpoint_signature_fails_closed(self) -> None:
        bundle = self._bundle()
        checkpoint = bundle["verificationMaterial"]["tlogEntries"][0][
            "inclusionProof"
        ]["checkpoint"]
        body, signature_line = checkpoint["envelope"].split("\n\n", 1)
        prefix, encoded = signature_line.strip().rsplit(" ", 1)
        signature = bytearray(base64.b64decode(encoded))
        signature[-1] ^= 1
        checkpoint["envelope"] = (
            body
            + "\n\n"
            + prefix
            + " "
            + base64.b64encode(signature).decode("ascii")
            + "\n"
        )

        self.assertBlocked(self._verify(bundle), "Rekor checkpoint signature invalid")

    def test_bad_real_checkpoint_key_hint_fails_closed(self) -> None:
        bundle = self._bundle()
        checkpoint = bundle["verificationMaterial"]["tlogEntries"][0][
            "inclusionProof"
        ]["checkpoint"]
        body, signature_line = checkpoint["envelope"].split("\n\n", 1)
        prefix, encoded = signature_line.strip().rsplit(" ", 1)
        signature = bytearray(base64.b64decode(encoded))
        signature[0] ^= 1
        checkpoint["envelope"] = (
            body
            + "\n\n"
            + prefix
            + " "
            + base64.b64encode(signature).decode("ascii")
            + "\n"
        )

        self.assertBlocked(self._verify(bundle), "Rekor checkpoint signature invalid")

    def test_bad_real_signed_entry_timestamp_fails_closed(self) -> None:
        bundle = self._bundle()
        promise = bundle["verificationMaterial"]["tlogEntries"][0][
            "inclusionPromise"
        ]
        signature = bytearray(base64.b64decode(promise["signedEntryTimestamp"]))
        signature[-1] ^= 1
        promise["signedEntryTimestamp"] = base64.b64encode(signature).decode("ascii")

        self.assertBlocked(self._verify(bundle), "Rekor signed entry timestamp invalid")

    def test_global_log_index_is_bound_by_real_set(self) -> None:
        bundle = self._bundle()
        entry = bundle["verificationMaterial"]["tlogEntries"][0]
        entry["logIndex"] = str(int(entry["logIndex"]) + 1)

        self.assertBlocked(self._verify(bundle), "Rekor signed entry timestamp invalid")

    def test_real_rekor_body_must_bind_exact_envelope(self) -> None:
        bundle = self._bundle()
        bundle["dsseEnvelope"]["unexpected"] = "not logged"

        self.assertBlocked(
            self._verify(bundle),
            "Rekor entry does not bind DSSE envelope and leaf certificate",
        )

    def test_real_subject_digest_mismatch_fails_closed(self) -> None:
        self.assertBlocked(
            self._verify(evidence=self._evidence() + b"tampered"),
            "evidence subject digest mismatch",
        )

    def test_real_certificate_outside_trusted_time_fails_closed(self) -> None:
        from cryptography import x509

        bundle = self._bundle()
        certificate = bundle["verificationMaterial"]["certificate"]
        leaf = x509.load_der_x509_certificate(base64.b64decode(certificate["rawBytes"]))
        outside_time = leaf.not_valid_before.replace(tzinfo=timezone.utc) - timedelta(
            seconds=1
        )
        bundle["verificationMaterial"]["tlogEntries"][0]["integratedTime"] = str(
            int(outside_time.timestamp())
        )

        with mock.patch(
            "depone.agent_fabric.keyless_verify._verify_rekor",
            return_value=outside_time,
        ):
            self.assertBlocked(
                self._verify(bundle),
                "Fulcio certificate not valid at trusted signing time",
            )


if __name__ == "__main__":
    unittest.main()
