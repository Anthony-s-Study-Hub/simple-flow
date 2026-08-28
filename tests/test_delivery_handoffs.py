from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path

import pytest

from simple_flow_agent.delivery import (
    DeliveryBlocked,
    DeliveryRecord,
    DeliveryTarget,
    prepare_delivery,
    ready_for_review,
)
from simple_flow_agent.drafts import DraftStore
from simple_flow_agent.implementation_plan import plan_implementation


@dataclass
class FakeGateway:
    issue_number: int = 54
    pr_number: int = 81
    checks_pass: bool = True
    created_issue: int = 0
    created_branch: int = 0
    created_pr: int = 0
    marked_ready: int = 0

    def ensure_issue(self, _target: DeliveryTarget) -> tuple[int, str]:
        self.created_issue += 1
        return self.issue_number, f"https://github.example/issues/{self.issue_number}"

    def ensure_branch(self, _target: DeliveryTarget, issue_number: int) -> str:
        self.created_branch += 1
        return f"feature/{issue_number}-deterministic-delivery"

    def ensure_draft_pr(self, _target: DeliveryTarget, issue_number: int, branch: str) -> tuple[int, str]:
        self.created_pr += 1
        return self.pr_number, f"https://github.example/pull/{self.pr_number}"

    def review_state(self, _record: DeliveryRecord) -> tuple[bool, tuple[str, ...]]:
        return self.checks_pass, () if self.checks_pass else ("tdd-green-replay",)

    def mark_ready(self, _record: DeliveryRecord) -> None:
        self.marked_ready += 1


def _target(tmp_path: Path, *, route: str = "CREATE_INDEPENDENT_ISSUE") -> DeliveryTarget:
    store = DraftStore(tmp_path / "drafts")
    draft = store.create_feature(
        summary="Make delivery deterministic.",
        requirements=["Open a draft PR before implementation."],
        acceptance_criteria=["CI must pass before review."],
        scope=["simple_flow_agent/"],
        out_of_scope=["Automatic merging"],
        documentation_impact=[],
        roadmap_target="UNMAPPED",
        execution={"implementation_route": route},
    )
    plan = plan_implementation(store, draft_id=draft.draft_id)
    return DeliveryTarget.from_plan(plan, draft, repository="owner/repo", base_branch="main")


def test_prepare_delivery_creates_the_issue_branch_and_draft_pr_once(tmp_path: Path) -> None:
    target = _target(tmp_path)
    gateway = FakeGateway()

    record = prepare_delivery(target, gateway=gateway)
    repeated = prepare_delivery(target, gateway=gateway, existing=record)

    assert record.status == "DRAFT_PR_OPEN"
    assert record.issue_number == 54
    assert record.pr_number == 81
    assert gateway.created_issue == 1
    assert gateway.created_branch == 1
    assert gateway.created_pr == 1
    assert repeated == record


def test_prepare_delivery_reuses_the_current_pr_route_without_new_artifacts(tmp_path: Path) -> None:
    target = _target(tmp_path, route="UPDATE_CURRENT_PR")
    target = DeliveryTarget(
        **{**target.to_json_data(), "source_issue": 12, "source_pr": 34}
    )
    gateway = FakeGateway()

    record = prepare_delivery(target, gateway=gateway)

    assert record.issue_number == 12
    assert record.pr_number == 34
    assert gateway.created_issue == gateway.created_branch == gateway.created_pr == 0


def test_ready_for_review_requires_passing_real_required_checks(tmp_path: Path) -> None:
    target = _target(tmp_path)
    gateway = FakeGateway(checks_pass=False)
    record = prepare_delivery(target, gateway=gateway)

    with pytest.raises(DeliveryBlocked, match="tdd-green-replay"):
        ready_for_review(record, gateway=gateway)

    gateway.checks_pass = True
    ready = ready_for_review(record, gateway=gateway)

    assert ready.status == "REVIEW_READY"
    assert gateway.marked_ready == 1


def test_remote_finalizer_uses_an_explicit_noninteractive_merge_method(monkeypatch, tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "simple_flow_deploy" / "skill_resources" / "pr-finalize" / "scripts" / "finalize_remote_pr.py"
    spec = importlib.util.spec_from_file_location("finalize_remote_pr", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    commands: list[list[str]] = []

    monkeypatch.setattr(module, "_verify_ready", lambda *_args: None)
    monkeypatch.setattr(module, "_command", lambda command: commands.append(command) or "")
    monkeypatch.setattr(module, "_json_command", lambda _command: {"state": "MERGED", "mergedAt": "now", "url": "https://github.example/pull/81"})

    assert module.main(
        [
            "--pr",
            "81",
            "--repo",
            "owner/repo",
            "--approved",
            "--status-file",
            str(tmp_path / "status.json"),
            "--delivery-dir",
            str(tmp_path / "deliveries"),
            "--finalization-dir",
            str(tmp_path / "finalizations"),
        ]
    ) == 0
    assert commands == [["gh", "pr", "merge", "81", "--repo", "owner/repo", "--merge", "--delete-branch"]]


def test_remote_finalizer_resolves_the_current_delivery_from_structured_handoffs(
    tmp_path: Path,
) -> None:
    module = _finalizer_module()
    status = tmp_path / "status.json"
    deliveries = tmp_path / "deliveries"
    deliveries.mkdir()
    status.write_text(
        json.dumps(
            {
                "schema": "simple-tool-status.v1",
                "active_draft": "DRAFT-0002",
                "active_issue": 54,
                "active_pull_request": None,
            }
        ),
        encoding="utf-8",
    )
    (deliveries / "DRAFT-0002.json").write_text(
        json.dumps({"issue_number": 54, "pr_number": 81}), encoding="utf-8"
    )

    target = module._resolve_target(None, status, deliveries)

    assert target.pr_number == 81
    assert target.issue_numbers == (54,)
    assert target.source == "active-delivery"


def test_remote_finalizer_prioritizes_explicit_then_active_pull_request(tmp_path: Path) -> None:
    module = _finalizer_module()
    status = tmp_path / "status.json"
    deliveries = tmp_path / "deliveries"
    deliveries.mkdir()
    status.write_text(
        '{"active_issue": 54, "active_pull_request": 81}', encoding="utf-8"
    )

    explicit = module._resolve_target(
        "https://github.example/owner/repo/pull/82", status, deliveries
    )
    active = module._resolve_target(None, status, deliveries)

    assert (explicit.pr_number, explicit.source) == (82, "explicit-pr")
    assert (active.pr_number, active.source) == (81, "active-pull-request")


def test_remote_finalizer_refuses_to_guess_between_delivery_candidates(tmp_path: Path) -> None:
    module = _finalizer_module()
    status = tmp_path / "status.json"
    deliveries = tmp_path / "deliveries"
    deliveries.mkdir()
    status.write_text(
        '{"active_draft": null, "active_issue": 54, "active_pull_request": null}',
        encoding="utf-8",
    )
    for name, pr in (("DRAFT-0001", 81), ("DRAFT-0002", 82)):
        (deliveries / f"{name}.json").write_text(
            json.dumps({"issue_number": 54, "pr_number": pr}), encoding="utf-8"
        )

    with pytest.raises(ValueError, match="multiple delivery records"):
        module._resolve_target(None, status, deliveries)


def test_remote_finalizer_clears_only_matching_active_delivery_pointers(tmp_path: Path) -> None:
    module = _finalizer_module()
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "active_draft": "DRAFT-0002",
                "active_issue": 54,
                "active_pull_request": 81,
            }
        ),
        encoding="utf-8",
    )

    cleanup = module._clear_matching_status(status, pr_number=81, issue_numbers=(54,))
    saved = json.loads(status.read_text(encoding="utf-8"))

    assert cleanup == {"active_issue_cleared": True, "active_pull_request_cleared": True}
    assert saved == {
        "active_draft": "DRAFT-0002",
        "active_issue": None,
        "active_pull_request": None,
    }

    status.write_text(
        json.dumps(
            {
                "active_draft": "DRAFT-0003",
                "active_issue": 55,
                "active_pull_request": 82,
            }
        ),
        encoding="utf-8",
    )
    cleanup = module._clear_matching_status(status, pr_number=81, issue_numbers=(54,))

    assert cleanup == {"active_issue_cleared": False, "active_pull_request_cleared": False}
    assert json.loads(status.read_text(encoding="utf-8"))["active_pull_request"] == 82


def test_remote_finalizer_merges_and_records_scoped_cleanup(monkeypatch, tmp_path: Path) -> None:
    module = _finalizer_module()
    status = tmp_path / "status.json"
    deliveries = tmp_path / "deliveries"
    finalizations = tmp_path / "finalizations"
    deliveries.mkdir()
    status.write_text(
        '{"active_draft": "DRAFT-0001", "active_issue": 54, "active_pull_request": 81}',
        encoding="utf-8",
    )
    (deliveries / "DRAFT-0001.json").write_text(
        '{"issue_number": 54, "pr_number": 81}', encoding="utf-8"
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        module,
        "_verify_ready",
        lambda *_args: {"closingIssuesReferences": [{"number": 54}]},
    )
    monkeypatch.setattr(module, "_command", lambda command: commands.append(command) or "")
    monkeypatch.setattr(
        module,
        "_json_command",
        lambda command: (
            {"state": "CLOSED"}
            if "issue" in command
            else {
                "state": "MERGED",
                "mergedAt": "now",
                "url": "https://github.example/pull/81",
            }
        ),
    )

    assert module.main(
        [
            "--repo",
            "owner/repo",
            "--approved",
            "--status-file",
            str(status),
            "--delivery-dir",
            str(deliveries),
            "--finalization-dir",
            str(finalizations),
        ]
    ) == 0

    assert commands == [["gh", "pr", "merge", "81", "--repo", "owner/repo", "--merge", "--delete-branch"]]
    assert json.loads(status.read_text(encoding="utf-8")) == {
        "active_draft": "DRAFT-0001",
        "active_issue": None,
        "active_pull_request": None,
    }
    record = json.loads((finalizations / "PR-81.json").read_text(encoding="utf-8"))
    assert record["target_source"] == "active-pull-request"
    assert record["issue_numbers"] == [54]
    assert record["cleanup"]["head_branch"] == "not-applicable"


def _finalizer_module():
    script = Path(__file__).resolve().parents[1] / "simple_flow_deploy" / "skill_resources" / "pr-finalize" / "scripts" / "finalize_remote_pr.py"
    spec = importlib.util.spec_from_file_location("finalize_remote_pr", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
