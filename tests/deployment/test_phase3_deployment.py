from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SSOT_SCRIPT_ROOT = ROOT / "simple_flow_deploy" / "skill_resources"
UNPREFIXED_SKILLS = [
    "discussion",
    "documentation-curation",
    "issue-draft",
    "start-implement",
    "review-triage",
    "pr-finalize",
]
SKILL_SCRIPTS = {
    "discussion": [],
    "documentation-curation": ["scripts/curate_documentation.py"],
    "issue-draft": ["scripts/create_draft.py"],
    "start-implement": ["scripts/select_path.py", "scripts/start_documentation.py"],
    "review-triage": ["scripts/classify_finding.py"],
    "pr-finalize": ["scripts/check_pre_merge.py"],
}


def test_installer_populates_required_files_with_unprefixed_skills(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    report = _install(target)

    assert report["status"] == "success"
    assert (target / "AGENTS.md").exists()
    assert (target / ".github" / "workflows" / "issue-governance.yml").exists()
    assert (target / ".github" / "workflows" / "pr-governance.yml").exists()
    assert (target / ".github" / "workflows" / "phase1-tests.yml").exists()
    assert not (target / ".github" / "workflows" / "phase1-gates.yml").exists()
    assert (target / ".github" / "ISSUE_TEMPLATE" / "feature.md").exists()
    assert (target / ".github" / "ISSUE_TEMPLATE" / "documentation.md").exists()
    assert not (target / ".github" / "ISSUE_TEMPLATE" / "project_change.md").exists()
    assert (target / ".github" / "pull_request_template.md").exists()
    assert not (target / "simple_flow_gates").exists()
    assert not (target / "simple_flow_agent").exists()
    assert not (target / "simple_flow_documentation_curation").exists()
    assert not (target / "tests").exists()
    assert (target / "scripts" / "orphan_branch_watch.py").exists()
    assert (target / ".simple-flow" / "project-config.json").exists()
    assert (target / ".simple-flow" / "baselines" / "high-level-project-baseline.md").exists()
    assert (target / ".simple-flow" / "baselines" / "component-baseline-template.md").exists()
    assert (target / "docs" / "simple-flow" / "usage-guide.md").exists()
    assert (target / "docs" / "simple-flow" / "project-integration-guide.md").exists()
    assert (target / "docs" / "simple-flow" / "github-setup-guide.md").exists()

    for skill_name in UNPREFIXED_SKILLS:
        skill_file = target / ".codex" / "skills" / skill_name / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        expected = (ROOT / "simple_flow_deploy" / "assets" / "skills" / f"simple-flow-{skill_name}" / "SKILL.md").read_text(encoding="utf-8").replace(
            f"name: simple-flow-{skill_name}", f"name: {skill_name}"
        )
        assert skill_file.exists()
        assert text == expected
        assert f"name: {skill_name}" in text
        assert "simple-flow-" not in str(skill_file)
        assert "name: simple-flow-" not in text
        if skill_name == "start-implement":
            assert "derive `--repo` from\n   `git remote get-url origin`" in text
        for script in SKILL_SCRIPTS[skill_name]:
            deployed_script = target / ".codex" / "skills" / skill_name / script
            ssot_script = SSOT_SCRIPT_ROOT / skill_name / script
            assert ssot_script.exists()
            assert deployed_script.exists()
            assert deployed_script.read_text(encoding="utf-8") == ssot_script.read_text(
                encoding="utf-8"
            )
            assert script in text


def test_public_package_deploys_the_canonical_skill_text(tmp_path: Path) -> None:
    target = tmp_path / "public-package"
    _install(target)

    for source_skill, target_skill in {
        "simple-flow-discussion": "discussion",
        "simple-flow-documentation-curation": "documentation-curation",
        "simple-flow-issue-draft": "issue-draft",
        "simple-flow-start-implement": "start-implement",
        "simple-flow-review-triage": "review-triage",
        "simple-flow-pr-finalize": "pr-finalize",
    }.items():
        expected = (ROOT / "simple_flow_deploy" / "assets" / "skills" / source_skill / "SKILL.md").read_text(encoding="utf-8").replace(
            f"name: {source_skill}", f"name: {target_skill}"
        )
        if target_skill == "start-implement":
            assert "derive `--repo` from\n   `git remote get-url origin`" in expected
        assert (target / ".codex" / "skills" / target_skill / "SKILL.md").read_text(encoding="utf-8") == expected


def test_repeated_install_is_idempotent_and_reports_existing_files(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    first = _install(target)
    second = _install(target)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["created"] == []
    assert second["skipped"]
    assert len(list((target / ".codex" / "skills").glob("*/SKILL.md"))) == 6
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
    assert "run: python -m pytest" in (
        ordinary / ".github" / "workflows" / "phase1-tests.yml"
    ).read_text(encoding="utf-8")
    assert "run: npm test" in (
        alternate / ".github" / "workflows" / "phase1-tests.yml"
    ).read_text(encoding="utf-8")
    assert _hash_core_files(ordinary) == _hash_core_files(alternate)


def test_reference_integrity_and_required_check_names(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _install(target)

    pr_governance = (target / ".github" / "workflows" / "pr-governance.yml").read_text(
        encoding="utf-8"
    )
    issue_governance = (target / ".github" / "workflows" / "issue-governance.yml").read_text(
        encoding="utf-8"
    )
    phase1_tests = (target / ".github" / "workflows" / "phase1-tests.yml").read_text(
        encoding="utf-8"
    )
    repo_rules = (ROOT / "simple_flow_gates" / "repository_rules.py").read_text(
        encoding="utf-8"
    )

    assert "python -m simple_flow_gates.cli validate-issue" in issue_governance
    assert "python -m simple_flow_gates.cli validate-pr-contract" in pr_governance
    assert "python -m simple_flow_gates.cli validate-linked-issue" in pr_governance
    assert "python -m simple_flow_gates.cli validate-scope" in pr_governance
    assert "python -m simple_flow_gates.cli validate-documentation-impact" in pr_governance
    assert "python -m simple_flow_gates.cli validate-tdd-evidence" in pr_governance
    assert "python -m simple_flow_gates.cli verify-tdd-red" in pr_governance
    assert "python -m simple_flow_gates.cli verify-tdd-green" in pr_governance
    assert "current-head-tests" in phase1_tests
    assert "scripts.orphan_branch_watch" in (
        target / ".github" / "workflows" / "orphan-branch-watch.yml"
    ).read_text(encoding="utf-8")
    for check in [
        "pr-contract",
        "linked-issue-contract",
        "scope-governance",
        "documentation-impact",
        "tdd-evidence-order",
        "tdd-red-replay",
        "tdd-green-replay",
        "current-head-tests",
    ]:
        assert f'"{check}"' in repo_rules
    assert '"phase1-gates"' not in repo_rules
    assert '"phase1-tests"' not in repo_rules
    assert str(ROOT) not in pr_governance
    assert "C:\\\\" not in pr_governance
    assert (
        "git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v0.2.1"
        in pr_governance
    )
    _assert_deployed_skill_script_references_exist(target)


def test_documentation_start_script_plan_only_validates_append_change(tmp_path: Path) -> None:
    from simple_flow_agent.drafts import DraftStore

    drafts_dir = tmp_path / "drafts"
    draft = DraftStore(drafts_dir).create_documentation(
        change="Append 'Phase 4 smoke marker: remote artifact path verified.' to docs/simple-flow/usage-guide.md",
        reason="Prove remote artifact creation",
        impact="Smoke validation only",
        supersedes="None",
        affected_project_documents=["docs/simple-flow/usage-guide.md"],
        source_context="Phase 4 test",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SSOT_SCRIPT_ROOT / "start-implement" / "scripts" / "start_documentation.py"),
            "--draft-id",
            draft.draft_id,
            "--drafts-dir",
            str(drafts_dir),
            "--repo",
            "owner/repo",
            "--plan-only",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["status"] == "planned"
    assert plan["doc_path"] == "docs/simple-flow/usage-guide.md"
    assert plan["marker"] == "Phase 4 smoke marker: remote artifact path verified."
    assert plan["issue_title"].startswith("Append")


def test_documentation_start_script_scrubs_proxy_env_for_gh(monkeypatch) -> None:
    module = _load_script_module(
        SSOT_SCRIPT_ROOT / "start-implement" / "scripts" / "start_documentation.py"
    )
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")

    env = module.command_env(["gh", "issue", "create"])

    assert "HTTPS_PROXY" not in env
    assert "ALL_PROXY" not in env


def test_deployed_payload_matches_public_package_ssot(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _install(target)

    manifest = json.loads(
        (target / ".simple-flow" / "install-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["install_mode"] == "thin"
    assert manifest["release_source"].startswith(
        "git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v"
    )
    assert not (target / "tests").exists()
    assert not (target / "simple_flow_gates").exists()

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
        "-m",
        "simple_flow_deploy.cli",
        "install",
        str(target),
        *args,
        "--json",
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
        ".github/workflows/issue-governance.yml",
        ".github/workflows/pr-governance.yml",
        ".codex/skills/discussion/SKILL.md",
        ".codex/skills/documentation-curation/SKILL.md",
        ".codex/skills/documentation-curation/scripts/curate_documentation.py",
        ".codex/skills/issue-draft/SKILL.md",
        ".codex/skills/issue-draft/scripts/create_draft.py",
    ]:
        files[relative] = (project / relative).read_text(encoding="utf-8")
    return files


def _assert_deployed_skill_script_references_exist(target: Path) -> None:
    for skill, scripts in SKILL_SCRIPTS.items():
        skill_dir = target / ".codex" / "skills" / skill
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for script in scripts:
            ssot_script = SSOT_SCRIPT_ROOT / skill / script
            deployed_script = skill_dir / script
            assert script in skill_text
            assert ssot_script.exists()
            assert deployed_script.exists()
            assert deployed_script.read_text(encoding="utf-8") == ssot_script.read_text(
                encoding="utf-8"
            )


def _load_script_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module
