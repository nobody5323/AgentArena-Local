from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.scorer import calculate_score


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
