#!/usr/bin/env python3
"""README product-page quality gate."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MAX_LINES = 190
MAX_VERSION_MENTIONS = 8
REQUIRED_SECTIONS = [
    "## Quickstart",
    "## Product boundary",
    "## Repository and install boundary",
    "## What exists today",
    "## Command taxonomy",
    "## Normal ORRO loop",
    "## Quality",
    "## Documentation",
    "## License",
]
REQUIRED_TERMS = [
    "assets/dwm-hero.svg",
    "docs/command-reference.md",
    "docs/spec.md",
    "Depone verifies; witnessd executes; ORRO exposes the workflow.",
    "separate Depone and witnessd skills",
    "not the final flagship user UX",
    "Commands that launch workers, own sessions, retry, call external MCP/tools",
    "Depone reads the artifact bytes offline.",
]


class ReadmeQualityError(ValueError):
    """Raised when README quality checks fail."""


def version_mentions(text: str) -> int:
    return len(re.findall(r"\bV\d{1,3}\b", text))


def check_text(text: str, *, max_lines: int = MAX_LINES, root: Path = ROOT) -> None:
    problems: list[str] = []
    lines = text.splitlines()
    if len(lines) > max_lines:
        problems.append(f"README is too long: {len(lines)} lines > {max_lines}")
    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing section: {section}")
    for term in REQUIRED_TERMS:
        if term not in text:
            problems.append(f"missing required term: {term}")
    mentions = version_mentions(text)
    if mentions > MAX_VERSION_MENTIONS:
        problems.append(f"too many version mentions: {mentions} > {MAX_VERSION_MENTIONS}")
    if "V36 README graph artifacts" in text or "V67 adds" in text:
        problems.append("README appears to contain release-history prose")
    command_reference = root / "docs" / "command-reference.md"
    spec = root / "docs" / "spec.md"
    if not command_reference.is_file():
        problems.append("docs/command-reference.md is missing")
    if not spec.is_file():
        problems.append("docs/spec.md is missing")
    if problems:
        raise ReadmeQualityError("; ".join(problems))


def check_readme(path: Path = README) -> None:
    if not path.is_file() or path.is_symlink():
        raise ReadmeQualityError(f"README is missing or unsafe: {path}")
    check_text(path.read_text(encoding="utf-8"), root=path.resolve(strict=False).parent)


def self_test() -> None:
    good = "\n".join(
        [
            "# Depone",
            "Depone verifies; witnessd executes; ORRO exposes the workflow.",
            "## Quickstart",
            "## Product boundary",
            "## Repository and install boundary",
            "separate Depone and witnessd skills",
            "not the final flagship user UX",
            "## What exists today",
            "## Command taxonomy",
            "Commands that launch workers, own sessions, retry, call external MCP/tools",
            "## Normal ORRO loop",
            "Depone reads the artifact bytes offline.",
            "## Quality",
            "assets/dwm-hero.svg",
            "docs/command-reference.md",
            "docs/spec.md",
            "## Documentation",
            "## License",
            "",
        ]
    )
    check_text(good, max_lines=40)
    try:
        check_text(good + "\n".join([f"V{index} release note" for index in range(20)]), max_lines=80)
    except ReadmeQualityError:
        pass
    else:
        raise ReadmeQualityError("self-test failed: release-note README passed")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "README.md"
        path.write_text(good, encoding="utf-8")
        try:
            check_readme(path)
        except ReadmeQualityError:
            pass
        else:
            raise ReadmeQualityError("self-test failed: missing reference docs passed")
        (root / "docs").mkdir()
        (root / "docs" / "command-reference.md").write_text("# commands\n", encoding="utf-8")
        (root / "docs" / "spec.md").write_text("# spec\n", encoding="utf-8")
        check_readme(path)
    print("readme quality self-test: pass")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("path", nargs="?", default=str(README))
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        else:
            check_readme(Path(args.path))
            print("readme quality check: pass")
    except ReadmeQualityError as exc:
        print(f"check_readme_quality: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
