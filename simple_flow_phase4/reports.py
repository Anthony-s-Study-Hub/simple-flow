from __future__ import annotations

import json
from pathlib import Path

from simple_flow_phase4.models import RunReport, ScenarioResult


def write_reports(report: RunReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{report.run_id}.json"
    md_path = report_dir / f"{report.run_id}.md"
    json_path.write_text(json.dumps(report.to_json_data(), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: RunReport) -> str:
    lines = [
        "# Phase 4 Experiment Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Generated At: `{report.generated_at}`",
        f"- Overall Status: `{report.overall_status.value}`",
        f"- Harness Commit SHA: `{report.harness_commit_sha}`",
        f"- Workflow Package Version: `{report.workflow_package_version}`",
        f"- Test Repo: `{report.test_repo_url}`",
        f"- Codex CLI Version: `{_single_line(report.codex_cli_version)}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in report.status_counts().items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Scenario Summary", ""])
    for result in report.scenarios:
        lines.append(f"- {result.scenario_id}: {result.status.value} - {result.failure_reason or 'objective rules satisfied'}")

    lines.extend(["", "## Scenario Details", ""])
    for result in report.scenarios:
        lines.extend(_scenario_markdown(result))
    return "\n".join(lines) + "\n"


def _scenario_markdown(result: ScenarioResult) -> list[str]:
    lines = [
        f"### {result.scenario_id} - {result.status.value}",
        "",
        f"- Prompt/Input Reference: `{result.prompt_reference}`",
        f"- Expected Result: {', '.join(result.expected_result.get('expected_objective_state', []))}",
        f"- Failure Reason: {result.failure_reason or 'None'}",
        f"- Relevant Issues: {_numbers(result.relevant_issues)}",
        f"- Relevant PRs: {_numbers(result.relevant_prs)}",
        f"- CI Result: `{result.ci_result.get('summary', 'not observed')}`",
        "",
        "Objective Rule Results:",
        "",
    ]
    for rule in result.objective_rule_results:
        marker = "PASS" if rule.passed else "FAIL"
        lines.append(
            f"- {marker}: {rule.name} (`{rule.metric}` {rule.operator} `{rule.expected}`; actual `{rule.actual}`)"
        )
    lines.extend(["", "Post-run Agentic Diagnosis:", ""])
    if result.post_run_agentic_diagnosis:
        for key, value in result.post_run_agentic_diagnosis.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None recorded.")
    lines.append("")
    return lines


def _numbers(items: list[dict[str, object]]) -> str:
    if not items:
        return "none"
    return ", ".join(f"#{item.get('number')}" for item in items)


def _single_line(text: str) -> str:
    return " ".join(text.split())
