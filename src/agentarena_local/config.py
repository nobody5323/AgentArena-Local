from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class InitResult:
    root: Path
    config_dir: Path
    config_file: Path
    overwritten: bool


DEFAULT_CONFIG = {
    "version": 1,
    "workspace": {
        "tasks_dir": "tasks",
        "runs_dir": ".agentarena/runs",
        "reports_dir": ".agentarena/reports",
    },
}


def init_workspace(path: Path, *, force: bool = False) -> InitResult:
    root = path.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_dir = root / ".agentarena"
    config_file = config_dir / "config.yaml"
    overwritten = config_file.exists()

    if overwritten and not force:
        raise FileExistsError(
            f"{config_file} already exists. Use --force to overwrite it."
        )

    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "runs").mkdir(exist_ok=True)
    (config_dir / "reports").mkdir(exist_ok=True)
    config_file.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")

    return InitResult(
        root=root,
        config_dir=config_dir,
        config_file=config_file,
        overwritten=overwritten,
    )
