from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from simple_flow_gates.contracts import IssueContract, WorkType, normalize_work_type


EXECUTION_ROUTES = {
    "CREATE_INDEPENDENT_ISSUE",
    "PUBLISH_REVISED_DRAFT",
    "CREATE_LINKED_SUBISSUE",
    "UPDATE_CURRENT_PR",
    "CREATE_LINKED_FOLLOW_UP",
    "CREATE_INDEPENDENT_FOLLOW_UP",
}
LIFECYCLE_STATES = {"READY", "BLOCKED", "COMPLETED", "SUPERSEDED"}


@dataclass(frozen=True)
class Draft:
    draft_id: str
    work_type: str
    fields: dict[str, str]
    source_issue: int | None = None
    source_pr: int | None = None
    execution: dict[str, object] = field(default_factory=dict)

    def to_issue_body(self) -> str:
        work_type = normalize_work_type(self.work_type)
        if work_type == WorkType.FEATURE:
            headings = [
                "Summary",
                "Requirements",
                "Acceptance Criteria",
                "Scope",
                "Out of Scope",
                "Documentation Impact",
                "Roadmap Target",
            ]
        elif work_type == WorkType.DOCUMENTATION:
            headings = [
                "Change",
                "Reason",
                "Impact",
                "Supersedes",
                "Affected Project Documents",
                "Source PR / Decision Context",
            ]
        else:
            raise ValueError(f"Unsupported draft work type: {self.work_type}")

        chunks = [f"Type: {work_type.value}"]
        for heading in headings:
            chunks.append(f"## {heading}\n\n{self.fields[heading]}")
        return "\n\n".join(chunks) + "\n"

    def to_json_data(self) -> dict[str, object]:
        return {
            "draft_id": self.draft_id,
            "work_type": self.work_type,
            "fields": self.fields,
            "source_issue": self.source_issue,
            "source_pr": self.source_pr,
            "execution": self.execution,
        }

    @classmethod
    def from_json_data(cls, data: dict[str, object]) -> "Draft":
        return cls(
            draft_id=str(data["draft_id"]),
            work_type=normalize_work_type(str(data["work_type"])).value,
            fields={str(k): str(v) for k, v in dict(data["fields"]).items()},
            source_issue=_optional_int(data.get("source_issue")),
            source_pr=_optional_int(data.get("source_pr")),
            execution=_normalize_execution(data.get("execution")),
        )


class DraftStore:
    def __init__(self, root: str | Path, roadmap_targets: set[str] | None = None):
        self.root = Path(root)
        self.roadmap_targets = roadmap_targets or set()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_feature(
        self,
        *,
        summary: str,
        requirements: list[str],
        acceptance_criteria: list[str],
        scope: list[str],
        out_of_scope: list[str],
        documentation_impact: list[str],
        roadmap_target: str,
        source_issue: int | None = None,
        source_pr: int | None = None,
        execution: dict[str, object] | None = None,
    ) -> Draft:
        draft = Draft(
            draft_id=self._next_id(),
            work_type=WorkType.FEATURE.value,
            fields={
                "Summary": summary,
                "Requirements": _render_lines(requirements),
                "Acceptance Criteria": _render_lines(acceptance_criteria),
                "Scope": _render_lines(scope),
                "Out of Scope": _render_lines(out_of_scope),
                "Documentation Impact": _render_optional_docs(documentation_impact),
                "Roadmap Target": roadmap_target,
            },
            source_issue=source_issue,
            source_pr=source_pr,
            execution=_normalize_execution(execution),
        )
        self._validate_and_save(draft)
        return draft

    def create_documentation(
        self,
        *,
        change: str,
        reason: str,
        impact: str,
        supersedes: str,
        affected_project_documents: list[str],
        source_context: str,
        source_issue: int | None = None,
        source_pr: int | None = None,
        execution: dict[str, object] | None = None,
    ) -> Draft:
        draft = Draft(
            draft_id=self._next_id(),
            work_type=WorkType.DOCUMENTATION.value,
            fields={
                "Change": change,
                "Reason": reason,
                "Impact": impact,
                "Supersedes": supersedes,
                "Affected Project Documents": _render_lines(affected_project_documents),
                "Source PR / Decision Context": source_context,
            },
            source_issue=source_issue,
            source_pr=source_pr,
            execution=_normalize_execution(execution),
        )
        self._validate_and_save(draft)
        return draft

    def create_project_change(
        self,
        *,
        change: str,
        reason: str,
        impact: str,
        supersedes: str,
        affected_project_documents: list[str],
        source_context: str,
        source_issue: int | None = None,
        source_pr: int | None = None,
    ) -> Draft:
        """Legacy alias for callers that still request the old work type name."""
        return self.create_documentation(
            change=change,
            reason=reason,
            impact=impact,
            supersedes=supersedes,
            affected_project_documents=affected_project_documents,
            source_context=source_context,
            source_issue=source_issue,
            source_pr=source_pr,
        )

    def read(self, draft_id: str) -> Draft:
        path = self.root / f"{draft_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return Draft.from_json_data(data)

    def list(self) -> list[Draft]:
        return [self.read(path.stem) for path in sorted(self.root.glob("DRAFT-*.json"))]

    def _validate_and_save(self, draft: Draft) -> None:
        IssueContract.parse(draft.to_issue_body(), self.roadmap_targets)
        json_path = self.root / f"{draft.draft_id}.json"
        md_path = self.root / f"{draft.draft_id}.md"
        json_path.write_text(
            json.dumps(draft.to_json_data(), indent=2) + "\n",
            encoding="utf-8",
        )
        md_path.write_text(draft.to_issue_body(), encoding="utf-8")

    def _next_id(self) -> str:
        highest = 0
        for path in self.root.glob("DRAFT-*.json"):
            match = re.fullmatch(r"DRAFT-(\d{4})\.json", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
        return f"DRAFT-{highest + 1:04d}"


def _render_lines(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        raise ValueError("Draft list fields must contain at least one value.")
    return "\n".join(f"- {value}" for value in cleaned)


def _render_optional_docs(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        return "None"
    return "\n".join(f"- {value}" for value in cleaned)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _normalize_execution(value: object) -> dict[str, object]:
    raw = {} if value is None else dict(value) if isinstance(value, dict) else None
    if raw is None:
        raise ValueError("Draft execution metadata must be an object.")

    route = str(raw.get("implementation_route", "CREATE_INDEPENDENT_ISSUE"))
    if route not in EXECUTION_ROUTES:
        raise ValueError(f"Unsupported implementation route: {route}")
    lifecycle = str(raw.get("lifecycle", "READY"))
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(f"Unsupported draft lifecycle: {lifecycle}")

    priority = raw.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("Draft execution priority must be an integer.")

    return {
        "lifecycle": lifecycle,
        "intent_tags": _metadata_list(raw.get("intent_tags", []), "intent_tags"),
        "components": _metadata_list(raw.get("components", []), "components"),
        "priority": priority,
        "implementation_route": route,
        "triage_decision_id": _metadata_optional_string(raw.get("triage_decision_id")),
        "parent_draft_id": _metadata_optional_string(raw.get("parent_draft_id")),
        "supersedes_draft_id": _metadata_optional_string(raw.get("supersedes_draft_id")),
    }


def _metadata_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Draft execution {name} must be a list of non-empty strings.")
    return [item.strip() for item in value]


def _metadata_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Draft execution references must be non-empty strings when provided.")
    return value.strip()

