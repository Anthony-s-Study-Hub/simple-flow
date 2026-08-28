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
from simple_flow_agent.implementation_plan import (
    DraftSelectionError,
    ImplementationIntent,
    plan_implementation,
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
    status = tmp_path / "status.json"
    roadmap.write_text("PHASE_1_GOVERNANCE\n", encoding="utf-8")
    status.write_text('{"active_draft": null}\n', encoding="utf-8")
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
                "execution": {
                    "intent_tags": ["pipeline"],
                    "components": ["simple_flow_agent"],
                    "priority": 10,
                },
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
            "--status-file",
            str(status),
        ],
        cwd=root,
    )
    assert created["draft_id"] == "DRAFT-0001"
    assert (draft_dir / "DRAFT-0001.json").exists()
    assert DraftStore(draft_dir).read("DRAFT-0001").execution["priority"] == 10
    assert json.loads(status.read_text(encoding="utf-8"))["active_draft"] == "DRAFT-0001"


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


def test_review_triage_script_persists_a_draft_stage_resolution(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "triage" / "RT-0001.json"

    triage = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "review-triage", "classify_finding.py")),
            "--relationship",
            "CURRENT",
            "--merge-impact",
            "FOLLOW-UP",
            "--reason",
            "The planned draft needs the requested behavior.",
            "--decision-id",
            "RT-0001",
            "--target-draft-id",
            "DRAFT-0001",
            "--stage",
            "DRAFT",
            "--resolution",
            "SUPERSEDE_DRAFT",
            "--output",
            str(output_path),
        ],
        cwd=root,
    )

    assert triage["resolution"] == "SUPERSEDE_DRAFT"
    assert json.loads(output_path.read_text(encoding="utf-8"))["target_draft_id"] == "DRAFT-0001"


def test_start_implement_script_selects_a_routed_draft(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    draft_dir = tmp_path / "drafts"
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
        execution={"implementation_route": "UPDATE_CURRENT_PR"},
    )

    plan = _run_json(
        [
            sys.executable,
            str(_skill_script(root, "start-implement", "plan_implementation.py")),
            "--draft-id",
            "DRAFT-0001",
            "--drafts-dir",
            str(draft_dir),
        ],
        cwd=root,
    )
    assert plan["route"] == "UPDATE_CURRENT_PR"
    assert plan["stop_point"] == "HUMAN_PR_REVIEW"
    assert "merge_pull_request" not in plan["actions"]


def test_pr_finalize_script_requires_explicit_approval(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(_skill_script(root, "pr-finalize", "finalize_remote_pr.py")),
            "--pr",
            "1",
            "--repo",
            "owner/repo",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "Missing explicit PR-Finalize invocation authorization" in completed.stderr


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


def test_draft_execution_metadata_preserves_the_typed_issue_contract(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)

    draft = store.create_feature(
        summary="Plan deterministic implementation.",
        requirements=["Preserve typed issue contracts"],
        acceptance_criteria=["Planner returns one route"],
        scope=["simple_flow_agent/"],
        out_of_scope=["GitHub workflow changes"],
        documentation_impact=["docs/phase2-skills.md"],
        roadmap_target="UNMAPPED",
        execution={
            "intent_tags": ["planner", "workflow"],
            "components": ["simple_flow_agent"],
            "priority": 80,
            "implementation_route": "CREATE_INDEPENDENT_ISSUE",
        },
    )

    assert IssueContract.parse(draft.to_issue_body()).work_type == WorkType.FEATURE
    assert draft.execution["implementation_route"] == "CREATE_INDEPENDENT_ISSUE"
    assert DraftStore(tmp_path).read(draft.draft_id).execution["priority"] == 80


def test_planner_selects_matching_draft_without_asking_for_an_id(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    deployment = store.create_feature(
        summary="Deploy the deterministic skill runtime.",
        requirements=["Copy runtime files"],
        acceptance_criteria=["Installed scripts run"],
        scope=["simple_flow_deploy/"],
        out_of_scope=["Agent behavior"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={
            "intent_tags": ["deploy", "runtime"],
            "components": ["simple_flow_deploy"],
            "priority": 20,
        },
    )
    store.create_feature(
        summary="Plan the workflow implementation route.",
        requirements=["Select drafts deterministically"],
        acceptance_criteria=["Matching draft is selected"],
        scope=["simple_flow_agent/"],
        out_of_scope=["Deployment"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={
            "intent_tags": ["planner", "workflow"],
            "components": ["simple_flow_agent"],
            "priority": 20,
        },
    )

    plan = plan_implementation(
        store,
        intent=ImplementationIntent(tags=("deploy",), components=("simple_flow_deploy",)),
    )

    assert plan.draft_id == deployment.draft_id
    assert plan.selection_reason["method"] == "intent-match"
    assert plan.route == "CREATE_INDEPENDENT_ISSUE"


def test_planner_stops_on_a_materially_tied_intent_match(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    for summary in ("First deployment plan.", "Second deployment plan."):
        store.create_feature(
            summary=summary,
            requirements=["Deploy"],
            acceptance_criteria=["Deploy succeeds"],
            scope=["simple_flow_deploy/"],
            out_of_scope=["Other work"],
            documentation_impact=[],
            roadmap_target="UNMAPPED",
            execution={"intent_tags": ["deploy"], "components": ["simple_flow_deploy"]},
        )

    with pytest.raises(DraftSelectionError, match="materially tied"):
        plan_implementation(store, intent=ImplementationIntent(tags=("deploy",)))


def test_planner_excludes_a_draft_superseded_by_an_immutable_successor(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    original = store.create_feature(
        summary="Original deployment plan.",
        requirements=["Deploy"],
        acceptance_criteria=["Install succeeds"],
        scope=["simple_flow_deploy/"],
        out_of_scope=["Other work"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={"intent_tags": ["deploy"]},
    )
    successor = store.create_feature(
        summary="Revised deployment plan.",
        requirements=["Deploy with runtime"],
        acceptance_criteria=["Installed scripts run"],
        scope=["simple_flow_deploy/"],
        out_of_scope=["Other work"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={
            "intent_tags": ["deploy"],
            "supersedes_draft_id": original.draft_id,
            "implementation_route": "PUBLISH_REVISED_DRAFT",
        },
    )

    plan = plan_implementation(store, intent=ImplementationIntent(tags=("deploy",)))

    assert plan.draft_id == successor.draft_id


def test_planner_follows_the_route_persisted_in_a_review_derived_draft(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    draft = store.create_feature(
        summary="Patch the current pull request.",
        requirements=["Apply review feedback"],
        acceptance_criteria=["Review finding is addressed"],
        scope=["simple_flow_agent/"],
        out_of_scope=["New issue creation"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        source_issue=52,
        source_pr=53,
        execution={
            "triage_decision_id": "RT-0001",
            "implementation_route": "UPDATE_CURRENT_PR",
            "intent_tags": ["review", "patch"],
        },
    )

    plan = plan_implementation(store, draft_id=draft.draft_id)

    assert plan.route == "UPDATE_CURRENT_PR"
    assert plan.actions[0] == "resume_current_pull_request"


def test_pr_finalize_requires_explicit_human_authorization() -> None:
    state = PRState.ready()

    with pytest.raises(FinalizeBlocked, match="explicit PR-Finalize"):
        pre_merge_check(state, authorized=False)


def test_pr_finalize_blocks_objective_failures() -> None:
    blockers = [
        PRState.ready(required_checks={"pr-contract": False, "current-head-tests": True}),
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

