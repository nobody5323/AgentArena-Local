import json
from pathlib import Path

from typer.testing import CliRunner

from agentarena_local.cli import app


runner = CliRunner()


def test_dashboard_generation_writes_html(tmp_path: Path, monkeypatch) -> None:
    result_dir = tmp_path / ".agentarena" / "runs" / "run_task" / "codex"
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_task",
                "agent": "codex",
                "variant": None,
                "task": {"id": "task", "type": "generation"},
                "score": 75,
                "tests_passed": True,
                "diff": {"changed_files": ["app.py"], "total_diff_lines": 9},
                "constraint_violations": [],
                "duration_seconds": 2.0,
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["dashboard"])

    assert result.exit_code == 0
    html = (tmp_path / ".agentarena" / "reports" / "dashboard.html").read_text(encoding="utf-8")
    assert "Diff vs score" in html
    assert "Pass rate by agent" in html
