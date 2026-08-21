from __future__ import annotations

from dataclasses import dataclass
import re

from simple_flow_gates.contracts import ContractError, PullRequestContract


MAIN_BRANCHES = {"main", "master", "trunk"}
BRANCH_ISSUE_PATTERNS = [
    re.compile(r"(?:^|[/_-])issue[/_-](\d+)(?:$|[/_-])", re.IGNORECASE),
    re.compile(r"(?:^|[/_-])feature[/_-](\d+)(?:$|[/_-])", re.IGNORECASE),
    re.compile(r"(?:^|[/_-])project-change[/_-](\d+)(?:$|[/_-])", re.IGNORECASE),
    re.compile(r"(?:^|[/_-])sf[/_-](\d+)(?:$|[/_-])", re.IGNORECASE),
]


@dataclass(frozen=True)
class PullRequestState:
    body: str
    head_ref: str
    base_ref: str
    is_draft: bool
    action: str = "synchronize"


def validate_branch_pr_gate(state: PullRequestState) -> PullRequestContract:
    pr = PullRequestContract.parse(state.body)

    if state.head_ref in MAIN_BRANCHES:
        raise ContractError("Pull request head branch must not be the main branch.")
    if state.base_ref not in MAIN_BRANCHES:
        raise ContractError("Pull request base branch must be the protected main branch.")

    branch_issue = issue_number_from_branch(state.head_ref)
    if branch_issue is None:
        raise ContractError(
            "Branch must include an issue binding such as 'feature/123-short-name'."
        )
    if branch_issue != pr.linked_issue:
        raise ContractError(
            f"Branch issue binding #{branch_issue} does not match linked issue #{pr.linked_issue}."
        )

    if state.action == "opened" and not state.is_draft:
        raise ContractError("Formal development pull requests must be opened as draft PRs.")

    return pr


def issue_number_from_branch(branch_name: str) -> int | None:
    for pattern in BRANCH_ISSUE_PATTERNS:
        match = pattern.search(branch_name)
        if match:
            return int(match.group(1))
    return None

