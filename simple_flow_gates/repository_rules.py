from __future__ import annotations


REQUIRED_STATUS_CHECKS = [
    "pr-contract",
    "linked-issue-contract",
    "scope-governance",
    "documentation-impact",
    "tdd-evidence-order",
    "tdd-red-replay",
    "tdd-green-replay",
    "current-head-tests",
]


def desired_repository_settings() -> dict[str, bool]:
    return {
        "delete_branch_on_merge": True,
        "allow_auto_merge": False,
    }


def desired_main_branch_policy() -> dict[str, object]:
    return {
        "require_pull_request": True,
        "enforce_admins": True,
        "required_approving_review_count": 0,
        "required_status_checks": REQUIRED_STATUS_CHECKS,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
