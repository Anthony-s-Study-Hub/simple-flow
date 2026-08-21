from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simple_flow_test_harness.models import RunReport, ScenarioResult
from simple_flow_test_harness.transcript import compact_codex_response, compact_text


def write_reports(report: RunReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{report.run_id}.json"
    md_path = report_dir / f"{report.run_id}.md"
    json_path.write_text(json.dumps(compact_report_data(report), indent=2) + "\n", encoding="utf-8")
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
        f"- Run Mode: `{report.run_mode}`",
        f"- Overall Status: `{report.overall_status.value}`",
        f"- Harness Commit SHA: `{report.harness_commit_sha}`",
        f"- Workflow Package Version: `{report.workflow_package_version}`",
        f"- Test Repo: `{report.test_repo_url}`",
        f"- Timeout Seconds: `{report.timeout_seconds}`",
        f"- Codex Model: `{report.codex_model or 'default'}`",
        f"- Codex CLI Version: `{_single_line(report.codex_cli_version)}`",
        f"- Smoke Scenarios: `{', '.join(report.smoke_scenario_ids) or 'none'}`",
        "",
    ]
    if report.full_suite_skipped_reason:
        lines.extend(["## Smoke Gate", "", report.full_suite_skipped_reason, ""])

    lines.extend(["## Status Counts", ""])
    for status, count in report.status_counts().items():
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Scenario Summary", ""])
    for result in report.scenarios:
        reason = compact_text(result.failure_reason or "objective rules satisfied", 220)
        lines.append(f"- {result.scenario_id}: {result.status.value} - {reason}")

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
        f"- Failure Reason: {compact_text(result.failure_reason or 'None', 350)}",
        f"- Relevant Issues: {_numbers(result.relevant_issues)}",
        f"- Relevant PRs: {_numbers(result.relevant_prs)}",
        f"- CI Result: `{result.ci_result.get('summary', 'not observed')}`",
        "",
        "Fixture Prompt:",
        "",
    ]
    if result.prompt_exchange:
        for exchange in result.prompt_exchange:
            prompt = exchange.fixture_prompt
            lines.append(f"- {exchange.action_ref}: {prompt.get('user_action', 'not captured')}")
    else:
        lines.append("- None captured.")

    lines.extend(["", "Response Received:", ""])
    if result.prompt_exchange:
        for exchange in result.prompt_exchange:
            response = exchange.response_received
            lines.append(
                f"- {exchange.action_ref}: {response.get('meaningful_response', 'not captured')} "
                f"(exit `{response.get('exit_code')}`)"
            )
    else:
        lines.append("- None captured.")

    lines.extend(["", "Objective Rule Results:", ""])
    for rule in result.objective_rule_results:
        marker = "PASS" if rule.passed else "FAIL"
        lines.append(
            f"- {marker}: {rule.name} (`{rule.metric}` {rule.operator} `{rule.expected}`; "
            f"actual `{compact_text(str(rule.actual), 180)}`)"
        )

    lines.extend(["", "Post-run Agentic Diagnosis:", ""])
    if result.post_run_agentic_diagnosis:
        for key, value in result.post_run_agentic_diagnosis.items():
            lines.append(f"- {key}: {compact_text(value, 220)}")
    else:
        lines.append("- None recorded.")
    lines.append("")
    return lines


def compact_report_data(report: RunReport) -> dict[str, Any]:
    return _compact_value(report.to_json_data())


def _compact_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_compact_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    if {"command", "cwd", "exit_code", "stdout", "stderr"} <= set(value):
        response = compact_codex_response(
            str(value.get("stdout", "")),
            str(value.get("stderr", "")),
            int(value["exit_code"]) if value.get("exit_code") is not None else None,
        )
        return {
            "command": _compact_command(value.get("command", [])),
            "cwd": value.get("cwd", ""),
            "exit_code": value.get("exit_code"),
            "meaningful_output": response["meaningful_response"],
            "stdout_chars": response["stdout_chars"],
            "stderr_chars": response["stderr_chars"],
        }

    compacted: dict[str, Any] = {}
    for key, child in value.items():
        if key in {"codex_output", "draft_text", "body"} and isinstance(child, str):
            compacted[key] = compact_text(child, 900)
        elif key == "failure_reason" and isinstance(child, str):
            compacted[key] = compact_text(child, 700)
        else:
            compacted[key] = _compact_value(child)
    return compacted


def _compact_command(command: Any) -> list[str]:
    if not isinstance(command, list):
        return [compact_text(str(command), 160)]

    compacted: list[str] = []
    for part in command:
        text = str(part)
        if text.startswith("USER_ACTION TO EXECUTE NOW:") or len(text) > 220:
            compacted.append(compact_text(text, 220))
        else:
            compacted.append(text)
    return compacted


def _numbers(items: list[dict[str, object]]) -> str:
    if not items:
        return "none"
    return ", ".join(f"#{item.get('number')}" for item in items)


def _single_line(text: str) -> str:
    return " ".join(text.split())
