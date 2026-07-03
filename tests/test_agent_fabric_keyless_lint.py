from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.keyless import (
    SIGNING_STATUS_KEYLESS_FULCIO_REKOR,
    keyless_fixture_boundary,
    lint_keyless_bundle_fixture,
)
from depone.agent_fabric.sign import (
    _generate_ed25519_keypair,
    openssl_path,
    verify_signed_bundle,
)


class AgentFabricKeylessLintTest(unittest.TestCase):
    def _fixture(self, name: str) -> dict[str, object]:
        return json.loads(resource_text(f"fixtures/agent_fabric/keyless/{name}"))

    def _pinned_hash(self) -> str:
        return resource_text("fixtures/agent_fabric/keyless/keyless-bundle.sha256").strip()

    def test_fixture_subject_is_real_depone_valid_capture_manifest(self) -> None:
        capture = json.loads(
            resource_text("fixtures/agent_fabric/keyless/keyless-capture-manifest.json")
        )
        self.assertEqual(validate_capture_manifest(capture), [])

    def test_linter_lints_pinned_shape_but_never_trusts_signature(self) -> None:
        report = lint_keyless_bundle_fixture(
            self._fixture("keyless-bundle.json"),
            expected_bundle_sha256=self._pinned_hash(),
        )
        self.assertEqual(report["decision"], "lint_passed")
        self.assertEqual(report["signing_status"], SIGNING_STATUS_KEYLESS_FULCIO_REKOR)
        self.assertFalse(report["signature_verified"])
        self.assertFalse(report["trusts_external_signature"])
        self.assertFalse(report["keyless_identity"])
        self.assertFalse(report["transparency_logged"])
        self.assertFalse(report["boundary"]["raises_assurance"])
        self.assertFalse(report["boundary"]["trusts_external_signature"])

    def test_operator_verifier_rejects_keyless_bundle(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl executable is not on PATH")
        bundle = self._fixture("keyless-bundle.json")
        with tempfile.TemporaryDirectory() as temp_text:
            _private_key, public_key = _generate_ed25519_keypair(Path(temp_text))
            self.assertFalse(verify_signed_bundle(bundle, str(public_key)))

    def test_self_consistent_forged_bundle_is_blocked_by_pin(self) -> None:
        report = lint_keyless_bundle_fixture(
            self._fixture("negative-forged-self-consistent.json"),
            expected_bundle_sha256=self._pinned_hash(),
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIn("fixture hash mismatch", report["reasons"])
        self.assertFalse(report["signature_verified"])

    def test_valid_embedded_capture_with_fake_subject_digest_is_blocked(self) -> None:
        report = lint_keyless_bundle_fixture(
            self._fixture("negative-fake-subject.json"),
            expected_bundle_sha256=None,
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIn("subject digest mismatch", report["reasons"])
        self.assertFalse(report["signature_verified"])

    def test_assurance_upgrade_is_blocked(self) -> None:
        report = lint_keyless_bundle_fixture(
            self._fixture("negative-assurance-upgrade.json"),
            expected_bundle_sha256=None,
        )
        self.assertEqual(report["decision"], "blocked")
        self.assertIn("assurance exceeds A2", report["reasons"])
        self.assertFalse(report["signature_verified"])

    def test_boundary_is_not_operator_key(self) -> None:
        boundary = keyless_fixture_boundary()
        self.assertFalse(boundary["operator_key"])
        self.assertFalse(boundary["keyless_identity"])
        self.assertFalse(boundary["transparency_logged"])
        self.assertTrue(boundary["claimed_keyless_identity"])
        self.assertTrue(boundary["claimed_rekor_metadata"])
        self.assertFalse(boundary["raises_assurance"])
        self.assertFalse(boundary["trusts_external_signature"])


if __name__ == "__main__":
    unittest.main()
