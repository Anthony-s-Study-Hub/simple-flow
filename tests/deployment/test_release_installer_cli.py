from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[2]
RELEASE_SOURCE = "git+https://github.com/Anthony-s-Study-Hub/simple-flow.git@v9.9.9"


def test_release_cli_doctor_is_read_only_and_reports_prechecks(tmp_path: Path) -> None:
    target = tmp_path / "target-project"
    target.mkdir()

    completed = _run_cli(
        "doctor",
        str(target),
        "--release-source",
        RELEASE_SOURCE,
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] in {"ok", "warning"}
    check_names = {check["name"] for check in report["checks"]}
    assert {
        "python-version",
        "git-command",
        "target-writable",
        "packaged-assets",
        "install-conflicts",
    }.issubset(check_names)
    assert not (target / ".simple-flow").exists()


def test_release_cli_default_install_uses_thin_packaged_layout(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli(
        "install",
        str(target),
        "--project-name",
        "release-cli-target",
        "--release-source",
        RELEASE_SOURCE,
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "success"
    assert report["mode"] == "thin"

    manifest = json.loads(
        (target / ".simple-flow" / "install-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["package"]["name"] == "simple-flow"
    assert manifest["package"]["version"] == _project_version()
    assert manifest["install_mode"] == "thin"
    assert manifest["release_source"] == RELEASE_SOURCE
    assert "AGENTS.md" in manifest["files"]

    assert (target / ".codex" / "skills" / "start-implement" / "SKILL.md").exists()
    assert (target / ".github" / "workflows" / "pr-governance.yml").exists()
    assert (target / "docs" / "simple-flow" / "usage-guide.md").exists()
    assert not (target / "simple_flow_gates").exists()
    assert not (target / "simple_flow_agent").exists()
    assert not (target / "simple_flow_documentation_curation").exists()
    assert not (target / "tests").exists()

    pr_governance = (target / ".github" / "workflows" / "pr-governance.yml").read_text(
        encoding="utf-8"
    )
    assert RELEASE_SOURCE in pr_governance
    assert 'python -m pip install -e ".[test]"' not in pr_governance


def test_release_cli_vendored_mode_preserves_self_contained_layout(tmp_path: Path) -> None:
    target = tmp_path / "target-project"

    completed = _run_cli(
        "install",
        str(target),
        "--mode",
        "vendored",
        "--project-name",
        "vendored-target",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "success"
    assert report["mode"] == "vendored"
    assert (target / "simple_flow_gates" / "cli.py").exists()
    assert (target / "simple_flow_agent" / "drafts.py").exists()
    assert (target / "tests" / "test_cli.py").exists()


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
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])
