from __future__ import annotations

from dataclasses import dataclass

from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.constraints import ConstraintViolation
from agentarena_local.metrics.strict import StrictEvaluation


@dataclass(frozen=True)
class ScoreResult:
    score: int
    breakdown: dict[str, int]


def _violation_penalty(violation: ConstraintViolation) -> int:
    if violation.severity == "high":
        return 20
    if violation.severity == "low":
        return 5
    return 10


def _diff_quality_points(diff_stats: DiffStats) -> int:
    if diff_stats.changed_file_count == 0 or diff_stats.total_diff_lines == 0:
        return 0
    if diff_stats.changed_file_count <= 3 and diff_stats.total_diff_lines <= 120:
        return 10
    if diff_stats.changed_file_count <= 5 and diff_stats.total_diff_lines <= 250:
        return 6
    return 2


def _test_change_points(diff_stats: DiffStats) -> int:
    test_like_paths = [
        path
        for path in diff_stats.changed_files
        if "test" in path.lower() or "spec" in path.lower()
    ]
    if test_like_paths:
        return 10
    return 0


def calculate_score(
    *,
    tests_passed: bool | None,
    constraints_passed: bool,
    violations: list[ConstraintViolation],
    diff_stats: DiffStats,
    duration_seconds: float,
) -> ScoreResult:
    test_points = 60 if tests_passed is True else 0
    if tests_passed is None:
        test_points = 30

    constraint_points = 20 if constraints_passed else 0
    minimal_diff_points = 10 if diff_stats.total_diff_lines <= 200 else 5
    time_points = 10 if duration_seconds <= 600 else 5

    breakdown = {
        "tests_passed": test_points,
        "constraints_passed": constraint_points,
        "minimal_diff": minimal_diff_points,
        "time_efficiency": time_points,
        "violations": -sum(_violation_penalty(violation) for violation in violations),
    }
    score = sum(breakdown.values())
    if tests_passed is False:
        score = min(score, 50)
    return ScoreResult(score=max(0, min(100, score)), breakdown=breakdown)


def calculate_generation_score(
    *,
    tests_passed: bool | None,
    feature_completeness: int,
    constraints_passed: bool,
    diff_stats: DiffStats,
) -> ScoreResult:
    test_points = 40 if tests_passed is True else 0
    if tests_passed is None:
        test_points = 15
    diff_quality_points = _diff_quality_points(diff_stats)
    test_change_points = _test_change_points(diff_stats)
    breakdown = {
        "tests_passed": test_points,
        "feature_completeness": max(0, min(25, feature_completeness)),
        "constraints_passed": 15 if constraints_passed else 0,
        "diff_quality": diff_quality_points,
        "test_changes": test_change_points,
    }
    score = sum(breakdown.values())
    if diff_stats.changed_file_count == 0:
        score = min(score, 30)
    if tests_passed is False:
        score = min(score, 50)
    return ScoreResult(score=max(0, min(100, score)), breakdown=breakdown)


def _rate_points(rate: float | None, maximum: int) -> int:
    if rate is None:
        return maximum
    return round(max(0.0, min(1.0, rate)) * maximum)


def calculate_strict_generation_score(
    *,
    strict: StrictEvaluation,
    feature_completeness: int,
    constraints_passed: bool,
    violations: list[ConstraintViolation],
    diff_stats: DiffStats,
    duration_seconds: float,
) -> ScoreResult:
    fail_to_pass_points = _rate_points(strict.fail_to_pass_rate, 30)
    pass_to_pass_points = _rate_points(strict.pass_to_pass_rate, 15)
    hidden_points = _rate_points(strict.hidden_rate, 15) if strict.hidden_rate is not None else 0
    feature_points = round(max(0, min(25, feature_completeness)) * 0.4)
    constraint_points = 8 if constraints_passed else 0
    diff_points = min(7, _diff_quality_points(diff_stats))
    test_points = _test_change_points(diff_stats)
    time_points = 3 if duration_seconds <= 600 else 1
    violation_penalty = sum(_violation_penalty(violation) for violation in violations)
    baseline_points = 2 if strict.task_valid is not False else -20

    breakdown = {
        "fail_to_pass": fail_to_pass_points,
        "pass_to_pass": pass_to_pass_points,
        "hidden": hidden_points,
        "feature_completeness": feature_points,
        "constraints_passed": constraint_points,
        "diff_quality": diff_points,
        "test_changes": test_points,
        "time_efficiency": time_points,
        "task_validity": baseline_points,
        "violations": -violation_penalty,
    }
    score = sum(breakdown.values())

    if strict.task_valid is False:
        score = min(score, 40)
    if strict.fail_to_pass_passed is False:
        score = min(score, 60)
    if strict.pass_to_pass_passed is False:
        score = min(score, 70)
    if strict.hidden_passed is False:
        score = min(score, 80)
    if diff_stats.changed_file_count == 0:
        score = min(score, 30)
    if strict.hidden_rate is None:
        score = min(score, 85)
    if test_points == 0:
        score = min(score, 80)
    if not strict.resolved:
        score = min(score, 85)

    return ScoreResult(score=max(0, min(100, score)), breakdown=breakdown)
