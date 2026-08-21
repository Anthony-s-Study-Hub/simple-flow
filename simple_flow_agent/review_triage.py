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


@dataclass(frozen=True)
class ReviewTriageResult:
    relationship: str
    merge_impact: str
    source_issue: int
    source_pr: int
    reason: str

    def applies_to(self, draft: Draft) -> bool:
        return (
            draft.source_issue == self.source_issue
            and draft.source_pr == self.source_pr
        )


def classify_review_finding(
    *,
    relationship: str,
    merge_impact: str,
    source_issue: int,
    source_pr: int,
    reason: str,
) -> ReviewTriageResult:
    normalized_relationship = Relationship(relationship).value
    normalized_impact = MergeImpact(merge_impact).value
    if not reason.strip():
        raise ValueError("Review-Triage reason must be non-empty.")
    return ReviewTriageResult(
        relationship=normalized_relationship,
        merge_impact=normalized_impact,
        source_issue=int(source_issue),
        source_pr=int(source_pr),
        reason=reason.strip(),
    )

