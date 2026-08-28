from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Iterable

from simple_flow_test_harness.agent_backends import (
    CODEX_BACKEND,
    LOCAL_OPENAI_BACKEND,
    create_agent_backend,
)
from simple_flow_test_harness.assertions import evaluate_scenario
from simple_flow_test_harness.checkpoints import evaluate_skill_checkpoints
from simple_flow_test_harness.commands import CommandFailure, run_command
from simple_flow_test_harness.environment import Phase4Environment
from simple_flow_test_harness.evidence import collect_state
from simple_flow_test_harness.models import (
    CommandResult,
    Outcome,
    Phase4Config,
    PromptExchange,
    RunReport,
    Scenario,
    ScenarioResult,
)
from simple_flow_test_harness.scenarios import FULL_SUITE_SCENARIO_IDS, SMOKE_SCENARIO_IDS, load_scenarios
from simple_flow_test_harness.transcript import compact_codex_response, compact_fixture_prompt, compact_text


class Phase4Runner:
    def __init__(self, config: Phase4Config):
        self.config = config
        self.environment = Phase4Environment(config)
        self.agent_backend = create_agent_backend(config)

    def run(self, scenario_ids: Iterable[str] | None = None) -> RunReport:
        scenarios = load_scenarios()
        requested_ids = list(scenario_ids or scenarios)
        unknown = [scenario_id for scenario_id in requested_ids if scenario_id not in scenarios]
        if unknown:
            raise ValueError(f"Unknown Phase 4 scenario IDs: {', '.join(unknown)}")

        generated_at = _now()
        run_id = "phase4-" + generated_at.replace(":", "").replace("-", "").replace("+", "z")
        harness_commit_sha = _git_value(self.config.source_root, ["git", "rev-parse", "HEAD"])
        workflow_package_version = _workflow_version(self.config.source_root)
        codex_cli_version = self._codex_cli_version()

        if scenario_ids is None and self.config.smoke_only:
            return self._new_report(
                run_id=run_id,
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
                scenarios=self._run_selected(
                    [scenarios[scenario_id] for scenario_id in SMOKE_SCENARIO_IDS],
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                ),
                run_mode="smoke-only",
            )

        if scenario_ids is None and self.config.smoke_gate:
            smoke_results = self._run_selected(
                [scenarios[scenario_id] for scenario_id in SMOKE_SCENARIO_IDS],
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
            )
            skipped_reason = ""
            all_results = list(smoke_results)
            if all(result.status == Outcome.PASS for result in smoke_results):
                remaining_ids = [
                    scenario_id
                    for scenario_id in FULL_SUITE_SCENARIO_IDS
                    if scenario_id not in SMOKE_SCENARIO_IDS
                ]
                all_results.extend(
                    self._run_selected(
                        [scenarios[scenario_id] for scenario_id in remaining_ids],
                        generated_at=generated_at,
                        harness_commit_sha=harness_commit_sha,
                        workflow_package_version=workflow_package_version,
                        codex_cli_version=codex_cli_version,
                    )
                )
            else:
                skipped_reason = "Smoke gate did not pass; full Phase 4 suite was not run."
            return self._new_report(
                run_id=run_id,
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
                scenarios=all_results,
                run_mode="smoke-gated",
                full_suite_skipped_reason=skipped_reason,
            )

        run_mode = "selected" if scenario_ids is not None else "full"
        return self._new_report(
            run_id=run_id,
            generated_at=generated_at,
            harness_commit_sha=harness_commit_sha,
            workflow_package_version=workflow_package_version,
            codex_cli_version=codex_cli_version,
            scenarios=self._run_selected(
                [scenarios[scenario_id] for scenario_id in requested_ids],
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
            ),
            run_mode=run_mode,
        )

    def _run_selected(
        self,
        selected_scenarios: list[Scenario],
        *,
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
    ) -> list[ScenarioResult]:
        if self.config.dry_run:
            return [
                self._dry_run_result(
                    scenario,
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
                for scenario in selected_scenarios
            ]

        blockers, prerequisite_evidence = self.environment.prerequisite_evidence()
        backend_blockers, backend_evidence = self.agent_backend.prerequisite_evidence(
            source_root=self.config.source_root,
            timeout_seconds=self.config.timeout_seconds,
        )
        blockers.extend(backend_blockers)
        prerequisite_evidence.update(backend_evidence)
        if blockers:
            return [
                self._blocked_result(
                    scenario,
                    blockers=blockers,
                    evidence=prerequisite_evidence,
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
                for scenario in selected_scenarios
            ]

        results: list[ScenarioResult] = []
        for scenario in selected_scenarios:
            results.append(
                self._run_one(
                    scenario,
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
            )
        return results

    def _new_report(
        self,
        *,
        run_id: str,
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
        scenarios: list[ScenarioResult],
        run_mode: str,
        full_suite_skipped_reason: str = "",
    ) -> RunReport:
        return RunReport(
            run_id=run_id,
            generated_at=generated_at,
            harness_commit_sha=harness_commit_sha,
            workflow_package_version=workflow_package_version,
            test_repo_url=self.config.test_repo_url,
            codex_cli_version=codex_cli_version,
            scenarios=scenarios,
            run_mode=run_mode,
            smoke_scenario_ids=list(SMOKE_SCENARIO_IDS),
            full_suite_skipped_reason=full_suite_skipped_reason,
            timeout_seconds=self.config.timeout_seconds,
            codex_model=self.config.codex_model,
            agent_backend=self.config.agent_backend,
            agent_model=_agent_model(self.config),
            agent_endpoint=_agent_endpoint(self.config),
            codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
        )

    def _codex_cli_version(self) -> str:
        if self.config.agent_backend != CODEX_BACKEND:
            return self.agent_backend.version_label(source_root=self.config.source_root)
        if self.config.dry_run:
            return "not run in dry-run mode"
        return self.agent_backend.version_label(source_root=self.config.source_root)

    def _run_one(
        self,
        scenario: Scenario,
        *,
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
    ) -> ScenarioResult:
        try:
            prepared = self.environment.prepare_scenario_project(scenario.scenario_id)
            scenario_fixtures = _apply_scenario_fixtures(prepared.path, scenario)
            initial_state = collect_state(
                project_path=prepared.path,
                repo_full_name=prepared.repo_full_name,
                config=self.config,
            )
            agent_result, prompt_exchange, agent_metadata = self._run_agent(
                prepared.path,
                prepared.repo_full_name,
                scenario,
            )
            final_state = collect_state(
                project_path=prepared.path,
                repo_full_name=prepared.repo_full_name,
                config=self.config,
                agent_result=agent_result,
                codex_result=agent_result if self.config.agent_backend == CODEX_BACKEND else None,
            )
            _add_delta_metrics(initial_state, final_state)
            infrastructure_blocker = _agent_infrastructure_blocker(agent_result, self.config.agent_backend)
            if infrastructure_blocker:
                checkpoints, confidence = evaluate_skill_checkpoints(
                    scenario=scenario,
                    agent_backend=self.config.agent_backend,
                    agent_metadata=agent_metadata,
                    agent_result=agent_result,
                    objective_rule_results=[],
                    final_state=final_state,
                )
                evidence = {
                    "setup_commands": [result.to_json_data() for result in prepared.setup_commands],
                    "scenario_fixtures": scenario_fixtures,
                    "agent_backend": agent_metadata,
                    "agent_result": agent_result.to_json_data(),
                    "codex_command": agent_result.to_json_data()
                    if self.config.agent_backend == CODEX_BACKEND
                    else None,
                    "harness_worktree_dirty": _worktree_dirty(self.config.source_root),
                }
                return ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    status=Outcome.BLOCKED,
                    prompt_reference=scenario.prompt_reference,
                    expected_result=scenario.to_json_data(),
                    observed_result=final_state.get("metrics", {}),
                    evidence=evidence,
                    failure_reason=infrastructure_blocker,
                    initial_state=initial_state,
                    final_state=final_state,
                    github_test_repo=prepared.repo_full_name,
                    relevant_issues=final_state.get("github", {}).get("issues", []),
                    relevant_prs=final_state.get("github", {}).get("pull_requests", []),
                    ci_result=_ci_summary(final_state),
                    codex_cli_version=codex_cli_version,
                    workflow_package_version=workflow_package_version,
                    harness_commit_sha=harness_commit_sha,
                    execution_timestamp=_now(),
                    agent_backend=self.config.agent_backend,
                    agent_model=_agent_model(self.config),
                    agent_endpoint=_agent_endpoint(self.config),
                    codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
                    objective_rule_results=[],
                    skill_checkpoints=checkpoints,
                    skill_confidence=confidence,
                    post_run_agentic_diagnosis=_diagnose(Outcome.BLOCKED, infrastructure_blocker),
                    prompt_exchange=prompt_exchange,
                )
            status, rule_results, failure_reason = evaluate_scenario(scenario, final_state)
            diagnosis = _diagnose(status, failure_reason)
            checkpoints, confidence = evaluate_skill_checkpoints(
                scenario=scenario,
                agent_backend=self.config.agent_backend,
                agent_metadata=agent_metadata,
                agent_result=agent_result,
                objective_rule_results=rule_results,
                final_state=final_state,
            )
            evidence = {
                "setup_commands": [result.to_json_data() for result in prepared.setup_commands],
                "scenario_fixtures": scenario_fixtures,
                "agent_backend": agent_metadata,
                "agent_result": agent_result.to_json_data(),
                "codex_command": agent_result.to_json_data()
                if self.config.agent_backend == CODEX_BACKEND
                else None,
                "harness_worktree_dirty": _worktree_dirty(self.config.source_root),
            }
            return ScenarioResult(
                scenario_id=scenario.scenario_id,
                status=status,
                prompt_reference=scenario.prompt_reference,
                expected_result=scenario.to_json_data(),
                observed_result=final_state.get("metrics", {}),
                evidence=evidence,
                failure_reason=failure_reason,
                initial_state=initial_state,
                final_state=final_state,
                github_test_repo=prepared.repo_full_name,
                relevant_issues=final_state.get("github", {}).get("issues", []),
                relevant_prs=final_state.get("github", {}).get("pull_requests", []),
                ci_result=_ci_summary(final_state),
                codex_cli_version=codex_cli_version,
                workflow_package_version=workflow_package_version,
                harness_commit_sha=harness_commit_sha,
                execution_timestamp=_now(),
                agent_backend=self.config.agent_backend,
                agent_model=_agent_model(self.config),
                agent_endpoint=_agent_endpoint(self.config),
                codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
                objective_rule_results=rule_results,
                skill_checkpoints=checkpoints,
                skill_confidence=confidence,
                post_run_agentic_diagnosis=diagnosis,
                prompt_exchange=prompt_exchange,
            )
        except (CommandFailure, subprocess.TimeoutExpired, OSError) as exc:
            return self._blocked_result(
                scenario,
                blockers=[compact_text(str(exc))],
                evidence={"exception": type(exc).__name__},
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
            )
        except Exception as exc:
            return self._error_result(
                scenario,
                error=exc,
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                codex_cli_version=codex_cli_version,
            )
        finally:
            if not self.config.keep_workspace:
                scenario_path = self.config.workspace_root / scenario.scenario_id
                if scenario_path.exists():
                    self.environment._safe_reset_local_workspace(scenario_path)

    def _run_agent(
        self,
        project_path: Path,
        repo_full_name: str,
        scenario: Scenario,
    ) -> tuple[CommandResult, list[PromptExchange], dict[str, object]]:
        session_id = ""
        results: list[tuple[str, CommandResult]] = []
        exchanges: list[PromptExchange] = []
        turns: list[dict[str, object]] = []
        variables: dict[str, str] = {}

        for step in scenario.ordered_steps:
            if step.step_type.value != "USER_ACTION":
                continue
            variables.update(_mechanical_variables(project_path, repo_full_name, self.config))
            action_text = _substitute_variables(step.text, variables)
            prompt = _user_action_prompt(
                scenario=scenario,
                action_ref=step.ref,
                action_text=action_text,
                first_action=not session_id,
                gh_path=self.config.gh_path,
                test_repo=self.config.test_repo_url,
            )
            turn = self.agent_backend.run_action(
                project_path=project_path,
                prompt=prompt,
                session_id=session_id,
                scenario_id=scenario.scenario_id,
                action_ref=step.ref,
                timeout_seconds=self.config.timeout_seconds,
            )
            result = turn.command_result
            exchanges.append(
                PromptExchange(
                    action_ref=step.ref,
                    fixture_prompt=compact_fixture_prompt(prompt),
                    response_received=compact_codex_response(result.stdout, result.stderr, result.exit_code),
                )
            )
            results.append((step.ref, result))
            turns.append({"action_ref": step.ref, "user_action": action_text, **turn.metadata})
            session_id = turn.session_id or session_id
            if result.exit_code != 0:
                break

        exit_code = _combined_agent_exit_code(results)
        stdout = "\n\n".join(
            f"=== {ref} STDOUT ===\n{result.stdout}" for ref, result in results
        )
        stderr = "\n\n".join(
            f"=== {ref} STDERR ===\n{result.stderr}" for ref, result in results if result.stderr
        )
        return CommandResult(
            command=("agent-scenario", self.config.agent_backend, scenario.scenario_id),
            cwd=str(project_path),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        ), exchanges, {
            "backend": self.config.agent_backend,
            "model": _agent_model(self.config),
            "endpoint": _agent_endpoint(self.config),
            "codex_cli_used": self.config.agent_backend == CODEX_BACKEND,
            "turns": turns,
        }

    def _dry_run_result(
        self,
        scenario: Scenario,
        *,
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
    ) -> ScenarioResult:
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            status=Outcome.NOT_RUN,
            prompt_reference=scenario.prompt_reference,
            expected_result=scenario.to_json_data(),
            observed_result={},
            evidence={"dry_run": True},
            failure_reason="Dry run validates definitions and report generation only.",
            initial_state={},
            final_state={},
            github_test_repo=self.environment.repo,
            relevant_issues=[],
            relevant_prs=[],
            ci_result={"summary": "not run"},
            codex_cli_version=codex_cli_version,
            workflow_package_version=workflow_package_version,
            harness_commit_sha=harness_commit_sha,
            execution_timestamp=generated_at,
            agent_backend=self.config.agent_backend,
            agent_model=_agent_model(self.config),
            agent_endpoint=_agent_endpoint(self.config),
            codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
            objective_rule_results=[],
            post_run_agentic_diagnosis={},
            prompt_exchange=_dry_run_exchanges(
                scenario,
                gh_path=self.config.gh_path,
                test_repo=self.config.test_repo_url,
                agent_backend=self.config.agent_backend,
            ),
        )

    def _blocked_result(
        self,
        scenario: Scenario,
        *,
        blockers: list[str],
        evidence: dict[str, object],
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
    ) -> ScenarioResult:
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            status=Outcome.BLOCKED,
            prompt_reference=scenario.prompt_reference,
            expected_result=scenario.to_json_data(),
            observed_result={},
            evidence=evidence,
            failure_reason="; ".join(compact_text(blocker) for blocker in blockers),
            initial_state={},
            final_state={},
            github_test_repo=self.environment.repo,
            relevant_issues=[],
            relevant_prs=[],
            ci_result={"summary": "blocked before CI observation"},
            codex_cli_version=codex_cli_version,
            workflow_package_version=workflow_package_version,
            harness_commit_sha=harness_commit_sha,
            execution_timestamp=generated_at,
            agent_backend=self.config.agent_backend,
            agent_model=_agent_model(self.config),
            agent_endpoint=_agent_endpoint(self.config),
            codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
            objective_rule_results=[],
            post_run_agentic_diagnosis=_diagnose(
                Outcome.BLOCKED,
                "; ".join(compact_text(blocker) for blocker in blockers),
            ),
            prompt_exchange=[],
        )

    def _error_result(
        self,
        scenario: Scenario,
        *,
        error: Exception,
        generated_at: str,
        harness_commit_sha: str,
        workflow_package_version: str,
        codex_cli_version: str,
    ) -> ScenarioResult:
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            status=Outcome.ERROR,
            prompt_reference=scenario.prompt_reference,
            expected_result=scenario.to_json_data(),
            observed_result={},
            evidence={"exception": type(error).__name__},
            failure_reason=str(error),
            initial_state={},
            final_state={},
            github_test_repo=self.environment.repo,
            relevant_issues=[],
            relevant_prs=[],
            ci_result={"summary": "harness error before CI observation"},
            codex_cli_version=codex_cli_version,
            workflow_package_version=workflow_package_version,
            harness_commit_sha=harness_commit_sha,
            execution_timestamp=generated_at,
            agent_backend=self.config.agent_backend,
            agent_model=_agent_model(self.config),
            agent_endpoint=_agent_endpoint(self.config),
            codex_cli_used=self.config.agent_backend == CODEX_BACKEND,
            objective_rule_results=[],
            post_run_agentic_diagnosis=_diagnose(Outcome.ERROR, str(error)),
            prompt_exchange=[],
        )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_value(root: Path, command: list[str]) -> str:
    result = run_command(command, cwd=root, timeout_seconds=30)
    return (result.stdout or result.stderr).strip()


def _workflow_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def _worktree_dirty(root: Path) -> bool:
    result = run_command(["git", "status", "--porcelain"], cwd=root, timeout_seconds=30)
    return bool(result.stdout.strip())


def _ci_summary(state: dict[str, object]) -> dict[str, object]:
    prs = state.get("github", {}).get("pull_requests", []) if isinstance(state.get("github"), dict) else []
    rollups = []
    for pr in prs:
        if isinstance(pr, dict):
            rollups.append(
                {
                    "number": pr.get("number"),
                    "statusCheckRollup": pr.get("statusCheckRollup"),
                    "reviewDecision": pr.get("reviewDecision"),
                }
            )
    return {
        "summary": "observed" if rollups else "not observed",
        "pull_request_checks": rollups,
    }


def _add_delta_metrics(initial_state: dict[str, object], final_state: dict[str, object]) -> None:
    initial_github = initial_state.get("github", {})
    final_github = final_state.get("github", {})
    if not isinstance(initial_github, dict) or not isinstance(final_github, dict):
        return

    initial_issue_numbers = _number_set(initial_github.get("issues", []))
    initial_pr_numbers = _number_set(initial_github.get("pull_requests", []))
    new_issues = [
        issue
        for issue in _dict_items(final_github.get("issues", []))
        if _item_number(issue) not in initial_issue_numbers
    ]
    new_prs = [
        pr
        for pr in _dict_items(final_github.get("pull_requests", []))
        if _item_number(pr) not in initial_pr_numbers
    ]
    metrics = final_state.setdefault("metrics", {})
    if not isinstance(metrics, dict):
        return
    metrics.update(
        {
            "new_issue_count": len(new_issues),
            "new_open_issue_count": len([issue for issue in new_issues if issue.get("state") == "OPEN"]),
            "new_closed_issue_count": len([issue for issue in new_issues if issue.get("state") == "CLOSED"]),
            "new_pr_count": len(new_prs),
            "new_open_pr_count": len([pr for pr in new_prs if pr.get("state") == "OPEN"]),
            "new_draft_pr_count": len([pr for pr in new_prs if pr.get("isDraft")]),
            "new_merged_pr_count": len(
                [pr for pr in new_prs if pr.get("state") == "MERGED" or pr.get("mergedAt")]
            ),
        }
    )
    final_github["new_issues"] = new_issues
    final_github["new_pull_requests"] = new_prs


def _number_set(items: object) -> set[int]:
    return {number for number in (_item_number(item) for item in _dict_items(items)) if number is not None}


def _dict_items(items: object) -> list[dict[str, object]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _item_number(item: object) -> int | None:
    if not isinstance(item, dict) or "number" not in item:
        return None
    try:
        return int(item["number"])
    except (TypeError, ValueError):
        return None


def _apply_scenario_fixtures(project_path: Path, scenario: Scenario) -> list[dict[str, object]]:
    applied: list[dict[str, object]] = []
    for fixture in scenario.fixture_files:
        relative_path = Path(fixture.relative_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Unsafe Phase 4 file fixture path: {fixture.relative_path}")
        fixture_path = project_path / relative_path
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(fixture.content, encoding="utf-8")
        applied.append(
            {
                "type": "file",
                "relative_path": fixture.relative_path,
            }
        )

    if not scenario.fixture_draft:
        return applied

    from simple_flow_agent.drafts import DraftStore

    fixture = scenario.fixture_draft
    if fixture.work_type != "DOCUMENTATION":
        raise ValueError(f"Unsupported Phase 4 draft fixture work type: {fixture.work_type}")

    fields = fixture.fields
    store = DraftStore(project_path / ".simple-flow" / "drafts")
    draft = store.create_documentation(
        change=str(fields["Change"]),
        reason=str(fields["Reason"]),
        impact=str(fields["Impact"]),
        supersedes=str(fields["Supersedes"]),
        affected_project_documents=_fixture_list(fields["Affected Project Documents"]),
        source_context=str(fields["Source PR / Decision Context"]),
        source_issue=fixture.source_issue,
        source_pr=fixture.source_pr,
    )
    applied.append(
        {
            "type": "canonical_draft",
            "draft_id": draft.draft_id,
            "work_type": draft.work_type,
            "fields": draft.fields,
        }
    )
    return applied


def _fixture_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [
        line.strip().removeprefix("-").strip()
        for line in str(value).splitlines()
        if line.strip()
    ]


def _user_action_prompt(
    *,
    scenario: Scenario,
    action_ref: str,
    action_text: str,
    first_action: bool,
    gh_path: str,
    test_repo: str,
) -> str:
    prefix = (
        "Start a new isolated Phase 4 scenario session."
        if first_action
        else "Continue the same isolated Phase 4 scenario session."
    )
    return (
        f"USER_ACTION TO EXECUTE NOW: {action_text}\n"
        "This is a human-supplied workflow action. Execute this action now; do not ask for the action again.\n\n"
        f"{prefix}\n"
        "Execute exactly this one fixed USER_ACTION. Do not execute future USER_ACTIONs until they are sent in a later turn.\n"
        "Do not ask what to do next. Stop when the invoked skill stage says STOP.\n"
        "The harness will perform OBSERVE and ASSERT steps after the agent turn exits; do not decide PASS or FAIL.\n"
        "Run in this test project only and use AGENTS.md plus installed agent skills as workflow truth.\n"
        "@documentation-curation -> documentation-curation/SKILL.md; "
        "@issue-draft -> issue-draft/SKILL.md; "
        "@start-implement -> start-implement/SKILL.md; "
        "@review-triage -> review-triage/SKILL.md; "
        "@pr-finalize -> pr-finalize/SKILL.md. "
        "In the current deployed test layout, these skill files live under .codex/skills/<skill>/SKILL.md.\n"
        f"Use this GitHub CLI executable for GitHub operations: {gh_path}\n"
        f"GitHub test repository: {test_repo}\n"
        f"Scenario ID: {scenario.scenario_id}\n"
        f"Scenario Purpose: {scenario.purpose}\n"
        f"Action Reference: {action_ref}\n"
    )


def _dry_run_exchanges(
    scenario: Scenario,
    *,
    gh_path: str,
    test_repo: str,
    agent_backend: str = CODEX_BACKEND,
) -> list[PromptExchange]:
    exchanges: list[PromptExchange] = []
    first_action = True
    for step in scenario.ordered_steps:
        if step.step_type.value != "USER_ACTION":
            continue
        prompt = _user_action_prompt(
            scenario=scenario,
            action_ref=step.ref,
            action_text=step.text,
            first_action=first_action,
            gh_path=gh_path,
            test_repo=test_repo,
        )
        exchanges.append(
            PromptExchange(
                action_ref=step.ref,
                fixture_prompt=compact_fixture_prompt(prompt),
                response_received=compact_codex_response(
                    "",
                    f"Dry run; {agent_backend} backend was not invoked.",
                    None,
                ),
            )
        )
        first_action = False
    return exchanges


def _substitute_variables(text: str, variables: dict[str, str]) -> str:
    for name, value in variables.items():
        text = text.replace("{{" + name + "}}", value)
    return text


def _mechanical_variables(project_path: Path, repo_full_name: str, config: Phase4Config) -> dict[str, str]:
    variables: dict[str, str] = {
        "gh_path": config.gh_path,
        "test_repo": config.test_repo_url,
    }
    drafts_dir = project_path / ".simple-flow" / "drafts"
    draft_ids = sorted(path.stem for path in drafts_dir.glob("DRAFT-*.json")) if drafts_dir.exists() else []
    if draft_ids:
        variables["draft_id"] = draft_ids[-1]

    issues = _gh_json(
        [
            config.gh_path,
            "issue",
            "list",
            "--repo",
            repo_full_name,
            "--state",
            "all",
            "--json",
            "number",
            "--limit",
            "100",
        ],
        project_path,
    )
    if issues:
        variables["issue_number"] = str(max(int(item["number"]) for item in issues if "number" in item))

    prs = _gh_json(
        [
            config.gh_path,
            "pr",
            "list",
            "--repo",
            repo_full_name,
            "--state",
            "all",
            "--json",
            "number,headRefName",
            "--limit",
            "100",
        ],
        project_path,
    )
    if prs:
        latest_pr = max((item for item in prs if "number" in item), key=lambda item: int(item["number"]))
        variables["pr_number"] = str(latest_pr["number"])
        if latest_pr.get("headRefName"):
            variables["branch_name"] = str(latest_pr["headRefName"])
    return variables


def _gh_json(command: list[str], cwd: Path) -> list[dict[str, object]]:
    result = run_command(command, cwd=cwd, timeout_seconds=60)
    if result.exit_code != 0 or not result.stdout.strip():
        return []
    data = json.loads(result.stdout)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _combined_agent_exit_code(results: list[tuple[str, CommandResult]]) -> int:
    if any(result.exit_code == 124 for _, result in results):
        return 124
    if all(result.exit_code == 0 for _, result in results):
        return 0
    return 1


def _combined_codex_exit_code(results: list[tuple[str, CommandResult]]) -> int:
    return _combined_agent_exit_code(results)


def _agent_infrastructure_blocker(result: CommandResult, backend: str) -> str:
    if backend == LOCAL_OPENAI_BACKEND:
        return _local_openai_infrastructure_blocker(result)
    return _codex_infrastructure_blocker(result)


def _codex_infrastructure_blocker(result: CommandResult) -> str:
    if result.exit_code == 0:
        return ""
    if result.exit_code == 124:
        return "Codex CLI infrastructure blocker: timed out"
    output = f"{result.stdout}\n{result.stderr}".lower()
    markers = (
        "requires a newer version of codex",
        "failed to refresh available models",
        "failed to load models cache",
        "no last agent message",
        "timed out",
    )
    for marker in markers:
        if marker in output:
            return "Codex CLI infrastructure blocker: " + marker
    return ""


def _local_openai_infrastructure_blocker(result: CommandResult) -> str:
    if result.exit_code == 0:
        return ""
    if result.exit_code == 124:
        return "Local OpenAI-compatible backend infrastructure blocker: timed out"
    output = f"{result.stdout}\n{result.stderr}".lower()
    markers = (
        "local openai backend error",
        "local openai-compatible backend unavailable",
        "connection refused",
        "timed out",
        "http 400",
        "http 401",
        "http 404",
        "http 500",
    )
    for marker in markers:
        if marker in output:
            return "Local OpenAI-compatible backend infrastructure blocker: " + marker
    return ""


def _agent_model(config: Phase4Config) -> str | None:
    if config.agent_backend == LOCAL_OPENAI_BACKEND:
        return config.local_llm_model
    return config.codex_model


def _agent_endpoint(config: Phase4Config) -> str:
    if config.agent_backend == LOCAL_OPENAI_BACKEND:
        return config.local_llm_url
    if config.codex_oss:
        return f"codex-oss:{config.codex_local_provider or 'configured-local-provider'}"
    return ""


def _diagnose(status: Outcome, failure_reason: str) -> dict[str, str]:
    if status == Outcome.PASS:
        return {}
    if status == Outcome.BLOCKED:
        return {
            "Likely Cause": "External prerequisite or GitHub/agent backend execution blocker.",
            "Suspected Source": failure_reason,
            "Recommended Fix": "Resolve the blocker, then rerun the same fixed scenario without changing scenario expectations.",
            "Rerun Recommendation": "Rerun after the external condition changes.",
        }
    if status == Outcome.ERROR:
        return {
            "Likely Cause": "Harness implementation failed before objective scenario judgment.",
            "Suspected Source": failure_reason,
            "Recommended Fix": "Fix harness code and rerun the same fixed scenario.",
            "Rerun Recommendation": "Required because ERROR is not a system-under-test result.",
        }
    return {
        "Likely Cause": "Observed objective state did not satisfy the fixed Phase 4 scenario rules.",
        "Suspected Source": failure_reason,
        "Recommended Fix": "Inspect objective evidence, adjust Simple Flow source behavior if needed, then rerun the same fixed scenario.",
        "Rerun Recommendation": "Required after any source change affecting workflow or harness logic.",
    }
