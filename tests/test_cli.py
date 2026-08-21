from __future__ import annotations

import json
from pathlib import Path

from simple_flow_gates.cli import main
from tests.conftest import documentation_issue_body, feature_issue_body, pr_body


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


def test_split_pr_contract_and_linked_issue_cli_commands_pass(tmp_path: Path) -> None:
    event_path = _write_pr_event(tmp_path)
    issue_body = _write_issue_body(tmp_path, feature_issue_body())
    roadmap = _write_roadmap(tmp_path)

    assert main(["validate-pr-contract", "--event-path", str(event_path)]) == 0
    assert (
        main(
            [
                "validate-linked-issue",
                "--issue-body",
                str(issue_body),
                "--roadmap-targets",
                str(roadmap),
            ]
        )
        == 0
    )


def test_split_scope_and_documentation_cli_commands_use_changed_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    issue_body = _write_issue_body(
        tmp_path,
        feature_issue_body(
            docs="- docs/phase1-governance.md",
            scope="- simple_flow_gates/\n- docs/",
        ),
    )
    roadmap = _write_roadmap(tmp_path)
    monkeypatch.setattr(
        "simple_flow_gates.cli.changed_files",
        lambda base_ref: ["simple_flow_gates/cli.py", "docs/phase1-governance.md"],
    )

    assert (
        main(
            [
                "validate-scope",
                "--issue-body",
                str(issue_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "validate-documentation-impact",
                "--issue-body",
                str(issue_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
            ]
        )
        == 0
    )

    monkeypatch.setattr(
        "simple_flow_gates.cli.changed_files",
        lambda base_ref: ["simple_flow_gates/cli.py"],
    )
    assert (
        main(
            [
                "validate-documentation-impact",
                "--issue-body",
                str(issue_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
            ]
        )
        == 1
    )


def test_split_tdd_evidence_cli_preserves_feature_and_documentation_rules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    event_path = _write_pr_event(tmp_path)
    feature_body = _write_issue_body(tmp_path, feature_issue_body())
    documentation_body = _write_issue_body(
        tmp_path,
        documentation_issue_body(),
        name="documentation.md",
    )
    roadmap = _write_roadmap(tmp_path)
    evidence = _write_tdd_evidence(tmp_path)
    monkeypatch.setattr(
        "simple_flow_gates.cli.commit_history",
        lambda base_ref: ["red", "implementation", "green"],
    )

    assert (
        main(
            [
                "validate-tdd-evidence",
                "--event-path",
                str(event_path),
                "--issue-body",
                str(feature_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
                "--tdd-evidence",
                str(evidence),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "validate-tdd-evidence",
                "--event-path",
                str(event_path),
                "--issue-body",
                str(documentation_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "validate-tdd-evidence",
                "--event-path",
                str(event_path),
                "--issue-body",
                str(feature_body),
                "--roadmap-targets",
                str(roadmap),
                "--base-ref",
                "origin/main",
            ]
        )
        == 1
    )


def _write_issue_body(tmp_path: Path, body: str, *, name: str = "issue.md") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _write_roadmap(tmp_path: Path) -> Path:
    path = tmp_path / "roadmap.txt"
    path.write_text("PHASE_1_GOVERNANCE\n", encoding="utf-8")
    return path


def _write_pr_event(tmp_path: Path) -> Path:
    path = tmp_path / "event.json"
    path.write_text(
        json.dumps(
            {
                "action": "synchronize",
                "pull_request": {
                    "body": pr_body(123),
                    "head": {"ref": "feature/123-meaningful-ci"},
                    "base": {"ref": "main"},
                    "draft": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_tdd_evidence(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            {
                "issue": 123,
                "red": {
                    "commit": "red",
                    "command": "python -m pytest",
                    "exit_code": 1,
                },
                "implementation": {"commit": "implementation"},
                "green": {
                    "commit": "green",
                    "command": "python -m pytest",
                    "exit_code": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path
