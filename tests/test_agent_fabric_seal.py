from __future__ import annotations

import json
import unittest

from depone.agent_fabric.seal import seal_capture, verify_capture_seal


class AgentFabricSealTest(unittest.TestCase):
    def test_round_trip_verifies_with_same_key(self) -> None:
        capture = {"observed_by": "observer", "touched_files": ["sample.txt"]}
        key = b"observer-held-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        self.assertTrue(verify_capture_seal(capture, seal, key))

    def test_wrong_key_tamper_and_malformed_seal_fail_closed(self) -> None:
        capture = {"observed_by": "observer", "touched_files": ["sample.txt"]}
        key = b"observer-held-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        self.assertFalse(verify_capture_seal(capture, seal, b"wrong-key"))
        tampered = dict(capture)
        tampered["touched_files"] = ["other.txt"]
        self.assertFalse(verify_capture_seal(tampered, seal, key))
        malformed = dict(seal)
        malformed["alg"] = "HMAC-SHA1"
        self.assertFalse(verify_capture_seal(capture, malformed, key))
        self.assertFalse(verify_capture_seal(capture, {"alg": "HMAC-SHA256"}, key))

    def test_key_id_is_non_secret_label_not_key_material(self) -> None:
        capture = {"observed_by": "observer"}
        key = b"super-secret-observer-key"
        seal = seal_capture(capture, key, key_id="observer-key-1")
        seal_json = json.dumps(seal, sort_keys=True)
        self.assertNotEqual(seal["key_id"], key.decode("utf-8"))
        self.assertNotIn(key.decode("utf-8"), seal_json)

if __name__ == "__main__":
    unittest.main()
