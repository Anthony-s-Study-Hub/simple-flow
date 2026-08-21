from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from simple_flow_documentation_curation.baselines import (
    BaselineSchemaError,
    parse_component_baseline,
    parse_project_baseline,
)


@dataclass(frozen=True)
class StructuralConflict:
    code: str
    message: str
    path: str = ""


def check_structural_conflicts(
    project_baseline_text: str,
    component_baselines: dict[str, str],
    *,
    valid_references: set[str] | None = None,
) -> list[StructuralConflict]:
    conflicts: list[StructuralConflict] = []
    valid = valid_references or set()

    try:
        project = parse_project_baseline(project_baseline_text)
    except BaselineSchemaError as exc:
        return [StructuralConflict("PROJECT_SCHEMA_ERROR", str(exc))]

    for entry in project.components.values():
        if PurePosixPath(entry.baseline_document).as_posix() not in component_baselines:
            conflicts.append(
                StructuralConflict(
                    "MISSING_COMPONENT_DOCUMENT",
                    f"Component Index points to missing document: {entry.baseline_document}",
                    entry.baseline_document,
                )
            )

    all_decisions: dict[str, list[str]] = {}
    supersedes: dict[str, list[str]] = {}
    statuses: dict[str, str] = {}
    for path, text in component_baselines.items():
        try:
            parsed = parse_component_baseline(text)
        except BaselineSchemaError as exc:
            conflicts.append(StructuralConflict("COMPONENT_SCHEMA_ERROR", str(exc), path))
            parsed = None

        for decision_id in _decision_ids_anywhere(text):
            all_decisions.setdefault(decision_id, []).append(path)

        if parsed is None:
            continue
        for decision in parsed.decisions.values():
            statuses[decision.decision_id] = decision.status
            if decision.supersedes:
                supersedes.setdefault(decision.decision_id, []).extend(
                    value.strip()
                    for value in decision.supersedes.split(",")
                    if value.strip()
                )
            for reference in decision.evidence:
                if valid and reference not in valid:
                    conflicts.append(
                        StructuralConflict(
                            "INVALID_EVIDENCE_REFERENCE",
                            f"{decision.decision_id} points to unknown evidence {reference}",
                            path,
                        )
                    )

    for decision_id, paths in all_decisions.items():
        if len(paths) > 1:
            conflicts.append(
                StructuralConflict(
                    "DUPLICATE_DECISION_ID",
                    f"{decision_id} appears {len(paths)} times",
                    ", ".join(paths),
                )
            )

    for decision_id, replaced_ids in supersedes.items():
        for replaced_id in replaced_ids:
            if statuses.get(replaced_id) == "ACTIVE":
                conflicts.append(
                    StructuralConflict(
                        "SUPERSEDED_DECISION_STILL_ACTIVE",
                        f"{decision_id} supersedes {replaced_id}, but {replaced_id} is ACTIVE",
                    )
                )

    conflicts.extend(_supersedes_cycles(supersedes))
    return conflicts


def _decision_ids_anywhere(text: str) -> list[str]:
    return re.findall(r"^### Decision (?P<id>D-\d+)", text, flags=re.MULTILINE)


def _supersedes_cycles(supersedes: dict[str, list[str]]) -> list[StructuralConflict]:
    conflicts: list[StructuralConflict] = []

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node):] + [node]
            conflicts.append(
                StructuralConflict("SUPERSEDES_CYCLE", " -> ".join(cycle))
            )
            return
        for child in supersedes.get(node, ()):
            visit(child, path + [node])

    for decision_id in supersedes:
        visit(decision_id, [])
    return conflicts
