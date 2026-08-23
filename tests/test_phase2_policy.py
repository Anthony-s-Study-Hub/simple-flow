from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "simple_flow_deploy" / "assets" / "skills"


def test_agents_md_contains_global_default_deny_rules() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    required = [
        "Default Deny",
        "current skill has not explicitly authorized",
        "must stop after completing its owned stage",
        "must not call or simulate the next stage",
        "Only Issue-Draft may generate a Canonical Draft",
        "Only Start-Implement may publish or update formal Issues",
        "Only PR-Finalize may merge",
        "Review-Triage must not modify issues or code",
        "Discussion must not generate formal drafts",
        "Start-Implement must not merge pull requests",
        "must not bypass Issue, Branch, Pull Request, or CI",
        "must go through Review-Triage before fixes",
    ]
    for phrase in required:
        assert phrase in text


def test_all_five_phase2_skills_exist_with_unique_ownership_markers() -> None:
    expected = {
        "simple-flow-discussion": "Owned Stage: Discussion",
        "simple-flow-issue-draft": "Owned Stage: Issue-Draft",
        "simple-flow-start-implement": "Owned Stage: Start-Implement",
        "simple-flow-review-triage": "Owned Stage: Review-Triage",
        "simple-flow-pr-finalize": "Owned Stage: PR-Finalize",
    }

    for folder, marker in expected.items():
        skill = SKILLS_ROOT / folder / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\nname: ")
        assert "description: " in text
        assert marker in text
        assert "STOP" in text


def test_phase2_skills_define_required_deployed_script_entrypoints() -> None:
    expected_scripts = {
        "simple-flow-discussion": [],
        "simple-flow-issue-draft": ["scripts/create_draft.py"],
        "simple-flow-start-implement": ["scripts/select_path.py"],
        "simple-flow-review-triage": ["scripts/classify_finding.py"],
        "simple-flow-pr-finalize": ["scripts/check_pre_merge.py"],
    }

    for folder, scripts in expected_scripts.items():
        skill_dir = SKILLS_ROOT / folder
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert not (skill_dir / "scripts").exists()
        for script in scripts:
            assert script in text

    discussion = (SKILLS_ROOT / "simple-flow-discussion" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "no deterministic script" in discussion


def test_skill_exclusive_permissions_have_no_merge_or_draft_overlap() -> None:
    skills = {
        path.parent.name: path.read_text(encoding="utf-8")
        for path in SKILLS_ROOT.glob("*/SKILL.md")
    }

    draft_owners = [
        name for name, text in skills.items() if "Permission: generate-canonical-draft" in text
    ]
    issue_owners = [
        name for name, text in skills.items() if "Permission: publish-formal-issue" in text
    ]
    merge_owners = [
        name for name, text in skills.items() if "Permission: merge-pull-request" in text
    ]

    assert draft_owners == ["simple-flow-issue-draft"]
    assert issue_owners == ["simple-flow-start-implement"]
    assert merge_owners == ["simple-flow-pr-finalize"]

