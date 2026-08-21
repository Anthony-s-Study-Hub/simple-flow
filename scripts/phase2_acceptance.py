from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simple_flow_agent.drafts import DraftStore
from simple_flow_agent.finalize import FinalizeBlocked, PRState, pre_merge_check
from simple_flow_agent.review_triage import classify_review_finding
from simple_flow_agent.start_implement import (
    AmbiguousReviewTriageError,
    select_start_path,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    store = DraftStore(workspace / "drafts")

    normal_feature = store.create_feature(
        summary="Normal feature acceptance.",
        requirements=["Start through approved draft"],
        acceptance_criteria=["Stop at human PR review"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Phase 3"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
    )
    normal_plan = select_start_path(store, normal_feature.draft_id)
    assert normal_plan.path == "FEATURE_NORMAL"
    assert normal_plan.stop_point == "HUMAN_PR_REVIEW"
    assert "merge_pull_request" not in normal_plan.actions

    review_draft = store.create_feature(
        summary="Review triage acceptance.",
        requirements=["Use matching review context"],
        acceptance_criteria=["Current, subissue, and new issue route correctly"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Direct fixes"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        source_issue=10,
        source_pr=20,
    )
    for relationship in ["CURRENT", "SUBISSUE", "NEW ISSUE"]:
        triage = classify_review_finding(
            relationship=relationship,
            merge_impact="BLOCKING",
            source_issue=10,
            source_pr=20,
            reason=f"{relationship} acceptance scenario.",
        )
        assert select_start_path(store, review_draft.draft_id, [triage]).path.startswith(
            "REVIEW_"
        )

    documentation = store.create_documentation(
        change="Documentation acceptance.",
        reason="Long-term document rule.",
        impact="Project docs update.",
        supersedes="None",
        affected_project_documents=["AGENTS.md"],
        source_context="Acceptance scenario",
    )
    documentation_plan = select_start_path(store, documentation.draft_id)
    assert documentation_plan.path == "DOCUMENTATION_NORMAL"
    assert documentation_plan.tdd_required is False

    try:
        pre_merge_check(PRState.ready(), authorized=False)
    except FinalizeBlocked:
        pass
    else:
        raise AssertionError("PR-Finalize must require explicit authorization.")

    try:
        select_start_path(
            store,
            review_draft.draft_id,
            [
                classify_review_finding(
                    relationship="CURRENT",
                    merge_impact="BLOCKING",
                    source_issue=10,
                    source_pr=20,
                    reason="First.",
                ),
                classify_review_finding(
                    relationship="SUBISSUE",
                    merge_impact="FOLLOW-UP",
                    source_issue=10,
                    source_pr=20,
                    reason="Second.",
                ),
            ],
        )
    except AmbiguousReviewTriageError:
        pass
    else:
        raise AssertionError("Ambiguous Review-Triage context must stop.")

    assert pre_merge_check(PRState.ready(), authorized=True).can_merge is True
    print("Phase 2 acceptance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
