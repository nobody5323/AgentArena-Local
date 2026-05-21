from __future__ import annotations

from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.constraints import ConstraintViolation


def analyze_failures(
    *,
    setup_passed: bool | None,
    agent_exit_code: int,
    tests_passed: bool | None,
    diff_stats: DiffStats,
    violations: list[ConstraintViolation],
) -> list[str]:
    failures: list[str] = []
    if setup_passed is False:
        failures.append("setup_failed")
    if agent_exit_code != 0:
        failures.append("agent_runtime_error")
    if tests_passed is False:
        failures.append("test_failed")
    if diff_stats.changed_file_count == 0:
        failures.append("no_code_changed")

    violation_kinds = {violation.kind for violation in violations}
    if "forbidden_files" in violation_kinds:
        failures.append("modified_forbidden_file")
    if "max_files_changed" in violation_kinds:
        failures.append("too_many_files_changed")
    if "max_diff_lines" in violation_kinds:
        failures.append("diff_too_large")
    if "forbidden_patterns" in violation_kinds:
        failures.append("forbidden_pattern_found")

    return failures
