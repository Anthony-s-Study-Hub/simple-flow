from __future__ import annotations

import json
from pathlib import Path

import pytest

from simple_flow_documentation_curation.baselines import (
    BaselineSchemaError,
    parse_component_baseline,
)
from simple_flow_documentation_curation.collector import collect_history
from simple_flow_documentation_curation.cursor import (
    CurationCursor,
    CurationCursorStore,
    commit_pending_cursor,
)
from simple_flow_documentation_curation.models import CurationAnalysis, DecisionProposal
from simple_flow_documentation_curation.normalizer import normalize_history
from simple_flow_documentation_curation.patch_planner import plan_patch_operations
from simple_flow_documentation_curation.references import ReferenceResolver
from simple_flow_documentation_curation.relationships import resolve_relationships
from simple_flow_documentation_curation.versioning import (
    bump_baseline_metadata,
    update_component_index_timestamp,
)


def test_history_collector_filters_incrementally_without_dropping_same_timestamp_items() -> None:
    package = collect_history(
        {
            "repository": "owner/repo",
            "issues": [
                {"number": 1, "updated_at": "2026-08-21T09:00:00Z", "state": "closed"},
                {"number": 2, "updated_at": "2026-08-21T10:00:00Z", "state": "open"},
                {
                    "number": 3,
                    "updated_at": "2026-08-21T10:00:00Z",
                    "state": "open",
                    "timeline": [{"event": "reopened", "created_at": "2026-08-21T10:00:00Z"}],
                },
            ],
            "pull_requests": [
                {
                    "number": 4,
                    "state": "merged",
                    "updated_at": "2026-08-21T11:00:00Z",
                    "merged_at": "2026-08-21T11:30:00Z",
                    "reviews": [{"id": "R1", "state": "APPROVED", "submitted_at": "2026-08-21T11:20:00Z"}],
                    "commits": [{"sha": "abc123"}],
                }
            ],
        },
        since=CurationCursor("2026-08-21T10:00:00Z", "issue:2"),
    )

    assert [item.id for item in package.work_items] == ["issue:3", "pr:4"]
    assert package.work_item("issue:3").reopened is True
    assert package.work_item("pr:4").merged_at == "2026-08-21T11:30:00Z"
    assert package.work_item("pr:4").reviews[0].state == "APPROVED"
    assert {commit.sha for commit in package.commits} == {"abc123"}


def test_curation_cursor_store_only_commits_pending_after_documentation_pr_merge(tmp_path: Path) -> None:
    store = CurationCursorStore(tmp_path)
    current = CurationCursor("2026-08-21T10:00:00Z", "issue:2")
    pending = CurationCursor("2026-08-21T11:00:00Z", "pr:4")

    store.write_committed(current)
    store.write_pending(pending)

    assert store.read_committed() == current
    assert store.read_pending() == pending
    assert store.finalize_pending(documentation_pr_merged=False) == current
    assert store.read_committed() == current
    assert store.finalize_pending(documentation_pr_merged=True) == pending
    assert store.read_committed() == pending
    assert commit_pending_cursor(
        current=pending,
        pending=CurationCursor("2026-08-21T09:00:00Z", "issue:1"),
        documentation_pr_merged=True,
    ) == pending


def test_reference_resolver_verifies_exact_review_comment_and_file_line_references() -> None:
    package = resolve_relationships(
        normalize_history(
            {
                "repository": "owner/repo",
                "pull_requests": [
                    {
                        "number": 31,
                        "updated_at": "2026-08-21T11:00:00Z",
                        "state": "merged",
                        "reviews": [{"id": "R1", "state": "APPROVED"}],
                        "comments": [{"id": "C1", "body": "Use the draft boundary."}],
                    }
                ],
                "commits": [{"sha": "abc123"}],
            }
        )
    )
    resolver = ReferenceResolver(package)

    assert resolver.resolve("pr:31#review:R1").url.endswith("/pull/31#pullrequestreview-R1")
    assert resolver.resolve("pr:31#comment:C1").url.endswith("/pull/31#discussion_rC1")
    assert (
        resolver.resolve("file:abc123:simple_flow_documentation_curation/renderer.py:10").url
        == "https://github.com/owner/repo/blob/abc123/simple_flow_documentation_curation/renderer.py#L10"
    )
    assert (
        resolver.resolve("file:abc123:simple_flow_documentation_curation/renderer.py:10-12").url
        == "https://github.com/owner/repo/blob/abc123/simple_flow_documentation_curation/renderer.py#L10-L12"
    )
    with pytest.raises(ValueError, match="Unknown review reference"):
        resolver.resolve("pr:31#review:R404")
    with pytest.raises(ValueError, match="Unknown comment reference"):
        resolver.resolve("pr:31#comment:C404")


def test_component_baseline_decision_fields_reject_wrong_order_and_unknown_fields() -> None:
    valid = _component_baseline()
    assert parse_component_baseline(valid).decisions["D-001"].decision == "Use draft boundary."

    wrong_order = valid.replace(
        "Decision: Use draft boundary.\nReason: It preserves the existing workflow.",
        "Reason: It preserves the existing workflow.\nDecision: Use draft boundary.",
    )
    with pytest.raises(BaselineSchemaError, match="field order"):
        parse_component_baseline(wrong_order)

    unknown = valid.replace(
        "Effective Date: 2026-08-21",
        "Effective Date: 2026-08-21\nDebug Notes: temporary",
    )
    with pytest.raises(BaselineSchemaError, match="unknown decision field"):
        parse_component_baseline(unknown)


def test_patch_planner_handles_supersede_and_version_manager_updates_component_index() -> None:
    analysis = CurationAnalysis(
        decisions=[
            DecisionProposal(
                decision_id="D-002",
                component="documentation-curation",
                proposed_classification="SUPERSEDED",
                decision="The old direct-baseline edit approach is superseded.",
                short_reason="Phase 5 requires draft-only handoff.",
                constraint_consequence="Formal baseline edits must use the DOCUMENTATION workflow.",
                supersedes="D-001",
                exact_references=("pr:31#review:R1",),
                affected_baseline_section="Locked Decisions",
                proposed_baseline_action="SUPERSEDE_DECISION",
            )
        ],
        findings=[],
        new_components=[],
        proposed_baseline_operations=[],
    )

    operations = plan_patch_operations(analysis)
    assert [operation.operation for operation in operations] == [
        "SUPERSEDE_DECISION",
        "UPDATE_DECISION",
    ]
    assert operations[1].payload["decision_id"] == "D-001"
    assert operations[1].payload["status"] == "SUPERSEDED"

    text = "Version: v1.3\nLast Updated: 2026-08-20\n"
    assert bump_baseline_metadata(text, "2026-08-21").splitlines() == [
        "Version: v1.4",
        "Last Updated: 2026-08-21",
    ]

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
| documentation-curation | Documentation Curation | Curates history | docs/baselines/documentation-curation.md | ACTIVE | 2026-08-20 |
"""
    updated = update_component_index_timestamp(project, "documentation-curation", "2026-08-21")
    assert "| documentation-curation | Documentation Curation | Curates history | docs/baselines/documentation-curation.md | ACTIVE | 2026-08-21 |" in updated


def test_phase5_scenario_fixture_includes_superseded_classification() -> None:
    from simple_flow_test_harness.scenarios import load_scenarios

    scenario = load_scenarios()["E06"]
    analysis_fixture = next(
        fixture
        for fixture in scenario.fixture_files
        if fixture.relative_path.endswith("E06-analysis.json")
    )
    analysis = json.loads(analysis_fixture.content)

    assert "SUPERSEDED" in {
        decision["proposed_classification"]
        for decision in analysis["decisions"]
    }
    assert any(
        rule.metric == "draft_text" and rule.expected == "SUPERSEDED"
        for rule in scenario.pass_rules
    )


def _component_baseline() -> str:
    return """# Component Baseline: Documentation Curation
Component ID: documentation-curation
Version: v1.3
Last Updated: 2026-08-21

## Role
Curate history.

## Current Architecture
Collector, analyzer input, validator, planner, renderer.

## Locked Decisions
### Decision D-001
Decision: Use draft boundary.
Reason: It preserves the existing workflow.
Constraint / Consequence: Do not create GitHub artifacts.
Status: ACTIVE
Supersedes:
Evidence: issue:30, pr:31
Effective Date: 2026-08-21

## Interfaces / Contracts
DOCUMENTATION draft handoff.

## Constraints / Known Limits
Human resolves blocking findings.

## Current Development State
Implemented: Core curation.
Validated: Static tests.
Not Yet Validated: Live curation.
Next Structural Work: Real history fixture.
"""
