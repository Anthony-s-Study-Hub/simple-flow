from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from simple_flow_agent.delivery import (
    DeliveryBlocked,
    DeliveryRecord,
    DeliveryTarget,
    prepare_delivery,
    ready_for_review,
)
from simple_flow_agent.drafts import DraftStore
from simple_flow_agent.implementation_plan import plan_implementation


@dataclass
class FakeGateway:
    issue_number: int = 54
    pr_number: int = 81
    checks_pass: bool = True
    created_issue: int = 0
    created_branch: int = 0
    created_pr: int = 0
    marked_ready: int = 0

    def ensure_issue(self, _target: DeliveryTarget) -> tuple[int, str]:
        self.created_issue += 1
        return self.issue_number, f"https://github.example/issues/{self.issue_number}"

    def ensure_branch(self, _target: DeliveryTarget, issue_number: int) -> str:
        self.created_branch += 1
        return f"feature/{issue_number}-deterministic-delivery"

    def ensure_draft_pr(self, _target: DeliveryTarget, issue_number: int, branch: str) -> tuple[int, str]:
        self.created_pr += 1
        return self.pr_number, f"https://github.example/pull/{self.pr_number}"

    def review_state(self, _record: DeliveryRecord) -> tuple[bool, tuple[str, ...]]:
        return self.checks_pass, () if self.checks_pass else ("tdd-green-replay",)

    def mark_ready(self, _record: DeliveryRecord) -> None:
        self.marked_ready += 1


def _target(tmp_path: Path, *, route: str = "CREATE_INDEPENDENT_ISSUE") -> DeliveryTarget:
    store = DraftStore(tmp_path / "drafts")
    draft = store.create_feature(
        summary="Make delivery deterministic.",
        requirements=["Open a draft PR before implementation."],
        acceptance_criteria=["CI must pass before review."],
        scope=["simple_flow_agent/"],
        out_of_scope=["Automatic merging"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={"implementation_route": route},
    )
    plan = plan_implementation(store, draft_id=draft.draft_id)
    return DeliveryTarget.from_plan(plan, draft, repository="owner/repo", base_branch="main")


def test_prepare_delivery_creates_the_issue_branch_and_draft_pr_once(tmp_path: Path) -> None:
    target = _target(tmp_path)
    gateway = FakeGateway()

    record = prepare_delivery(target, gateway=gateway)
    repeated = prepare_delivery(target, gateway=gateway, existing=record)

    assert record.status == "DRAFT_PR_OPEN"
    assert record.issue_number == 54
    assert record.pr_number == 81
    assert gateway.created_issue == 1
    assert gateway.created_branch == 1
    assert gateway.created_pr == 1
    assert repeated == record


def test_prepare_delivery_reuses_the_current_pr_route_without_new_artifacts(tmp_path: Path) -> None:
    target = _target(tmp_path, route="UPDATE_CURRENT_PR")
    target = DeliveryTarget(
        **{**target.to_json_data(), "source_issue": 12, "source_pr": 34}
    )
    gateway = FakeGateway()

    record = prepare_delivery(target, gateway=gateway)

    assert record.issue_number == 12
    assert record.pr_number == 34
    assert gateway.created_issue == gateway.created_branch == gateway.created_pr == 0


def test_ready_for_review_requires_passing_real_required_checks(tmp_path: Path) -> None:
    target = _target(tmp_path)
    gateway = FakeGateway(checks_pass=False)
    record = prepare_delivery(target, gateway=gateway)

    with pytest.raises(DeliveryBlocked, match="tdd-green-replay"):
        ready_for_review(record, gateway=gateway)

    gateway.checks_pass = True
    ready = ready_for_review(record, gateway=gateway)

    assert ready.status == "REVIEW_READY"
    assert gateway.marked_ready == 1
