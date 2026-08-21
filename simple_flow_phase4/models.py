from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class StepType(StrEnum):
    USER_ACTION = "USER_ACTION"
    OBSERVE = "OBSERVE"
    ASSERT = "ASSERT"


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class ScenarioStep:
    step_type: StepType
    text: str
    ref: str

    def to_prompt_line(self) -> str:
        return f"{self.step_type.value}: {self.text}"

    def to_json_data(self) -> dict[str, str]:
        return {
            "type": self.step_type.value,
            "ref": self.ref,
            "text": self.text,
        }


@dataclass(frozen=True)
class AssertionRule:
    name: str
    metric: str
    operator: str
    expected: Any
    success_if_blocked: bool = False

    def to_json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric": self.metric,
            "operator": self.operator,
            "expected": self.expected,
            "success_if_blocked": self.success_if_blocked,
        }


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    group: str
    purpose: str
    initial_state: str
    ordered_steps: tuple[ScenarioStep, ...]
    expected_objective_state: tuple[str, ...]
    forbidden_state: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    pass_rules: tuple[AssertionRule, ...]
    cleanup_requirements: tuple[str, ...]

    @property
    def prompt_reference(self) -> str:
        return f"phase4-scenario:{self.scenario_id}"

    def fixed_prompt(self, *, gh_path: str, test_repo: str) -> str:
        steps = "\n".join(f"{index}. {step.to_prompt_line()}" for index, step in enumerate(self.ordered_steps, 1))
        expected = "\n".join(f"- {item}" for item in self.expected_objective_state)
        forbidden = "\n".join(f"- {item}" for item in self.forbidden_state)
        return (
            "Execute this Simple Flow Phase 4 scenario now. This is the complete user request, not a setup message.\n"
            "Do not reply with readiness, an acknowledgement, or a request for another task.\n"
            "You are the Agent Under Test for the Simple Flow Phase 4 experiment.\n"
            "Run in this test project only. Do not use any context from the main project task.\n"
            "Use the installed project files, AGENTS.md, and .codex skills as the source of workflow truth.\n"
            "Skill aliases in USER_ACTION lines map to installed skills: "
            "@discussion -> .codex/skills/discussion/SKILL.md; "
            "@issue-draft -> .codex/skills/issue-draft/SKILL.md; "
            "@start-implement -> .codex/skills/start-implement/SKILL.md; "
            "@review-triage -> .codex/skills/review-triage/SKILL.md; "
            "@pr-finalize -> .codex/skills/pr-finalize/SKILL.md.\n"
            "When a USER_ACTION names a skill alias, read the mapped SKILL.md and perform that skill's responsibilities; do not merely describe the stage.\n"
            "Use the GitHub CLI only through this exact executable path when a GitHub operation is needed:\n"
            f"{gh_path}\n"
            f"The GitHub test repository is {test_repo}.\n"
            "Do not ask the main harness for feedback during this scenario. If a Simple Flow stage says STOP, stop.\n"
            "Do not decide PASS or FAIL; the harness will do that from objective state after you exit.\n\n"
            f"Scenario ID: {self.scenario_id}\n"
            f"Purpose: {self.purpose}\n"
            f"Initial State: {self.initial_state}\n\n"
            "Begin immediately. Treat every USER_ACTION below as an already-supplied human message.\n"
            "Execute USER_ACTION lines in order in this single isolated session. OBSERVE and ASSERT lines are for you to inspect relevant state, not to decide final PASS/FAIL.\n"
            "Do not ask what to do next.\n\n"
            "Fixed Ordered Steps:\n"
            f"{steps}\n\n"
            "Expected Objective State:\n"
            f"{expected}\n\n"
            "Forbidden State:\n"
            f"{forbidden}\n"
        )

    def to_json_data(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "group": self.group,
            "purpose": self.purpose,
            "initial_state": self.initial_state,
            "ordered_steps": [step.to_json_data() for step in self.ordered_steps],
            "expected_objective_state": list(self.expected_objective_state),
            "forbidden_state": list(self.forbidden_state),
            "evidence_sources": list(self.evidence_sources),
            "pass_rules": [rule.to_json_data() for rule in self.pass_rules],
            "cleanup_requirements": list(self.cleanup_requirements),
            "prompt_reference": self.prompt_reference,
        }


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str

    def to_json_data(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass
class RuleResult:
    name: str
    passed: bool
    metric: str
    operator: str
    expected: Any
    actual: Any
    reason: str = ""

    def to_json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "metric": self.metric,
            "operator": self.operator,
            "expected": self.expected,
            "actual": self.actual,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PromptExchange:
    action_ref: str
    fixture_prompt: dict[str, str]
    response_received: dict[str, Any]

    def to_json_data(self) -> dict[str, Any]:
        return {
            "action_ref": self.action_ref,
            "fixture_prompt": self.fixture_prompt,
            "response_received": self.response_received,
        }


@dataclass
class ScenarioResult:
    scenario_id: str
    status: Outcome
    prompt_reference: str
    expected_result: dict[str, Any]
    observed_result: dict[str, Any]
    evidence: dict[str, Any]
    failure_reason: str
    initial_state: dict[str, Any]
    final_state: dict[str, Any]
    github_test_repo: str
    relevant_issues: list[dict[str, Any]]
    relevant_prs: list[dict[str, Any]]
    ci_result: dict[str, Any]
    codex_cli_version: str
    workflow_package_version: str
    harness_commit_sha: str
    execution_timestamp: str
    objective_rule_results: list[RuleResult] = field(default_factory=list)
    post_run_agentic_diagnosis: dict[str, Any] = field(default_factory=dict)
    prompt_exchange: list[PromptExchange] = field(default_factory=list)

    def to_json_data(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "prompt_reference": self.prompt_reference,
            "expected_result": self.expected_result,
            "observed_result": self.observed_result,
            "evidence": self.evidence,
            "status": self.status.value,
            "failure_reason": self.failure_reason,
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "github_test_repo": self.github_test_repo,
            "relevant_issues": self.relevant_issues,
            "relevant_prs": self.relevant_prs,
            "ci_result": self.ci_result,
            "codex_cli_version": self.codex_cli_version,
            "workflow_package_version": self.workflow_package_version,
            "harness_commit_sha": self.harness_commit_sha,
            "execution_timestamp": self.execution_timestamp,
            "objective_rule_results": [
                result.to_json_data() for result in self.objective_rule_results
            ],
            "post_run_agentic_diagnosis": self.post_run_agentic_diagnosis,
            "prompt_exchange": [exchange.to_json_data() for exchange in self.prompt_exchange],
        }


@dataclass(frozen=True)
class Phase4Config:
    source_root: Path
    workspace_root: Path
    report_dir: Path
    test_repo_url: str
    gh_path: str
    codex_command: str
    timeout_seconds: int
    allow_remote_reset: bool
    dry_run: bool = False
    keep_workspace: bool = False
    codex_bypass_sandbox: bool = False
    codex_model: str | None = None
    smoke_gate: bool = True
    smoke_only: bool = False


@dataclass
class RunReport:
    run_id: str
    generated_at: str
    harness_commit_sha: str
    workflow_package_version: str
    test_repo_url: str
    codex_cli_version: str
    scenarios: list[ScenarioResult]
    run_mode: str = "direct"
    smoke_scenario_ids: list[str] = field(default_factory=list)
    full_suite_skipped_reason: str = ""
    timeout_seconds: int = 0
    codex_model: str | None = None

    def status_counts(self) -> dict[str, int]:
        counts = {outcome.value: 0 for outcome in Outcome}
        for result in self.scenarios:
            counts[result.status.value] += 1
        return counts

    @property
    def overall_status(self) -> Outcome:
        counts = self.status_counts()
        if counts[Outcome.ERROR.value]:
            return Outcome.ERROR
        if counts[Outcome.FAIL.value]:
            return Outcome.FAIL
        if counts[Outcome.BLOCKED.value]:
            return Outcome.BLOCKED
        if counts[Outcome.NOT_RUN.value]:
            return Outcome.NOT_RUN
        return Outcome.PASS

    def to_json_data(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "harness_commit_sha": self.harness_commit_sha,
            "workflow_package_version": self.workflow_package_version,
            "test_repo_url": self.test_repo_url,
            "codex_cli_version": self.codex_cli_version,
            "run_mode": self.run_mode,
            "smoke_scenario_ids": self.smoke_scenario_ids,
            "full_suite_skipped_reason": self.full_suite_skipped_reason,
            "timeout_seconds": self.timeout_seconds,
            "codex_model": self.codex_model,
            "overall_status": self.overall_status.value,
            "status_counts": self.status_counts(),
            "scenarios": [result.to_json_data() for result in self.scenarios],
        }
