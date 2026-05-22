from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.scorer import (
    calculate_generation_score,
    calculate_score,
    calculate_strict_generation_score,
)
from agentarena_local.metrics.strict import StrictEvaluation


def test_scorer_clamps_score_range() -> None:
    score = calculate_score(
        tests_passed=True,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["app.py"], 1, 1, 2),
        duration_seconds=1,
    )

    assert 0 <= score.score <= 100


def test_scorer_caps_failed_tests_at_50() -> None:
    score = calculate_score(
        tests_passed=False,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["app.py"], 1, 1, 2),
        duration_seconds=1,
    )

    assert score.score <= 50


def test_generation_score_requires_test_changes_for_full_credit() -> None:
    score = calculate_generation_score(
        tests_passed=True,
        feature_completeness=25,
        constraints_passed=True,
        diff_stats=DiffStats(["src/app.py"], 20, 4, 24),
    )

    assert score.score == 90
    assert score.breakdown["test_changes"] == 0


def test_generation_score_rewards_test_changes() -> None:
    score = calculate_generation_score(
        tests_passed=True,
        feature_completeness=25,
        constraints_passed=True,
        diff_stats=DiffStats(["src/app.py", "tests/test_app.py"], 30, 8, 38),
    )

    assert score.score == 100
    assert score.breakdown["test_changes"] == 10


def test_generation_score_caps_no_change_result() -> None:
    score = calculate_generation_score(
        tests_passed=True,
        feature_completeness=25,
        constraints_passed=True,
        diff_stats=DiffStats([], 0, 0, 0),
    )

    assert score.score <= 30


def test_strict_generation_score_can_reach_full_credit() -> None:
    strict = StrictEvaluation(
        enabled=True,
        baseline_passed=False,
        fail_to_pass_passed=True,
        pass_to_pass_passed=True,
        hidden_passed=True,
        resolved=True,
        task_valid=True,
        fail_to_pass_rate=1.0,
        pass_to_pass_rate=1.0,
        hidden_rate=1.0,
    )

    score = calculate_strict_generation_score(
        strict=strict,
        feature_completeness=25,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["src/app.py", "tests/test_app.py"], 20, 5, 25),
        duration_seconds=30,
    )

    assert score.score == 100
    assert score.breakdown["fail_to_pass"] == 30
    assert score.breakdown["pass_to_pass"] == 15
    assert score.breakdown["hidden"] == 15


def test_strict_generation_score_caps_failed_fail_to_pass() -> None:
    strict = StrictEvaluation(
        enabled=True,
        baseline_passed=False,
        fail_to_pass_passed=False,
        pass_to_pass_passed=True,
        hidden_passed=True,
        resolved=False,
        task_valid=True,
        fail_to_pass_rate=0.0,
        pass_to_pass_rate=1.0,
        hidden_rate=1.0,
    )

    score = calculate_strict_generation_score(
        strict=strict,
        feature_completeness=25,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["src/app.py", "tests/test_app.py"], 20, 5, 25),
        duration_seconds=30,
    )

    assert score.score <= 60


def test_strict_generation_score_requires_test_changes_for_full_credit() -> None:
    strict = StrictEvaluation(
        enabled=True,
        baseline_passed=False,
        fail_to_pass_passed=True,
        pass_to_pass_passed=True,
        hidden_passed=True,
        resolved=True,
        task_valid=True,
        fail_to_pass_rate=1.0,
        pass_to_pass_rate=1.0,
        hidden_rate=1.0,
    )

    score = calculate_strict_generation_score(
        strict=strict,
        feature_completeness=25,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["src/app.py"], 20, 5, 25),
        duration_seconds=30,
    )

    assert score.score <= 80
    assert score.breakdown["test_changes"] == 0


def test_strict_generation_score_caps_missing_hidden_tests() -> None:
    strict = StrictEvaluation(
        enabled=True,
        baseline_passed=False,
        fail_to_pass_passed=True,
        pass_to_pass_passed=True,
        hidden_passed=None,
        resolved=True,
        task_valid=True,
        fail_to_pass_rate=1.0,
        pass_to_pass_rate=1.0,
        hidden_rate=None,
    )

    score = calculate_strict_generation_score(
        strict=strict,
        feature_completeness=25,
        constraints_passed=True,
        violations=[],
        diff_stats=DiffStats(["src/app.py", "tests/test_app.py"], 20, 5, 25),
        duration_seconds=30,
    )

    assert score.score <= 85
    assert score.breakdown["hidden"] == 0
