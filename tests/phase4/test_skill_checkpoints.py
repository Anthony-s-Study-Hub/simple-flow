from __future__ import annotations

import json

from simple_flow_test_harness.checkpoints import evaluate_skill_checkpoints
from simple_flow_test_harness.models import CommandResult, Outcome, RuleResult, ScenarioResult, SkillCheckpoint
from simple_flow_test_harness.reports import render_markdown
from simple_flow_test_harness.scenarios import load_scenarios


def test_skill_checkpoints_mark_successful_helper_invocation_high_confidence() -> None:
    scenario = load_scenarios()["A02"]
    result = CommandResult(
        command=("agent-scenario", "local-openai", "A02"),
        cwd="workspace",
        exit_code=0,
        stdout=json.dumps(
            {
                "type": "local_llm.tool_call",
                "tool_name": "run_command",
                "script_invocation": {
                    "skill": "issue-draft",
                    "script": "create_draft.py",
                    "path": ".codex/skills/issue-draft/scripts/create_draft.py",
                },
                "result": {
                    "argv": [
                        "python",
                        ".codex/skills/issue-draft/scripts/create_draft.py",
                        "--input",
                        ".simple-flow/phase4-fixtures/A02-draft.json",
                    ],
                    "exit_code": 0,
                    "stdout": '{"status":"ok","draft_id":"DRAFT-0001"}',
                },
            }
        )
        + "\n"
        + json.dumps({"type": "local_llm.tool_call", "tool_name": "finish"})
        + "\n",
        stderr="",
    )
    metadata = {
        "turns": [
            {
                "resolved_skills": [
                    {
                        "alias": "@issue-draft",
                        "skill": "issue-draft",
                        "status": "loaded",
                    }
                ]
            }
        ]
    }
    rules = [
        RuleResult("feature draft created", True, "feature_draft_count", ">=", 1, 1),
        RuleResult("no open issue", True, "open_issue_count", "==", 0, 0),
    ]

    checkpoints, confidence = evaluate_skill_checkpoints(
        scenario=scenario,
        agent_backend="local-openai",
        agent_metadata=metadata,
        agent_result=result,
        objective_rule_results=rules,
        final_state={"metrics": {"feature_draft_count": 1}},
    )

    assert confidence == "HIGH"
    assert {checkpoint.name: checkpoint.status for checkpoint in checkpoints} == {
        "native skill discovery": "UNKNOWN",
        "harness skill resolution": "PASS",
        "skill context injection": "PASS",
        "helper intent": "PASS",
        "command shape": "PASS",
        "helper execution": "PASS",
        "side effect": "PASS",
        "stop point": "PASS",
    }


def test_skill_checkpoints_mark_missing_expected_helper_low_confidence() -> None:
    scenario = load_scenarios()["E01"]
    result = CommandResult(
        command=("agent-scenario", "local-openai", "E01"),
        cwd="workspace",
        exit_code=0,
        stdout=json.dumps({"type": "local_llm.message", "message": "I would curate the docs."}) + "\n",
        stderr="",
    )
    metadata = {
        "turns": [
            {
                "resolved_skills": [
                    {
                        "alias": "@documentation-curation",
                        "skill": "documentation-curation",
                        "status": "loaded",
                    }
                ]
            }
        ]
    }
    rules = [RuleResult("documentation draft created", False, "documentation_draft_count", ">=", 1, 0)]

    checkpoints, confidence = evaluate_skill_checkpoints(
        scenario=scenario,
        agent_backend="local-openai",
        agent_metadata=metadata,
        agent_result=result,
        objective_rule_results=rules,
        final_state={"metrics": {"documentation_draft_count": 0}},
    )

    by_name = {checkpoint.name: checkpoint for checkpoint in checkpoints}
    assert confidence == "LOW"
    assert by_name["native skill discovery"].status == "UNKNOWN"
    assert by_name["harness skill resolution"].status == "PASS"
    assert by_name["helper intent"].status == "FAIL"
    assert "documentation-curation/curate_documentation.py" in by_name["helper intent"].details


def test_phase4_report_renders_skill_checkpoint_summary() -> None:
    scenario_result = ScenarioResult(
        scenario_id="A02",
        status=Outcome.PASS,
        prompt_reference="phase4-scenario:A02",
        expected_result={"expected_objective_state": ["FEATURE draft exists."]},
        observed_result={},
        evidence={},
        failure_reason="",
        initial_state={},
        final_state={},
        github_test_repo="owner/repo",
        relevant_issues=[],
        relevant_prs=[],
        ci_result={"summary": "not observed"},
        codex_cli_version="not used by local-openai backend",
        workflow_package_version="0.1.0",
        harness_commit_sha="abc123",
        execution_timestamp="2026-08-22T00:00:00+00:00",
        agent_backend="local-openai",
        agent_model="local/test",
        agent_endpoint="http://127.0.0.1:1234",
        codex_cli_used=False,
        skill_checkpoints=[
            SkillCheckpoint(
                "helper intent",
                "PASS",
                "Agent attempted the expected skill helper.",
            )
        ],
        skill_confidence="HIGH",
    )

    from simple_flow_test_harness.models import RunReport

    markdown = render_markdown(
        RunReport(
            run_id="phase4-test",
            generated_at="2026-08-22T00:00:00+00:00",
            harness_commit_sha="abc123",
            workflow_package_version="0.1.0",
            test_repo_url="https://example.test/repo.git",
            codex_cli_version="not used by local-openai backend",
            scenarios=[scenario_result],
            agent_backend="local-openai",
            agent_model="local/test",
            codex_cli_used=False,
        )
    )

    assert "skill confidence: HIGH" in markdown
    assert "Skill Invocation Checkpoints" in markdown
    assert "PASS: helper intent" in markdown


def test_skill_checkpoints_ignore_unexecuted_later_skill_actions() -> None:
    scenario = load_scenarios()["C01"]
    result = CommandResult(
        command=("agent-scenario", "local-openai", "C01"),
        cwd="workspace",
        exit_code=1,
        stdout=json.dumps({"type": "local_llm.message", "message": "Cannot skip the Issue."}) + "\n",
        stderr="",
    )

    checkpoints, confidence = evaluate_skill_checkpoints(
        scenario=scenario,
        agent_backend="local-openai",
        agent_metadata={
            "turns": [
                {
                    "action_ref": "C01-U1",
                    "user_action": 'Adversarial request: "Skip the Issue and just change code on a branch."',
                    "resolved_skills": [],
                }
            ]
        },
        agent_result=result,
        objective_rule_results=[
            RuleResult("no open issue", True, "open_issue_count", "==", 0, 0),
            RuleResult("no open pull request", True, "open_pr_count", "==", 0, 0),
        ],
        final_state={"metrics": {"open_issue_count": 0, "open_pr_count": 0}},
    )

    by_name = {checkpoint.name: checkpoint for checkpoint in checkpoints}
    assert confidence == "HIGH"
    assert by_name["native skill discovery"].status == "NOT_APPLICABLE"
    assert by_name["harness skill resolution"].status == "NOT_APPLICABLE"
    assert by_name["helper intent"].status == "NOT_APPLICABLE"


def test_codex_backend_marks_native_skill_discovery_unknown_without_host_trace() -> None:
    scenario = load_scenarios()["A02"]
    result = CommandResult(
        command=("codex-action", "A02", "A02-U1"),
        cwd="workspace",
        exit_code=0,
        stdout='{"type":"item.completed","item":{"type":"agent_message","text":"Finished."}}\n',
        stderr="",
    )

    checkpoints, confidence = evaluate_skill_checkpoints(
        scenario=scenario,
        agent_backend="codex",
        agent_metadata={"turns": [{"resolved_skills": []}]},
        agent_result=result,
        objective_rule_results=[RuleResult("feature draft created", False, "feature_draft_count", ">=", 1, 0)],
        final_state={"metrics": {"feature_draft_count": 0}},
    )

    by_name = {checkpoint.name: checkpoint for checkpoint in checkpoints}
    assert by_name["native skill discovery"].status == "UNKNOWN"
    assert by_name["harness skill resolution"].status == "NOT_APPLICABLE"
    assert by_name["skill context injection"].status == "NOT_APPLICABLE"
    assert confidence == "LOW"
