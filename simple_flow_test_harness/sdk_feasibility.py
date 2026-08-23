"""Small, host-neutral Phase 4 SDK feasibility pilot.

The pilot deliberately does not emulate a coding-agent harness.  It drives a
real Codex or Claude SDK and asks the host to use the skills already installed
in the supplied test project.  Scenario prompts remain ordinary developer
requests; setup, fixtures, structured output and observations stay outside the
prompt.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Protocol


SDK_HOSTS = ("codex-sdk", "claude-sdk")
DEFAULT_LIVENESS_SECONDS = 60
REMOTE_CLEANUP_NOTE = "Closed by Simple Flow Phase 4 SDK cleanup."


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class TestClass(StrEnum):
    DETERMINISTIC = "deterministic"
    AGENT_CAPABILITY = "agent-capability"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class Checkpoint:
    name: str
    test_class: TestClass
    purpose: str
    confidence_eligible: bool = False


CHECKPOINTS = (
    Checkpoint("local_route", TestClass.INFRASTRUCTURE, "SDK is configured for the selected local endpoint."),
    Checkpoint("prompt_fidelity", TestClass.DETERMINISTIC, "The SDK received the unchanged developer prompt."),
    Checkpoint("structured_result", TestClass.DETERMINISTIC, "The SDK adapter emitted a complete machine-readable turn record."),
    Checkpoint("host_trace", TestClass.DETERMINISTIC, "The SDK emitted trace events usable as evidence."),
    Checkpoint("skill_invocation", TestClass.DETERMINISTIC, "The requested skill was attached through the host SDK."),
    Checkpoint("precondition", TestClass.DETERMINISTIC, "The framework established and validated the scenario prerequisites."),
    Checkpoint("objective_state", TestClass.DETERMINISTIC, "Observed project state satisfies the scenario oracle."),
    Checkpoint("remote_state", TestClass.DETERMINISTIC, "Remote repository evidence satisfies the scenario manifest."),
    Checkpoint("remote_cleanup", TestClass.DETERMINISTIC, "Run-owned remote artifacts were removed and cleanup was verified."),
    Checkpoint("workflow_outcome", TestClass.AGENT_CAPABILITY, "The agent produced the required skill outcome.", True),
    Checkpoint("stop_boundary", TestClass.AGENT_CAPABILITY, "The agent stopped at the required workflow boundary.", True),
)


class CIExpectation(StrEnum):
    IGNORE = "ignore"
    PRESENT = "present"
    SUCCESS = "success"


@dataclass(frozen=True)
class Fixture:
    relative_path: str
    content: str
    attach_to_turn: bool = False
    label: str = "approved Canonical Draft input"


@dataclass(frozen=True)
class RemoteExpectation:
    """Fixed, deterministic references for a remote skill outcome.

    Values that depend on GitHub allocation are deliberately expressed as a
    relationship to the new Issue number, not guessed before the run.
    """

    issue_title: str
    branch_template: str
    pr_title: str
    base_branch: str
    pr_draft: bool
    pr_merged: bool
    exact_files: tuple[tuple[str, str], ...]
    ci_expectation: CIExpectation = CIExpectation.IGNORE

    def branch_for_issue(self, issue_number: int) -> str:
        return self.branch_template.format(issue_number=issue_number)


@dataclass(frozen=True)
class PilotScenario:
    scenario_id: str
    goal: str
    prompt: str
    expected: tuple[str, ...]
    required_skill: str | None
    requires_stop: bool
    fixtures: tuple[Fixture, ...] = ()
    remote_expectation: RemoteExpectation | None = None


PILOT_SCENARIOS = (
    PilotScenario(
        "P01",
        "Discussion remains exploratory and creates no workflow artifact.",
        '@discussion "Explore adding a lightweight health endpoint. Give concise options, risks, and open questions; then stop."',
        ("no new draft", "no workspace change"),
        "discussion",
        True,
    ),
    PilotScenario(
        "P02",
        "Issue-Draft creates one feature draft and stops before implementation.",
        "@issue-draft FEATURE: Add a lightweight health endpoint with a JSON status response. "
        "Requirements: provide GET /health and return a JSON status value. "
        "Acceptance criteria: a healthy service returns HTTP 200 with JSON status; the endpoint is documented. "
        "Scope: the health endpoint and its focused tests. Out of scope: dependency health checks and unrelated refactoring. "
        "Documentation impact: update the usage guide. Roadmap target: UNMAPPED.",
        ("at least one new draft", "no new implementation branch"),
        "issue-draft",
        True,
        (
            Fixture(
                "draft_input.json",
                "{\n"
                '  "work_type": "FEATURE",\n'
                '  "summary": "Add a lightweight health endpoint",\n'
                '  "requirements": ["Provide GET /health and return JSON status."],\n'
                '  "acceptance_criteria": ["A healthy service returns HTTP 200 with JSON status.", "The endpoint is documented."],\n'
                '  "scope": ["The health endpoint and focused tests."],\n'
                '  "out_of_scope": ["Dependency health checks and unrelated refactoring."],\n'
                '  "documentation_impact": ["Update the usage guide."],\n'
                '  "roadmap_target": "UNMAPPED"\n'
                "}\n",
                True,
                "approved Canonical Draft input",
            ),
        ),
    ),
    PilotScenario(
        "P03-U",
        "Start-Implement rejects an unknown draft without creating work artifacts.",
        "@start-implement DRAFT-9999",
        ("no new draft", "no workspace change"),
        "start-implement",
        True,
    ),
    PilotScenario(
        "P03-R",
        "Start-Implement turns an approved documentation draft into its exact remote Issue, branch, and draft PR state.",
        "@start-implement DRAFT-0001",
        ("one matching remote issue", "one bound remote branch", "one open draft PR", "exact documentation content", "not merged"),
        "start-implement",
        True,
        (
            Fixture(
                ".simple-flow/drafts/DRAFT-0001.json",
                "{\n"
                '  "draft_id": "DRAFT-0001",\n'
                '  "work_type": "DOCUMENTATION",\n'
                '  "fields": {\n'
                '    "Change": "Append \'Phase 4 P03 remote verification marker.\' to docs/app/usage.md",\n'
                '    "Reason": "Prove the Start-Implement remote workflow with deterministic evidence.",\n'
                '    "Impact": "Creates a disposable documentation-only evaluation change.",\n'
                '    "Supersedes": "None",\n'
                '    "Affected Project Documents": "- docs/app/usage.md",\n'
                '    "Source PR / Decision Context": "Phase 4 P03 remote fixture"\n'
                "  },\n"
                '  "source_issue": null,\n'
                '  "source_pr": null\n'
                "}\n",
            ),
            Fixture(
                ".simple-flow/drafts/DRAFT-0001.md",
                "Type: DOCUMENTATION\n\n## Change\n\nAppend 'Phase 4 P03 remote verification marker.' to docs/app/usage.md\n\n## Reason\n\nProve the Start-Implement remote workflow with deterministic evidence.\n\n## Impact\n\nCreates a disposable documentation-only evaluation change.\n\n## Supersedes\n\nNone\n\n## Affected Project Documents\n\n- docs/app/usage.md\n\n## Source PR / Decision Context\n\nPhase 4 P03 remote fixture\n",
            ),
            Fixture(
                ".simple-flow/phase4-remote-context.json",
                "{\n  \"repository\": \"{{repository}}\",\n  \"gh_command\": \"gh\"\n}\n",
                True,
                "remote execution context",
            ),
        ),
        RemoteExpectation(
            issue_title="Append 'Phase 4 P03 remote verification marker.' to docs/app/usage.md",
            branch_template="documentation/{issue_number}-phase4-smoke",
            pr_title="Append 'Phase 4 P03 remote verification marker.' to docs/app/usage.md",
            base_branch="main",
            pr_draft=True,
            pr_merged=False,
            exact_files=(("docs/app/usage.md", "# Test Project Usage\n\nThe sample app exposes a small health payload helper.\n\nPhase 4 P03 remote verification marker.\n"),),
        ),
    ),
)


RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "workflow_state", "stopped"],
    "properties": {
        "summary": {"type": "string"},
        "workflow_state": {"type": "string"},
        "stopped": {"type": "boolean"},
    },
}


@dataclass(frozen=True)
class LocalModelConfig:
    host: str
    endpoint: str
    model: str
    provider: str = "phase4_local"
    liveness_seconds: int = DEFAULT_LIVENESS_SECONDS
    action_timeout_seconds: int = 900

    def __post_init__(self) -> None:
        if self.host not in SDK_HOSTS:
            raise ValueError(f"Unsupported SDK host: {self.host}")
        if not self.endpoint.startswith(("http://", "https://")):
            raise ValueError("Local model endpoint must be an http(s) URL")
        if self.liveness_seconds < DEFAULT_LIVENESS_SECONDS:
            raise ValueError("Liveness checks must wait at least 60 seconds")
        if self.action_timeout_seconds <= self.liveness_seconds:
            raise ValueError("Action timeout must exceed the liveness interval")


@dataclass(frozen=True)
class SdkEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SdkTurn:
    final_text: str
    events: tuple[SdkEvent, ...]
    structured_result: dict[str, Any] | None
    session_id: str | None = None
    error: str | None = None
    submitted_prompt: str = ""
    attached_skill: str | None = None
    completed: bool = False


@dataclass(frozen=True)
class WorkspaceSnapshot:
    draft_count: int
    changed_paths: tuple[str, ...]
    implementation_branches: int


@dataclass(frozen=True)
class RemoteSnapshot:
    repository: str
    base_branch: str
    base_sha: str
    issues: tuple[dict[str, Any], ...]
    pull_requests: tuple[dict[str, Any], ...]
    branches: dict[str, str]


@dataclass(frozen=True)
class RemoteVerification:
    verdict: Verdict
    evidence: dict[str, Any]
    cleanup_verdict: Verdict = Verdict.PASS


@dataclass(frozen=True)
class ScenarioPrecondition:
    verdict: Verdict
    evidence: dict[str, Any]


@dataclass(frozen=True)
class RemoteVerificationConfig:
    repository: str
    gh_path: str


@dataclass(frozen=True)
class TrialResult:
    scenario_id: str
    verdicts: dict[str, Verdict]
    evidence: dict[str, Any]

    @property
    def is_blocked(self) -> bool:
        return any(value == Verdict.BLOCKED for value in self.verdicts.values())


class SdkAdapter(Protocol):
    async def run(self, scenario: PilotScenario, project_root: Path) -> SdkTurn: ...


class RemoteGateway(Protocol):
    def snapshot(self, base_branch: str) -> RemoteSnapshot: ...

    def file_content(self, branch: str, path: str) -> str: ...

    def branch_descends_from(self, base_sha: str, branch: str) -> bool: ...

    def ci_conclusions(self, pr_number: int) -> tuple[str, ...]: ...

    def issue_has_cleanup_note(self, issue_number: int) -> bool: ...

    def cleanup(self, *, pr_numbers: tuple[int, ...], issue_numbers: tuple[int, ...], branches: tuple[str, ...]) -> dict[str, Any]: ...


class WorkspaceObserver:
    """Small, deterministic local observer for the non-remote pilot scenarios."""

    def snapshot(self, project_root: Path) -> WorkspaceSnapshot:
        drafts = project_root / ".simple-flow" / "drafts"
        draft_count = len(list(drafts.glob("*.json"))) if drafts.exists() else 0
        changed_paths = tuple(sorted(_git_changed_paths(project_root)))
        branches = _git_implementation_branch_count(project_root)
        return WorkspaceSnapshot(draft_count, changed_paths, branches)


class GitHubRemoteGateway:
    """Narrow GitHub/Git observer used by every remote-capable SDK scenario.

    All reads are explicit JSON/API calls. Cleanup only touches identifiers
    discovered during this run, never repository-wide lists.
    """

    def __init__(self, project_root: Path, config: RemoteVerificationConfig):
        self.project_root = project_root
        self.config = config

    def snapshot(self, base_branch: str) -> RemoteSnapshot:
        repository = self.config.repository
        repo_data = self._gh_json(["api", f"repos/{repository}"])
        actual_base = str(repo_data.get("default_branch", ""))
        if actual_base != base_branch:
            raise RuntimeError(f"Expected default branch {base_branch}, found {actual_base or 'none'}")
        ref = self._gh_json(["api", f"repos/{repository}/git/ref/heads/{base_branch}"])
        base_sha = str(ref.get("object", {}).get("sha", ""))
        if not base_sha:
            raise RuntimeError(f"Cannot resolve {base_branch} SHA for {repository}")
        issues = tuple(
            item for item in self._gh_paginated(f"repos/{repository}/issues?state=all&per_page=100")
            if isinstance(item, dict) and "pull_request" not in item
        )
        pulls = tuple(
            item for item in self._gh_paginated(f"repos/{repository}/pulls?state=all&per_page=100")
            if isinstance(item, dict)
        )
        refs = self._gh_json(["api", f"repos/{repository}/git/matching-refs/heads/"])
        if not isinstance(refs, list):
            raise RuntimeError("GitHub branch reference response was not a list")
        branches = {
            str(item.get("ref", "")).removeprefix("refs/heads/"): str(item.get("object", {}).get("sha", ""))
            for item in refs
            if isinstance(item, dict) and item.get("ref")
        }
        return RemoteSnapshot(repository, base_branch, base_sha, issues, pulls, branches)

    def file_content(self, branch: str, path: str) -> str:
        self._run(["git", "fetch", "--quiet", "origin", branch])
        return self._run(["git", "show", f"origin/{branch}:{path}"]).stdout

    def branch_descends_from(self, base_sha: str, branch: str) -> bool:
        self._run(["git", "fetch", "--quiet", "origin", branch])
        result = self._run(["git", "merge-base", "--is-ancestor", base_sha, f"origin/{branch}"], check=False)
        return result.returncode == 0

    def ci_conclusions(self, pr_number: int) -> tuple[str, ...]:
        data = self._gh_json(["pr", "view", str(pr_number), "--repo", self.config.repository, "--json", "statusCheckRollup"])
        rollup = data.get("statusCheckRollup", []) if isinstance(data, dict) else []
        return tuple(
            str(item.get("conclusion", ""))
            for item in rollup
            if isinstance(item, dict) and item.get("conclusion")
        )

    def issue_has_cleanup_note(self, issue_number: int) -> bool:
        comments = self._gh_paginated(f"repos/{self.config.repository}/issues/{issue_number}/comments?per_page=100")
        return any(isinstance(item, dict) and str(item.get("body", "")) == REMOTE_CLEANUP_NOTE for item in comments)

    def cleanup(self, *, pr_numbers: tuple[int, ...], issue_numbers: tuple[int, ...], branches: tuple[str, ...]) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        for pr_number in pr_numbers:
            result = self._run([self.config.gh_path, "pr", "close", str(pr_number), "--repo", self.config.repository, "--delete-branch"], check=False)
            actions.append({"action": "close_pr_delete_branch", "id": pr_number, "returncode": result.returncode, "stderr": result.stderr[-500:]})
        for branch in branches:
            result = self._run(["git", "push", "origin", "--delete", branch], check=False)
            actions.append({"action": "delete_branch", "branch": branch, "returncode": result.returncode, "stderr": result.stderr[-500:]})
        for issue_number in issue_numbers:
            result = self._run([self.config.gh_path, "issue", "close", str(issue_number), "--repo", self.config.repository, "--comment", REMOTE_CLEANUP_NOTE], check=False)
            actions.append({"action": "close_issue", "id": issue_number, "returncode": result.returncode, "stderr": result.stderr[-500:]})
        return {"actions": actions, "success": all(item["returncode"] == 0 for item in actions)}

    def _gh_json(self, args: list[str]) -> dict[str, Any] | list[Any]:
        result = self._run([self.config.gh_path, *args])
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GitHub returned non-JSON output: {result.stdout[-500:]}") from exc
        if not isinstance(data, (dict, list)):
            raise RuntimeError("GitHub JSON response was not an object or list")
        return data

    def _gh_paginated(self, endpoint: str) -> list[Any]:
        data = self._gh_json(["api", "--paginate", endpoint])
        return data if isinstance(data, list) else [data]

    def _run(self, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, cwd=self.project_root, text=True, capture_output=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(f"Remote command failed ({result.returncode}): {' '.join(command)}\n{result.stderr[-1000:]}")
        return result


class RemoteScenarioPipeline:
    """Capture and compare a manifest-defined remote outcome for any skill."""

    def __init__(self, scenario: PilotScenario, gateway: RemoteGateway):
        if scenario.remote_expectation is None:
            raise ValueError(f"{scenario.scenario_id} has no remote expectation")
        self.scenario = scenario
        self.gateway = gateway
        self.expectation = scenario.remote_expectation
        self.before: RemoteSnapshot | None = None

    def capture_before(self) -> RemoteVerification:
        try:
            self.before = self.gateway.snapshot(self.expectation.base_branch)
            return RemoteVerification(Verdict.PASS, {"before": _remote_snapshot_data(self.before)})
        except Exception as exc:
            return RemoteVerification(Verdict.BLOCKED, {"error": f"{type(exc).__name__}: {exc}"})

    def capture_and_verify(self) -> RemoteVerification:
        if self.before is None:
            return RemoteVerification(Verdict.BLOCKED, {"error": "Remote baseline was not captured"})
        after: RemoteSnapshot | None = None
        cleanup: dict[str, Any] = {"actions": [], "success": False}
        failures: list[str] = []
        pr_numbers: tuple[int, ...] = ()
        issue_numbers: tuple[int, ...] = ()
        branches: tuple[str, ...] = ()
        try:
            after = self.gateway.snapshot(self.expectation.base_branch)
            try:
                evidence, _, _, _ = self._evaluate(after)
                failures.extend(evidence["failures"])
            except Exception as exc:
                evidence = {"before": _remote_snapshot_data(self.before), "failures": []}
                failures.append(f"Verification error: {type(exc).__name__}: {exc}")
        except Exception as exc:
            return RemoteVerification(Verdict.BLOCKED, {"before": _remote_snapshot_data(self.before), "error": f"{type(exc).__name__}: {exc}"})
        finally:
            if after is not None:
                try:
                    pr_numbers, issue_numbers, branches = self._run_artifact_ids(after)
                    cleanup = self.gateway.cleanup(pr_numbers=pr_numbers, issue_numbers=issue_numbers, branches=branches)
                except Exception as exc:
                    cleanup = {"actions": [], "success": False, "error": f"{type(exc).__name__}: {exc}"}
        cleanup_check: dict[str, Any] = {"failures": []}
        if cleanup.get("success"):
            try:
                post_cleanup = self.gateway.snapshot(self.expectation.base_branch)
                cleanup_check = self._verify_cleanup(post_cleanup, pr_numbers, issue_numbers, branches)
                cleanup_check["post_cleanup"] = _remote_snapshot_data(post_cleanup)
            except Exception as exc:
                cleanup_check = {"failures": [f"Cleanup verification error: {type(exc).__name__}: {exc}"]}
        cleanup_verdict = Verdict.PASS if cleanup.get("success") and not cleanup_check["failures"] else Verdict.FAIL
        evidence["after"] = _remote_snapshot_data(after)
        evidence["cleanup"] = cleanup
        evidence["cleanup_verification"] = cleanup_check
        evidence["failures"] = failures
        return RemoteVerification(Verdict.PASS if not failures else Verdict.FAIL, evidence, cleanup_verdict)

    def _run_artifact_ids(self, after: RemoteSnapshot) -> tuple[tuple[int, ...], tuple[int, ...], tuple[str, ...]]:
        before = self.before
        assert before is not None
        pr_numbers = tuple(number for number in (_item_number(item) for item in _new_remote_items(before.pull_requests, after.pull_requests)) if number is not None)
        issue_numbers = tuple(number for number in (_item_number(item) for item in _new_remote_items(before.issues, after.issues)) if number is not None)
        pr_heads = {
            str(item.get("head", {}).get("ref", ""))
            for item in _new_remote_items(before.pull_requests, after.pull_requests)
            if isinstance(item.get("head"), dict)
        }
        branches = tuple(sorted((set(after.branches) - set(before.branches)) - pr_heads))
        return pr_numbers, issue_numbers, branches

    def _verify_cleanup(
        self,
        post_cleanup: RemoteSnapshot,
        pr_numbers: tuple[int, ...],
        issue_numbers: tuple[int, ...],
        branches: tuple[str, ...],
    ) -> dict[str, Any]:
        failures: list[str] = []
        pull_by_number = {_item_number(item): item for item in post_cleanup.pull_requests}
        issue_by_number = {_item_number(item): item for item in post_cleanup.issues}
        for pr_number in pr_numbers:
            if str(pull_by_number.get(pr_number, {}).get("state", "")).lower() != "closed":
                failures.append(f"Cleanup did not close pull request {pr_number}")
        for issue_number in issue_numbers:
            if str(issue_by_number.get(issue_number, {}).get("state", "")).lower() != "closed":
                failures.append(f"Cleanup did not close issue {issue_number}")
            elif not self.gateway.issue_has_cleanup_note(issue_number):
                failures.append(f"Cleanup note missing from issue {issue_number}")
        for branch in branches:
            if branch in post_cleanup.branches:
                failures.append(f"Cleanup did not delete branch {branch}")
        return {"pull_requests": list(pr_numbers), "issues": list(issue_numbers), "branches": list(branches), "required_note": REMOTE_CLEANUP_NOTE, "failures": failures}

    def _evaluate(self, after: RemoteSnapshot) -> tuple[dict[str, Any], int | None, int | None, str | None]:
        before = self.before
        assert before is not None
        failures: list[str] = []
        new_issues = _new_remote_items(before.issues, after.issues)
        matched_issues = [item for item in new_issues if str(item.get("title", "")) == self.expectation.issue_title]
        issue_number = _one_number(matched_issues, "matching issue", failures)
        branch = self.expectation.branch_for_issue(issue_number) if issue_number is not None else None
        if branch is not None:
            if branch not in after.branches:
                failures.append(f"Expected branch missing: {branch}")
            elif not self.gateway.branch_descends_from(before.base_sha, branch):
                failures.append(f"Branch does not descend from baseline: {branch}")
        expected_branches = {branch} if branch else set()
        unexpected_branches = sorted(set(after.branches) - set(before.branches) - expected_branches)
        if unexpected_branches:
            failures.append(f"Unexpected new branches: {', '.join(unexpected_branches)}")

        new_prs = _new_remote_items(before.pull_requests, after.pull_requests)
        matched_prs = [
            item for item in new_prs
            if str(item.get("title", "")) == self.expectation.pr_title
            and str(item.get("base", {}).get("ref", "")) == self.expectation.base_branch
            and str(item.get("head", {}).get("ref", "")) == (branch or "")
        ]
        pr_number = _one_number(matched_prs, "matching pull request", failures)
        if pr_number is not None:
            pr = matched_prs[0]
            if bool(pr.get("draft")) != self.expectation.pr_draft:
                failures.append("Pull request draft state differs from manifest")
            if bool(pr.get("merged_at")) != self.expectation.pr_merged:
                failures.append("Pull request merge state differs from manifest")
            self._check_ci(pr_number, failures)
        expected_prs = {pr_number} if pr_number is not None else set()
        unexpected_prs = sorted(_item_number(item) for item in new_prs if _item_number(item) not in expected_prs)
        if unexpected_prs:
            failures.append(f"Unexpected new pull requests: {unexpected_prs}")
        expected_issues = {issue_number} if issue_number is not None else set()
        unexpected_issues = sorted(_item_number(item) for item in new_issues if _item_number(item) not in expected_issues)
        if unexpected_issues:
            failures.append(f"Unexpected new issues: {unexpected_issues}")
        if branch is not None and branch in after.branches:
            for path, expected_content in self.expectation.exact_files:
                if self.gateway.file_content(branch, path) != expected_content:
                    failures.append(f"Exact content mismatch: {path}")
        return (
            {
                "before": _remote_snapshot_data(before),
                "manifest": asdict(self.expectation),
                "matched_issue_number": issue_number,
                "expected_branch": branch,
                "matched_pr_number": pr_number,
                "failures": failures,
            },
            issue_number,
            pr_number,
            branch,
        )

    def _check_ci(self, pr_number: int, failures: list[str]) -> None:
        expectation = self.expectation.ci_expectation
        if expectation == CIExpectation.IGNORE:
            return
        conclusions = self.gateway.ci_conclusions(pr_number)
        if expectation == CIExpectation.PRESENT and not conclusions:
            failures.append("Expected CI result is absent")
        if expectation == CIExpectation.SUCCESS and (not conclusions or any(value != "SUCCESS" for value in conclusions)):
            failures.append(f"Expected successful CI, found: {list(conclusions)}")


class CodexSdkAdapter:
    """Codex app-server SDK adapter, pinned by the phase4-sdk extra."""

    def __init__(self, config: LocalModelConfig):
        self.config = config

    async def run(self, scenario: PilotScenario, project_root: Path) -> SdkTurn:
        from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, MentionInput, Sandbox, SkillInput, TextInput

        # app-server receives the local routing settings directly.  No API key,
        # remote provider, prompt-side skill context, or shell wrapper is used.
        endpoint = _endpoint_root(self.config.endpoint)
        overrides = (
            f'model_provider="{self.config.provider}"',
            f'model_providers.{self.config.provider}.name="Phase 4 local"',
            f'model_providers.{self.config.provider}.base_url="{endpoint}/v1"',
            f'model_providers.{self.config.provider}.wire_api="responses"',
            f'model_providers.{self.config.provider}.requires_openai_auth=false',
        )
        client = AsyncCodex(CodexConfig(cwd=str(project_root), config_overrides=overrides))
        events: list[SdkEvent] = []
        skill_path = _skill_path(project_root, scenario.required_skill)
        if scenario.required_skill and skill_path is None:
            return SdkTurn("", (), None, error=f"Missing installed skill: {scenario.required_skill}", submitted_prompt=scenario.prompt)
        try:
            thread = await client.thread_start(
                cwd=str(project_root),
                model=self.config.model,
                model_provider=self.config.provider,
                approval_mode=ApprovalMode.auto_review,
                sandbox=Sandbox.workspace_write,
            )
            turn_input = [TextInput(scenario.prompt)]
            if skill_path is not None:
                turn_input.append(SkillInput(scenario.required_skill or "", str(skill_path)))
            for fixture, path in _attached_fixture_paths(project_root, scenario):
                turn_input.append(MentionInput(fixture.label, str(path)))
            turn = await thread.turn(turn_input, output_schema=RESULT_SCHEMA, sandbox=Sandbox.workspace_write)
            completed: Any | None = None
            async for event in _stream_with_liveness(
                turn.stream(),
                self.config.liveness_seconds,
                self.config.action_timeout_seconds,
            ):
                events.append(_normalize_codex_event(event))
                if getattr(event, "method", "") == "turn/completed":
                    completed = getattr(getattr(event, "payload", None), "turn", None)
            final_response = getattr(completed, "final_response", "") if completed else ""
            final_response = final_response or _codex_final_text(events)
            return SdkTurn(
                final_text=final_response or "",
                events=tuple(events),
                structured_result=_capture_result(final_response or "", events, thread.id, completed is not None),
                session_id=thread.id,
                error=getattr(completed, "error", None) if completed else "Codex completed without a completion event",
                submitted_prompt=scenario.prompt,
                attached_skill=scenario.required_skill,
                completed=completed is not None,
            )
        except Exception as exc:  # SDK errors are infrastructure evidence, not agent failures.
            return SdkTurn("", tuple(events), None, error=f"{type(exc).__name__}: {exc}", submitted_prompt=scenario.prompt)
        finally:
            await client.close()


class ClaudeSdkAdapter:
    """Claude Code SDK adapter routed through an OpenAI-compatible local gateway."""

    def __init__(self, config: LocalModelConfig):
        self.config = config

    async def run(self, scenario: PilotScenario, project_root: Path) -> SdkTurn:
        from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query

        events: list[SdkEvent] = []
        final_text = ""
        session_id: str | None = None
        endpoint = _endpoint_root(self.config.endpoint)
        options = ClaudeCodeOptions(
            cwd=project_root,
            model=self.config.model,
            permission_mode="acceptEdits",
            env={"ANTHROPIC_BASE_URL": endpoint},
            extra_args={"json-schema": json.dumps(RESULT_SCHEMA, separators=(",", ":"))},
        )
        try:
            stream = query(prompt=scenario.prompt, options=options)
            async for message in _stream_with_liveness(
                stream,
                self.config.liveness_seconds,
                self.config.action_timeout_seconds,
            ):
                events.append(_normalize_claude_event(message))
                if isinstance(message, ResultMessage):
                    final_text = message.result or ""
                    session_id = message.session_id
                    if message.is_error:
                        return SdkTurn(final_text, tuple(events), None, session_id, "Claude returned an error result")
            return SdkTurn(
                final_text,
                tuple(events),
                _capture_result(final_text, events, session_id, True),
                session_id,
                submitted_prompt=scenario.prompt,
                completed=True,
            )
        except Exception as exc:
            return SdkTurn(final_text, tuple(events), None, session_id, f"{type(exc).__name__}: {exc}", submitted_prompt=scenario.prompt)


async def _stream_with_liveness(
    stream: AsyncIterator[Any],
    liveness_seconds: int,
    action_timeout_seconds: int,
) -> AsyncIterator[Any]:
    """Yield pushed SDK events; after 60s of silence record one local liveness event.

    The timeout is not an agent prompt and does not make another model request.
    It is deliberately a minimum 60 seconds to avoid result-polling churn.
    """
    started = time.monotonic()
    events: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for item in stream:
                await events.put(("event", item))
        except BaseException as exc:
            await events.put(("error", exc))
        finally:
            await events.put(("done", None))

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            remaining = action_timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError(f"SDK action exceeded {action_timeout_seconds} seconds")
            try:
                kind, value = await asyncio.wait_for(events.get(), timeout=min(liveness_seconds, remaining))
            except TimeoutError:
                # This wait observes the local SDK process only. It sends no
                # agent request and leaves the stream owned by the pump task.
                yield SdkEvent("liveness_check", {"waited_seconds": liveness_seconds})
                continue
            if kind == "event":
                yield value
            elif kind == "error":
                raise value
            else:
                return
    finally:
        if not pump_task.done():
            pump_task.cancel()
            with suppress(asyncio.CancelledError):
                await pump_task


def run_pilot_trial(
    scenario: PilotScenario,
    turn: SdkTurn,
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
    *,
    config: LocalModelConfig,
    remote: RemoteVerification | None = None,
    precondition: ScenarioPrecondition | None = None,
) -> TrialResult:
    precondition = precondition or ScenarioPrecondition(Verdict.PASS, {})
    local_objective = _objective_verdict(scenario, before, after)
    remote_objective = remote.verdict if remote is not None else (Verdict.PASS if scenario.remote_expectation is None else Verdict.BLOCKED)
    objective = _combined_objective_verdict(precondition.verdict, local_objective, remote_objective)
    verdicts: dict[str, Verdict] = {
        "local_route": Verdict.PASS if config.endpoint else Verdict.BLOCKED,
        "prompt_fidelity": Verdict.PASS if turn.submitted_prompt == scenario.prompt and prompt_is_developer_realistic(scenario.prompt) else Verdict.FAIL,
        "structured_result": Verdict.PASS if _valid_result(turn.structured_result) else Verdict.FAIL,
        "host_trace": Verdict.PASS if turn.events else Verdict.BLOCKED,
        "skill_invocation": _skill_delivery_verdict(turn.attached_skill, scenario.required_skill),
        "precondition": precondition.verdict,
        "objective_state": local_objective,
        "remote_state": remote_objective,
        "remote_cleanup": remote.cleanup_verdict if remote is not None else Verdict.PASS,
        "workflow_outcome": _workflow_outcome_verdict(turn, objective),
        "stop_boundary": _stop_verdict(turn.structured_result, scenario.requires_stop, objective),
    }
    if turn.error:
        for name in verdicts:
            if name != "prompt_fidelity":
                verdicts[name] = Verdict.BLOCKED
    return TrialResult(
        scenario.scenario_id,
        verdicts,
        {
            "error": turn.error,
            "session_id": turn.session_id,
            "event_count": len(turn.events),
            "event_methods": sorted({str(event.data.get("method", event.data.get("type", event.kind))) for event in turn.events}),
            "attached_skill": turn.attached_skill,
            "final_text_preview": turn.final_text[:1200],
            "before": asdict(before),
            "after": asdict(after),
            "remote": remote.evidence if remote is not None else None,
            "precondition": precondition.evidence,
        },
    )


def prompt_is_developer_realistic(prompt: str) -> bool:
    lowered = prompt.lower()
    forbidden = ("skill.md", ".codex/skills", "scripts/", "python ", "argv", "helper")
    return bool(prompt.strip()) and not any(fragment in lowered for fragment in forbidden)


def capability_confidence(trials: Iterable[TrialResult], checkpoint: str) -> dict[str, Any]:
    """Return statistical confidence for one capability checkpoint only.

    Deterministic and infrastructure checkpoints are intentionally rejected.
    BLOCKED/UNKNOWN trials are reported separately and never enter the rate or
    Wilson interval.
    """
    node = next((item for item in CHECKPOINTS if item.name == checkpoint), None)
    if node is None or not node.confidence_eligible:
        raise ValueError(f"{checkpoint} is not confidence-eligible")
    trial_list = list(trials)
    scenario_ids = {trial.scenario_id for trial in trial_list}
    if len(scenario_ids) != 1:
        raise ValueError("Confidence must be calculated for exactly one scenario configuration")
    values = [trial.verdicts.get(checkpoint, Verdict.UNKNOWN) for trial in trial_list]
    valid = [value for value in values if value in (Verdict.PASS, Verdict.FAIL)]
    passed = sum(value == Verdict.PASS for value in valid)
    total = len(valid)
    low, high = _wilson_interval(passed, total)
    return {
        "scenario_id": next(iter(scenario_ids)),
        "checkpoint": checkpoint,
        "valid_trials": total,
        "passed_trials": passed,
        "blocked_trials": sum(value == Verdict.BLOCKED for value in values),
        "unknown_trials": sum(value == Verdict.UNKNOWN for value in values),
        "pass_rate": passed / total if total else None,
        "wilson_95": [low, high] if total else None,
    }


def capability_confidence_by_scenario(trials: Iterable[TrialResult]) -> list[dict[str, Any]]:
    grouped: dict[str, list[TrialResult]] = {}
    for trial in trials:
        grouped.setdefault(trial.scenario_id, []).append(trial)
    return [
        {
            "scenario_id": scenario_id,
            "checkpoints": [
                capability_confidence(group, "workflow_outcome"),
                capability_confidence(group, "stop_boundary"),
            ],
        }
        for scenario_id, group in grouped.items()
    ]


def make_adapter(config: LocalModelConfig) -> SdkAdapter:
    if config.host == "codex-sdk":
        return CodexSdkAdapter(config)
    if config.host == "claude-sdk":
        return ClaudeSdkAdapter(config)
    raise ValueError(f"Unsupported SDK host: {config.host}")


async def run_live_pilot(
    config: LocalModelConfig,
    project_root: Path,
    *,
    repetitions: int = 1,
    scenarios: Iterable[PilotScenario] = PILOT_SCENARIOS,
    remote_config: RemoteVerificationConfig | None = None,
) -> list[TrialResult]:
    """Run the small live pilot against a caller-supplied, disposable project."""
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    adapter = make_adapter(config)
    observer = WorkspaceObserver()
    trials: list[TrialResult] = []
    for _ in range(repetitions):
        for scenario in scenarios:
            _prepare_fixture(project_root, scenario, remote_config)
            precondition = _scenario_precondition(project_root, scenario)
            before = observer.snapshot(project_root)
            remote_pipeline: RemoteScenarioPipeline | None = None
            remote_before: RemoteVerification | None = None
            if scenario.remote_expectation is not None:
                if remote_config is None:
                    remote_before = RemoteVerification(Verdict.BLOCKED, {"error": "Remote verification is required for this scenario"})
                else:
                    remote_pipeline = RemoteScenarioPipeline(scenario, GitHubRemoteGateway(project_root, remote_config))
                    remote_before = remote_pipeline.capture_before()
            if precondition.verdict == Verdict.PASS:
                turn = await adapter.run(scenario, project_root)
            else:
                turn = SdkTurn(
                    "", (), None,
                    error="Scenario precondition did not pass",
                    submitted_prompt=scenario.prompt,
                    attached_skill=scenario.required_skill,
                )
            after = observer.snapshot(project_root)
            remote_after = remote_pipeline.capture_and_verify() if remote_pipeline is not None and remote_before and remote_before.verdict == Verdict.PASS else remote_before
            trials.append(run_pilot_trial(scenario, turn, before, after, config=config, remote=remote_after, precondition=precondition))
    return trials


def sdk_preflight(config: LocalModelConfig) -> dict[str, Any]:
    """Check local routing prerequisites without sending an agent task."""
    from importlib.util import find_spec
    from urllib import error, request

    package = "openai_codex" if config.host == "codex-sdk" else "claude_code_sdk"
    result: dict[str, Any] = {
        "host": config.host,
        "model": config.model,
        "endpoint": _endpoint_root(config.endpoint),
        "sdk_package": package,
        "sdk_package_available": find_spec(package) is not None,
        "local_model_reachable": False,
    }
    try:
        with request.urlopen(f"{_endpoint_root(config.endpoint)}/v1/models", timeout=10) as response:
            result["local_model_reachable"] = 200 <= response.status < 300
            result["models_response_status"] = response.status
    except (OSError, error.HTTPError) as exc:
        result["models_error"] = str(exc)
    result["ready"] = result["sdk_package_available"] and result["local_model_reachable"]
    return result


def _wilson_interval(passed: int, total: int) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    proportion = passed / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half = z * ((proportion * (1 - proportion) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _valid_result(value: dict[str, Any] | None) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 1
        and isinstance(value.get("session_id"), str)
        and isinstance(value.get("final_text"), str)
        and isinstance(value.get("event_count"), int)
        and isinstance(value.get("turn_completed"), bool)
    )


def _parse_structured_result(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _capture_result(final_text: str, events: Iterable[SdkEvent], session_id: str | None, completed: bool) -> dict[str, Any]:
    """Normalize SDK output into the test harness's required result record.

    This record is produced from the SDK transport, rather than asking a local
    model to repeat the developer prompt as JSON. Any optional JSON returned by
    the agent is retained as supplementary evidence only.
    """
    captured_events = tuple(events)
    return {
        "schema_version": 1,
        "session_id": session_id or "",
        "final_text": final_text,
        "event_count": len(captured_events),
        "turn_completed": completed,
        "agent_report": _parse_structured_result(final_text),
    }


def _skill_path(project_root: Path, skill_name: str | None) -> Path | None:
    if skill_name is None:
        return None
    path = project_root / ".codex" / "skills" / skill_name / "SKILL.md"
    return path if path.is_file() else None


def _fixture_paths(project_root: Path, scenario: PilotScenario) -> tuple[Path, ...]:
    return tuple(project_root / fixture.relative_path for fixture in scenario.fixtures)


def _attached_fixture_paths(project_root: Path, scenario: PilotScenario) -> tuple[tuple[Fixture, Path], ...]:
    return tuple((fixture, project_root / fixture.relative_path) for fixture in scenario.fixtures if fixture.attach_to_turn)


def _prepare_fixture(
    project_root: Path,
    scenario: PilotScenario,
    remote_config: RemoteVerificationConfig | None = None,
) -> None:
    for fixture in scenario.fixtures:
        path = project_root / fixture.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = fixture.content
        if "{{repository}}" in content:
            if remote_config is None:
                raise ValueError(f"{scenario.scenario_id} fixture requires remote configuration")
            content = content.replace("{{repository}}", remote_config.repository)
        path.write_text(content, encoding="utf-8")


def _scenario_precondition(project_root: Path, scenario: PilotScenario) -> ScenarioPrecondition:
    """Validate framework-owned inputs before the agent receives the task."""
    if scenario.scenario_id != "P03-R":
        return ScenarioPrecondition(Verdict.PASS, {"kind": "not-required"})
    try:
        from simple_flow_agent.drafts import DraftStore
        from simple_flow_agent.start_implement import select_start_path

        draft = DraftStore(project_root / ".simple-flow" / "drafts").read("DRAFT-0001")
        plan = select_start_path(DraftStore(project_root / ".simple-flow" / "drafts"), draft.draft_id)
        valid = draft.work_type == "DOCUMENTATION" and plan.path == "DOCUMENTATION_NORMAL" and not plan.tdd_required
        return ScenarioPrecondition(
            Verdict.PASS if valid else Verdict.FAIL,
            {"draft_id": draft.draft_id, "work_type": draft.work_type, "path": plan.path, "tdd_required": plan.tdd_required},
        )
    except Exception as exc:
        return ScenarioPrecondition(Verdict.BLOCKED, {"error": f"{type(exc).__name__}: {exc}"})


def _skill_delivery_verdict(attached_skill: str | None, required_skill: str | None) -> Verdict:
    if required_skill is None:
        return Verdict.PASS
    return Verdict.PASS if attached_skill == required_skill else Verdict.FAIL


def _workflow_outcome_verdict(turn: SdkTurn, objective: Verdict) -> Verdict:
    if not turn.completed:
        return Verdict.UNKNOWN
    return Verdict.PASS if objective == Verdict.PASS else Verdict.FAIL


def _stop_verdict(result: dict[str, Any] | None, required: bool, objective: Verdict) -> Verdict:
    if not required:
        return Verdict.PASS
    if not _valid_result(result):
        return Verdict.UNKNOWN
    return Verdict.PASS if result["turn_completed"] and objective == Verdict.PASS else Verdict.FAIL


def _objective_verdict(scenario: PilotScenario, before: WorkspaceSnapshot, after: WorkspaceSnapshot) -> Verdict:
    new_drafts = after.draft_count - before.draft_count
    changed = after.changed_paths != before.changed_paths
    new_branches = after.implementation_branches - before.implementation_branches
    if scenario.scenario_id == "P02":
        return Verdict.PASS if new_drafts >= 1 and new_branches <= 0 else Verdict.FAIL
    if scenario.remote_expectation is not None:
        # Start-Implement is expected to create and commit locally before it
        # pushes the branch. The remote manifest owns that capability oracle.
        return Verdict.PASS if new_drafts == 0 else Verdict.FAIL
    return Verdict.PASS if new_drafts == 0 and not changed and new_branches <= 0 else Verdict.FAIL


def _combined_objective_verdict(*values: Verdict) -> Verdict:
    if Verdict.BLOCKED in values:
        return Verdict.BLOCKED
    if Verdict.UNKNOWN in values:
        return Verdict.UNKNOWN
    return Verdict.PASS if all(value == Verdict.PASS for value in values) else Verdict.FAIL


def _normalize_codex_event(event: Any) -> SdkEvent:
    if isinstance(event, SdkEvent):
        return event
    method = getattr(event, "method", "notification")
    payload = getattr(event, "payload", None)
    payload_data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else {"payload": str(payload)}
    encoded = json.dumps(payload_data, sort_keys=True).lower()
    if _has_skill_tool(payload_data):
        kind = "skill"
    elif "tool" in method.lower() or "command" in method.lower() or "tool" in encoded or "command" in encoded:
        kind = "tool"
    else:
        kind = "event"
    return SdkEvent(kind, {"method": method, **payload_data})


def _has_skill_tool(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"tool_name", "toolName", "tool"} and isinstance(nested, str) and nested.lower() in {"skill", "skills"}:
                return True
            if _has_skill_tool(nested):
                return True
    if isinstance(value, list):
        return any(_has_skill_tool(nested) for nested in value)
    return False


def _codex_final_text(events: Iterable[SdkEvent]) -> str:
    """Recover the completed agent message when app-server omits final_response."""
    completed = [event for event in events if event.data.get("method") == "item/completed"]
    for event in reversed(completed):
        text = _find_agent_text(event.data)
        if text:
            return text
    deltas = [
        str(event.data["delta"])
        for event in events
        if event.data.get("method") == "item/agentMessage/delta" and isinstance(event.data.get("delta"), str)
    ]
    return "".join(deltas)


def _find_agent_text(value: Any) -> str:
    if isinstance(value, dict):
        item_type = str(value.get("type", "")).lower()
        if item_type in {"agentmessage", "assistantmessage"}:
            for key in ("text", "content", "message"):
                if isinstance(value.get(key), str):
                    return value[key]
        for nested in value.values():
            found = _find_agent_text(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_agent_text(nested)
            if found:
                return found
    return ""


def _normalize_claude_event(message: Any) -> SdkEvent:
    if isinstance(message, SdkEvent):
        return message
    type_name = type(message).__name__
    data = asdict(message) if hasattr(message, "__dataclass_fields__") else {"message": str(message)}
    kind = "tool" if type_name in {"AssistantMessage", "UserMessage"} and "ToolUseBlock" in str(data) else "event"
    if "tool_use" in json.dumps(data).lower():
        kind = "tool"
    return SdkEvent(kind, {"type": type_name, **data})


def _endpoint_root(endpoint: str) -> str:
    stripped = endpoint.rstrip("/")
    return stripped[:-3] if stripped.endswith("/v1") else stripped


def _git_changed_paths(project_root: Path) -> list[str]:
    import subprocess

    result = subprocess.run(["git", "status", "--porcelain"], cwd=project_root, text=True, capture_output=True, check=False)
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        parts = Path(path).parts
        if "__pycache__" in parts or path.endswith(".pyc") or Path(path).name.startswith("phase4-sdk-"):
            continue
        paths.append(path)
    return paths


def _git_implementation_branch_count(project_root: Path) -> int:
    import subprocess

    result = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=project_root, text=True, capture_output=True, check=False)
    protected = {"main", "master", "develop"}
    return sum(branch.strip() not in protected for branch in result.stdout.splitlines() if branch.strip())


def _item_number(item: dict[str, Any]) -> int | None:
    value = item.get("number")
    return int(value) if isinstance(value, int | str) and str(value).isdigit() else None


def _new_remote_items(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    before_numbers = {_item_number(item) for item in before}
    return [item for item in after if _item_number(item) not in before_numbers]


def _one_number(items: list[dict[str, Any]], label: str, failures: list[str]) -> int | None:
    numbers = [_item_number(item) for item in items]
    valid = [number for number in numbers if number is not None]
    if len(valid) != 1:
        failures.append(f"Expected exactly one {label}, found {len(valid)}")
        return None
    return valid[0]


def _remote_snapshot_data(snapshot: RemoteSnapshot) -> dict[str, Any]:
    return {
        "repository": snapshot.repository,
        "base_branch": snapshot.base_branch,
        "base_sha": snapshot.base_sha,
        "issue_numbers": sorted(number for number in (_item_number(item) for item in snapshot.issues) if number is not None),
        "pull_request_numbers": sorted(number for number in (_item_number(item) for item in snapshot.pull_requests) if number is not None),
        "branches": snapshot.branches,
    }
