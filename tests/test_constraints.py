from agentarena_local.gitops.diff import DiffStats
from agentarena_local.metrics.constraints import check_constraints
from agentarena_local.tasks import Constraint


def test_constraints_detect_limits_and_forbidden_content() -> None:
    diff = DiffStats(
        changed_files=["app.py", "secrets.env"],
        added_lines=8,
        deleted_lines=4,
        total_diff_lines=12,
    )
    patch = "+password = 'hardcoded'\n"
    constraints = [
        Constraint(kind="max_files_changed", value="1"),
        Constraint(kind="max_diff_lines", value="10"),
        Constraint(kind="forbidden_files", value=["*.env"]),
        Constraint(kind="forbidden_patterns", value=["hardcoded"]),
    ]

    violations = check_constraints(constraints, diff, patch)

    assert {violation.kind for violation in violations} == {
        "max_files_changed",
        "max_diff_lines",
        "forbidden_files",
        "forbidden_patterns",
    }
