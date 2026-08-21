from __future__ import annotations

import argparse
from pathlib import Path

from simple_flow_deploy.installer import (
    INSTALL_MODES,
    default_release_source,
    doctor,
    install,
    package_version,
)


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    version = package_version(ROOT)
    parser = argparse.ArgumentParser(prog="simple-flow")
    parser.add_argument(
        "--version",
        action="version",
        version=f"simple-flow {version}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Run read-only install prechecks.")
    _add_target_argument(doctor_parser)
    _add_install_options(doctor_parser, default_mode="thin")
    doctor_parser.set_defaults(func=_run_doctor)

    install_parser = subparsers.add_parser("install", help="Install Simple Flow into a project.")
    _add_target_argument(install_parser)
    _add_install_options(install_parser, default_mode="thin")
    install_parser.add_argument("--clean-target", action="store_true")
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.set_defaults(func=_run_install)

    plan_parser = subparsers.add_parser("plan", help="Show the install plan without writing files.")
    _add_target_argument(plan_parser)
    _add_install_options(plan_parser, default_mode="thin")
    plan_parser.set_defaults(func=_run_plan)

    upgrade_parser = subparsers.add_parser("upgrade", help="Reapply the selected release install.")
    _add_target_argument(upgrade_parser)
    _add_install_options(upgrade_parser, default_mode="thin")
    upgrade_parser.add_argument("--dry-run", action="store_true")
    upgrade_parser.set_defaults(func=_run_install)

    args = parser.parse_args(argv)
    return args.func(args)


def _add_target_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=".")


def _add_install_options(parser: argparse.ArgumentParser, *, default_mode: str) -> None:
    parser.add_argument("--project-name", default="new-project")
    parser.add_argument("--test-command", default="python -m pytest")
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--documentation", action="append", default=[])
    parser.add_argument("--mode", choices=sorted(INSTALL_MODES), default=default_mode)
    parser.add_argument("--release-source")
    parser.add_argument("--json", action="store_true")


def _run_doctor(args: argparse.Namespace) -> int:
    report = doctor(
        source_root=ROOT,
        target=args.target,
        project_name=args.project_name,
        test_command=args.test_command,
        scope=args.scope or ["src/"],
        documentation=args.documentation or ["docs/"],
        mode=args.mode,
        release_source=args.release_source,
    )
    if args.json:
        print(report.to_json())
    else:
        _print_doctor(report)
    return 0 if report.status in {"ok", "warning"} else 1


def _run_install(args: argparse.Namespace) -> int:
    report = install(
        source_root=ROOT,
        target=args.target,
        project_name=args.project_name,
        test_command=args.test_command,
        scope=args.scope or ["src/"],
        documentation=args.documentation or ["docs/"],
        clean_target=getattr(args, "clean_target", False),
        mode=args.mode,
        release_source=args.release_source,
        dry_run=getattr(args, "dry_run", False),
    )
    if args.json:
        print(report.to_json())
    else:
        _print_install(report, dry_run=getattr(args, "dry_run", False))
    return 0 if report.status == "success" else 1


def _run_plan(args: argparse.Namespace) -> int:
    args.dry_run = True
    return _run_install(args)


def _print_doctor(report) -> None:
    print(f"Simple Flow doctor: {report.status}")
    print(f"Target: {report.target}")
    print(f"Mode: {report.mode}")
    if report.release_source:
        print(f"Release source: {report.release_source}")
    for check in report.checks:
        print(f"- {check.name}: {check.status} - {check.message}")


def _print_install(report, *, dry_run: bool) -> None:
    action = "Plan" if dry_run else "Install"
    print(f"Simple Flow {action.lower()}: {report.status}")
    print(f"Target: {report.target}")
    print(f"Mode: {report.mode}")
    if report.release_source:
        print(f"Release source: {report.release_source}")
    print(f"Created/changed: {len(report.created)}")
    print(f"Skipped: {len(report.skipped)}")
    if report.conflicts:
        print("Conflicts:")
        for conflict in report.conflicts:
            print(f"- {conflict['path']}: {conflict['reason']}")


def current_install_command(version: str | None = None) -> str:
    resolved_version = version or package_version(ROOT)
    return (
        "uvx --from "
        f"{default_release_source(resolved_version)} "
        "simple-flow install ."
    )


if __name__ == "__main__":
    raise SystemExit(main())
