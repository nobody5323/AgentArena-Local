from pathlib import Path

from typer.testing import CliRunner

from agentarena_local.cli import app


runner = CliRunner()


def test_init_creates_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / ".agentarena" / "config.yaml").exists()
    assert (tmp_path / ".agentarena" / "runs").is_dir()
    assert (tmp_path / ".agentarena" / "reports").is_dir()


def test_validate_accepts_example_task() -> None:
    result = runner.invoke(app, ["validate", "examples/python_debug_login/task.yaml"])

    assert result.exit_code == 0
    assert "Valid task" in result.output
    assert "python-debug-login" in result.output


def test_validate_rejects_invalid_type(tmp_path: Path) -> None:
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        """
id: bad-task
title: Bad task
type: unsupported
repo: .
description: Invalid task.
instructions: Do something.
success_criteria:
  - It should fail validation.
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", str(task_file)])

    assert result.exit_code != 0
    assert "unsupported" in result.output
