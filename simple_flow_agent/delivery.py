from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from simple_flow_agent.drafts import Draft
from simple_flow_agent.implementation_plan import ImplementationPlan


class DeliveryBlocked(RuntimeError):
    """Raised when an objective delivery condition is not satisfied."""


@dataclass(frozen=True)
class DeliveryTarget:
    draft_id: str
    work_type: str
    summary: str
    route: str
    repository: str
    base_branch: str
    source_issue: int | None
    source_pr: int | None

    @classmethod
    def from_plan(
        cls,
        plan: ImplementationPlan,
        draft: Draft,
        *,
        repository: str,
        base_branch: str,
    ) -> "DeliveryTarget":
        return cls(
            draft_id=plan.draft_id,
            work_type=plan.work_type,
            summary=plan.summary,
            route=plan.route,
            repository=repository,
            base_branch=base_branch,
            source_issue=draft.source_issue,
            source_pr=draft.source_pr,
        )

    def to_json_data(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryRecord:
    schema_version: str
    draft_id: str
    route: str
    repository: str
    base_branch: str
    issue_number: int
    issue_url: str
    branch: str | None
    pr_number: int
    pr_url: str
    status: str

    def to_json_data(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_json_data(cls, raw: dict[str, object]) -> "DeliveryRecord":
        return cls(
            schema_version=str(raw["schema_version"]),
            draft_id=str(raw["draft_id"]),
            route=str(raw["route"]),
            repository=str(raw["repository"]),
            base_branch=str(raw["base_branch"]),
            issue_number=int(raw["issue_number"]),
            issue_url=str(raw["issue_url"]),
            branch=_optional_text(raw.get("branch")),
            pr_number=int(raw["pr_number"]),
            pr_url=str(raw["pr_url"]),
            status=str(raw["status"]),
        )


class DeliveryGateway(Protocol):
    def ensure_issue(self, target: DeliveryTarget) -> tuple[int, str]: ...

    def ensure_branch(self, target: DeliveryTarget, issue_number: int) -> str: ...

    def ensure_draft_pr(
        self, target: DeliveryTarget, issue_number: int, branch: str
    ) -> tuple[int, str]: ...

    def review_state(self, record: DeliveryRecord) -> tuple[bool, tuple[str, ...]]: ...

    def mark_ready(self, record: DeliveryRecord) -> None: ...


def prepare_delivery(
    target: DeliveryTarget,
    *,
    gateway: DeliveryGateway,
    existing: DeliveryRecord | None = None,
) -> DeliveryRecord:
    if existing:
        _validate_existing(target, existing)
        return existing
    if target.route == "UPDATE_CURRENT_PR":
        if target.source_issue is None or target.source_pr is None:
            raise DeliveryBlocked("UPDATE_CURRENT_PR requires source Issue and PR references.")
        return DeliveryRecord(
            schema_version="simple-flow-delivery.v1",
            draft_id=target.draft_id,
            route=target.route,
            repository=target.repository,
            base_branch=target.base_branch,
            issue_number=target.source_issue,
            issue_url=f"https://github.com/{target.repository}/issues/{target.source_issue}",
            branch=None,
            pr_number=target.source_pr,
            pr_url=f"https://github.com/{target.repository}/pull/{target.source_pr}",
            status="DRAFT_PR_OPEN",
        )

    issue_number, issue_url = gateway.ensure_issue(target)
    branch = gateway.ensure_branch(target, issue_number)
    pr_number, pr_url = gateway.ensure_draft_pr(target, issue_number, branch)
    return DeliveryRecord(
        schema_version="simple-flow-delivery.v1",
        draft_id=target.draft_id,
        route=target.route,
        repository=target.repository,
        base_branch=target.base_branch,
        issue_number=issue_number,
        issue_url=issue_url,
        branch=branch,
        pr_number=pr_number,
        pr_url=pr_url,
        status="DRAFT_PR_OPEN",
    )


def ready_for_review(record: DeliveryRecord, *, gateway: DeliveryGateway) -> DeliveryRecord:
    if record.status != "DRAFT_PR_OPEN":
        raise DeliveryBlocked(f"Delivery {record.draft_id} is not an open draft PR.")
    passed, failing = gateway.review_state(record)
    if not passed:
        detail = ", ".join(failing) if failing else "required checks are pending or unavailable"
        raise DeliveryBlocked(f"PR #{record.pr_number} is not ready: {detail}.")
    gateway.mark_ready(record)
    passed, failing = gateway.review_state(record)
    if not passed:
        detail = ", ".join(failing) if failing else "required checks are pending or unavailable"
        raise DeliveryBlocked(f"PR #{record.pr_number} did not pass checks after becoming review-ready: {detail}.")
    return DeliveryRecord(**{**record.to_json_data(), "status": "REVIEW_READY"})


def _validate_existing(target: DeliveryTarget, record: DeliveryRecord) -> None:
    if record.schema_version != "simple-flow-delivery.v1":
        raise DeliveryBlocked("Unsupported delivery record schema.")
    for name in ("draft_id", "route", "repository", "base_branch"):
        if getattr(record, name) != getattr(target, name):
            raise DeliveryBlocked(f"Existing delivery record {name} does not match the selected plan.")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
