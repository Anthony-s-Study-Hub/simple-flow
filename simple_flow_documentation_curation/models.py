from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class WorkItemKind(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pr"


class ProposalClassification(StrEnum):
    FINAL = "FINAL"
    SUPERSEDED = "SUPERSEDED"
    INTERMEDIATE = "INTERMEDIATE"
    ABANDONED = "ABANDONED"
    FOLLOW_UP = "FOLLOW_UP"
    IMPLEMENTATION_ONLY = "IMPLEMENTATION_ONLY"
    UNRESOLVED = "UNRESOLVED"


BASELINE_ACTIONS = {
    "ADD_DECISION",
    "UPDATE_DECISION",
    "SUPERSEDE_DECISION",
    "UPDATE_ARCHITECTURE",
    "UPDATE_INTERFACE",
    "UPDATE_CONSTRAINT",
    "UPDATE_DEVELOPMENT_STATE",
    "CREATE_COMPONENT_BASELINE",
    "UPDATE_COMPONENT_INDEX",
    "NO_CHANGE",
}


@dataclass(frozen=True)
class Review:
    review_id: str
    state: str
    submitted_at: str = ""
    body: str = ""
    url: str = ""


@dataclass(frozen=True)
class DiscussionComment:
    comment_id: str
    body: str = ""
    created_at: str = ""
    url: str = ""


@dataclass(frozen=True)
class WorkItem:
    id: str
    kind: WorkItemKind
    number: int
    title: str = ""
    state: str = ""
    updated_at: str = ""
    body: str = ""
    labels: tuple[str, ...] = ()
    milestone: str = ""
    roadmap_target: str = ""
    changed_files: tuple[str, ...] = ()
    merged_at: str = ""
    closed_at: str = ""
    reopened: bool = False
    reviews: tuple[Review, ...] = ()
    comments: tuple[DiscussionComment, ...] = ()
    related_prs: tuple[str, ...] = ()
    closes: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    existing_decision_ids: tuple[str, ...] = ()

    def with_relationships(
        self,
        *,
        related_prs: tuple[str, ...] | None = None,
        closes: tuple[str, ...] | None = None,
        references: tuple[str, ...] | None = None,
        existing_decision_ids: tuple[str, ...] | None = None,
    ) -> "WorkItem":
        return replace(
            self,
            related_prs=self.related_prs if related_prs is None else related_prs,
            closes=self.closes if closes is None else closes,
            references=self.references if references is None else references,
            existing_decision_ids=(
                self.existing_decision_ids
                if existing_decision_ids is None
                else existing_decision_ids
            ),
        )


@dataclass(frozen=True)
class CommitRef:
    sha: str
    url: str = ""


@dataclass(frozen=True)
class NormalizedHistoryPackage:
    repository: str
    collected_at: str
    work_items: tuple[WorkItem, ...]
    commits: tuple[CommitRef, ...] = ()

    def work_item(self, item_id: str) -> WorkItem:
        for item in self.work_items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    @property
    def item_ids(self) -> set[str]:
        return {item.id for item in self.work_items}

    @property
    def commit_shas(self) -> set[str]:
        return {commit.sha for commit in self.commits}

    def with_work_items(self, work_items: tuple[WorkItem, ...]) -> "NormalizedHistoryPackage":
        return replace(self, work_items=work_items)


@dataclass(frozen=True)
class CurationCursor:
    updated_at: str
    stable_id: str

    def to_json_data(self) -> dict[str, str]:
        return {"updated_at": self.updated_at, "stable_id": self.stable_id}

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> "CurationCursor":
        return cls(updated_at=str(data["updated_at"]), stable_id=str(data["stable_id"]))


@dataclass(frozen=True)
class DecisionProposal:
    decision_id: str
    component: str
    proposed_classification: str
    decision: str
    short_reason: str
    constraint_consequence: str
    supersedes: str
    exact_references: tuple[str, ...]
    affected_baseline_section: str
    proposed_baseline_action: str

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> "DecisionProposal":
        return cls(
            decision_id=str(data["decision_id"]),
            component=str(data["component"]),
            proposed_classification=str(data["proposed_classification"]),
            decision=str(data["decision"]),
            short_reason=str(data["short_reason"]),
            constraint_consequence=str(data["constraint_consequence"]),
            supersedes=str(data.get("supersedes", "")),
            exact_references=tuple(str(value) for value in data.get("exact_references", ())),
            affected_baseline_section=str(data["affected_baseline_section"]),
            proposed_baseline_action=str(data["proposed_baseline_action"]),
        )

    def to_json_data(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "component": self.component,
            "proposed_classification": self.proposed_classification,
            "decision": self.decision,
            "short_reason": self.short_reason,
            "constraint_consequence": self.constraint_consequence,
            "supersedes": self.supersedes,
            "exact_references": list(self.exact_references),
            "affected_baseline_section": self.affected_baseline_section,
            "proposed_baseline_action": self.proposed_baseline_action,
        }


@dataclass(frozen=True)
class DocumentationFinding:
    finding_id: str
    component: str
    finding_type: str
    conflict: str
    why_it_matters: str
    exact_references: tuple[str, ...]
    question: str
    affected_baseline_section: str
    blocking_impact: str

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> "DocumentationFinding":
        return cls(
            finding_id=str(data["finding_id"]),
            component=str(data["component"]),
            finding_type=str(data["finding_type"]),
            conflict=str(data["conflict"]),
            why_it_matters=str(data["why_it_matters"]),
            exact_references=tuple(str(value) for value in data.get("exact_references", ())),
            question=str(data["question"]),
            affected_baseline_section=str(data["affected_baseline_section"]),
            blocking_impact=str(data["blocking_impact"]),
        )

    def to_json_data(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "component": self.component,
            "finding_type": self.finding_type,
            "conflict": self.conflict,
            "why_it_matters": self.why_it_matters,
            "exact_references": list(self.exact_references),
            "question": self.question,
            "affected_baseline_section": self.affected_baseline_section,
            "blocking_impact": self.blocking_impact,
        }


@dataclass(frozen=True)
class NewComponentProposal:
    component_id: str
    component_name: str
    role: str
    responsibility_boundary: str
    parent_related_components: tuple[str, ...]
    reason_for_separation: str
    evidence: tuple[str, ...]
    suggested_baseline_path: str

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> "NewComponentProposal":
        return cls(
            component_id=str(data["component_id"]),
            component_name=str(data["component_name"]),
            role=str(data["role"]),
            responsibility_boundary=str(data["responsibility_boundary"]),
            parent_related_components=tuple(
                str(value) for value in data.get("parent_related_components", ())
            ),
            reason_for_separation=str(data["reason_for_separation"]),
            evidence=tuple(str(value) for value in data.get("evidence", ())),
            suggested_baseline_path=str(data["suggested_baseline_path"]),
        )

    def to_json_data(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_name": self.component_name,
            "role": self.role,
            "responsibility_boundary": self.responsibility_boundary,
            "parent_related_components": list(self.parent_related_components),
            "reason_for_separation": self.reason_for_separation,
            "evidence": list(self.evidence),
            "suggested_baseline_path": self.suggested_baseline_path,
        }


@dataclass(frozen=True)
class PatchOperation:
    operation: str
    target_component: str
    target_section: str
    reason: str
    payload: dict[str, Any]

    def to_json_data(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "target_component": self.target_component,
            "target_section": self.target_section,
            "reason": self.reason,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class CurationAnalysis:
    decisions: list[DecisionProposal]
    findings: list[DocumentationFinding]
    new_components: list[NewComponentProposal]
    proposed_baseline_operations: list[PatchOperation]
    pending_cursor: CurationCursor | None = None

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> "CurationAnalysis":
        cursor_data = data.get("pending_cursor")
        return cls(
            decisions=[
                DecisionProposal.from_json_data(item)
                for item in data.get("decisions", ())
            ],
            findings=[
                DocumentationFinding.from_json_data(item)
                for item in data.get("findings", ())
            ],
            new_components=[
                NewComponentProposal.from_json_data(item)
                for item in data.get("new_components", ())
            ],
            proposed_baseline_operations=[
                PatchOperation(
                    operation=str(item["operation"]),
                    target_component=str(item["target_component"]),
                    target_section=str(item["target_section"]),
                    reason=str(item["reason"]),
                    payload=dict(item.get("payload", {})),
                )
                for item in data.get("proposed_baseline_operations", ())
            ],
            pending_cursor=(
                None
                if cursor_data is None
                else CurationCursor.from_json_data(dict(cursor_data))
            ),
        )

    def with_operations(self, operations: list[PatchOperation]) -> "CurationAnalysis":
        return replace(self, proposed_baseline_operations=operations)

    def with_pending_cursor(self, cursor: CurationCursor) -> "CurationAnalysis":
        return replace(self, pending_cursor=cursor)

    def to_json_data(self) -> dict[str, Any]:
        return {
            "decisions": [decision.to_json_data() for decision in self.decisions],
            "findings": [finding.to_json_data() for finding in self.findings],
            "new_components": [
                component.to_json_data() for component in self.new_components
            ],
            "proposed_baseline_operations": [
                operation.to_json_data()
                for operation in self.proposed_baseline_operations
            ],
            "pending_cursor": (
                None if self.pending_cursor is None else self.pending_cursor.to_json_data()
            ),
        }
