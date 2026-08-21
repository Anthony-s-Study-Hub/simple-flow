from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import os
import subprocess
import tempfile

from simple_flow_gates.contracts import ContractError, IssueContract, WorkType


@dataclass(frozen=True)
class PhaseEvidence:
    commit: str
    command: str
    exit_code: int


@dataclass(frozen=True)
class TddEvidence:
    issue: int
    red: PhaseEvidence
    implementation_commit: str
    green: PhaseEvidence

    @classmethod
    def from_json(cls, raw: str) -> "TddEvidence":
        data = json.loads(raw)
        return cls(
            issue=int(data["issue"]),
            red=PhaseEvidence(
                commit=data["red"]["commit"],
                command=data["red"]["command"],
                exit_code=int(data["red"]["exit_code"]),
            ),
            implementation_commit=data["implementation"]["commit"],
            green=PhaseEvidence(
                commit=data["green"]["commit"],
                command=data["green"]["command"],
                exit_code=int(data["green"]["exit_code"]),
            ),
        )

    @classmethod
    def from_path(cls, path: str | Path) -> "TddEvidence":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def validate_tdd_gate(
    issue: IssueContract,
    linked_issue_number: int,
    evidence: TddEvidence | None,
    commit_history: list[str],
) -> None:
    if issue.work_type == WorkType.DOCUMENTATION:
        return

    if evidence is None:
        raise ContractError("FEATURE work requires TDD evidence.")
    if evidence.issue != linked_issue_number:
        raise ContractError(
            f"TDD evidence issue #{evidence.issue} does not match linked issue #{linked_issue_number}."
        )
    if evidence.red.exit_code == 0:
        raise ContractError("RED phase evidence must record a failing test command.")
    if evidence.green.exit_code != 0:
        raise ContractError("GREEN phase evidence must record a passing test command.")

    positions = _commit_positions(commit_history)
    required = [evidence.red.commit, evidence.implementation_commit, evidence.green.commit]
    missing = [commit for commit in required if commit not in positions]
    if missing:
        raise ContractError("TDD evidence references commit(s) outside PR history: " + ", ".join(missing))

    red_index = positions[evidence.red.commit]
    implementation_index = positions[evidence.implementation_commit]
    green_index = positions[evidence.green.commit]
    if not red_index < implementation_index < green_index:
        raise ContractError("TDD evidence must be ordered RED before implementation before GREEN.")


def verify_tdd_commands(
    evidence: TddEvidence,
    repo_path: str | Path = ".",
    timeout_seconds: int = 300,
) -> None:
    verify_tdd_command(evidence, "red", repo_path=repo_path, timeout_seconds=timeout_seconds)
    verify_tdd_command(evidence, "green", repo_path=repo_path, timeout_seconds=timeout_seconds)


def verify_tdd_command(
    evidence: TddEvidence,
    phase: str,
    repo_path: str | Path = ".",
    timeout_seconds: int = 300,
) -> None:
    normalized_phase = phase.lower()
    if normalized_phase == "red":
        label = "RED"
        phase_evidence = evidence.red
    elif normalized_phase == "green":
        label = "GREEN"
        phase_evidence = evidence.green
    else:
        raise ContractError(f"Unsupported TDD phase: {phase}")

    repo = Path(repo_path)
    with tempfile.TemporaryDirectory(prefix="simple-flow-tdd-") as tmpdir:
        worktree = Path(tmpdir) / normalized_phase
        _git(["worktree", "add", "--detach", str(worktree), phase_evidence.commit], repo)
        try:
            observed = _run_evidence_command(
                phase_evidence.command,
                worktree,
                timeout_seconds,
            )
        finally:
            _git(["worktree", "remove", "--force", str(worktree)], repo)
        if observed != phase_evidence.exit_code:
            raise ContractError(
                f"{label} command exit code mismatch at {phase_evidence.commit}: "
                f"expected {phase_evidence.exit_code}, observed {observed}."
            )


def _commit_positions(commit_history: list[str]) -> dict[str, int]:
    return {commit: index for index, commit in enumerate(commit_history)}


def _run_evidence_command(command: str, cwd: Path, timeout_seconds: int) -> int:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(cwd)
        if not existing_pythonpath
        else str(cwd) + os.pathsep + existing_pythonpath
    )
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        shell=True,
        timeout=timeout_seconds,
    )
    return completed.returncode


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
