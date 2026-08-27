from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def main(argv: list[str] | None = None) -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.drafts import DraftStore
    from simple_flow_gates.contracts import WorkType, load_roadmap_targets

    parser = argparse.ArgumentParser(
        description="Create and validate a Simple Flow Canonical Draft."
    )
    parser.add_argument("--input", required=True, help="JSON file containing draft fields.")
    parser.add_argument("--drafts-dir", default=".simple_tool/drafts")
    parser.add_argument("--roadmap-targets", default=".simple_tool/roadmap-targets.txt")
    parser.add_argument(
        "--triage-file",
        help="Optional structured Review-Triage decision that authoritatively sets the execution route.",
    )
    parser.add_argument("--status-file", default=".simple_tool/status.json")
    args = parser.parse_args(argv)

    try:
        input_path = Path(args.input)
        data = json.loads(input_path.read_text(encoding="utf-8"))
        drafts_dir = Path(args.drafts_dir).resolve()
        roadmap_path = Path(args.roadmap_targets)
        roadmap_targets = (
            load_roadmap_targets(str(roadmap_path)) if roadmap_path.exists() else set()
        )
        store = DraftStore(drafts_dir, roadmap_targets=roadmap_targets)
        work_type = _work_type(data)
        triage = _triage_decision(args.triage_file)
        execution = _execution(data, triage)
        source_issue = _source_reference(data, "source_issue", triage)
        source_pr = _source_reference(data, "source_pr", triage)

        if work_type == WorkType.FEATURE:
            draft = store.create_feature(
                summary=str(_field(data, "summary", "Summary")),
                requirements=_as_list(_field(data, "requirements", "Requirements")),
                acceptance_criteria=_as_list(
                    _field(data, "acceptance_criteria", "Acceptance Criteria")
                ),
                scope=_as_list(_field(data, "scope", "Scope")),
                out_of_scope=_as_list(_field(data, "out_of_scope", "Out of Scope")),
                documentation_impact=_as_list(
                    _field(data, "documentation_impact", "Documentation Impact", default=[])
                ),
                roadmap_target=str(_field(data, "roadmap_target", "Roadmap Target")),
                source_issue=source_issue,
                source_pr=source_pr,
                execution=execution,
            )
        elif work_type == WorkType.DOCUMENTATION:
            draft = store.create_documentation(
                change=str(_field(data, "change", "Change")),
                reason=str(_field(data, "reason", "Reason")),
                impact=str(_field(data, "impact", "Impact")),
                supersedes=str(_field(data, "supersedes", "Supersedes")),
                affected_project_documents=_as_list(
                    _field(
                        data,
                        "affected_project_documents",
                        "Affected Project Documents",
                    )
                ),
                source_context=str(
                    _field(data, "source_context", "Source PR / Decision Context")
                ),
                source_issue=source_issue,
                source_pr=source_pr,
                execution=execution,
            )
        else:
            raise ValueError(f"Unsupported work_type: {work_type}")
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    _record_active_draft(Path(args.status_file), draft.draft_id)
    print(
        json.dumps(
            {
                "status": "ok",
                "draft_id": draft.draft_id,
                "work_type": draft.work_type,
                "json_path": str(drafts_dir / f"{draft.draft_id}.json"),
                "markdown_path": str(drafts_dir / f"{draft.draft_id}.md"),
            },
            indent=2,
        )
    )
    return 0


def _add_repo_root_to_path() -> None:
    roots = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    for parent in [*roots, *Path(__file__).resolve().parents]:
        runtime = parent / ".simple_tool" / "runtime"
        if (runtime / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(runtime))
            return
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return
    return


def _work_type(data: dict[str, Any]):
    from simple_flow_gates.contracts import normalize_work_type

    raw = str(_field(data, "work_type", "type", "Type")).upper().replace("-", "_")
    return normalize_work_type(raw)


def _field(data: dict[str, Any], *names: str, default: Any = ...):
    sources = [data]
    fields = data.get("fields")
    if isinstance(fields, dict):
        sources.append(fields)

    normalized_names = {_normalize(name) for name in names}
    for source in sources:
        normalized_source = {_normalize(str(key)): value for key, value in source.items()}
        for name in normalized_names:
            if name in normalized_source:
                return normalized_source[name]

    if default is not ...:
        return default
    raise KeyError(f"Missing required draft field: {' or '.join(names)}")


def _normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [
        line.strip().lstrip("-*").strip()
        for line in str(value).splitlines()
        if line.strip()
    ]


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _execution(data: dict[str, Any], decision) -> dict[str, object]:
    raw = data.get("execution", {})
    if not isinstance(raw, dict):
        raise ValueError("execution must be a JSON object.")
    execution = dict(raw)
    if not decision:
        return execution

    from simple_flow_agent.review_triage import route_for_resolution

    route = route_for_resolution(decision.resolution)
    existing_route = execution.get("implementation_route")
    if existing_route and existing_route != route:
        raise ValueError("execution implementation_route conflicts with the Review-Triage decision.")
    execution.update(
        {
            "implementation_route": route,
            "triage_decision_id": decision.decision_id,
        }
    )
    if decision.resolution == "SUPERSEDE_DRAFT":
        execution["supersedes_draft_id"] = decision.target_draft_id
    else:
        execution["parent_draft_id"] = decision.target_draft_id
    return execution


def _triage_decision(path: str | None):
    if not path:
        return None
    from simple_flow_agent.review_triage import review_triage_from_data

    return review_triage_from_data(json.loads(Path(path).read_text(encoding="utf-8")))


def _source_reference(data: dict[str, Any], name: str, decision) -> int | None:
    supplied = _optional_int(_field(data, name, default=None))
    if not decision:
        return supplied
    triage_value = getattr(decision, name)
    if supplied is not None and triage_value is not None and supplied != triage_value:
        raise ValueError(f"{name} conflicts with the Review-Triage decision.")
    return supplied if supplied is not None else triage_value


def _record_active_draft(status_path: Path, draft_id: str) -> None:
    if not status_path.exists():
        return
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if not isinstance(status, dict):
        raise ValueError("Simple Flow status file must be a JSON object.")
    status["active_draft"] = draft_id
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
