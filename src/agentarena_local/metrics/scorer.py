from __future__ import annotations

from dataclasses import dataclass

from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.constraints import ConstraintViolation


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
    test_points = 50 if tests_passed is True else 0
    if tests_passed is None:
        test_points = 25
    breakdown = {
        "tests_passed": test_points,
        "feature_completeness": max(0, min(25, feature_completeness)),
        "constraints_passed": 15 if constraints_passed else 0,
        "minimal_diff": 10 if diff_stats.total_diff_lines <= 200 else 5,
    }
    score = sum(breakdown.values())
    if tests_passed is False:
        score = min(score, 50)
    return ScoreResult(score=max(0, min(100, score)), breakdown=breakdown)
