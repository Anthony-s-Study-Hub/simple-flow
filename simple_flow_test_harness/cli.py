from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
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
from simple_flow_test_harness.sdk_feasibility import (
    DEFAULT_LIVENESS_SECONDS,
    LocalModelConfig,
    PILOT_SCENARIOS,
    RemoteVerificationConfig,
    Verdict,
    capability_confidence_by_scenario,
    run_live_pilot,
    sdk_preflight,
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

    if args.command == "sdk-preflight":
        result = sdk_preflight(_sdk_config(args))
        print(json.dumps(result, indent=2))
        return 0 if result["ready"] else 2

    if args.command == "sdk-pilot":
        sdk_config = _sdk_config(args)
        if args.repetitions < 1:
            print("--repetitions must be positive.", file=sys.stderr)
            return 2
        if args.dry_run:
            print(json.dumps({
                "host": sdk_config.host,
                "endpoint": sdk_config.endpoint,
                "model": sdk_config.model,
                "structured_result_schema": "enabled",
                "scenarios": [
                    {"id": item.scenario_id, "goal": item.goal, "prompt": item.prompt, "expected": item.expected}
                    for item in PILOT_SCENARIOS
                ],
            }, indent=2))
            return 0
        project_root = Path(args.project_root).resolve()
        if not project_root.is_dir():
            print(f"Pilot project root does not exist: {project_root}", file=sys.stderr)
            return 2
        selected = tuple(item for item in PILOT_SCENARIOS if not args.scenario or item.scenario_id in args.scenario)
        remote_config = None
        remote_setup: dict[str, object] | None = None
        if any(item.remote_expectation is not None for item in selected):
            if not args.remote_verify:
                print("Selected scenario requires --remote-verify for its remote capability oracle.", file=sys.stderr)
                return 2
            if not args.allow_remote_reset:
                print("Remote SDK pilot requires --allow-remote-reset for the explicitly configured disposable test repository.", file=sys.stderr)
                return 2
            environment = Phase4Environment(config)
            prepared = environment.prepare_scenario_project("sdk-pilot-remote")
            project_root = prepared.path
            remote_config = RemoteVerificationConfig(repository=prepared.repo_full_name, gh_path=args.gh_path)
            remote_setup = {
                "project_root": str(prepared.path),
                "repository": prepared.repo_full_name,
                "commands": [command.to_json_data() for command in prepared.setup_commands],
            }
            trials = asyncio.run(
                run_live_pilot(
                    sdk_config,
                    project_root,
                    repetitions=args.repetitions,
                    scenarios=selected,
                    remote_config=remote_config,
                )
            )
        else:
            trials = asyncio.run(
                run_live_pilot(
                    sdk_config,
                    project_root,
                    repetitions=args.repetitions,
                    scenarios=selected,
                    remote_config=remote_config,
                )
            )
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "remote_setup": remote_setup,
            "trials": [
                {"scenario_id": trial.scenario_id, "verdicts": trial.verdicts, "evidence": trial.evidence}
                for trial in trials
            ],
            "capability_confidence": capability_confidence_by_scenario(trials),
        }
        report_dir = Path(args.report_dir).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"phase4-sdk-pilot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        report_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, default=str))
        print(f"Phase 4 SDK pilot report: {report_path}")
        return 0 if all(not trial.is_blocked and all(value == Verdict.PASS for value in trial.verdicts.values()) for trial in trials) else 1

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
    commands = {
        "run", "list-scenarios", "validate", "cleanup", "probe-local-llm", "probe-codex-local-llm",
        "sdk-preflight", "sdk-pilot",
    }
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
    sdk_preflight_parser = subparsers.add_parser("sdk-preflight", parents=[parent])
    sdk_preflight_parser.add_argument("--sdk-host", choices=("codex-sdk", "claude-sdk"), default="codex-sdk")
    sdk_preflight_parser.add_argument("--liveness-seconds", type=int, default=DEFAULT_LIVENESS_SECONDS)
    sdk_pilot_parser = subparsers.add_parser("sdk-pilot", parents=[parent])
    sdk_pilot_parser.add_argument("--sdk-host", choices=("codex-sdk", "claude-sdk"), default="codex-sdk")
    sdk_pilot_parser.add_argument("--project-root", default=str(source_root))
    sdk_pilot_parser.add_argument("--scenario", action="append", choices=tuple(item.scenario_id for item in PILOT_SCENARIOS))
    sdk_pilot_parser.add_argument("--repetitions", type=int, default=1)
    sdk_pilot_parser.add_argument("--liveness-seconds", type=int, default=DEFAULT_LIVENESS_SECONDS)
    sdk_pilot_parser.add_argument("--action-timeout-seconds", type=int, default=900)
    sdk_pilot_parser.add_argument("--remote-verify", action="store_true", help="Enable manifest-verified remote checks for selected remote scenarios.")
    sdk_pilot_parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(raw_args)


def _sdk_config(args: argparse.Namespace) -> LocalModelConfig:
    return LocalModelConfig(
        host=args.sdk_host,
        endpoint=args.local_llm_url,
        model=args.local_llm_model,
        liveness_seconds=args.liveness_seconds,
        action_timeout_seconds=getattr(args, "action_timeout_seconds", max(args.timeout_seconds, 900)),
    )




if __name__ == "__main__":
    raise SystemExit(main())
