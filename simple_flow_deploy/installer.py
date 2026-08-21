from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil


SKILL_MAP = {
    "simple-flow-discussion": "discussion",
    "simple-flow-issue-draft": "issue-draft",
    "simple-flow-start-implement": "start-implement",
    "simple-flow-review-triage": "review-triage",
    "simple-flow-pr-finalize": "pr-finalize",
}

CORE_FILES = [
    "AGENTS.md",
    ".github/ISSUE_TEMPLATE/feature.md",
    ".github/ISSUE_TEMPLATE/documentation.md",
    ".github/pull_request_template.md",
    ".github/workflows/phase1-gates.yml",
    ".github/workflows/phase1-tests.yml",
    ".github/workflows/orphan-branch-watch.yml",
    ".simple-flow/roadmap-targets.txt",
    "simple_flow_gates/__init__.py",
    "simple_flow_gates/branch_pr.py",
    "simple_flow_gates/cli.py",
    "simple_flow_gates/contracts.py",
    "simple_flow_gates/git_utils.py",
    "simple_flow_gates/orphan.py",
    "simple_flow_gates/repository_rules.py",
    "simple_flow_gates/scope.py",
    "simple_flow_gates/tdd.py",
    "simple_flow_agent/__init__.py",
    "simple_flow_agent/drafts.py",
    "simple_flow_agent/finalize.py",
    "simple_flow_agent/review_triage.py",
    "simple_flow_agent/start_implement.py",
    "scripts/__init__.py",
    "scripts/configure_repository.ps1",
    "scripts/orphan_branch_watch.py",
    "scripts/phase2_acceptance.py",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_branch_pr_gate.py",
    "tests/test_cli.py",
    "tests/test_issue_contract.py",
    "tests/test_orphan_and_repository_rules.py",
    "tests/test_orphan_branch_watch_script.py",
    "tests/test_phase2_workflow.py",
    "tests/test_scope_documentation_gates.py",
    "tests/test_tdd_gate.py",
    "tests/test_workflows.py",
]

DOC_FILES = {
    "docs/deployment/usage-guide.md": "docs/simple-flow/usage-guide.md",
    "docs/deployment/project-integration-guide.md": "docs/simple-flow/project-integration-guide.md",
    "docs/deployment/github-setup-guide.md": "docs/simple-flow/github-setup-guide.md",
}

SKILL_RESOURCE_ROOT = Path("simple_flow_deploy/skill_resources")


@dataclass
class InstallReport:
    status: str = "success"
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    target: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "target": self.target,
                "created": self.created,
                "skipped": self.skipped,
                "conflicts": self.conflicts,
                "failures": self.failures,
            },
            indent=2,
        )


def install(
    *,
    source_root: str | Path,
    target: str | Path,
    project_name: str = "new-project",
    test_command: str = "python -m pytest",
    scope: list[str] | None = None,
    documentation: list[str] | None = None,
    clean_target: bool = False,
) -> InstallReport:
    source = Path(source_root).resolve()
    destination = Path(target).resolve()
    report = InstallReport(target=str(destination))

    if clean_target:
        _clean_target(destination)

    destination.mkdir(parents=True, exist_ok=True)
    desired = _desired_files(
        source,
        project_name=project_name,
        test_command=test_command,
        scope=scope or ["src/"],
        documentation=documentation or ["docs/"],
    )

    conflicts = _find_conflicts(destination, desired)
    if conflicts:
        report.status = "conflict"
        report.conflicts = conflicts
        return report

    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") == content:
            report.skipped.append(relative)
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        report.created.append(relative)

    return report


def _desired_files(
    source: Path,
    *,
    project_name: str,
    test_command: str,
    scope: list[str],
    documentation: list[str],
) -> dict[str, str]:
    files: dict[str, str] = {}
    for relative in CORE_FILES:
        text = (source / relative).read_text(encoding="utf-8")
        if relative.startswith(".github/workflows/"):
            text = _portable_workflow(text)
        files[relative] = text

    for source_skill, target_skill in SKILL_MAP.items():
        source_dir = source / "skills" / source_skill
        skill_text = (source_dir / "SKILL.md").read_text(encoding="utf-8")
        files[f".codex/skills/{target_skill}/SKILL.md"] = skill_text.replace(
            f"name: {source_skill}",
            f"name: {target_skill}",
        )

        resource_dir = source / SKILL_RESOURCE_ROOT / target_skill
        if not resource_dir.exists():
            continue
        for path in resource_dir.rglob("*"):
            if not path.is_file():
                continue
            skill_relative = path.relative_to(resource_dir)
            text = path.read_text(encoding="utf-8")
            files[
                f".codex/skills/{target_skill}/{skill_relative.as_posix()}"
            ] = text

    for source_doc, target_doc in DOC_FILES.items():
        files[target_doc] = (source / source_doc).read_text(encoding="utf-8")

    files[".simple-flow/project-config.json"] = (
        json.dumps(
            {
                "project_name": project_name,
                "test_command": test_command,
                "scope": scope,
                "documentation": documentation,
                "roadmap_target_source": "GitHub Projects or .simple-flow/roadmap-targets.txt",
            },
            indent=2,
        )
        + "\n"
    )
    files[".simple-flow/README.md"] = _project_readme(project_name)
    return files


def _portable_workflow(text: str) -> str:
    return text.replace(
        'python -m pip install -e ".[test]"',
        "python -m pip install pytest",
    )


def _find_conflicts(destination: Path, desired: dict[str, str]) -> list[dict[str, str]]:
    conflicts = []
    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") != content:
            conflicts.append(
                {
                    "path": relative,
                    "reason": "exists with different content",
                }
            )
    return conflicts


def _clean_target(destination: Path) -> None:
    if not destination.exists():
        return
    manifest = destination / ".simple-flow" / "project-config.json"
    if destination.name != "Phase3_Target_Project" and not manifest.exists():
        raise ValueError(f"Refusing to clean unmanaged target: {destination}")
    shutil.rmtree(destination)


def _project_readme(project_name: str) -> str:
    return (
        f"# {project_name} Simple Flow Setup\n\n"
        "This directory contains the installed Simple Flow controlled development workflow.\n"
        "Project-specific settings live in `.simple-flow/project-config.json`.\n"
    )

