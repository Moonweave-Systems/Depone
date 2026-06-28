"""V128 in-toto/DSSE and OTel GenAI evidence substrate helpers.

The substrate is a derived view over existing Depone evidence. It does not
upgrade assurance and it does not claim signatures when ``signatures`` is empty.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.claim_gate import canonical_hash

INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
DEPONE_PREDICATE_TYPE = "https://depone.dev/attestations/evidence/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
SPAN_SCHEMA_VERSION = "1.0"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _span_id(seed: str, offset: int = 0) -> str:
    digest = canonical_hash({"seed": seed, "offset": offset})
    return digest[:16]


def _trace_id(seed: str) -> str:
    return canonical_hash({"trace": seed})[:32]


def build_intoto_statement_from_capture(
    capture_manifest: dict[str, Any],
    *,
    name: str = "depone-capture-manifest",
) -> dict[str, Any]:
    """Serialize an existing capture manifest as an in-toto Statement."""

    validation_errors = validate_capture_manifest(capture_manifest)
    observer_capture = (
        capture_manifest.get("observer_capture")
        if isinstance(capture_manifest.get("observer_capture"), dict)
        else {}
    )
    subject = [
        {
            "name": name,
            "digest": {"sha256": canonical_hash(capture_manifest)},
        },
        {
            "name": "source_fixture",
            "digest": {"sha256": str(capture_manifest.get("source_fixture_hash", ""))},
        },
    ]
    observer_hash = capture_manifest.get("observer_capture_hash")
    if isinstance(observer_hash, str) and observer_hash:
        subject.append(
            {
                "name": "observer_capture",
                "digest": {"sha256": observer_hash},
            }
        )

    return {
        "_type": INTOTO_STATEMENT_TYPE,
        "subject": subject,
        "predicateType": DEPONE_PREDICATE_TYPE,
        "predicate": {
            "schema_version": "1.0",
            "source_kind": capture_manifest.get("kind"),
            "assurance": capture_manifest.get("assurance"),
            "decision": capture_manifest.get("decision"),
            "validation_errors": validation_errors,
            "allowed_touched_files": capture_manifest.get("allowed_touched_files", []),
            "observer": {
                "observed_by": observer_capture.get("observed_by"),
                "touched_files": observer_capture.get("touched_files", []),
                "test_output": observer_capture.get("test_output", {}),
                "command_receipts": observer_capture.get("command_receipts", []),
            },
            "boundary": {
                "raises_assurance": False,
                "signed": False,
                "signing_status": "unsigned-content-addressed",
            },
        },
    }


def wrap_statement_in_dsse(statement: dict[str, Any]) -> dict[str, Any]:
    """Wrap an in-toto Statement in an unsigned DSSE envelope."""

    payload = _canonical_json(statement).encode("utf-8")
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [],
    }


def decode_dsse_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    if envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise ValueError("unsupported DSSE payloadType")
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        raise ValueError("DSSE payload must be a base64 string")
    decoded = base64.b64decode(payload.encode("ascii")).decode("utf-8")
    value = json.loads(decoded)
    if not isinstance(value, dict):
        raise ValueError("DSSE payload must decode to an object")
    return value


def build_otel_genai_spans(
    capture_manifest: dict[str, Any],
    *,
    runner_receipt: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit static OTel GenAI-shaped spans without inventing usage fields."""

    seed = canonical_hash(
        {
            "capture": capture_manifest,
            "runner": runner_receipt or {},
        }
    )
    trace_id = _trace_id(seed)
    root_span_id = _span_id(seed, 0)
    runner_kind = (
        runner_receipt.get("runner_kind")
        if isinstance(runner_receipt, dict)
        else "unknown"
    )
    arm = runner_receipt.get("arm") if isinstance(runner_receipt, dict) else "unknown"
    spans = [
        {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "name": "invoke_agent",
            "attributes": {
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": str(runner_kind),
                "depone.arm": str(arm),
                "depone.assurance": str(capture_manifest.get("assurance", "")),
                "depone.decision": str(capture_manifest.get("decision", "")),
            },
        }
    ]

    observer_capture = (
        capture_manifest.get("observer_capture")
        if isinstance(capture_manifest.get("observer_capture"), dict)
        else {}
    )
    receipts = observer_capture.get("command_receipts", [])
    if isinstance(receipts, list):
        for index, receipt in enumerate(receipts, start=1):
            if not isinstance(receipt, dict):
                continue
            spans.append(
                {
                    "trace_id": trace_id,
                    "span_id": _span_id(seed, index),
                    "parent_span_id": root_span_id,
                    "name": "execute_tool",
                    "attributes": {
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": "verification_command",
                        "depone.command": receipt.get("command", []),
                        "depone.exit_code": receipt.get("exit_code"),
                        "depone.status": receipt.get("status"),
                    },
                }
            )
    return spans


def build_evidence_bundle(
    capture_manifest: dict[str, Any],
    *,
    runner_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    statement = build_intoto_statement_from_capture(capture_manifest)
    return {
        "kind": "depone-evidence-substrate-bundle",
        "schema_version": "1.0",
        "statement": statement,
        "dsse_envelope": wrap_statement_in_dsse(statement),
        "otel_spans": build_otel_genai_spans(
            capture_manifest,
            runner_receipt=runner_receipt,
        ),
        "assurance": capture_manifest.get("assurance"),
        "signing_status": "unsigned-content-addressed",
        "boundary": {
            "raises_assurance": False,
            "signed": False,
            "approves_public_claim": False,
        },
    }


def validate_statement_for_capture(
    statement: dict[str, Any],
    capture_manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if statement.get("_type") != INTOTO_STATEMENT_TYPE:
        errors.append("statement._type is not in-toto Statement v1")
    if statement.get("predicateType") != DEPONE_PREDICATE_TYPE:
        errors.append("statement.predicateType is not Depone evidence v1")
    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        return errors + ["statement.subject must be a list"]
    digests = {
        item.get("name"): item.get("digest", {}).get("sha256")
        for item in subjects
        if isinstance(item, dict) and isinstance(item.get("digest"), dict)
    }
    expected = {
        "depone-capture-manifest": canonical_hash(capture_manifest),
        "source_fixture": capture_manifest.get("source_fixture_hash"),
    }
    observer_hash = capture_manifest.get("observer_capture_hash")
    if observer_hash:
        expected["observer_capture"] = observer_hash
    for name, digest in expected.items():
        if digests.get(name) != digest:
            errors.append(f"statement subject digest mismatch: {name}")
    return errors


def evaluate_external_statement_subjects(
    statement: dict[str, Any],
    artifact_digests: dict[str, str],
) -> dict[str, Any]:
    """Evaluate externally supplied subjects against present artifact digests."""

    subjects = statement.get("subject")
    mismatches: list[dict[str, str]] = []
    if not isinstance(subjects, list):
        return {
            "decision": "inconclusive",
            "mismatches": [{"name": "subject", "reason": "missing subject list"}],
        }
    for item in subjects:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        digest = item.get("digest", {})
        expected = digest.get("sha256") if isinstance(digest, dict) else None
        actual = artifact_digests.get(str(name))
        if not expected or actual != expected:
            mismatches.append(
                {
                    "name": str(name),
                    "expected": str(expected),
                    "actual": str(actual),
                }
            )
    return {
        "decision": "pass" if not mismatches else "inconclusive",
        "mismatches": mismatches,
    }


def _self_test() -> None:
    from copy import deepcopy
    from pathlib import Path

    fixture_path = Path(
        "depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
    )
    capture = json.loads(fixture_path.read_text(encoding="utf-8"))
    bundle = build_evidence_bundle(capture)
    statement = bundle["statement"]
    if validate_statement_for_capture(statement, capture):
        raise AssertionError("expected statement to validate against capture")
    decoded = decode_dsse_payload(bundle["dsse_envelope"])
    if decoded != statement:
        raise AssertionError("expected DSSE payload to round-trip")
    if bundle["dsse_envelope"]["signatures"] != []:
        raise AssertionError("V128 DSSE envelope must remain unsigned")
    spans = bundle["otel_spans"]
    operations = {
        span.get("attributes", {}).get("gen_ai.operation.name")
        for span in spans
        if isinstance(span.get("attributes"), dict)
    }
    if not {"invoke_agent", "execute_tool"}.issubset(operations):
        raise AssertionError("expected invoke_agent and execute_tool spans")
    if any(
        key.startswith("gen_ai.usage.")
        for span in spans
        for key in span.get("attributes", {})
    ):
        raise AssertionError("unobserved gen_ai.usage.* fields must be omitted")
    tampered = deepcopy(statement)
    tampered["subject"][0]["digest"]["sha256"] = "0" * 64
    if not validate_statement_for_capture(tampered, capture):
        raise AssertionError("expected tampered statement to fail validation")
    external = evaluate_external_statement_subjects(
        tampered,
        {"depone-capture-manifest": canonical_hash(capture)},
    )
    if external["decision"] != "inconclusive":
        raise AssertionError("digest mismatch must be inconclusive, not pass")


if __name__ == "__main__":
    _self_test()
