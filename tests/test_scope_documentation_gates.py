from __future__ import annotations

import pytest

from simple_flow_gates.contracts import ContractError, IssueContract
from simple_flow_gates.scope import validate_documentation_gate, validate_scope_gate
from tests.conftest import feature_issue_body, project_change_issue_body


def test_scope_inside_declared_paths_passes(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)

    validate_scope_gate(issue, ["simple_flow_gates/contracts.py", "tests/test_issue_contract.py"])


def test_scope_outside_declared_paths_fails(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)

    with pytest.raises(ContractError, match="outside issue scope"):
        validate_scope_gate(issue, ["README.md"])


def test_documentation_impact_none_allows_no_doc_changes(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(docs="None"), roadmap_targets)

    validate_documentation_gate(issue, ["simple_flow_gates/contracts.py"])


def test_required_documentation_missing_fails(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(
        feature_issue_body(
            scope="- simple_flow_gates/\n- docs/phase1-governance.md",
            docs="- docs/phase1-governance.md",
        ),
        roadmap_targets,
    )

    with pytest.raises(ContractError, match="Documentation Impact requires"):
        validate_documentation_gate(issue, ["simple_flow_gates/contracts.py"])


def test_required_documentation_present_passes(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(
        feature_issue_body(
            scope="- simple_flow_gates/\n- docs/phase1-governance.md",
            docs="- docs/phase1-governance.md",
        ),
        roadmap_targets,
    )

    validate_documentation_gate(issue, ["simple_flow_gates/contracts.py", "docs/phase1-governance.md"])


def test_project_change_uses_affected_documents_for_scope_and_docs(
    roadmap_targets: set[str],
) -> None:
    issue = IssueContract.parse(project_change_issue_body(), roadmap_targets)

    validate_scope_gate(issue, ["docs/phase1-governance.md"])
    validate_documentation_gate(issue, ["docs/phase1-governance.md"])

