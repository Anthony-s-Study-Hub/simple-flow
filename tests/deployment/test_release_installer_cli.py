from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "documentation-curation",
    "issue-draft",
    "start-implement",
    "review-triage",
    "pr-finalize",
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


def test_release_cli_default_install_deploys_dual_skill_layout_and_shared_agent_rules(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli("install", str(target), "--json")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "success"
    assert report["agent"] == "both"
    assert (target / ".simple_tool" / "status.json").exists()
    installed_rules = target / "AGENTS.md"
    assert installed_rules.read_text(encoding="utf-8") == (
        ROOT / "simple_flow_deploy" / "assets" / "AGENTS.md"
    ).read_text(encoding="utf-8")
    rules_text = installed_rules.read_text(encoding="utf-8")
    assert "Treat every user message as discussion by default." in rules_text
    assert "Do not ask for confirmation while the plan is incomplete or exploratory." in rules_text
    assert "The original request does not itself authorize the stage." in rules_text
    assert "covers all internal work owned by that stage" in rules_text
    assert "Only Start-Implement may publish or update formal Issues" in rules_text
    assert "Only the owning skill may change transition files under `.simple_tool/`" in rules_text
    for root in (".codex/skills", ".claude/skills"):
        assert {path.parent.name for path in (target / root).glob("*/SKILL.md")} == SKILLS
        for skill in SKILLS:
            policy = (target / root / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
            expected_policy = "false" if skill == "pr-finalize" else "true"
            assert f"allow_implicit_invocation: {expected_policy}" in policy
    assert not (target / ".simple-flow").exists()
    assert not (target / ".github").exists()
    assert not (target / "simple_flow_gates").exists()
    assert not (target / "scripts").exists()


def test_release_cli_can_install_one_agent_protocol(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli("install", str(target), "--agent", "claude", "--json")

    assert completed.returncode == 0, completed.stderr
    assert (target / ".claude" / "skills" / "start-implement" / "SKILL.md").exists()
    assert not (target / ".codex").exists()


def test_release_cli_refuses_conflicting_shared_agent_rules(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    _run_cli("install", str(target), "--json")
    (target / "AGENTS.md").write_text("local rules\n", encoding="utf-8")

    completed = _run_cli("install", str(target), "--json")

    assert completed.returncode != 0
    report = json.loads(completed.stdout)
    assert report["status"] == "conflict"
    assert report["conflicts"] == [
        {"path": "AGENTS.md", "reason": "exists with different content"}
    ]


def test_release_cli_plan_includes_shared_agent_rules_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli("plan", str(target), "--json")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert "AGENTS.md" in report["created"]
    assert not target.exists()


def test_release_cli_version_reports_package_version() -> None:
    completed = _run_cli("--version")

    assert completed.returncode == 0, completed.stderr
    assert _project_version() in completed.stdout


def test_next_public_release_version_is_0_2_8() -> None:
    assert _project_version() == "0.2.8"


def test_built_release_wheel_contains_shared_agent_rules(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    wheel = next(wheel_dir.glob("simple_flow-*.whl"))
    with ZipFile(wheel) as archive:
        assert "simple_flow_deploy/assets/AGENTS.md" in archive.namelist()
        for skill in SKILLS:
            assert f"simple_flow_deploy/assets/skills/simple-flow-{skill}/agents/openai.yaml" in archive.namelist()


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "simple_flow_deploy.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _project_version() -> str:
    return str(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
