from __future__ import annotations

from typing import Any

from simple_flow_documentation_curation.models import (
    CommitRef,
    DiscussionComment,
    NormalizedHistoryPackage,
    Review,
    WorkItem,
    WorkItemKind,
)


def normalize_history(raw: dict[str, Any]) -> NormalizedHistoryPackage:
    """Convert raw GitHub-like data into the stable Phase 5 history package."""
    issues = [
        _item_from_issue(item)
        for item in raw.get("issues", ())
    ]
    prs = [
        _item_from_pull_request(item)
        for item in raw.get("pull_requests", ())
    ]
    commits = _commits(raw)
    work_items = tuple(sorted(issues + prs, key=lambda item: (item.updated_at, item.id)))
    return NormalizedHistoryPackage(
        repository=str(raw.get("repository", "")),
        collected_at=str(raw.get("collected_at", "")),
        work_items=work_items,
        commits=commits,
    )


def _item_from_issue(raw: dict[str, Any]) -> WorkItem:
    number = int(raw["number"])
    return WorkItem(
        id=f"issue:{number}",
        kind=WorkItemKind.ISSUE,
        number=number,
        title=str(raw.get("title", "")),
        state=str(raw.get("state", "")),
        updated_at=str(raw.get("updated_at", "")),
        body=str(raw.get("body", "")),
        labels=_strings(raw.get("labels", ())),
        milestone=str(raw.get("milestone", "")),
        roadmap_target=str(raw.get("roadmap_target", "")),
        closed_at=str(raw.get("closed_at", "")),
        reopened=bool(raw.get("reopened", False)) or _has_timeline_event(raw, "reopened"),
    )


def _item_from_pull_request(raw: dict[str, Any]) -> WorkItem:
    number = int(raw["number"])
    return WorkItem(
        id=f"pr:{number}",
        kind=WorkItemKind.PULL_REQUEST,
        number=number,
        title=str(raw.get("title", "")),
        state=str(raw.get("state", "")),
        updated_at=str(raw.get("updated_at", "")),
        body=str(raw.get("body", "")),
        labels=_strings(raw.get("labels", ())),
        milestone=str(raw.get("milestone", "")),
        roadmap_target=str(raw.get("roadmap_target", "")),
        changed_files=_strings(raw.get("changed_files", ())),
        merged_at=str(raw.get("merged_at", "")),
        closed_at=str(raw.get("closed_at", "")),
        reviews=tuple(
            Review(
                review_id=str(review.get("id", "")),
                state=str(review.get("state", "")),
                submitted_at=str(review.get("submitted_at", "")),
                body=str(review.get("body", "")),
                url=str(review.get("url", "")),
            )
            for review in raw.get("reviews", ())
        ),
        comments=tuple(
            DiscussionComment(
                comment_id=str(comment.get("id", "")),
                body=str(comment.get("body", "")),
                created_at=str(comment.get("created_at", "")),
                url=str(comment.get("url", "")),
            )
            for comment in raw.get("comments", ())
        ),
    )


def _strings(values: Any) -> tuple[str, ...]:
    return tuple(str(value) for value in values or () if str(value))


def _commits(raw: dict[str, Any]) -> tuple[CommitRef, ...]:
    commits: dict[str, CommitRef] = {}
    for item in raw.get("commits", ()):
        if item.get("sha"):
            commits[str(item["sha"])] = CommitRef(
                sha=str(item["sha"]),
                url=str(item.get("url", "")),
            )
    for pr in raw.get("pull_requests", ()):
        for item in pr.get("commits", ()):
            if item.get("sha"):
                commits[str(item["sha"])] = CommitRef(
                    sha=str(item["sha"]),
                    url=str(item.get("url", "")),
                )
    return tuple(commits[sha] for sha in sorted(commits))


def _has_timeline_event(raw: dict[str, Any], event_name: str) -> bool:
    return any(
        str(event.get("event", "")).lower() == event_name
        for event in raw.get("timeline", ())
    )
