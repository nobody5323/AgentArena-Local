from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_AGENT_COMMANDS = {
    "claude": "claude",
    "codex": "codex",
    "gemini": "gemini",
    "aider": "aider",
    "manual": "manual",
    "cursor": "manual",
    "cline": "manual",
    "windsurf": "manual",
}


@dataclass(frozen=True)
class InitResult:
    root: Path
    config_dir: Path
    config_file: Path
    overwritten: bool


@dataclass(frozen=True)
class AppConfig:
    root: Path
    config_file: Path
    agent_commands: dict[str, str]
    default_timeout_seconds: int | None
    keep_worktree: bool
    runs_dir: Path
    reports_dir: Path


DEFAULT_CONFIG = {
    "version": 1,
    "agents": {
        name: {"command": command}
        for name, command in DEFAULT_AGENT_COMMANDS.items()
    },
    "defaults": {
        "timeout_seconds": 1800,
        "keep_worktree": False,
    },
    "workspace": {
        "tasks_dir": "tasks",
        "runs_dir": ".agentarena/runs",
        "reports_dir": ".agentarena/reports",
    },
}


def _resolve_config_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return root / path


def load_config(path: Path | None = None) -> AppConfig:
    root = (path or Path.cwd()).expanduser().resolve()
    config_file = root / ".agentarena" / "config.yaml"
    raw = DEFAULT_CONFIG
    if config_file.exists():
        loaded = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        raw = {
            **DEFAULT_CONFIG,
            **loaded,
            "agents": {
                **DEFAULT_CONFIG["agents"],
                **loaded.get("agents", {}),
            },
            "defaults": {
                **DEFAULT_CONFIG["defaults"],
                **loaded.get("defaults", {}),
            },
            "workspace": {
                **DEFAULT_CONFIG["workspace"],
                **loaded.get("workspace", {}),
            },
        }

    agents = raw.get("agents", {})
    agent_commands = {
        name: str(value.get("command", DEFAULT_AGENT_COMMANDS.get(name, name)))
        for name, value in agents.items()
        if isinstance(value, dict)
    }
    defaults = raw.get("defaults", {})
    workspace = raw.get("workspace", {})
    timeout = defaults.get("timeout_seconds")
    return AppConfig(
        root=root,
        config_file=config_file,
        agent_commands=agent_commands,
        default_timeout_seconds=int(timeout) if timeout is not None else None,
        keep_worktree=bool(defaults.get("keep_worktree", False)),
        runs_dir=_resolve_config_path(root, str(workspace.get("runs_dir", ".agentarena/runs"))),
        reports_dir=_resolve_config_path(root, str(workspace.get("reports_dir", ".agentarena/reports"))),
    )


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
