from __future__ import annotations

from pathlib import Path

from simple_flow_deploy.installer import install


ROOT = Path(__file__).resolve().parents[2]


def test_public_release_install_writes_only_codex_and_claude_skill_protocols(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target-project"

    report = install(source_root=ROOT, target=target)

    assert report.status == "success"
    assert {path.name for path in target.iterdir()} == {".codex", ".claude"}
    assert len(list(target.glob(".codex/skills/*/SKILL.md"))) == 6
    assert len(list(target.glob(".claude/skills/*/SKILL.md"))) == 6
