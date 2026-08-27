from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SKILL_MAP = {
    "simple-flow-discussion": "discussion",
    "simple-flow-documentation-curation": "documentation-curation",
    "simple-flow-issue-draft": "issue-draft",
    "simple-flow-start-implement": "start-implement",
    "simple-flow-review-triage": "review-triage",
    "simple-flow-pr-finalize": "pr-finalize",
}


def test_public_release_cli_contract_deploys_only_standard_codex_and_claude_skills(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    report = _install(target)

    assert report["status"] == "success"
    assert report["agent"] == "both"
    assert (target / ".simple_tool" / "status.json").exists()
    for root in (".codex/skills", ".claude/skills"):
        deployed = {path.parent.name for path in (target / root).glob("*/SKILL.md")}
        assert deployed == set(SKILL_MAP.values())
        for source_skill, skill in SKILL_MAP.items():
            installed = target / root / skill / "SKILL.md"
            source = ROOT / "simple_flow_deploy" / "assets" / "skills" / source_skill / "SKILL.md"
            assert installed.read_text(encoding="utf-8") == source.read_text(encoding="utf-8").replace(
                f"name: {source_skill}", f"name: {skill}"
            )

    assert {path.name for path in target.iterdir()} == {".codex", ".claude", ".simple_tool"}


def test_public_release_cli_contract_is_idempotent_and_refuses_conflicting_skill(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _install(target)

    repeated = _install(target)
    assert repeated["status"] == "success"
    assert repeated["created"] == []
    assert repeated["skipped"]

    skill = target / ".codex" / "skills" / "discussion" / "SKILL.md"
    skill.write_text("local skill override\n", encoding="utf-8")
    conflict = _install(target, check=False)
    assert conflict["status"] == "conflict"
    assert conflict["conflicts"] == [
        {"path": ".codex/skills/discussion/SKILL.md", "reason": "exists with different content"}
    ]


def test_start_implement_uses_a_file_backed_draft_and_the_issue_pr_main_route() -> None:
    text = (ROOT / "simple_flow_deploy" / "assets" / "skills" / "simple-flow-start-implement" / "SKILL.md").read_text(encoding="utf-8")

    assert ".simple_tool/drafts/" in text
    assert "scripts/plan_implementation.py" in text
    assert "Create or reuse the matching GitHub Issue" in text
    assert "Open a pull request against the default branch" in text
    assert "Closes #<issue-number>" in text
    assert "Do not merge" in text


def test_release_command_uses_the_tagged_public_repository() -> None:
    from simple_flow_deploy.cli import current_install_command

    command = current_install_command()
    assert "git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v" in command
    assert command.endswith("simple-flow install .")


def _install(target: Path, *, check: bool = True) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "simple_flow_deploy.cli", "install", str(target), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check:
        assert completed.returncode == 0, completed.stderr
    else:
        assert completed.returncode != 0
    return json.loads(completed.stdout)
