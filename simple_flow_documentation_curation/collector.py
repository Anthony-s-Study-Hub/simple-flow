from __future__ import annotations

from typing import Any

from simple_flow_documentation_curation.cursor import CurationCursor, filter_items_since
from simple_flow_documentation_curation.models import NormalizedHistoryPackage
from simple_flow_documentation_curation.normalizer import normalize_history
from simple_flow_documentation_curation.relationships import resolve_relationships


def collect_history(
    raw_history: dict[str, Any],
    *,
    since: CurationCursor | None = None,
) -> NormalizedHistoryPackage:
    """Collect deterministic history facts from a raw GitHub history snapshot."""
    package = resolve_relationships(normalize_history(raw_history))
    if since is None:
        return package
    return package.with_work_items(tuple(filter_items_since(package.work_items, since)))
