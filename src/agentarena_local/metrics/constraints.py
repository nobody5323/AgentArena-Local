from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict, dataclass

from agentarena_local.gitops.diff import DiffStats
from agentarena_local.tasks import Constraint


@dataclass(frozen=True)
class ConstraintViolation:
    kind: str
    message: str
    severity: str = "medium"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _as_string_list(value: str | int | list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, int):
        return [str(value)]
    return [item.strip() for item in value.split(",") if item.strip()]


def check_constraints(
    constraints: list[Constraint],
    diff_stats: DiffStats,
    patch: str,
) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []

    for constraint in constraints:
        if constraint.kind == "max_files_changed":
            limit = int(constraint.value)
            if diff_stats.changed_file_count > limit:
                violations.append(
                    ConstraintViolation(
                        kind=constraint.kind,
                        message=(
                            f"Changed {diff_stats.changed_file_count} files, "
                            f"limit is {limit}."
                        ),
                        severity="medium",
                    )
                )
        elif constraint.kind == "max_diff_lines":
            limit = int(constraint.value)
            if diff_stats.total_diff_lines > limit:
                violations.append(
                    ConstraintViolation(
                        kind=constraint.kind,
                        message=(
                            f"Diff has {diff_stats.total_diff_lines} changed lines, "
                            f"limit is {limit}."
                        ),
                        severity="medium",
                    )
                )
        elif constraint.kind == "forbidden_files":
            patterns = _as_string_list(constraint.value)
            for changed_file in diff_stats.changed_files:
                if any(fnmatch.fnmatch(changed_file, pattern) for pattern in patterns):
                    violations.append(
                        ConstraintViolation(
                            kind=constraint.kind,
                            message=f"Modified forbidden file: {changed_file}.",
                            severity="high",
                        )
                    )
        elif constraint.kind == "forbidden_patterns":
            patterns = _as_string_list(constraint.value)
            for pattern in patterns:
                if re.search(pattern, patch, flags=re.MULTILINE):
                    violations.append(
                        ConstraintViolation(
                            kind=constraint.kind,
                            message=f"Diff contains forbidden pattern: {pattern}.",
                            severity="high",
                        )
                    )

    return violations
