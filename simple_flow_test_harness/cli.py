from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from simple_flow_test_harness.agent_backends import (
    DEFAULT_AGENT_BACKEND,
    DEFAULT_LOCAL_LLM_MODEL,
    DEFAULT_LOCAL_LLM_URL,
    SUPPORTED_AGENT_BACKENDS,
    probe_codex_local_llm_backend,
    probe_local_openai_backend,
)
from simple_flow_test_harness.environment import (
    DEFAULT_TEST_REPO_URL,
    Phase4Environment,
    default_codex_command,
    default_gh_path,
)
from simple_flow_test_harness.models import Outcome, Phase4Config
from simple_flow_test_harness.reports import write_reports
from simple_flow_test_harness.runner import Phase4Runner
from simple_flow_test_harness.scenarios import (
    ALL_SCENARIO_IDS,
    FULL_SUITE_SCENARIO_IDS,
    PHASE5_EXTENSION_SCENARIO_IDS,
    REQUIRED_SCENARIO_IDS,
    SMOKE_ONLY_SCENARIO_IDS,
    SMOKE_SCENARIO_IDS,
    load_scenarios,
)


DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_WORKSPACE_DIRNAME = "simple-flow-test-harness-workspace"


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
        codex_oss=getattr(args, "codex_oss", False),
        codex_local_provider=getattr(args, "codex_local_provider", None),
        smoke_gate=getattr(args, "smoke_gate", True),
        smoke_only=getattr(args, "smoke_only", False),
        agent_backend=getattr(args, "agent_backend", DEFAULT_AGENT_BACKEND),
        local_llm_url=getattr(args, "local_llm_url", DEFAULT_LOCAL_LLM_URL),
        local_llm_model=getattr(args, "local_llm_model", DEFAULT_LOCAL_LLM_MODEL),
        local_llm_max_tool_calls=getattr(args, "local_llm_max_tool_calls", 8),
    )

    if args.command == "list-scenarios":
        for scenario in load_scenarios().values():
            print(f"{scenario.scenario_id}\t{scenario.group}\t{scenario.purpose}")
        return 0

    if args.command == "validate":
        scenarios = load_scenarios()
        print(f"Phase 4 scenario catalog valid: {len(scenarios)} scenarios")
        print(f"Full suite scenarios: {len(FULL_SUITE_SCENARIO_IDS)}")
        print(f"Smoke-only scenarios: {len(SMOKE_ONLY_SCENARIO_IDS)}")
        print(f"Phase 5 extension scenarios: {len(PHASE5_EXTENSION_SCENARIO_IDS)}")
        print("Required scenarios: " + ", ".join(REQUIRED_SCENARIO_IDS))
        print("Phase 5 extension scenarios: " + ", ".join(PHASE5_EXTENSION_SCENARIO_IDS))
        print("Smoke scenarios: " + ", ".join(SMOKE_SCENARIO_IDS))
        return 0

    if args.command == "cleanup":
        Phase4Environment(config).cleanup_workspace()
        print(f"Cleaned Simple Flow test harness workspace: {config.workspace_root}")
        return 0

    if args.command == "probe-local-llm":
        result = probe_local_openai_backend(
            base_url=args.local_llm_url,
            model=args.local_llm_model,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["models_ok"] and result["chat_completions_ok"] and result["tool_calls_ok"] else 1

    if args.command == "probe-codex-local-llm":
        result = probe_codex_local_llm_backend(
            base_url=args.local_llm_url,
            model=args.local_llm_model,
            codex_command=args.codex_command,
            local_provider=args.codex_local_provider or "lmstudio",
            source_root=source_root,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["responses_ok"] and result["responses_tool_calls_ok"] and result["codex_exec_ok"] else 1

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
    commands = {"run", "list-scenarios", "validate", "cleanup", "probe-local-llm", "probe-codex-local-llm"}
    if not raw_args or raw_args[0] not in commands:
        raw_args.insert(0, "run")

    parser = argparse.ArgumentParser(prog="phase4-run")
    parent = argparse.ArgumentParser(add_help=False)
    source_root = Path(__file__).resolve().parents[1]
    parent.add_argument("--source-root", default=str(source_root))
    parent.add_argument("--workspace-root", default=str(source_root / ".simple-flow" / DEFAULT_WORKSPACE_DIRNAME))
    parent.add_argument("--report-dir", default=str(source_root / ".simple-flow" / "phase4-reports"))
    parent.add_argument("--test-repo-url", default=DEFAULT_TEST_REPO_URL)
    parent.add_argument("--gh-path", default=default_gh_path())
    parent.add_argument("--codex-command", default=default_codex_command())
    parent.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parent.add_argument("--allow-remote-reset", action="store_true")
    parent.add_argument("--agent-backend", choices=SUPPORTED_AGENT_BACKENDS, default=DEFAULT_AGENT_BACKEND)
    parent.add_argument("--local-llm-url", default=DEFAULT_LOCAL_LLM_URL)
    parent.add_argument("--local-llm-model", default=DEFAULT_LOCAL_LLM_MODEL)
    parent.add_argument("--local-llm-max-tool-calls", type=int, default=8)
    parent.add_argument("--codex-oss", action="store_true")
    parent.add_argument("--codex-local-provider", choices=("lmstudio", "ollama"))

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
    subparsers.add_parser("probe-local-llm", parents=[parent])
    subparsers.add_parser("probe-codex-local-llm", parents=[parent])
    return parser.parse_args(raw_args)


if __name__ == "__main__":
    raise SystemExit(main())
