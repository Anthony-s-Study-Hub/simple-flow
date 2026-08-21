from __future__ import annotations

import pytest

from simple_flow_gates.branch_pr import PullRequestState, validate_branch_pr_gate
from simple_flow_gates.contracts import ContractError
from tests.conftest import pr_body


def test_branch_pr_gate_passes_for_draft_pr_bound_to_issue() -> None:
    contract = validate_branch_pr_gate(
        PullRequestState(
            body=pr_body(123),
            head_ref="feature/123-phase1-gates",
            base_ref="main",
            is_draft=True,
            action="opened",
        )
    )

    assert contract.linked_issue == 123


def test_branch_pr_gate_accepts_documentation_branch_bound_to_issue() -> None:
    contract = validate_branch_pr_gate(
        PullRequestState(
            body=pr_body(123),
            head_ref="documentation/123-docs-only-change",
            base_ref="main",
            is_draft=True,
            action="opened",
        )
    )

    assert contract.linked_issue == 123


def test_pr_without_linked_issue_fails() -> None:
    body = pr_body(123).replace("Closes #123", "No issue yet")

    with pytest.raises(ContractError, match="Linked Issue"):
        validate_branch_pr_gate(
            PullRequestState(
                body=body,
                head_ref="feature/123-phase1-gates",
                base_ref="main",
                is_draft=True,
                action="opened",
            )
        )


def test_wrong_branch_issue_binding_fails() -> None:
    with pytest.raises(ContractError, match="does not match"):
        validate_branch_pr_gate(
            PullRequestState(
                body=pr_body(123),
                head_ref="feature/999-phase1-gates",
                base_ref="main",
                is_draft=True,
                action="opened",
            )
        )


def test_formal_development_pr_must_open_as_draft() -> None:
    with pytest.raises(ContractError, match="draft"):
        validate_branch_pr_gate(
            PullRequestState(
                body=pr_body(123),
                head_ref="feature/123-phase1-gates",
                base_ref="main",
                is_draft=False,
                action="opened",
            )
        )


def test_main_branch_cannot_be_head_branch() -> None:
    with pytest.raises(ContractError, match="head branch"):
        validate_branch_pr_gate(
            PullRequestState(
                body=pr_body(123),
                head_ref="main",
                base_ref="main",
                is_draft=True,
                action="opened",
            )
        )

