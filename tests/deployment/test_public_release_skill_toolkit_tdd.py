from __future__ import annotations

from pathlib import Path

from simple_flow_deploy.installer import install


ROOT = Path(__file__).resolve().parents[2]


def test_public_release_install_writes_skill_protocols_and_shared_agent_rules(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target-project"

    report = install(source_root=ROOT, target=target)

    assert report.status == "success"
    assert {path.name for path in target.iterdir()} == {".codex", ".claude", ".simple_tool", "AGENTS.md"}
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == (
        ROOT / "simple_flow_deploy" / "assets" / "AGENTS.md"
    ).read_text(encoding="utf-8")
    assert len(list(target.glob(".codex/skills/*/SKILL.md"))) == 5
    assert len(list(target.glob(".claude/skills/*/SKILL.md"))) == 5
