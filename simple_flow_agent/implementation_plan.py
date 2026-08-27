from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from simple_flow_agent.drafts import Draft, DraftStore
from simple_flow_gates.contracts import WorkType


class DraftSelectionError(RuntimeError):
    """Raised when structured state cannot select one safe implementation target."""


@dataclass(frozen=True)
class ImplementationIntent:
    tags: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()

    @classmethod
    def from_data(cls, raw: dict[str, object]) -> "ImplementationIntent":
        return cls(
            tags=_strings(raw.get("tags", []), "tags"),
            components=_strings(raw.get("components", []), "components"),
            terms=_strings(raw.get("terms", []), "terms"),
        )


@dataclass(frozen=True)
class ImplementationPlan:
    draft_id: str
    work_type: str
    summary: str
    route: str
    selection_reason: dict[str, object]
    actions: list[str]
    constraints: dict[str, object]
    stop_point: str = "HUMAN_PR_REVIEW"

    def to_json_data(self) -> dict[str, object]:
        return asdict(self)


def plan_implementation(
    store: DraftStore,
    *,
    draft_id: str | None = None,
    active_draft_id: str | None = None,
    intent: ImplementationIntent | None = None,
) -> ImplementationPlan:
    drafts = store.list()
    superseded_ids = {
        str(draft.execution["supersedes_draft_id"])
        for draft in drafts
        if draft.execution["supersedes_draft_id"]
    }
    eligible = [
        draft
        for draft in drafts
        if draft.execution["lifecycle"] == "READY" and draft.draft_id not in superseded_ids
    ]
    if draft_id:
        draft = _find_eligible(eligible, draft_id)
        reason = {"method": "explicit-draft-id", "draft_id": draft_id}
    elif intent and (intent.tags or intent.components or intent.terms):
        draft, reason = _select_by_intent(eligible, intent)
    elif active_draft_id:
        draft = _find_eligible(eligible, active_draft_id)
        reason = {"method": "active-draft", "draft_id": active_draft_id}
    elif len(eligible) == 1:
        draft = eligible[0]
        reason = {"method": "sole-eligible-draft", "draft_id": draft.draft_id}
    else:
        raise DraftSelectionError("No explicit draft, active draft, or structured intent selects one eligible draft.")

    route = str(draft.execution["implementation_route"])
    return ImplementationPlan(
        draft_id=draft.draft_id,
        work_type=draft.work_type,
        summary=_summary(draft),
        route=route,
        selection_reason=reason,
        actions=_actions_for(draft, route),
        constraints={
            "allowed_paths": _allowed_paths(draft),
            "tdd_required": draft.work_type == WorkType.FEATURE.value,
            "must_not_modify_draft": True,
            "must_not_merge": True,
        },
    )


def _select_by_intent(
    eligible: list[Draft], intent: ImplementationIntent
) -> tuple[Draft, dict[str, object]]:
    scored = sorted(
        ((_intent_score(draft, intent), draft) for draft in eligible),
        key=lambda item: (-item[0], -int(item[1].execution["priority"]), item[1].draft_id),
    )
    if not scored or scored[0][0] == 0:
        raise DraftSelectionError("Structured intent does not match an eligible draft.")
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] == best_score and int(scored[1][1].execution["priority"]) == int(best.execution["priority"]):
        raise DraftSelectionError("Eligible drafts are materially tied for the structured intent.")
    return best, {
        "method": "intent-match",
        "score": best_score,
        "matched_tags": sorted(set(intent.tags) & set(_lower(best.execution["intent_tags"]))),
        "matched_components": sorted(set(intent.components) & set(_lower(best.execution["components"]))),
    }


def _intent_score(draft: Draft, intent: ImplementationIntent) -> int:
    tags = set(_lower(draft.execution["intent_tags"]))
    components = set(_lower(draft.execution["components"]))
    summary = _summary(draft).lower()
    return (
        10 * len(set(intent.tags) & tags)
        + 20 * len(set(intent.components) & components)
        + len({term for term in intent.terms if term in summary})
    )


def _find_eligible(drafts: Iterable[Draft], draft_id: str) -> Draft:
    for draft in drafts:
        if draft.draft_id == draft_id:
            return draft
    raise DraftSelectionError(f"Draft {draft_id} is missing or is not eligible for implementation.")


def _summary(draft: Draft) -> str:
    return draft.fields["Summary"] if draft.work_type == WorkType.FEATURE.value else draft.fields["Change"]


def _allowed_paths(draft: Draft) -> list[str]:
    field = "Scope" if draft.work_type == WorkType.FEATURE.value else "Affected Project Documents"
    return [line.removeprefix("- ").strip() for line in draft.fields[field].splitlines() if line.strip()]


def _actions_for(draft: Draft, route: str) -> list[str]:
    if route == "UPDATE_CURRENT_PR":
        base = ["resume_current_pull_request"]
    elif route == "CREATE_LINKED_SUBISSUE":
        base = ["create_or_reuse_parent_issue", "create_linked_subissue", "create_bound_branch"]
    elif route in {"PUBLISH_REVISED_DRAFT", "CREATE_LINKED_FOLLOW_UP", "CREATE_INDEPENDENT_FOLLOW_UP", "CREATE_INDEPENDENT_ISSUE"}:
        base = ["create_or_reuse_issue", "create_bound_branch"]
    else:
        raise DraftSelectionError(f"Unsupported implementation route: {route}")
    if draft.work_type == WorkType.DOCUMENTATION.value:
        return base + ["author_documentation", "run_documentation_checks", "create_draft_pull_request"]
    return base + ["run_red_test", "implement_within_scope", "run_required_tests", "create_draft_pull_request"]


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Intent {name} must be a list of non-empty strings.")
    return tuple(item.strip().lower() for item in value)


def _lower(value: object) -> list[str]:
    return [str(item).lower() for item in list(value)]
