from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Iterable

from simple_flow_phase4.assertions import evaluate_scenario
from simple_flow_phase4.commands import CommandFailure, run_command
from simple_flow_phase4.environment import Phase4Environment
from simple_flow_phase4.evidence import collect_state
from simple_flow_phase4.models import (
    CommandResult,
    Outcome,
    Phase4Config,
    RunReport,
    Scenario,
    ScenarioResult,
)
from simple_flow_phase4.scenarios import load_scenarios


class Phase4Runner:
    def __init__(self, config: Phase4Config):
        self.config = config
        self.environment = Phase4Environment(config)

    def run(self, scenario_ids: Iterable[str] | None = None) -> RunReport:
        scenarios = load_scenarios()
        selected_ids = list(scenario_ids or scenarios)
        unknown = [scenario_id for scenario_id in selected_ids if scenario_id not in scenarios]
        if unknown:
            raise ValueError(f"Unknown Phase 4 scenario IDs: {', '.join(unknown)}")

        generated_at = _now()
        run_id = "phase4-" + generated_at.replace(":", "").replace("-", "").replace("+", "z")
        harness_commit_sha = _git_value(self.config.source_root, ["git", "rev-parse", "HEAD"])
        workflow_package_version = _workflow_version(self.config.source_root)
        codex_cli_version = (
            "not run in dry-run mode"
            if self.config.dry_run
            else _command_version(self.config.codex_command, self.config.source_root)
        )

        if self.config.dry_run:
            results = [
                self._dry_run_result(
                    scenarios[scenario_id],
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
                for scenario_id in selected_ids
            ]
            return RunReport(
                run_id=run_id,
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                test_repo_url=self.config.test_repo_url,
                codex_cli_version=codex_cli_version,
                scenarios=results,
            )

        blockers, prerequisite_evidence = self.environment.prerequisite_evidence()
        if blockers:
            results = [
                self._blocked_result(
                    scenarios[scenario_id],
                    blockers=blockers,
                    evidence=prerequisite_evidence,
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
                for scenario_id in selected_ids
            ]
            return RunReport(
                run_id=run_id,
                generated_at=generated_at,
                harness_commit_sha=harness_commit_sha,
                workflow_package_version=workflow_package_version,
                test_repo_url=self.config.test_repo_url,
                codex_cli_version=codex_cli_version,
                scenarios=results,
            )

        results: list[ScenarioResult] = []
        for scenario_id in selected_ids:
            results.append(
                self._run_one(
                    scenarios[scenario_id],
                    generated_at=generated_at,
                    harness_commit_sha=harness_commit_sha,
                    workflow_package_version=workflow_package_version,
                    codex_cli_version=codex_cli_version,
                )
            )
        return RunReport(
            run_id=run_id,
            generated_at=generated_at,
            harness_commit_sha=harness_commit_sha,
            workflow_package_version=workflow_package_version,
            test_repo_url=self.config.test_repo_url,
            codex_cli_version=codex_cli_version,
            scenarios=results,
        )

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
            initial_state = collect_state(
                project_path=prepared.path,
                repo_full_name=prepared.repo_full_name,
                config=self.config,
            )
            codex_result = self._run_codex(prepared.path, scenario)
            final_state = collect_state(
                project_path=prepared.path,
                repo_full_name=prepared.repo_full_name,
                config=self.config,
                codex_result=codex_result,
            )
            status, rule_results, failure_reason = evaluate_scenario(scenario, final_state)
            diagnosis = _diagnose(status, failure_reason)
            evidence = {
                "setup_commands": [result.to_json_data() for result in prepared.setup_commands],
                "codex_command": codex_result.to_json_data(),
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
                objective_rule_results=rule_results,
                post_run_agentic_diagnosis=diagnosis,
            )
        except (CommandFailure, subprocess.TimeoutExpired, OSError) as exc:
            return self._blocked_result(
                scenario,
                blockers=[str(exc)],
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

    def _run_codex(self, project_path: Path, scenario: Scenario) -> CommandResult:
        output_path = self.config.workspace_root / f"{scenario.scenario_id}-last-message.txt"
        prompt = scenario.fixed_prompt(gh_path=self.config.gh_path, test_repo=self.config.test_repo_url)
        command = [
            self.config.codex_command,
            "exec",
            "--ephemeral",
            "--json",
            "--output-last-message",
            str(output_path),
            "-C",
            str(project_path),
        ]
        if self.config.codex_bypass_sandbox:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.append("--full-auto")
        command.append(prompt)
        result = run_command(
            command,
            cwd=project_path,
            timeout_seconds=self.config.timeout_seconds,
        )
        if output_path.exists():
            result = CommandResult(
                command=result.command,
                cwd=result.cwd,
                exit_code=result.exit_code,
                stdout=result.stdout + "\n\nLAST MESSAGE:\n" + output_path.read_text(encoding="utf-8"),
                stderr=result.stderr,
            )
        return result

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
            objective_rule_results=[],
            post_run_agentic_diagnosis={},
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
            failure_reason="; ".join(blockers),
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
            objective_rule_results=[],
            post_run_agentic_diagnosis=_diagnose(Outcome.BLOCKED, "; ".join(blockers)),
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
            objective_rule_results=[],
            post_run_agentic_diagnosis=_diagnose(Outcome.ERROR, str(error)),
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


def _command_version(command: str, cwd: Path) -> str:
    try:
        result = run_command([command, "--version"], cwd=cwd, timeout_seconds=30)
    except OSError as exc:
        return f"unavailable: {exc}"
    return (result.stdout or result.stderr).strip()


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


def _diagnose(status: Outcome, failure_reason: str) -> dict[str, str]:
    if status == Outcome.PASS:
        return {}
    if status == Outcome.BLOCKED:
        return {
            "Likely Cause": "External prerequisite or GitHub/Codex execution blocker.",
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
