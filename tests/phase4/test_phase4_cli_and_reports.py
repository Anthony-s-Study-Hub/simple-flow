from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from simple_flow_phase4.cli import DEFAULT_CODEX_MODEL, _parse_args
from simple_flow_phase4.models import CommandResult
from simple_flow_phase4.reports import compact_report_data, render_markdown
from simple_flow_phase4.runner import (
    Phase4Runner,
    _add_delta_metrics,
    _codex_infrastructure_blocker,
    _combined_codex_exit_code,
)
from simple_flow_phase4.scenarios import SMOKE_SCENARIO_IDS
from simple_flow_phase4.transcript import compact_codex_response, compact_fixture_prompt


ROOT = Path(__file__).resolve().parents[2]


def test_phase4_validate_command_is_static() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_phase4.cli",
            "validate",
            "--source-root",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Phase 4 scenario catalog valid: 26 scenarios" in completed.stdout
    assert "Full suite scenarios: 25" in completed.stdout


def test_phase4_dry_run_generates_machine_and_human_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_phase4.cli",
            "run",
            "--scenario",
            "A01",
            "--dry-run",
            "--source-root",
            str(ROOT),
            "--workspace-root",
            str(workspace),
            "--report-dir",
            str(report_dir),
            "--codex-command",
            "missing-codex-command-for-static-test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    assert latest_json.exists()
    assert latest_md.exists()

    data = json.loads(latest_json.read_text(encoding="utf-8"))
    assert data["overall_status"] == "NOT_RUN"
    assert data["status_counts"]["NOT_RUN"] == 1
    assert data["scenarios"][0]["scenario_id"] == "A01"
    assert data["scenarios"][0]["codex_cli_version"] == "not run in dry-run mode"
    assert "Harness Commit SHA" in latest_md.read_text(encoding="utf-8")


def test_phase4_defaults_use_short_smoke_gate_and_mini_model() -> None:
    args = _parse_args([])

    assert args.command == "run"
    assert args.timeout_seconds == 60
    assert args.codex_model == DEFAULT_CODEX_MODEL
    assert "mini" in DEFAULT_CODEX_MODEL
    assert args.smoke_gate is True
    assert args.smoke_only is False


def test_phase4_timeout_blocker_takes_precedence_over_noisy_model_cache_output() -> None:
    result = CommandResult(
        command=("codex-action", "S01", "S01-U1"),
        cwd=str(ROOT),
        exit_code=124,
        stdout="",
        stderr="Codex action S01-U1 timed out after 60 seconds.\nfailed to refresh available models",
    )

    assert _codex_infrastructure_blocker(result) == "Codex CLI infrastructure blocker: timed out"


def test_phase4_combined_codex_result_preserves_timeout_exit_code() -> None:
    timeout = CommandResult(
        command=("codex-action", "S01", "S01-U1"),
        cwd=str(ROOT),
        exit_code=124,
        stdout="",
        stderr="timed out",
    )
    later = CommandResult(
        command=("codex-action", "S01", "S01-U2"),
        cwd=str(ROOT),
        exit_code=0,
        stdout="",
        stderr="",
    )

    assert _combined_codex_exit_code([("S01-U1", timeout), ("S01-U2", later)]) == 124


def test_phase4_delta_metrics_ignore_historical_closed_artifacts() -> None:
    historical_issue = {"number": 1, "state": "CLOSED"}
    historical_pr = {"number": 1, "state": "CLOSED", "isDraft": False, "mergedAt": None}
    initial_state = {
        "github": {
            "issues": [historical_issue],
            "pull_requests": [historical_pr],
        }
    }
    final_state = {
        "github": {
            "issues": [historical_issue, {"number": 2, "state": "OPEN"}],
            "pull_requests": [
                historical_pr,
                {"number": 2, "state": "OPEN", "isDraft": True, "mergedAt": None},
            ],
        },
        "metrics": {},
    }

    _add_delta_metrics(initial_state, final_state)

    assert final_state["metrics"]["new_issue_count"] == 1
    assert final_state["metrics"]["new_open_issue_count"] == 1
    assert final_state["metrics"]["new_pr_count"] == 1
    assert final_state["metrics"]["new_draft_pr_count"] == 1


def test_phase4_default_run_dry_run_exercises_smoke_only_before_full_suite(tmp_path: Path) -> None:
    config = _dry_config(tmp_path)

    report = Phase4Runner(config).run()

    assert report.run_mode == "smoke-gated"
    assert report.smoke_scenario_ids == list(SMOKE_SCENARIO_IDS)
    assert report.full_suite_skipped_reason == "Smoke gate did not pass; full Phase 4 suite was not run."
    assert [result.scenario_id for result in report.scenarios] == list(SMOKE_SCENARIO_IDS)


def test_phase4_smoke_only_cli_generates_smoke_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_phase4.cli",
            "run",
            "--smoke-only",
            "--dry-run",
            "--source-root",
            str(ROOT),
            "--workspace-root",
            str(workspace),
            "--report-dir",
            str(report_dir),
            "--codex-command",
            "missing-codex-command-for-static-test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    data = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
    assert data["run_mode"] == "smoke-only"
    assert [scenario["scenario_id"] for scenario in data["scenarios"]] == list(SMOKE_SCENARIO_IDS)


def test_compact_report_documents_processed_prompt_and_response() -> None:
    prompt = (
        "USER_ACTION TO EXECUTE NOW: @discussion \"Add status\"\n"
        "This is a human-supplied workflow action.\n"
        "Scenario ID: A01\n"
        "Scenario Purpose: Discussion smoke test.\n"
        "Action Reference: A01-U1\n"
        "Use this GitHub CLI executable for GitHub operations: C:/very/long/path/gh.exe\n"
    )
    raw_stdout = (
        '{"type":"thread.started","thread_id":"abc"}\n'
        '{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Discussed options and stopped before Issue-Draft."}]}\n'
        "RAW JSON NOISE " * 200
    )

    assert compact_fixture_prompt(prompt)["user_action"] == '@discussion "Add status"'
    assert compact_codex_response(raw_stdout, "", 0)["meaningful_response"] == (
        "Discussed options and stopped before Issue-Draft."
    )

    report = Phase4Runner(_dry_config(Path.cwd() / ".phase4-static-test")).run(["A01"])
    data = compact_report_data(report)
    markdown = render_markdown(report)

    assert data["scenarios"][0]["prompt_exchange"][0]["fixture_prompt"]["user_action"].startswith("@discussion")
    assert "Fixture Prompt" in markdown
    assert "Response Received" in markdown
    assert "RAW JSON NOISE" not in markdown


def _dry_config(tmp_path: Path):
    from simple_flow_phase4.environment import DEFAULT_TEST_REPO_URL, default_gh_path
    from simple_flow_phase4.models import Phase4Config

    return Phase4Config(
        source_root=ROOT,
        workspace_root=tmp_path / "workspace",
        report_dir=tmp_path / "reports",
        test_repo_url=DEFAULT_TEST_REPO_URL,
        gh_path=default_gh_path(),
        codex_command="missing-codex-command-for-static-test",
        timeout_seconds=60,
        allow_remote_reset=False,
        dry_run=True,
        codex_model=DEFAULT_CODEX_MODEL,
    )


def test_source_ci_does_not_run_live_phase4_experiment() -> None:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )

    assert "phase4-run run" not in workflow_text
    assert "codex exec" not in workflow_text
