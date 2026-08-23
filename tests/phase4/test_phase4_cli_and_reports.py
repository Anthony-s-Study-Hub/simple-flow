from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

from simple_flow_test_harness.cli import (
    DEFAULT_AGENT_BACKEND,
    DEFAULT_CODEX_MODEL,
    DEFAULT_LOCAL_LLM_MODEL,
    DEFAULT_LOCAL_LLM_URL,
    _parse_args,
)
from simple_flow_test_harness.agent_backends import CodexCliBackend
from simple_flow_test_harness.models import CommandResult, Outcome, ScenarioResult
from simple_flow_test_harness.reports import compact_report_data, render_markdown
from simple_flow_test_harness.runner import (
    Phase4Runner,
    _add_delta_metrics,
    _agent_infrastructure_blocker,
    _codex_infrastructure_blocker,
    _combined_codex_exit_code,
)
from simple_flow_test_harness.scenarios import REQUIRED_SCENARIO_IDS, SMOKE_SCENARIO_IDS
from simple_flow_test_harness.scenarios import FULL_SUITE_SCENARIO_IDS, PHASE5_EXTENSION_SCENARIO_IDS
from simple_flow_test_harness.transcript import compact_codex_response, compact_fixture_prompt


ROOT = Path(__file__).resolve().parents[2]


def test_phase4_validate_command_is_static() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_test_harness.cli",
            "validate",
            "--source-root",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Phase 4 scenario catalog valid: 38 scenarios" in completed.stdout
    assert "Full suite scenarios: 37" in completed.stdout
    assert "Phase 5 extension scenarios: 12" in completed.stdout


def test_phase4_dry_run_generates_machine_and_human_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_test_harness.cli",
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
    assert args.agent_backend == DEFAULT_AGENT_BACKEND
    assert args.timeout_seconds == 60
    assert args.codex_model == DEFAULT_CODEX_MODEL
    assert "mini" in DEFAULT_CODEX_MODEL
    assert args.smoke_gate is True
    assert args.smoke_only is False
    assert args.codex_bypass_sandbox is True
    assert "simple-flow-test-harness-workspace" in args.workspace_root


def test_phase4_cli_supports_local_openai_backend() -> None:
    args = _parse_args(
        [
            "run",
            "--agent-backend",
            "local-openai",
            "--local-llm-url",
            "http://127.0.0.1:1234",
            "--local-llm-model",
            "local/test-model",
        ]
    )

    assert args.agent_backend == "local-openai"
    assert args.local_llm_url == "http://127.0.0.1:1234"
    assert args.local_llm_model == "local/test-model"
    assert DEFAULT_LOCAL_LLM_URL == "http://169.254.83.107:1234"
    assert DEFAULT_LOCAL_LLM_MODEL == "google/gemma-4-e4b"


def test_phase4_cli_supports_codex_oss_local_provider() -> None:
    args = _parse_args(
        [
            "run",
            "--agent-backend",
            "codex",
            "--codex-oss",
            "--codex-local-provider",
            "lmstudio",
            "--codex-model",
            "google/gemma-4-e4b",
        ]
    )

    assert args.agent_backend == "codex"
    assert args.codex_oss is True
    assert args.codex_local_provider == "lmstudio"
    assert args.codex_model == "google/gemma-4-e4b"


def test_codex_backend_command_can_use_oss_local_provider(tmp_path: Path) -> None:
    config = replace(
        _dry_config(tmp_path),
        dry_run=False,
        codex_command="codex",
        codex_oss=True,
        codex_local_provider="lmstudio",
        codex_model="google/gemma-4-e4b",
    )

    command = CodexCliBackend(config)._codex_command(tmp_path, "Say ok", "")

    assert command[:3] == ["codex", "exec", "--json"]
    assert "--oss" in command
    assert command[command.index("--local-provider") + 1] == "lmstudio"
    assert 'model_provider="lmstudio"' in command
    assert command[command.index("--model") + 1] == "google/gemma-4-e4b"


def test_codex_backend_resume_keeps_oss_provider_override(tmp_path: Path) -> None:
    config = replace(
        _dry_config(tmp_path),
        dry_run=False,
        codex_command="codex",
        codex_oss=True,
        codex_local_provider="lmstudio",
        codex_model="google/gemma-4-e4b",
    )

    command = CodexCliBackend(config)._codex_command(tmp_path, "Continue", "thread-123")

    assert command[:4] == ["codex", "exec", "resume", "--json"]
    assert "--oss" not in command
    assert "--local-provider" not in command
    assert 'model_provider="lmstudio"' in command
    assert command[command.index("--model") + 1] == "google/gemma-4-e4b"
    assert command[-2:] == ["thread-123", "Continue"]


def test_probe_codex_local_llm_command_is_static() -> None:
    args = _parse_args(
        [
            "probe-codex-local-llm",
            "--local-llm-url",
            "http://127.0.0.1:1234",
            "--local-llm-model",
            "google/gemma-4-e4b",
            "--codex-local-provider",
            "lmstudio",
        ]
    )

    assert args.command == "probe-codex-local-llm"
    assert args.local_llm_url == "http://127.0.0.1:1234"
    assert args.local_llm_model == "google/gemma-4-e4b"
    assert args.codex_local_provider == "lmstudio"


def test_phase4_timeout_blocker_takes_precedence_over_noisy_model_cache_output() -> None:
    result = CommandResult(
        command=("codex-action", "S01", "S01-U1"),
        cwd=str(ROOT),
        exit_code=124,
        stdout="",
        stderr="Codex action S01-U1 timed out after 60 seconds.\nfailed to refresh available models",
    )

    assert _codex_infrastructure_blocker(result) == "Codex CLI infrastructure blocker: timed out"


def test_phase4_local_model_tool_limit_is_not_infrastructure_blocker() -> None:
    result = CommandResult(
        command=("agent-scenario", "local-openai", "C01"),
        cwd=str(ROOT),
        exit_code=1,
        stdout='{"type":"local_llm.stopped","message":"Local OpenAI backend stopped: maximum tool call count exceeded."}',
        stderr="Local OpenAI backend stopped: maximum tool call count exceeded.",
    )

    assert _agent_infrastructure_blocker(result, "local-openai") == ""


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


def test_phase4_passing_smoke_gate_does_not_repeat_smoke_members(tmp_path: Path, monkeypatch) -> None:
    selected_batches: list[list[str]] = []

    def fake_run_selected(self, selected_scenarios, **kwargs):
        selected_batches.append([scenario.scenario_id for scenario in selected_scenarios])
        return [_pass_result(scenario.scenario_id) for scenario in selected_scenarios]

    monkeypatch.setattr(Phase4Runner, "_run_selected", fake_run_selected)
    config = replace(_dry_config(tmp_path), dry_run=False, codex_command=sys.executable)

    report = Phase4Runner(config).run()

    expected_remaining = [
        scenario_id
        for scenario_id in FULL_SUITE_SCENARIO_IDS
        if scenario_id not in SMOKE_SCENARIO_IDS
    ]
    assert selected_batches == [list(SMOKE_SCENARIO_IDS), expected_remaining]
    assert report.run_mode == "smoke-gated"
    assert report.full_suite_skipped_reason == ""
    for scenario_id in SMOKE_SCENARIO_IDS:
        assert [result.scenario_id for result in report.scenarios].count(scenario_id) == 1


def test_phase4_smoke_only_cli_generates_smoke_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_test_harness.cli",
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


def test_phase4_local_backend_dry_run_reports_codex_not_used(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_test_harness.cli",
            "run",
            "--scenario",
            "A01",
            "--dry-run",
            "--agent-backend",
            "local-openai",
            "--local-llm-url",
            "http://127.0.0.1:1234",
            "--local-llm-model",
            "local/test-model",
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
    markdown = (report_dir / "latest.md").read_text(encoding="utf-8")
    assert data["agent_backend"] == "local-openai"
    assert data["agent_model"] == "local/test-model"
    assert data["agent_endpoint"] == "http://127.0.0.1:1234"
    assert data["codex_cli_used"] is False
    assert data["scenarios"][0]["agent_backend"] == "local-openai"
    assert data["scenarios"][0]["codex_cli_used"] is False
    assert "Agent Backend" in markdown
    assert "Codex CLI Used: `False`" in markdown
    assert "Codex Model: `n/a`" in markdown


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
    from simple_flow_test_harness.environment import DEFAULT_TEST_REPO_URL, default_gh_path
    from simple_flow_test_harness.models import Phase4Config

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


def _pass_result(scenario_id: str) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        status=Outcome.PASS,
        prompt_reference=f"phase4-scenario:{scenario_id}",
        expected_result={},
        observed_result={},
        evidence={},
        failure_reason="",
        initial_state={},
        final_state={},
        github_test_repo="Anthony-s-Study-Hub/simple-flow-test",
        relevant_issues=[],
        relevant_prs=[],
        ci_result={"summary": "stubbed"},
        codex_cli_version="stubbed",
        workflow_package_version="stubbed",
        harness_commit_sha="stubbed",
        execution_timestamp="2026-08-21T00:00:00+00:00",
    )


def test_source_ci_does_not_run_live_phase4_experiment() -> None:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )

    assert "phase4-run run" not in workflow_text
    assert "codex exec" not in workflow_text
