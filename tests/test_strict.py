from agentarena_local.metrics.strict import summarize_strict_evaluation
from agentarena_local.metrics.test_runner import CommandGroupResult, CommandResult


def _command(exit_code: int) -> CommandResult:
    return CommandResult(
        name="check",
        command="pytest",
        exit_code=exit_code,
        stdout="",
        stderr="",
        duration_seconds=0.1,
    )


def test_strict_summary_marks_valid_resolved_task() -> None:
    strict = summarize_strict_evaluation(
        baseline=CommandGroupResult(commands=[_command(1)], passed=False),
        fail_to_pass=CommandGroupResult(commands=[_command(0)], passed=True),
        pass_to_pass=CommandGroupResult(commands=[_command(0)], passed=True),
        hidden=CommandGroupResult(commands=[_command(0)], passed=True),
    )

    assert strict.enabled is True
    assert strict.task_valid is True
    assert strict.resolved is True
    assert strict.fail_to_pass_rate == 1.0


def test_strict_summary_rejects_baseline_that_already_passes() -> None:
    strict = summarize_strict_evaluation(
        baseline=CommandGroupResult(commands=[_command(0)], passed=True),
        fail_to_pass=CommandGroupResult(commands=[_command(0)], passed=True),
        pass_to_pass=CommandGroupResult(commands=[_command(0)], passed=True),
        hidden=CommandGroupResult(commands=[], passed=None),
    )

    assert strict.task_valid is False
    assert strict.resolved is False

