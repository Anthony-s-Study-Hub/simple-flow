from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    _add_repo_root_to_path()

    from simple_flow_agent.drafts import DraftStore
    from simple_flow_documentation_curation.cursor import pending_cursor_for
    from simple_flow_documentation_curation.models import CurationAnalysis
    from simple_flow_documentation_curation.normalizer import normalize_history
    from simple_flow_documentation_curation.patch_planner import plan_patch_operations
    from simple_flow_documentation_curation.references import ReferenceResolver
    from simple_flow_documentation_curation.relationships import resolve_relationships
    from simple_flow_documentation_curation.renderer import create_documentation_draft

    parser = argparse.ArgumentParser(
        description="Validate Documentation-Curation analysis and create a DOCUMENTATION draft."
    )
    parser.add_argument("--history-package", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--drafts-dir", default=".simple-flow/drafts")
    parser.add_argument("--output-dir", default=".simple-flow/documentation-curation")
    args = parser.parse_args()

    history_data = json.loads(Path(args.history_package).read_text(encoding="utf-8"))
    analysis_data = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    affected_documents = [
        str(value)
        for value in analysis_data.pop("affected_project_documents", ())
        if str(value).strip()
    ]

    history = resolve_relationships(normalize_history(history_data))
    pending = pending_cursor_for(history)
    analysis = CurationAnalysis.from_json_data(analysis_data)
    if analysis.pending_cursor is None:
        analysis = analysis.with_pending_cursor(pending)

    _validate_references(analysis, ReferenceResolver(history))
    operations = plan_patch_operations(analysis)
    analysis = analysis.with_operations(operations)

    drafts_dir = Path(args.drafts_dir).resolve()
    draft = create_documentation_draft(
        DraftStore(drafts_dir),
        analysis,
        affected_project_documents=affected_documents,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "ok",
        "draft_id": draft.draft_id,
        "work_type": draft.work_type,
        "json_path": str(drafts_dir / f"{draft.draft_id}.json"),
        "markdown_path": str(drafts_dir / f"{draft.draft_id}.md"),
        "pending_cursor": (
            None
            if analysis.pending_cursor is None
            else analysis.pending_cursor.to_json_data()
        ),
        "operation_count": len(operations),
        "stop_point": "DOCUMENTATION_DRAFT_CREATED",
        "created_issue": False,
        "created_branch": False,
        "created_pull_request": False,
        "called_start_implement": False,
        "called_pr_finalize": False,
        "merged": False,
    }
    (output_dir / f"{draft.draft_id}-curation-result.json").write_text(
        json.dumps(
            {
                **result,
                "analysis": analysis.to_json_data(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0


def _validate_references(analysis: CurationAnalysis, resolver: ReferenceResolver) -> None:
    for decision in analysis.decisions:
        resolver.validate_all(decision.exact_references)
        if decision.proposed_classification == "FINAL" and not decision.exact_references:
            raise ValueError(f"{decision.decision_id} FINAL proposal has no exact references.")
    for finding in analysis.findings:
        resolver.validate_all(finding.exact_references)
    for proposal in analysis.new_components:
        resolver.validate_all(proposal.evidence)


def _add_repo_root_to_path() -> None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "simple_flow_agent").is_dir():
            sys.path.insert(0, str(parent))
            return
    return


if __name__ == "__main__":
    raise SystemExit(main())
