from pathlib import Path

import yaml

from agentarena_local.config import init_workspace, load_config


def test_init_writes_v0_4_config(tmp_path: Path) -> None:
    init_workspace(tmp_path)

    config_file = tmp_path / ".agentarena" / "config.yaml"
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))

    assert data["agents"]["claude"]["command"] == "claude"
    assert data["defaults"]["timeout_seconds"] == 1800
    assert data["defaults"]["keep_worktree"] is False
    assert data["workspace"]["runs_dir"] == ".agentarena/runs"


def test_load_config_resolves_paths(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    config = load_config(tmp_path)

    assert config.runs_dir == tmp_path / ".agentarena" / "runs"
    assert config.reports_dir == tmp_path / ".agentarena" / "reports"
    assert config.agent_commands["codex"] == "codex"
