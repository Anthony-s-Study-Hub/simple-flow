from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_phase4_validate_command_is_static() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_phase4.cli",
            "validate",
            "--source-root",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Phase 4 scenario catalog valid: 25 scenarios" in completed.stdout


def test_phase4_dry_run_generates_machine_and_human_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "simple_flow_phase4.cli",
            "run",
            "--scenario",
            "A01",
            "--dry-run",
            "--source-root",
            str(ROOT),
            "--workspace-root",
            str(workspace),
            "--report-dir",
            str(report_dir),
            "--codex-command",
            "missing-codex-command-for-static-test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    assert latest_json.exists()
    assert latest_md.exists()

    data = json.loads(latest_json.read_text(encoding="utf-8"))
    assert data["overall_status"] == "NOT_RUN"
    assert data["status_counts"]["NOT_RUN"] == 1
    assert data["scenarios"][0]["scenario_id"] == "A01"
    assert data["scenarios"][0]["codex_cli_version"] == "not run in dry-run mode"
    assert "Harness Commit SHA" in latest_md.read_text(encoding="utf-8")


def test_source_ci_does_not_run_live_phase4_experiment() -> None:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )

    assert "phase4-run run" not in workflow_text
    assert "codex exec" not in workflow_text
