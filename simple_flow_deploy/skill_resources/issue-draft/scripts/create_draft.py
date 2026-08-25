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
    parser.add_argument("--drafts-dir", default=".simple-flow/drafts")
    parser.add_argument("--roadmap-targets", default=".simple-flow/roadmap-targets.txt")
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
                source_issue=_optional_int(_field(data, "source_issue", default=None)),
                source_pr=_optional_int(_field(data, "source_pr", default=None)),
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
                source_issue=_optional_int(_field(data, "source_issue", default=None)),
                source_pr=_optional_int(_field(data, "source_pr", default=None)),
            )
        else:
            raise ValueError(f"Unsupported work_type: {work_type}")
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

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
    for parent in Path(__file__).resolve().parents:
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


if __name__ == "__main__":
    raise SystemExit(main())
