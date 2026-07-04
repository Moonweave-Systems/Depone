from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_INCONCLUSIVE = 2
EXIT_USAGE = 3
EXIT_INTERNAL = 4


def wants_json(args: Any) -> bool:
    return bool(getattr(args, "json", False))


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))


def emit_result(args: Any, payload: dict[str, Any], *, human: list[str] | None = None) -> None:
    if wants_json(args):
        emit_json(payload)
        return
    for line in human or []:
        print(line)


def emit_error(
    args: Any,
    *,
    code: str,
    message: str,
    path: str | Path | None = None,
    legacy_code: str | None = None,
    exit_code: int = EXIT_USAGE,
) -> NoReturn:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "path": str(path) if path else None,
            **({"legacy_code": legacy_code} if legacy_code else {}),
        }
    }
    if wants_json(args):
        emit_json(payload)
    else:
        print(f"Error [{code}]: {message}", file=sys.stderr)
    sys.exit(exit_code)


def exit_code_for_decision(decision: str) -> int:
    normalized = decision.lower()
    if normalized in {"pass", "success", "verified", "ok"}:
        return EXIT_SUCCESS
    if normalized in {"inconclusive", "insufficient-evidence", "skipped"}:
        return EXIT_INCONCLUSIVE
    return EXIT_FAILED
