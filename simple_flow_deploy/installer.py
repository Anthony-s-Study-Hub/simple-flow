from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from importlib import resources
from importlib.metadata import PackageNotFoundError, version as distribution_version
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib


SKILL_MAP = {
    "simple-flow-discussion": "discussion",
    "simple-flow-documentation-curation": "documentation-curation",
    "simple-flow-issue-draft": "issue-draft",
    "simple-flow-start-implement": "start-implement",
    "simple-flow-review-triage": "review-triage",
    "simple-flow-pr-finalize": "pr-finalize",
}

THIN_CORE_FILES = [
    "AGENTS.md",
    ".github/ISSUE_TEMPLATE/feature.md",
    ".github/ISSUE_TEMPLATE/documentation.md",
    ".github/pull_request_template.md",
    ".github/workflows/issue-governance.yml",
    ".github/workflows/pr-governance.yml",
    ".github/workflows/phase1-tests.yml",
    ".github/workflows/orphan-branch-watch.yml",
    ".simple-flow/roadmap-targets.txt",
    "scripts/__init__.py",
    "scripts/configure_repository.ps1",
    "scripts/orphan_branch_watch.py",
]

DOC_FILES = {
    "docs/deployment/usage-guide.md": "docs/simple-flow/usage-guide.md",
    "docs/deployment/project-integration-guide.md": "docs/simple-flow/project-integration-guide.md",
    "docs/deployment/github-setup-guide.md": "docs/simple-flow/github-setup-guide.md",
}

PACKAGE_NAME = "simple-flow"
DEFAULT_RELEASE_REPOSITORY = "https://github.com/Anthony-s-Study-Hub/simple-flow.git"
INSTALL_MODES = {"thin"}


@dataclass
class InstallReport:
    status: str = "success"
    mode: str = "thin"
    release_source: str | None = None
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
                "mode": self.mode,
                "release_source": self.release_source,
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
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class PrecheckReport:
    status: str
    target: str
    mode: str
    package_version: str
    release_source: str | None
    checks: list[Precheck]

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "target": self.target,
                "mode": self.mode,
                "package_version": self.package_version,
                "release_source": self.release_source,
                "checks": [check.to_json_data() for check in self.checks],
            },
            indent=2,
        )


def install(
    *,
    source_root: str | Path,
    target: str | Path,
    project_name: str = "new-project",
    test_command: str = "python -m pytest",
    scope: list[str] | None = None,
    documentation: list[str] | None = None,
    clean_target: bool = False,
    mode: str = "thin",
    release_source: str | None = None,
    dry_run: bool = False,
) -> InstallReport:
    source = Path(source_root).resolve()
    destination = Path(target).resolve()
    _validate_mode(mode)
    version = package_version(source)
    resolved_release_source = default_release_source(version)
    _require_public_release_source(release_source, resolved_release_source)
    report = InstallReport(
        target=str(destination),
        mode=mode,
        release_source=resolved_release_source if mode == "thin" else None,
    )

    if clean_target:
        _clean_target(destination)

    desired = _desired_files(
        project_name=project_name,
        test_command=test_command,
        scope=scope or ["src/"],
        documentation=documentation or ["docs/"],
        package_version=version,
        release_source=resolved_release_source,
    )

    conflicts = _find_conflicts(destination, desired)
    if conflicts:
        report.status = "conflict"
        report.conflicts = conflicts
        return report

    if dry_run:
        report.created = _pending_creates(destination, desired)
        report.skipped = _matching_existing(destination, desired)
        return report

    destination.mkdir(parents=True, exist_ok=True)
    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") == content:
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
    project_name: str = "new-project",
    test_command: str = "python -m pytest",
    scope: list[str] | None = None,
    documentation: list[str] | None = None,
    mode: str = "thin",
    release_source: str | None = None,
) -> PrecheckReport:
    source = Path(source_root).resolve()
    destination = Path(target).resolve()
    _validate_mode(mode)
    version = package_version(source)
    resolved_release_source = default_release_source(version)
    _require_public_release_source(release_source, resolved_release_source)
    checks = [
        _check_python_version(),
        _check_command("git-command", "git"),
        _check_target_writable(destination),
        _check_packaged_assets(),
        _check_release_source(resolved_release_source),
    ]

    try:
        desired = _desired_files(
            project_name=project_name,
            test_command=test_command,
            scope=scope or ["src/"],
            documentation=documentation or ["docs/"],
            package_version=version,
            release_source=resolved_release_source,
        )
        conflicts = _find_conflicts(destination, desired)
        checks.append(
            Precheck(
                name="install-conflicts",
                status="fail" if conflicts else "ok",
                message=(
                    "Conflicting existing files: "
                    + ", ".join(item["path"] for item in conflicts)
                    if conflicts
                    else "No conflicting managed files detected."
                ),
            )
        )
    except Exception as exc:
        checks.append(
            Precheck(
                name="install-conflicts",
                status="fail",
                message=f"Unable to compute install plan: {exc}",
            )
        )

    if any(check.status == "fail" for check in checks):
        status = "blocked"
    elif any(check.status == "warn" for check in checks):
        status = "warning"
    else:
        status = "ok"

    return PrecheckReport(
        status=status,
        target=str(destination),
        mode=mode,
        package_version=version,
        release_source=resolved_release_source if mode == "thin" else None,
        checks=checks,
    )


def package_version(source_root: str | Path | None = None) -> str:
    root = Path(source_root).resolve() if source_root else Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return str(data["project"]["version"])
    try:
        return distribution_version(PACKAGE_NAME)
    except PackageNotFoundError:
        pass
    return "0.0.0"


def default_release_source(version: str) -> str:
    return f"git+{DEFAULT_RELEASE_REPOSITORY}@v{version}"


def _require_public_release_source(
    requested: str | None,
    expected: str,
) -> None:
    if requested is not None and requested != expected:
        raise ValueError(
            "Deployment source is fixed to the versioned public Simple Flow repository: "
            + expected
        )


def _desired_files(
    *,
    project_name: str,
    test_command: str,
    scope: list[str],
    documentation: list[str],
    package_version: str,
    release_source: str,
) -> dict[str, str]:
    files: dict[str, str] = {}
    for relative in THIN_CORE_FILES:
        text = _asset_text(relative)
        if relative.startswith(".github/workflows/"):
            text = _release_workflow(text, release_source)
        if relative == ".github/workflows/phase1-tests.yml":
            text = _replace_current_head_test_command(text, test_command)
        files[relative] = text

    for source_skill, target_skill in SKILL_MAP.items():
        skill_text = _canonical_skill_text(source_skill)
        files[f".codex/skills/{target_skill}/SKILL.md"] = skill_text.replace(
            f"name: {source_skill}",
            f"name: {target_skill}",
        )

        resource_root = _package_root() / "skill_resources" / target_skill
        for resource_relative, text in _resource_text_files(resource_root).items():
            files[f".codex/skills/{target_skill}/{resource_relative}"] = text

    for source_doc, target_doc in DOC_FILES.items():
        files[target_doc] = _asset_text(source_doc)

    baseline_root = _package_root() / "baseline_templates"
    files[".simple-flow/baselines/high-level-project-baseline.md"] = (
        baseline_root / "high-level-project-baseline.md"
    ).read_text(encoding="utf-8")
    files[".simple-flow/baselines/component-baseline-template.md"] = (
        baseline_root / "component-baseline-template.md"
    ).read_text(encoding="utf-8")

    _add_project_metadata(
        files,
        project_name=project_name,
        test_command=test_command,
        scope=scope,
        documentation=documentation,
        mode="thin",
        package_version=package_version,
        release_source=release_source,
    )
    return files


def _add_project_metadata(
    files: dict[str, str],
    *,
    project_name: str,
    test_command: str,
    scope: list[str],
    documentation: list[str],
    mode: str,
    package_version: str,
    release_source: str | None,
) -> None:
    files[".simple-flow/project-config.json"] = (
        json.dumps(
            {
                "project_name": project_name,
                "test_command": test_command,
                "scope": scope,
                "documentation": documentation,
                "install_mode": mode,
                "release_source": release_source,
                "roadmap_target_source": "GitHub Projects or .simple-flow/roadmap-targets.txt",
            },
            indent=2,
        )
        + "\n"
    )
    files[".simple-flow/README.md"] = _project_readme(project_name, mode=mode)
    files[".simple-flow/install-manifest.json"] = _install_manifest(
        project_name=project_name,
        mode=mode,
        package_version=package_version,
        release_source=release_source,
        files=files,
    )


def _release_workflow(text: str, release_source: str) -> str:
    install_command = f'python -m pip install "{_package_spec(release_source)}"'
    transformed = text.replace('python -m pip install -e ".[test]"', install_command)
    transformed = transformed.replace("python -m pip install pytest", install_command)
    if "Detect local orphan development branches" in transformed and install_command not in transformed:
        transformed = transformed.replace(
            "      - name: Detect local orphan development branches\n",
            "      - name: Install Simple Flow package\n"
            f"        run: {install_command}\n"
            "      - name: Detect local orphan development branches\n",
        )
    return transformed


def _replace_current_head_test_command(text: str, test_command: str) -> str:
    return text.replace("        run: python -m pytest\n", f"        run: {test_command}\n")


def _package_spec(release_source: str) -> str:
    if " @ " in release_source or release_source.startswith(f"{PACKAGE_NAME}["):
        return release_source
    return f"{PACKAGE_NAME}[test] @ {release_source}"


def _find_conflicts(destination: Path, desired: dict[str, str]) -> list[dict[str, str]]:
    conflicts = []
    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") != content:
            conflicts.append(
                {
                    "path": relative,
                    "reason": "exists with different content",
                }
            )
    return conflicts


def _pending_creates(destination: Path, desired: dict[str, str]) -> list[str]:
    pending = []
    for relative, content in desired.items():
        output = destination / relative
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            pending.append(relative)
    return pending


def _matching_existing(destination: Path, desired: dict[str, str]) -> list[str]:
    matching = []
    for relative, content in desired.items():
        output = destination / relative
        if output.exists() and output.read_text(encoding="utf-8") == content:
            matching.append(relative)
    return matching


def _clean_target(destination: Path) -> None:
    if not destination.exists():
        return
    manifest = destination / ".simple-flow" / "project-config.json"
    if destination.name != "Phase3_Target_Project" and not manifest.exists():
        raise ValueError(f"Refusing to clean unmanaged target: {destination}")
    shutil.rmtree(destination)


def _project_readme(project_name: str, *, mode: str) -> str:
    return (
        f"# {project_name} Simple Flow Setup\n\n"
        "This directory contains the installed Simple Flow controlled development workflow.\n"
        f"Install mode: `{mode}`.\n"
        "Project-specific settings live in `.simple-flow/project-config.json`.\n"
    )


def _install_manifest(
    *,
    project_name: str,
    mode: str,
    package_version: str,
    release_source: str | None,
    files: dict[str, str],
) -> str:
    manifest = {
        "schema": "simple-flow-install-manifest.v1",
        "package": {
            "name": PACKAGE_NAME,
            "version": package_version,
        },
        "project_name": project_name,
        "install_mode": mode,
        "release_source": release_source,
        "files": {
            relative: _sha256(content)
            for relative, content in sorted(files.items())
            if relative != ".simple-flow/install-manifest.json"
        },
    }
    return json.dumps(manifest, indent=2) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _asset_text(relative: str) -> str:
    return (_package_root() / "assets" / relative).read_text(encoding="utf-8")


def _canonical_skill_text(source_skill: str) -> str:
    """Return the one packaged source used by every deployment mode."""
    return _asset_text(f"skills/{source_skill}/SKILL.md")


def _package_root():
    return resources.files("simple_flow_deploy")


def _resource_text_files(root, prefix: str = "") -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.is_dir():
        return files
    for child in root.iterdir():
        child_relative = f"{prefix}{child.name}"
        if child.is_dir():
            files.update(_resource_text_files(child, f"{child_relative}/"))
        elif child.is_file() and "__pycache__" not in child_relative and not child.name.endswith(".pyc"):
            files[child_relative] = child.read_text(encoding="utf-8")
    return files


def _validate_mode(mode: str) -> None:
    if mode not in INSTALL_MODES:
        raise ValueError(f"Unsupported install mode: {mode}")


def _check_python_version() -> Precheck:
    if sys.version_info >= (3, 11):
        return Precheck(
            name="python-version",
            status="ok",
            message=f"Python {sys.version.split()[0]} satisfies >= 3.11.",
        )
    return Precheck(
        name="python-version",
        status="fail",
        message=f"Python {sys.version.split()[0]} is below the required 3.11.",
    )


def _check_command(name: str, command: str) -> Precheck:
    path = shutil.which(command)
    if path:
        return Precheck(name=name, status="ok", message=f"Found `{command}` at {path}.")
    return Precheck(name=name, status="fail", message=f"`{command}` is not on PATH.")


def _check_target_writable(destination: Path) -> Precheck:
    probe = destination if destination.exists() else destination.parent
    if probe.exists() and os.access(probe, os.W_OK):
        return Precheck(
            name="target-writable",
            status="ok",
            message=f"Target location is writable: {destination}",
        )
    return Precheck(
        name="target-writable",
        status="fail",
        message=f"Target location is not writable or parent is missing: {destination}",
    )


def _check_packaged_assets() -> Precheck:
    try:
        required = [
            "AGENTS.md",
            ".github/workflows/pr-governance.yml",
            "skills/simple-flow-start-implement/SKILL.md",
            "docs/deployment/usage-guide.md",
        ]
        missing = [
            relative
            for relative in required
            if not (_package_root() / "assets" / relative).is_file()
        ]
    except Exception as exc:
        return Precheck(
            name="packaged-assets",
            status="fail",
            message=f"Unable to inspect deployment assets: {exc}",
        )

    if missing:
        return Precheck(
            name="packaged-assets",
            status="fail",
            message="Missing deployment assets: " + ", ".join(missing),
        )
    return Precheck(
        name="packaged-assets",
        status="ok",
        message="Deployment assets are available from the public package SSOT.",
    )


def _check_release_source(release_source: str) -> Precheck:
    if release_source.strip():
        return Precheck(
            name="release-source",
            status="ok",
            message=f"Release package source is configured: {release_source}",
        )
    return Precheck(
        name="release-source",
        status="fail",
        message="Thin mode requires a release package source.",
    )
