from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
UNPREFIXED_SKILLS = [
    "discussion",
    "issue-draft",
    "start-implement",
    "review-triage",
    "pr-finalize",
]
SKILL_SCRIPTS = {
    "discussion": [],
    "issue-draft": ["scripts/create_draft.py"],
    "start-implement": ["scripts/select_path.py"],
    "review-triage": ["scripts/classify_finding.py"],
    "pr-finalize": ["scripts/check_pre_merge.py"],
}


def test_installer_populates_required_files_with_unprefixed_skills(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    report = _install(target)

    assert report["status"] == "success"
    assert (target / "AGENTS.md").exists()
    assert (target / ".github" / "workflows" / "phase1-gates.yml").exists()
    assert (target / ".github" / "workflows" / "phase1-tests.yml").exists()
    assert (target / ".github" / "ISSUE_TEMPLATE" / "feature.md").exists()
    assert (target / ".github" / "pull_request_template.md").exists()
    assert (target / "simple_flow_gates" / "contracts.py").exists()
    assert (target / "simple_flow_agent" / "drafts.py").exists()
    assert (target / "scripts" / "orphan_branch_watch.py").exists()
    assert (target / ".simple-flow" / "project-config.json").exists()
    assert (target / "docs" / "simple-flow" / "usage-guide.md").exists()
    assert (target / "docs" / "simple-flow" / "project-integration-guide.md").exists()
    assert (target / "docs" / "simple-flow" / "github-setup-guide.md").exists()

    for skill_name in UNPREFIXED_SKILLS:
        skill_file = target / ".codex" / "skills" / skill_name / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        assert skill_file.exists()
        assert f"name: {skill_name}" in text
        assert "simple-flow-" not in str(skill_file)
        assert "name: simple-flow-" not in text
        for script in SKILL_SCRIPTS[skill_name]:
            assert (target / ".codex" / "skills" / skill_name / script).exists()
            assert script in text


def test_repeated_install_is_idempotent_and_reports_existing_files(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    first = _install(target)
    second = _install(target)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["created"] == []
    assert second["skipped"]
    assert len(list((target / ".codex" / "skills").glob("*/SKILL.md"))) == 5
    assert (target / "AGENTS.md").read_text(encoding="utf-8").count("Default Deny") == 2


def test_conflicting_existing_file_is_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    target.mkdir()
    (target / "AGENTS.md").write_text("local project policy\n", encoding="utf-8")

    report = _install(target, check=False)

    assert report["status"] == "conflict"
    assert any(item["path"] == "AGENTS.md" for item in report["conflicts"])
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "local project policy\n"


def test_config_isolation_for_two_different_project_shapes(tmp_path: Path) -> None:
    ordinary = tmp_path / "ordinary-python"
    alternate = tmp_path / "alternate-node-layout"
    ordinary.mkdir()
    alternate.mkdir()
    (ordinary / "src").mkdir()
    (alternate / "packages").mkdir()

    ordinary_report = _install(
        ordinary,
        "--project-name",
        "ordinary-python",
        "--test-command",
        "python -m pytest",
        "--scope",
        "src/",
    )
    alternate_report = _install(
        alternate,
        "--project-name",
        "alternate-node-layout",
        "--test-command",
        "npm test",
        "--scope",
        "packages/",
    )

    ordinary_config = json.loads(
        (ordinary / ".simple-flow" / "project-config.json").read_text(encoding="utf-8")
    )
    alternate_config = json.loads(
        (alternate / ".simple-flow" / "project-config.json").read_text(encoding="utf-8")
    )

    assert ordinary_report["status"] == "success"
    assert alternate_report["status"] == "success"
    assert ordinary_config["test_command"] == "python -m pytest"
    assert alternate_config["test_command"] == "npm test"
    assert ordinary_config["scope"] == ["src/"]
    assert alternate_config["scope"] == ["packages/"]
    assert _hash_core_files(ordinary) == _hash_core_files(alternate)


def test_reference_integrity_and_required_check_names(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _install(target)

    phase1_gates = (target / ".github" / "workflows" / "phase1-gates.yml").read_text(
        encoding="utf-8"
    )
    repo_rules = (target / "simple_flow_gates" / "repository_rules.py").read_text(
        encoding="utf-8"
    )

    assert "python -m simple_flow_gates.cli validate-pr" in phase1_gates
    assert "scripts.orphan_branch_watch" in (
        target / ".github" / "workflows" / "orphan-branch-watch.yml"
    ).read_text(encoding="utf-8")
    assert '"phase1-gates"' in repo_rules
    assert '"phase1-tests"' in repo_rules
    assert str(ROOT) not in phase1_gates
    assert "C:\\\\" not in phase1_gates
    assert "Anthony-s-Study-Hub/simple-flow" not in phase1_gates
    _assert_deployed_skill_script_references_exist(target)


def test_deployed_phase1_and_phase2_regressions_pass(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _install(target)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_issue_contract.py",
            "tests/test_branch_pr_gate.py",
            "tests/test_scope_documentation_gates.py",
            "tests/test_tdd_gate.py",
            "tests/test_phase2_workflow.py",
        ],
        cwd=target,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "passed" in completed.stdout

    skill_files = list((target / ".codex" / "skills").glob("*/SKILL.md"))
    skill_text = "\n".join(path.read_text(encoding="utf-8") for path in skill_files)
    assert sorted(path.parent.name for path in skill_files) == sorted(UNPREFIXED_SKILLS)
    assert "Permission: generate-canonical-draft" in skill_text
    assert "Permission: publish-formal-issue" in skill_text
    assert "Permission: merge-pull-request" in skill_text
    assert "Default Deny" in (target / "AGENTS.md").read_text(encoding="utf-8")


def test_real_target_project_destination_is_successfully_set_up() -> None:
    target = ROOT.parent / "Phase3_Target_Project"
    report = _install(
        target,
        "--project-name",
        "phase3-target-project",
        "--test-command",
        "python -m pytest checks",
        "--scope",
        "app/",
        "--clean-target",
    )

    assert report["status"] == "success"
    assert (target / "AGENTS.md").exists()
    assert sorted(path.parent.name for path in (target / ".codex" / "skills").glob("*/SKILL.md")) == sorted(
        UNPREFIXED_SKILLS
    )
    assert not any(
        path.parent.name.startswith("simple-flow-")
        for path in (target / ".codex" / "skills").glob("*/SKILL.md")
    )


def _install(target: Path, *args: str, check: bool = True) -> dict[str, object]:
    command = [
        sys.executable,
        "scripts/install_simple_flow.py",
        "--target",
        str(target),
        *args,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    if not check and completed.returncode == 0:
        raise AssertionError("installer was expected to report a conflict")
    return json.loads(completed.stdout)


def _hash_core_files(project: Path) -> dict[str, str]:
    files = {}
    for relative in [
        "AGENTS.md",
        ".github/workflows/phase1-gates.yml",
        ".github/workflows/phase1-tests.yml",
        ".codex/skills/discussion/SKILL.md",
        ".codex/skills/issue-draft/SKILL.md",
        ".codex/skills/issue-draft/scripts/create_draft.py",
        "simple_flow_gates/contracts.py",
        "simple_flow_agent/drafts.py",
    ]:
        files[relative] = (project / relative).read_text(encoding="utf-8")
    return files


def _assert_deployed_skill_script_references_exist(target: Path) -> None:
    for skill, scripts in SKILL_SCRIPTS.items():
        skill_dir = target / ".codex" / "skills" / skill
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for script in scripts:
            assert script in skill_text
            assert (skill_dir / script).exists()
