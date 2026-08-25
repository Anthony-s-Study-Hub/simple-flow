from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from importlib.metadata import PackageNotFoundError, version as distribution_version
import json
import os
from pathlib import Path
import sys
import tomllib


SKILLS = (
    "simple-flow-discussion",
    "simple-flow-documentation-curation",
    "simple-flow-issue-draft",
    "simple-flow-start-implement",
    "simple-flow-review-triage",
    "simple-flow-pr-finalize",
)
AGENT_ROOTS = {"codex": ".codex/skills", "claude": ".claude/skills"}
INSTALL_TARGETS = {"both", *AGENT_ROOTS}
PACKAGE_NAME = "simple-flow"


@dataclass
class InstallReport:
    status: str = "success"
    agent: str = "both"
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    target: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "target": self.target,
                "agent": self.agent,
                "created": self.created,
                "skipped": self.skipped,
                "conflicts": self.conflicts,
                "failures": self.failures,
            },
            indent=2,
        )


@dataclass(frozen=True)
class Precheck:
    name: str
    status: str
    message: str

    def to_json_data(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "message": self.message}


@dataclass
class PrecheckReport:
    status: str
    target: str
    agent: str
    package_version: str
    checks: list[Precheck]

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "target": self.target,
                "agent": self.agent,
                "package_version": self.package_version,
                "checks": [check.to_json_data() for check in self.checks],
            },
            indent=2,
        )


def install(
    *,
    source_root: str | Path,
    target: str | Path,
    agent: str = "both",
    dry_run: bool = False,
) -> InstallReport:
    del source_root  # Deployment intentionally uses only packaged skill assets.
    destination = Path(target).resolve()
    _validate_agent(agent)
    desired = _desired_files(agent)
    report = InstallReport(target=str(destination), agent=agent)

    conflicts = _find_conflicts(destination, desired)
    if conflicts:
        report.status = "conflict"
        report.conflicts = conflicts
        return report
    if dry_run:
        report.created = _pending_creates(destination, desired)
        report.skipped = _matching_existing(destination, desired)
        return report

    for relative, content in desired.items():
        output = destination / relative
        if output.exists():
            report.skipped.append(relative)
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        report.created.append(relative)
    return report


def doctor(
    *,
    source_root: str | Path,
    target: str | Path,
    agent: str = "both",
) -> PrecheckReport:
    del source_root
    destination = Path(target).resolve()
    _validate_agent(agent)
    checks = [_check_python_version(), _check_target_writable(destination), _check_packaged_assets()]
    conflicts = _find_conflicts(destination, _desired_files(agent))
    checks.append(
        Precheck(
            name="install-conflicts",
            status="fail" if conflicts else "ok",
            message=(
                "Conflicting skill files: " + ", ".join(item["path"] for item in conflicts)
                if conflicts
                else "No conflicting skill files detected."
            ),
        )
    )
    status = "blocked" if any(check.status == "fail" for check in checks) else "ok"
    return PrecheckReport(status, str(destination), agent, package_version(), checks)


def package_version(source_root: str | Path | None = None) -> str:
    root = Path(source_root).resolve() if source_root else Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        return str(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"])
    try:
        return distribution_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def _desired_files(agent: str) -> dict[str, str]:
    files: dict[str, str] = {}
    selected_agents = AGENT_ROOTS if agent == "both" else {agent: AGENT_ROOTS[agent]}
    for root in selected_agents.values():
        for skill in SKILLS:
            files[f"{root}/{skill}/SKILL.md"] = _asset_text(f"skills/{skill}/SKILL.md")
    return files


def _asset_text(relative: str) -> str:
    return (_package_root() / "assets" / relative).read_text(encoding="utf-8")


def _package_root():
    return resources.files("simple_flow_deploy")


def _find_conflicts(destination: Path, desired: dict[str, str]) -> list[dict[str, str]]:
    conflicts = []
    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") != content:
            conflicts.append({"path": relative, "reason": "exists with different content"})
    return conflicts


def _pending_creates(destination: Path, desired: dict[str, str]) -> list[str]:
    return [
        relative
        for relative, content in desired.items()
        if not (destination / relative).exists()
        or (destination / relative).read_text(encoding="utf-8") != content
    ]


def _matching_existing(destination: Path, desired: dict[str, str]) -> list[str]:
    return [
        relative
        for relative, content in desired.items()
        if (destination / relative).exists()
        and (destination / relative).read_text(encoding="utf-8") == content
    ]


def _validate_agent(agent: str) -> None:
    if agent not in INSTALL_TARGETS:
        raise ValueError(f"Unsupported agent target: {agent}")


def _check_python_version() -> Precheck:
    if sys.version_info >= (3, 11):
        return Precheck("python-version", "ok", f"Python {sys.version.split()[0]} satisfies >= 3.11.")
    return Precheck("python-version", "fail", f"Python {sys.version.split()[0]} is below the required 3.11.")


def _check_target_writable(destination: Path) -> Precheck:
    probe = destination if destination.exists() else destination.parent
    if probe.exists() and os.access(probe, os.W_OK):
        return Precheck("target-writable", "ok", f"Target location is writable: {destination}")
    return Precheck("target-writable", "fail", f"Target location is not writable or parent is missing: {destination}")


def _check_packaged_assets() -> Precheck:
    missing = [
        f"skills/{skill}/SKILL.md"
        for skill in SKILLS
        if not (_package_root() / "assets" / "skills" / skill / "SKILL.md").is_file()
    ]
    if missing:
        return Precheck("packaged-assets", "fail", "Missing skill assets: " + ", ".join(missing))
    return Precheck("packaged-assets", "ok", "All packaged skill assets are available.")
