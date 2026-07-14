from __future__ import annotations

import ast
import unittest
from pathlib import Path

from depone.agent_fabric._witnessd_shim import (
    WitnessdUnavailableError,
    load_witnessd_module,
)

ALLOWED_WITNESSD_IMPORTING_MODULES = {
    Path("depone/agent_fabric/_witnessd_shim.py"),
}


class WitnessdShimTests(unittest.TestCase):
    def test_load_witnessd_module_raises_structured_error_when_absent(self) -> None:
        with self.assertRaises(WitnessdUnavailableError) as raised:
            load_witnessd_module("witnessd.definitely_not_a_real_module_xyz")

        self.assertEqual(
            raised.exception.code, "ERR_DEPONE_EXECUTION_SURFACE_MOVED_TO_WITNESSD"
        )

    def test_no_other_depone_module_imports_witnessd(self) -> None:
        # Only the migration error shim may know how to locate witnessd. The
        # verifier modules must not wire themselves to the runtime.
        repo = Path(__file__).resolve().parents[1]
        violations: list[str] = []
        for path in sorted((repo / "depone").rglob("*.py")):
            relative = path.relative_to(repo)
            if relative in ALLOWED_WITNESSD_IMPORTING_MODULES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name == "witnessd" or alias.name.startswith("witnessd.")
                    for alias in node.names
                ):
                    violations.append(str(relative))
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and (
                        node.module == "witnessd" or node.module.startswith("witnessd.")
                    )
                ):
                    violations.append(str(relative))

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
