from __future__ import annotations

from typing import Any

from simple_flow_test_harness.models import AssertionRule, Outcome, RuleResult, Scenario


def evaluate_scenario(scenario: Scenario, observed_state: dict[str, Any]) -> tuple[Outcome, list[RuleResult], str]:
    metrics = observed_state.get("metrics", {})
    results = [_evaluate_rule(rule, metrics) for rule in scenario.pass_rules]
    failures = [result for result in results if not result.passed]
    if failures:
        reason = "; ".join(f"{failure.name}: {failure.reason}" for failure in failures)
        return Outcome.FAIL, results, reason
    return Outcome.PASS, results, ""


def _evaluate_rule(rule: AssertionRule, metrics: dict[str, Any]) -> RuleResult:
    actual = _get_metric(metrics, rule.metric)
    try:
        passed = _compare(actual, rule.operator, rule.expected)
    except TypeError as exc:
        return RuleResult(
            name=rule.name,
            passed=False,
            metric=rule.metric,
            operator=rule.operator,
            expected=rule.expected,
            actual=actual,
            reason=str(exc),
        )

    reason = "" if passed else f"expected {actual!r} {rule.operator} {rule.expected!r}"
    return RuleResult(
        name=rule.name,
        passed=passed,
        metric=rule.metric,
        operator=rule.operator,
        expected=rule.expected,
        actual=actual,
        reason=reason,
    )


def _get_metric(metrics: dict[str, Any], name: str) -> Any:
    value: Any = metrics
    for part in name.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == ">=":
        return actual >= expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == "<":
        return actual < expected
    if operator == "contains":
        return str(expected) in str(actual)
    if operator == "not_contains":
        return str(expected) not in str(actual)
    if operator == "is_true":
        return bool(actual) is True
    if operator == "is_false":
        return bool(actual) is False
    raise ValueError(f"Unsupported assertion operator: {operator}")
