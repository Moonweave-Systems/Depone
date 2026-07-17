from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from depone.verify.engine import VerificationReport


def _report_mapping(report: VerificationReport | Mapping[str, Any]) -> Mapping[str, Any]:
    if is_dataclass(report):
        return asdict(report)
    return report


def _capture_mapping(capture: Any) -> Mapping[str, Any]:
    if is_dataclass(capture):
        return asdict(capture)
    if isinstance(capture, Mapping):
        return capture
    return {}


def _finding_mapping(finding: Any) -> Mapping[str, Any]:
    if is_dataclass(finding):
        return asdict(finding)
    if isinstance(finding, Mapping):
        return finding
    return {}


def render_operator_view(report: VerificationReport | Mapping[str, Any]) -> str:
    """Render the operator-facing V111 summary for a verification report."""
    report_data = _report_mapping(report)
    captures = [
        _capture_mapping(capture)
        for capture in report_data.get("agent_fabric_captures", [])
    ]
    advisory_findings = [
        _finding_mapping(finding)
        for finding in report_data.get("advisory_findings", [])
    ]

    lines = [
        "# Verification Operator View",
        "",
        f"- Decision: {report_data.get('decision', 'unknown')}",
        f"- Assurance: {report_data.get('assurance', 'unknown')}",
        "- Evidence contract schema: "
        f"{report_data.get('evidence_contract_schema_version') or 'none'}",
        f"- Agent Fabric captures: {len(captures)}",
        "",
        "## Agent Fabric captures",
    ]

    if not captures:
        lines.append("- None")
    else:
        for index, capture in enumerate(captures, start=1):
            errors = capture.get("errors", [])
            valid = "yes" if capture.get("valid") is True else "no"
            lines.extend(
                [
                    f"{index}. `{capture.get('evidence_path', 'unknown')}`",
                    f"   - Decision: {capture.get('decision', 'unknown')}",
                    f"   - Assurance: {capture.get('assurance', 'unknown')}",
                    f"   - Valid: {valid}",
                ]
            )
            if errors:
                lines.append("   - Errors:")
                for error in errors:
                    lines.append(f"     - {error}")
            else:
                lines.append("   - Errors: none")

    lines.extend(["", "## Advisory findings — does not affect the verdict"])
    if not advisory_findings:
        lines.append("- None")
    else:
        for index, finding in enumerate(advisory_findings, start=1):
            lines.extend(
                [
                    f"{index}. `{finding.get('code', 'unknown')}`",
                    f"   - Evidence: `{finding.get('evidence_path', 'unknown')}`",
                    f"   - Detail: {finding.get('message', 'unknown')}",
                ]
            )

    return "\n".join(lines) + "\n"


def write_operator_view(
    report: VerificationReport | Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_operator_view(report), encoding="utf-8")
    return path
