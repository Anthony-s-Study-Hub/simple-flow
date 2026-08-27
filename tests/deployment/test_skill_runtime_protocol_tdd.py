from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from simple_flow_deploy.installer import install


ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = {
    "discussion": [],
    "documentation-curation": ["scripts/curate_documentation.py"],
    "issue-draft": ["scripts/create_draft.py"],
    "start-implement": [
        "scripts/plan_implementation.py",
        "scripts/select_path.py",
        "scripts/start_documentation.py",
    ],
    "review-triage": ["scripts/classify_finding.py"],
    "pr-finalize": ["scripts/check_pre_merge.py"],
}


def test_install_restores_short_skill_names_scripts_and_shared_runtime(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    report = install(source_root=ROOT, target=target)

    assert report.status == "success"
    assert (target / ".simple_tool" / "status.json").exists()
    assert (target / ".simple_tool" / "drafts").is_dir()
    assert (target / ".simple_tool" / "runtime" / "simple_flow_agent").is_dir()
    for root in (".codex/skills", ".claude/skills"):
        for skill, scripts in SKILL_SCRIPTS.items():
            skill_dir = target / root / skill
            assert (skill_dir / "SKILL.md").exists()
            assert f"name: {skill}" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            for script in scripts:
                script_path = skill_dir / script
                assert script_path.exists()
                completed = subprocess.run(
                    [sys.executable, str(script_path), "--help"],
                    cwd=target,
                    capture_output=True,
                    text=True,
                )
                assert completed.returncode == 0, completed.stderr
