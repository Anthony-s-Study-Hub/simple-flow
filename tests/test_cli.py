from __future__ import annotations

from pathlib import Path

from simple_flow_gates.cli import main
from tests.conftest import feature_issue_body


def test_validate_issue_cli_passes(tmp_path: Path) -> None:
    issue_body = tmp_path / "issue.md"
    roadmap = tmp_path / "roadmap.txt"
    issue_body.write_text(feature_issue_body(), encoding="utf-8")
    roadmap.write_text("PHASE_1_GOVERNANCE\n", encoding="utf-8")

    assert main(
        [
            "validate-issue",
            "--issue-body",
            str(issue_body),
            "--roadmap-targets",
            str(roadmap),
        ]
    ) == 0


def test_validate_issue_cli_fails_for_bad_contract(tmp_path: Path) -> None:
    issue_body = tmp_path / "issue.md"
    roadmap = tmp_path / "roadmap.txt"
    issue_body.write_text("Type: FEATURE\n", encoding="utf-8")
    roadmap.write_text("PHASE_1_GOVERNANCE\n", encoding="utf-8")

    assert main(
        [
            "validate-issue",
            "--issue-body",
            str(issue_body),
            "--roadmap-targets",
            str(roadmap),
        ]
    ) == 1
