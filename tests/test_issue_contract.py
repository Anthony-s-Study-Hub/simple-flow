from __future__ import annotations

import pytest

from simple_flow_gates.contracts import ContractError, IssueContract, WorkType
from tests.conftest import documentation_issue_body, feature_issue_body, project_change_issue_body


def test_legal_feature_issue_passes(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)

    assert issue.work_type == WorkType.FEATURE
    assert issue.fields["Roadmap Target"] == "PHASE_1_GOVERNANCE"


def test_missing_field_fails(roadmap_targets: set[str]) -> None:
    body = feature_issue_body().replace("\n## Roadmap Target\n\nPHASE_1_GOVERNANCE\n", "")

    with pytest.raises(ContractError, match="required fields in order"):
        IssueContract.parse(body, roadmap_targets)


def test_field_order_drift_fails(roadmap_targets: set[str]) -> None:
    body = feature_issue_body().replace(
        "## Requirements\n\n- Validate contracts.\n\n## Acceptance Criteria",
        "## Acceptance Criteria\n\n- Invalid contracts fail.\n\n## Requirements",
    )

    with pytest.raises(ContractError, match="required fields in order"):
        IssueContract.parse(body, roadmap_targets)


def test_unknown_top_level_field_fails(roadmap_targets: set[str]) -> None:
    body = feature_issue_body().replace(
        "## Roadmap Target",
        "## Surprise Field\n\nUnexpected.\n\n## Roadmap Target",
    )

    with pytest.raises(ContractError, match="required fields in order"):
        IssueContract.parse(body, roadmap_targets)


def test_feature_roadmap_target_must_be_configured(roadmap_targets: set[str]) -> None:
    body = feature_issue_body(roadmap="NOT_A_TARGET")

    with pytest.raises(ContractError, match="Roadmap Target"):
        IssueContract.parse(body, roadmap_targets)


def test_documentation_issue_passes_without_roadmap(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(documentation_issue_body(), roadmap_targets)

    assert issue.work_type == WorkType.DOCUMENTATION
    assert issue.scope_patterns == ["docs/phase1-governance.md"]


def test_legacy_project_change_issue_normalizes_to_documentation(
    roadmap_targets: set[str],
) -> None:
    issue = IssueContract.parse(project_change_issue_body(), roadmap_targets)

    assert issue.work_type == WorkType.DOCUMENTATION
    assert issue.scope_patterns == ["docs/phase1-governance.md"]

