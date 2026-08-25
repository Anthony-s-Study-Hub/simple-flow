from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "simple-flow-discussion",
    "simple-flow-documentation-curation",
    "simple-flow-issue-draft",
    "simple-flow-start-implement",
    "simple-flow-review-triage",
    "simple-flow-pr-finalize",
}


def test_release_cli_doctor_is_read_only_and_checks_skill_assets(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    target.mkdir()

    completed = _run_cli("doctor", str(target), "--json")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "ok"
    assert report["agent"] == "both"
    assert {check["name"] for check in report["checks"]} == {
        "python-version",
        "target-writable",
        "packaged-assets",
        "install-conflicts",
    }
    assert list(target.iterdir()) == []


def test_release_cli_default_install_uses_dual_skill_layout_only(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli("install", str(target), "--json")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "success"
    assert report["agent"] == "both"
    assert len(report["created"]) == 12
    for root in (".codex/skills", ".claude/skills"):
        assert {path.parent.name for path in (target / root).glob("*/SKILL.md")} == SKILLS
    assert not (target / ".simple-flow").exists()
    assert not (target / ".github").exists()
    assert not (target / "AGENTS.md").exists()
    assert not (target / "simple_flow_gates").exists()
    assert not (target / "scripts").exists()


def test_release_cli_can_install_one_agent_protocol(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli("install", str(target), "--agent", "claude", "--json")

    assert completed.returncode == 0, completed.stderr
    assert (target / ".claude" / "skills" / "simple-flow-start-implement" / "SKILL.md").exists()
    assert not (target / ".codex").exists()


def test_release_cli_version_reports_package_version() -> None:
    completed = _run_cli("--version")

    assert completed.returncode == 0, completed.stderr
    assert _project_version() in completed.stdout


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "simple_flow_deploy.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _project_version() -> str:
    return str(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
