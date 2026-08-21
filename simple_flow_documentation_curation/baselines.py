from __future__ import annotations

from dataclasses import dataclass
import re


PROJECT_SECTIONS = (
    "Project Goal",
    "Global Principles",
    "High-Level Architecture",
    "Cross-Component Rules",
    "Current Stage",
    "Component Index",
)

COMPONENT_SECTIONS = (
    "Role",
    "Current Architecture",
    "Locked Decisions",
    "Interfaces / Contracts",
    "Constraints / Known Limits",
    "Current Development State",
)

DECISION_FIELDS = (
    "Decision",
    "Reason",
    "Constraint / Consequence",
    "Status",
    "Supersedes",
    "Evidence",
    "Effective Date",
)


class BaselineSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class ComponentIndexEntry:
    component_id: str
    component_name: str
    role: str
    baseline_document: str
    status: str
    last_updated: str


@dataclass(frozen=True)
class ProjectBaseline:
    version: str
    last_updated: str
    components: dict[str, ComponentIndexEntry]


@dataclass(frozen=True)
class LockedDecision:
    decision_id: str
    decision: str
    reason: str
    constraint_consequence: str
    status: str
    supersedes: str
    evidence: tuple[str, ...]
    effective_date: str


@dataclass(frozen=True)
class ComponentBaseline:
    component_id: str
    version: str
    last_updated: str
    decisions: dict[str, LockedDecision]


def parse_project_baseline(text: str) -> ProjectBaseline:
    _require_heading(text, "# High-Level Project Baseline")
    sections = _sections(text)
    _require_section_order(sections, PROJECT_SECTIONS)
    return ProjectBaseline(
        version=_metadata(text, "Version"),
        last_updated=_metadata(text, "Last Updated"),
        components=_parse_component_index(sections["Component Index"]),
    )


def parse_component_baseline(text: str) -> ComponentBaseline:
    if not text.lstrip().startswith("# Component Baseline:"):
        raise BaselineSchemaError("component baseline heading is missing")
    sections = _sections(text)
    _require_section_order(sections, COMPONENT_SECTIONS)
    return ComponentBaseline(
        component_id=_metadata(text, "Component ID"),
        version=_metadata(text, "Version"),
        last_updated=_metadata(text, "Last Updated"),
        decisions=_parse_decisions(sections["Locked Decisions"]),
    )


def _require_heading(text: str, heading: str) -> None:
    if not text.lstrip().startswith(heading):
        raise BaselineSchemaError(f"expected heading {heading}")


def _sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^## (?P<name>.+)$", text, re.MULTILINE))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group("name").strip()] = text[start:end].strip()
    return result


def _require_section_order(sections: dict[str, str], expected: tuple[str, ...]) -> None:
    observed = tuple(sections)
    if observed != expected:
        raise BaselineSchemaError(
            f"section order must be {', '.join(expected)}; observed {', '.join(observed)}"
        )


def _metadata(text: str, field: str) -> str:
    match = re.search(rf"^{re.escape(field)}:\s*(?P<value>.*)$", text, re.MULTILINE)
    if not match:
        raise BaselineSchemaError(f"missing metadata field: {field}")
    value = match.group("value").strip()
    if not value:
        raise BaselineSchemaError(f"empty metadata field: {field}")
    return value


def _parse_component_index(text: str) -> dict[str, ComponentIndexEntry]:
    rows = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    expected_header = (
        "Component ID",
        "Component Name",
        "Role",
        "Baseline Document",
        "Status",
        "Last Updated",
    )
    if len(rows) < 2 or _cells(rows[0]) != expected_header:
        raise BaselineSchemaError("Component Index fields do not match the fixed schema")

    components: dict[str, ComponentIndexEntry] = {}
    for row in rows[2:]:
        cells = _cells(row)
        if len(cells) != len(expected_header):
            raise BaselineSchemaError("Component Index row does not match the fixed schema")
        entry = ComponentIndexEntry(*cells)
        if not entry.component_id:
            raise BaselineSchemaError("Component Index row is missing Component ID")
        if entry.component_id in components:
            raise BaselineSchemaError(f"duplicate Component ID: {entry.component_id}")
        components[entry.component_id] = entry
    return components


def _parse_decisions(text: str) -> dict[str, LockedDecision]:
    decisions: dict[str, LockedDecision] = {}
    blocks = re.split(r"(?=^### Decision )", text, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        heading = re.match(r"^### Decision (?P<id>D-\d+)", block)
        if not heading:
            raise BaselineSchemaError("Locked Decisions entries must start with ### Decision D-000")
        decision_id = heading.group("id")
        fields = _field_map(block)
        missing = [field for field in DECISION_FIELDS if field not in fields]
        if missing:
            raise BaselineSchemaError(f"decision {decision_id} missing field(s): {', '.join(missing)}")
        if decision_id in decisions:
            raise BaselineSchemaError(f"duplicate Decision ID: {decision_id}")
        status = fields["Status"]
        if status not in {"ACTIVE", "SUPERSEDED"}:
            raise BaselineSchemaError(f"decision {decision_id} has invalid Status: {status}")
        decisions[decision_id] = LockedDecision(
            decision_id=decision_id,
            decision=fields["Decision"],
            reason=fields["Reason"],
            constraint_consequence=fields["Constraint / Consequence"],
            status=status,
            supersedes=fields["Supersedes"],
            evidence=tuple(
                value.strip()
                for value in fields["Evidence"].split(",")
                if value.strip()
            ),
            effective_date=fields["Effective Date"],
        )
    return decisions


def _field_map(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith("###"):
            continue
        name, value = line.split(":", 1)
        fields[name.strip()] = value.strip()
    return fields


def _cells(row: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in row.strip("|").split("|"))
