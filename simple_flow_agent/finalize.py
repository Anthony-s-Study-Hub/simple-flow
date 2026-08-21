from __future__ import annotations

from dataclasses import dataclass, field


class FinalizeBlocked(RuntimeError):
    """Raised when PR-Finalize must stop on an objective blocker."""


@dataclass(frozen=True)
class PRState:
    exists: bool
    open: bool
    draft: bool
    required_checks: dict[str, bool]
    unresolved_conversations: int
    commits_after_human_review: int
    linked_issue_closed: bool
    head_branch_deleted: bool
    project_item_updated: bool

    @classmethod
    def ready(
        cls,
        *,
        required_checks: dict[str, bool] | None = None,
        unresolved_conversations: int = 0,
        commits_after_human_review: int = 0,
    ) -> "PRState":
        return cls(
            exists=True,
            open=True,
            draft=False,
            required_checks=required_checks
            if required_checks is not None
            else {"phase1-gates": True, "phase1-tests": True},
            unresolved_conversations=unresolved_conversations,
            commits_after_human_review=commits_after_human_review,
            linked_issue_closed=False,
            head_branch_deleted=False,
            project_item_updated=False,
        )


@dataclass(frozen=True)
class FinalizeResult:
    can_merge: bool
    required_cleanup: list[str] = field(default_factory=list)


def pre_merge_check(state: PRState, *, authorized: bool) -> FinalizeResult:
    if not authorized:
        raise FinalizeBlocked("Missing explicit PR-Finalize human authorization.")
    if not state.exists:
        raise FinalizeBlocked("Pull request does not exist.")
    if not state.open:
        raise FinalizeBlocked("Pull request is not open.")
    if state.draft:
        raise FinalizeBlocked("Pull request is still draft.")
    failed_checks = [name for name, passed in state.required_checks.items() if not passed]
    if failed_checks:
        raise FinalizeBlocked("Required CI checks failed: " + ", ".join(failed_checks))
    if state.unresolved_conversations:
        raise FinalizeBlocked("Pull request has unresolved review conversations.")
    if state.commits_after_human_review:
        raise FinalizeBlocked("New commits appeared after human review.")
    return FinalizeResult(
        can_merge=True,
        required_cleanup=[
            "confirm_linked_issue_closed",
            "confirm_head_branch_deleted",
            "confirm_project_item_updated",
        ],
    )

