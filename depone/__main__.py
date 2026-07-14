"""Depone CLI entrypoint for core commands and Agent Fabric smoke."""

from __future__ import annotations

import argparse
import importlib
import sys

from depone.cli._response import EXIT_INTERNAL, EXIT_USAGE, emit_error, emit_json


_LAZY_MODULES = {
    "agent_fabric_adapter_smoke": "depone.cli.agent_fabric_adapter_smoke",
    "agent_fabric_claim_gate": "depone.cli.agent_fabric_claim_gate",
    "agent_fabric_controlled_capture": "depone.cli.agent_fabric_controlled_capture",
    "agent_fabric_dogfood_evidence": "depone.cli.agent_fabric_dogfood_evidence",
    "agent_fabric_evidence_chain": "depone.cli.agent_fabric_evidence_chain",
    "agent_fabric_evidence_ingest": "depone.cli.agent_fabric_evidence_ingest",
    "agent_fabric_evidence_substrate": "depone.cli.agent_fabric_evidence_substrate",
    "agent_fabric_harness_snapshot": "depone.cli.agent_fabric_harness_snapshot",
    "agent_fabric_paired_evidence": "depone.cli.agent_fabric_paired_evidence",
    "agent_fabric_seal": "depone.cli.agent_fabric_seal",
    "agent_fabric_sign": "depone.cli.agent_fabric_sign",
    "agent_fabric_smoke": "depone.cli.agent_fabric_smoke",
    "agent_fabric_team_ledger": "depone.cli.agent_fabric_team_ledger",
    "agent_fabric_verify_seal": "depone.cli.agent_fabric_verify_seal",
    "agent_fabric_verify_signature": "depone.cli.agent_fabric_verify_signature",
    "compile_mod": "depone.compile",
    "demo": "depone.cli.demo",
    "design": "depone.cli.design",
    "doctor": "depone.cli.doctor",
    "evidence_next": "depone.cli.evidence_next",
    "mcp_server": "depone.mcp.server",
    "proofcheck": "depone.cli.proofcheck",
    "team_dry_run": "depone.cli.team_dry_run",
    "team_merge_attempt": "depone.cli.team_merge_attempt",
    "team_pr_artifact": "depone.cli.team_pr_artifact",
    "validate": "depone.cli.validate",
    "validate_contracts": "depone.cli.validate_contracts",
    "verify_mod": "depone.verify",
}


def _load(name: str):
    module = importlib.import_module(_LAZY_MODULES[name])
    globals()[name] = module
    return module


def __getattr__(name: str):
    if name in _LAZY_MODULES:
        return _load(name)
    raise AttributeError(name)


class DeponeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--json" in sys.argv[1:]:
            emit_json(
                {
                    "error": {
                        "code": "ERR_CLI_USAGE",
                        "message": message,
                        "path": None,
                    }
                }
            )
            self.exit(EXIT_USAGE)
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one machine-readable JSON object on stdout",
    )


def _add_evidence_substrate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--capture-manifest",
        default="",
        help="Input Agent Fabric capture manifest JSON",
    )
    parser.add_argument(
        "--runner-receipt",
        default="",
        help="Optional V126 runner receipt JSON for OTel runner attributes",
    )
    parser.add_argument(
        "--out",
        default="evidence-substrate-bundle.json",
        help="Output evidence substrate bundle JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_ingest_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--statement",
        help="Input in-toto Statement JSON or bundle JSON containing statement",
    )
    group.add_argument(
        "--dsse",
        help="Input DSSE envelope JSON or bundle JSON containing dsse_envelope",
    )
    group.add_argument(
        "--signed-bundle",
        help="Input signed evidence bundle JSON; requires --public-key",
    )
    parser.add_argument(
        "--public-key",
        default="",
        help="Ed25519 public key PEM used to verify --signed-bundle",
    )
    parser.add_argument(
        "--otel-spans",
        default=None,
        help="Optional OTel span JSON or bundle JSON containing otel_spans",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help=(
            "Subject artifact locator as name=path[:raw|:json]; repeat for "
            "each artifact. Default digest mode is raw bytes."
        ),
    )
    parser.add_argument(
        "--out",
        default="evidence-ingest-verdict.json",
        help="Output evidence ingest verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_chain_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--capture",
        action="append",
        default=[],
        help="Capture manifest JSON path; repeat in append-only chain order",
    )
    parser.add_argument(
        "--out",
        default="evidence-chain-verdict.json",
        help="Output evidence chain verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_team_pr_artifact_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input",
        default="",
        help="Saved gh pr view JSON or normalized PR JSON input",
    )
    parser.add_argument(
        "--artifact",
        default="",
        help="Existing team-pr-artifact JSON to validate without network",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repository in owner/name form; overrides saved input repo",
    )
    parser.add_argument(
        "--pr-number",
        default="",
        help="PR number for optional --live-gh capture",
    )
    parser.add_argument(
        "--captured-at",
        default="",
        help="ISO timestamp to bind to the produced artifact",
    )
    parser.add_argument(
        "--expected-head-sha",
        default="",
        help="Expected PR head SHA; mismatch blocks",
    )
    parser.add_argument(
        "--expected-base-sha",
        default="",
        help="Expected PR base SHA; mismatch blocks",
    )
    parser.add_argument(
        "--expected-pr-url",
        default="",
        help="Expected PR URL; mismatch blocks",
    )
    parser.add_argument(
        "--live-gh",
        action="store_true",
        help="Optionally capture via gh pr view; saved JSON input is preferred",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the PR artifact JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_team_merge_attempt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Git repository root used for the merge attempt")
    parser.add_argument("--base", default="", help="Base commit or revision to check out before merging")
    parser.add_argument("--head", action="append", default=[], help="Head commit/revision to merge; repeatable")
    parser.add_argument("--artifact", default="", help="Existing team-merge-attempt JSON to validate")
    parser.add_argument("--captured-at", default="", help="ISO timestamp to bind to the produced receipt")
    parser.add_argument("--in-place", action="store_true", help="Use the target repo worktree instead of a disposable worktree")
    parser.add_argument("--allow-dirty-target", action="store_true", help="Allow in-place attempts on a dirty target worktree")
    parser.add_argument("--out", default="", help="Optional output path for the merge-attempt receipt JSON")
    parser.add_argument("--self-test", action="store_true", help="Run self-test and exit")
    _add_json_arg(parser)

def _add_team_ledger_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger",
        default="",
        help="Team Ledger v0 JSON path to validate",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Base directory for relative lane evidence_dir values; defaults to ledger parent",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the Team Ledger verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_team_dry_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--plan",
        default="",
        help="Team dry-run plan JSON path",
    )
    parser.add_argument(
        "--out-dir",
        default="out/team-dry-run",
        help="Repo-relative output directory for dry-run artifacts",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_team_ledger_merge_receipt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--lane",
        action="append",
        default=[],
        help="Lane id covered by the merge receipt; repeat for each lane",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Repo-relative touched file covered by the merge receipt; repeat for each file",
    )
    parser.add_argument(
        "--conflict-event",
        action="append",
        default=[],
        help="Optional JSON object describing a merge conflict/resolution event; repeatable",
    )
    parser.add_argument(
        "--decision",
        choices=["pass", "blocked"],
        default="pass",
        help="Merge receipt decision",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the merge receipt JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_worktree_lane_receipt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--worktree",
        required=False,
        default=".",
        help="Local git worktree path to inspect read-only",
    )
    parser.add_argument(
        "--base-commit",
        required=False,
        default="",
        help="Base commit/revision used to derive changed_files",
    )
    parser.add_argument(
        "--evidence-dir",
        required=False,
        default="",
        help="Repo-relative lane evidence directory recorded in the receipt",
    )
    parser.add_argument(
        "--command-receipt",
        action="append",
        default=[],
        help="JSON object for an already-run lane command; repeatable",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the worktree lane receipt JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_next_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Evidence-run artifact directory to re-validate before selecting next action",
    )
    parser.add_argument(
        "--source-fixture",
        default="",
        help=(
            "Optional source fixture JSON path override for the source_fixture subject"
        ),
    )
    parser.add_argument(
        "--previous-capture",
        default="",
        help=(
            "Optional predecessor capture-manifest.json for validating a prev_capture_hash subject"
        ),
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the evidence-next decision JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_proofcheck_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Directory containing ORRO artifact JSON files to verify offline",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the proofcheck verdict JSON",
    )
    _add_json_arg(parser)


def main() -> None:
    parser = DeponeArgumentParser(
        prog="depone",
        description="Workflow designer + cross-platform evidence verifier.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"depone v{__import__('depone').__version__}",
    )

    sub = parser.add_subparsers(
        dest="command", required=True, parser_class=DeponeArgumentParser
    )

    # design
    design_parser = sub.add_parser(
        "design", help="Decompose an objective into a workflow plan"
    )
    design_parser.add_argument(
        "objective", nargs="?", help="Natural-language objective"
    )
    design_parser.add_argument(
        "--out", default="plan.json", help="Output path for plan.json"
    )
    design_parser.add_argument(
        "--surface", help="Repo path, API spec, or doc URL in scope"
    )
    design_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(design_parser)

    # validate
    validate_parser = sub.add_parser(
        "validate", help="Validate a plan.json against the schema"
    )
    validate_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    validate_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(validate_parser)

    # compile
    compile_parser = sub.add_parser(
        "compile", help="Compile a plan into a target framework workflow"
    )
    compile_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    compile_parser.add_argument(
        "--target",
        default=None,
        choices=["conductor", "langgraph", "agent-fabric"],
        help="Target workflow framework",
    )
    compile_parser.add_argument("--out", default="workflow.yaml", help="Output path")
    compile_parser.add_argument(
        "--harness",
        default="shell",
        help="Agent Fabric target harness (used with --target agent-fabric)",
    )
    compile_parser.add_argument(
        "--roles",
        action="append",
        default=[],
        help=(
            "Role contract JSON path for --target agent-fabric; may be repeated "
            "or point at a role-set JSON"
        ),
    )
    compile_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(compile_parser)

    # verify
    verify_parser = sub.add_parser(
        "verify", help="Verify execution evidence against a plan"
    )
    verify_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    verify_parser.add_argument(
        "--evidence", default=None, help="Path to execution evidence directory"
    )
    verify_parser.add_argument(
        "--adapter", default="generic", help="Evidence adapter (conductor, generic)"
    )
    verify_parser.add_argument(
        "--out", default="verification-report.json", help="Output path for report"
    )
    verify_parser.add_argument(
        "--operator-view-out",
        default=None,
        help="Output path for a V111 operator-readable report view",
    )
    verify_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(verify_parser)

    # proofcheck
    proofcheck_parser = sub.add_parser(
        "proofcheck",
        help="Offline proofcheck for persisted ORRO artifacts",
    )
    _add_proofcheck_args(proofcheck_parser)

    # validate-contracts
    vc_parser = sub.add_parser(
        "validate-contracts",
        help="Validate V107 Agent Fabric contracts (roles, toolbelts, harnesses)",
    )
    vc_parser.add_argument("--file", help="Path to a single contract JSON file")
    vc_parser.add_argument(
        "--all", action="store_true", help="Validate all contracts under contracts/"
    )
    vc_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # mcp
    mcp_parser = sub.add_parser(
        "mcp",
        help="Run the stdlib-only MCP stdio server for Depone evidence tools",
    )
    mcp_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # doctor
    doctor_parser = sub.add_parser(
        "doctor",
        help="Check package-local readiness for agent-session use",
    )
    doctor_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(doctor_parser)

    # agent-fabric-smoke
    smoke_parser = sub.add_parser(
        "agent-fabric-smoke",
        help="Export the source-only Agent Fabric compile-to-report smoke summary",
    )
    smoke_parser.add_argument("--profile", help="Agent Fabric profile JSON path")
    smoke_parser.add_argument(
        "--roles",
        action="append",
        default=[],
        help="Role contract JSON path; may be repeated or point at a role-set JSON",
    )
    smoke_parser.add_argument(
        "--plan", help="Depone plan JSON path for report verification"
    )
    smoke_parser.add_argument("--harness", default="shell", help="Target harness name")
    smoke_parser.add_argument(
        "--out",
        default="agent-fabric-smoke.json",
        help="Output path for smoke summary JSON",
    )
    smoke_parser.add_argument(
        "--operator-view-out",
        default=None,
        help="Optional output path for the embedded operator Markdown view",
    )
    smoke_parser.add_argument(
        "--observer-capture",
        default=None,
        help="Optional Depone observer capture JSON for A1-local-observed smoke",
    )
    smoke_parser.add_argument(
        "--allow-touched-file",
        action="append",
        default=[],
        help="Allowed touched file for observer capture validation; may be repeated",
    )
    smoke_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-harness-snapshot
    harness_snapshot_parser = sub.add_parser(
        "agent-fabric-harness-snapshot",
        help="Export source-only Agent Fabric harness capability snapshots",
    )
    harness_snapshot_parser.add_argument(
        "--harness",
        action="append",
        default=[],
        help=(
            "Harness name to include; may be repeated, "
            "defaults to all known harnesses"
        ),
    )
    harness_snapshot_parser.add_argument(
        "--out",
        default="agent-fabric-harness-snapshot.json",
        help="Output path for harness snapshot JSON",
    )
    harness_snapshot_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-adapter-smoke
    adapter_smoke_parser = sub.add_parser(
        "agent-fabric-adapter-smoke",
        help="Export source-only Agent Fabric adapter smoke reports",
    )
    adapter_smoke_parser.add_argument(
        "--adapter-fixture", help="Reference adapter fixture JSON path"
    )
    adapter_smoke_parser.add_argument(
        "--harness-snapshot",
        default=None,
        help="Optional harness snapshot JSON path; defaults to adapter harness",
    )
    adapter_smoke_parser.add_argument(
        "--out",
        default="agent-fabric-adapter-smoke.json",
        help="Output path for adapter smoke report JSON",
    )
    adapter_smoke_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )




    # agent-fabric-controlled-capture
    controlled_capture_parser = sub.add_parser(
        "agent-fabric-controlled-capture",
        help="Export source-only Agent Fabric controlled capture corpus reports",
    )
    controlled_capture_parser.add_argument(
        "--capture-manifest",
        action="append",
        default=[],
        help="Agent Fabric capture manifest JSON path; repeat for corpus coverage",
    )
    controlled_capture_parser.add_argument(
        "--out",
        default="controlled-capture-corpus.json",
        help="Output path for controlled capture corpus JSON",
    )
    controlled_capture_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-dogfood-evidence
    dogfood_evidence_parser = sub.add_parser(
        "agent-fabric-dogfood-evidence",
        help="Export source-only Agent Fabric dogfood evidence",
    )
    dogfood_evidence_parser.add_argument(
        "--capture-manifest",
        action="append",
        help=(
            "Agent Fabric capture manifest JSON path; repeat to export a "
            "controlled capture corpus summary"
        ),
    )
    dogfood_evidence_parser.add_argument(
        "--out",
        default="dogfood-evidence.json",
        help="Output path for dogfood evidence report JSON",
    )
    dogfood_evidence_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-paired-evidence
    paired_evidence_parser = sub.add_parser(
        "agent-fabric-paired-evidence",
        help="Export source-only paired Agent Fabric dogfood evidence",
    )
    paired_evidence_parser.add_argument(
        "--adapter-smoke", help="Adapter smoke report JSON path"
    )
    paired_evidence_parser.add_argument(
        "--dogfood-evidence", help="Dogfood evidence JSON path"
    )
    paired_evidence_parser.add_argument(
        "--claim-scope",
        default="public-benefit",
        help="Claim scope being paired",
    )
    paired_evidence_parser.add_argument(
        "--out",
        default="agent-fabric-paired-evidence.json",
        help="Output path for paired evidence report JSON",
    )
    paired_evidence_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-seal
    seal_parser = sub.add_parser(
        "agent-fabric-seal",
        help="Write an observer-held HMAC seal for a capture",
    )
    seal_parser.add_argument("--capture", default="", help="Observer capture JSON")
    seal_parser.add_argument("--seal-key-file", default="", help="Raw HMAC key file")
    seal_parser.add_argument(
        "--seal-key-id",
        default="",
        help="Non-secret key label to embed in the seal",
    )
    seal_parser.add_argument("--out", default="", help="Output seal JSON path")
    seal_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-verify-seal
    verify_seal_parser = sub.add_parser(
        "agent-fabric-verify-seal",
        help="Verify an observer-held HMAC seal for a capture",
    )
    verify_seal_parser.add_argument("--capture", default="", help="Observer capture JSON")
    verify_seal_parser.add_argument("--seal", default="", help="Observer seal JSON")
    verify_seal_parser.add_argument(
        "--seal-key-file",
        default="",
        help="Raw HMAC key file",
    )
    verify_seal_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-sign
    sign_parser = sub.add_parser(
        "agent-fabric-sign",
        help="Sign a DSSE evidence bundle with an operator Ed25519 key via openssl",
    )
    sign_parser.add_argument("--bundle", default="", help="Evidence bundle JSON")
    sign_parser.add_argument("--private-key", default="", help="Ed25519 private key PEM")
    sign_parser.add_argument(
        "--key-id",
        default="",
        help="Non-secret key label to embed in the DSSE signature",
    )
    sign_parser.add_argument("--out", default="", help="Output signed bundle JSON")
    sign_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-verify-signature
    verify_signature_parser = sub.add_parser(
        "agent-fabric-verify-signature",
        help="Verify a DSSE evidence bundle signature with an Ed25519 public key",
    )
    verify_signature_parser.add_argument(
        "--bundle",
        default="",
        help="Signed evidence bundle JSON",
    )
    verify_signature_parser.add_argument(
        "--public-key",
        default="",
        help="Ed25519 public key PEM",
    )
    verify_signature_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-evidence-substrate
    evidence_substrate_parser = sub.add_parser(
        "agent-fabric-evidence-substrate",
        help="Export V128 in-toto/DSSE and OTel GenAI evidence bundle",
    )
    _add_evidence_substrate_args(evidence_substrate_parser)

    # evidence-substrate (agent-facing alias)
    evidence_substrate_alias_parser = sub.add_parser(
        "evidence-substrate",
        help="Export V128 in-toto/DSSE and OTel GenAI evidence bundle",
    )
    _add_evidence_substrate_args(evidence_substrate_alias_parser)

    # agent-fabric-evidence-ingest
    evidence_ingest_parser = sub.add_parser(
        "agent-fabric-evidence-ingest",
        help="Ingest external in-toto/DSSE and OTel evidence as untrusted input",
    )
    _add_evidence_ingest_args(evidence_ingest_parser)

    # evidence-ingest (agent-facing alias)
    evidence_ingest_alias_parser = sub.add_parser(
        "evidence-ingest",
        help="Ingest external in-toto/DSSE and OTel evidence as untrusted input",
    )
    _add_evidence_ingest_args(evidence_ingest_alias_parser)

    # agent-fabric-evidence-chain
    evidence_chain_parser = sub.add_parser(
        "agent-fabric-evidence-chain",
        help="Verify an ordered append-only capture manifest chain",
    )
    _add_evidence_chain_args(evidence_chain_parser)

    # evidence-chain (agent-facing alias)
    evidence_chain_alias_parser = sub.add_parser(
        "evidence-chain",
        help="Verify an ordered append-only capture manifest chain",
    )
    _add_evidence_chain_args(evidence_chain_alias_parser)

    # evidence-next
    evidence_next_parser = sub.add_parser(
        "evidence-next",
        help="Re-validate an evidence-run directory and select the next safe action",
    )
    _add_evidence_next_args(evidence_next_parser)

    # next (native operator alias)
    next_parser = sub.add_parser(
        "next",
        help="Compatibility alias for evidence-next",
    )
    _add_evidence_next_args(next_parser)

    team_pr_artifact_parser = sub.add_parser(
        "team-pr-artifact",
        help="Build or validate a Team Ledger GitHub PR artifact",
    )
    _add_team_pr_artifact_args(team_pr_artifact_parser)

    team_merge_attempt_parser = sub.add_parser(
        "team-merge-attempt",
        help="Run a disposable git merge attempt and write a receipt",
    )
    _add_team_merge_attempt_args(team_merge_attempt_parser)

    # team-ledger
    team_ledger_parser = sub.add_parser(
        "team-ledger",
        help="Validate a Team Ledger v0 leader/lane fan-in record",
    )
    _add_team_ledger_args(team_ledger_parser)

    team_ledger_alias_parser = sub.add_parser(
        "agent-fabric-team-ledger",
        help="Validate a Team Ledger v0 leader/lane fan-in record",
    )
    _add_team_ledger_args(team_ledger_alias_parser)

    team_ledger_merge_receipt_parser = sub.add_parser(
        "team-ledger-merge-receipt",
        help="Write a Team Ledger merge receipt JSON artifact",
    )
    _add_team_ledger_merge_receipt_args(team_ledger_merge_receipt_parser)

    worktree_lane_receipt_parser = sub.add_parser(
        "worktree-lane-receipt",
        help="Write a read-only local worktree lane receipt JSON artifact",
    )
    _add_worktree_lane_receipt_args(worktree_lane_receipt_parser)

    team_dry_run_parser = sub.add_parser(
        "team-dry-run",
        help="Plan Team Ledger lanes without launching workers",
    )
    _add_team_dry_run_args(team_dry_run_parser)

    # agent-fabric-claim-gate
    claim_gate_parser = sub.add_parser(
        "agent-fabric-claim-gate",
        help="Gate Agent Fabric public claims on source evidence",
    )
    claim_gate_parser.add_argument(
        "--adapter-smoke", help="Adapter smoke report JSON path"
    )
    claim_gate_parser.add_argument(
        "--paired-evidence",
        default=None,
        help="Optional paired evidence report JSON path",
    )
    claim_gate_parser.add_argument(
        "--claim-scope",
        default="public-benefit",
        help="Claim scope being gated",
    )
    claim_gate_parser.add_argument(
        "--out",
        default="agent-fabric-claim-gate.json",
        help="Output path for claim gate report JSON",
    )
    claim_gate_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # demo
    demo_parser = sub.add_parser(
        "demo", help="Run a complete design -> compile -> verify cycle"
    )
    demo_parser.add_argument(
        "--out", default=None, help="Output directory for demo artifacts"
    )
    demo_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(demo_parser)

    args = parser.parse_args()

    try:
        if args.command == "design":
            _load("design").run(args)
        elif args.command == "validate":
            _load("validate").run(args)
        elif args.command == "compile":
            _load("compile_mod").run(args)
        elif args.command == "verify":
            _load("verify_mod").run(args)
        elif args.command == "proofcheck":
            _load("proofcheck").run(args)
        elif args.command == "validate-contracts":
            _load("validate_contracts").run(args)
        elif args.command == "mcp":
            _load("mcp_server").run(args)
        elif args.command == "doctor":
            _load("doctor").run(args)
        elif args.command == "agent-fabric-smoke":
            _load("agent_fabric_smoke").run(args)
        elif args.command == "agent-fabric-harness-snapshot":
            _load("agent_fabric_harness_snapshot").run(args)
        elif args.command == "agent-fabric-adapter-smoke":
            _load("agent_fabric_adapter_smoke").run(args)
        elif args.command == "agent-fabric-controlled-capture":
            _load("agent_fabric_controlled_capture").run(args)
        elif args.command == "agent-fabric-dogfood-evidence":
            _load("agent_fabric_dogfood_evidence").run(args)
        elif args.command == "agent-fabric-paired-evidence":
            _load("agent_fabric_paired_evidence").run(args)
        elif args.command == "agent-fabric-seal":
            _load("agent_fabric_seal").run(args)
        elif args.command == "agent-fabric-verify-seal":
            _load("agent_fabric_verify_seal").run(args)
        elif args.command == "agent-fabric-sign":
            _load("agent_fabric_sign").run(args)
        elif args.command == "agent-fabric-verify-signature":
            _load("agent_fabric_verify_signature").run(args)
        elif args.command in ("agent-fabric-evidence-substrate", "evidence-substrate"):
            _load("agent_fabric_evidence_substrate").run(args)
        elif args.command in ("agent-fabric-evidence-ingest", "evidence-ingest"):
            _load("agent_fabric_evidence_ingest").run(args)
        elif args.command in ("agent-fabric-evidence-chain", "evidence-chain"):
            _load("agent_fabric_evidence_chain").run(args)
        elif args.command == "team-pr-artifact":
            _load("team_pr_artifact").run(args)
        elif args.command == "team-merge-attempt":
            _load("team_merge_attempt").run(args)
        elif args.command in ("team-ledger", "agent-fabric-team-ledger"):
            _load("agent_fabric_team_ledger").run(args)
        elif args.command == "team-ledger-merge-receipt":
            _load("agent_fabric_team_ledger").run_merge_receipt(args)
        elif args.command == "worktree-lane-receipt":
            _load("agent_fabric_team_ledger").run_worktree_receipt(args)
        elif args.command == "team-dry-run":
            _load("team_dry_run").run(args)
        elif args.command in ("evidence-next", "next"):
            _load("evidence_next").run(args)
        elif args.command == "agent-fabric-claim-gate":
            _load("agent_fabric_claim_gate").run(args)
        elif args.command == "demo":
            _load("demo").run(args)
        else:
            parser.print_help()
            sys.exit(EXIT_USAGE)
    except SystemExit:
        raise
    except Exception as exc:
        emit_error(
            args,
            code="ERR_INTERNAL",
            message=str(exc),
            exit_code=EXIT_INTERNAL,
        )


if __name__ == "__main__":
    main()
