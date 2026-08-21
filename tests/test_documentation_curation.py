from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from simple_flow_agent.drafts import DraftStore
from simple_flow_documentation_curation.baselines import (
    BaselineSchemaError,
    parse_component_baseline,
    parse_project_baseline,
)
from simple_flow_documentation_curation.conflicts import check_structural_conflicts
from simple_flow_documentation_curation.cursor import (
    CurationCursor,
    filter_items_since,
    pending_cursor_for,
)
from simple_flow_documentation_curation.mapping import (
    ComponentRule,
    MappingStatus,
    map_work_item_to_components,
)
from simple_flow_documentation_curation.models import (
    CurationAnalysis,
    DecisionProposal,
    DocumentationFinding,
    NewComponentProposal,
)
from simple_flow_documentation_curation.normalizer import normalize_history
from simple_flow_documentation_curation.patch_planner import plan_patch_operations
from simple_flow_documentation_curation.references import ReferenceResolver
from simple_flow_documentation_curation.relationships import resolve_relationships
from simple_flow_documentation_curation.renderer import create_documentation_draft
from simple_flow_documentation_curation.versioning import bump_version, set_last_updated


ROOT = Path(__file__).resolve().parents[1]


def test_history_normalization_relationships_cursor_and_component_mapping() -> None:
    package = normalize_history(
        {
            "repository": "owner/repo",
            "collected_at": "2026-08-21T12:00:00Z",
            "issues": [
                {
                    "number": 30,
                    "title": "Implement curation",
                    "state": "closed",
                    "updated_at": "2026-08-21T10:00:00Z",
                    "labels": ["component:workflow-control"],
                    "body": "Phase 5 implementation",
                }
            ],
            "pull_requests": [
                {
                    "number": 31,
                    "title": "Implement phase 5",
                    "state": "merged",
                    "updated_at": "2026-08-21T11:00:00Z",
                    "merged_at": "2026-08-21T11:30:00Z",
                    "body": "Closes #30 and refs #29. Decision D-010 is final.",
                    "changed_files": [
                        "simple_flow_documentation_curation/renderer.py",
                        "docs/phase5-documentation-curation.md",
                    ],
                    "reviews": [{"id": "R1", "state": "APPROVED"}],
                }
            ],
        }
    )

    resolved = resolve_relationships(package)
    issue = resolved.work_item("issue:30")
    pr = resolved.work_item("pr:31")

    assert issue.related_prs == ("pr:31",)
    assert pr.closes == ("issue:30",)
    assert pr.references == ("issue:29",)

    pending = pending_cursor_for(resolved)
    assert pending == CurationCursor(updated_at="2026-08-21T11:00:00Z", stable_id="pr:31")
    assert [item.id for item in filter_items_since(resolved.work_items, CurationCursor("2026-08-21T10:00:00Z", "issue:30"))] == [
        "pr:31"
    ]

    mapping = map_work_item_to_components(
        pr,
        [
            ComponentRule(
                component_id="documentation-curation",
                name="Documentation Curation",
                labels=("component:documentation-curation",),
                paths=("simple_flow_documentation_curation/", "docs/phase5"),
            )
        ],
    )
    assert mapping.status is MappingStatus.KNOWN_COMPONENT
    assert mapping.component_ids == ("documentation-curation",)


def test_baseline_schema_and_structural_conflicts_are_deterministic() -> None:
    project = """# High-Level Project Baseline
Version: v1.3
Last Updated: 2026-08-20

## Project Goal
Controlled development workflow.

## Global Principles
Default Deny.

## High-Level Architecture
Skills call deterministic helpers.

## Cross-Component Rules
DOCUMENTATION drafts feed the existing documentation workflow.

## Current Stage
Phase 5.

## Component Index
| Component ID | Component Name | Role | Baseline Document | Status | Last Updated |
|---|---|---|---|---|---|
| workflow-control | Workflow Control | Owns workflow stages | docs/baselines/workflow-control.md | ACTIVE | 2026-08-20 |
"""
    component = """# Component Baseline: Workflow Control
Component ID: workflow-control
Version: v1.3
Last Updated: 2026-08-20

## Role
Own workflow authorization boundaries.

## Current Architecture
Five skills and deterministic helpers.

## Locked Decisions
### Decision D-001
Decision: Start-Implement stops before merge.
Reason: Merge authorization belongs to PR-Finalize.
Constraint / Consequence: Start-Implement must not merge.
Status: ACTIVE
Supersedes:
Evidence: issue:30, pr:31
Effective Date: 2026-08-20

## Interfaces / Contracts
Draft ID handoff.

## Constraints / Known Limits
Shared GitHub identity.

## Current Development State
Implemented: Phase 1-4.
Validated: Static tests.
Not Yet Validated: Phase 5 real curation.
Next Structural Work: Documentation-Curation.
"""

    parsed_project = parse_project_baseline(project)
    parsed_component = parse_component_baseline(component)

    assert parsed_project.components["workflow-control"].baseline_document == "docs/baselines/workflow-control.md"
    assert parsed_component.decisions["D-001"].status == "ACTIVE"

    with pytest.raises(BaselineSchemaError, match="section order"):
        parse_component_baseline(component.replace("## Role", "## Current Architecture", 1))

    conflicts = check_structural_conflicts(
        project,
        {
            "docs/baselines/workflow-control.md": component
            + "\n### Decision D-001\n"
            + "Decision: Duplicate\n"
            + "Reason: Duplicate.\n"
            + "Constraint / Consequence: Ambiguous baseline.\n"
            + "Status: ACTIVE\n"
            + "Supersedes:\n"
            + "Evidence: issue:30\n"
            + "Effective Date: 2026-08-21\n"
        },
        valid_references={"issue:30", "pr:31"},
    )
    assert {conflict.code for conflict in conflicts} >= {"DUPLICATE_DECISION_ID"}


def test_reference_resolution_patch_planning_rendering_and_versioning(tmp_path: Path) -> None:
    package = resolve_relationships(
        normalize_history(
            {
                "repository": "owner/repo",
                "issues": [{"number": 30, "updated_at": "2026-08-21T10:00:00Z", "state": "closed"}],
                "pull_requests": [{"number": 31, "updated_at": "2026-08-21T11:00:00Z", "state": "merged"}],
                "commits": [{"sha": "abc123"}],
            }
        )
    )
    resolver = ReferenceResolver(package)

    assert resolver.resolve("issue:30").url == "https://github.com/owner/repo/issues/30"
    assert resolver.resolve("pr:31").url == "https://github.com/owner/repo/pull/31"
    assert resolver.resolve("commit:abc123").url == "https://github.com/owner/repo/commit/abc123"
    with pytest.raises(ValueError, match="Unknown reference"):
        resolver.resolve("issue:404")

    analysis = CurationAnalysis(
        decisions=[
            DecisionProposal(
                decision_id="D-010",
                component="documentation-curation",
                proposed_classification="FINAL",
                decision="Documentation-Curation stops after a DOCUMENTATION draft.",
                short_reason="The Phase 5 handoff is the existing DOCUMENTATION workflow.",
                constraint_consequence="The skill must not create Issues, branches, PRs, or merges.",
                supersedes="",
                exact_references=("issue:30", "pr:31"),
                affected_baseline_section="Locked Decisions",
                proposed_baseline_action="ADD_DECISION",
            )
        ],
        findings=[
            DocumentationFinding(
                finding_id="F-001",
                component="documentation-curation",
                finding_type="UNRESOLVED_NONBLOCKING",
                conflict="One prior note calls curation a workflow, while Phase 5 makes it a draft entrypoint.",
                why_it_matters="The baseline should not describe a parallel workflow.",
                exact_references=("issue:30", "pr:31"),
                question="Should the baseline call it an entrypoint only?",
                affected_baseline_section="Role",
                blocking_impact="No block for the stop-boundary decision.",
            )
        ],
        new_components=[
            NewComponentProposal(
                component_id="documentation-curation",
                component_name="Documentation Curation",
                role="Curates history into baseline update proposals.",
                responsibility_boundary="Before DOCUMENTATION Start-Implement only.",
                parent_related_components=("workflow-control",),
                reason_for_separation="It owns independent schemas, cursoring, and draft rendering.",
                evidence=("issue:30",),
                suggested_baseline_path="docs/baselines/documentation-curation.md",
            )
        ],
        proposed_baseline_operations=[],
        pending_cursor=CurationCursor("2026-08-21T11:00:00Z", "pr:31"),
    )

    operations = plan_patch_operations(analysis)
    assert [operation.operation for operation in operations] == ["ADD_DECISION", "NO_CHANGE", "CREATE_COMPONENT_BASELINE"]
    assert operations[0].target_section == "Locked Decisions"

    drafts_dir = tmp_path / "drafts"
    draft = create_documentation_draft(
        DraftStore(drafts_dir),
        analysis.with_operations(operations),
        affected_project_documents=[
            "docs/baselines/high-level-project-baseline.md",
            "docs/baselines/documentation-curation.md",
        ],
    )

    assert draft.work_type == "DOCUMENTATION"
    assert draft.fields["Change"].startswith("Apply Documentation-Curation proposals")
    assert "D-010" in draft.fields["Reason"]
    assert "Pending Curation Cursor: 2026-08-21T11:00:00Z / pr:31" in draft.fields["Source PR / Decision Context"]
    assert (drafts_dir / f"{draft.draft_id}.json").exists()

    assert bump_version("v1.3") == "v1.4"
    assert "Last Updated: 2026-08-21" in set_last_updated("Version: v1.3\nLast Updated: 2026-08-20\n", "2026-08-21")


def test_documentation_curation_script_generates_draft_and_stops(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    analysis = tmp_path / "analysis.json"
    drafts = tmp_path / "drafts"
    output = tmp_path / "curation"

    history.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "issues": [{"number": 30, "updated_at": "2026-08-21T10:00:00Z", "state": "closed"}],
                "pull_requests": [{"number": 31, "updated_at": "2026-08-21T11:00:00Z", "state": "merged"}],
            }
        ),
        encoding="utf-8",
    )
    analysis.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "decision_id": "D-010",
                        "component": "documentation-curation",
                        "proposed_classification": "FINAL",
                        "decision": "Documentation-Curation stops after draft generation.",
                        "short_reason": "Phase 5 hands off to the existing documentation workflow.",
                        "constraint_consequence": "Do not create Issues, branches, PRs, or merges.",
                        "supersedes": "",
                        "exact_references": ["issue:30", "pr:31"],
                        "affected_baseline_section": "Locked Decisions",
                        "proposed_baseline_action": "ADD_DECISION",
                    }
                ],
                "findings": [],
                "new_components": [],
                "affected_project_documents": ["docs/baselines/high-level-project-baseline.md"],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "simple_flow_deploy/skill_resources/documentation-curation/scripts/curate_documentation.py",
            "--history-package",
            str(history),
            "--analysis",
            str(analysis),
            "--drafts-dir",
            str(drafts),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["stop_point"] == "DOCUMENTATION_DRAFT_CREATED"
    assert result["draft_id"].startswith("DRAFT-")
    assert result["created_issue"] is False
    assert result["created_pull_request"] is False
    assert (drafts / f"{result['draft_id']}.json").exists()
