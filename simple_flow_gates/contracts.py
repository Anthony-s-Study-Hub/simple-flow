from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Iterable


class ContractError(ValueError):
    """Raised when a workflow contract is malformed."""


class WorkType(StrEnum):
    FEATURE = "FEATURE"
    DOCUMENTATION = "DOCUMENTATION"


FEATURE_FIELDS = [
    "Summary",
    "Requirements",
    "Acceptance Criteria",
    "Scope",
    "Out of Scope",
    "Documentation Impact",
    "Roadmap Target",
]

DOCUMENTATION_FIELDS = [
    "Change",
    "Reason",
    "Impact",
    "Supersedes",
    "Affected Project Documents",
    "Source PR / Decision Context",
]

PR_FIELDS = [
    "Linked Issue",
    "Implementation Summary",
    "Acceptance Criteria Evidence",
    "Changed Files / Scope",
    "Documentation Changes",
    "Important Technical Decisions",
    "Known Limitations",
]

LEGACY_WORK_TYPE_ALIASES = {
    "PROJECT_CHANGE": WorkType.DOCUMENTATION,
}
SPECIAL_ROADMAP_TARGETS = {
    "UNMAPPED",
    "DOCUMENTATION_REQUIRED",
    # Legacy spelling accepted for existing feature issues.
    "PROJECT_CHANGE_REQUIRED",
}
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TYPE_RE = re.compile(r"^\s*Type:\s*([A-Z_]+)\s*$", re.MULTILINE)
ISSUE_REF_RE = re.compile(r"(?:#|issues/)(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class IssueContract:
    work_type: WorkType
    fields: dict[str, str]

    @classmethod
    def parse(cls, body: str, roadmap_targets: Iterable[str] = ()) -> "IssueContract":
        type_match = TYPE_RE.search(body)
        if not type_match:
            raise ContractError("Issue body must include a top-level 'Type: ...' line.")

        work_type = normalize_work_type(type_match.group(1))

        expected_fields = fields_for_work_type(work_type)
        fields = _parse_ordered_fields(body, expected_fields)
        _reject_extra_top_level_headings(body, expected_fields)
        _require_non_empty(fields)

        if work_type == WorkType.FEATURE:
            _validate_roadmap_target(fields["Roadmap Target"], roadmap_targets)

        return cls(work_type=work_type, fields=fields)

    @property
    def scope_patterns(self) -> list[str]:
        if self.work_type == WorkType.DOCUMENTATION:
            return _list_items(self.fields["Affected Project Documents"])
        return _list_items(self.fields["Scope"])

    @property
    def documentation_impact(self) -> list[str]:
        if self.work_type == WorkType.DOCUMENTATION:
            return _list_items(self.fields["Affected Project Documents"])
        raw = self.fields["Documentation Impact"].strip()
        if raw.lower() == "none":
            return []
        return _list_items(raw)


@dataclass(frozen=True)
class PullRequestContract:
    fields: dict[str, str]
    linked_issue: int

    @classmethod
    def parse(cls, body: str) -> "PullRequestContract":
        fields = _parse_ordered_fields(body, PR_FIELDS)
        _reject_extra_top_level_headings(body, PR_FIELDS)
        _require_non_empty(fields)
        linked_issue = _extract_issue_number(fields["Linked Issue"])
        return cls(fields=fields, linked_issue=linked_issue)


def fields_for_work_type(work_type: WorkType) -> list[str]:
    if work_type == WorkType.FEATURE:
        return FEATURE_FIELDS
    if work_type == WorkType.DOCUMENTATION:
        return DOCUMENTATION_FIELDS
    raise ContractError(f"Unsupported work type: {work_type}")


def normalize_work_type(raw: str) -> WorkType:
    normalized = raw.strip().upper().replace("-", "_")
    if normalized in LEGACY_WORK_TYPE_ALIASES:
        return LEGACY_WORK_TYPE_ALIASES[normalized]
    try:
        return WorkType(normalized)
    except ValueError as exc:
        raise ContractError(f"Unknown issue Type: {raw}") from exc


def load_roadmap_targets(path: str) -> set[str]:
    targets: set[str] = set()
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                targets.add(value)
    return targets


def _parse_ordered_fields(body: str, expected_fields: list[str]) -> dict[str, str]:
    headings = list(HEADING_RE.finditer(body))
    heading_names = [match.group(1).strip() for match in headings]
    if heading_names != expected_fields:
        raise ContractError(
            "Top-level headings must exactly match the required fields in order: "
            + ", ".join(expected_fields)
        )

    parsed: dict[str, str] = {}
    for index, match in enumerate(headings):
        field_name = match.group(1).strip()
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        parsed[field_name] = body[start:end].strip()
    return parsed


def _reject_extra_top_level_headings(body: str, expected_fields: list[str]) -> None:
    actual = [match.group(1).strip() for match in HEADING_RE.finditer(body)]
    extra = [heading for heading in actual if heading not in expected_fields]
    if extra:
        raise ContractError(f"Unknown top-level field(s): {', '.join(extra)}")


def _require_non_empty(fields: dict[str, str]) -> None:
    missing = [name for name, value in fields.items() if not value.strip()]
    if missing:
        raise ContractError(f"Required field(s) must be non-empty: {', '.join(missing)}")


def _validate_roadmap_target(raw: str, roadmap_targets: Iterable[str]) -> None:
    target = raw.strip()
    allowed = set(roadmap_targets) | SPECIAL_ROADMAP_TARGETS
    if target not in allowed:
        raise ContractError(
            f"Roadmap Target '{target}' is not configured and is not one of: "
            + ", ".join(sorted(SPECIAL_ROADMAP_TARGETS))
        )


def _extract_issue_number(raw: str) -> int:
    match = ISSUE_REF_RE.search(raw)
    if not match:
        raise ContractError("Linked Issue must reference an issue number such as '#123'.")
    return int(match.group(1))


def _list_items(raw: str) -> list[str]:
    items: list[str] = []
    for line in raw.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith(("- ", "* ")):
            value = value[2:].strip()
        items.append(value)
    return items

