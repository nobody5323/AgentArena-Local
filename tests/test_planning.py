from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.failure_analysis import extend_planning_failures
from agentarena_local.planning.plan_scorer import score_plan


def test_planning_task_scores_when_code_is_not_modified() -> None:
    score = score_plan(
        plan_text="Use StudentController and StudentService. Add classId filter and pytest tests. Risk: query edge cases.",
        expected_keywords=["StudentController", "StudentService", "classId", "test"],
        modified_code=False,
    )

    assert score.score == 100
    assert score.modified_code is False


def test_planning_modified_code_failure_is_recorded() -> None:
    score = score_plan(
        plan_text="Plan mentions StudentController.",
        expected_keywords=["StudentController"],
        modified_code=DiffStats(["app.py"], 1, 0, 1).total_diff_lines > 0,
    )

    failures = extend_planning_failures([], modified_code=score.modified_code, keyword_hit_rate=score.keyword_hit_rate)

    assert "planning_modified_code" in failures


def test_expected_keyword_hit_rate_is_calculated() -> None:
    score = score_plan(
        plan_text="StudentController and classId only.",
        expected_keywords=["StudentController", "StudentService", "classId", "test"],
        modified_code=False,
    )

    assert score.keyword_hit_rate == 0.5
    assert score.keyword_hits == ["StudentController", "classId"]
