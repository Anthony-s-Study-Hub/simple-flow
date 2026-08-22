from __future__ import annotations

import json
import re
from typing import Any

from simple_flow_test_harness.agent_backends import CODEX_BACKEND, LOCAL_OPENAI_BACKEND
from simple_flow_test_harness.models import CommandResult, RuleResult, Scenario, SkillCheckpoint, StepType


PASS = "PASS"
FAIL = "FAIL"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNKNOWN = "UNKNOWN"

ALIAS_TO_SKILL = {
    "@discussion": "discussion",
    "@documentation-curation": "documentation-curation",
    "@issue-draft": "issue-draft",
    "@start-implement": "start-implement",
    "@review-triage": "review-triage",
    "@pr-finalize": "pr-finalize",
}

DEFAULT_HELPER_SCRIPTS = {
    "documentation-curation": ("curate_documentation.py",),
    "issue-draft": ("create_draft.py",),
    "pr-finalize": ("check_pre_merge.py",),
    "review-triage": ("classify_finding.py",),
    "start-implement": ("select_path.py", "start_documentation.py"),
}


def evaluate_skill_checkpoints(
    *,
    scenario: Scenario,
    agent_backend: str,
    agent_metadata: dict[str, object],
    agent_result: CommandResult,
    objective_rule_results: list[RuleResult],
    final_state: dict[str, object],
) -> tuple[list[SkillCheckpoint], str]:
    action_texts = _action_texts(scenario, agent_metadata)
    aliases = _expected_aliases(action_texts)
    expected_helpers = _expected_helpers(action_texts, aliases)
    resolved = _resolved_skill_names(agent_metadata)
    helper_events = _helper_events(agent_result)

    checkpoints = [
        _skill_discovery_checkpoint(agent_backend, aliases, resolved),
        _instruction_exposure_checkpoint(agent_backend, aliases, resolved),
        _helper_intent_checkpoint(expected_helpers, helper_events),
        _command_shape_checkpoint(expected_helpers, helper_events),
        _helper_execution_checkpoint(expected_helpers, helper_events),
        _side_effect_checkpoint(objective_rule_results, final_state),
        _stop_point_checkpoint(agent_result),
    ]
    return checkpoints, _confidence(agent_backend, aliases, expected_helpers, checkpoints)


def _action_texts(scenario: Scenario, agent_metadata: dict[str, object]) -> list[str]:
    turns = agent_metadata.get("turns", [])
    texts = (
        [
            str(turn["user_action"])
            for turn in turns
            if isinstance(turn, dict) and str(turn.get("user_action", "")).strip()
        ]
        if isinstance(turns, list)
        else []
    )
    if texts:
        return texts
    return [
        step.text
        for step in scenario.ordered_steps
        if step.step_type == StepType.USER_ACTION
    ]


def _expected_aliases(action_texts: list[str]) -> list[str]:
    aliases: list[str] = []
    for text in action_texts:
        for alias in ALIAS_TO_SKILL:
            if alias in text and alias not in aliases:
                aliases.append(alias)
    return aliases


def _expected_helpers(action_texts: list[str], aliases: list[str]) -> list[dict[str, str]]:
    helpers: list[dict[str, str]] = []
    action_text = "\n".join(action_texts)
    for skill, script in re.findall(r"\.codex/skills/([^/\s]+)/scripts/([^\"'\s]+)", action_text):
        helpers.append({"skill": skill, "script": script.split("/")[-1], "source": "explicit"})
    if helpers:
        return helpers

    for alias in aliases:
        skill = ALIAS_TO_SKILL[alias]
        for script in DEFAULT_HELPER_SCRIPTS.get(skill, ()):
            helpers.append({"skill": skill, "script": script, "source": "skill-default"})
    return helpers


def _resolved_skill_names(agent_metadata: dict[str, object]) -> set[str]:
    names: set[str] = set()
    turns = agent_metadata.get("turns", [])
    if not isinstance(turns, list):
        return names
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        resolved = turn.get("resolved_skills", [])
        if not isinstance(resolved, list):
            continue
        for item in resolved:
            if isinstance(item, dict) and item.get("status") == "loaded" and item.get("skill"):
                names.add(str(item["skill"]))
    return names


def _helper_events(agent_result: CommandResult) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in agent_result.stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        invocation = event.get("script_invocation")
        result = event.get("result", {})
        if not invocation and isinstance(result, dict):
            invocation = result.get("script_invocation")
        if not isinstance(invocation, dict):
            continue
        result = result if isinstance(result, dict) else {}
        events.append(
            {
                "skill": str(invocation.get("skill", "")),
                "script": str(invocation.get("script", "")),
                "path": str(invocation.get("path", "")),
                "argv": result.get("argv", []),
                "exit_code": result.get("exit_code"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
            }
        )
    return events


def _skill_discovery_checkpoint(agent_backend: str, aliases: list[str], resolved: set[str]) -> SkillCheckpoint:
    if not aliases:
        return SkillCheckpoint("skill discovery", NOT_APPLICABLE, "No skill alias was present in USER_ACTION steps.")
    if agent_backend == CODEX_BACKEND:
        return SkillCheckpoint("skill discovery", UNKNOWN, "Codex backend skill loading is not exposed in harness metadata.")
    expected = {ALIAS_TO_SKILL[alias] for alias in aliases}
    missing = sorted(expected - resolved)
    status = PASS if not missing else FAIL
    details = "All expected skill aliases resolved." if not missing else f"Missing resolved skills: {', '.join(missing)}."
    return SkillCheckpoint("skill discovery", status, details, {"expected": sorted(expected), "resolved": sorted(resolved)})


def _instruction_exposure_checkpoint(agent_backend: str, aliases: list[str], resolved: set[str]) -> SkillCheckpoint:
    if not aliases:
        return SkillCheckpoint("instruction exposure", NOT_APPLICABLE, "No skill instructions were needed.")
    if agent_backend == CODEX_BACKEND:
        return SkillCheckpoint("instruction exposure", UNKNOWN, "Codex backend instruction exposure is external to the local harness.")
    expected = {ALIAS_TO_SKILL[alias] for alias in aliases}
    missing = sorted(expected - resolved)
    status = PASS if not missing else FAIL
    details = "Relevant SKILL.md context was loaded for the local backend." if not missing else f"SKILL.md context was not loaded for: {', '.join(missing)}."
    return SkillCheckpoint("instruction exposure", status, details)


def _helper_intent_checkpoint(
    expected_helpers: list[dict[str, str]], helper_events: list[dict[str, Any]]
) -> SkillCheckpoint:
    if not expected_helpers:
        return SkillCheckpoint("helper intent", NOT_APPLICABLE, "The invoked skill has no deterministic helper expectation.")
    missing = _missing_helpers(expected_helpers, helper_events)
    status = PASS if not missing else FAIL
    details = "Agent attempted the expected skill helper." if not missing else f"No observed helper invocation for: {', '.join(missing)}."
    return SkillCheckpoint("helper intent", status, details, {"observed": _helper_labels(helper_events)})


def _command_shape_checkpoint(
    expected_helpers: list[dict[str, str]], helper_events: list[dict[str, Any]]
) -> SkillCheckpoint:
    if not expected_helpers:
        return SkillCheckpoint("command shape", NOT_APPLICABLE, "No helper command was expected.")
    matching = _matching_helper_events(expected_helpers, helper_events)
    if not matching:
        return SkillCheckpoint("command shape", FAIL, "No helper command was available to inspect.")
    bad = [event for event in matching if not _argv_shape_ok(event.get("argv"))]
    status = PASS if not bad else FAIL
    details = "Helper command used executable argv without shell-only redirection." if not bad else "Helper command shape used shell-only syntax or missing argv."
    return SkillCheckpoint("command shape", status, details)


def _helper_execution_checkpoint(
    expected_helpers: list[dict[str, str]], helper_events: list[dict[str, Any]]
) -> SkillCheckpoint:
    if not expected_helpers:
        return SkillCheckpoint("helper execution", NOT_APPLICABLE, "No deterministic helper was expected.")
    matching = _matching_helper_events(expected_helpers, helper_events)
    if not matching:
        return SkillCheckpoint("helper execution", FAIL, "Expected helper did not run.")
    failed = [event for event in matching if event.get("exit_code") not in (0, "0")]
    status = PASS if not failed else FAIL
    details = "Expected helper exited successfully." if not failed else "One or more expected helper invocations exited non-zero."
    return SkillCheckpoint("helper execution", status, details, {"exit_codes": [event.get("exit_code") for event in matching]})


def _side_effect_checkpoint(
    objective_rule_results: list[RuleResult], final_state: dict[str, object]
) -> SkillCheckpoint:
    if not objective_rule_results:
        return SkillCheckpoint("side effect", UNKNOWN, "Objective rules were not evaluated for this scenario.")
    failed = [result.name for result in objective_rule_results if not result.passed]
    status = PASS if not failed else FAIL
    details = "Expected objective side effects were observed." if not failed else f"Objective side effects missing or forbidden state observed: {', '.join(failed)}."
    metrics = final_state.get("metrics", {})
    evidence = metrics if isinstance(metrics, dict) else {}
    return SkillCheckpoint("side effect", status, details, evidence)


def _stop_point_checkpoint(agent_result: CommandResult) -> SkillCheckpoint:
    output = f"{agent_result.stdout}\n{agent_result.stderr}".lower()
    if not output.strip():
        return SkillCheckpoint("stop point", UNKNOWN, "No agent output was recorded.")
    markers = ("stop_point", "finish", "human_pr_review", "documentation_draft_created", "stop")
    status = PASS if any(marker in output for marker in markers) else UNKNOWN
    details = "Agent/helper output included a recognizable stop or finish marker." if status == PASS else "No explicit stop marker was observed."
    return SkillCheckpoint("stop point", status, details)


def _confidence(
    agent_backend: str,
    aliases: list[str],
    expected_helpers: list[dict[str, str]],
    checkpoints: list[SkillCheckpoint],
) -> str:
    by_name = {checkpoint.name: checkpoint for checkpoint in checkpoints}
    if agent_backend == LOCAL_OPENAI_BACKEND and aliases:
        if by_name["skill discovery"].status == FAIL or by_name["instruction exposure"].status == FAIL:
            return "HARNESS_ISSUE"
    if expected_helpers:
        if by_name["helper intent"].status == FAIL:
            return "LOW"
        if by_name["command shape"].status == FAIL or by_name["helper execution"].status == FAIL:
            return "MEDIUM"
    if by_name["side effect"].status == FAIL:
        return "LOW" if not expected_helpers else "MEDIUM"
    if all(checkpoint.status in {PASS, NOT_APPLICABLE, UNKNOWN} for checkpoint in checkpoints):
        return "HIGH"
    return "MEDIUM"


def _missing_helpers(expected_helpers: list[dict[str, str]], helper_events: list[dict[str, Any]]) -> list[str]:
    return [
        _helper_label(helper)
        for helper in expected_helpers
        if not any(_matches_helper(helper, event) for event in helper_events)
    ]


def _matching_helper_events(
    expected_helpers: list[dict[str, str]], helper_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        event
        for event in helper_events
        if any(_matches_helper(helper, event) for helper in expected_helpers)
    ]


def _matches_helper(helper: dict[str, str], event: dict[str, Any]) -> bool:
    return helper["skill"] == event.get("skill") and helper["script"] == event.get("script")


def _helper_label(helper: dict[str, str]) -> str:
    return f"{helper['skill']}/{helper['script']}"


def _helper_labels(events: list[dict[str, Any]]) -> list[str]:
    return [f"{event.get('skill')}/{event.get('script')}" for event in events]


def _argv_shape_ok(argv: object) -> bool:
    if not isinstance(argv, list) or not argv:
        return False
    text_parts = [str(part) for part in argv]
    if any(part in {">", ">>", "|", "&&", ";"} for part in text_parts):
        return False
    if text_parts[0].lower() == "echo":
        return False
    return True
