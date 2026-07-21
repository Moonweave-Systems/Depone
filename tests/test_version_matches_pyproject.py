from __future__ import annotations

import unittest
from pathlib import Path

import depone

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    for line in (
        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    ):
        stripped = line.strip()
        if stripped.startswith("version"):
            return stripped.split("=", 1)[1].strip().strip('"')
    raise AssertionError("pyproject.toml has no version")


class VersionMatchesPyprojectTests(unittest.TestCase):
    def test_version_is_not_the_stale_hardcoded_value(self) -> None:
        # Regression for the drift where __version__ was hardcoded to 0.1.0
        # while the package was 0.2.x.
        self.assertNotEqual(depone.__version__, "0.1.0")

    def test_version_matches_pyproject_in_source_tree(self) -> None:
        self.assertEqual(depone.__version__, _pyproject_version())


if __name__ == "__main__":
    unittest.main()
