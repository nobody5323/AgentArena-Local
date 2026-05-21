from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.failure_analysis import extend_generation_failures
from agentarena_local.metrics.feature import evaluate_feature_slice
from agentarena_local.tasks import FeatureChecks


def test_generation_required_pattern_missing_records_failure() -> None:
    evaluation = evaluate_feature_slice(
        diff_stats=DiffStats(["README.md"], 1, 0, 1),
        patch="+hello\n",
        expected_files_may_change=["src/**", "tests/**"],
        feature_checks=FeatureChecks(required_patterns=["filter", "status"]),
    )

    failures = extend_generation_failures(
        [],
        missing_required_patterns=evaluation.missing_required_patterns,
        unexpected_files=evaluation.unexpected_files,
    )

    assert evaluation.missing_required_patterns == ["filter", "status"]
    assert "feature_required_pattern_missing" in failures
    assert "unexpected_file_changed" in failures
