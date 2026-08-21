from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Callable
from urllib.parse import urlparse

from simple_flow_deploy.installer import install
from simple_flow_test_harness.commands import CommandFailure, run_command
from simple_flow_test_harness.models import CommandResult, Phase4Config


DEFAULT_TEST_REPO_URL = "https://github.com/Anthony-s-Study-Hub/simple-flow-test.git"
WINDOWS_GH_PATH = r"C:\Program Files\GitHub CLI\gh.exe"


@dataclass(frozen=True)
class PreparedProject:
    path: Path
    repo_full_name: str
    setup_commands: list[CommandResult]


def default_gh_path() -> str:
    candidate = Path(WINDOWS_GH_PATH)
    if candidate.exists():
        return str(candidate)
    return "gh"


def default_codex_command() -> str:
    for command in ("codex.cmd", "codex.exe", "codex"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return "codex"


def repo_full_name(repo_url: str) -> str:
    if repo_url.startswith("git@github.com:"):
        value = repo_url.removeprefix("git@github.com:")
        return value.removesuffix(".git")
    parsed = urlparse(repo_url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"Only GitHub test repositories are supported: {repo_url}")
    path = parsed.path.strip("/").removesuffix(".git")
    if not re.fullmatch(r"[^/]+/[^/]+", path):
        raise ValueError(f"Cannot determine GitHub owner/repo from: {repo_url}")
    return path


class Phase4Environment:
    def __init__(self, config: Phase4Config):
        self.config = config
        self.repo = repo_full_name(config.test_repo_url)

    def prerequisite_evidence(self) -> tuple[list[str], dict[str, object]]:
        blockers: list[str] = []
        evidence: dict[str, object] = {}

        for name, command in {
            "git": ["git", "--version"],
            "gh": [self.config.gh_path, "--version"],
            "codex": [self.config.codex_command, "--version"],
        }.items():
            try:
                result = run_command(command, cwd=self.config.source_root, timeout_seconds=30)
            except (OSError, TimeoutError) as exc:
                blockers.append(f"{name} command unavailable: {exc}")
                continue
            evidence[f"{name}_version_command"] = result.to_json_data()
            if result.exit_code != 0:
                blockers.append(f"{name} command failed: {result.stderr or result.stdout}")

        try:
            auth = run_command(
                [self.config.gh_path, "auth", "status"],
                cwd=self.config.source_root,
                timeout_seconds=30,
            )
            evidence["gh_auth_status"] = auth.to_json_data()
            if auth.exit_code != 0:
                blockers.append("GitHub CLI is not authenticated.")
        except (OSError, TimeoutError) as exc:
            blockers.append(f"Cannot inspect GitHub auth status: {exc}")

        repo_result = run_command(
            [
                self.config.gh_path,
                "repo",
                "view",
                self.repo,
                "--json",
                "name,owner,defaultBranchRef,url",
            ],
            cwd=self.config.source_root,
            timeout_seconds=30,
        )
        evidence["test_repo_view"] = repo_result.to_json_data()
        if repo_result.exit_code != 0:
            blockers.append(f"Cannot view GitHub test repo {self.repo}.")

        return blockers, evidence

    def prepare_scenario_project(self, scenario_id: str) -> PreparedProject:
        scenario_workspace = self.config.workspace_root / scenario_id
        self._safe_reset_local_workspace(scenario_workspace)
        scenario_workspace.parent.mkdir(parents=True, exist_ok=True)

        setup_commands: list[CommandResult] = []
        setup_commands.append(
            run_command(
                ["git", "clone", self.config.test_repo_url, str(scenario_workspace)],
                cwd=self.config.workspace_root.parent,
                timeout_seconds=120,
            )
        )
        if not (scenario_workspace / ".git").exists():
            scenario_workspace.mkdir(parents=True, exist_ok=True)
            setup_commands.append(
                run_command(["git", "init"], cwd=scenario_workspace, timeout_seconds=30, check=True)
            )
            setup_commands.append(
                run_command(
                    ["git", "remote", "add", "origin", self.config.test_repo_url],
                    cwd=scenario_workspace,
                    timeout_seconds=30,
                    check=True,
                )
            )

        self._clean_remote_state(scenario_workspace, setup_commands)
        self._clear_worktree_contents(scenario_workspace)
        self._write_baseline_project(scenario_workspace)
        install_report = install(
            source_root=self.config.source_root,
            target=scenario_workspace,
            project_name="phase4-test-project",
            test_command="python -m pytest",
            scope=["src/", "tests/"],
            documentation=["docs/"],
        )
        if install_report.status != "success":
            raise RuntimeError(f"Unable to deploy Simple Flow into Phase 4 test project: {install_report.to_json()}")

        setup_commands.extend(
            [
                run_command(
                    ["git", "config", "user.name", "Simple Flow Phase 4 Harness"],
                    cwd=scenario_workspace,
                    timeout_seconds=30,
                    check=True,
                ),
                run_command(
                    ["git", "config", "user.email", "phase4-harness@example.invalid"],
                    cwd=scenario_workspace,
                    timeout_seconds=30,
                    check=True,
                ),
                run_command(["git", "checkout", "-B", "main"], cwd=scenario_workspace, timeout_seconds=30, check=True),
                run_command(["git", "add", "--all"], cwd=scenario_workspace, timeout_seconds=30, check=True),
            ]
        )

        status = run_command(["git", "status", "--porcelain"], cwd=scenario_workspace, timeout_seconds=30, check=True)
        setup_commands.append(status)
        if status.stdout.strip():
            setup_commands.append(
                run_command(
                    ["git", "commit", "-m", f"Reset Phase 4 baseline for {scenario_id}"],
                    cwd=scenario_workspace,
                    timeout_seconds=60,
                    check=True,
                )
            )
        if self.config.allow_remote_reset:
            setup_commands.append(
                run_command(
                    ["git", "push", "--force", "origin", "main"],
                    cwd=scenario_workspace,
                    timeout_seconds=120,
                    check=True,
                )
            )
        else:
            setup_commands.append(
                run_command(
                    ["git", "push", "origin", "main"],
                    cwd=scenario_workspace,
                    timeout_seconds=120,
                )
            )

        return PreparedProject(path=scenario_workspace, repo_full_name=self.repo, setup_commands=setup_commands)

    def cleanup_workspace(self) -> None:
        self._safe_reset_local_workspace(self.config.workspace_root)

    def _safe_reset_local_workspace(self, target: Path) -> None:
        resolved_target = target.resolve()
        resolved_root = self.config.workspace_root.resolve()
        if resolved_target == resolved_root or resolved_root in resolved_target.parents:
            if resolved_target.exists():
                _remove_tree(resolved_target)
            return
        raise ValueError(f"Refusing to remove path outside Phase 4 workspace: {resolved_target}")

    def _clean_remote_state(self, repo_path: Path, setup_commands: list[CommandResult]) -> None:
        if not self.config.allow_remote_reset:
            return
        setup_commands.append(
            run_command(
                [self.config.gh_path, "pr", "list", "--repo", self.repo, "--state", "open", "--json", "number", "--limit", "100"],
                cwd=repo_path,
                timeout_seconds=60,
            )
        )
        for item in _json_list(setup_commands[-1]):
            number = str(item["number"])
            setup_commands.append(
                run_command(
                    [self.config.gh_path, "pr", "close", number, "--repo", self.repo, "--delete-branch"],
                    cwd=repo_path,
                    timeout_seconds=60,
                )
            )

        setup_commands.append(
            run_command(
                [self.config.gh_path, "issue", "list", "--repo", self.repo, "--state", "open", "--json", "number", "--limit", "100"],
                cwd=repo_path,
                timeout_seconds=60,
            )
        )
        for item in _json_list(setup_commands[-1]):
            number = str(item["number"])
            setup_commands.append(
                run_command(
                    [self.config.gh_path, "issue", "close", number, "--repo", self.repo, "--comment", "Closed by Phase 4 harness reset."],
                    cwd=repo_path,
                    timeout_seconds=60,
                )
            )

        branches = run_command(["git", "ls-remote", "--heads", "origin"], cwd=repo_path, timeout_seconds=60)
        setup_commands.append(branches)
        for line in branches.stdout.splitlines():
            if not line.strip():
                continue
            branch = line.rsplit("refs/heads/", 1)[-1]
            if branch not in {"main", "master"}:
                setup_commands.append(
                    run_command(
                        ["git", "push", "origin", "--delete", branch],
                        cwd=repo_path,
                        timeout_seconds=60,
                    )
                )

    def _clear_worktree_contents(self, repo_path: Path) -> None:
        for child in repo_path.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                _remove_tree(child)
            else:
                child.unlink()

    def _write_baseline_project(self, repo_path: Path) -> None:
        files = {
            "README.md": (
                "# Simple Flow Phase 4 Test Project\n\n"
                "This repository is reset by the Phase 4 harness before each scenario.\n"
            ),
            "pyproject.toml": (
                "[build-system]\n"
                'requires = ["setuptools>=68"]\n'
                'build-backend = "setuptools.build_meta"\n\n'
                "[project]\n"
                'name = "phase4-test-project"\n'
                'version = "0.0.1"\n'
                'requires-python = ">=3.11"\n\n'
                "[tool.pytest.ini_options]\n"
                'pythonpath = [".", "src"]\n'
            ),
            "src/simple_flow_test_app/__init__.py": '"""Small app used by the Simple Flow Phase 4 experiment."""\n',
            "src/simple_flow_test_app/health.py": (
                "def health_payload() -> dict[str, str]:\n"
                '    return {"status": "ok"}\n'
            ),
            "tests/test_health.py": (
                "from simple_flow_test_app.health import health_payload\n\n\n"
                "def test_health_payload_reports_ok() -> None:\n"
                '    assert health_payload() == {"status": "ok"}\n'
            ),
            "docs/app/usage.md": (
                "# Test Project Usage\n\n"
                "The sample app exposes a small health payload helper.\n"
            ),
            "docs/roadmap.md": "# Test Project Roadmap\n\n- UNMAPPED\n",
            ".gitignore": "__pycache__/\n.pytest_cache/\n*.egg-info/\n",
        }
        for relative, content in files.items():
            path = repo_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


def _json_list(result: CommandResult) -> list[dict[str, object]]:
    if result.exit_code != 0 or not result.stdout.strip():
        return []
    data = json.loads(result.stdout)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, onerror=_retry_remove_readonly)


def _retry_remove_readonly(
    func: Callable[[str], None],
    path: str,
    _exc_info: object,
) -> None:
    Path(path).chmod(0o700)
    func(path)
