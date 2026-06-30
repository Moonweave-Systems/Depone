from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_install_smoke():
    spec = importlib.util.spec_from_file_location(
        "install_smoke",
        ROOT / "scripts" / "install_smoke.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load install_smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallSmokeTests(unittest.TestCase):
    def test_decision_passes_only_when_every_check_passes(self) -> None:
        install_smoke = load_install_smoke()

        self.assertEqual(
            install_smoke.decide(
                [
                    {"name": "source-install", "ok": True},
                    {"name": "depone-doctor", "ok": True},
                ]
            ),
            "pass",
        )
        self.assertEqual(
            install_smoke.decide(
                [
                    {"name": "source-install", "ok": True},
                    {"name": "depone-doctor", "ok": False},
                ]
            ),
            "blocked",
        )

    def test_payload_records_honest_install_boundary(self) -> None:
        install_smoke = load_install_smoke()

        payload = install_smoke.build_payload(
            source=ROOT,
            python_executable="/usr/bin/python3",
            venv_python="/tmp/example/bin/python",
            checks=[{"name": "source-install", "ok": True}],
        )

        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(
            payload["install_boundary"],
            {
                "creates_virtualenv": True,
                "installs_source_package": True,
                "installs_runtime_dependencies": False,
                "publishes_package": False,
                "claims_pypi_ready": False,
            },
        )

    def test_write_json_artifact_creates_parent_directory(self) -> None:
        install_smoke = load_install_smoke()
        payload = {"decision": "pass", "checks": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "nested" / "install-smoke.json"
            install_smoke.write_json_artifact(out_path, payload)

            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8")), payload)

    def test_team_ledger_payload_pass_detects_top_level_error_count(self) -> None:
        install_smoke = load_install_smoke()

        self.assertTrue(
            install_smoke.team_ledger_payload_passes(
                {"decision": "pass", "error_count": 0}
            )
        )
        self.assertFalse(
            install_smoke.team_ledger_payload_passes(
                {"decision": "pass", "error_count": 1}
            )
        )

    def test_doctor_payload_prefers_explicit_decision(self) -> None:
        install_smoke = load_install_smoke()

        self.assertTrue(install_smoke.doctor_payload_passes({"decision": "pass"}))
        self.assertFalse(
            install_smoke.doctor_payload_passes({"decision": "blocked", "ok": True})
        )
        self.assertTrue(install_smoke.doctor_payload_passes({"ok": True}))


if __name__ == "__main__":
    unittest.main()
