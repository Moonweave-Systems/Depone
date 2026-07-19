from __future__ import annotations

import base64
import builtins
import json
import socket
import unittest
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


FIXTURE_ROOT = "fixtures/agent_fabric/keyless/verify"
IDENTITY_POLICY = {
    "issuer": "https://oauth2.sigstore.dev/auth",
    "subject": "octocat@example.com",
}


@unittest.skipUnless(
    HAS_CRYPTOGRAPHY, "requires the depone[keyless] extra (cryptography)"
)
class AgentFabricKeylessVerifyTest(unittest.TestCase):
    def _bundle(self) -> dict[str, object]:
        return json.loads(resource_text(f"{FIXTURE_ROOT}/valid-bundle.json"))

    def _trusted_root(self) -> dict[str, object]:
        return json.loads(resource_text(f"{FIXTURE_ROOT}/trusted-root.json"))

    def _evidence(self) -> bytes:
        return resource_bytes(f"{FIXTURE_ROOT}/evidence.bin")

    def _verify(
        self,
        bundle: dict[str, object] | None = None,
        *,
        evidence: bytes | None = None,
        policy: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return verify_keyless_bundle(
            bundle if bundle is not None else self._bundle(),
            evidence if evidence is not None else self._evidence(),
            policy if policy is not None else dict(IDENTITY_POLICY),
            self._trusted_root(),
        )

    def assertBlocked(self, report: dict[str, object], reason: str) -> None:  # noqa: N802
        self.assertEqual(report["decision"], "blocked")
        self.assertIsNone(report["anchor_class"])
        self.assertFalse(report["keyless_identity"])
        self.assertFalse(report["transparency_logged"])
        self.assertFalse(report["signature_verified"])
        self.assertFalse(report["raises_assurance"])
        self.assertIn(reason, report["reasons"])

    def test_valid_bundle_passes_with_exact_federated_identity_policy(self) -> None:
        report = self._verify()

        self.assertEqual(report["decision"], "pass")
        self.assertEqual(
            report["anchor_class"], ANCHOR_CLASS_KEYLESS_TRANSPARENCY_LOGGED
        )
        self.assertTrue(report["keyless_identity"])
        self.assertTrue(report["transparency_logged"])
        self.assertTrue(report["signature_verified"])
        self.assertFalse(report["raises_assurance"])
        self.assertEqual(report["reasons"], [])

    def test_tampered_leaf_certificate_fails_closed(self) -> None:
        bundle = self._bundle()
        certificate = bundle["verificationMaterial"]["certificate"]
        leaf = bytearray(base64.b64decode(certificate["rawBytes"]))
        leaf[-1] ^= 1
        certificate["rawBytes"] = base64.b64encode(leaf).decode("ascii")

        self.assertBlocked(
            self._verify(bundle),
            "Rekor entry does not bind DSSE envelope and leaf certificate",
        )

    def test_wrong_policy_issuer_fails_closed(self) -> None:
        policy = dict(IDENTITY_POLICY)
        policy["issuer"] = "https://issuer.example.invalid"

        self.assertBlocked(self._verify(policy=policy), "OIDC issuer mismatch")

    def test_wrong_policy_subject_fails_closed(self) -> None:
        policy = dict(IDENTITY_POLICY)
        policy["subject"] = "mallory@example.com"

        self.assertBlocked(self._verify(policy=policy), "OIDC subject mismatch")

    def test_corrupted_merkle_inclusion_node_fails_closed(self) -> None:
        bundle = self._bundle()
        proof = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]
        node = bytearray(base64.b64decode(proof["hashes"][0]))
        node[0] ^= 1
        proof["hashes"][0] = base64.b64encode(node).decode("ascii")

        self.assertBlocked(self._verify(bundle), "Rekor inclusion proof invalid")

    def test_bad_checkpoint_signature_fails_closed(self) -> None:
        bundle = self._bundle()
        checkpoint = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionProof"][
            "checkpoint"
        ]
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

    def test_bad_signed_entry_timestamp_fails_closed(self) -> None:
        bundle = self._bundle()
        promise = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionPromise"]
        signature = bytearray(base64.b64decode(promise["signedEntryTimestamp"]))
        signature[-1] ^= 1
        promise["signedEntryTimestamp"] = base64.b64encode(signature).decode("ascii")

        self.assertBlocked(self._verify(bundle), "Rekor signed entry timestamp invalid")

    def test_subject_digest_mismatch_fails_closed(self) -> None:
        self.assertBlocked(
            self._verify(evidence=self._evidence() + b"tampered"),
            "evidence subject digest mismatch",
        )

    def test_certificate_outside_trusted_time_fails_closed(self) -> None:
        bundle = self._bundle()
        expired_bundle = json.loads(
            resource_text(f"{FIXTURE_ROOT}/expired-certificate-bundle.json")
        )
        bundle["verificationMaterial"] = expired_bundle["verificationMaterial"]

        self.assertBlocked(
            self._verify(bundle),
            "Fulcio certificate not valid at trusted signing time",
        )

    def test_valid_bundle_verifies_without_network(self) -> None:
        with (
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(
                socket, "create_connection", side_effect=AssertionError("network")
            ),
        ):
            self.assertEqual(self._verify()["decision"], "pass")

    def test_legacy_raw_oidc_issuer_extension_is_accepted(self) -> None:
        legacy_bundle = json.loads(
            resource_text(f"{FIXTURE_ROOT}/legacy-issuer-bundle.json")
        )

        report = self._verify(legacy_bundle)

        self.assertEqual(report["decision"], "pass")

    def test_equivalent_pem_certificates_and_log_key_are_accepted(self) -> None:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        bundle = self._bundle()
        trusted_root = self._trusted_root()
        leaf_record = bundle["verificationMaterial"]["certificate"]
        leaf = x509.load_der_x509_certificate(base64.b64decode(leaf_record["rawBytes"]))
        leaf_record["rawBytes"] = base64.b64encode(
            leaf.public_bytes(serialization.Encoding.PEM)
        ).decode("ascii")
        ca_record = trusted_root["certificateAuthorities"][0]["certChain"][
            "certificates"
        ][0]
        ca = x509.load_der_x509_certificate(base64.b64decode(ca_record["rawBytes"]))
        ca_record["rawBytes"] = base64.b64encode(
            ca.public_bytes(serialization.Encoding.PEM)
        ).decode("ascii")
        log_key_record = trusted_root["tlogs"][0]["publicKey"]
        log_key = serialization.load_der_public_key(
            base64.b64decode(log_key_record["rawBytes"])
        )
        log_key_record["rawBytes"] = base64.b64encode(
            log_key.public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ).decode("ascii")

        report = verify_keyless_bundle(
            bundle, self._evidence(), dict(IDENTITY_POLICY), trusted_root
        )
        self.assertEqual(report["decision"], "pass")

    def test_log_id_must_match_pinned_public_key_bytes(self) -> None:
        trusted_root = self._trusted_root()
        trusted_root["tlogs"][0]["publicKey"]["rawBytes"] = base64.b64encode(
            b"not the pinned log key"
        ).decode("ascii")

        report = verify_keyless_bundle(
            self._bundle(), self._evidence(), dict(IDENTITY_POLICY), trusted_root
        )
        self.assertBlocked(report, "Rekor log key not trusted")

    def test_missing_cryptography_extra_fails_closed(self) -> None:
        real_import = builtins.__import__

        def import_without_cryptography(
            name: str,
            globals: object = None,
            locals: object = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "cryptography" or name.startswith("cryptography."):
                raise ImportError("simulated absent optional dependency")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=import_without_cryptography):
            report = self._verify()

        self.assertEqual(
            report,
            {
                "decision": "blocked",
                "anchor_class": None,
                "keyless_identity": False,
                "transparency_logged": False,
                "signature_verified": False,
                "raises_assurance": False,
                "reasons": [
                    "keyless verification unavailable (install depone[keyless])"
                ],
            },
        )

    def test_missing_required_bundle_structure_fails_closed(self) -> None:
        bundle = self._bundle()
        del bundle["verificationMaterial"]

        self.assertBlocked(
            self._verify(bundle),
            "bundle structure invalid: verificationMaterial must be an object",
        )

    def test_unsupported_bundle_media_type_fails_closed(self) -> None:
        bundle = self._bundle()
        bundle["mediaType"] = "application/example"

        self.assertBlocked(
            self._verify(bundle), "bundle structure invalid: unsupported mediaType"
        )


if __name__ == "__main__":
    unittest.main()
