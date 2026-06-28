"""Observer-held HMAC seals for Agent Fabric captures.

The seal is symmetric HMAC-SHA256, not a public/asymmetric signature. It gives
integrity and authenticity to holders of the key and detects forgery by a party
without the key. It is not forge-proof against a same-uid runner that can read
the key; full privilege-boundary custody and A3 public signing remain deferred.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
from pathlib import Path
from typing import Any

ALG = "HMAC-SHA256"
BOUNDARY = {
    "symmetric": True,
    "public_verifiable": False,
    "forge_proof_same_uid": False,
}
BOUNDARY_NOTE = (
    "Symmetric HMAC seal: integrity/authenticity for key holders only; "
    "not public signing and not forge-proof if a same-uid runner can read the key."
)


def _canonical_bytes(capture: dict[str, Any]) -> bytes:
    """Return the same canonical JSON bytes used by claim_gate.canonical_hash."""

    return json.dumps(capture, sort_keys=True, separators=(",", ":")).encode("utf-8")


def seal_capture(capture: dict[str, Any], key: bytes, *, key_id: str) -> dict[str, Any]:
    """Seal a capture with an observer-held symmetric key.

    key_id is a non-secret caller-supplied label. It is never derived from the
    key, and the returned record must not be described as a public signature.
    """

    if not isinstance(capture, dict):
        raise ValueError("capture must be a JSON object")
    if not isinstance(key, bytes) or not key:
        raise ValueError("seal key must be non-empty bytes")
    if not isinstance(key_id, str) or not key_id:
        raise ValueError("key_id must be a non-empty non-secret label")
    value = hmac.new(key, _canonical_bytes(capture), hashlib.sha256).hexdigest()
    return {
        "alg": ALG,
        "key_id": key_id,
        "value": value,
        "boundary": dict(BOUNDARY),
        "note": BOUNDARY_NOTE,
    }


def verify_capture_seal(
    capture: dict[str, Any],
    seal: dict[str, Any],
    key: bytes,
) -> bool:
    """Verify a symmetric capture seal, returning False on any malformed input."""

    try:
        if not isinstance(capture, dict) or not isinstance(seal, dict):
            return False
        if seal.get("alg") != ALG:
            return False
        key_id = seal.get("key_id")
        value = seal.get("value")
        boundary = seal.get("boundary")
        if not isinstance(key_id, str) or not key_id:
            return False
        if not isinstance(value, str):
            return False
        if not isinstance(boundary, dict):
            return False
        if boundary.get("symmetric") is not True:
            return False
        if boundary.get("public_verifiable") is not False:
            return False
        if boundary.get("forge_proof_same_uid") is not False:
            return False
        expected = seal_capture(capture, key, key_id=key_id)
        return hmac.compare_digest(value, expected["value"])
    except Exception:
        return False


def _self_test() -> None:
    capture: dict[str, Any] = {
        "observed_by": "depone.agent_fabric.observer",
        "touched_files": ["sample.txt"],
        "observer_independence": {"privilege_boundary": False},
    }
    key = b"observer-held-key"
    seal = seal_capture(capture, key, key_id="observer-key-1")
    if not verify_capture_seal(capture, seal, key):
        raise AssertionError("same key should verify")
    if verify_capture_seal(capture, seal, b"wrong-key"):
        raise AssertionError("wrong key should not verify")
    tampered = dict(capture)
    tampered["touched_files"] = ["other.txt"]
    if verify_capture_seal(tampered, seal, key):
        raise AssertionError("tampered capture should not verify")
    bad_seal = dict(seal)
    bad_seal["alg"] = "not-hmac"
    if verify_capture_seal(capture, bad_seal, key):
        raise AssertionError("wrong alg should not verify")
    if key.decode("utf-8") == seal["key_id"]:
        raise AssertionError("key_id must not be the key")
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "capture.seal.json"
        path.write_text(json.dumps(seal, sort_keys=True), encoding="utf-8")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not verify_capture_seal(capture, loaded, key):
            raise AssertionError("serialized seal should verify")
    print("depone agent-fabric-seal --self-test: pass")
