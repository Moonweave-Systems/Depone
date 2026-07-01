"""Separated observer-owned capture path for Agent Fabric runs."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import (
    ASSURANCE_A1,
    build_capture_manifest,
    validate_capture_manifest,
)
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.observer_provenance import (
    DSSE_PROVENANCE_PAYLOAD_TYPE,
    DSSE_PROVENANCE_SCHEME,
    build_signed_trusted_observer_provenance,
    validate_trusted_observer_provenance,
)
from depone.agent_fabric.paired_run import (
    PairedRunError,
    build_observer_capture,
)
from depone.agent_fabric.sign import (
    ERR_OPENSSL_UNAVAILABLE,
    _generate_ed25519_keypair,
    openssl_path,
)

OBSERVER_INDEPENDENCE_MODEL = "separate-process-observer-owned-dir"
OBSERVER_INDEPENDENCE_NOTE = (
    "Process- and directory-separated capture. Not privilege-isolated "
    "(same uid); full A2 requires a uid or container boundary, deferred."
)


def _norm_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _is_inside_or_equal(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [_norm_path(path), _norm_path(root)]
        ) == _norm_path(root)
    except ValueError:
        return False


def _separation_error(message: str) -> PairedRunError:
    return PairedRunError("ERR_OBSERVER_NOT_SEPARATED", message)


def enforce_path_outside_runner_sandbox(
    *,
    runner_sandbox: Path,
    path: Path,
    label: str,
) -> Path:
    """Fail closed unless a named observer-owned path is outside the runner."""

    runner = runner_sandbox.expanduser().resolve(strict=False)
    target = path.expanduser().resolve(strict=False)
    if _is_inside_or_equal(target, runner):
        raise _separation_error(f"{label} must be outside --runner-sandbox")
    return target


def enforce_observer_separation(
    *,
    runner_sandbox: Path,
    out_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    """Fail closed unless observer outputs live outside the runner sandbox."""

    runner = runner_sandbox.expanduser().resolve(strict=False)
    out_abs = out_path.expanduser().resolve(strict=False)
    log_abs = log_path.expanduser().resolve(strict=False)
    observer_dir = out_abs.parent.expanduser().resolve(strict=False)
    log_dir = log_abs.parent.expanduser().resolve(strict=False)

    if _is_inside_or_equal(observer_dir, runner):
        raise _separation_error(
            "--out parent must be outside --runner-sandbox"
        )
    if _is_inside_or_equal(out_abs, runner):
        raise _separation_error("--out must be outside --runner-sandbox")
    if _is_inside_or_equal(log_dir, runner) or _is_inside_or_equal(log_abs, runner):
        raise _separation_error("--log must be outside --runner-sandbox")
    if _norm_path(observer_dir) == _norm_path(runner):
        raise _separation_error("observer dir must not equal runner sandbox")

    return {
        "model": OBSERVER_INDEPENDENCE_MODEL,
        "observer_pid": os.getpid(),
        "runner_sandbox": str(runner),
        "observer_dir": str(observer_dir),
        "out_is_outside_sandbox": True,
        "privilege_boundary": False,
        "tamper_resistant_same_uid": False,
        "note": OBSERVER_INDEPENDENCE_NOTE,
    }


def build_separated_observer_capture(
    *,
    runner_sandbox: Path,
    source_fixture_hash: str,
    verification_command: list[str],
    out_path: Path,
    log_path: Path,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    independence = enforce_observer_separation(
        runner_sandbox=runner_sandbox,
        out_path=out_path,
        log_path=log_path,
    )
    capture = build_observer_capture(
        runner_sandbox,
        source_fixture_hash=source_fixture_hash,
        verification_command=verification_command,
        log_path=log_path.expanduser().resolve(strict=False),
        timeout_seconds=timeout_seconds,
    )
    capture["observer_independence"] = independence
    return capture


def write_observer_capture(out_path: Path, capture: dict[str, Any]) -> str:
    out_abs = out_path.expanduser().resolve(strict=False)
    out_abs.parent.mkdir(parents=True, exist_ok=True)
    out_abs.write_text(
        canonical_json_pretty(capture),
        encoding="utf-8",
    )
    return canonical_hash(capture)


def canonical_json_pretty(value: Any) -> str:
    return f"{json.dumps(value, indent=2, sort_keys=True)}\n"


def _self_test() -> None:
    import subprocess
    import sys

    def run_git(repo: Path, args: list[str]) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr.strip() or result.stdout.strip())

    with tempfile.TemporaryDirectory() as sandbox_dir:
        sandbox = Path(sandbox_dir)
        run_git(sandbox, ["init"])
        run_git(sandbox, ["config", "user.email", "observer@example.invalid"])
        run_git(sandbox, ["config", "user.name", "Observer Test"])
        (sandbox / "sample.txt").write_text("before\n", encoding="utf-8")
        run_git(sandbox, ["add", "sample.txt"])
        run_git(sandbox, ["commit", "-m", "seed"])
        (sandbox / "sample.txt").write_text("after\n", encoding="utf-8")

        inside = sandbox / "observer-capture.json"
        try:
            build_separated_observer_capture(
                runner_sandbox=sandbox,
                source_fixture_hash="fixture-hash",
                verification_command=[sys.executable, "-c", "print('ok')"],
                out_path=inside,
                log_path=sandbox / "verify-log.json",
            )
        except PairedRunError as exc:
            if exc.code != "ERR_OBSERVER_NOT_SEPARATED":
                raise
        else:
            raise AssertionError("observer output inside sandbox must be blocked")
        if inside.exists():
            raise AssertionError("failed separation must not write observer output")

        with tempfile.TemporaryDirectory() as observer_dir:
            fixture = json.loads(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json")
            )
            fixture_hash = canonical_hash(fixture)
            out_path = Path(observer_dir) / "observer-capture.json"
            log_path = Path(observer_dir) / "verify-log.json"
            capture = build_separated_observer_capture(
                runner_sandbox=sandbox,
                source_fixture_hash=fixture_hash,
                verification_command=[
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('sample.txt').exists()",
                ],
                out_path=out_path,
                log_path=log_path,
            )
            capture_hash = write_observer_capture(out_path, capture)
            if capture_hash != canonical_hash(capture):
                raise AssertionError("capture hash mismatch")
            if not out_path.exists() or not log_path.exists():
                raise AssertionError("observer-owned outputs were not written")
            independence = capture.get("observer_independence", {})
            if independence.get("privilege_boundary") is not False:
                raise AssertionError("A2-lite must not claim privilege isolation")
            manifest = build_capture_manifest(
                fixture,
                observer_capture=capture,
                allowed_touched_files=["sample.txt"],
            )
            if manifest.get("assurance") != ASSURANCE_A1:
                raise AssertionError("separated observer path must remain A1")
            errors = validate_capture_manifest(manifest)
            if errors:
                raise AssertionError(f"capture manifest should validate: {errors}")
            if openssl_path() is None:
                provenance = _unsigned_self_test_provenance(manifest)
                provenance_errors = validate_trusted_observer_provenance(
                    manifest,
                    evidence_path="agent-fabric-capture-manifest.json",
                    provenance=[provenance],
                    public_key_path=str(Path(observer_dir) / "operator.pub"),
                )
                if ERR_OPENSSL_UNAVAILABLE not in provenance_errors:
                    raise AssertionError(
                        "missing openssl must fail closed for DSSE provenance"
                    )
            else:
                private_key, public_key = _generate_ed25519_keypair(Path(observer_dir))
                provenance = build_signed_trusted_observer_provenance(
                    manifest,
                    evidence_path="agent-fabric-capture-manifest.json",
                    private_key_path=str(private_key),
                    key_id="agent-fabric-observe-self-test-operator-key",
                )
                provenance_errors = validate_trusted_observer_provenance(
                    manifest,
                    evidence_path="agent-fabric-capture-manifest.json",
                    provenance=[provenance],
                    public_key_path=str(public_key),
                )
                if provenance_errors:
                    raise AssertionError(
                        f"trusted observer provenance should validate: {provenance_errors}"
                    )
    print("depone agent-fabric-observe --self-test: pass")


def _unsigned_self_test_provenance(manifest: dict[str, Any]) -> dict[str, Any]:
    binding = {
        "kind": "trusted-observer-provenance-binding",
        "schema_version": "1.0",
        "evidence_path": "agent-fabric-capture-manifest.json",
        "manifest_hash": canonical_hash(manifest),
        "observer_capture_hash": manifest.get("observer_capture_hash"),
    }
    payload = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "kind": "trusted-observer-provenance",
        "schema_version": "1.0",
        "evidence_path": "agent-fabric-capture-manifest.json",
        "manifest_hash": binding["manifest_hash"],
        "observer_capture_hash": binding["observer_capture_hash"],
        "scheme": DSSE_PROVENANCE_SCHEME,
        "key_id": "agent-fabric-observe-self-test-operator-key",
        "dsse_envelope": {
            "payloadType": DSSE_PROVENANCE_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [],
        },
    }
