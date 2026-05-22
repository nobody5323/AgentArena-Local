from __future__ import annotations

from dataclasses import asdict, dataclass

from agentarena_local.metrics.test_runner import CommandGroupResult


@dataclass(frozen=True)
class StrictEvaluation:
    enabled: bool
    baseline_passed: bool | None
    fail_to_pass_passed: bool | None
    pass_to_pass_passed: bool | None
    hidden_passed: bool | None
    resolved: bool
    task_valid: bool | None
    fail_to_pass_rate: float | None
    pass_to_pass_rate: float | None
    hidden_rate: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _pass_rate(result: CommandGroupResult) -> float | None:
    if not result.commands:
        return None
    passed = sum(1 for command in result.commands if command.succeeded)
    return passed / len(result.commands)


def summarize_strict_evaluation(
    *,
    baseline: CommandGroupResult,
    fail_to_pass: CommandGroupResult,
    pass_to_pass: CommandGroupResult,
    hidden: CommandGroupResult,
) -> StrictEvaluation:
    enabled = any(
        result.commands
        for result in (baseline, fail_to_pass, pass_to_pass, hidden)
    )
    fail_rate = _pass_rate(fail_to_pass)
    pass_rate = _pass_rate(pass_to_pass)
    hidden_rate = _pass_rate(hidden)
    task_valid = None
    if baseline.commands:
        task_valid = baseline.passed is False
    resolved = (
        enabled
        and (fail_to_pass.passed is not False)
        and (pass_to_pass.passed is not False)
        and (hidden.passed is not False)
        and (task_valid is not False)
    )
    return StrictEvaluation(
        enabled=enabled,
        baseline_passed=baseline.passed,
        fail_to_pass_passed=fail_to_pass.passed,
        pass_to_pass_passed=pass_to_pass.passed,
        hidden_passed=hidden.passed,
        resolved=resolved,
        task_valid=task_valid,
        fail_to_pass_rate=fail_rate,
        pass_to_pass_rate=pass_rate,
        hidden_rate=hidden_rate,
    )

