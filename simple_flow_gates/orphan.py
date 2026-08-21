from __future__ import annotations

from dataclasses import dataclass

from simple_flow_gates.branch_pr import MAIN_BRANCHES


@dataclass(frozen=True)
class BranchState:
    name: str
    commits_ahead: int
    has_open_pr: bool


def find_orphan_branches(branches: list[BranchState]) -> list[BranchState]:
    return [
        branch
        for branch in branches
        if branch.name not in MAIN_BRANCHES
        and branch.commits_ahead > 0
        and not branch.has_open_pr
    ]

