#!/usr/bin/env python3
"""Model-agnostic verdict-integrity pass for the research-orchestration pattern.

This is Keelplane Core: zero model dependency. It turns the raw verdicts a verifier
returned (on ANY substrate -- Claude Workflow or a Codex driver) into a trustworthy
ledger, enforcing the against-source discipline in code rather than in prompt text:

  1. drop verdicts whose claim_id was never in the draft (hallucinated);
  2. downgrade a confirmed / partially-supported verdict that lacks an evidence
     locator+excerpt to "unverified" (so "confirmed" always means cited);
  3. normalize any unknown / missing verdict string to "unverified" (it can never
     vanish from both the buckets AND the uncovered list);
  4. dedupe to one verdict per claim, keeping the most CONSERVATIVE on conflict;
  5. compute "uncovered" = claims that received no surviving verdict.

Invariant: every claim ends up in exactly one of {confirmed, partial, refuted,
unverified} OR in uncovered -- never silently dropped, never silently confirmed.

The contract lives in fixtures/verdict-integrity/cases.json, shared with the JS
reference (scripts/verdict_integrity_check.cjs) so the implementations cannot drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "fixtures" / "verdict-integrity" / "cases.json"

VERDICT_VALUES = ("confirmed", "partially-supported", "refuted", "unverified")
# Conservative ordering: on a per-claim conflict the higher rank wins, so the ledger
# never over-claims (refuted beats unverified beats partial beats confirmed).
CONSERVATIVE_RANK = {
    "refuted": 3,
    "unverified": 2,
    "partially-supported": 1,
    "confirmed": 0,
}


def has_evidence(verdict: dict[str, Any]) -> bool:
    evidence = verdict.get("evidence")
    return bool(
        evidence and evidence.get("locator") and evidence.get("excerpt_or_value")
    )


def apply_integrity(
    claims: list[dict[str, Any]], raw_verdicts: list[dict[str, Any]]
) -> dict[str, Any]:
    claim_ids = {c.get("id") for c in claims if isinstance(c, dict) and c.get("id")}
    by_claim: dict[str, dict[str, Any]] = {}
    dropped = 0
    downgraded = 0

    for raw in raw_verdicts:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        claim_id = raw.get("claim_id")
        if claim_id not in claim_ids:
            dropped += 1
            continue

        verdict = dict(raw)  # do not mutate the caller's data
        label = verdict.get("verdict")
        if label in ("confirmed", "partially-supported") and not has_evidence(verdict):
            verdict["reason"] = (
                f"downgraded (no evidence locator/excerpt): {verdict.get('reason', '')}"
            )
            label = "unverified"
            verdict["verdict"] = label
            downgraded += 1
        if label not in CONSERVATIVE_RANK:
            verdict["reason"] = (
                f"normalized (unknown verdict {label!r}): {verdict.get('reason', '')}"
            )
            label = "unverified"
            verdict["verdict"] = label

        prev = by_claim.get(claim_id)
        if (
            prev is None
            or CONSERVATIVE_RANK[label] > CONSERVATIVE_RANK[prev["verdict"]]
        ):
            by_claim[claim_id] = verdict

    verdicts = list(by_claim.values())
    uncovered = [
        c for c in claims if isinstance(c, dict) and c.get("id") not in by_claim
    ]
    return {
        "verdicts": verdicts,
        "confirmed": [v for v in verdicts if v["verdict"] == "confirmed"],
        "partial": [v for v in verdicts if v["verdict"] == "partially-supported"],
        "refuted": [v for v in verdicts if v["verdict"] == "refuted"],
        "unverified": [v for v in verdicts if v["verdict"] == "unverified"],
        "uncovered": uncovered,
        "dropped": dropped,
        "downgraded": downgraded,
    }


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "confirmed": len(result["confirmed"]),
        "partial": len(result["partial"]),
        "refuted": len(result["refuted"]),
        "unverified": len(result["unverified"]),
        "uncovered": sorted(c.get("id") for c in result["uncovered"]),
        "dropped": result["dropped"],
        "downgraded": result["downgraded"],
    }


def self_test() -> None:
    cases = json.loads(CASES_PATH.read_text())["cases"]
    failures: list[str] = []
    for case in cases:
        got = summarize(apply_integrity(case["claims"], case["raw_verdicts"]))
        want = case["expect"]
        for key in (
            "confirmed",
            "partial",
            "refuted",
            "unverified",
            "dropped",
            "downgraded",
        ):
            if got[key] != want[key]:
                failures.append(
                    f"{case['name']}: {key} expected {want[key]}, got {got[key]}"
                )
        if got["uncovered"] != sorted(want["uncovered"]):
            failures.append(
                f"{case['name']}: uncovered expected {sorted(want['uncovered'])}, got {got['uncovered']}"
            )
        # invariant: every claim is bucketed exactly once or uncovered
        bucketed = (
            got["confirmed"] + got["partial"] + got["refuted"] + got["unverified"]
        )
        if bucketed + len(got["uncovered"]) != len(case["claims"]):
            failures.append(
                f"{case['name']}: invariant broken (bucketed {bucketed} + uncovered {len(got['uncovered'])} != claims {len(case['claims'])})"
            )

    if failures:
        for line in failures:
            print(f"FAIL: {line}", file=sys.stderr)
        raise SystemExit(f"verdict-integrity self-test: {len(failures)} failure(s)")
    print(f"verdict-integrity self-test: pass ({len(cases)} cases)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the verdict-integrity pass.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--claims", help="path to a JSON array of draft claims")
    parser.add_argument(
        "--verdicts", help="path to a JSON array of raw verifier verdicts"
    )
    parser.add_argument(
        "--out", help="write the full result JSON here (default: print summary)"
    )
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.claims or not args.verdicts:
        parser.error("provide --self-test, or both --claims and --verdicts")

    claims = json.loads(Path(args.claims).read_text())
    raw_verdicts = json.loads(Path(args.verdicts).read_text())
    result = apply_integrity(claims, raw_verdicts)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(summarize(result), indent=2))


if __name__ == "__main__":
    main()
