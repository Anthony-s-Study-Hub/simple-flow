from __future__ import annotations

from collections import defaultdict
import re

from simple_flow_documentation_curation.models import NormalizedHistoryPackage, WorkItem, WorkItemKind


CLOSES_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(?P<number>\d+)",
    re.IGNORECASE,
)
REFERENCES_RE = re.compile(
    r"\b(?:ref(?:s|erences?)?)\s+#(?P<number>\d+)",
    re.IGNORECASE,
)
DECISION_RE = re.compile(r"\bD-\d+\b")


def resolve_relationships(package: NormalizedHistoryPackage) -> NormalizedHistoryPackage:
    related_prs: dict[str, list[str]] = defaultdict(list)
    resolved: list[WorkItem] = []

    for item in package.work_items:
        if item.kind != WorkItemKind.PULL_REQUEST:
            resolved.append(item)
            continue
        closes = tuple(_issue_id(number) for number in _numbers(CLOSES_RE, item.body))
        references = tuple(
            sorted(set(_issue_id(number) for number in _numbers(REFERENCES_RE, item.body)) - set(closes))
        )
        for issue_id in closes:
            related_prs[issue_id].append(item.id)
        resolved.append(
            item.with_relationships(
                closes=closes,
                references=references,
                existing_decision_ids=tuple(sorted(set(DECISION_RE.findall(item.body)))),
            )
        )

    final_items: list[WorkItem] = []
    for item in resolved:
        if item.kind == WorkItemKind.ISSUE:
            final_items.append(
                item.with_relationships(related_prs=tuple(sorted(set(related_prs[item.id]))))
            )
        else:
            final_items.append(item)

    return package.with_work_items(tuple(sorted(final_items, key=lambda item: (item.updated_at, item.id))))


def _numbers(pattern: re.Pattern[str], text: str) -> list[int]:
    return [int(match.group("number")) for match in pattern.finditer(text or "")]


def _issue_id(number: int) -> str:
    return f"issue:{number}"
