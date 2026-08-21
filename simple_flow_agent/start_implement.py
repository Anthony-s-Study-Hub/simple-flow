from __future__ import annotations

from dataclasses import dataclass

from simple_flow_agent.drafts import Draft, DraftStore
from simple_flow_agent.review_triage import ReviewTriageResult
from simple_flow_gates.contracts import WorkType


class AmbiguousReviewTriageError(RuntimeError):
    """Raised when Start-Implement cannot safely pick one review context."""


@dataclass(frozen=True)
class StartImplementPlan:
    draft_id: str
    work_type: str
    summary: str
    path: str
    tdd_required: bool
    actions: list[str]
    stop_point: str = "HUMAN_PR_REVIEW"


def select_start_path(
    store: DraftStore,
    draft_id: str,
    triage_results: list[ReviewTriageResult] | None = None,
) -> StartImplementPlan:
    draft = store.read(draft_id)
    relevant_triage = [
        triage
        for triage in (triage_results or [])
        if triage.applies_to(draft)
    ]
    if len(relevant_triage) > 1:
        raise AmbiguousReviewTriageError(
            f"Multiple Review-Triage results match {draft_id}; Start-Implement must stop."
        )

    if relevant_triage:
        triage = relevant_triage[0]
        relationship = triage.relationship.replace(" ", "_")
        impact = triage.merge_impact.replace("-", "_")
        path = f"REVIEW_{relationship}_{impact}"
    elif draft.work_type == WorkType.FEATURE.value:
        path = "FEATURE_NORMAL"
    elif draft.work_type == WorkType.DOCUMENTATION.value:
        path = "DOCUMENTATION_NORMAL"
    else:
        raise ValueError(f"Unsupported draft work type: {draft.work_type}")

    return StartImplementPlan(
        draft_id=draft.draft_id,
        work_type=draft.work_type,
        summary=_summary(draft),
        path=path,
        tdd_required=draft.work_type == WorkType.FEATURE.value,
        actions=_actions_for(draft, path),
    )


def _summary(draft: Draft) -> str:
    if draft.work_type == WorkType.FEATURE.value:
        return draft.fields["Summary"]
    return draft.fields["Change"]


def _actions_for(draft: Draft, path: str) -> list[str]:
    base = ["publish_formal_issue", "create_bound_branch"]
    if draft.work_type == WorkType.DOCUMENTATION.value:
        return base + ["create_pull_request", "update_documentation", "wait_for_ci"]
    if path.startswith("REVIEW_CURRENT"):
        return ["resume_current_pull_request", "run_red_green_tdd", "wait_for_ci"]
    if path.startswith("REVIEW_SUBISSUE"):
        return base + ["create_draft_pull_request", "run_red_green_tdd", "wait_for_ci"]
    if path.startswith("REVIEW_NEW_ISSUE"):
        return base + ["create_draft_pull_request", "run_red_green_tdd", "wait_for_ci"]
    return base + ["create_draft_pull_request", "run_red_green_tdd", "wait_for_ci"]

