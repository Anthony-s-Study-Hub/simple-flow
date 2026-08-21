from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from simple_flow_gates.branch_pr import PullRequestState, validate_branch_pr_gate
from simple_flow_gates.contracts import ContractError, IssueContract, load_roadmap_targets
from simple_flow_gates.git_utils import changed_files, commit_history
from simple_flow_gates.scope import validate_documentation_gate, validate_scope_gate
from simple_flow_gates.tdd import TddEvidence, validate_tdd_gate, verify_tdd_commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="simple-flow-gates")
    subparsers = parser.add_subparsers(dest="command", required=True)

    issue_parser = subparsers.add_parser("validate-issue")
    issue_parser.add_argument("--issue-body", required=True)
    issue_parser.add_argument("--roadmap-targets", default=".simple-flow/roadmap-targets.txt")

    pr_parser = subparsers.add_parser("validate-pr")
    pr_parser.add_argument("--event-path", required=True)
    pr_parser.add_argument("--issue-body", required=True)
    pr_parser.add_argument("--roadmap-targets", default=".simple-flow/roadmap-targets.txt")
    pr_parser.add_argument("--base-ref", default="origin/main")
    pr_parser.add_argument("--tdd-evidence")
    pr_parser.add_argument(
        "--skip-tdd-command-verification",
        action="store_true",
        help="Only validate TDD evidence structure and commit ordering.",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "validate-issue":
            roadmap_targets = load_roadmap_targets(args.roadmap_targets)
            IssueContract.parse(Path(args.issue_body).read_text(encoding="utf-8"), roadmap_targets)
            print("Issue Gate PASS")
            return 0
        if args.command == "validate-pr":
            _validate_pr(args)
            print("Phase 1 PR gates PASS")
            return 0
    except ContractError as exc:
        print(f"Phase 1 gate FAIL: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unhandled command: {args.command}")
    return 2


def _validate_pr(args: argparse.Namespace) -> None:
    event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    pull_request = event["pull_request"]
    state = PullRequestState(
        body=pull_request.get("body") or "",
        head_ref=pull_request["head"]["ref"],
        base_ref=pull_request["base"]["ref"],
        is_draft=bool(pull_request.get("draft")),
        action=event.get("action", "synchronize"),
    )
    pr_contract = validate_branch_pr_gate(state)

    roadmap_targets = load_roadmap_targets(args.roadmap_targets)
    issue_contract = IssueContract.parse(
        Path(args.issue_body).read_text(encoding="utf-8"), roadmap_targets
    )
    files = changed_files(args.base_ref)
    validate_scope_gate(issue_contract, files)
    validate_documentation_gate(issue_contract, files)

    evidence = TddEvidence.from_path(args.tdd_evidence) if args.tdd_evidence else None
    validate_tdd_gate(issue_contract, pr_contract.linked_issue, evidence, commit_history(args.base_ref))
    if evidence is not None and not args.skip_tdd_command_verification:
        verify_tdd_commands(evidence)


if __name__ == "__main__":
    raise SystemExit(main())
