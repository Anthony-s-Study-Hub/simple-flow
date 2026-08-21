from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from simple_flow_documentation_curation.models import WorkItem


class MappingStatus(Enum):
    KNOWN_COMPONENT = "KNOWN_COMPONENT"
    MULTIPLE_COMPONENTS = "MULTIPLE_COMPONENTS"
    UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"


@dataclass(frozen=True)
class ComponentRule:
    component_id: str
    name: str
    labels: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    evidence_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentMapping:
    status: MappingStatus
    component_ids: tuple[str, ...]
    reasons: tuple[str, ...]


def map_work_item_to_components(item: WorkItem, rules: list[ComponentRule]) -> ComponentMapping:
    matches: dict[str, list[str]] = {}
    labels = set(item.labels)

    for rule in rules:
        reasons: list[str] = []
        if labels.intersection(rule.labels):
            reasons.append("label")
        if _matches_path(item.changed_files, rule.paths):
            reasons.append("path")
        if _matches_path(item.changed_files, rule.docs):
            reasons.append("document")
        if _matches_path(item.references + item.closes + item.related_prs, rule.evidence_prefixes):
            reasons.append("evidence")
        if reasons:
            matches[rule.component_id] = reasons

    component_ids = tuple(sorted(matches))
    if not component_ids:
        return ComponentMapping(MappingStatus.UNKNOWN_COMPONENT, (), ())
    if len(component_ids) > 1:
        return ComponentMapping(
            MappingStatus.MULTIPLE_COMPONENTS,
            component_ids,
            tuple(f"{component}:{','.join(matches[component])}" for component in component_ids),
        )
    return ComponentMapping(
        MappingStatus.KNOWN_COMPONENT,
        component_ids,
        tuple(matches[component_ids[0]]),
    )


def _matches_path(values: tuple[str, ...], prefixes: tuple[str, ...]) -> bool:
    normalized = tuple(value.replace("\\", "/") for value in values)
    return any(
        value == prefix.rstrip("/") or value.startswith(prefix.replace("\\", "/"))
        for value in normalized
        for prefix in prefixes
    )
