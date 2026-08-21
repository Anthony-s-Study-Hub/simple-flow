from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from simple_flow_agent.drafts import DraftStore
from simple_flow_agent.finalize import (
    FinalizeBlocked,
    PRState,
    pre_merge_check,
)
from simple_flow_agent.review_triage import classify_review_finding
from simple_flow_agent.start_implement import (
    AmbiguousReviewTriageError,
    select_start_path,
)
from simple_flow_gates.contracts import IssueContract, WorkType


def test_issue_draft_creates_structured_and_rendered_feature_draft(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)

    draft = store.create_feature(
        summary="Add a small workflow feature.",
        requirements=["Requirement A"],
        acceptance_criteria=["Acceptance A"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Phase 3"],
        documentation_impact=["docs/phase2-skills.md"],
        roadmap_target="UNMAPPED",
    )

    assert draft.draft_id == "DRAFT-0001"
    assert (tmp_path / "DRAFT-0001.json").exists()
    assert (tmp_path / "DRAFT-0001.md").exists()
    parsed = IssueContract.parse(draft.to_issue_body())
    assert parsed.work_type == WorkType.FEATURE
    assert "Add a small workflow feature." in (tmp_path / "DRAFT-0001.md").read_text(
        encoding="utf-8"
    )


def test_issue_draft_feature_script_creates_draft(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    draft_input = tmp_path / "draft-input.json"
    draft_dir = tmp_path / "drafts"
    roadmap = tmp_path / "roadmap-targets.txt"
    roadmap.write_text("PHASE_1_GOVERNANCE\n", encoding="utf-8")
    draft_input.write_text(
        json.dumps(
            {
                "work_type": "FEATURE",
                "summary": "Executable skill pipeline.",
                "requirements": ["Create the draft through a skill-local script"],
                "acceptance_criteria": ["Start-Implement reads the script output"],
                "scope": ["skills/"],
                "out_of_scope": ["Phase 4"],
                "documentation_impact": ["docs/phase2-skills.md"],
                "roadmap_target": "PHASE_1_GOVERNANCE",
                "source_issue": 14,
                "source_pr": 15,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "issue-draft", "create_draft.py")),
            "--input",
            str(draft_input),
            "--drafts-dir",
            str(draft_dir),
            "--roadmap-targets",
            str(roadmap),
        ],
        cwd=root,
    )
    assert created["draft_id"] == "DRAFT-0001"
    assert (draft_dir / "DRAFT-0001.json").exists()


def test_review_triage_script_classifies_blocking_current_finding() -> None:
    root = Path(__file__).resolve().parents[1]

    triage = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "review-triage", "classify_finding.py")),
            "--relationship",
            "CURRENT",
            "--merge-impact",
            "BLOCKING",
            "--source-issue",
            "14",
            "--source-pr",
            "15",
            "--reason",
            "Review found a blocking current-work issue.",
        ],
        cwd=root,
    )
    assert triage["relationship"] == "CURRENT"
    assert triage["merge_impact"] == "BLOCKING"
    assert triage["source_issue"] == 14
    assert triage["source_pr"] == 15


def test_start_implement_script_selects_review_blocking_path(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    draft_dir = tmp_path / "drafts"
    triage_output = tmp_path / "triage.json"
    store = DraftStore(draft_dir)
    store.create_feature(
        summary="Executable skill pipeline.",
        requirements=["Create the draft through a skill script"],
        acceptance_criteria=["Start-Implement reads the script output"],
        scope=["skills/"],
        out_of_scope=["Phase 4"],
        documentation_impact=["docs/phase2-skills.md"],
        roadmap_target="UNMAPPED",
        source_issue=14,
        source_pr=15,
    )
    triage_output.write_text(
        json.dumps(
            {
                "relationship": "CURRENT",
                "merge_impact": "BLOCKING",
                "source_issue": 14,
                "source_pr": 15,
                "reason": "Review found a blocking current-work issue.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    plan = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "start-implement", "select_path.py")),
            "--draft-id",
            "DRAFT-0001",
            "--drafts-dir",
            str(draft_dir),
            "--triage-file",
            str(triage_output),
        ],
        cwd=root,
    )
    assert plan["path"] == "REVIEW_CURRENT_BLOCKING"
    assert plan["stop_point"] == "HUMAN_PR_REVIEW"
    assert "merge_pull_request" not in plan["actions"]


def test_pr_finalize_script_allows_ready_authorized_merge(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    pr_state = tmp_path / "pr-state.json"
    pr_state.write_text(
        json.dumps(
            {
                "exists": True,
                "open": True,
                "draft": False,
                "required_checks": {"phase1-gates": True, "phase1-tests": True},
                "unresolved_conversations": 0,
                "commits_after_human_review": 0,
                "linked_issue_closed": False,
                "head_branch_deleted": False,
                "project_item_updated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    finalize = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "pr-finalize", "check_pre_merge.py")),
            "--state",
            str(pr_state),
            "--authorized",
        ],
        cwd=root,
    )
    assert finalize["can_merge"] is True


def test_issue_draft_script_creates_documentation_draft(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    draft_input = tmp_path / "documentation-input.json"
    draft_dir = tmp_path / "drafts"
    draft_input.write_text(
        json.dumps(
            {
                "work_type": "DOCUMENTATION",
                "change": "Clarify the usage guide.",
                "reason": "The existing wording is misleading.",
                "impact": "Future users pick the documentation-only path.",
                "supersedes": "None",
                "affected_project_documents": ["docs/deployment/usage-guide.md"],
                "source_context": "Issue #16",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "issue-draft", "create_draft.py")),
            "--input",
            str(draft_input),
            "--drafts-dir",
            str(draft_dir),
        ],
        cwd=root,
    )
    assert created["work_type"] == "DOCUMENTATION"
    assert "Type: DOCUMENTATION" in (draft_dir / "DRAFT-0001.md").read_text(
        encoding="utf-8"
    )


def test_start_implement_reads_specified_draft_not_latest(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    first = store.create_feature(
        summary="First approved draft.",
        requirements=["A"],
        acceptance_criteria=["A passes"],
        scope=["simple_flow_agent/"],
        out_of_scope=["B"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
    )
    store.create_feature(
        summary="Latest but not approved draft.",
        requirements=["B"],
        acceptance_criteria=["B passes"],
        scope=["skills/"],
        out_of_scope=["A"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
    )

    plan = select_start_path(store, first.draft_id)

    assert plan.draft_id == "DRAFT-0001"
    assert plan.summary == "First approved draft."
    assert plan.path == "FEATURE_NORMAL"


def test_documentation_does_not_require_tdd(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_documentation(
        change="Update baseline policy.",
        reason="A long-term rule changed.",
        impact="Future work follows the new rule.",
        supersedes="None",
        affected_project_documents=["AGENTS.md"],
        source_context="PR #10",
    )

    plan = select_start_path(store, draft.draft_id)

    assert plan.work_type == "DOCUMENTATION"
    assert plan.path == "DOCUMENTATION_NORMAL"
    assert plan.tdd_required is False


def test_review_triage_relationships_select_expected_start_paths(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_feature(
        summary="Review follow-up.",
        requirements=["Fix current review issue"],
        acceptance_criteria=["Review issue handled"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Other PRs"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        source_issue=20,
        source_pr=30,
    )

    cases = {
        "CURRENT": "REVIEW_CURRENT_BLOCKING",
        "SUBISSUE": "REVIEW_SUBISSUE_BLOCKING",
        "NEW ISSUE": "REVIEW_NEW_ISSUE_BLOCKING",
    }
    for relationship, expected_path in cases.items():
        triage = classify_review_finding(
            relationship=relationship,
            merge_impact="BLOCKING",
            source_issue=20,
            source_pr=30,
            reason="Reviewer found a blocking issue.",
        )
        assert select_start_path(store, draft.draft_id, [triage]).path == expected_path


def test_old_review_triage_does_not_pollute_new_feature(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_feature(
        summary="Unrelated feature.",
        requirements=["Build unrelated work"],
        acceptance_criteria=["No old review context"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Old review"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        source_issue=99,
        source_pr=100,
    )
    old_triage = classify_review_finding(
        relationship="CURRENT",
        merge_impact="BLOCKING",
        source_issue=1,
        source_pr=2,
        reason="Old review finding.",
    )

    assert select_start_path(store, draft.draft_id, [old_triage]).path == "FEATURE_NORMAL"


def test_ambiguous_review_triage_context_stops(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_feature(
        summary="Ambiguous review continuation.",
        requirements=["Do not guess"],
        acceptance_criteria=["Stops on ambiguity"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Guessing"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        source_issue=50,
        source_pr=60,
    )
    triages = [
        classify_review_finding(
            relationship="CURRENT",
            merge_impact="BLOCKING",
            source_issue=50,
            source_pr=60,
            reason="First finding.",
        ),
        classify_review_finding(
            relationship="SUBISSUE",
            merge_impact="FOLLOW-UP",
            source_issue=50,
            source_pr=60,
            reason="Second finding.",
        ),
    ]

    with pytest.raises(AmbiguousReviewTriageError):
        select_start_path(store, draft.draft_id, triages)


def test_start_implement_stops_at_human_review_and_never_merges(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_feature(
        summary="Stop before merge.",
        requirements=["Stop"],
        acceptance_criteria=["No merge action"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Merge"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
    )

    plan = select_start_path(store, draft.draft_id)

    assert plan.stop_point == "HUMAN_PR_REVIEW"
    assert "merge_pull_request" not in plan.actions


def test_pr_finalize_requires_explicit_human_authorization() -> None:
    state = PRState.ready()

    with pytest.raises(FinalizeBlocked, match="explicit PR-Finalize"):
        pre_merge_check(state, authorized=False)


def test_pr_finalize_blocks_objective_failures() -> None:
    blockers = [
        PRState.ready(required_checks={"phase1-gates": False, "phase1-tests": True}),
        PRState.ready(unresolved_conversations=1),
        PRState.ready(commits_after_human_review=1),
    ]

    for state in blockers:
        with pytest.raises(FinalizeBlocked):
            pre_merge_check(state, authorized=True)


def test_pr_finalize_ready_state_allows_merge_and_cleanup_checks() -> None:
    result = pre_merge_check(PRState.ready(), authorized=True)

    assert result.can_merge is True
    assert result.required_cleanup == [
        "confirm_linked_issue_closed",
        "confirm_head_branch_deleted",
        "confirm_project_item_updated",
    ]


def test_phase2_acceptance_script_covers_runnable_scenarios(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase2_acceptance.py",
            "--workspace",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Phase 2 acceptance PASS" in completed.stdout


def _skill_script(
    root: Path,
    installed_skill: str,
    script_name: str,
) -> Path:
    script_path = (
        root
        / "simple_flow_deploy"
        / "skill_resources"
        / installed_skill
        / "scripts"
        / script_name
    )
    if script_path.exists():
        return script_path

    deployed_path = root / ".codex" / "skills" / installed_skill / "scripts" / script_name
    assert deployed_path.exists()
    return deployed_path


def _run_json(command: list[str], *, cwd: Path) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)

