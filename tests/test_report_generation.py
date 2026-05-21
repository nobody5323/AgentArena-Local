import json
from pathlib import Path

from typer.testing import CliRunner

from agentarena_local.cli import app


runner = CliRunner()


def test_report_generation_writes_html(tmp_path: Path, monkeypatch) -> None:
    result_dir = tmp_path / ".agentarena" / "runs" / "run_task" / "codex"
    result_dir.mkdir(parents=True)
    (result_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_task",
                "agent": "codex",
                "variant": None,
                "task": {"id": "task", "title": "Task", "type": "debug"},
                "score": 88,
                "tests_passed": True,
                "diff": {"changed_files": ["app.py"], "total_diff_lines": 4},
                "constraint_violations": [],
                "duration_seconds": 1.0,
                "failures": [],
                "files": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["report", "--format", "html"])

    assert result.exit_code == 0
    html = (tmp_path / ".agentarena" / "reports" / "latest-report.html").read_text(encoding="utf-8")
    assert "AgentArena Local Report" in html
    assert "codex" in html
