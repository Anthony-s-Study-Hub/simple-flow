from __future__ import annotations

from pathlib import Path

from simple_flow_gates.repository_rules import REQUIRED_STATUS_CHECKS


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PR_CHECKS = [
    "pr-contract",
    "linked-issue-contract",
    "scope-governance",
    "documentation-impact",
    "tdd-evidence-order",
    "tdd-red-replay",
    "tdd-green-replay",
    "current-head-tests",
]


def test_orphan_branch_watch_passes_gh_token_to_detector() -> None:
    workflow = _workflow("orphan-branch-watch.yml")

    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "python -m scripts.orphan_branch_watch" in workflow


def test_issue_governance_workflow_is_issue_only() -> None:
    workflow = _workflow("issue-governance.yml")
    normalized = workflow.replace("\r\n", "\n")

    assert "name: Issue Governance" in workflow
    assert "on:\n  issues:" in normalized
    assert "on:\n  pull_request:" not in normalized
    assert "  issue-contract:" in workflow
    assert "validate-issue" in workflow


def test_pr_governance_workflow_is_pr_only_and_granular() -> None:
    workflow = _workflow("pr-governance.yml")
    normalized = workflow.replace("\r\n", "\n")

    assert "name: PR Governance" in workflow
    assert "on:\n  pull_request:" in normalized
    assert "on:\n  issues:" not in normalized
    for job in REQUIRED_PR_CHECKS[:-1]:
        assert f"  {job}:" in workflow
    assert "validate-pr-contract" in workflow
    assert "validate-linked-issue" in workflow
    assert "validate-scope" in workflow
    assert "validate-documentation-impact" in workflow
    assert "validate-tdd-evidence" in workflow
    assert "verify-tdd-red" in workflow
    assert "verify-tdd-green" in workflow

    assert '--base-ref "${{ github.event.pull_request.base.sha }}"' in workflow


def test_current_head_tests_workflow_is_separate_from_governance() -> None:
    workflow = _workflow("phase1-tests.yml")

    assert "name: PR Tests" in workflow
    assert "  current-head-tests:" in workflow
    assert "python -m pytest" in workflow
    assert "simple_flow_gates.cli validate-" not in workflow


def test_required_status_checks_match_granular_pr_jobs() -> None:
    assert REQUIRED_STATUS_CHECKS == REQUIRED_PR_CHECKS


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
