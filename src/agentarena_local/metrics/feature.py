from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict, dataclass

from agentarena_local.gitops.diff import DiffStats
from agentarena_local.tasks import FeatureChecks


@dataclass(frozen=True)
class FeatureEvaluation:
    completeness: int
    missing_required_patterns: list[str]
    forbidden_patterns_found: list[str]
    unexpected_files: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_feature_slice(
    *,
    diff_stats: DiffStats,
    patch: str,
    expected_files_may_change: list[str],
    feature_checks: FeatureChecks,
) -> FeatureEvaluation:
    missing = [
        pattern
        for pattern in feature_checks.required_patterns
        if re.search(pattern, patch, flags=re.IGNORECASE | re.MULTILINE) is None
    ]
    forbidden = [
        pattern
        for pattern in feature_checks.forbidden_patterns
        if re.search(pattern, patch, flags=re.IGNORECASE | re.MULTILINE) is not None
    ]
    unexpected: list[str] = []
    if expected_files_may_change:
        for changed_file in diff_stats.changed_files:
            if not any(fnmatch.fnmatch(changed_file, pattern) for pattern in expected_files_may_change):
                unexpected.append(changed_file)

    required_total = len(feature_checks.required_patterns)
    required_points = 20 if required_total == 0 else round(((required_total - len(missing)) / required_total) * 20)
    forbidden_points = 5 if not forbidden else 0
    completeness = max(0, min(25, required_points + forbidden_points))
    warnings = [f"Unexpected file changed: {path}" for path in unexpected]
    return FeatureEvaluation(
        completeness=completeness,
        missing_required_patterns=missing,
        forbidden_patterns_found=forbidden,
        unexpected_files=unexpected,
        warnings=warnings,
    )
