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
    ]
    for phrase in required:
        assert phrase in text


def test_portable_skill_toolkit_contains_six_valid_skill_entrypoints() -> None:
    expected = {
        "simple-flow-discussion",
        "simple-flow-documentation-curation",
        "simple-flow-issue-draft",
        "simple-flow-start-implement",
        "simple-flow-review-triage",
        "simple-flow-pr-finalize",
    }

    skills = {path.parent.name: path.read_text(encoding="utf-8") for path in SKILLS_ROOT.glob("*/SKILL.md")}

    assert set(skills) == expected
    for text in skills.values():
        assert text.startswith("---\nname: ")
        assert "description: " in text
        assert ".simple-flow/" not in text
    assert ".simple_tool/" in skills["simple-flow-issue-draft"]
    assert "scripts/create_draft.py" in skills["simple-flow-issue-draft"]
    assert ".simple_tool/" in skills["simple-flow-start-implement"]
    assert "scripts/select_path.py" in skills["simple-flow-start-implement"]


def test_workflow_ownership_keeps_issue_pr_and_merge_actions_separate() -> None:
    issue_draft = (SKILLS_ROOT / "simple-flow-issue-draft" / "SKILL.md").read_text(encoding="utf-8")
    start = (SKILLS_ROOT / "simple-flow-start-implement" / "SKILL.md").read_text(encoding="utf-8")
    finalize = (SKILLS_ROOT / "simple-flow-pr-finalize" / "SKILL.md").read_text(encoding="utf-8")

    assert "Do not create or edit a GitHub Issue" in issue_draft
    assert "Create or reuse the matching GitHub Issue" in start
    assert "Open a pull request against the default branch" in start
    assert "Do not merge" in start
    assert "explicitly approves merging a pull request" in finalize
    assert "Merge with the repository's normal merge method" in finalize
