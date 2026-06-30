#!/usr/bin/env python3
"""Run a clean source-install smoke test for Depone."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 180
INSTALL_TIMEOUT_SECONDS = 420


def decide(checks: list[dict[str, Any]]) -> str:
    return "pass" if checks and all(bool(check.get("ok")) for check in checks) else "blocked"


def command_display(command: list[str]) -> list[str]:
    return [str(part) for part in command]


def tail_text(text: str, *, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command_display(command),
            "returncode": None,
            "ok": False,
            "timed_out": True,
            "stdout": tail_text(exc.stdout or ""),
            "stderr": tail_text(exc.stderr or ""),
        }

    return {
        "command": command_display(command),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "timed_out": False,
        "stdout": tail_text(completed.stdout),
        "stderr": tail_text(completed.stderr),
    }


def parse_json_stdout(check: dict[str, Any]) -> dict[str, Any] | None:
    stdout = str(check.get("stdout", ""))
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        check["ok"] = False
        check["parse_error"] = "stdout was not valid JSON"
        return None
    check["json"] = payload
    return payload if isinstance(payload, dict) else None


def team_ledger_payload_passes(payload: dict[str, Any]) -> bool:
    error_count = payload.get("error_count")
    if error_count is None and isinstance(payload.get("summary"), dict):
        error_count = payload["summary"].get("error_count")
    return payload.get("decision") == "pass" and error_count == 0


def doctor_payload_passes(payload: dict[str, Any]) -> bool:
    if "decision" in payload:
        return payload.get("decision") == "pass"
    return payload.get("ok") is True


def venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_console_path(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def build_payload(
    *,
    source: Path,
    python_executable: str,
    venv_python: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "command": "install-smoke",
        "schema_version": "1.0",
        "decision": decide(checks),
        "source": str(source),
        "python_executable": python_executable,
        "venv_python": venv_python,
        "checks": checks,
        "install_boundary": {
            "creates_virtualenv": True,
            "installs_source_package": True,
            "installs_runtime_dependencies": False,
            "publishes_package": False,
            "claims_pypi_ready": False,
        },
    }


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_install_smoke(source: Path, python_executable: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="depone-install-smoke-") as temp_dir:
        temp_root = Path(temp_dir)
        venv_dir = temp_root / "venv"
        create_venv = run_command(
            [python_executable, "-m", "venv", str(venv_dir)],
            cwd=source,
        )
        create_venv["name"] = "create-virtualenv"
        checks.append(create_venv)

        venv_python = venv_python_path(venv_dir)
        depone_console = venv_console_path(venv_dir, "depone")
        if create_venv["ok"]:
            install = run_command(
                [str(venv_python), "-m", "pip", "install", "--no-deps", str(source)],
                cwd=source,
                timeout_seconds=INSTALL_TIMEOUT_SECONDS,
            )
        else:
            install = {
                "command": [str(venv_python), "-m", "pip", "install", "--no-deps", str(source)],
                "returncode": None,
                "ok": False,
                "timed_out": False,
                "stdout": "",
                "stderr": "virtualenv creation failed",
            }
        install["name"] = "source-install"
        checks.append(install)

        if install["ok"]:
            doctor = run_command([str(depone_console), "doctor", "--json"], cwd=source)
        else:
            doctor = {
                "command": [str(depone_console), "doctor", "--json"],
                "returncode": None,
                "ok": False,
                "timed_out": False,
                "stdout": "",
                "stderr": "source install failed",
            }
        doctor["name"] = "depone-console-doctor"
        doctor_payload = parse_json_stdout(doctor) if doctor["ok"] else None
        if doctor_payload is not None:
            doctor["ok"] = doctor_payload_passes(doctor_payload)
        checks.append(doctor)

        if install["ok"]:
            self_test = run_command(
                [str(venv_python), "-m", "depone", "team-ledger", "--self-test"],
                cwd=source,
            )
        else:
            self_test = {
                "command": [str(venv_python), "-m", "depone", "team-ledger", "--self-test"],
                "returncode": None,
                "ok": False,
                "timed_out": False,
                "stdout": "",
                "stderr": "source install failed",
            }
        self_test["name"] = "module-team-ledger-self-test"
        checks.append(self_test)

        ledger_path = source / "docs" / "cloud-lane-artifact" / "team-ledger.json"
        if install["ok"]:
            cloud_fixture = run_command(
                [
                    str(venv_python),
                    "-m",
                    "depone",
                    "team-ledger",
                    "--ledger",
                    str(ledger_path),
                    "--json",
                ],
                cwd=source,
            )
        else:
            cloud_fixture = {
                "command": [
                    str(venv_python),
                    "-m",
                    "depone",
                    "team-ledger",
                    "--ledger",
                    str(ledger_path),
                    "--json",
                ],
                "returncode": None,
                "ok": False,
                "timed_out": False,
                "stdout": "",
                "stderr": "source install failed",
            }
        cloud_fixture["name"] = "cloud-lane-artifact"
        cloud_payload = parse_json_stdout(cloud_fixture) if cloud_fixture["ok"] else None
        if cloud_payload is not None:
            cloud_fixture["ok"] = team_ledger_payload_passes(cloud_payload)
        checks.append(cloud_fixture)

        return build_payload(
            source=source,
            python_executable=python_executable,
            venv_python=str(venv_python),
            checks=checks,
        )


def self_test() -> None:
    if decide([{"ok": True}, {"ok": True}]) != "pass":
        raise SystemExit("self-test failed: passing checks did not pass")
    if decide([{"ok": True}, {"ok": False}]) != "blocked":
        raise SystemExit("self-test failed: failing check did not block")
    payload = build_payload(
        source=ROOT,
        python_executable=sys.executable,
        venv_python="/tmp/example/bin/python",
        checks=[{"name": "source-install", "ok": True}],
    )
    if payload["decision"] != "pass":
        raise SystemExit("self-test failed: payload did not pass")
    if payload["install_boundary"]["claims_pypi_ready"] is not False:
        raise SystemExit("self-test failed: payload overclaims PyPI readiness")
    with tempfile.TemporaryDirectory() as temp_dir:
        artifact = Path(temp_dir) / "nested" / "install-smoke.json"
        write_json_artifact(artifact, payload)
        if not artifact.exists():
            raise SystemExit("self-test failed: artifact was not written")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT,
        help="source tree to install (default: repository root)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to create the virtualenv",
    )
    parser.add_argument("--json", action="store_true", help="print the JSON result")
    parser.add_argument("--out", type=Path, help="write the JSON result to this path")
    parser.add_argument("--self-test", action="store_true", help="run script self-test")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        self_test()
        print("install-smoke self-test: pass")
        return 0

    source = args.source.resolve()
    if not (source / "pyproject.toml").exists():
        raise SystemExit(f"source does not look like a Python project: {source}")

    payload = run_install_smoke(source, args.python)
    if args.out:
        write_json_artifact(args.out, payload)
    if args.json or not args.out:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
