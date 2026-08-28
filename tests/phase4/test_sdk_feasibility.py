from __future__ import annotations

from dataclasses import replace
import asyncio
import time

import pytest

from simple_flow_test_harness.cli import _parse_args, _sdk_config, main
from simple_flow_test_harness.sdk_feasibility import (
    CHECKPOINTS,
    DEFAULT_LIVENESS_SECONDS,
    LocalModelConfig,
    PILOT_SCENARIOS,
    RemoteVerificationConfig,
    RemoteVerification,
    RemoteScenarioPipeline,
    RemoteSnapshot,
    SdkEvent,
    SdkTurn,
    TrialResult,
    Verdict,
    WorkspaceSnapshot,
    capability_confidence,
    capability_confidence_by_scenario,
    prompt_is_developer_realistic,
    run_pilot_trial,
    _stream_with_liveness,
    _git_changed_paths,
    _prepare_fixture,
    _remaining_action_seconds,
    _executes_skill_script,
    _has_draft_review_links,
    _remote_execution_preflight,
    _scenario_precondition,
    _sandbox_mode,
    _skill_tool_invocation_evidence,
    _tool_invocation_evidence,
)


def _config() -> LocalModelConfig:
    return LocalModelConfig(
        host="codex-sdk",
        endpoint="http://127.0.0.1:1234",
        model="local-test-model",
        action_timeout_seconds=61,
    )


def test_pilot_prompts_are_developer_requests_without_harness_mechanics() -> None:
    assert {scenario.scenario_id for scenario in PILOT_SCENARIOS} == {"P02", "P03-U", "P03-R", "P04", "P05", "P06"}
    assert {scenario.required_skill for scenario in PILOT_SCENARIOS} == {
        "issue-draft", "start-implement", "review-triage", "documentation-curation", "pr-finalize",
    }
    assert all(prompt_is_developer_realistic(scenario.prompt) for scenario in PILOT_SCENARIOS)
    assert not prompt_is_developer_realistic("Run python .codex/skills/issue-draft/scripts/create_draft.py")
    assert {
        scenario.scenario_id: scenario.draft_work_type
        for scenario in PILOT_SCENARIOS
        if scenario.draft_work_type is not None
    } == {"P02": "FEATURE", "P05": "DOCUMENTATION"}


def test_checkpoint_classes_make_confidence_scope_explicit() -> None:
    eligible = {checkpoint.name for checkpoint in CHECKPOINTS if checkpoint.confidence_eligible}
    assert eligible == {"workflow_outcome", "stop_boundary"}
    assert all(checkpoint.test_class.value != "deterministic" for checkpoint in CHECKPOINTS if checkpoint.confidence_eligible)


def test_remote_codex_turns_use_full_access_while_local_turns_stay_workspace_write() -> None:
    remote = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    local = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P02")
    assert _sandbox_mode(_config(), remote) == "full-access"
    assert _sandbox_mode(_config(), local) == "workspace-write"


class _FakeRemoteGateway:
    def __init__(self, before: RemoteSnapshot, after: RemoteSnapshot, files: dict[tuple[str, str], str]):
        self.before = before
        self.after = after
        self.files = files
        self.cleaned: dict[str, object] | None = None
        self.snapshot_calls = 0
        self.ci = ()

    def snapshot(self, _base_branch: str) -> RemoteSnapshot:
        self.snapshot_calls += 1
        if self.snapshot_calls == 1:
            return self.before
        if self.cleaned is None:
            return self.after
        closed_issues = tuple({**item, "state": "closed"} for item in self.after.issues)
        closed_prs = tuple({**item, "state": "closed"} for item in self.after.pull_requests)
        deleted_branches = {name: sha for name, sha in self.after.branches.items() if name == "main"}
        return RemoteSnapshot(self.after.repository, self.after.base_branch, self.after.base_sha, closed_issues, closed_prs, deleted_branches)

    def file_content(self, branch: str, path: str) -> str:
        return self.files[(branch, path)]

    def branch_descends_from(self, _base_sha: str, _branch: str) -> bool:
        return True

    def ci_conclusions(self, _pr_number: int) -> tuple[str, ...]:
        return self.ci

    def issue_has_cleanup_note(self, _issue_number: int) -> bool:
        return True

    def cleanup(self, **kwargs):
        self.cleaned = kwargs
        return {"success": True, "actions": []}

    def seed_finalize_fixture(self, _expectation):
        return {"issue_number": 42, "pr_number": 43, "branch": "phase4-harness/pr-finalize-42"}


def test_remote_pipeline_checks_fixed_manifest_references_and_cleans_only_matched_artifacts() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo",
        "main",
        "base-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title},),
        ({
            "number": 43,
            "title": scenario.remote_expectation.pr_title,
            "base": {"ref": "main"},
            "head": {"ref": "documentation/42-phase4-smoke"},
            "draft": True,
            "merged_at": None,
        },),
        {"main": "base-sha", "documentation/42-phase4-smoke": "head-sha"},
    )
    gateway = _FakeRemoteGateway(
        before,
        after,
        {("documentation/42-phase4-smoke", "docs/app/usage.md"): scenario.remote_expectation.exact_files[0][1]},
    )
    pipeline = RemoteScenarioPipeline(scenario, gateway)
    assert pipeline.capture_before().verdict == Verdict.PASS
    result = pipeline.capture_and_verify()
    assert result.verdict == Verdict.PASS
    assert result.cleanup_verdict == Verdict.PASS
    assert result.evidence["matched_issue_number"] == 42
    assert result.evidence["matched_pr_number"] == 43
    assert gateway.cleaned == {"pr_numbers": (43,), "issue_numbers": (42,), "branches": ()}


def test_remote_pipeline_rejects_unexpected_remote_mutations() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo", "main", "base-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title}, {"number": 99, "title": "unrelated"}),
        (),
        {"main": "base-sha"},
    )
    pipeline = RemoteScenarioPipeline(scenario, _FakeRemoteGateway(before, after, {}))
    pipeline.capture_before()
    result = pipeline.capture_and_verify()
    assert result.verdict == Verdict.FAIL
    assert any("Unexpected new issues" in failure for failure in result.evidence["failures"])


def test_remote_pipeline_attempts_cleanup_when_verification_errors() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo", "main", "base-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title},),
        ({"number": 43, "title": scenario.remote_expectation.pr_title, "base": {"ref": "main"}, "head": {"ref": "documentation/42-phase4-smoke"}, "draft": True, "merged_at": None},),
        {"main": "base-sha", "documentation/42-phase4-smoke": "head-sha"},
    )
    gateway = _FakeRemoteGateway(before, after, {})
    pipeline = RemoteScenarioPipeline(scenario, gateway)
    pipeline.capture_before()
    result = pipeline.capture_and_verify()
    assert result.verdict == Verdict.FAIL
    assert gateway.cleaned == {"pr_numbers": (43,), "issue_numbers": (42,), "branches": ()}


def test_remote_pipeline_reuses_manifest_for_ci_dependent_skills() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    scenario = replace(scenario, remote_expectation=replace(scenario.remote_expectation, ci_expectation="success"))
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo", "main", "base-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title},),
        ({"number": 43, "title": scenario.remote_expectation.pr_title, "base": {"ref": "main"}, "head": {"ref": "documentation/42-phase4-smoke"}, "draft": True, "merged_at": None},),
        {"main": "base-sha", "documentation/42-phase4-smoke": "head-sha"},
    )
    gateway = _FakeRemoteGateway(before, after, {("documentation/42-phase4-smoke", "docs/app/usage.md"): scenario.remote_expectation.exact_files[0][1]})
    gateway.ci = ("SUCCESS",)
    pipeline = RemoteScenarioPipeline(scenario, gateway)
    pipeline.capture_before()
    assert pipeline.capture_and_verify().verdict == Verdict.PASS


def test_pr_finalize_pipeline_verifies_the_seeded_artifact_lifecycle() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P06")
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo", "main", "merged-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title, "state": "closed"},),
        ({
            "number": 43, "title": scenario.remote_expectation.pr_title,
            "base": {"ref": "main"}, "head": {"ref": "phase4-harness/pr-finalize-42"},
            "draft": False, "state": "closed", "merged_at": "2026-08-24T00:00:00Z",
        },),
        {"main": "merged-sha"},
    )
    gateway = _FakeRemoteGateway(before, after, {("main", "docs/app/usage.md"): scenario.remote_expectation.exact_files[0][1]})
    pipeline = RemoteScenarioPipeline(scenario, gateway)
    assert pipeline.capture_before().verdict == Verdict.PASS
    assert pipeline.prepare_fixture().verdict == Verdict.PASS
    result = pipeline.capture_and_verify()
    assert result.verdict == Verdict.PASS
    assert result.cleanup_verdict == Verdict.PASS
    assert result.evidence["fixture"]["pr_number"] == 43
    assert gateway.cleaned == {"pr_numbers": (), "issue_numbers": (42,), "branches": ()}


def test_pr_finalize_cleanup_does_not_delete_a_pr_head_twice() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P06")
    before = RemoteSnapshot("owner/repo", "main", "base-sha", (), (), {"main": "base-sha"})
    after = RemoteSnapshot(
        "owner/repo", "main", "base-sha",
        ({"number": 42, "title": scenario.remote_expectation.issue_title, "state": "open"},),
        ({"number": 43, "title": scenario.remote_expectation.pr_title, "merged_at": None},),
        {"main": "base-sha", "phase4-harness/pr-finalize-42": "head-sha"},
    )
    pipeline = RemoteScenarioPipeline(scenario, _FakeRemoteGateway(before, after, {}))
    pipeline.before = before
    pipeline.fixture = {"issue_number": 42, "pr_number": 43, "branch": "phase4-harness/pr-finalize-42"}
    assert pipeline._run_artifact_ids(after) == ((43,), (42,), ())


def test_trial_cross_checks_trace_result_and_local_state() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P02")
    turn = SdkTurn(
        final_text=(
            "Created DRAFT-0001.\n"
            "[Open draft for review](<C:/phase4/.simple-flow/drafts/DRAFT-0001.md>)\n"
            "[Open draft JSON](<C:/phase4/.simple-flow/drafts/DRAFT-0001.json>)"
        ),
        structured_result={
            "schema_version": 1,
            "session_id": "session-1",
            "final_text": "draft created",
            "event_count": 1,
            "turn_completed": True,
        },
        events=(
            SdkEvent("event", {"method": "turn/completed"}),
            SdkEvent("tool", {"method": "item/completed", "item": {
                "type": "commandExecution",
                "command": "python .codex/skills/issue-draft/scripts/create_draft.py --input draft_input.json",
                "exitCode": 0,
            }}),
        ),
        submitted_prompt=scenario.prompt,
        attached_skill="issue-draft",
        completed=True,
    )
    result = run_pilot_trial(
        scenario,
        turn,
        WorkspaceSnapshot(0, (), 0),
        WorkspaceSnapshot(1, (".simple-flow/drafts/DRAFT-0001.json",), 0),
        config=_config(),
    )
    assert set(result.verdicts.values()) == {Verdict.PASS}
    changed_prompt = run_pilot_trial(
        scenario,
        replace(turn, submitted_prompt="altered by harness"),
        WorkspaceSnapshot(0, (), 0),
        WorkspaceSnapshot(1, (".simple-flow/drafts/DRAFT-0001.json",), 0),
        config=_config(),
    )
    assert changed_prompt.verdicts["prompt_fidelity"] == Verdict.FAIL


def test_draft_review_link_contract_requires_one_absolute_markdown_json_pair() -> None:
    assert _has_draft_review_links(
        "[Open draft for review](<C:/phase4/.simple-flow/drafts/DRAFT-0001.md>)\n"
        "[Open draft JSON](<C:/phase4/.simple-flow/drafts/DRAFT-0001.json>)"
    )
    assert not _has_draft_review_links(
        "[Open draft for review](.simple-flow/drafts/DRAFT-0001.md)\n"
        "[Open draft JSON](.simple-flow/drafts/DRAFT-0001.json)"
    )
    assert not _has_draft_review_links(
        "[Open draft for review](<C:/phase4/.simple-flow/drafts/DRAFT-0001.md>)\n"
        "[Open draft JSON](<C:/phase4/.simple-flow/drafts/DRAFT-0002.json>)"
    )


def test_report_retains_failed_command_evidence_and_redacts_tokens() -> None:
    events = (
        SdkEvent(
            "tool",
            {
                "method": "item/completed",
                "item": {
                    "type": "commandExecution",
                    "command": "sed -n '1p' .codex/skills/issue-draft/scripts/create_draft.py",
                    "exitCode": 1,
                    "aggregatedOutput": "sed unavailable",
                },
            },
        ),
        SdkEvent(
            "tool",
            {
                "method": "item/completed",
                "item": {
                    "type": "commandExecution",
                    "command": "python .codex/skills/issue-draft/scripts/create_draft.py",
                    "exitCode": 1,
                    "aggregatedOutput": "fatal: denied; token gho_abcdefghijklmnopqrstuvwxyz123456",
                },
            },
        ),
    )
    evidence = _tool_invocation_evidence(events)
    assert evidence[1:] == [{
        "type": "commandExecution",
        "command": "python .codex/skills/issue-draft/scripts/create_draft.py",
        "exit_code": 1,
        "output": "fatal: denied; token [REDACTED_TOKEN]",
    }]
    assert _skill_tool_invocation_evidence(evidence, "issue-draft") == evidence[1:]
    assert _executes_skill_script(
        'pwsh -Command "python .\\.codex\\skills\\issue-draft\\scripts\\create_draft.py"',
        ".codex/skills/issue-draft/scripts/",
    )
    assert not _executes_skill_script(
        'pwsh -Command "python -c \\"print(open(\'.codex/skills/issue-draft/scripts/create_draft.py\').read())\\""',
        ".codex/skills/issue-draft/scripts/",
    )
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P02")
    turn = SdkTurn(
        final_text="draft created",
        structured_result={"schema_version": 1, "session_id": "s", "final_text": "draft created", "event_count": 1, "turn_completed": True},
        events=events,
        submitted_prompt=scenario.prompt,
        attached_skill="issue-draft",
        completed=True,
    )
    result = run_pilot_trial(scenario, turn, WorkspaceSnapshot(0, (), 0), WorkspaceSnapshot(1, (), 0), config=_config())
    assert result.evidence["failed_tool_invocations"] == evidence
    assert result.evidence["failed_skill_tool_invocations"] == evidence[1:]


def test_remote_preflight_blocks_before_agent_when_git_ref_write_is_unavailable(monkeypatch, tmp_path) -> None:
    import simple_flow_test_harness.sdk_feasibility as feasibility

    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")

    def fake_command(command, _project_root, *, environment=None):
        if command == ["git", "branch", "--show-current"]:
            return {"command": command, "exit_code": 0, "stdout": "main\n", "stderr": ""}
        if command[:3] == ["git", "checkout", "-B"]:
            return {"command": command, "exit_code": 1, "stdout": "", "stderr": "Permission denied"}
        return {"command": command, "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(feasibility, "_preflight_command", fake_command)
    result = _remote_execution_preflight(tmp_path, scenario, _config())
    assert result.verdict == Verdict.BLOCKED
    check = result.evidence
    assert check["sandbox"] == "full-access"
    assert check["failures"] == ["Git ref write preflight failed"]
    assert check["commands"][1]["stderr"] == "Permission denied"


def test_blocked_remote_preflight_does_not_enter_capability_confidence() -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    turn = SdkTurn(
        final_text="",
        structured_result={"schema_version": 1, "session_id": "s", "final_text": "", "event_count": 0, "turn_completed": True},
        events=(),
        submitted_prompt=scenario.prompt,
        attached_skill="start-implement",
        completed=True,
    )
    blocked = RemoteVerification(Verdict.BLOCKED, {"error": "Git ref write preflight failed"})
    result = run_pilot_trial(
        scenario,
        turn,
        WorkspaceSnapshot(1, (), 0),
        WorkspaceSnapshot(1, (), 0),
        config=_config(),
        remote=blocked,
    )
    assert result.verdicts["workflow_outcome"] == Verdict.BLOCKED
    assert capability_confidence([result], "workflow_outcome")["valid_trials"] == 0


def test_confidence_uses_only_valid_capability_trials() -> None:
    trials = [
        TrialResult("P02", {"workflow_outcome": Verdict.PASS}, {}),
        TrialResult("P02", {"workflow_outcome": Verdict.FAIL}, {}),
        TrialResult("P02", {"workflow_outcome": Verdict.BLOCKED}, {}),
        TrialResult("P02", {"workflow_outcome": Verdict.UNKNOWN}, {}),
    ]
    summary = capability_confidence(trials, "workflow_outcome")
    assert summary["valid_trials"] == 2
    assert summary["passed_trials"] == 1
    assert summary["blocked_trials"] == 1
    assert summary["unknown_trials"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["wilson_95"][0] < 0.5 < summary["wilson_95"][1]
    with pytest.raises(ValueError, match="not confidence-eligible"):
        capability_confidence(trials, "objective_state")
    with pytest.raises(ValueError, match="exactly one scenario"):
        capability_confidence([trials[0], TrialResult("P03-U", {"workflow_outcome": Verdict.PASS}, {})], "workflow_outcome")
    assert [item["scenario_id"] for item in capability_confidence_by_scenario(trials)] == ["P02"]


def test_local_model_config_requires_non_polling_interval_and_larger_timeout() -> None:
    with pytest.raises(ValueError, match="at least 60"):
        LocalModelConfig("codex-sdk", "http://127.0.0.1:1234", "model", liveness_seconds=59, action_timeout_seconds=61)
    with pytest.raises(ValueError, match="must exceed"):
        LocalModelConfig("codex-sdk", "http://127.0.0.1:1234", "model", liveness_seconds=DEFAULT_LIVENESS_SECONDS, action_timeout_seconds=60)


def test_sdk_preflight_uses_its_own_safe_action_timeout_default() -> None:
    assert _sdk_config(_parse_args(["sdk-preflight"])).action_timeout_seconds == 900


def test_sdk_pilot_rejects_zero_repetitions(capsys) -> None:
    assert main(["sdk-pilot", "--repetitions", "0"]) == 2
    assert "must be positive" in capsys.readouterr().err


def test_stream_liveness_does_not_cancel_the_sdk_owned_generator() -> None:
    async def exercise() -> list[object]:
        release = asyncio.Event()

        async def source():
            await release.wait()
            yield "completed"

        stream = _stream_with_liveness(source(), liveness_seconds=0.01, action_timeout_seconds=1)
        first = await anext(stream)
        release.set()
        second = await anext(stream)
        await stream.aclose()
        return [first, second]

    liveness, completed = asyncio.run(exercise())
    assert isinstance(liveness, SdkEvent)
    assert liveness.kind == "liveness_check"
    assert completed == "completed"


def test_action_timeout_budget_includes_turn_startup() -> None:
    assert 0 < _remaining_action_seconds(time.monotonic(), 1) <= 1
    with pytest.raises(TimeoutError, match="SDK action exceeded 1 seconds"):
        _remaining_action_seconds(-10_000.0, 1)


def test_workspace_observer_ignores_harness_logs_and_python_cache(tmp_path) -> None:
    import subprocess

    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "package/__init__.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=pilot@example.invalid", "-c", "user.name=Phase 4 Pilot", "commit", "--quiet", "-m", "fixture"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "phase4-sdk-run.stdout.log").write_text("log", encoding="utf-8")
    cache = package / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.cpython-311.pyc").write_bytes(b"cache")
    (tmp_path / "meaningful.txt").write_text("change", encoding="utf-8")
    assert _git_changed_paths(tmp_path) == ["meaningful.txt"]


def test_p02_fixture_is_harness_setup_not_prompt_content(tmp_path) -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P02")
    _prepare_fixture(tmp_path, scenario)
    fixture = tmp_path / "draft_input.json"
    assert fixture.is_file()
    assert '"work_type": "FEATURE"' in fixture.read_text(encoding="utf-8")
    assert fixture.name not in scenario.prompt


def test_p03_remote_context_is_run_scoped_fixture_not_prompt_content(tmp_path) -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    _prepare_fixture(tmp_path, scenario, RemoteVerificationConfig("owner/disposable", "gh"))
    context = tmp_path / ".simple-flow" / "phase4-remote-context.json"
    assert '"repository": "owner/disposable"' in context.read_text(encoding="utf-8")
    assert "owner/disposable" not in scenario.prompt


def test_p03_remote_precondition_validates_the_independent_mock_draft(tmp_path) -> None:
    scenario = next(item for item in PILOT_SCENARIOS if item.scenario_id == "P03-R")
    _prepare_fixture(tmp_path, scenario, RemoteVerificationConfig("owner/disposable", "gh"))
    precondition = _scenario_precondition(tmp_path, scenario)
    assert precondition.verdict == Verdict.PASS
    assert precondition.evidence["path"] == "DOCUMENTATION_NORMAL"
    (tmp_path / ".simple-flow" / "drafts" / "DRAFT-0001.json").unlink()
    assert _scenario_precondition(tmp_path, scenario).verdict == Verdict.BLOCKED
