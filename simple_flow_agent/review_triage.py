from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from simple_flow_agent.drafts import Draft


class Relationship(StrEnum):
    CURRENT = "CURRENT"
    SUBISSUE = "SUBISSUE"
    NEW_ISSUE = "NEW ISSUE"


class MergeImpact(StrEnum):
    BLOCKING = "BLOCKING"
    FOLLOW_UP = "FOLLOW-UP"


class TriageStage(StrEnum):
    DRAFT = "DRAFT"
    DELIVERY = "DELIVERY"


class TriageResolution(StrEnum):
    SUPERSEDE_DRAFT = "SUPERSEDE_DRAFT"
    CREATE_CHILD_DRAFT = "CREATE_CHILD_DRAFT"
    CREATE_INDEPENDENT_DRAFT = "CREATE_INDEPENDENT_DRAFT"
    PATCH_CURRENT_PR = "PATCH_CURRENT_PR"
    CREATE_LINKED_FOLLOW_UP = "CREATE_LINKED_FOLLOW_UP"
    CREATE_INDEPENDENT_FOLLOW_UP = "CREATE_INDEPENDENT_FOLLOW_UP"


RESOLUTION_ROUTES = {
    TriageResolution.SUPERSEDE_DRAFT.value: "PUBLISH_REVISED_DRAFT",
    TriageResolution.CREATE_CHILD_DRAFT.value: "CREATE_LINKED_SUBISSUE",
    TriageResolution.CREATE_INDEPENDENT_DRAFT.value: "CREATE_INDEPENDENT_ISSUE",
    TriageResolution.PATCH_CURRENT_PR.value: "UPDATE_CURRENT_PR",
    TriageResolution.CREATE_LINKED_FOLLOW_UP.value: "CREATE_LINKED_FOLLOW_UP",
    TriageResolution.CREATE_INDEPENDENT_FOLLOW_UP.value: "CREATE_INDEPENDENT_FOLLOW_UP",
}


@dataclass(frozen=True)
class ReviewTriageResult:
    relationship: str
    merge_impact: str
    source_issue: int | None
    source_pr: int | None
    reason: str
    decision_id: str | None = None
    target_draft_id: str | None = None
    stage: str = TriageStage.DELIVERY.value
    resolution: str | None = None

    def applies_to(self, draft: Draft) -> bool:
        if self.target_draft_id:
            return draft.draft_id == self.target_draft_id
        return (
            draft.source_issue == self.source_issue
            and draft.source_pr == self.source_pr
        )


def classify_review_finding(
    *,
    relationship: str,
    merge_impact: str,
    source_issue: int | None,
    source_pr: int | None,
    reason: str,
    decision_id: str | None = None,
    target_draft_id: str | None = None,
    stage: str = TriageStage.DELIVERY.value,
    resolution: str | None = None,
) -> ReviewTriageResult:
    normalized_relationship = Relationship(relationship).value
    normalized_impact = MergeImpact(merge_impact).value
    if not reason.strip():
        raise ValueError("Review-Triage reason must be non-empty.")
    normalized_stage = TriageStage(stage).value
    normalized_resolution = TriageResolution(resolution).value if resolution else None
    if normalized_stage == TriageStage.DRAFT.value and not target_draft_id:
        raise ValueError("DRAFT Review-Triage decisions require a target draft ID.")
    if normalized_stage == TriageStage.DRAFT.value and not normalized_resolution:
        raise ValueError("DRAFT Review-Triage decisions require an explicit resolution.")
    if normalized_stage == TriageStage.DELIVERY.value and (source_issue is None or source_pr is None):
        raise ValueError("DELIVERY Review-Triage decisions require source Issue and PR values.")
    return ReviewTriageResult(
        relationship=normalized_relationship,
        merge_impact=normalized_impact,
        source_issue=int(source_issue) if source_issue is not None else None,
        source_pr=int(source_pr) if source_pr is not None else None,
        reason=reason.strip(),
        decision_id=_optional_text(decision_id),
        target_draft_id=_optional_text(target_draft_id),
        stage=normalized_stage,
        resolution=normalized_resolution,
    )


def route_for_resolution(resolution: str | None) -> str:
    if not resolution:
        raise ValueError("Review-Triage decision must include an explicit resolution.")
    try:
        return RESOLUTION_ROUTES[TriageResolution(resolution).value]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unsupported Review-Triage resolution: {resolution}") from exc


def review_triage_from_data(raw: dict[str, object]) -> ReviewTriageResult:
    return classify_review_finding(
        relationship=str(raw["relationship"]),
        merge_impact=str(raw["merge_impact"]),
        source_issue=_optional_int(raw.get("source_issue")),
        source_pr=_optional_int(raw.get("source_pr")),
        reason=str(raw["reason"]),
        decision_id=_optional_text(raw.get("decision_id")),
        target_draft_id=_optional_text(raw.get("target_draft_id")),
        stage=str(raw.get("stage", TriageStage.DELIVERY.value)),
        resolution=_optional_text(raw.get("resolution")),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)

