from __future__ import annotations

import argparse
from pathlib import Path
import sys

from simple_flow_phase4.environment import (
    DEFAULT_TEST_REPO_URL,
    Phase4Environment,
    default_codex_command,
    default_gh_path,
)
from simple_flow_phase4.models import Outcome, Phase4Config
from simple_flow_phase4.reports import write_reports
from simple_flow_phase4.runner import Phase4Runner
from simple_flow_phase4.scenarios import (
    ALL_SCENARIO_IDS,
    REQUIRED_SCENARIO_IDS,
    SMOKE_ONLY_SCENARIO_IDS,
    SMOKE_SCENARIO_IDS,
    load_scenarios,
)


DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    source_root = Path(args.source_root).resolve()
    config = Phase4Config(
        source_root=source_root,
        workspace_root=Path(args.workspace_root).resolve(),
        report_dir=Path(args.report_dir).resolve(),
        test_repo_url=args.test_repo_url,
        gh_path=args.gh_path,
        codex_command=args.codex_command,
        timeout_seconds=args.timeout_seconds,
        allow_remote_reset=args.allow_remote_reset,
        dry_run=getattr(args, "dry_run", False),
        keep_workspace=getattr(args, "keep_workspace", False),
        codex_bypass_sandbox=getattr(args, "codex_bypass_sandbox", False),
        codex_model=getattr(args, "codex_model", None),
        smoke_gate=getattr(args, "smoke_gate", True),
        smoke_only=getattr(args, "smoke_only", False),
    )

    if args.command == "list-scenarios":
        for scenario in load_scenarios().values():
            print(f"{scenario.scenario_id}\t{scenario.group}\t{scenario.purpose}")
        return 0

    if args.command == "validate":
        scenarios = load_scenarios()
        print(f"Phase 4 scenario catalog valid: {len(scenarios)} scenarios")
        print(f"Full suite scenarios: {len(REQUIRED_SCENARIO_IDS)}")
        print(f"Smoke-only scenarios: {len(SMOKE_ONLY_SCENARIO_IDS)}")
        print("Required scenarios: " + ", ".join(REQUIRED_SCENARIO_IDS))
        print("Smoke scenarios: " + ", ".join(SMOKE_SCENARIO_IDS))
        return 0

    if args.command == "cleanup":
        Phase4Environment(config).cleanup_workspace()
        print(f"Cleaned Phase 4 workspace: {config.workspace_root}")
        return 0

    if args.command == "run":
        report = Phase4Runner(config).run(args.scenario)
        json_path, markdown_path = write_reports(report, config.report_dir)
        print(f"Phase 4 report JSON: {json_path}")
        print(f"Phase 4 report Markdown: {markdown_path}")
        print(f"Overall status: {report.overall_status.value}")
        if report.overall_status == Outcome.PASS:
            return 0
        if report.overall_status == Outcome.BLOCKED:
            return 2
        return 1

    raise AssertionError(f"Unhandled command: {args.command}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    commands = {"run", "list-scenarios", "validate", "cleanup"}
    if not raw_args or raw_args[0] not in commands:
        raw_args.insert(0, "run")

    parser = argparse.ArgumentParser(prog="phase4-run")
    parent = argparse.ArgumentParser(add_help=False)
    source_root = Path(__file__).resolve().parents[1]
    parent.add_argument("--source-root", default=str(source_root))
    parent.add_argument("--workspace-root", default=str(source_root / ".simple-flow" / "phase4-workspace"))
    parent.add_argument("--report-dir", default=str(source_root / ".simple-flow" / "phase4-reports"))
    parent.add_argument("--test-repo-url", default=DEFAULT_TEST_REPO_URL)
    parent.add_argument("--gh-path", default=default_gh_path())
    parent.add_argument("--codex-command", default=default_codex_command())
    parent.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parent.add_argument("--allow-remote-reset", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", parents=[parent])
    run_parser.add_argument("--scenario", action="append", choices=ALL_SCENARIO_IDS)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--keep-workspace", action="store_true")
    run_parser.add_argument("--codex-bypass-sandbox", dest="codex_bypass_sandbox", action="store_true")
    run_parser.add_argument("--codex-full-auto-sandbox", dest="codex_bypass_sandbox", action="store_false")
    run_parser.add_argument("--codex-model", default=DEFAULT_CODEX_MODEL)
    run_parser.add_argument("--smoke-only", action="store_true")
    run_parser.add_argument("--no-smoke-gate", dest="smoke_gate", action="store_false")
    run_parser.set_defaults(smoke_gate=True)
    run_parser.set_defaults(codex_bypass_sandbox=True)

    subparsers.add_parser("list-scenarios", parents=[parent])
    subparsers.add_parser("validate", parents=[parent])
    subparsers.add_parser("cleanup", parents=[parent])
    return parser.parse_args(raw_args)


if __name__ == "__main__":
    raise SystemExit(main())
