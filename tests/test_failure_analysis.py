from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.failure_analysis import analyze_failures


def test_failure_analysis_detects_no_code_changed() -> None:
    failures = analyze_failures(
        setup_passed=True,
        agent_exit_code=0,
        tests_passed=True,
        diff_stats=DiffStats([], 0, 0, 0),
        violations=[],
    )

    assert "no_code_changed" in failures
