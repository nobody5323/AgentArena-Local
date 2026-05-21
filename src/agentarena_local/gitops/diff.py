from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiffStats:
    changed_files: list[str]
    added_lines: int
    deleted_lines: int
    total_diff_lines: int

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    def to_dict(self) -> dict[str, int | list[str]]:
        return asdict(self)


def compute_diff_stats(patch: str, changed_files: list[str] | None = None) -> DiffStats:
    files = list(changed_files or [])
    if changed_files is None:
        for line in patch.splitlines():
            if line.startswith("diff --git "):
                parts = line.split(" ")
                if len(parts) >= 4:
                    files.append(parts[3].removeprefix("b/"))

    added = 0
    deleted = 0
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1

    return DiffStats(
        changed_files=sorted(set(files)),
        added_lines=added,
        deleted_lines=deleted,
        total_diff_lines=added + deleted,
    )


def collect_diff(cwd: Path) -> tuple[str, DiffStats]:
    patch = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    names_output = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    changed_files = [line.strip() for line in names_output.splitlines() if line.strip()]
    return patch, compute_diff_stats(patch, changed_files)
