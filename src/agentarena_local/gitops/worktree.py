from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str


def ensure_git_repo(path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{path} is not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def get_head_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def create_worktree(repo: Path, path: Path, ref: str = "HEAD") -> Worktree:
    repo_root = ensure_git_repo(repo)
    head = get_head_commit(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(path), ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return Worktree(path=path.resolve(), head=head)


def remove_worktree(repo: Path, path: Path) -> None:
    repo_root = ensure_git_repo(repo)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
