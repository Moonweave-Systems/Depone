#!/usr/bin/env python3
"""Repo-local release text checks for secrets and placeholders."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".pytest_cache", ".ruff_cache", "__pycache__", "out"}
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}|"
    r"-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----"
)
PLACEHOLDER_PATTERN = re.compile(r"T[O]DO|T[B]D|PLACE[H]OLDER|FIX[M]E")


class TextCheckError(ValueError):
    """Raised when release text checks fail."""


def iter_text_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def check_files(root: Path) -> None:
    secret_hits: list[str] = []
    placeholder_hits: list[str] = []
    for path in iter_text_files(root):
        text = path.read_text(errors="replace")
        rel_path = path.relative_to(root)
        if SECRET_PATTERN.search(text):
            secret_hits.append(str(rel_path))
        if path.suffix.lower() == ".md" and PLACEHOLDER_PATTERN.search(text):
            placeholder_hits.append(str(rel_path))
    if secret_hits:
        raise TextCheckError(f"secret-like values found: {secret_hits}")
    if placeholder_hits:
        raise TextCheckError(f"placeholder markers found: {placeholder_hits}")


def self_test() -> None:
    sample_secret = "api_" + 'key = "12345678"'
    if not SECRET_PATTERN.search(sample_secret):
        raise TextCheckError("self-test failed: secret pattern missed")
    if not PLACEHOLDER_PATTERN.search("T" + "ODO"):
        raise TextCheckError("self-test failed: placeholder pattern missed")
    if SECRET_PATTERN.search("secret access requires approval"):
        raise TextCheckError("self-test failed: benign secret phrase matched")
    print("release text check self-test: pass")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        else:
            check_files((ROOT / args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root))
            print("release text check: pass")
    except TextCheckError as exc:
        print(f"check_release_text: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
