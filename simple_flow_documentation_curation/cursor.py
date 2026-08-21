from __future__ import annotations

from collections.abc import Iterable

from simple_flow_documentation_curation.models import CurationCursor, NormalizedHistoryPackage, WorkItem


EMPTY_CURSOR = CurationCursor(updated_at="", stable_id="")


def pending_cursor_for(package: NormalizedHistoryPackage) -> CurationCursor:
    if not package.work_items:
        return EMPTY_CURSOR
    latest = max(package.work_items, key=lambda item: (item.updated_at, item.id))
    return CurationCursor(updated_at=latest.updated_at, stable_id=latest.id)


def filter_items_since(items: Iterable[WorkItem], cursor: CurationCursor) -> list[WorkItem]:
    return [
        item
        for item in sorted(items, key=lambda value: (value.updated_at, value.id))
        if (item.updated_at, item.id) > (cursor.updated_at, cursor.stable_id)
    ]


def commit_pending_cursor(
    *,
    current: CurationCursor,
    pending: CurationCursor,
    documentation_pr_merged: bool,
) -> CurationCursor:
    if not documentation_pr_merged:
        return current
    if (pending.updated_at, pending.stable_id) < (current.updated_at, current.stable_id):
        return current
    return pending
