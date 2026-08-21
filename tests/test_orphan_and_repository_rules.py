from __future__ import annotations

from pathlib import Path

from simple_flow_gates.orphan import BranchState, find_orphan_branches
from simple_flow_gates.repository_rules import (
    REQUIRED_STATUS_CHECKS,
    desired_main_branch_policy,
    desired_repository_settings,
)


def test_orphan_watch_detects_development_branch_without_pr() -> None:
    branches = [
        BranchState(name="main", commits_ahead=0, has_open_pr=False),
        BranchState(name="feature/123-with-pr", commits_ahead=2, has_open_pr=True),
        BranchState(name="feature/124-no-pr", commits_ahead=1, has_open_pr=False),
    ]

    assert find_orphan_branches(branches) == [
        BranchState(name="feature/124-no-pr", commits_ahead=1, has_open_pr=False)
    ]


def test_orphan_watch_ignores_main_and_branches_with_open_prs() -> None:
    branches = [
        BranchState(name="main", commits_ahead=5, has_open_pr=False),
        BranchState(name="feature/123-with-pr", commits_ahead=2, has_open_pr=True),
    ]

    assert find_orphan_branches(branches) == []


def test_review_merge_policy_matches_phase1_identity_constraints() -> None:
    repository_settings = desired_repository_settings()
    branch_policy = desired_main_branch_policy()

    assert repository_settings["delete_branch_on_merge"] is True
    assert repository_settings["allow_auto_merge"] is False
    assert branch_policy["require_pull_request"] is True
    assert branch_policy["enforce_admins"] is True
    assert branch_policy["required_conversation_resolution"] is True
    assert branch_policy["allow_force_pushes"] is False
    assert branch_policy["required_approving_review_count"] == 0
    assert branch_policy["required_status_checks"] == REQUIRED_STATUS_CHECKS


def test_repository_configuration_script_uses_required_status_checks() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "configure_repository.ps1"
    text = script.read_text(encoding="utf-8")

    for check in REQUIRED_STATUS_CHECKS:
        assert f'"{check}"' in text
    assert '"phase1-gates"' not in text
    assert '"phase1-tests"' not in text
