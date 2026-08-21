from __future__ import annotations

from simple_flow_phase4.models import StepType
from simple_flow_phase4.scenarios import (
    REQUIRED_SCENARIO_IDS,
    SMOKE_SCENARIO_IDS,
    load_scenarios,
)


def test_required_phase4_scenarios_are_defined_once() -> None:
    scenarios = load_scenarios()

    assert tuple(scenarios) == REQUIRED_SCENARIO_IDS
    assert len(scenarios) == 25


def test_scenarios_are_data_driven_with_fixed_steps_and_objective_rules() -> None:
    allowed_variables = {
        "{{draft_id}}",
        "{{issue_number}}",
        "{{pr_number}}",
        "{{branch_name}}",
    }

    for scenario in load_scenarios().values():
        assert scenario.purpose
        assert scenario.initial_state
        assert scenario.expected_objective_state
        assert scenario.forbidden_state
        assert scenario.evidence_sources
        assert scenario.pass_rules
        assert scenario.cleanup_requirements
        assert scenario.prompt_reference == f"phase4-scenario:{scenario.scenario_id}"
        assert any(step.step_type == StepType.USER_ACTION for step in scenario.ordered_steps)
        assert any(step.step_type == StepType.ASSERT for step in scenario.ordered_steps)

        for step in scenario.ordered_steps:
            assert step.step_type in StepType
            variables = {part for part in step.text.split() if part.startswith("{{") and part.endswith("}}")}
            assert variables <= allowed_variables


def test_first_version_covers_required_groups() -> None:
    scenarios = load_scenarios()

    assert [scenario_id for scenario_id in scenarios if scenario_id.startswith("A")] == [
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
        "A06",
        "A07",
    ]
    assert [scenario_id for scenario_id in scenarios if scenario_id.startswith("B")] == [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
    ]
    assert [scenario_id for scenario_id in scenarios if scenario_id.startswith("C")] == [
        "C01",
        "C02",
        "C03",
        "C04",
        "C05",
        "C06",
        "C07",
        "C08",
        "C09",
        "C10",
    ]
    assert [scenario_id for scenario_id in scenarios if scenario_id.startswith("D")] == [
        "D01",
        "D02",
        "D03",
    ]


def test_smoke_scenarios_are_small_representative_subset() -> None:
    scenarios = load_scenarios()

    assert SMOKE_SCENARIO_IDS == ("A01", "A02", "A06", "C01")
    assert set(SMOKE_SCENARIO_IDS) < set(REQUIRED_SCENARIO_IDS)
    assert [scenarios[scenario_id].group for scenario_id in SMOKE_SCENARIO_IDS] == [
        "A - Single Skill",
        "A - Single Skill",
        "A - Single Skill",
        "C - Violation And Adversarial",
    ]

    smoke_actions = "\n".join(
        step.text
        for scenario_id in SMOKE_SCENARIO_IDS
        for step in scenarios[scenario_id].ordered_steps
    )
    assert "@discussion" in smoke_actions
    assert "@issue-draft" in smoke_actions
    assert "@review-triage" in smoke_actions
    assert "@start-implement" in smoke_actions
