from __future__ import annotations

import shutil
from pathlib import Path


def install_agents_md(source: Path, worktree_root: Path) -> Path:
    destination = worktree_root / "AGENTS.md"
    shutil.copyfile(source, destination)
    return destination
