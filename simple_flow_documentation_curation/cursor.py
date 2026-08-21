from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path

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


class CurationCursorStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.committed_path = self.root / "curation-cursor.json"
        self.pending_path = self.root / "pending-curation-cursor.json"

    def read_committed(self) -> CurationCursor:
        return self._read(self.committed_path)

    def write_committed(self, cursor: CurationCursor) -> None:
        self._write(self.committed_path, cursor)

    def read_pending(self) -> CurationCursor:
        return self._read(self.pending_path)

    def write_pending(self, cursor: CurationCursor) -> None:
        self._write(self.pending_path, cursor)

    def finalize_pending(self, *, documentation_pr_merged: bool) -> CurationCursor:
        current = self.read_committed()
        pending = self.read_pending()
        committed = commit_pending_cursor(
            current=current,
            pending=pending,
            documentation_pr_merged=documentation_pr_merged,
        )
        if committed != current:
            self.write_committed(committed)
        return committed

    def _read(self, path: Path) -> CurationCursor:
        if not path.exists():
            return EMPTY_CURSOR
        return CurationCursor.from_json_data(json.loads(path.read_text(encoding="utf-8")))

    def _write(self, path: Path, cursor: CurationCursor) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cursor.to_json_data(), indent=2) + "\n", encoding="utf-8")
