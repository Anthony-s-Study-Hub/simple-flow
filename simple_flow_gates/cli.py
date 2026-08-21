from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from simple_flow_gates.branch_pr import PullRequestState, validate_branch_pr_gate
from simple_flow_gates.contracts import ContractError, IssueContract, load_roadmap_targets
from simple_flow_gates.git_utils import changed_files, commit_history
from simple_flow_gates.scope import validate_documentation_gate, validate_scope_gate
from simple_flow_gates.tdd import (
    TddEvidence,
    validate_tdd_gate,
    verify_tdd_command,
    verify_tdd_commands,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="simple-flow-gates")
    subparsers = parser.add_subparsers(dest="command", required=True)

    issue_parser = subparsers.add_parser("validate-issue")
    _add_issue_arguments(issue_parser)

    pr_parser = subparsers.add_parser("validate-pr")
    _add_pr_arguments(pr_parser)
    _add_issue_arguments(pr_parser)
    _add_base_ref_argument(pr_parser)
    _add_tdd_evidence_argument(pr_parser)
    pr_parser.add_argument(
        "--skip-tdd-command-verification",
        action="store_true",
        help="Only validate TDD evidence structure and commit ordering.",
    )

    pr_contract_parser = subparsers.add_parser("validate-pr-contract")
    _add_pr_arguments(pr_contract_parser)

    linked_issue_parser = subparsers.add_parser("validate-linked-issue")
    _add_issue_arguments(linked_issue_parser)

    scope_parser = subparsers.add_parser("validate-scope")
    _add_issue_arguments(scope_parser)
    _add_base_ref_argument(scope_parser)

    documentation_parser = subparsers.add_parser("validate-documentation-impact")
    _add_issue_arguments(documentation_parser)
    _add_base_ref_argument(documentation_parser)

    tdd_parser = subparsers.add_parser("validate-tdd-evidence")
    _add_pr_arguments(tdd_parser)
    _add_issue_arguments(tdd_parser)
    _add_base_ref_argument(tdd_parser)
    _add_tdd_evidence_argument(tdd_parser)

    red_parser = subparsers.add_parser("verify-tdd-red")
    _add_pr_arguments(red_parser)
    _add_issue_arguments(red_parser)
    _add_base_ref_argument(red_parser)
    _add_tdd_evidence_argument(red_parser)

    green_parser = subparsers.add_parser("verify-tdd-green")
    _add_pr_arguments(green_parser)
    _add_issue_arguments(green_parser)
    _add_base_ref_argument(green_parser)
    _add_tdd_evidence_argument(green_parser)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate-issue":
            _load_issue_contract(args)
            print("Issue Contract PASS")
            return 0
        if args.command == "validate-pr":
            _validate_pr(args)
            print("Phase 1 PR gates PASS")
            return 0
        if args.command == "validate-pr-contract":
            _validate_pr_contract(args)
            print("PR Contract PASS")
            return 0
        if args.command == "validate-linked-issue":
            _load_issue_contract(args)
            print("Linked Issue Contract PASS")
            return 0
        if args.command == "validate-scope":
            _validate_scope(args, _load_issue_contract(args))
            print("Scope Governance PASS")
            return 0
        if args.command == "validate-documentation-impact":
            _validate_documentation_impact(args, _load_issue_contract(args))
            print("Documentation Impact PASS")
            return 0
        if args.command == "validate-tdd-evidence":
            pr_contract = _validate_pr_contract(args)
            issue_contract = _load_issue_contract(args)
            _validate_tdd_evidence(args, issue_contract, pr_contract.linked_issue)
            print("TDD Evidence Order PASS")
            return 0
        if args.command == "verify-tdd-red":
            _verify_tdd_phase(args, "red")
            print("TDD RED Replay PASS")
            return 0
        if args.command == "verify-tdd-green":
            _verify_tdd_phase(args, "green")
            print("TDD GREEN Replay PASS")
            return 0
    except ContractError as exc:
        print(f"Phase 1 gate FAIL: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unhandled command: {args.command}")
    return 2


def _validate_pr(args: argparse.Namespace) -> None:
    pr_contract = _validate_pr_contract(args)
    issue_contract = _load_issue_contract(args)
    _validate_scope(args, issue_contract)
    _validate_documentation_impact(args, issue_contract)

    evidence = _validate_tdd_evidence(args, issue_contract, pr_contract.linked_issue)
    if evidence is not None and not args.skip_tdd_command_verification:
        verify_tdd_commands(evidence)


def _validate_pr_contract(args: argparse.Namespace):
    event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    pull_request = event["pull_request"]
    state = PullRequestState(
        body=pull_request.get("body") or "",
        head_ref=pull_request["head"]["ref"],
        base_ref=pull_request["base"]["ref"],
        is_draft=bool(pull_request.get("draft")),
        action=event.get("action", "synchronize"),
    )
    return validate_branch_pr_gate(state)


def _load_issue_contract(args: argparse.Namespace) -> IssueContract:
    roadmap_targets = load_roadmap_targets(args.roadmap_targets)
    return IssueContract.parse(
        Path(args.issue_body).read_text(encoding="utf-8"), roadmap_targets
    )


def _validate_scope(args: argparse.Namespace, issue_contract: IssueContract) -> None:
    validate_scope_gate(issue_contract, changed_files(args.base_ref))


def _validate_documentation_impact(
    args: argparse.Namespace,
    issue_contract: IssueContract,
) -> None:
    validate_documentation_gate(issue_contract, changed_files(args.base_ref))


def _validate_tdd_evidence(
    args: argparse.Namespace,
    issue_contract: IssueContract,
    linked_issue: int,
) -> TddEvidence | None:
    evidence = TddEvidence.from_path(args.tdd_evidence) if args.tdd_evidence else None
    validate_tdd_gate(issue_contract, linked_issue, evidence, commit_history(args.base_ref))
    return evidence


def _verify_tdd_phase(args: argparse.Namespace, phase: str) -> None:
    pr_contract = _validate_pr_contract(args)
    issue_contract = _load_issue_contract(args)
    evidence = _validate_tdd_evidence(args, issue_contract, pr_contract.linked_issue)
    if evidence is not None:
        verify_tdd_command(evidence, phase)


def _add_issue_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--roadmap-targets", default=".simple-flow/roadmap-targets.txt")


def _add_pr_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--event-path", required=True)


def _add_base_ref_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-ref", default="origin/main")


def _add_tdd_evidence_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tdd-evidence")


if __name__ == "__main__":
    raise SystemExit(main())
