from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from simple_flow_gates.contracts import ContractError, IssueContract
from simple_flow_gates.tdd import (
    PhaseEvidence,
    TddEvidence,
    validate_tdd_gate,
    verify_tdd_commands,
)
import simple_flow_gates.tdd as tdd
from tests.conftest import documentation_issue_body, feature_issue_body


def test_feature_with_real_red_green_evidence_passes(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)
    evidence = _evidence(red_exit=1)

    validate_tdd_gate(issue, 123, evidence, ["red", "implementation", "green"])


def test_feature_without_red_evidence_fails(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)

    with pytest.raises(ContractError, match="requires TDD evidence"):
        validate_tdd_gate(issue, 123, None, ["implementation", "green"])


def test_red_phase_that_actually_passed_fails(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)
    evidence = _evidence(red_exit=0)

    with pytest.raises(ContractError, match="RED phase"):
        validate_tdd_gate(issue, 123, evidence, ["red", "implementation", "green"])


def test_red_commit_later_than_implementation_fails(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(feature_issue_body(), roadmap_targets)
    evidence = _evidence(red_exit=1)

    with pytest.raises(ContractError, match="ordered RED"):
        validate_tdd_gate(issue, 123, evidence, ["implementation", "red", "green"])


def test_documentation_does_not_trigger_tdd_gate(roadmap_targets: set[str]) -> None:
    issue = IssueContract.parse(documentation_issue_body(), roadmap_targets)

    validate_tdd_gate(issue, 123, None, ["implementation"])


def test_tdd_command_replay_passes_for_real_red_green_commits(tmp_path: Path) -> None:
    evidence, history = _make_tdd_repo(tmp_path, red_has_implementation=False)

    validate_tdd_gate(
        IssueContract.parse(feature_issue_body(), {"PHASE_1_GOVERNANCE"}),
        123,
        evidence,
        history,
    )
    verify_tdd_commands(evidence, repo_path=tmp_path)


def test_tdd_command_replay_can_verify_red_and_green_separately(tmp_path: Path) -> None:
    evidence, _history = _make_tdd_repo(tmp_path, red_has_implementation=False)

    tdd.verify_tdd_command(evidence, "red", repo_path=tmp_path)
    tdd.verify_tdd_command(evidence, "green", repo_path=tmp_path)


def test_tdd_command_replay_fails_when_red_commit_actually_passes(tmp_path: Path) -> None:
    evidence, _history = _make_tdd_repo(tmp_path, red_has_implementation=True)

    with pytest.raises(ContractError, match="RED command exit code mismatch"):
        verify_tdd_commands(evidence, repo_path=tmp_path)


def _evidence(red_exit: int) -> TddEvidence:
    return TddEvidence(
        issue=123,
        red=PhaseEvidence(commit="red", command="python -m pytest", exit_code=red_exit),
        implementation_commit="implementation",
        green=PhaseEvidence(commit="green", command="python -m pytest", exit_code=0),
    )


def _make_tdd_repo(tmp_path: Path, *, red_has_implementation: bool) -> tuple[TddEvidence, list[str]]:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "phase1@example.com")
    _git(tmp_path, "config", "user.name", "Phase 1 Test")

    (tmp_path / "test_flow.py").write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('implemented.txt').exists() else 1)\n",
        encoding="utf-8",
    )
    if red_has_implementation:
        (tmp_path / "implemented.txt").write_text("already present\n", encoding="utf-8")
    _git(tmp_path, "add", "test_flow.py")
    if red_has_implementation:
        _git(tmp_path, "add", "implemented.txt")
    _git(tmp_path, "commit", "-m", "red")
    red = _git_output(tmp_path, "rev-parse", "HEAD")

    (tmp_path / "implemented.txt").write_text("done\n", encoding="utf-8")
    _git(tmp_path, "add", "implemented.txt")
    _git(tmp_path, "commit", "-m", "implementation")
    implementation = _git_output(tmp_path, "rev-parse", "HEAD")

    (tmp_path / "green.txt").write_text("green evidence marker\n", encoding="utf-8")
    _git(tmp_path, "add", "green.txt")
    _git(tmp_path, "commit", "-m", "green")
    green = _git_output(tmp_path, "rev-parse", "HEAD")

    return (
        TddEvidence(
            issue=123,
            red=PhaseEvidence(commit=red, command="python test_flow.py", exit_code=1),
            implementation_commit=implementation,
            green=PhaseEvidence(commit=green, command="python test_flow.py", exit_code=0),
        ),
        [red, implementation, green],
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _git_output(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
