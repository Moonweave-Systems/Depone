from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from depone.verify.adapters.base import EvidenceContext, EvidenceFile


def read_evidence(evidence_dir: str) -> EvidenceContext:
    """Read all files in a directory as generic execution evidence.

    Every file under evidence_dir is discovered, hashed, and returned.
    Subdirectories are walked recursively. Binary files are stored as
    hex strings; text files are stored as-is.
    """
    root = Path(evidence_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"evidence_dir is not a directory: {evidence_dir}")

    files: list[EvidenceFile] = []
    run_id: str | None = None
    raw: dict = {}

    for entry in sorted(root.rglob("*")):
        if entry.is_dir():
            continue
        rel = entry.relative_to(root).as_posix()
        content_bytes = entry.read_bytes()
        sha = hashlib.sha256(content_bytes).hexdigest()

        # Try to decode as text; fall back to base64
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = content_bytes.hex()

        files.append(EvidenceFile(path=rel, content=content, sha256=sha))

        # Check for run metadata in known files
        if rel == "run-metadata.json":
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    raw["metadata"] = parsed
                    run_id = parsed.get("run_id")
            except json.JSONDecodeError:
                pass

    provenance = _read_trusted_observer_provenance(root)
    if provenance is not None:
        raw["trusted_observer_provenance"] = provenance
    seal_key = _read_trusted_observer_seal_key(root)
    if seal_key is not None:
        raw["trusted_observer_seal_key"] = seal_key
    public_key_file = _read_trusted_observer_public_key_file(root)
    if public_key_file is not None:
        raw["trusted_observer_public_key_file"] = public_key_file

    return EvidenceContext(run_id=run_id, files=files, raw=raw)


def _read_trusted_observer_provenance(evidence_root: Path) -> list[Any] | None:
    """Load operator-provided provenance from outside the evidence directory."""

    configured = os.environ.get("DEPONE_TRUSTED_OBSERVER_PROVENANCE_FILE")
    if not configured:
        return None
    path = Path(configured).expanduser().resolve(strict=False)
    root = evidence_root.expanduser().resolve(strict=False)
    try:
        if os.path.commonpath([str(path), str(root)]) == str(root):
            return None
    except ValueError:
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        nested = parsed.get("trusted_observer_provenance")
        if isinstance(nested, list):
            return nested
        return [parsed]
    return None


def _read_trusted_observer_seal_key(evidence_root: Path) -> bytes | None:
    key_text = os.environ.get("DEPONE_TRUSTED_OBSERVER_SEAL_KEY")
    if key_text is not None:
        return key_text.encode("utf-8")
    configured = os.environ.get("DEPONE_TRUSTED_OBSERVER_SEAL_KEY_FILE")
    if not configured:
        return None
    path = Path(configured).expanduser().resolve(strict=False)
    root = evidence_root.expanduser().resolve(strict=False)
    try:
        if os.path.commonpath([str(path), str(root)]) == str(root):
            return None
    except ValueError:
        return None
    try:
        key = path.read_bytes()
    except OSError:
        return None
    return key or None


def _read_trusted_observer_public_key_file(evidence_root: Path) -> str | None:
    """Return an operator public key path only when it is outside evidence."""

    configured = os.environ.get("DEPONE_TRUSTED_OBSERVER_PUBLIC_KEY_FILE")
    if not configured:
        return None
    path = Path(configured).expanduser().resolve(strict=False)
    root = evidence_root.expanduser().resolve(strict=False)
    try:
        if os.path.commonpath([str(path), str(root)]) == str(root):
            return None
    except ValueError:
        return None
    if not path.is_file():
        return None
    return str(path)
